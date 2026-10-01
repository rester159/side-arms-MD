#include "game.h"
#include "hud.h"
#include "flow.h"
#include "gen/frontend.h"

/* Top-level flow: boot -> mode select (Arcade / Home) -> settings -> the
 * arcade attract loop (flow_attract.c) and game (flow_game.c).
 * docs/frontend.md; arcade flow docs/re/flow_player.md §2. */

GameConfig game_cfg;
FlowState flow_state;
u8 credits;
RankEntry ranking[5];

const u32 *game_extend_table(void) { return fe_extend_tables[game_cfg.bonus & 3]; }
s8 game_rank_offset(void) { return fe_rank_offset[game_cfg.difficulty & 7]; }

/* ---- ranking ($E680, 5 x {score, name}; insertion $1C02) + SRAM ------------------ */
#define SRAM_MAGIC 0x53415231UL      /* "SAR1" */

static u8 sram_sum(const u8 *b, u16 n)
{
    u8 s = 0x5A;
    for (u16 i = 0; i < n; i++) s = (u8)((s << 1) | (s >> 7)) ^ b[i];
    return s;
}

static void ranking_save(void)
{
    u8 buf[5 * 7];
    for (u16 i = 0; i < 5; i++) {
        u32 v = ranking[i].score;
        buf[i * 7 + 0] = v >> 24; buf[i * 7 + 1] = v >> 16; buf[i * 7 + 2] = v >> 8; buf[i * 7 + 3] = v;
        memcpy(buf + i * 7 + 4, ranking[i].name, 3);
    }
    SRAM_enable();
    SRAM_writeLong(0, SRAM_MAGIC);
    for (u16 i = 0; i < sizeof(buf); i++) SRAM_writeByte(4 + i, buf[i]);
    SRAM_writeByte(4 + sizeof(buf), sram_sum(buf, sizeof(buf)));
    SRAM_disable();
}

static void ranking_load(void)
{
    u8 buf[5 * 7];
    for (u16 i = 0; i < 5; i++) {
        ranking[i].score = fe_default_ranking[i].score;
        memcpy(ranking[i].name, fe_default_ranking[i].name, 3);
    }
    SRAM_enableRO();
    bool ok = SRAM_readLong(0) == SRAM_MAGIC;
    for (u16 i = 0; ok && i < sizeof(buf); i++) buf[i] = SRAM_readByte(4 + i);
    ok = ok && SRAM_readByte(4 + sizeof(buf)) == sram_sum(buf, sizeof(buf));
    SRAM_disable();
    if (ok)
        for (u16 i = 0; i < 5; i++) {
            const u8 *b = buf + i * 7;
            ranking[i].score = ((u32)b[0] << 24) | ((u32)b[1] << 16) | ((u16)b[2] << 8) | b[3];
            memcpy(ranking[i].name, b + 4, 3);
        }
    hi_score = ranking[0].score;     /* $E600 = top ranking score */
}

/* $1C02: compare with the 5 entries from the bottom up, shift, insert. */
u8 ranking_insert(u32 score, const u8 name[3])
{
    if (score <= ranking[4].score) return 0;
    s16 i = 4;
    while (i > 0 && score > ranking[i - 1].score) { ranking[i] = ranking[i - 1]; i--; }
    ranking[i].score = score;
    memcpy(ranking[i].name, name, 3);
    ranking_save();
    return i + 1;
}

/* ---- mode select / settings -------------------------------------------------- */
static u8 cursor;

typedef struct { const char *label; u8 *val; u8 count; const char *const *names; } Option;

static const char *const DIFF_ARC[8] = { "1 EASIEST", "2", "3", "4 NORMAL", "5", "6", "7", "8 HARDEST" };
static const char *const DIFF_HOME[4] = { "EASY", "NORMAL", "HARD", "HARDEST" };
static const u8 DIFF_HOME_VAL[4] = { 1, 3, 5, 7 };
static const char *const BONUS[4] = { "100K ONLY", "EVERY 100K", "150K 300K 450K", "200K 400K 600K" };
static const char *const ONOFF[2] = { "OFF", "ON" };
static const char *const LIVES_ARC[2] = { "3", "5" };
static const char *const LIVES_HOME[7] = { "1", "2", "3", "4", "5", "6", "7" };
static u8 opt_diff, opt_lives, opt_bonus, opt_cont, opt_demo;

