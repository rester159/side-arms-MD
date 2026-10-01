#include "game.h"
#include "boss.h"
#include "gen/level_data.h"
#include "gen/assets.h"

/* Camera timeline. The arcade auto-scrolls 1 px every second frame on each
 * moving axis (arcade $2001-$2041, run when $E003 is odd) and fires each
 * script record when the camera reaches its position (interpreter $2044).
 * The starfield steps once every 4 frames on a moving axis ($201E/$203E),
 * always in the same direction: half the background speed.
 *
 * Halts ($8057): mode $40 stops the scroll and the script, and the live
 * directions read by the rest of the game ($E088/$E089, e.g. the player's
 * terrain push-back) are forced to 0 ($1FC9); the script's latched
 * directions ($E08A/$E08B) come back on resume ($8051, boss death).
 *
 * Section ends (EV_NEXT, docs/re/levels.md 2): the arcade script runs on into
 * the next section's records; the port restarts the timeline at the next
 * section, whose first record is the same teleport. */

Level level;
u8 level_bullet_speed = 3;              /* $E050 speed level (3-6), loaded with the stage music */
volatile u16 dbg_warp;                  /* test hook: (section + 1) | (boss ordinal << 8), see level_warp() */
static s8 latch_x, latch_y;             /* $E08A/$E08B */
void enemy_spawn_event(u16 section, u16 index) __attribute__((weak));

/* B0:$80CA: the stage music also loads $E050 from table $813C indexed by the difficulty; the
 * level data carries the default-difficulty value, the front end applies the chosen one */
u8 game_bullet_speed(u8 music, u8 dflt) __attribute__((weak));
static u8 bullet_speed(const LevelEvent *e) { return game_bullet_speed ? game_bullet_speed(e->a, e->c) : e->c; }

static s8 dir_of(u8 a) { return a == 0 ? 0 : a == 1 ? 1 : -1; }   /* $2001: 0 stop, 1 +1, else -1 */

static void apply_dirs(void)
{
    bool run = level.mode == SCROLL_RUN;
    level.dir_x = run ? latch_x : 0;
    level.dir_y = run ? latch_y : 0;
}

void level_start(u16 section)
{
    const LevelSection *s = &level_sections[section];
    level.section = section;
    level.next_event = 0;
    level.scroll_x = s->start_x;
    level.scroll_y = s->start_y;
    /* the latched directions carry over ($E08A/$E08B are only written by the
     * script): e.g. after wheel #2 the scroll keeps moving right from C80,500
     * until section 5's first records (at C81,500) fire */
    if (section == 0) latch_x = latch_y = 0;
    level.mode = SCROLL_RUN;
    level.tick = 0;
    /* a section's script opens with its teleport (fired by the previous
     * section's end or wheel-boss death in the arcade): apply it now */
    if (s->nevents && s->ev[0].op == EV_TELEPORT) {
        level.scroll_x = s->ev[0].b; level.scroll_y = s->ev[0].c;
        level.next_event = 1;
    }
    apply_dirs();
    video_set_camera(cam_x(), cam_y());
}

void level_resume(void)
{
    /* arcade $8051: resume scrolling in the saved direction after a boss */
    level.mode = SCROLL_RUN;
    apply_dirs();
}

/* $8057, also used by the boss module to hold the camera during a death sequence */
void level_halt(void)
{
    level.mode = SCROLL_HALT;
    apply_dirs();
}

