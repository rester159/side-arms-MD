#pragma once
#include <genesis.h>
/* Owned by the player/weapons module (player.c, weapons.c, combined.c). Design: docs/player.md. */

#define MAX_SHOTS 9                 /* arcade: 9 shot records per player (+$E0..+$1DF) */
typedef struct {
    s16 x, y, vx, vy;               /* screen pixels of the 16x16 sprite, px/frame */
    u8 active;                      /* 0 free, 1 flying, 2 exploding. Only active == 1 shots hit enemies
                                       (arcade collision tests state $80 only, $2500) */
    u8 kind, life, damage;          /* kind: ShotKind; life: explosion countdown */
    u8 half_w, half_h;              /* hit box half sizes in pixels, centred on (x+8, y+8) */
    bool pierce;                    /* M.B.L.: passes through enemies (+$07 != 0) */
    u16 code; u8 colour;
    u8 timer, phase, delay;         /* timer: S.G. fuse / robot boomerang counter (+$18), phase: S.G.
                                       burst (+$19), delay: M.B.L. segment launch delay (+$0E) */
} Shot;

enum { SHOT_NORMAL, SHOT_BIT, SHOT_SG, SHOT_MBL, SHOT_3WAY, SHOT_AUTO, SHOT_RING };
enum { WPN_NONE, WPN_BIT, WPN_SG, WPN_MBL, WPN_3WAY, WPN_AUTO };   /* selected slot (+$10) */

typedef enum { PL_OFF, PL_ALIVE, PL_DYING } PlayerState;
typedef struct {
    PlayerState state;
    u8 id;                          /* 0 = P1, 1 = P2 */
    s16 x, y;                       /* screen position of the 32x32 body (top-left) */
    s16 old_x, old_y;
    bool facing_left;
    bool vertical;                  /* +$28: copy of the stage axis ($E040) taken at spawn */
    u8 speed;                       /* 1-3 */
    u8 weapon;                      /* selected slot 0-5 (WPN_*) */
    u8 level[6];                    /* [1] BIT 0-3, [2] S.G. 0-3, [3] M.B.L. 0-2, [4] 3WAY 0-2, [5] AUTO 0/$10/$11 */
    u8 lives;
    u8 invuln, entry, fire_pose, death_timer, death_frame;
    bool fire_latch, select_latch;
    u32 score;                      /* points (displayed value) */
    Shot shots[MAX_SHOTS];
    /* --- added by the player module --- */
    bool in_play;                   /* arcade alive mask $E018 bit: spawned and not out of lives */
    bool entry_latch;               /* +$2A: joystick took control back during the entry glide */
    u8 prev_held;                   /* last frame's pad: weapon select reads it (arcade $1E03 runs first) */
    u16 body_code;                  /* +$00 body sprite code before the P2 +$80 offset */
    s16 ref_x, ref_y;               /* +$22/+$23: orbit reference (last drawn body y, x+16) */
    u8 bit_step[3];                 /* BIT orbit path index per orbiter (+$9E/+$BE/+$DE) */
    s16 bit_x[3], bit_y[3]; u16 bit_code[3];
    bool bits_valid;                /* orbiter records hold a position (cleared with +$80..+$1FF) */
    s16 att_x, att_y; u16 att_code; /* M.B.L. launcher sprite (+$80) */
    bool att_valid;
    u8 extend_idx;                  /* +$1A: next entry of the bonus-life table */
    u8 ring_toggle;                 /* +$35: combined-robot ring pattern A/B */
    u8 name[3];                     /* +$3C: free for the front end (NAMING) */
    /* --- Boss Rush (port, not arcade; docs/frontend.md) --- */
    u8 energy;                      /* 0: the arcade's lives rule. 1-8: energy bar - a hit that would kill
                                       costs one segment instead (the last one kills) */
    bool hit_blink;                 /* the invulnerability after an absorbed hit blinks the body */
} Player;

extern Player players[2];
void players_init(void);
void player_spawn(Player *p);                   /* respawn $1871: entry glide, 80 f invulnerable */
void player_start(Player *p, u8 lives);         /* new game for p ($1839): speed 1, no weapons, score 0 */
void player_continue(Player *p, u8 lives);      /* CONTINUE accepted ($1B09): score 0, weapons kept */
bool player_out_of_lives(const Player *p);      /* lives exhausted, death animation over ($1A81) */
void players_update(void);
void players_draw(void);
void player_kill(Player *p);                    /* arcade $222C (ignored while invulnerable) */
/* Boss Rush: frames of invulnerability after a hit absorbed by the energy bar (2 s) */
#define PLAYER_HIT_INVULN 120
/* Boss Rush: weapon levels [WPN_*] (0 = not owned; AUTO: 0/$10/$11) and speed 1-3, orbit rebuilt */
void player_loadout(Player *p, const u8 level[6], u8 speed);
void player_add_score(Player *p, u32 points);   /* score + extends (arcade $2272/$22AE) */
Player *player_credit(Player *shooter);         /* who scores a shooter's kill ($2516: the owner, or
                                                   the other player when the owner has no lives) */
void player_apply_item(Player *p, u8 item);     /* pickup effects (arcade $2657), arcade item codes */
void shot_hit(Player *p, Shot *s);              /* a shot hit an enemy: explode unless piercing */

/* Scoring / options */
extern u32 hi_score;                /* $E600, default 100000 (ranking $0B34) */
extern u16 extend_setting;           /* DSW0 bits 4-5: 0 = 100000 once (arcade default), 1 = every 100000
                                       to 500000, 2 = every 150000 to 600000, 3 = every 200000 to 600000;
                                       4 = none (Home option, not arcade) */
extern bool score_enabled;          /* arcade $E010: FALSE in the attract demo (no score, $2272) */

/* Combined "Side Arms" robot (combined.c) */
extern u8 combined;                 /* $E014: 0, or leader id + 1 (1 = P1-led $41, 2 = P2-led $42) */
extern u8 combined_hp;              /* $E015: hits the robot can take */
bool players_world_frozen(void);    /* TRUE while the merge/split sequence runs: the arcade suspends every
                                       other task ($3078), so level scroll and enemies must not update */
