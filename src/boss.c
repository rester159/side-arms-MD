#include "boss_int.h"
#include "bg.h"
#include "enemies.h"
#include "hud.h"
#include "gen/assets.h"

/* Boss framework: dispatch from the level timeline, shared helpers (aim,
 * collisions, score, HUD state), the boss projectile/effect pool and the death
 * explosion task. Design and arcade sources: docs/bosses.md. */

/* Other modules' services, used when linked in (weak: the boss module also
 * builds alone; each has a local fallback or is skipped). */
#pragma weak enemy_bullet_spawn
#pragma weak enemy_bullets_live
#pragma weak enemies_clear
#pragma weak fx_explosion
void item_spawn_pow(s16 x, s16 y) __attribute__((weak));
extern u8 en_target_y __attribute__((weak)), en_target_x2 __attribute__((weak));

s16 boss_shift;
BossHud boss_hud;
static u8 kind;                         /* 0 none, 1 sprite, 2 wheel, 3 final */

/* ======================================================================= helpers */

void boss_hud_set(bool on, u8 bars, u8 hits)
{
    if (bars != boss_hud.bars || on != boss_hud.active) boss_hud.serial++;
    boss_hud.active = on; boss_hud.bars = bars; boss_hud.hits = hits;
}

u8 boss_rng(u8 *seed, u8 add) { return *seed += add; }

/* $E020/$E021: the target player chosen by the enemy module every 8 frames
 * (B2:$813A); fallback P1, else P2, else ($78, $E0) ($820F). */
void boss_target(s16 *y, s16 *x)
{
    if (&en_target_y && &en_target_x2) {
        *y = en_target_y; *x = en_target_x2 * 2 + boss_shift;
        return;
    }
    for (u16 i = 0; i < 2; i++) {
        Player *p = &players[i];
        if (p->state == PL_ALIVE) { *y = raw_y(p->y); *x = raw_x(p->x); return; }
    }
    *y = 0x78; *x = 0xE0 * 2;
}

static u8 clamp8(s16 v) { return v < 0 ? 0 : v > 255 ? 255 : v; }

/* $0715: octant (target above: +4, left: +2, steep: +1) and a 5-sector ratio
 * test of minor against major/8 x 1, 3, 5, 7 in (y, x/2) space; table $0780. */
u8 boss_aim_at(s16 y, s16 x, s16 ty, s16 tx)
{
    u8 c = 0;
    s16 dy = clamp8(ty) - clamp8(y), dx = clamp8(tx >> 1) - clamp8(x >> 1);
    if (dy < 0) { dy = -dy; c = 4; }
    if (dx < 0) { dx = -dx; c += 2; }
    u8 d = dx, e = dy;
    if (d < e) { d = dy; e = dx; if (c == 0 || c == 4) c++; }
    else if (c == 2 || c == 6) c++;
    u8 b = (d >> 3) & 0x1F, l = 0;
    if (b < e) { l = 1; if (3 * b < e) { l = 2; if (5 * b < e) { l = 3; if (7 * b < e) l = 4; } } }
    return aim_sector[(c << 3) | l];
}

u8 boss_aim(s16 y, s16 x)
{
    s16 ty, tx;
    boss_target(&ty, &tx);
    return boss_aim_at(y, x, ty, tx);
}

volatile u8 boss_dbg_autohit;    /* test hook (QA bot): every boss hit test also counts one P1 shot */

u8 boss_shots(s16 py, s16 px, u8 c, u8 d2, Player **who)
{
    u8 n = 0;
    if (boss_dbg_autohit) { *who = &players[0]; n = 1; }
    for (u16 i = 0; i < 2; i++) {
        Player *p = &players[i];
        for (u16 k = 0; k < MAX_SHOTS; k++) {
            Shot *s = &p->shots[k];
            if (s->active != 1) continue;
            s16 dy = py - raw_y(s->y), dx = px - raw_x(s->x);
            if (dy < 0) dy = -dy;
            if (dx < 0) dx = -dx;
            if (dy >= c + s->half_h || dx >= d2 + s->half_w) continue;
            shot_hit(p, s);
            *who = p; n++;
        }
    }
    return n;
}

