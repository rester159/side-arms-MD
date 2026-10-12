#include "sprites.h"
#include "player.h"
#include "hud.h"
#include "palette.h"
#include "video.h"
#include "gen/assets.h"
#include "gen/boss_data.h"
#include "gen/bc_player_projectile_keys.h"

/* Display list -> SAT. Patterns come from the build-time bank (arcade 16x16
 * cells pre-converted to Genesis tiles in their palette) and are cached in
 * VRAM: 64 small slots (16x16, 4 tiles) and 13 big slots (32x32, 16 tiles,
 * one 2x2 composite). Upload = DMA straight from ROM.
 *
 * Cost per sprite matters more than anything here (the 68000 draws 10-50
 * sprites a frame, ~1 scanline of CPU each): a cached pattern is found through
 * a per-code index (two ways per code, so a flashing object's two colours both
 * stay resident) and its SAT attribute word is kept with the slot; a ROM
 * pattern comes from a direct table (spr_bank_index); a 32x32 composite is one
 * 512-byte DMA from a pre-interleaved block (spr_big) when the build made one. */

#define MAX_SPR      80
#define SMALL_SLOTS  64
#define BIG_SLOTS    13
#define NONE         0xFF
#define NORMAL_UPLOAD_BUDGET 8192
#define UPLOAD_BUDGET 6144              /* bytes of pattern DMA per frame */
#define NO_KEY       0xFFFF

typedef struct { u16 key, attr; u16 *used; } FastSprite;
#define FAST_SLOTS 128
/* A compact table frees RAM for full wheel images. Fold all four palette
 * bits into its seven-bit index; full keys resolve every hash collision. */
static inline u16 fast_hash(u16 key) { return (key ^ (key >> 8)) & (FAST_SLOTS - 1); }

typedef struct {
    FastSprite fast[FAST_SLOTS];
    u16 key[SMALL_SLOTS];               /* code | colour << 11, NO_KEY = empty */
    u16 used[SMALL_SLOTS];              /* stamp of the last frame that drew it */
    u16 attr[SMALL_SLOTS];              /* SAT attribute word: priority | palette | first tile */
    u8 idx[2048][2];                    /* code -> slot + 1 (two ways), verified by key */
    u16 hand, n;
} Cache;

static inline FastSprite *fast_entry(Cache *c, u16 key)
{
#if defined(__m68k__)
    /* Fold the eight-byte entry scale into the hash: shifts by three and
     * five replace shifts by eight and three, preserving every bucket. */
    _Static_assert(sizeof(FastSprite) == 8, "fast sprite entry stride");
    u16 offset = ((u16)(key << 3) ^ (key >> 5)) & ((FAST_SLOTS - 1) << 3);
    /* Every bucket fits a positive signed-word displacement on 68000. */
    _Static_assert(((FAST_SLOTS - 1) << 3) < 32768, "signed cache offset");
    s16 displacement = (s16)offset;
    /* Keep the signed word through address formation; range propagation
     * otherwise widens the mask back to AND.L / MOVEA.L. No instruction emits. */
    __asm__("" : "+d"(displacement));
    return (FastSprite *)((u8 *)c->fast + displacement);
#else
    return &c->fast[fast_hash(key)];
#endif
}

static Cache small, big;
static u16 repeat_small_key, repeat_small_attr;
static u16 stamp, count, budget, uploads;
static u16 spike_count;
static u8 blue_count, blue_entries[16], blue_poses[16];
static bool blue_bc;
static u8 spike_entries[MAX_SPR];
static u8 fallback[4][128];             /* runtime remap for patterns missing from the bank */
static u16 nfallback;
/* Per-frame DMA sources for submerged robot cache misses; never reused until
 * the queued frame has flushed. Cached wet poses need no further uploads. */
static u32 water_pattern[4][128];
static u8 water_uploads;
volatile u32 spr_dbg_dropped;           /* debug: sprites not shown (SAT full or pattern not resident) */
volatile u32 spr_dbg_slow;              /* debug: 32x32 composites without a pre-built block */
volatile u16 spr_dbg_slow_key[64];      /* debug: their keys (ring) */
volatile u32 spr_dbg_remap;             /* debug: 16x16 patterns missing from the bank (runtime remap) */
volatile u16 spr_dbg_remap_key[64];     /* debug: their keys (ring; tools/qa_soak.py --collect) */

u16 spr_uploads(void) { return uploads; }

/* More than 2 KiB of new patterns in the last picture signals cache churn.
 * Present the next update instead of batching additional animation changes.
 * This is a conservative scheduling hint, not a guarantee against overflow;
 * BC retains 6 KiB; Normal can stream 8 KiB on animation-heavy pictures. */
bool spr_stream_busy(void) { return budget < (blue_bc ? UPLOAD_BUDGET : NORMAL_UPLOAD_BUDGET) - 2048; }

