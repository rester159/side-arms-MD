/* Internal interface of the boss modules (boss.c, boss_sprite.c, boss_wheel.c, boss_final.c). */
#pragma once
#include "game.h"
#include "boss.h"
#include "sprites.h"
#include "gen/boss_data.h"

/* Boss logic runs in arcade sprite coordinates ("raw": the arcade screen shows
 * x 64..447, y 16..239; the collision boxes use x/2 as the arcade does). Screen
 * and player coordinates convert through the boss view shift: the sprite bosses
 * are drawn 32 px further left than in the arcade so the whole 128-px body fits
 * the 320-px screen (docs/bosses.md, deviations). Everything that belongs to the
 * fight (boss, beams, missiles, explosions, collision tests) shifts together. */
extern s16 boss_shift;
static inline s16 to_gx(s16 x) { return x - ARCADE_VIEW_X - boss_shift; }
static inline s16 to_gy(s16 y) { return y - ARCADE_VIEW_Y; }
static inline s16 raw_x(s16 gx) { return gx + ARCADE_VIEW_X + boss_shift; }
static inline s16 raw_y(s16 gy) { return gy + ARCADE_VIEW_Y; }

/* arcade sounds used by the bosses (docs/re/sound.md) */
#define SND_STOP_ALL    0x00
#define SND_KILL_BIG    0x11
#define SND_KILL_SMALL  0x12
#define SND_BOSS_IN     0x13
#define SND_BLAST       0x14
#define SND_CRACK       0x15
#define SND_HIT         0x17
#define SND_LASER       0x18
#define SND_CLEAR       0x2A
#define SND_ENDING      0x2C
#define SND_WHEEL       0x35

/* ---- shared helpers (boss.c) ---- */
void boss_target(s16 *y, s16 *x);               /* $E020/$E021 as raw (y, x) */
u8 boss_aim_at(s16 y, s16 x, s16 ty, s16 tx);   /* $0715: direction 0-31 from a top-left to a target */
u8 boss_aim(s16 y, s16 x);                      /* $06E8: ... to the current target */
/* player shots against a reference point (top-left space, arcade $2591/$29C7/$2D92):
 * |py - shot.y| < c + shot.half_h and |px - shot.x| < d2 + shot.half_w. Every hit shot
 * is consumed (shot_hit); returns the number of hits, *who = last shooter. */
u8 boss_shots(s16 py, s16 px, u8 c, u8 d2, Player **who);
/* player contact (arcade $2617/$2AD5/$2E16): kills each player with
 * |p.y + oy - py| < e and |p.x + ox - px| < f2. Returns TRUE if one was touched. */
bool boss_touch(s16 py, s16 px, u8 e, u8 f2, s8 oy, s8 ox);
bool boss_can_fire(void);                       /* $05AA: live enemy bullets < cap ($E017) */
void boss_score(Player *p, u8 score_idx);       /* $2272 with score index +$15 */
u8 boss_rng(u8 *seed, u8 add);
void boss_hud_set(bool on, u8 bars, u8 hits);
void boss_pows(s16 cy, s16 cx2, u8 sub, u8 dy, u8 dx);  /* 4 POW capsules ($4DCF) around (cy, cx2*2) */
void boss_defeated(void);                       /* the killing hit: boss_kills++ */
void boss_wipe(void);                           /* $6B71: enemies, bullets, boss shots gone */
/* death explosion task $3916/$3A06: blasts around (cy, cx2) then a 480-frame pause, then
 * level_resume() (sprite bosses) - the wheel calls it after moving to the next section. */
void boss_blast_task(const s8 *list, u16 n, s16 cy, s16 cx2);
bool boss_blast_running(void);

/* ---- 32x32 pattern blocks in VRAM lent by the BG cache (boss.c) ---- */
void bc_reserve(u8 n);                          /* add n blocks to the pool (fewer if the cache is short) */
void bc_release(void);
void bc_draw(u16 code, u8 colour, s16 x, s16 y);   /* 2x2 cells c, c+1, c+8, c+9 at a screen position */
void bc_draw_resident(u16 code, u8 colour, s16 x, s16 y);   /* same, skipped until resident */
void bc_prefetch(u16 code, u8 colour);
void bs_reserve(u8 blocks);                     /* 4 x 16x16 projectile patterns per block */

/* ---- projectile / effect pool (boss.c) ---- */
void pj_clear(void);
void pj_update(void);
void pj_draw(void);
void pj_beam(s16 y, s16 x, const BossStep *st, u8 n, bool loop, bool contact, u8 e, u8 f2, s8 mate);
s8 pj_last(void);                               /* index of the last spawned projectile, -1 */
void pj_link(s8 a, s8 b);                       /* a's death also removes b (beam pairs) */
void pj_missile(s16 y, s16 x, u8 heading, const BossStep *launch, u8 n);
bool pj_bullet(s16 y, s16 x, u8 dir, u8 bank);  /* bank 0/1: final boss bursts, 0xFF: capped */
u8 pj_bank_live(u8 bank);
void pj_blast(s16 y, s16 x, const BossStep *st, u8 n);   /* 2x2 explosion */

/* ---- boss kinds ---- */
void sboss_start(u8 type);
bool sboss_update(void);                        /* FALSE when gone */
void sboss_draw(void);
void sboss_reset(void);
void wboss_start(u8 type);
bool wboss_update(void);
void wboss_draw(void);
void wboss_reset(void);
void fboss_start(void);
bool fboss_update(void);
void fboss_draw(void);
void fboss_reset(void);
void ending_start(void);
void ending_reset(void);
void boss_ending_tick(void);