bool boss_touch(s16 py, s16 px, u8 e, u8 f2, s8 oy, s8 ox)
{
    bool hit = FALSE;
    for (u16 i = 0; i < 2; i++) {
        Player *p = &players[i];
        if (p->state != PL_ALIVE || p->invuln) continue;
        s16 dy = raw_y(p->y) + oy - py, dx = raw_x(p->x) + ox - px;
        if (dy < 0) dy = -dy;
        if (dx < 0) dx = -dx;
        if (dy < e && dx < f2) { player_kill(p); hit = TRUE; }
    }
    return hit;
}

static u8 pj_capped_live(void);

bool boss_can_fire(void)
{
    u16 live = pj_capped_live() + (enemy_bullets_live ? enemy_bullets_live() : 0);
    return live < level.rank;
}

void boss_score(Player *p, u8 idx)
{
    if (p && idx) player_add_score(player_credit(p), score_points[idx >> 3]);   /* $2D1D */
}

/* $6BBA-$6C11 / $754F-$75A3: four POW capsules ($4DCF, x bit 8 set by the
 * template) in a diamond around the centre (cy, cx2): x0 = rlca(cx2 - sub),
 * top/bottom at x0 (cy -+ dy), right/left at x0 +- dx (8-bit wrap). */
void boss_pows(s16 cy, s16 cx2, u8 sub, u8 dy, u8 dx)
{
    if (!item_spawn_pow) return;
    u8 v = cx2 - sub, x0 = (v << 1) | (v >> 7);
    item_spawn_pow(to_gx(256 + x0), to_gy(cy - dy));
    item_spawn_pow(to_gx(256 + (u8)(x0 + dx)), to_gy(cy));
    item_spawn_pow(to_gx(256 + x0), to_gy(cy + dy));
    item_spawn_pow(to_gx(256 + (u8)(x0 - dx)), to_gy(cy));
}

void boss_wipe(void)
{
    pj_clear();
    if (enemies_clear) enemies_clear();
}

/* ======================================================================= pattern blocks */

/* The boss objects' 32x32 patterns live in VRAM blocks lent by the BG metatile
 * cache (bg_reserve_blocks): a small LRU cache keyed by (code, colour), filled
 * by DMA from the build-time bank (boss_block_*). A hit costs a few dozen
 * cycles, against ~2000 for the generic sprite cache's slot search. */
#define BC_MAX 40
#define BC_UPLOADS 4                    /* 2 KB of pattern DMA per frame at most */
#define HINT(k) (((k) ^ ((k) >> 6) ^ ((k) >> 11)) & 63)
typedef struct { u16 tile, key, used; } BcEnt;
static BcEnt bc[BC_MAX];
static u8 bc_n, bc_up;
static u16 bc_stamp;

/* least recently used entry not used this frame (-1: none) */
static s16 lru_pick(const BcEnt *e, u16 n)
{
    s16 lru = -1; u16 age = 0;
    for (u16 i = 0; i < n; i++) {
        u16 d = e[i].key == 0xFFFF ? 0xFFFF : (u16)(bc_stamp - e[i].used);
        if (d > age) { age = d; lru = i; }
    }
    return lru;
}

void bc_reserve(u8 n)
{
    u16 tiles[BC_MAX];
    if (bc_n + n > BC_MAX) n = BC_MAX - bc_n;
    u16 got = bg_reserve_blocks(n, tiles);
    for (u16 i = 0; i < got; i++) { bc[bc_n].tile = tiles[i]; bc[bc_n].key = 0xFFFF; bc[bc_n].used = 0; bc_n++; }
}

/* 16x16 projectile patterns: quarters of lent blocks, same LRU scheme */
#define BS_MAX 16
static BcEnt bs[BS_MAX];
static u8 bs_n;

void bs_reserve(u8 blocks)
{
    u16 tiles[4];
    if (blocks > 4) blocks = 4;
    u16 got = bg_reserve_blocks(blocks, tiles);
    for (u16 i = 0; i < got; i++)
        for (u16 q = 0; q < 4 && bs_n < BS_MAX; q++) { bs[bs_n].tile = tiles[i] + 4 * q; bs[bs_n].key = 0xFFFF; bs_n++; }
}