static u16 slot_tile(const Cache *c, u16 s)
{
    if (c == &small) return VRAM_SPR_TILE + s * 4;
    if (s < 8) return VRAM_SPR_BIG_TILE + s * 16;
    if (s < 13) return VRAM_SPR_BIG2_TILE + (s - 8) * 16;
    return VRAM_SPR_TILE + 48 * 4 + (s - 13) * 16;
}

static void cache_reset(Cache *c, u16 n)
{
    memset(c, 0, sizeof(*c));
    for (u16 i = 0; i < SMALL_SLOTS; i++) c->key[i] = NO_KEY;
    for (u16 i = 0; i < FAST_SLOTS; i++) c->fast[i].key = NO_KEY;
    c->n = n;
}

void spr_init(void)
{
    /* The compact Home HUD frees its streamed weapon-bar tiles. Four extra
     * big slots also share the last sixteen small slots: retain four robot
     * recolors and their firing poses without evicting the enemy animations. */
    bool multi = game_player_limit() > 2;
    cache_reset(&small, multi ? 48 : SMALL_SLOTS);
    cache_reset(&big, multi ? 19 : BIG_SLOTS);
    pal_load(32, sprite_pal, 32);
    VDP_resetSprites();
}

void spr_begin(void)
{
    stamp++;
    count = 0;
    budget = NORMAL_UPLOAD_BUDGET;
    nfallback = 0;
    water_uploads = 0;
    spike_count = 0;
    blue_count = 0; blue_bc = FALSE;
}

void spr_bc_begin(void)
{
    spr_begin();
    budget = UPLOAD_BUDGET;
    repeat_small_key = NO_KEY;
    blue_bc = TRUE;
}

/* Runtime remap through the arcade colour's LUT (palette sprite_lut[256 + colour]). */
static const u8 *remap(u16 code, u8 colour)
{
    if (nfallback >= 4) return NULL;
    spr_dbg_remap_key[spr_dbg_remap & 63] = code | (colour << 11);
    spr_dbg_remap++;
    const u8 *src = sprite_pens_unique + (u32)sprite_pen_index[code] * 128;
    const u8 *l = sprite_pair_lut + colour * 256;
    u8 *dst = fallback[nfallback++];
    for (u16 i = 0; i < 128; i++) dst[i] = l[src[i]];
    return dst;
}

/* 16x16 pattern for (code, colour): ROM bank entry (each pattern carries its
 * own palette choice in bit 15 of the index), or a runtime remap. */
static const u8 *pattern_src(u16 code, u8 colour, u8 *pal)
{
    code &= 0x7FF;
    u16 e = spr_bank_index[code | (colour << 11)];
    if (e) { *pal = e >> 15; return spr_bank + (u32)((e & 0x7FFF) - 1) * 128; }
    *pal = sprite_lut[256 + colour] & 1;
    return remap(code, colour);
}

/* Victim slot (clock hand, skipping slots drawn this frame), or NONE. */
static u16 victim(Cache *c)
{
    /* Big animation poses recur frequently. Prefer a slot untouched last
     * frame, then fall back to the first recent slot; current-frame slots
     * stay pinned. The small cache keeps its original clock policy. */
    u16 recent = NONE;
    for (u16 k = 0; k < c->n; k++) {
        u16 i = c->hand;
        if (++c->hand == c->n) c->hand = 0;
        if (c->key[i] == NO_KEY) return i;
        if (c->used[i] == stamp) continue;
        if (c != &big || (u16)(stamp - c->used[i]) > 1) return i;
        if (recent == NONE) recent = i;
    }
    if (recent != NONE) {
        c->hand = recent + 1;
        if (c->hand == c->n) c->hand = 0;
    }
    return recent;
}

static void claim(Cache *c, u16 s, u16 code, u16 key, u8 pal)
{
    u16 old = c->key[s];
    if (old != NO_KEY) {
        FastSprite *f = fast_entry(c, old);
        if (f->key == old) f->key = NO_KEY;
    }
    c->key[s] = key; c->used[s] = stamp;
    c->attr[s] = TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, slot_tile(c, s));
    u8 *w = c->idx[code];
    w[1] = w[0]; w[0] = s + 1;
    FastSprite *f = fast_entry(c, key);
    f->key = key; f->attr = c->attr[s]; f->used = &c->used[s];
}

/* miss paths: upload into a victim slot; return the SAT attribute word, or 0 */
static __attribute__((noinline)) u16 small_miss(u16 code, u8 colour, u16 key)
{
    if (budget < 128) return 0;
    u16 s = victim(&small);
    if (s == NONE) return 0;
    u8 pal;
    const u8 *src = pattern_src(code, colour, &pal);
    if (!src) return 0;
    claim(&small, s, code, key, pal);
    DMA_queueDmaFast(DMA_VRAM, (void *)src, (VRAM_SPR_TILE + s * 4) * 32, 64, 2);
    budget -= 128; uploads++;
    return small.attr[s];
}

