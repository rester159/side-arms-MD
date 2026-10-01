#include "game.h"
#include "hud.h"
#include "flow.h"
#include "boss.h"
#include "enemies.h"
#include "gen/frontend.h"
#include "gen/level_data.h"

/* BOSS RUSH (port mode, Home screen; not in the arcade). docs/frontend.md "Boss Rush".
 *
 * Every boss of the game in the arcade's order, one after the other. The rush_list is read from the
 * level timeline (the EV_BOSS records of tools/build_levels.py, in section order: 12 bosses), so
 * each fight is the arcade's own: same boss code, HP, weapons, bullet speed and cap (the section's
 * rank / music records are replayed by level_warp()), same arena. Each arena starts with the camera
 * one pixel before the boss record on its leg; the timeline then runs as in the game: the boss
 * spawns, the camera reaches the halt (EV_HALT; sprite bosses 1-14 px later, wheels after a 262 px
 * ride-in during which their frames are pre-rendered), and the fight is the arcade's. Enemy spawn
 * records are skipped (level_spawns_off). The bosses' POW drops stay (the breather lets the
 * players collect them; they are cleared at the next warp).
 *
 * The players have no lives: an energy bar (Player.energy, HUD row 1) takes the hits (player.c
 * energy_hit). One more boss refills a little. Time = frames of fighting (from the end of the
 * boss card to the killing hit), shown on HUD row 1 and kept as a record in SRAM (flow.c). */

/* ---- tuning (documented in docs/frontend.md) ----------------------------------------------- */
#define RUSH_ENERGY     HUD_ENERGY_MAX  /* 8 segments at the start (and for a 2P join) */
#define RUSH_REFILL     2               /* segments back after each boss */
#define RUSH_SPEED      2               /* speed level 1-3 */
/* weapon levels [WPN_*]: BIT 1, S.G. 1, M.B.L. 1, 3WAY 1, AUTO $10 (one shot every 4 frames) -
 * no POW carriers in the rush, the boss drops can still raise them */
static const u8 RUSH_LOADOUT[6] = { 0, 1, 1, 1, 1, 0x10 };
#define CARD_FRAMES     120             /* boss card; the ships glide in meanwhile (entry 80 f) */
#define BREATHER_FRAMES 180             /* after a kill: explosions, POW, "ENERGY +2" */
#define FINAL_FRAMES    110             /* after the final boss (before the ending task's text at 120) */
#define OUT_FRAMES      90              /* after the last ship's death animation */
#define MAX_BOSSES      16

typedef struct { u8 section, ordinal, kind, music; } RushBoss;
static RushBoss rush_list[MAX_BOSSES];
static u8 rush_n;

enum { RS_CARD, RS_FIGHT, RS_BREATHER, RS_OUT };
static u8 rush_rs, rush_idx;                      /* state, boss index */
static u16 rush_timer, kills_ref;
static bool rush_joined[2], result_clear, new_record;
static u32 rush_frames, saved_hi;
static u8 rush_defeated;

RushRecord rush_best;

/* ---- boss rush_list from the level timeline --------------------------------------------------- */
static void build_list(void)
{
    rush_n = 0;
    for (u16 s = 0; s < LEVEL_SECTIONS; s++) {
        const LevelSection *sec = &level_sections[s];
        u8 ord = 0, music = 0;
        for (u16 i = 0; i < sec->nevents && rush_n < MAX_BOSSES; i++) {
            const LevelEvent *e = &sec->ev[i];
            if (e->op == EV_MUSIC) music = e->a;
            if (e->op != EV_BOSS) continue;
            RushBoss *b = &rush_list[rush_n++];
            b->section = s; b->ordinal = ++ord; b->kind = e->a; b->music = music;
        }
    }
}