void bc_release(void)
{
    if (bc_n || bs_n) bg_release_blocks();
    bc_n = bs_n = 0;
}

void bc_frame(void) { bc_stamp++; bc_up = 0; }

static void bs_draw(u16 code, u8 colour, s16 x, s16 y)
{
    if (x <= -16 || x >= SCREEN_W || y <= -16 || y >= SCREEN_H) return;
    u16 key = code | ((colour & 15) << 11);
    u8 pal = sprite_lut[256 + (colour & 15)] & 1;
    static u8 hint[64];
    static u16 absent[64];              /* keys not in the boss bank: straight to the sprite cache */
    u8 *h = &hint[HINT(key)];
    if (*h < bs_n && bs[*h].key == key) { bs[*h].used = bc_stamp; spr_tile16(bs[*h].tile, pal, x, y); return; }
    if (absent[HINT(key)] == key + 1) { spr_16(code, colour, x, y, 0); return; }
    for (u16 i = 0; i < bs_n; i++)
        if (bs[i].key == key) { bs[i].used = bc_stamp; *h = i; spr_tile16(bs[i].tile, pal, x, y); return; }
    s16 lru = bc_up < BC_UPLOADS * 4 ? lru_pick(bs, bs_n) : -1;
    if (lru >= 0) {
        u16 lo = 0, hi = BOSS_SMALL;
        while (lo < hi) { u16 mid = (lo + hi) >> 1; if (boss_small_keys[mid] < key) lo = mid + 1; else hi = mid; }
        if (lo < BOSS_SMALL && boss_small_keys[lo] == key) {
            bc_up++;                            /* 4 small uploads cost one block upload */
            bs[lru].key = key; bs[lru].used = bc_stamp; *h = lru;
            DMA_queueDmaFast(DMA_VRAM, (void *)(boss_small_data + (u32)lo * 128), bs[lru].tile * 32, 64, 2);
            spr_tile16(bs[lru].tile, pal, x, y);
            return;
        }
        absent[HINT(key)] = key + 1;
    }
    spr_16(code, colour, x, y, 0);
}

static const u8 *bank_find(u16 key)
{
    u16 lo = 0, hi = BOSS_BLOCKS;
    while (lo < hi) {
        u16 mid = (lo + hi) >> 1;
        if (boss_block_keys[mid] < key) lo = mid + 1; else hi = mid;
    }
    return lo < BOSS_BLOCKS && boss_block_keys[lo] == key ? boss_block_data + (u32)lo * 512 : NULL;
}

/* VRAM tile of the block holding (code, colour), uploading it into the least
 * recently used block if needed (and allowed this frame); 0 = not resident */
static u8 bc_hint[64];                  /* last entry index per key hash: hits in O(1) */
static u16 bc_absent[64];               /* key + 1 of keys missing from the bank (no search again) */

static u16 bc_get(u16 code, u8 colour)
{
    u16 key = code | ((colour & 15) << 11);
    u8 *h = &bc_hint[HINT(key)];
    if (*h < bc_n && bc[*h].key == key) { bc[*h].used = bc_stamp; return bc[*h].tile; }
    for (u16 i = 0; i < bc_n; i++)
        if (bc[i].key == key) { bc[i].used = bc_stamp; *h = i; return bc[i].tile; }
    if (bc_absent[HINT(key)] == key + 1) return 0;
    if (bc_up >= BC_UPLOADS) return 0;
    const u8 *src = bank_find(key);
    if (!src) { bc_absent[HINT(key)] = key + 1; return 0; }     /* not in the bank: generic cache */
    s16 lru = lru_pick(bc, bc_n);
    if (lru < 0) return 0;
    bc_up++;
    bc[lru].key = key; bc[lru].used = bc_stamp; *h = lru;
    DMA_queueDmaFast(DMA_VRAM, (void *)src, bc[lru].tile * 32, 256, 2);
    return bc[lru].tile;
}