static __attribute__((noinline)) u16 big_miss(u16 code, u8 colour, u16 key)
{
    if (budget < 512) return 0;
    u16 blk = spr_big_index[key & 0x7fff];
    u8 pal = blk >> 15;                 /* the block's own palette choice */
    blk &= 0x7FFF;
    const u8 *block = blk ? spr_big + (u32)(blk - 1) * 512 : NULL;
    if (key & 0x8000) {
        if (!block || water_uploads == 4) return 0;
        const u32 *source = (const u32 *)block;
        u32 *wet = water_pattern[water_uploads++];
        /* Remove one pixel in four, in alternating rows. Tile rows retain
         * their original colors, outlines and shading; water shows through. */
        for (u16 i = 0; i < 128; i++)
            wet[i] = source[i] & ((i & 1) ? 0xffffffffu : 0xf0f0f0f0u);
        block = (const u8 *)wet;
    }
    if (!block) {
        /* BC's final serpent uses the existing boss bank. Reuse preconverted
         * blocks in this cache rather than rebuilding their four cells. This
         * search runs only on a miss absent from the ordinary sprite bank. */
        u16 lo = 0, hi = BOSS_BLOCKS;
        while (lo < hi) {
            u16 mid = (lo + hi) >> 1;
            if (boss_block_keys[mid] < key) lo = mid + 1; else hi = mid;
        }
        if (lo < BOSS_BLOCKS && boss_block_keys[lo] == key) {
            block = boss_block_data + (u32)lo * 512;
            pal = sprite_lut[256 + colour] & 1;
        }
    }
    const u8 *tl = NULL, *tr = NULL, *bl = NULL, *br = NULL;
    if (!block) {
        /* no pre-built block: four cells sharing the colour's fallback palette, 8 transfers */
        if (nfallback) return 0;
        pal = sprite_lut[256 + colour] & 1;
        tl = remap(code, colour); tr = remap(code + 1, colour);
        bl = remap(code + 8, colour); br = remap(code + 9, colour);
        if (!tl || !tr || !bl || !br) return 0;
    }
    u16 s = victim(&big);
    if (s == NONE) return 0;
    claim(&big, s, code, key, pal);
    u16 dst = slot_tile(&big, s) * 32;
    if (block) {
        DMA_queueDmaFast(DMA_VRAM, (void *)block, dst, 256, 2);
    } else {
        spr_dbg_slow_key[spr_dbg_slow & 63] = key;
        spr_dbg_slow++;
        /* 4x4 sprite tiles are column-major; each 16x16 cell holds its two tile
         * columns as 64-byte runs. */
        const u8 *top[2] = { tl, tr }, *bot[2] = { bl, br };
        for (u16 col = 0; col < 4; col++) {
            const u8 *t = top[col >> 1] + (col & 1) * 64, *b = bot[col >> 1] + (col & 1) * 64;
            DMA_queueDmaFast(DMA_VRAM, (void *)t, dst, 32, 2);
            DMA_queueDmaFast(DMA_VRAM, (void *)b, dst + 64, 32, 2);
            dst += 128;
        }
    }
    budget -= 512; uploads++;
    return big.attr[s];
}

/* SAT attribute word of a cached (code, colour), 0 = not cached. Hit path. */
/* Hash collisions fall back to the original two-way code index. The normal
 * draw path reads one compact entry and stamps its slot through a pointer.
 * Decode the tile code only in the slow path: a fast hit needs just the key. */
static __attribute__((noinline)) u16 lookup_slow(Cache *c, u16 key)
{
    u8 *w = c->idx[key & 0x7ff];
    for (u16 k = 0; k < 2; k++) {
        u16 s = w[k];
        if (!s || c->key[--s] != key) continue;
        c->used[s] = stamp;
        FastSprite *f = fast_entry(c, key);
        f->key = key; f->attr = c->attr[s]; f->used = &c->used[s];
        return f->attr;
    }
    return 0;
}

static inline u16 lookup_at(Cache *c, u16 key, FastSprite *f)
{
    if (f->key == key) { *f->used = stamp; return f->attr; }
    return lookup_slow(c, key);
}

static inline u16 lookup(Cache *c, u16 key)
{
    return lookup_at(c, key, fast_entry(c, key));
}

/* A successful lookup pins its slot for this frame. Repeated BC draws can
 * reuse the attribute without hashing/stamping again. spr_bc_begin invalidates
 * the small-sprite shortcut before any drawing; ordinary submissions keep lookup(). */