/* ---- text helpers ------------------------------------------------------------------------ */
void rush_time_text(char *buf, u32 f)
{
    u32 cs = (f % 60) * 100 / 60, s = f / 60, m = s / 60;
    s %= 60;
    if (m > 99) { m = 99; s = 59; cs = 99; }
    char *p = buf;
    if (m >= 10) *p++ = '0' + m / 10;
    *p++ = '0' + m % 10; *p++ = ':';
    *p++ = '0' + s / 10; *p++ = '0' + s % 10; *p++ = '.';
    *p++ = '0' + cs / 10; *p++ = '0' + cs % 10; *p = 0;
}

static void ctext(s16 row, u8 colour, const char *s)
{
    s16 n = strlen(s);
    hud_text((HUD_COLS - n) / 2, row, colour, s);
}

static char *put_num(char *p, u16 v)
{
    if (v >= 10) *p++ = '0' + v / 10;
    *p++ = '0' + v % 10;
    *p = 0;
    return p;
}

/* Cards use rows 3-5, right under the top HUD rows: with rows 0-5 forced on, the window is still
 * one top block + one bottom block, so the HUD keeps its 2-interrupt split (docs/frontend.md, HUD;
 * text in the middle rows would need the 28-interrupt mode). */
#define CARD_ROW  3
#define CARD_ROWS (HUD_ROW_BIT(3) | HUD_ROW_BIT(4) | HUD_ROW_BIT(5))
#define CARD_SHOWN (HUD_ROWS_TOP | CARD_ROWS)

static void card_clear(void) { hud_clear(CARD_ROWS); hud_rows(0); }
static void card_open(void) { hud_clear(CARD_ROWS); hud_rows(CARD_SHOWN); }

static void card_boss(void)
{
    char t[24], *p;
    card_open();
    p = t; memcpy(p, "BOSS ", 5); p = put_num(p + 5, rush_idx + 1); memcpy(p, " / ", 3); put_num(p + 3, rush_n);
    ctext(CARD_ROW, 4, t);
    p = t; memcpy(p, "SECTION ", 8); put_num(p + 8, rush_list[rush_idx].section + 1);
    ctext(CARD_ROW + 1, 0, rush_list[rush_idx].kind == 2 ? "FINAL BOSS" : t);
    if (rush_idx == 0) ctext(CARD_ROW + 2, 0, "READY");
}

static void card_defeated(void)
{
    char t[24];
    card_open();
    ctext(CARD_ROW, 4, "BOSS DEFEATED");
    memcpy(t, "TIME ", 5); rush_time_text(t + 5, rush_frames);
    ctext(CARD_ROW + 1, 0, t);
    if (rush_idx + 1 < rush_n) ctext(CARD_ROW + 2, 0, "ENERGY +2");
}

/* HUD row 1, under HI: the fight time in whole seconds, redrawn only when it changes (the cards and
 * the result screen give it to 1/100 s); a per-frame redraw cost a frame at the busiest boss moments */
static u16 shown_secs;

static void time_hud(bool force)
{
    u16 secs = rush_frames / 60;
    if (secs == shown_secs && !force) return;
    shown_secs = secs;
    char t[12];
    rush_time_text(t, (u32)secs * 60);
    t[strlen(t) - 3] = 0;                   /* drop ".CC" */
    hud_blank(16, 1, 8);
    hud_text(t[2] == ':' ? 17 : 18, 1, 0, t);
}

/* ---- players ----------------------------------------------------------------------------- */
static void join(u16 i)
{
    Player *p = &players[i];
    rush_joined[i] = TRUE;
    player_start(p, 1);                 /* one life: the energy bar takes the hits */
    p->energy = RUSH_ENERGY;
    player_loadout(p, RUSH_LOADOUT, RUSH_SPEED);
}

static bool all_out(void)
{
    for (u16 i = 0; i < 2; i++) if (rush_joined[i] && !player_out_of_lives(&players[i])) return FALSE;
    return TRUE;
}