/* load ahead (e.g. a boss's flash colours during its intro) */
void bc_prefetch(u16 code, u8 colour) { bc_get(code, colour); }

void bc_draw(u16 code, u8 colour, s16 x, s16 y)
{
    if (x <= -32 || x >= SCREEN_W || y <= -32 || y >= SCREEN_H) return;
    u16 t = bc_get(code, colour);
    if (t) spr_tile32(t, sprite_lut[256 + (colour & 15)] & 1, x, y);
    else spr_32(code, colour, x, y, 0);         /* not resident yet: generic sprite cache */
}

/* same, but skips a block that is not resident yet (bodies that flash anyway) */
void bc_draw_resident(u16 code, u8 colour, s16 x, s16 y)
{
    if (x <= -32 || x >= SCREEN_W || y <= -32 || y >= SCREEN_H) return;
    u16 t = bc_get(code, colour);
    if (t) spr_tile32(t, sprite_lut[256 + (colour & 15)] & 1, x, y);
}

/* ======================================================================= projectiles */

enum { PJ_NONE, PJ_BEAM, PJ_MISSILE, PJ_BULLET, PJ_BLAST, PJ_SPARK };
#define NPJ 40
typedef struct {
    u8 kind, bank;
    s16 y, x;
    s8 dy, dx;
    u8 t, i, n;
    bool loop, contact;
    const BossStep *st;
    u16 code; u8 colour;
    u8 heading, dir, phase, e, f2;
    s8 mate;
} Pj;
static Pj pj[NPJ];
static s8 pj_new = -1;

void pj_clear(void) { memset(pj, 0, sizeof(pj)); pj_new = -1; }
s8 pj_last(void) { return pj_new; }
void pj_link(s8 a, s8 b) { if (a >= 0 && b >= 0) pj[(u8)a].mate = b; }

static Pj *pj_alloc(u8 kind)
{
    for (u16 i = 0; i < NPJ; i++)
        if (!pj[i].kind) { memset(&pj[i], 0, sizeof(Pj)); pj[i].kind = kind; pj[i].mate = -1; pj[i].bank = 0xFF; pj_new = i; return &pj[i]; }
    pj_new = -1;
    return NULL;
}

static void load(Pj *p)
{
    const BossStep *s = &p->st[p->i];
    p->t = s->frames; p->code = s->code; p->colour = s->colour; p->dy = s->dy; p->dx = s->dx;
}

static u8 pj_capped_live(void)
{
    u8 n = 0;
    for (u16 i = 0; i < NPJ; i++)
        if ((pj[i].kind == PJ_MISSILE) || (pj[i].kind == PJ_BULLET && pj[i].bank == 0xFF)) n++;
    return n;
}

u8 pj_bank_live(u8 bank)
{
    u8 n = 0;
    for (u16 i = 0; i < NPJ; i++) if (pj[i].kind == PJ_BULLET && pj[i].bank == bank) n++;
    return n;
}

/* beam records: laser bursts $3613 (one 250-frame step), wheel #2 pod beams $7333 (looping) */
void pj_beam(s16 y, s16 x, const BossStep *st, u8 n, bool loop, bool contact, u8 e, u8 f2, s8 mate)
{
    Pj *p = pj_alloc(PJ_BEAM);
    if (!p) return;
    p->y = y; p->x = x; p->st = st; p->n = n; p->loop = loop; p->contact = contact;
    p->e = e; p->f2 = f2; p->mate = mate;
    load(p);
}

/* homing missile $4B89: launch steps, then every 7 frames re-aim and turn one
 * notch (heading +-2 of 32) towards the target ($4B50, steps $4BA9). Shootable
 * 8x8 (+$0C/+$0D = 8/4), contact 12x12 (+$0E/+$0F = $0C/6), HP 1, 0 points. */
void pj_missile(s16 y, s16 x, u8 heading, const BossStep *launch, u8 n)
{
    Pj *p = pj_alloc(PJ_MISSILE);
    if (!p) return;
    p->y = y; p->x = x; p->heading = heading; p->st = launch; p->n = n; p->contact = TRUE;
    p->e = 12; p->f2 = 12;
    load(p);
}

