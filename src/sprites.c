#include "sprites.h"
#include "palette.h"
#include "video.h"
#include "gen/assets.h"

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
#define UPLOAD_BUDGET 6144              /* bytes of pattern DMA per frame */
#define NO_KEY       0xFFFF

typedef struct {
    u16 key[SMALL_SLOTS];               /* code | colour << 11, NO_KEY = empty */
    u16 used[SMALL_SLOTS];              /* stamp of the last frame that drew it */
    u16 attr[SMALL_SLOTS];              /* SAT attribute word: priority | palette | first tile */
    u8 idx[2048][2];                    /* code -> slot + 1 (two ways), verified by key */
    u16 hand, n;
} Cache;
static Cache small, big;
static u16 stamp, count, budget, uploads;
static u8 fallback[4][128];             /* runtime remap for patterns missing from the bank */
static u16 nfallback;
volatile u32 spr_dbg_dropped;           /* debug: sprites not shown (SAT full or pattern not resident) */
volatile u32 spr_dbg_slow;              /* debug: 32x32 composites without a pre-built block */
volatile u16 spr_dbg_slow_key[64];      /* debug: their keys (ring) */
volatile u32 spr_dbg_remap;             /* debug: 16x16 patterns missing from the bank (runtime remap) */
volatile u16 spr_dbg_remap_key[64];     /* debug: their keys (ring; tools/qa_soak.py --collect) */

u16 spr_uploads(void) { return uploads; }

static u16 slot_tile(const Cache *c, u16 s)
{
    if (c == &small) return VRAM_SPR_TILE + s * 4;
    return s < 8 ? VRAM_SPR_BIG_TILE + s * 16 : VRAM_SPR_BIG2_TILE + (s - 8) * 16;
}

static void cache_reset(Cache *c, u16 n)
{
    memset(c, 0, sizeof(*c));
    for (u16 i = 0; i < SMALL_SLOTS; i++) c->key[i] = NO_KEY;
    c->n = n;
}

void spr_init(void)
{
    cache_reset(&small, SMALL_SLOTS);
    cache_reset(&big, BIG_SLOTS);
    pal_load(32, sprite_pal, 32);
    VDP_resetSprites();
}

void spr_begin(void)
{
    stamp++;
    count = 0;
    budget = UPLOAD_BUDGET;
    nfallback = 0;
}

/* Runtime remap through the arcade colour's LUT (palette sprite_lut[256 + colour]). */
static const u8 *remap(u16 code, u8 colour)
{
    if (nfallback >= 4) return NULL;
    spr_dbg_remap_key[spr_dbg_remap & 63] = code | (colour << 11);
    spr_dbg_remap++;
    const u8 *src = sprite_pens + (u32)code * 128;
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
    for (u16 k = 0; k < c->n; k++) {
        u16 i = c->hand;
        if (++c->hand == c->n) c->hand = 0;
        if (c->key[i] == NO_KEY || c->used[i] != stamp) return i;
    }
    return NONE;
}

static void claim(Cache *c, u16 s, u16 code, u16 key, u8 pal)
{
    c->key[s] = key; c->used[s] = stamp;
    c->attr[s] = TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, slot_tile(c, s));
    u8 *w = c->idx[code];
    w[1] = w[0]; w[0] = s + 1;
}

/* miss paths: upload into a victim slot; return the SAT attribute word, or 0 */
static u16 small_miss(u16 code, u8 colour, u16 key)
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

static u16 big_miss(u16 code, u8 colour, u16 key)
{
    if (budget < 512) return 0;
    u16 blk = spr_big_index[key];
    u8 pal = blk >> 15;                 /* the block's own palette choice */
    blk &= 0x7FFF;
    const u8 *tl = NULL, *tr = NULL, *bl = NULL, *br = NULL;
    if (!blk) {
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
    if (blk) {
        DMA_queueDmaFast(DMA_VRAM, (void *)(spr_big + (u32)(blk - 1) * 512), dst, 256, 2);
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
static inline u16 lookup(Cache *c, u16 code, u16 key)
{
    u8 *w = c->idx[code];
    u16 s = w[0];
    if (s && c->key[--s] == key) { c->used[s] = stamp; return c->attr[s]; }
    s = w[1];
    if (s && c->key[--s] == key) { c->used[s] = stamp; w[1] = w[0]; w[0] = s + 1; return c->attr[s]; }
    return 0;
}

/* one SAT entry (SGDK's VDPSprite: y, size, link, attribute, x); flips are
 * SPR_FLIPX = 1 -> bit 11, SPR_FLIPY = 2 -> bit 12 */
static inline void emit(u16 attr, s16 x, s16 y, u16 size, u8 flags)
{
    u16 *d = (u16 *)&vdpSpriteCache[count];
    count++;
    d[0] = y + 0x80;
    d[1] = size | count;
    d[2] = attr | ((u16)(flags & 3) << 11);
    d[3] = x + 0x80;
}

void spr_16(u16 code, u8 colour, s16 x, s16 y, u8 flags)
{
    if ((u16)(x + 15) >= SCREEN_W + 15 || (u16)(y + 15) >= SCREEN_H + 15) return;
    if (count >= MAX_SPR) { spr_dbg_dropped++; return; }
    colour &= 15;
    code &= 0x7FF;
    u16 key = code | (colour << 11);
    u16 a = lookup(&small, code, key);
    if (!a) a = small_miss(code, colour, key);
    if (!a) { spr_dbg_dropped++; return; }
    emit(a, x, y, SPRITE_SIZE(2, 2) << 8, flags);
}

void spr_32(u16 code, u8 colour, s16 x, s16 y, u8 flags)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31) return;
    if (count >= MAX_SPR) { spr_dbg_dropped++; return; }
    colour &= 15;
    code &= 0x7FF;
    u16 key = code | (colour << 11);
    u16 a = lookup(&big, code, key);
    if (!a) a = big_miss(code, colour, key);
    if (a) { emit(a, x, y, SPRITE_SIZE(4, 4) << 8, flags); return; }
    /* big cache full: draw the four cells separately */
    spr_16(code, colour, x, y, flags);
    spr_16(code + 1, colour, x + 16, y, flags);
    spr_16(code + 8, colour, x, y + 16, flags);
    spr_16(code + 9, colour, x + 16, y + 16, flags);
}

/* A 32x32 sprite whose 16 patterns the caller keeps in VRAM itself (boss
 * blocks borrowed from the BG cache, bg_reserve_blocks). pal = 0/1 -> PAL2/PAL3. */
void spr_tile32(u16 tile, u8 pal, s16 x, s16 y)
{
    if ((u16)(x + 31) >= SCREEN_W + 31 || (u16)(y + 31) >= SCREEN_H + 31 || count >= MAX_SPR) return;
    emit(TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, tile), x, y, SPRITE_SIZE(4, 4) << 8, 0);
}

void spr_tile16(u16 tile, u8 pal, s16 x, s16 y)
{
    if ((u16)(x + 15) >= SCREEN_W + 15 || (u16)(y + 15) >= SCREEN_H + 15 || count >= MAX_SPR) return;
    emit(TILE_ATTR_FULL(PAL2 + (pal & 1), 1, 0, 0, tile), x, y, SPRITE_SIZE(2, 2) << 8, 0);
}

void spr_end(void)
{
    if (!count) {
        VDP_setSpriteFull(0, -32, -32, SPRITE_SIZE(1, 1), 0, 0);
        VDP_updateSprites(1, DMA_QUEUE_COPY);
        return;
    }
    VDP_setSpriteLink(count - 1, 0);
    VDP_updateSprites(count, DMA_QUEUE_COPY);
}
