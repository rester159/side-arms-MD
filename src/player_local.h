/* Private interface between player.c, weapons.c and combined.c. */
#pragma once
#include "game.h"
#include "sprites.h"
#include "gen/player_data.h"

#define P2_CODE  0x80                       /* P2 body codes = P1 + $80 (B2:$8FB8) */
#define P2_COLOUR 4                         /* descriptor $1D24 attr */

extern u8 fire_flash;                       /* $E016: robot muzzle flash, set by every fire */

static inline bool is_leader(const Player *p) { return combined == p->id + 1; }

/* weapons.c */
void weapons_clear(Player *p);              /* zero orbiters, launcher and shots (+$80..+$1FF) */
void weapons_build_bits(Player *p);         /* $1F26: orbit start phases */
void weapon_select(Player *p);              /* $1E03 */
void weapons_pose(Player *p);               /* B2:$8511: weapon pose, orbiters, launcher */
void weapons_fire(Player *p, u8 in);        /* B2:$86CC-$8D11 */
void weapons_ring(Player *src, u8 in);      /* B2:$8D51/$8DE6: combined robot ring */
void weapons_draw(const Player *p);
void shot_explode(Shot *s);

/* player.c */
void player_move(Player *p, u8 dir, const s8 (*table)[2]);   /* B2:$8368-$84B4; sets `crushed` */
extern bool crushed;
void player_respawn_in_place(Player *p);    /* $1960/$196B */
void player_kill_now(Player *p);            /* $222C without the invulnerability test */

/* combined.c */
void combine_reset(void);                   /* new game: no robot, no sequence */
void combine_start(Player *leader);         /* item $06, $2E4E */
void combine_hit(void);                     /* $2237: robot loses a hit point */
void combine_join(Player *p);               /* partner joins/continues while merged ($1B41) */
bool combine_update(void);                  /* TRUE: a merge/split sequence consumed the frame */
void combine_update_player(Player *p, u8 in);
bool combine_draw(void);                    /* TRUE: sequence drew the players */
void combine_draw_robot(const Player *leader);