/* enemy bullet $4000 (codes $126 c8 / $127 c7 alternating, contact 12x12): the
 * enemy module's when present and capped, else this pool. bank 0/1 = final boss
 * burst records ($F000/$F100 halves), which bypass the cap like the arcade. */
bool pj_bullet(s16 y, s16 x, u8 dir, u8 bank)
{
    if (bank == 0xFF && enemy_bullet_spawn) return enemy_bullet_spawn(to_gx(x), to_gy(y), dir);
    if (bank == 0xFF && !boss_can_fire()) return FALSE;
    Pj *p = pj_alloc(PJ_BULLET);
    if (!p) return FALSE;
    p->y = y; p->x = x; p->dir = dir & 31; p->bank = bank; p->contact = TRUE; p->e = 12; p->f2 = 12;
    p->code = 0x126; p->colour = 8;
    return TRUE;
}

void pj_blast(s16 y, s16 x, const BossStep *st, u8 n)
{
    Pj *p = pj_alloc(PJ_BLAST);
    if (!p) return;
    p->y = y; p->x = x; p->st = st; p->n = n;
    load(p);
}

static void pj_kill(Pj *p)
{
    if (p->mate >= 0 && pj[(u8)p->mate].kind == PJ_BEAM) pj[(u8)p->mate].kind = PJ_NONE;   /* $3651: pair dies together */
    p->kind = PJ_NONE;
}

static void missile_steer(Pj *p)
{
    u8 aim = boss_aim(p->y, p->x) & 0x1E;      /* $4B50 */
    if (p->heading != aim) {
        if (((p->heading - aim) & 0x1E) < 0x10) p->heading -= 2; else p->heading += 2;
        p->heading &= 0x1E;
    }
    p->st = missile_heading; p->i = p->heading >> 1; p->n = 0;
    load(p);
}

void pj_update(void)
{
    bool small_check = !(frame & 1);           /* small objects collide on even $E003 */
    s8 lvl = level_bullet_speed < 3 ? 0 : level_bullet_speed > 6 ? 3 : level_bullet_speed - 3;
    for (u16 k = 0; k < NPJ; k++) {
        Pj *p = &pj[k];
        if (!p->kind) continue;
        switch (p->kind) {
        case PJ_BEAM:
        case PJ_BLAST:
        case PJ_SPARK:
            if (--p->t == 0) {
                if (++p->i >= p->n) {
                    if (!p->loop) { pj_kill(p); continue; }
                    p->i = 0;
                }
                load(p);
            }
            break;
        case PJ_MISSILE:
            if (--p->t == 0) {
                if (p->n && p->i + 1 < p->n) { p->i++; load(p); }
                else missile_steer(p);
            }
            break;
        case PJ_BULLET: {
            const s8 *c = &bullet_cycle[((lvl * 32 + p->dir) * 4 + p->phase) * 2];
            p->dy = c[0]; p->dx = c[1];
            p->phase = (p->phase + 1) & 3;
            p->code = (p->phase & 1) ? 0x126 : 0x127;      /* $4022 scripts: $126 c8 / $127 c7 */
            p->colour = (p->phase & 1) ? 8 : 7;
            break;
        }
        }
        p->y += p->dy; p->x += p->dx;
        if (p->kind == PJ_BLAST || p->kind == PJ_SPARK) continue;
        /* small-object kill rule ($23CB): y >= $F1 (or wrapped), x < $30, x >= $1C0 */
        if (p->y < 0 || p->y >= 0xF1 || p->x < 0x30 || p->x >= 0x1C0) { pj_kill(p); continue; }
        if (!small_check) continue;
        if (p->kind == PJ_MISSILE) {
            Player *who = NULL;
            if (boss_shots(p->y, p->x, 8, 8, &who)) {          /* $2591 */
                sound_play(SND_KILL_SMALL);
                p->kind = PJ_SPARK; p->st = small_explosion_steps; p->n = 7; p->i = 0; load(p);
                continue;
            }
        }
        if (p->contact && boss_touch(p->y, p->x, p->e, p->f2, 8, 8)) {   /* $2617 */
            if (p->kind == PJ_BEAM) continue;                  /* immune beams stay */
            pj_kill(p);
        }
    }
}