static inline u16 lookup_repeat(u16 key)
{
    if (repeat_small_key == key) return repeat_small_attr;
    u16 attr = lookup(&small, key);
    if (attr) { repeat_small_key = key; repeat_small_attr = attr; }
    return attr;
}

/* Map the two flip flags into SAT bits 11/12. On 68000, rotating the
 * masked word by five costs less than shifting it left eleven places. */
static inline u16 sprite_flip_bits(u8 flags)
{
#if defined(__m68k__)
    if (!__builtin_constant_p(flags)) {
        u16 bits = flags & 3;
        __asm__("ror.w #5,%0" : "+d"(bits) : : "cc");
        return bits;
    }
#endif
    return (u16)(flags & 3) << 11;
}

/* one SAT entry (SGDK's VDPSprite: y, size, link, attribute, x); flips are
 * SPR_FLIPX = 1 -> bit 11, SPR_FLIPY = 2 -> bit 12 */
static inline void emit_bits(u16 attr, s16 x, s16 y, u16 size, u16 flip_bits)
{
    /* SAT entries stay within a signed-word byte displacement. */
    _Static_assert(sizeof(vdpSpriteCache[0]) == 8 && MAX_SPR * 8 < 32768,
                   "sprite table fits a word displacement");
    s16 offset = (s16)(count << 3);
    u16 *d = (u16 *)((u8 *)vdpSpriteCache + offset);
    count++;
#if defined(__m68k__)
    /* Store the four SAT words together. Explicit registers preserve hardware
     * word order; positions intentionally wrap just as the ordinary stores do. */
    register u16 sat_y __asm__("d0") = y + 0x80;
    register u16 sat_link __asm__("d1") = size | count;
    register u16 sat_attr __asm__("d2") = attr | flip_bits;
    register u16 sat_x __asm__("d3") = x + 0x80;
    __asm__ volatile ("movem.w %%d0-%%d3,(%4)" : :
        "d"(sat_y), "d"(sat_link), "d"(sat_attr), "d"(sat_x), "a"(d) : "memory");
#else
    d[0] = y + 0x80;
    d[1] = size | count;
    d[2] = attr | flip_bits;
    d[3] = x + 0x80;
#endif
}

static inline void emit(u16 attr, s16 x, s16 y, u16 size, u8 flags)
{
    emit_bits(attr, x, y, size, sprite_flip_bits(flags));
}

void spr_16(u16 code, u8 colour, s16 x, s16 y, u8 flags)
{
    spr_key16((code & 0x7ff) | ((u16)(colour & 15) << 11), x, y, flags);
}

static __attribute__((always_inline)) inline void cached_key16(u16 key, s16 x, s16 y, u16 flags, u8 repeat, u8 prepared)
{
    if ((u16)(x + 15) >= SCREEN_W + 15 || (u16)(y + 15) >= SCREEN_H + 15) return;
    if (count >= MAX_SPR) { spr_dbg_dropped++; return; }
    u16 a = repeat ? lookup_repeat(key) : lookup(&small, key);
    if (!a) a = small_miss(key & 0x7ff, key >> 11, key);
    if (!a) { spr_dbg_dropped++; return; }
    emit_bits(a, x, y, SPRITE_SIZE(2, 2) << 8, prepared ? flags : sprite_flip_bits(flags));
}

void spr_key16(u16 key, s16 x, s16 y, u8 flags)
{
    cached_key16(key, x, y, flags, 0, 0);
}

/* Input is the already-masked four-bit colour. Rotate it into key bits 11–14. */
static inline __attribute__((always_inline)) u16 shot_palette_bits(u16 colour)
{
#if defined(__m68k__)
    __asm__("ror.w #5,%0" : "+d"(colour) : : "cc");
    return colour;
#else
    return colour << 11;
#endif
}

/* Submit a player's contiguous shot array in one call. Keep the cached path
 * inside this loop instead of marshalling four stack arguments per bullet. */