static void panel(void)
{
    HudPanel hp;
    memset(&hp, 0, sizeof(hp));
    hp.on = TRUE;
    hp.hi = hi_score;
    hp.twoup = rush_joined[1];
    if (boss_hud.active) hp.boss_bars = boss_hud.bars;
    for (u16 i = 0; i < 2; i++) {
        HudPlayer *h = &hp.pl[i];
        if (!rush_joined[i]) continue;
        h->score = TRUE;
        h->bar = TRUE;
        h->energy_on = TRUE;
        h->energy = players[i].energy;
        if (player_out_of_lives(&players[i])) h->msg = HUD_MSG_GAMEOVER;
    }
    hud_panel(&hp);
}

/* ---- arenas ------------------------------------------------------------------------------ */
static void arena_enter(void)
{
    const RushBoss *b = &rush_list[rush_idx];
    enemies_clear();                    /* bullets, POW and explosions of the last arena */
    level_warp(b->section, b->ordinal); /* bosses_reset, the section's records up to the boss */
    /* one pixel before the boss record, on its leg: the next scroll step fires it */
    const LevelEvent *e = &level_sections[b->section].ev[level.next_event];
    level.scroll_x = e->x - level.dir_x;
    level.scroll_y = e->y - level.dir_y;
    level.vertical = level.dir_y > 0;   /* $E040: spawn side (H: from the left, V: from the top) */
    video_set_camera(cam_x(), cam_y());
    if (b->music) sound_play(b->music); /* the section's music until the boss's own */
    for (u16 i = 0; i < 2; i++) {
        Player *p = &players[i];
        if (!rush_joined[i] || !p->in_play) continue;
        if (p->state == PL_ALIVE) player_spawn(p);         /* entry glide into the new arena */
        for (u16 k = 0; k < MAX_SHOTS; k++) p->shots[k].active = 0;
    }
    rush_rs = RS_CARD; rush_timer = CARD_FRAMES;
    card_boss();
}

void flow_rush_start(u16 starter)
{
    build_list();
    flow_game_reset();                  /* players_init, front-end game state idle */
    memset(rush_joined, 0, sizeof(rush_joined));
    saved_hi = hi_score;
    score_enabled = TRUE;
    extend_setting = BONUS_NONE;        /* no bonus lives: the energy bar is the only reserve */
    level_spawns_off = TRUE;
    rush_idx = 0; rush_defeated = 0; rush_frames = 0;
    /* stage video (as flow_game.c stage_start) */
    hud_screen_reset();
    hud_game_pool_reset();
    level_start(0);
    level_warp(rush_list[0].section, rush_list[0].ordinal);
    stage_video_on();
    stage_sprites_on();
    hud_sprites(TRUE);
    flow_state = FS_RUSH;
    arena_enter();
    time_hud(TRUE);
    join(starter);
}

/* back to the normal game rules (also on a soft reset, flow.c) */
void flow_rush_abort(void)
{
    hud_rows(0);
    level_spawns_off = FALSE;
    hi_score = saved_hi;                /* rush scores do not enter the arcade ranking / HI */
    extend_setting = game_cfg.bonus;
    bosses_reset();
    enemies_clear();
}

static void rush_end(bool clear)
{
    result_clear = clear;
    flow_rush_abort();
    /* record: more bosses beat it, the same count with less time beats it */
    new_record = rush_defeated > rush_best.bosses
              || (rush_defeated && rush_defeated == rush_best.bosses && rush_frames < rush_best.frames);
    if (new_record) { rush_best.bosses = rush_defeated; rush_best.frames = rush_frames; settings_save(); }
    flow_goto(FS_RUSH_END);
}