static const Option OPTS_ARCADE[] = {
    { "DIFFICULTY", &opt_diff, 8, DIFF_ARC }, { "LIVES", &opt_lives, 2, LIVES_ARC },
    { "BONUS LIFE", &opt_bonus, 4, BONUS }, { "CONTINUE", &opt_cont, 2, ONOFF },
    { "DEMO SOUNDS", &opt_demo, 2, ONOFF },
};
static const Option OPTS_HOME[] = {
    { "DIFFICULTY", &opt_diff, 4, DIFF_HOME }, { "LIVES", &opt_lives, 7, LIVES_HOME },
    { "BONUS LIFE", &opt_bonus, 4, BONUS },
};

#define SEL_ROW   14
#define OPT_ROW   7

static void select_draw(void)
{
    static const char *const ITEM[2] = { "ARCADE", "HOME" };
    static const char *const DESC[2] = { "ORIGINAL FLOW WITH CREDITS", " FREE PLAY  -  OPTIONS  " };
    for (u16 i = 0; i < 2; i++) {
        hud_text(14, SEL_ROW + i * 2, 0, cursor == i ? ">" : " ");
        hud_text(16, SEL_ROW + i * 2, cursor == i ? 4 : 0, ITEM[i]);
    }
    hud_blank(0, SEL_ROW + 5, 40);
    hud_text(7, SEL_ROW + 5, 2, DESC[cursor]);
}

static void select_enter(void)
{
    hud_sprites(FALSE);
    hud_panel_off();
    hud_screen_reset();
    hud_clear(HUD_ROWS_ALL);
    scene_off();
    video_set_layers(FALSE, TRUE);
    hud_logo(TRUE, HUD_LOGO_TILE);
    cursor = game_cfg.mode;
    select_draw();
    hud_text(7, 23, 0, "PORTED BY RESTER 159, 2026");
    hud_string(FE_STR_COPYRIGHT, -1, -1);
}

static void select_update(void)
{
    u8 in = pad[0].pressed | pad[1].pressed;
    if (in & (IN_UP | IN_DOWN)) { cursor ^= 1; select_draw(); }
    if (in & (IN_START | IN_FIRE_L | IN_FIRE_R)) {
        game_cfg.mode = cursor;
        flow_goto(FS_SETUP);
    }
}

static const Option *opts(u16 *n)
{
    if (game_cfg.mode == MODE_ARCADE) { *n = sizeof(OPTS_ARCADE) / sizeof(Option); return OPTS_ARCADE; }
    *n = sizeof(OPTS_HOME) / sizeof(Option); return OPTS_HOME;
}

static void setup_draw(void)
{
    u16 n;
    const Option *o = opts(&n);
    for (u16 i = 0; i < n; i++) {
        s16 row = OPT_ROW + i * 2;
        hud_blank(0, row, 40);
        hud_text(2, row, 0, cursor == i ? ">" : " ");
        hud_text(4, row, cursor == i ? 4 : 0, o[i].label);
        hud_text(18, row, cursor == i ? 4 : 2, o[i].names[*o[i].val]);
    }
    s16 row = OPT_ROW + n * 2 + 1;
    hud_text(2, row, 0, cursor == n ? ">" : " ");
    hud_text(4, row, cursor == n ? 4 : 0, "START GAME");
}

static void setup_enter(void)
{
    hud_screen_reset();
    hud_clear(HUD_ROWS_ALL);
    cursor = 0;
    if (game_cfg.mode == MODE_ARCADE) {
        opt_diff = game_cfg.difficulty; opt_lives = game_cfg.lives == FE_LIVES_B;
        opt_bonus = game_cfg.bonus; opt_cont = game_cfg.allow_continue; opt_demo = game_cfg.demo_sounds;
        hud_text(14, 3, 4, "DIP SWITCHES");
    } else {
        opt_diff = game_cfg.difficulty >= 6 ? 3 : game_cfg.difficulty >= 4 ? 2 : game_cfg.difficulty >= 2 ? 1 : 0;
        opt_lives = game_cfg.lives >= 1 && game_cfg.lives <= 7 ? game_cfg.lives - 1 : 2;
        opt_bonus = game_cfg.bonus;
        hud_text(16, 3, 4, "OPTIONS");
    }
    hud_text(4, 24, 2, "UP DOWN SELECT  LEFT RIGHT SET");
    setup_draw();
}