void __attribute__((noinline)) spr_shots(const Shot *shot, u16 n)
{
    /* Cache operations do not emit sprites or inspect the submitted count.
     * Keep the SAT cursor local across this batch, then publish before return. */
    u16 submitted = count;
    u16 *dst = (u16 *)vdpSpriteCache;
    if (submitted < MAX_SPR)
        dst = (u16 *)((u8 *)dst + (s16)(submitted << 3));
    for (; n; n--, shot++) {
        if (!shot->active) continue;
        s16 x = shot->x, y = shot->y;
        if ((u16)(x + 15) >= SCREEN_W + 15 || (u16)(y + 15) >= SCREEN_H + 15) continue;
        if (submitted >= MAX_SPR) { spr_dbg_dropped++; continue; }
        u16 code = shot->code & 0x7FF;
        u8 colour = shot->colour & 15;
        u16 key = code | shot_palette_bits(colour);
        u16 attr = lookup(&small, key);
        if (!attr) attr = small_miss(code, colour, key);
        if (attr) {
            submitted++;
#if defined(__m68k__)
            register u16 sat_y __asm__("d0") = y + 0x80;
            register u16 sat_link __asm__("d1") = (SPRITE_SIZE(2, 2) << 8) | submitted;
            register u16 sat_attr __asm__("d2") = attr;
            register u16 sat_x __asm__("d3") = x + 0x80;
            __asm__ volatile ("movem.w %%d0-%%d3,(%4)" : :
                "d"(sat_y), "d"(sat_link), "d"(sat_attr), "d"(sat_x), "a"(dst) : "memory");
#else
            dst[0] = y + 0x80;
            dst[1] = (SPRITE_SIZE(2, 2) << 8) | submitted;
            dst[2] = attr;
            dst[3] = x + 0x80;
#endif
            dst += 4;
        } else spr_dbg_dropped++;
    }
    count = submitted;
}

void spr_32(u16 code, u8 colour, s16 x, s16 y, u8 flags)
{
    u16 first = count;
    spr_key32((code & 0x7ff) | ((u16)(colour & 15) << 11), x, y, flags);
    if (!blue_bc && (colour & 15) == 7 && count == first + 1 && blue_count < 16) {
        u16 c = code & 0x7ff, pose = 0xffff;
        if (c >= 0x1c0 && c <= 0x1c6 && !(c & 1)) pose = (c - 0x1c0) >> 1;
        else if (c >= 0x1d0 && c <= 0x1d4 && !(c & 1)) pose = 4 + ((c - 0x1d0) >> 1);
        if (pose != 0xffff) { blue_entries[blue_count] = first; blue_poses[blue_count++] = pose; }
    }
}

static __attribute__((always_inline)) inline void cached_key32(u16 key, s16 x, s16 y, u16 flags, FastSprite *hint, u8 hinted, u8 prepared)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31) return;
    if (count >= MAX_SPR) { spr_dbg_dropped++; return; }
    u16 a = hinted ? lookup_at(&big, key, hint) : lookup(&big, key);
    if (!a) a = big_miss(key & 0x7ff, key >> 11, key);
    if (a) { emit_bits(a, x, y, SPRITE_SIZE(4, 4) << 8, prepared ? flags : sprite_flip_bits(flags)); return; }
    if (prepared) flags = (flags >> 11) & 3;
    /* big cache full: draw the four cells separately */
    u16 code = key & 0x7ff;
    u8 colour = (key >> 11) & 15;
    spr_16(code, colour, x, y, flags);
    spr_16(code + 1, colour, x + 16, y, flags);
    spr_16(code + 8, colour, x, y + 16, flags);
    spr_16(code + 9, colour, x + 16, y + 16, flags);
}

void spr_key32(u16 key, s16 x, s16 y, u8 flags)
{
    cached_key32(key, x, y, flags, NULL, 0, 0);
}

/* A 32x32 sprite whose 16 patterns the caller keeps in VRAM itself (boss
 * blocks borrowed from the BG cache, bg_reserve_blocks). pal = 0/1 -> PAL2/PAL3. */
void spr_tile32(u16 tile, u8 pal, s16 x, s16 y)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31 || count >= MAX_SPR) return;
    emit(TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, tile), x, y, SPRITE_SIZE(4, 4) << 8, 0);
}

void spr_tile32_flags(u16 tile, u8 pal, s16 x, s16 y, u8 flags)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31 || count >= MAX_SPR) return;
    emit(TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, tile), x, y, SPRITE_SIZE(4, 4) << 8, flags);
}

void spr_tile16(u16 tile, u8 pal, s16 x, s16 y)
{
    if ((u16)(x + 15) >= SCREEN_W + 15 || (u16)(y + 15) >= SCREEN_H + 15 || count >= MAX_SPR) return;
    emit(TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, tile), x, y, SPRITE_SIZE(2, 2) << 8, 0);
}

/* Repack only after the complete submission list is known. Extra pieces use
 * spare SAT entries and an ordinary unused big-cache slot; failure retains
 * the original sprite and cannot evict a pattern submitted this frame. */