void pj_draw(void)
{
    for (u16 k = 0; k < NPJ; k++) {
        Pj *p = &pj[k];
        if (!p->kind || !p->code) continue;
        if (p->kind == PJ_BLAST) bc_draw(p->code, p->colour, to_gx(p->x), to_gy(p->y));
        else bs_draw(p->code, p->colour, to_gx(p->x), to_gy(p->y));
    }
}

/* ======================================================================= death explosions */

/* $3916 (sprite bosses) / $3A06 (wheels): sound $00/$14/$2A, a 2x2 explosion
 * ($3AF6) at each listed offset from (cy, cx2*2), then 300 + 180 frames, then
 * $8051 resumes the scroll. */
static struct { const s8 *list; u16 n, i; s16 cy, cx2; u16 wait; bool on; } blast;

void boss_blast_task(const s8 *list, u16 n, s16 cy, s16 cx2)
{
    sound_play(SND_STOP_ALL);
    sound_play(SND_BLAST);
    sound_play(SND_CLEAR);
    blast.list = list; blast.n = n / 3; blast.i = 0; blast.cy = cy; blast.cx2 = cx2; blast.wait = 1; blast.on = TRUE;
}

bool boss_blast_running(void) { return blast.on; }

static void blast_update(void)
{
    if (!blast.on || --blast.wait) return;
    if (blast.i < blast.n) {
        const s8 *e = &blast.list[blast.i++ * 3];
        u8 v = blast.cy + e[0], h = blast.cx2 + e[1];
        pj_blast(v, h * 2 + (h >> 7), explosion_steps, 7);     /* x = rlca(x/2 + dx) with b7 -> x bit 8 */
        blast.wait = (u8)e[2];
        if (blast.i == blast.n) blast.wait += 300 + 180;   /* $3970: $0233 + $0229 */
        return;
    }
    blast.on = FALSE;
    level_resume();                                         /* $3976 / $3A66 */
}

/* ======================================================================= dispatch */

void bosses_reset(void)
{
    sboss_reset(); wboss_reset(); fboss_reset(); ending_reset();
    pj_clear();
    bc_release();
    memset(&blast, 0, sizeof(blast));
    kind = 0; boss_shift = 0;
    boss_hud_set(FALSE, 0, 0);
}

void boss_start(u8 k, u16 id)
{
    switch (k) {
    case 0:     /* sprite bosses: $69D0 (section 1), $6C12 (3, 5), $6DB4 (7-9) */
        kind = 1; sboss_start(id == 0x69D0 ? 0 : id == 0x6C12 ? 1 : 2);
        break;
    case 1:     /* BG wheels $7192 / $719C / $71A6 */
        kind = 2; wboss_start(id == 0x7192 ? 0 : id == 0x719C ? 1 : 2);
        break;
    default:    /* final $5FC3 */
        kind = 3; fboss_start();
        break;
    }
}

void bosses_update(void)
{
    bc_frame();
    boss_ending_tick();
    blast_update();
    pj_update();
    bool alive = FALSE;
    switch (kind) {
    case 1: alive = sboss_update(); break;
    case 2: alive = wboss_update(); break;
    case 3: alive = fboss_update(); break;
    }
    if (kind && !alive) { kind = 0; boss_hud_set(FALSE, 0, 0); }
    if (!kind && !blast.on) {
        boss_shift = 0;
        bool blasts = FALSE;
        for (u16 i = 0; i < NPJ; i++) if (pj[i].kind == PJ_BLAST) blasts = TRUE;
        if (!blasts) bc_release();              /* VRAM blocks back to the BG cache */
    }
}

void bosses_draw(void)
{
    pj_draw();
    switch (kind) {
    case 1: sboss_draw(); break;
    case 2: wboss_draw(); break;
    case 3: fboss_draw(); break;
    }
}
