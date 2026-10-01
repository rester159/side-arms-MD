#pragma once
/* Internal interface of the enemy modules (enemies.c, items.c, fx.c, enemy_*.c).
 * Behaviour reference: docs/re/objects.md; design: docs/enemies.md. */
#include "game.h"
#include "enemies.h"
#include "gen/enemy_data.h"

/* Object pools. Sizes are the arcade's (docs/re/objects.md 1.1): a spawn with no free slot is
 * dropped, exactly as in the original, so the pool sizes are part of the behaviour. */
enum { EP_SMALL, EP_BIG, EP_ITEM };
#define N_SMALL  16     /* 1x1 objects: enemy bullets, missiles, bombs, snake segments ($F000) */
#define N_BIG     9     /* 2x2 enemies ($F600-$FA7F) */
#define N_ITEM    8     /* pickups, hidden bonuses, mines, orb fragments ($FF00) */

/* Object flags: same bit meanings as the arcade record's +$09 (the generator copies them). */
#define EF_SHOTPROOF    0x01    /* player shots pass through */
#define EF_NOCONTACT    0x02    /* no contact with the players */
#define EF_NOTERRAIN    0x04    /* no terrain test */
#define EF_BGLOCK       0x20    /* moves with the background (camera) */
#define EF_KILLREQ      0x40    /* dies on its next update */
#define EF_NATIVEDEATH  0x80    /* death = behaviour function instead of a death script */

typedef struct Enemy {
    u8 live;            /* 0 = free slot */
    u8 pool;            /* EP_* */
    u8 flags;           /* EF_* */
    u8 cat;             /* arcade category (+$07); 0 = enemy bullet (counted for the cap) */
    s16 x, y;           /* Genesis screen px of the sprite's top-left (arcade sprite - (96, 16)) */
    s8 dy, dx;          /* px per frame */
    u8 timer;           /* frames left in the current motion step */
    u8 colour;
    u16 code;           /* arcade sprite code (2x2 objects: top-left cell) */
    u16 next;           /* motion step loaded when the timer runs out */
    u8 hp;
    u8 item;            /* 0 = hostile, else pickup code (player_apply_item) */
    u8 box[4];          /* shot box half-h, half-w/2; contact box half-h, half-w/2 (arcade +$0C-$0F) */
    u8 r[10];           /* per-family state (arcade +$10..+$19): r[5] score index, r[6] last aim, r[8] carried letter */
    u8 wall;            /* AI id of the terrain handler (0 = none) */
    u8 sub_y;           /* 2x2 objects: arcade y of the top cells after the last move (+$22) */
    u16 death;          /* death script step, or AI id when flags & EF_NATIVEDEATH */
    s16 sub_x;          /* 2x2 objects: arcade x of the right cells after the last move (+$23) */
    u16 spare;
} Enemy;

#define R_SCORE  5
#define R_AIM    6
#define R_X2     7
#define R_LETTER 8

extern Enemy en_small[N_SMALL], en_big[N_BIG], en_item[N_ITEM];

/* Arcade coordinate views (the RE notes and every constant in the natives use them). */
#define AX(e)        ((s16)((e)->x + 96))           /* 9-bit sprite x */
#define AY(e)        ((u8)((e)->y + 16))            /* 8-bit sprite y */
#define AX2(e)       ((u8)(AX(e) >> 1))             /* x/2 of the current position */
/* +$17: x/2 as the arcade sees it. It is only refreshed when the object runs its collision tests
 * (even frames for small objects, odd for big ones, after moving), so natives and the aim helper
 * read a value up to 2 frames old; the timing of turns depends on it. */
#define X2(e)        ((e)->r[7])
/* The arcade's 2x2 objects keep the coordinates of their other three cells in sub-records that are
 * only rewritten when the object moves ($2856-$28F7). A native that reads them (muzzles at x+16 or
 * y+16) sees the position after the last move, i.e. before this frame's background-lock shift. */