static __attribute__((noinline,optimize("O2"))) void spike_strips(void)
{
    if (!spike_count || count >= MAX_SPR) return;
    u16 extra = spike_count;
    if (extra > MAX_SPR-count) extra = MAX_SPR-count;
    const u16 key = 0xc7fa; /* separate from original and packed-shot cache keys */
    u16 attr = lookup(&big, key);
    if (!attr && budget >= 384) {
        u16 slot = victim(&big);
        if (slot != NONE) {
            u8 palette = (spr_big_index[0x7d30] >> 15) & 1;
            claim(&big, slot, key & 0x7ff, key, palette);
            DMA_queueDmaFast(DMA_VRAM, (void *)bc_spike_strips,
                slot_tile(&big, slot)*32, 192, 2);
            budget -= 384; uploads++; attr = big.attr[slot];
        }
    }
    if (!attr) return;
    for (u16 j = 0; j < extra; j++) {
        VDPSprite *cap = &vdpSpriteCache[spike_entries[j]];
        /* Append the base, then splice it immediately after its cap through
         * the SAT link. No other entries need moving or relinking. */
        VDPSprite *base = &vdpSpriteCache[count];
        *base = *cap;
        u16 tile = attr & 0x7ff;
        base->attribut = (cap->attribut & 0xf800) | (tile+4);
        cap->attribut = (cap->attribut & 0xf800) | tile;
        cap->size = SPRITE_SIZE(2,2); base->size = SPRITE_SIZE(4,2);
        cap->x += 8;
        if (cap->attribut & 0x1000) cap->y += 16;
        else base->y += 16;
        cap->link = count++;
    }
}

/* Bounded composition of identical BC turret caps only. */
#include "gen/bc_cap_merge_patterns.inc"
volatile u32 dbg_cap_merges;
static __attribute__((noinline)) void cap_merge(void)
{
    if (spike_count<2 || game_player_limit()<3) return;
    u16 merged=0;
    for (u16 ai=0; ai<spike_count && merged<4; ai++) {
        u16 first=spike_entries[ai]; VDPSprite *a=&vdpSpriteCache[first];
        if (a->size!=SPRITE_SIZE(2,2) || a->x<128 || a->x>432) continue;
        u16 previous=first, next=a->link;
        for (u16 steps=0; next && steps<count; steps++) {
            VDPSprite *b=&vdpSpriteCache[next];
            if (b->size==SPRITE_SIZE(2,2) && b->attribut==a->attribut && b->y==a->y &&
                b->x>=128 && b->x<=432 && b->x+16>a->x && a->x+16>b->x) {
                /* Moving B ahead of intervening entries cannot change overlap. */
                u16 at=a->link; bool safe=TRUE;
                while (at!=next) {
                    VDPSprite *s=&vdpSpriteCache[at];
                    u16 h=8+(s->size&3)*8;
                    if (b->y<s->y+h && s->y<b->y+16) { safe=FALSE; break; }
                    at=s->link;
                }
                u16 left=a->x<b->x?a->x:b->x;
                u16 width=((a->x>b->x?a->x:b->x)+16-left+7)&~7;
                u16 bytes=width*8;
                /* Do not move the scanline fetch cutoff inside this pair.
                 * Conservatively sum all earlier sprites touching its rows. */
                u16 fetch=0, prior=0;
                while (safe && prior!=first) {
                    VDPSprite *s=&vdpSpriteCache[prior];
                    u16 w=8+((s->size>>2)&3)*8, h=8+(s->size&3)*8;
                    if (a->y<s->y+h && s->y<a->y+16) fetch+=w;
                    prior=s->link;
                }
                if (fetch+width>320) safe=FALSE;
                if (safe && budget>=bytes) {
                    s16 dx=(s16)b->x-(s16)a->x;
                    u16 variant=(dx+15)*2+!!(a->attribut&0x800);
                    u16 key=0xc780+variant;
                    u16 attr=lookup(&big,key);
                    if (!attr) {
                        u16 slot=victim(&big);
                        if (slot==NONE) return;
                        const u8 *source=cap_patterns+cap_offsets[variant];
                        if (((u32)source&0x1ffff)+bytes>0x20000) return;
                        if (!DMA_queueDmaFast(DMA_VRAM,(void *)source,slot_tile(&big,slot)*32,bytes/2,2)) return;
                        claim(&big,slot,key&0x7ff,key,(a->attribut>>13)&1);
                        budget-=bytes;uploads++;attr=big.attr[slot];
                    }
                    a->x=left;a->size=SPRITE_SIZE(width/8,2);
                    a->attribut=(a->attribut&0xf000)|(attr&0x7ff);
                    vdpSpriteCache[previous].link=b->link;
                    /* Prevent the removed cap becoming a later pair's first. */
                    b->size=0xff;
                    merged++;dbg_cap_merges++;break;
                }
            }
            previous=next;next=b->link;
        }
    }
}


