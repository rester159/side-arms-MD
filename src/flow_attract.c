#include "game.h"
#include "hud.h"
#include "flow.h"
#include "sprites.h"
#include "gen/frontend.h"
#include "gen/level_data.h"

/* Attract loop (docs/re/flow_player.md §2.1): WARNING ($0B84, 240 f) ->
 * title + RANKING TABLE ($0BD1, 360 f + 30 f) -> demo ($0D4A) -> title ...
 * A coin / Start leaves it (flow_try_start). */

void enemies_clear(void) __attribute__((weak));
void enemies_update(void) __attribute__((weak));
void enemies_draw(void) __attribute__((weak));
void bosses_reset(void) __attribute__((weak));
void bosses_update(void) __attribute__((weak));
void bosses_draw(void) __attribute__((weak));
void enemy_spawn_event(u16 section, u16 index) __attribute__((weak));
void enemy_spawn_record(u8 cmd, u16 target) __attribute__((weak));

static u16 timer;
static u8 phase;
static u16 demo_idle;               /* INSERT COIN screen: frames without input */

static void attract_panel(void)
{
    /* attract: "1UP" and "HI" only ($E010 = 0) */
    HudPanel p;
    memset(&p, 0, sizeof(p));
    p.on = TRUE;
    p.hi = hi_score;
    hud_panel(&p);
}

/* ---- Arcade: INSERT COIN screen ---------------------------------------------------------------
 * Entry of the Arcade mode: the title screen's city ($0C05) and logo ($0DF5) with the 1UP/HI row,
 * the World set's own "INSERT COIN" text record ($0E94, colour 2; in the ROM but never drawn by
 * its code) and the credit line of the credit screen (CREDIT $165F + the count, $15D4), both
 * blinking with the arcade's text blink ($1545: 24 frames on, 12 off). A coin (Start, or C) goes
 * to the credit screen at once, as the arcade's credit task does ($08DF -> $12AE). Idle for
 * COIN_IDLE frames: the attract loop (WARNING ...). Up Up Down Down Left Right Left Right: chime
 * (sound $1D) and the DIP-switch screen. */
#define COIN_ROW    16
#define COIN_COL    14
#define COIN_IDLE   900
#define BLINK_ON    24                  /* $1545: "THE BATTLE FOR SURVIVAL..." 24 f shown, 12 f off */
#define BLINK_LEN   36

static const u8 CODE[8] = { IN_UP, IN_UP, IN_DOWN, IN_DOWN, IN_LEFT, IN_RIGHT, IN_LEFT, IN_RIGHT };
static u8 code_pos;
static s8 blink_shown;

static void coin_text(bool on)
{
    if (blink_shown == on) return;
    blink_shown = on;
    if (on) {
        hud_string(FE_STR_INSERT_COIN, COIN_COL, COIN_ROW);
        hud_string(FE_STR_CREDIT, -1, -1);
        hud_number(21, 24, 4, credits, 3);              /* $D6A1, as the credit screen */
    } else {
        hud_string_clear(FE_STR_INSERT_COIN, COIN_COL, COIN_ROW);
        hud_string_clear(FE_STR_CREDIT, -1, -1);
        hud_blank(21, 24, 3);
    }
}

void flow_coin_enter(void)
{
    hud_sprites(FALSE);
    hud_panel_off();
    hud_screen_reset();
    hud_clear(HUD_ROWS_ALL);
    video_set_layers(FALSE, TRUE);
    scene_load_set(0);
    scene_show(FE_SCENE_TITLE);
    hud_logo(TRUE, HUD_LOGO_TILE);
    attract_panel();
    hud_string(FE_STR_COPYRIGHT, -1, -1);
    blink_shown = -1;
    coin_text(TRUE);
    code_pos = 0;
    timer = 0;                          /* blink phase */
    phase = 0;
    demo_idle = 0;
}

static bool secret_code(void)
{
    u8 d = (pad[0].pressed | pad[1].pressed) & (IN_UP | IN_DOWN | IN_LEFT | IN_RIGHT);
    if (!d) return FALSE;
    if (d == CODE[code_pos]) code_pos++;
    else code_pos = d == IN_UP ? (code_pos >= 2 ? 2 : 1) : 0;    /* "UP UP" may restart it */
    if (code_pos < 8) return FALSE;
    code_pos = 0;
    return TRUE;
}