static void setup_apply(void)
{
    if (game_cfg.mode == MODE_ARCADE) {
        game_cfg.difficulty = opt_diff;
        game_cfg.lives = opt_lives ? FE_LIVES_B : FE_LIVES_A;
        game_cfg.bonus = opt_bonus;
        game_cfg.allow_continue = opt_cont;
        game_cfg.demo_sounds = opt_demo;
    } else {
        game_cfg.difficulty = DIFF_HOME_VAL[opt_diff];
        game_cfg.lives = opt_lives + 1;
        game_cfg.bonus = opt_bonus;
        game_cfg.allow_continue = TRUE;       /* free continues */
        game_cfg.demo_sounds = TRUE;
    }
    extend_setting = game_cfg.bonus;    /* player.c bonus-life table (DSW0 bits 4-5) */
    credits = 0;
}

static void setup_update(void)
{
    u16 n;
    const Option *o = opts(&n);
    u8 in = pad[0].pressed | pad[1].pressed;
    if (in & IN_UP) { cursor = cursor ? cursor - 1 : n; setup_draw(); }
    if (in & IN_DOWN) { cursor = cursor < n ? cursor + 1 : 0; setup_draw(); }
    if (cursor < n && (in & (IN_LEFT | IN_RIGHT | IN_FIRE_L | IN_FIRE_R))) {
        u8 *v = o[cursor].val;
        if (in & IN_LEFT) *v = *v ? *v - 1 : o[cursor].count - 1;
        else *v = *v + 1 < o[cursor].count ? *v + 1 : 0;
        setup_draw();
    }
    if ((in & IN_START) || (cursor == n && (in & (IN_FIRE_L | IN_FIRE_R)))) {
        setup_apply();
        flow_goto(FS_WARNING);
    }
    if (in & IN_WEAPON) flow_goto(FS_SELECT);
}

/* ---- dispatch ------------------------------------------------------------------ */
void flow_goto(FlowState s)
{
    flow_state = s;
    switch (s) {
    case FS_SELECT:  select_enter(); break;
    case FS_SETUP:   setup_enter(); break;
    case FS_WARNING: flow_warning_enter(); break;
    case FS_TITLE:   flow_title_enter(); break;
    case FS_DEMO:    flow_demo_enter(); break;
    case FS_CREDIT:  flow_credit_enter(); break;
    case FS_INTRO:   flow_intro_enter(); break;
    case FS_PLAY:    break;
    }
}

void flow_init(void)
{
    game_cfg.mode = MODE_ARCADE;
    game_cfg.difficulty = 3;                /* "4 (normal)" */
    game_cfg.lives = FE_LIVES_A;
    game_cfg.bonus = 0;                     /* MAME default: 100000 once */
    game_cfg.allow_continue = TRUE;
    game_cfg.demo_sounds = TRUE;
    hud_init();
    ranking_load();
    flow_game_reset();
    flow_goto(FS_SELECT);
}

void flow_update(void)
{
    /* soft reset: A+B+C+Start on pad 1 -> mode select */
    if ((pad[0].held & (IN_FIRE_L | IN_FIRE_R | IN_WEAPON | IN_START)) == (IN_FIRE_L | IN_FIRE_R | IN_WEAPON | IN_START)
        && pad[0].pressed && flow_state != FS_SELECT) {
        sound_play(0x00);
        flow_game_reset();
        flow_goto(FS_SELECT);
        return;
    }
    switch (flow_state) {
    case FS_SELECT:  select_update(); break;
    case FS_SETUP:   setup_update(); break;
    case FS_WARNING: flow_warning_update(); break;
    case FS_TITLE:   flow_title_update(); break;
    case FS_DEMO:    flow_demo_update(); break;
    case FS_CREDIT:  flow_credit_update(); break;
    case FS_INTRO:   flow_intro_update(); break;
    case FS_PLAY:    flow_play_update(); break;
    }
}

void flow_draw(void)
{
    if (flow_state == FS_DEMO) flow_demo_draw();
    else if (flow_state == FS_PLAY) flow_game_draw();
    scene_update();
    hud_frame();
}
