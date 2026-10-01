#pragma once
#include <genesis.h>
/* Enemies, enemy bullets, pickups/POW, hidden bonuses, explosions (enemies.c, enemy_*.c,
 * items.c, fx.c). Behaviour: docs/re/objects.md; design and data format: docs/enemies.md.
 * All positions are Genesis screen pixels (arcade sprite coordinates - (96, 16)). */

/* --- called by the level timeline / game loop ---------------------------------------------- */
void enemy_spawn_event(u16 section, u16 index);  /* EV_SPAWN b: one arcade script spawn record */
void enemies_update(void);                       /* once per frame, after players_update() */
void enemies_draw(void);                         /* inside spr_begin()/spr_end(), after players_draw() */
/* raw arcade script record (cmd, target) outside the stage tables (attract demo): template SPAWN
 * records only, see enemies.c */
void enemy_spawn_record(u8 cmd, u16 target);
void enemies_clear(void);                        /* remove every enemy, bullet, pickup, explosion
                                                  * (call at game start / continue / attract start) */

/* --- for the boss module --------------------------------------------------------------------- */
/* Enemy bullet (arcade template $4000: code $126/$127, contact +-12 px, dies on terrain).
 * (x, y) = top-left of the 16x16 bullet sprite; dir = 0..31 (0 right, 8 down, 16 left, 24 up).
 * Speed is the current stage's bullet speed level ($E050); refused (FALSE) when the live-bullet
 * cap (level.rank, arcade $E017) is reached or the 16-record small-object pool is full. */
bool enemy_bullet_spawn(s16 x, s16 y, u8 dir);
/* Direction 0..31 from the point (x, y) (top-left of a 32x32 object, as the arcade's $06E8)
 * to the player the enemies currently target (re-chosen every 8 frames, B2:$813A). */
u8 enemy_aim(s16 x, s16 y);
/* Explosion effects (not tied to an enemy slot). kind: FX_BIG = 2x2 explosion colour 8
 * (script $4D5E), FX_BIG7 = same in colour 7 ($4D87), FX_SMALL = 16x16 burst ($4DAB).
 * (x, y) = top-left. bg_locked: the explosion scrolls with the background. */
enum { FX_BIG, FX_BIG7, FX_SMALL };
void fx_explosion(s16 x, s16 y, u8 kind, bool bg_locked);
/* POW capsule (template $4DCF: shoot it to cycle the items, touch it to take one) at (x, y) =
 * top-left of its 16x16 sprite; nothing happens when the 8 pickup slots are full. */
void item_spawn_pow(s16 x, s16 y);
/* Number of live enemy bullets (category 0 objects), for bosses that want to throttle. */
u8 enemy_bullets_live(void);

/* --- debug / tests ---------------------------------------------------------------------------- */
extern u16 enemy_spawned, enemy_dropped;         /* spawn statistics (objects created / dropped) */