void flow_coin_update(void)
{
    attract_panel();
    if (flow_try_start(0) || flow_try_start(1)) return;
    if (pad_raw[0].pressed | pad_raw[1].pressed) demo_idle = 0;
    if (secret_code()) {
        sound_play(0x1D);               /* chime: the bonus-life jingle */
        flow_goto(FS_SETUP);
        return;
    }
    coin_text(timer < BLINK_ON);
    if (++timer == BLINK_LEN) timer = 0;
    if (++demo_idle >= COIN_IDLE) flow_goto(FS_WARNING);
}

/* ---- WARNING ($0B84) --------------------------------------------------------- */
void flow_warning_enter(void)
{
    hud_sprites(FALSE);
    sound_play(0x00);
    hud_panel_off();
    hud_screen_reset();
    hud_clear(HUD_ROWS_ALL);
    scene_off();
    video_set_layers(FALSE, FALSE);     /* $024E: BG and stars off */
    hud_string(FE_STR_WARNING, -1, -1); /* region text ($0AA0), colour 4 */
    scene_load_set(0);                  /* prepare the title city meanwhile */
    timer = 240;                        /* $022E: 4 x 60 frames */
}

void flow_warning_update(void)
{
    if (flow_try_start(0) || flow_try_start(1)) return;
    if (!--timer) flow_goto(FS_TITLE);
}

/* ---- title + ranking ($0BD1) --------------------------------------------------- */
static const u8 ORD_ROW[5] = { 15, 17, 19, 21, 23 };

static void draw_ranking(void)
{
    hud_string(FE_STR_RANK_HEAD, -1, -1);     /* "◆◆◆ RANKING TABLE ◆◆◆" */
    hud_string(FE_STR_RANK_ORD, -1, -1);      /* 1ST..5TH, colour 2 */
    for (u16 i = 0; i < 5; i++) {
        hud_score(13, ORD_ROW[i], 2, ranking[i].score);         /* $0625 at $D459.. */
        u16 nm[3] = { ranking[i].name[0], ranking[i].name[1], ranking[i].name[2] };
        hud_codes(24, ORD_ROW[i], 2, nm, 3);                    /* $06B8 at $D464.. */
    }
    hud_string(FE_STR_COPYRIGHT, -1, -1);
}

void flow_title_enter(void)
{
    hud_sprites(FALSE);
    hud_screen_reset();
    video_set_layers(FALSE, TRUE);
    scene_load_set(0);
    scene_show(FE_SCENE_TITLE);         /* $0C05: scroll $180,0 */
    hud_logo(TRUE, HUD_LOGO_TILE);      /* $0DF5 */
    attract_panel();                    /* top row first: it owns rows 0-2 / 25-27 */
    draw_ranking();
    phase = 0;
    timer = 360;                        /* $0C95: 6 x 60 frames */
}

void flow_title_update(void)
{
    attract_panel();
    if (flow_try_start(0) || flow_try_start(1)) return;
    if (--timer) return;
    if (phase == 0) {
        /* $0C9A: ranking, header and copyright cleared, the logo stays 30 f */
        hud_string_clear(FE_STR_RANK_HEAD, -1, -1);
        hud_string_clear(FE_STR_RANK_ORD, -1, -1);
        hud_clear(0x00FFF800UL & ~(0xFFUL << FE_LOGO_ROW));
        hud_string_clear(FE_STR_COPYRIGHT, -1, -1);
        phase = 1; timer = 30;          /* $0CB2 */
        return;
    }
    flow_goto(FS_DEMO);
}

/* ---- attract demo ($0D4A) ------------------------------------------------------ */
static u8 variant;                      /* $E140: toggles each demo */
static const FeDemoScript *script;
static u16 next_ev;
static struct { const u16 *p; u16 count, i, left; u8 val; } din[2];
static u16 demo_frames;
static bool in_demo;

bool game_in_demo(void) { return in_demo; }

void flow_demo_enter(void)
{
    in_demo = TRUE;
    score_enabled = FALSE;              /* $E010 = 0: no scoring */
    players_init();
    hud_sprites(TRUE);
    hud_screen_reset();
    scene_off();
    stage_sprites_on();
    if (enemies_clear) enemies_clear();
    if (bosses_reset) bosses_reset();
    /* $0D6E: scroll 0,0, X +1, rank 2 ($0DC7); demo scroll script B1:$8000
     * (inputs $9600/$9800) or B1:$8074 ($9A00/$9D00) */
    script = &fe_demo_scripts[variant];
    next_ev = 0;
    level.section = 0;
    level.next_event = level_sections[0].nevents;   /* the stage script stays silent */
    level.scroll_x = level.scroll_y = 0;
    level.dir_x = 1; level.dir_y = 0;
    level.mode = SCROLL_RUN;
    level.rank = 2;
    level.tick = 0;
    if (variant == 0) {
        /* item showcase in empty space (scroll $B00,$700): the background
         * is blank there, so plane B's VRAM can hold the logo */
        video_set_layers(FALSE, TRUE);
        scene_invalidate();
        hud_logo(TRUE, VRAM_BG_TILE);
    } else {
        stage_video_on();               /* real terrain: no VRAM left for the logo */
    }
    for (u16 i = 0; i < 2; i++) {
        const FeDemoInput *in = &fe_demo_inputs[variant * 2 + i];
        din[i].p = in->pairs; din[i].count = in->count; din[i].i = 0; din[i].left = 1; din[i].val = 0;
        /* $0DCC: both players, speed 1, one life */
        player_start(&players[i], 1);
    }
    demo_frames = 0;
}