#include "gen/blue_effect_shades.inc"
volatile u32 dbg_blue_layers;
static u8 blue_scratch[2][512] __attribute__((aligned(2)));
static void blue_make(u16 variant, u8 *dst)
{
    static const u16 codes[7] = {0x1c0,0x1c2,0x1c4,0x1c6,0x1d0,0x1d2,0x1d4};
    u16 code = codes[variant >> 1];
    const u8 *lut = blue_pair_lut[variant & 1];
    for (u16 column = 0; column < 4; column++) {
        u16 cell = code + (column >> 1), half = (column & 1) * 64;
        const u8 *top = sprite_pens_unique + (u32)sprite_pen_index[cell] * 128 + half;
        const u8 *bottom = sprite_pens_unique + (u32)sprite_pen_index[cell+8] * 128 + half;
        for (u16 i = 0; i < 64; i++) *dst++ = lut[top[i]];
        for (u16 i = 0; i < 64; i++) *dst++ = lut[bottom[i]];
    }
}
static void blue_finish(void)
{
    u16 scratch_used = 0;
    for (u16 k = 0; k < blue_count && count < MAX_SPR; k++) {
        u16 entry = blue_entries[k];
        VDPSprite *a = &vdpSpriteCache[entry];
        s16 top = (a->y & 511) - 128;
        /* Conservative union over every sprite touching any effect row. */
        u16 width = 32, rows = 1;
        for (u16 j = 0; j < count; j++) {
            VDPSprite *b = &vdpSpriteCache[j];
            s16 y = (b->y & 511) - 128;
            u16 h = ((b->size & 3) + 1) * 8;
            if (y < top + 32 && y + h > top) {
                width += (((b->size >> 2) & 3) + 1) * 8;
                rows++;
                if (!(b->x & 511)) { width = 321; break; }
            }
        }
        if (width > 320 || rows > 20) continue;
        u16 variant = blue_poses[k] * 2, attrs[2], misses = 0;
        for (u16 i = 0; i < 2; i++) {
            attrs[i] = lookup(&big, 0xc800 + variant + i);
            if (!attrs[i]) misses++;
        }
        u16 free = 0;
        for (u16 i = 0; i < big.n; i++) if (big.used[i] != stamp) free++;
        if (free < misses || budget < misses * 512 || scratch_used + misses > 2) continue;
        bool ready = TRUE;
        for (u16 i = 0; i < 2; i++) {
            if (attrs[i]) continue;
            u8 *source = blue_scratch[scratch_used++];
            blue_make(variant+i, source);
            u16 slot = victim(&big);
            if (slot == NONE || !DMA_queueDmaFast(DMA_VRAM, (void *)source, slot_tile(&big, slot)*32, 256, 2)) {
                ready = FALSE; break;
            }
            u16 key = 0xc800 + variant + i;
            claim(&big, slot, key & 0x7ff, key, 1-i);
            attrs[i] = big.attr[slot]; budget -= 512; uploads++;
        }
        if (!ready) continue;
        VDPSprite *b = &vdpSpriteCache[count];
        *b = *a;
        u16 control = a->attribut & (0x8000 | 0x1800);
        a->attribut = (attrs[0] & 0x67ff) | control;
        b->attribut = (attrs[1] & 0x67ff) | control;
        a->link = count++;
        dbg_blue_layers++;
    }
}

void spr_end(void)
{
    if (!count) {
        VDP_setSpriteFull(0, -32, -32, SPRITE_SIZE(1, 1), 0, 0);
        VDP_updateSprites(1, DMA_QUEUE);
        return;
    }
    VDP_setSpriteLink(count - 1, 0);
    spike_strips();
    cap_merge();
    blue_finish();
    VDP_updateSprites(count, DMA_QUEUE);
}

void spr_under_window(u16 height)
{
    for (u16 i = 0; i < count; i++)
        if (vdpSpriteCache[i].y < 128+height) VDP_setSpritePriority(i, FALSE);
}

void spr_bc_straight3(s16 x, s16 y, u8 flags, u8 ascending)
{
    static u8 patterns[2][256] __attribute__((aligned(256)));
    static u8 ready, palette;
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 15) >= SCREEN_H + 15) return;
    if (!ready) {
        const u8 *src = pattern_src(BC_PROJECTILE_1B8_KEY & 0x7ff, BC_PROJECTILE_1B8_KEY >> 11, &palette);
        if (!src) return;
        for (u16 i = 0; i < 64; i++) {
            u8 left = src[i], right = src[i+64];
            for (u16 order = 0; order < 2; order++) {
                u8 front = order ? right : left, back = order ? left : right;
                u8 overlap = (front & 0xf0 ? front & 0xf0 : back & 0xf0) |
                    (front & 15 ? front & 15 : back & 15);
                patterns[order][i] = left;
                patterns[order][i+64] = patterns[order][i+128] = overlap;
                patterns[order][i+192] = right;
            }
        }
        ready = 1;
    }
    u8 order = !!ascending ^ (flags & 1);
    u16 code = 0x7f8 + order, key = 0xc000 | code;
    u16 attr = lookup(&big, key);
    if (!attr && budget >= 256) {
        u16 slot = victim(&big);
        if (slot != NONE) {
            claim(&big, slot, code, key, palette);
            DMA_queueDmaFast(DMA_VRAM, patterns[order], slot_tile(&big, slot)*32, 128, 2);
            budget -= 256; uploads++; attr = big.attr[slot];
        }
    }
    if (attr && count < MAX_SPR) emit(attr, x, y, SPRITE_SIZE(4, 2) << 8, flags);
    else {
        /* Preserve submission priority if the big cache cannot hold a strip. */
        for (u16 i = 0; i < 3; i++) spr_16(BC_PROJECTILE_1B8_KEY & 0x7ff, BC_PROJECTILE_1B8_KEY >> 11, x + (ascending ? i : 2-i)*8, y, flags);
    }
}