void flow_rush_update(void)
{
    /* player 2 (or 1) joins with Start once */
    for (u16 i = 0; i < 2; i++)
        if (!rush_joined[i] && (pad[i].pressed & IN_START) && rush_rs != RS_OUT) join(i);
    bool frozen = players_world_frozen();
    if (rush_rs != RS_CARD && !frozen) level_update();      /* the card holds the camera */
    players_update();
    if (!frozen) { enemies_update(); bosses_update(); }
    switch (rush_rs) {
    case RS_CARD:
        if (--rush_timer) break;
        card_clear();
        kills_ref = boss_kills;
        rush_rs = RS_FIGHT;
        break;
    case RS_FIGHT:
        rush_frames++;
        if (boss_kills != kills_ref) {
            rush_defeated++;
            for (u16 i = 0; i < 2; i++) {
                Player *p = &players[i];
                if (!rush_joined[i] || !p->energy) continue;
                p->energy = p->energy + RUSH_REFILL > RUSH_ENERGY ? RUSH_ENERGY : p->energy + RUSH_REFILL;
            }
            rush_rs = RS_BREATHER;
            rush_timer = rush_idx + 1 < rush_n ? BREATHER_FRAMES : FINAL_FRAMES;
            card_defeated();
        }
        break;
    case RS_BREATHER:
        if (--rush_timer) break;
        card_clear();
        if (++rush_idx >= rush_n) { rush_end(TRUE); return; }
        arena_enter();
        break;
    case RS_OUT:
        if (--rush_timer) break;
        rush_end(FALSE);
        return;
    }
    if (rush_rs != RS_OUT && all_out()) {
        rush_rs = RS_OUT; rush_timer = OUT_FRAMES;
        card_open();
        ctext(CARD_ROW + 1, 4, "GAME OVER");
    }
    time_hud(FALSE);
    panel();
}

void flow_rush_draw(void)
{
    players_draw();
    bosses_draw();
    enemies_draw();
}

/* ---- result screen ----------------------------------------------------------------------- */
static u16 end_t;

void flow_rush_end_enter(void)
{
    char t[32], *p;
    hud_sprites(FALSE);
    hud_panel_off();
    hud_screen_reset();
    hud_game_pool_reset();
    scene_off();
    video_set_layers(FALSE, TRUE);
    hud_logo(TRUE, HUD_LOGO_TILE);
    ctext(12, 4, result_clear ? "BOSS RUSH CLEAR" : "BOSS RUSH OVER");
    p = t; memcpy(p, "BOSSES DEFEATED  ", 17); p = put_num(p + 17, rush_defeated); memcpy(p, " / ", 3); put_num(p + 3, rush_n);
    ctext(15, 0, t);
    memcpy(t, "TIME  ", 6); rush_time_text(t + 6, rush_frames);
    ctext(17, 0, t);
    p = t; memcpy(p, "BEST  ", 6); p = put_num(p + 6, rush_best.bosses); memcpy(p, " / ", 3); p = put_num(p + 3, rush_n);
    *p++ = ' '; *p++ = ' '; rush_time_text(p, rush_best.frames);
    ctext(19, 2, t);
    if (new_record) ctext(21, 4, "NEW RECORD");
    for (u16 i = 0; i < 2; i++) {
        if (!rush_joined[i]) continue;
        hud_string(i ? FE_STR_TWOUP : FE_STR_ONEUP, i ? 22 : 6, 23);
        hud_score(i ? 26 : 10, 23, 0, players[i].score);
    }
    hud_string(FE_STR_COPYRIGHT, -1, -1);
    sound_play(0x00);
    sound_play(result_clear ? 0x2C : 0x2E);            /* ending / game over music */
    end_t = 0;
}

void flow_rush_end_update(void)
{
    end_t++;
    if (new_record) {
        if ((end_t % 36) == 0) ctext(21, 4, "NEW RECORD");          /* the battle-text blink, 24/12 */
        else if ((end_t % 36) == 24) hud_blank(10, 21, 20);
    }
    if (end_t < 60) return;
    if ((pad_raw[0].pressed | pad_raw[1].pressed) & (BUTTON_START | BUTTON_A | BUTTON_C)) {
        sound_play(0x00);
        flow_game_reset();
        flow_goto(FS_HOME);
    }
}
