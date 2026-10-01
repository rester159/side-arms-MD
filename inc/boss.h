#pragma once
#include <genesis.h>

/* Bosses (src/boss.c, boss_sprite.c, boss_wheel.c, boss_final.c; design in docs/bosses.md).
 *
 * Arcade sources: sprite bosses $69D0 / $6C12 / $6DB4, BG wheel bosses $7192 / $719C / $71A6,
 * final boss $5FC3 (docs/re/objects.md 6.1, docs/re/levels.md 2). */

/* EV_BOSS from level.c: kind 0 sprite, 1 BG wheel, 2 final; id = arcade spawn routine. */
void boss_start(u8 kind, u16 id);
void bosses_reset(void);            /* drop any boss, its shots and the ending (new game / warp) */
void bosses_update(void);           /* once per frame, after players_update() */
void bosses_draw(void);             /* in game_draw(), after players and enemies (bosses sit below) */

/* ---- HUD -----------------------------------------------------------------
 * The arcade draws one 4-character group ($6C-$6F) per remaining HP bar on the text
 * layer at $D137 (routine $0897 / $089C), right-aligned, and clears it when the boss
 * is gone. A bar is 20 hits (+$0B = $14). */
typedef struct {
    bool active;                    /* show the bar row */
    u8 bars;                        /* remaining bars (sprite bosses 3/6/8, wheel core 4) */
    u8 hits;                        /* hits left in the current bar */
    u8 serial;                      /* changes whenever bars changes (redraw trigger) */
} BossHud;
extern BossHud boss_hud;

/* ---- ending (final boss death task $3B8A) -------------------------------------
 * "CONGRATURATIONS ... THE END", then the staff roll, then the arcade restarts the
 * title cycle ($0B84). The front end should poll boss_game_cleared() and go back to
 * the title when it turns TRUE. The text is written with hud_text() (hud.h,
 * window plane; arcade text column c -> HUD column c - 12, row r -> r - 2). */
bool boss_ending_active(void);
bool boss_game_cleared(void);

/* Services of other modules the boss module uses when they are linked (weak):
 *   enemies.h  enemy_bullet_spawn(), enemy_bullets_live(), enemies_clear()
 *   hud.h      hud_text()
 *   void item_spawn_pow(s16 x, s16 y);   POW capsule ($4DCF, flags $A4) at Genesis screen x,y
 *                                        (top-left) - requested from the enemies/items module
 */

/* ---- level extras (level.c) ------------------------------------------------ */
extern u8 level_bullet_speed;       /* $E050: enemy bullet speed level 3-6, set with the stage music */
void level_halt(void);              /* $8057: stop scroll + script, live directions read 0 */
void level_warp(u16 section, u16 boss);   /* test/debug: section start, or just before its n-th boss */