u16 spr_mark(void) { return count; }

void spr_scene_palettes(u16 first)
{
    for (u16 i = first; i < count; i++) {
        u16 *entry = (u16 *)&vdpSpriteCache[i];
        entry[2] &= ~0x4000;
    }
}

/* BC actor submission can inline its cached path without expanding the
 * Normal-mode renderer. Keep the same clipping, budget and fallback rules. */
__attribute__((always_inline)) inline void spr_bc_key16(u16 key, s16 x, s16 y, u8 flags)
{
    cached_key16(key, x, y, flags, 1, 0);
}

__attribute__((always_inline)) inline void spr_bc_key32(u16 key, s16 x, s16 y, u8 flags)
{
    cached_key32(key, x, y, flags, NULL, 0, 0);
}

void *spr_bc_bucket(u16 key, u8 size)
{
    return fast_entry(size == 32 ? &big : &small, key);
}

__attribute__((always_inline)) inline void spr_bc_hint32(void *bucket, u16 key, s16 x, s16 y, u8 flags)
{
    cached_key32(key, x, y, flags, bucket, 1, 0);
}

/* Actor poses cache hardware flip bits; the other callers keep logical flags. */
__attribute__((always_inline)) inline void spr_bc_bits16(u16 key, s16 x, s16 y, u16 bits)
{
    cached_key16(key, x, y, bits, 1, 1);
}

static __attribute__((noinline)) void crop_fallback(u16 key, s16 x, s16 y, u16 bits)
{
    cached_key32(key, x, y, bits, NULL, 0, 1);
}

/* The first surfacer pose has no pens in its outer eight-pixel rows.
 * Crop both rows with one sprite entry and one existing big-cache slot. */
void __attribute__((noinline)) spr_bc_surfacer32(s16 x, s16 y, u16 bits)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31) return;
    if (count >= MAX_SPR) { spr_dbg_dropped++; return; }
    const u16 key = 0xc7fb;
    u16 attr = lookup(&big, key);
    if (!attr && budget >= 256) {
        u16 slot = victim(&big);
        if (slot != NONE) {
            claim(&big, slot, key & 0x7ff, key, spr_big_index[0x250] >> 15);
            DMA_queueDmaFast(DMA_VRAM, (void *)bc_surfacer_strip,
                            slot_tile(&big, slot)*32, 128, 2);
            budget -= 256; uploads++; attr = big.attr[slot];
        }
    }
    if (attr) emit_bits(attr, x, y + 8, SPRITE_SIZE(4,2) << 8, bits);
    else crop_fallback(0x250, x, y, bits);
}

/* Cropping the bottom row moves the origin only when vertically flipped. */
void __attribute__((noinline)) spr_bc_pod32(s16 x, s16 y, u16 bits)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31) return;
    if (count >= MAX_SPR) { spr_dbg_dropped++; return; }
    const u16 key = 0xc7fc;
    u16 attr = lookup(&big, key);
    if (!attr && budget >= 384) {
        u16 slot = victim(&big);
        if (slot != NONE) {
            claim(&big, slot, key & 0x7ff, key, spr_big_index[0x7ed6] >> 15);
            DMA_queueDmaFast(DMA_VRAM, (void *)bc_pod_strip,
                            slot_tile(&big, slot)*32, 192, 2);
            budget -= 384; uploads++; attr = big.attr[slot];
        }
    }
    if (attr) emit_bits(attr, x, y + (bits & 0x1000 ? 8 : 0), SPRITE_SIZE(4,3) << 8, bits);
    else crop_fallback(0x7ed6, x, y, bits);
}

__attribute__((always_inline)) inline void spr_bc_bits32(void *bucket, u16 key, s16 x, s16 y, u16 bits)
{
    cached_key32(key, x, y, bits, bucket, 1, 1);
}

void spr_bc_spike32(void *bucket, s16 x, s16 y, u16 bits)
{
    u16 first = count;
    cached_key32(0x7d30, x, y, bits, bucket, 1, 1);
    if (count == first + 1 && vdpSpriteCache[first].size == SPRITE_SIZE(4,4))
        spike_entries[spike_count++] = first;
}