static void demo_end(void)
{
    in_demo = FALSE;
    sound_play(0x00);
    hud_sprites(FALSE);
    for (u16 i = 0; i < 2; i++) { players[i].state = PL_OFF; players[i].score = 0; }
    if (enemies_clear) enemies_clear();
    if (bosses_reset) bosses_reset();
    variant ^= 1;
    hud_logo(FALSE, 0);
    video_set_layers(FALSE, TRUE);
    scene_invalidate();
}

void flow_demo_abort(void)
{
    if (in_demo) demo_end();
}

static void demo_inputs(void)
{
    input_clear_requests();             /* real pads' X/Y/Z must not steer the demo players */
    /* B2:$802C: (value, frames) pairs; inputs are active-high with the same
     * bit layout as the port's pads (R L D U, buttons 1-3) */
    for (u16 i = 0; i < 2; i++) {
        if (!--din[i].left) {
            if (din[i].i < din[i].count) {
                u16 e = din[i].p[din[i].i++];
                din[i].val = e >> 8;
                din[i].left = (e & 0xFF) ? (e & 0xFF) : 256;
            } else { din[i].val = 0; din[i].left = 0xFFFF; }
        }
        u8 v = din[i].val & 0x7F;
        pad[i].pressed = v & ~pad[i].held;
        pad[i].held = v;
    }
}

static void demo_events(void)
{
    while (next_ev < script->count) {
        const FeDemoEvent *e = &script->ev[next_ev];
        if (e->x != (u16)level.scroll_x || e->y != (u16)level.scroll_y) break;
        next_ev++;
        switch (e->op) {
        case FE_DEV_TELEPORT: level.scroll_x = e->b; level.scroll_y = e->c; video_set_camera(cam_x(), cam_y()); break;
        case FE_DEV_DIR_X: level.dir_x = e->a == 0 ? 0 : e->a == 1 ? 1 : -1; break;
        case FE_DEV_DIR_Y: level.dir_y = e->a == 0 ? 0 : e->a == 1 ? 1 : -1; break;
        case FE_DEV_MUSIC: sound_play(e->a); break;
        case FE_DEV_SPAWN:
            if (enemy_spawn_record) enemy_spawn_record(e->a, e->b);
            else if (e->c != 0xFFFF && enemy_spawn_event) enemy_spawn_event(e->c >> 12, e->c & 0xFFF);
            break;
        case FE_DEV_END: next_ev = 0xFFFF; return;   /* B1:$806E: back to the title */
        }
    }
}

void flow_demo_update(void)
{
    /* real pads first: a coin / Start ends the demo */
    if (flow_try_start(0) || flow_try_start(1)) { if (in_demo) demo_end(); return; }
    demo_inputs();
    bool frozen = players_world_frozen();
    if (!frozen) { level_update(); demo_events(); }
    players_update();
    if (!frozen) {
        if (enemies_update) enemies_update();
        if (bosses_update) bosses_update();
    }
    HudPanel hp;
    memset(&hp, 0, sizeof(hp));
    hp.on = TRUE; hp.hi = hi_score;
    hp.pl[0].bar = hp.pl[1].bar = TRUE;
    hud_panel(&hp);
    demo_frames++;
    /* the demo ends at the script end or when a player's death animation is
     * over ($1A46 -> $1BF7 with $E010 = 0); variant 2's script has no end
     * record, it is capped */
    bool dead = player_out_of_lives(&players[0]) || player_out_of_lives(&players[1]);
    if (next_ev == 0xFFFF || dead || demo_frames >= 3600) {
        demo_end();
        flow_goto(FS_TITLE);
    }
}

void flow_demo_draw(void)
{
    players_draw();
    if (bosses_draw) bosses_draw();
    if (enemies_draw) enemies_draw();
}