#define SUB_X16(e)   ((e)->sub_x)                   /* +$23 / +$63: x + 16 */
#define SUB_Y(e)     ((e)->sub_y)                   /* +$22: y */
#define SUB_Y16(e)   ((u8)((e)->sub_y + 16))         /* +$42 / +$62: y + 16 */
#define SET_AX(e, v) ((e)->x = (s16)(v) - 96)
#define SET_AY(e, v) ((e)->y = en_y_from_arcade((u8)(v)))
static inline s16 en_y_from_arcade(u8 ay) { return (ay >= 0xF8 ? (s16)ay - 256 : (s16)ay) - 16; }

/* frame parity for the collision cadence: small objects on even frames, big on odd ($2500/$291E) */
extern u16 frame;
extern u8 en_target_y, en_target_x2;     /* aim target (arcade $E020/$E021: y, x/2 of a player) */
extern u8 en_rng;                        /* arcade $E008: +1 every 3 frames, natives add constants */
extern u8 en_rnd[7];                     /* arcade $E009-$E00F, chained to $E008 */
extern u8 en_rng_div;
#define EN_E00F (en_rnd[6])              /* the turrets' byte ($9BDC, $9D78, $A0BD) */
extern u8 level_bullet_speed;            /* level.c: enemy bullet speed level 3..6 ($E050, set with the stage music) */
#define en_speed level_bullet_speed
extern s8 en_scroll_dx, en_scroll_dy;    /* camera movement this frame (BG-locked objects) */

/* --- motion (enemies.c) ------------------------------------------------------------------- */
/* Load a motion step now and keep going this frame (arcade "jp SET" $2435/$27EE). */
void en_set_motion(Enemy *e, u16 step);
/* Keep the current motion and keep going this frame (arcade "jp $2856/$2487"). A native that
 * calls neither returns from the object's update for this frame (arcade "ret"). */
void en_continue(Enemy *e);
void en_remove(Enemy *e);                /* free the slot silently (arcade kill $257F/$29A3) */
void en_die(Enemy *e);                   /* death: script or native ($25EF/$2AAD) */
void en_kill_by(Enemy *e, Player *p);    /* destroyed: sound, score to p, carried item, death */
Enemy *en_alloc(u8 pool);                /* first free slot of a pool or NULL */
Enemy *en_alloc_small_group(u8 n, u8 align);   /* n consecutive free small records */
void en_init(Enemy *e, u16 init);        /* copy an EnemyInit into a slot (template copy) */
Enemy *en_spawn(u8 pool, u16 init);      /* alloc + init */
bool en_terrain(Enemy *e);               /* terrain test at the object ($07C0 small / $082F big) */
static inline u16 en_index(Enemy *e, Enemy *base) { return (u16)(e - base); }

/* --- aim / bullets (enemies.c) ------------------------------------------------------------ */
u8 en_aim_at(u8 ay, u8 ax2, u8 ty, u8 tx2);   /* $0715: direction 0-31, 0 = right, 8 = down */
u8 en_aim(Enemy *e);                     /* $06E8: aim at the target, also stored in r[R_AIM] */
bool en_bullet_room(void);               /* $05AA: live enemy bullets < cap (level.rank) */
/* $05AA + $0531 + template $4000: bullet at arcade (ay, ax) in direction dir; NULL if refused */
Enemy *en_bullet_at(u8 ay, s16 ax, u8 dir);
Enemy *en_fire_aimed(Enemy *e);          /* bullet at (y+8, x) of e, aimed at the target ($B111) */

/* --- items (items.c) ---------------------------------------------------------------------- */
void en_drop_letter(Enemy *e);           /* $2A23: pickup for the carried letter at the centre */
void en_pickup(Enemy *e, Player *p);     /* $2657: a player touched a pickup */

/* --- natives with no C implementation (should not happen in a complete build) ------------ */
void en_native_missing(Enemy *e);
extern u16 en_missing_count;