/* returns FALSE when the timeline was restarted (stop firing this frame's records) */
static bool fire(const LevelEvent *e)
{
    switch (e->op) {
    case EV_TELEPORT: level.scroll_x = e->b; level.scroll_y = e->c; break;
    case EV_MUSIC:    sound_play(e->a); if (e->c) level_bullet_speed = bullet_speed(e); break;
    /* B0:$80B3 / $809C also set $E040 ('H' / 'V'); stop and reverse ($80BE/$80C4, $80A7/$80AD) don't */
    case EV_DIR_X:    latch_x = dir_of(e->a); if (e->a == 1) level.vertical = FALSE; apply_dirs(); break;
    case EV_DIR_Y:    latch_y = dir_of(e->a); if (e->a == 1) level.vertical = TRUE; apply_dirs(); break;
    case EV_RANK:     level.rank = e->a; break;   /* $8000: + table $8049[difficulty] = +0 by default */
    case EV_BOSS:     boss_start(e->a, e->b); break;
    case EV_HALT:     level_halt(); break;
    case EV_SPAWN:    if (enemy_spawn_event) enemy_spawn_event(level.section, e->b); break;
    case EV_NEXT:
        if (level.section + 1 < LEVEL_SECTIONS) { level_start(level.section + 1); return FALSE; }
        level_halt();                   /* past the last record: stay put */
        break;
    }
    return TRUE;
}

/* Debug/test entry: jump to a section, optionally just before its n-th boss
 * (1-based). Replays the section's direction/rank/music records up to there. */
void level_warp(u16 section, u16 boss)
{
    bosses_reset();
    level_start(section);
    const LevelSection *s = &level_sections[section];
    /* entering mid-game: take the direction towards the section's next record */
    if (level.next_event < s->nevents) {
        const LevelEvent *e = &s->ev[level.next_event];
        latch_x = e->x > level.scroll_x ? 1 : e->x < level.scroll_x ? -1 : 0;
        latch_y = e->y > level.scroll_y ? 1 : e->y < level.scroll_y ? -1 : 0;
    }
    apply_dirs();
    if (!boss) return;
    for (u16 i = level.next_event; i < s->nevents; i++) {
        const LevelEvent *e = &s->ev[i];
        if (e->op == EV_BOSS && !--boss) {
            /* start 32 px before the spawn point, on the leg that leads to it */
            level.scroll_x = e->x - latch_x * 32; level.scroll_y = e->y - latch_y * 32;
            level.next_event = i;
            break;
        }
        if (e->op == EV_DIR_X) latch_x = dir_of(e->a);
        else if (e->op == EV_DIR_Y) latch_y = dir_of(e->a);
        else if (e->op == EV_RANK) level.rank = e->a;
        else if (e->op == EV_MUSIC && e->c) level_bullet_speed = bullet_speed(e);
        else if (e->op == EV_TELEPORT) { level.scroll_x = e->b; level.scroll_y = e->c; }
    }
    apply_dirs();
    video_set_camera(cam_x(), cam_y());
}

void level_update(void)
{
    if (dbg_warp) { u16 w = dbg_warp; dbg_warp = 0; level_warp((w & 0xFF) - 1, w >> 8); }
    level.tick++;
    if (level.mode != SCROLL_RUN) { video_set_camera(cam_x(), cam_y()); return; }   /* $1FF4: no scroll, no script */
    if (frame & 1) {
        if (level.dir_y) {
            level.scroll_y = (level.scroll_y + level.dir_y) & 0xFFF;
            if (frame & 2) video_stars_step(0, 1);
        }
        if (level.dir_x) {
            level.scroll_x = (level.scroll_x + level.dir_x) & 0xFFF;
            if (frame & 2) video_stars_step(1, 0);
        }
    }
    /* fire every record whose position has been reached, in order */
    for (;;) {
        const LevelSection *s = &level_sections[level.section];
        if (level.next_event >= s->nevents || level.mode != SCROLL_RUN) break;
        const LevelEvent *e = &s->ev[level.next_event];
        if (e->x != level.scroll_x || e->y != level.scroll_y) break;
        level.next_event++;
        if (!fire(e)) continue;
    }
    video_set_camera(cam_x(), cam_y());
}

/* Arcade terrain bitmap (B2:$A000, test $84B5): 1 bit per 16x16 world cell. */
bool terrain_solid(s16 wx, s16 wy)
{
    u16 cx = (u16)wx >> 4, cy = (u16)wy >> 4;
    if (cx > 255 || cy > 255) return FALSE;
    return (terrain[cy * 32 + (cx >> 3)] >> (7 - (cx & 7))) & 1;
}
