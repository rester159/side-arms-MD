#include "palette.h"
#include "game.h"
#include "hud.h"
#include "flow.h"
#include "sound.h"
#include "gen/frontend.h"

/* Port menus (not arcade screens): the boot screen (Arcade / Home), the Arcade DIP-switch screen
 * (opened by a code on the INSERT COIN screen), the Home screen (logo + MD) and its OPTIONS with
 * CONTROLS and SOUND TEST.
 * docs/frontend.md. Menus read the physical buttons (pad_raw): Up/Down choose, Left/Right change,
 * A / C / Start select (or step a value), B goes back. Settings are saved to SRAM on leaving. */

/* ---- tiny menu engine -------------------------------------------------------------------- */
typedef struct {
    const char *label;
    u8 *val;                        /* NULL: an action entry */
    u8 count;
    const char *const *names;
} MItem;

enum { M_NONE = -1, M_BACK = -2, M_CHANGED = -3 };

static const MItem *items;
static u8 n_items, cursor;
static s16 row0, val_col;
static bool menu_grid;
static void developer_launch_label(void);

static void __attribute__((noinline, optimize("Os"))) menu_draw(void)
{
    for (u16 i = 0; i < n_items; i++) {
        s16 row = menu_grid ? row0 + (i % 6) * 3 : row0 + i * 2;
        s16 col = menu_grid ? (i / 6) * 20 : 0;
        const MItem *m = &items[i];
        bool on = cursor == i;
        hud_blank(col, row, menu_grid ? 20 : HUD_COLS);
        if (menu_grid) hud_blank(col, row + 1, 20);
        hud_text(col + (menu_grid ? 0 : 2), row, 0, on ? ">" : " ");
        hud_text(col + (menu_grid ? 2 : 4), row, on ? 4 : 0, m->label);
        if (m->val) hud_text(menu_grid ? col + 2 : val_col,
            row + (menu_grid ? 1 : 0), on ? 4 : 2, m->names[*m->val]);
    }
    if (flow_state == FS_HOME) developer_launch_label();
}

static void menu_open(const MItem *it, u8 n, s16 first_row, s16 vcol, const char *title)
{
    hud_sprites(FALSE);
    hud_panel_off();
    hud_screen_reset();
    hud_clear(HUD_ROWS_ALL);
    scene_off();
    video_set_layers(FALSE, TRUE);
    menu_grid = game_cfg.mode == MODE_HOME && flow_state == FS_SETUP;
    items = it; n_items = n; row0 = first_row; val_col = vcol; cursor = 0;
    s16 len = 0;
    while (title[len]) len++;
    hud_text((HUD_COLS - len) / 2, 2, 4, title);
    menu_draw();
}

static u16 menu_keys(void)
{
    u16 keys = 0;
    for (u16 i = 0; i < MAX_PLAYERS; i++) keys |= pad_raw[i].pressed;
    return keys;
}

/* index of the activated action entry, M_CHANGED after a value change, M_BACK, M_NONE */
static s16 menu_input(void)
{
    u16 in = menu_keys();
    if (in & BUTTON_B) return M_BACK;
    if (in & BUTTON_UP) { cursor = cursor ? cursor - 1 : n_items - 1; menu_draw(); }
    if (in & BUTTON_DOWN) { cursor = cursor + 1 < n_items ? cursor + 1 : 0; menu_draw(); }
    const MItem *m = &items[cursor];
    if (!m->val) return (in & (BUTTON_A | BUTTON_C | BUTTON_START)) ? cursor : M_NONE;
    if (in & ((menu_grid || flow_state == FS_HOME) ? (BUTTON_LEFT | BUTTON_RIGHT) : (BUTTON_LEFT | BUTTON_RIGHT | BUTTON_A | BUTTON_C))) {
        u8 *v = m->val;
        if (in & BUTTON_LEFT) *v = *v ? *v - 1 : m->count - 1;
        else *v = *v + 1 < m->count ? *v + 1 : 0;
        menu_draw();
        return M_CHANGED;
    }
    return M_NONE;
}

static const char *const ONOFF[2] = { "OFF", "ON" };
static const char *const SOUND_SOURCES[2] = { "ARCADE", "PC ENGINE" };
static const char *const COLOR_NAMES[2] = { "ARCADE", "VIVID" };
static const char *const BONUS[5] = { "100K ONLY", "EVERY 100K", "150K 300K 450K", "200K 400K 600K", "NONE" };
static const char *const NUM[10] = { "0", "1", "2", "3", "4", "5", "6", "7", "8", "9" };

/* ---- boot screen: ARCADE / HOME ----------------------------------------------------------- */
#define SEL_ROW 14

static void select_draw(void)
{
    static const char *const ITEM[2] = { "ARCADE", "HOME" };
    static const char *const DESC[2] = { "ORIGINAL FLOW WITH CREDITS", " OPTIONS, CONTROLS, SAVES " };
    for (u16 i = 0; i < 2; i++) {
        hud_text(14, SEL_ROW + i * 2, 0, cursor == i ? ">" : " ");
        hud_text(16, SEL_ROW + i * 2, cursor == i ? 4 : 0, ITEM[i]);
    }
    hud_blank(0, SEL_ROW + 5, HUD_COLS);
    hud_text(7, SEL_ROW + 5, 2, DESC[cursor]);
}

static void screen_clear(void)
{
    hud_sprites(FALSE);
    hud_panel_off();
    hud_screen_reset();
    hud_clear(HUD_ROWS_ALL);
    scene_off();
    video_set_layers(FALSE, TRUE);
}

void menu_select_enter(void)
{
    screen_clear();
    hud_logo(TRUE, HUD_LOGO_TILE);
    cursor = game_cfg.mode;
    select_draw();
    hud_text(7, 23, 0, "PORTED BY RESTER 159, 2026");
    hud_string(FE_STR_COPYRIGHT, -1, 28 - fe_strings[FE_STR_COPYRIGHT].rows);
    hud_text(36, 27, 0, "V2.0");                    /* port version, bottom right */
}

void menu_select_update(void)
{
    u16 in = menu_keys();
    if (in & (BUTTON_UP | BUTTON_DOWN)) { cursor ^= 1; select_draw(); }
    if (in & (BUTTON_START | BUTTON_A | BUTTON_C)) {
        game_cfg.mode = cursor;
        flow_apply_config();
        settings_save();                /* remembers the mode */
        flow_goto(cursor == MODE_ARCADE ? FS_COIN : FS_HOME);
    }
}

/* ---- Home screen: SIDE ARMS + MD, START GAME / BOSS RUSH / OPTIONS / BACK --------------- */
#define HOME_ROW 15
enum { HOME_START, HOME_BC, HOME_RUSH, HOME_OPTIONS, HOME_DEVELOPER, HOME_BACK, HOME_ITEMS };
static const char *const HOME_ITEM[HOME_ITEMS] = { "NORMAL", "BEFORE CHRIST", "BOSS RUSH", "OPTIONS", "DEVELOPER", "BACK" };
static u8 home_cursor;
static bool developer_unlocked, developer_menu;
static u8 developer_code, developer_mode, developer_round, developer_players;
bool developer_active;
u8 developer_invincible = 1, developer_lives = 1;
static bool developer_warp_pending;
static const char *const DEV_MODE[] = { "NORMAL", "BEFORE CHRIST" };
static const char *const DEV_ROUND[] = { "1", "2", "3", "4", "5", "6", "7", "8", "9", "10" };
static const char *const DEV_PLAYERS[] = { "1", "2", "3", "4" };
static void developer_launch_label(void)
{
    hud_blank(4, 22, 34);
    hud_text(4, 22, 2, "LAUNCH");
    hud_text(11, 22, 2, DEV_MODE[developer_mode]);
    hud_text(25, 22, 2, "ROUND");
    hud_number(31, 22, 2, developer_round + 1, 2);
}
static const MItem DEV_ITEMS[] = {
    { "MODE", &developer_mode, 2, DEV_MODE },
    { "ROUND", &developer_round, 10, DEV_ROUND },
    { "INVINCIBLE", &developer_invincible, 2, ONOFF },
    { "INFINITE LIVES", &developer_lives, 2, ONOFF },
    { "PLAYERS", &developer_players, 4, DEV_PLAYERS },
    { "LAUNCH", NULL, 0, NULL },
    { "SOUND TEST", NULL, 0, NULL },
    { "BACK", NULL, 0, NULL }
};
static void __attribute__((noinline, optimize("Os"))) developer_open(void)
{
    developer_menu = TRUE;
    menu_open(DEV_ITEMS, 8, 6, 25, "DEVELOPER");
    hud_text(4, 24, 2, "PRACTICE - NO RANKING");
}
static void __attribute__((noinline, optimize("Os"))) developer_update(void)
{
    s16 action = menu_input();
    if (action == M_BACK || action == 7) { menu_home_enter(); return; }
    if (action == 6) { developer_menu = FALSE; flow_goto(FS_SOUND); return; }
    if (action != 5) return;
    home_cfg.players = developer_players + 1;
    flow_apply_config();
    developer_menu = FALSE;
    developer_active = TRUE;
    if (developer_mode) {
        extern volatile u16 dbg_bc_native_start_round;
        bc_scene_start(home_cfg.players);
        dbg_bc_native_start_round = developer_round;
    } else {
        developer_warp_pending = TRUE;
        flow_home_start(0);
    }
}
void __attribute__((noinline, optimize("Os"))) developer_normal_update(void)
{
    if (!developer_active) return;
    if (developer_warp_pending && game_stage_running()) {
        extern volatile u16 dbg_warp;
        dbg_warp = developer_round + 1;
        developer_warp_pending = FALSE;
    }
    if (developer_invincible) for (u16 i = 0; i < game_player_limit(); i++)
        if (normal_players[i].in_play) normal_players[i].invuln = 200;
}
static void home_draw(void);
/* Reveal the Home entry; selecting it is a separate action. */
static bool __attribute__((noinline, optimize("Os"))) developer_secret(u16 in)
{
    static const u16 code[] = { BUTTON_UP, BUTTON_DOWN, BUTTON_UP, BUTTON_DOWN,
        BUTTON_LEFT, BUTTON_RIGHT, BUTTON_LEFT, BUTTON_RIGHT };
    if (!in) return FALSE;
    if (in == code[developer_code]) {
        if (++developer_code == 8) {
            developer_code = 0; developer_unlocked = TRUE;
            sound_play(0x1D); home_draw();
            return TRUE;
        }
        return developer_menu;
    }
    developer_code = in == BUTTON_UP ? (developer_code == 4 ? 3 : 1) : 0;
    return FALSE;
}

static bool player_dialog;
static u8 player_choice;
static const char *const PLAYER_OPTIONS[4] = { "1 PLAYER", "2 PLAYERS", "3 PLAYERS", "4 PLAYERS" };

static void player_dialog_draw(void)
{
    for (u16 y = 13; y <= 26; y++) hud_blank(0, y, HUD_COLS);
    hud_text(7, 13, 4, "+------------------------+");
    hud_text(7, 26, 4, "+------------------------+");
    for (u16 y = 14; y < 26; y++) {
        hud_text(7, y, 4, ":"); hud_text(32, y, 4, ":");
    }
    const char *title = HOME_ITEM[home_cursor];
    hud_text((HUD_COLS - strlen(title)) / 2, 14, 4, title);
    for (u16 i = 0; i < 4; i++) {
        hud_text(12, 16 + i * 2, 0, player_choice == i ? ">" : " ");
        hud_text(15, 16 + i * 2, player_choice == i ? 4 : 0, PLAYER_OPTIONS[i]);
    }
    hud_text(10, 24, 2, "A START     B CANCEL");
}

/* the line under the menu: credits for START GAME, the Boss Rush record for BOSS RUSH */
static void home_info(void)
{
    hud_blank(0, 25, HUD_COLS);
    if (home_cursor != HOME_RUSH) {
        hud_text(15, 25, 2, "CREDITS");
        hud_number(23, 25, 2, home_cfg.credits, 1);
        return;
    }
    char t[32], *p = t;
    memcpy(p, "BEST ", 5); p += 5;
    if (!rush_best.bosses) { memcpy(p, "-- NO RECORD --", 16); }
    else {
        if (rush_best.bosses >= 10) *p++ = '0' + rush_best.bosses / 10;
        *p++ = '0' + rush_best.bosses % 10;
        const char *w = rush_best.bosses == 1 ? " BOSS  " : " BOSSES  ";
        while (*w) *p++ = *w++;
        rush_time_text(p, rush_best.frames);
    }
    s16 n = strlen(t);
    hud_text((HUD_COLS - n) / 2, 25, 2, t);
}

static void home_draw(void)
{
    for (u16 i = 0; i < HOME_ITEMS; i++) {
        if (i == HOME_DEVELOPER && !developer_unlocked) continue;
        s16 col = i < 3 ? 3 : 23;
        s16 row = HOME_ROW + (i % 3) * 3;
        hud_text(col - 2, row, 0, home_cursor == i ? ">" : " ");
        hud_text(col, row, home_cursor == i ? 4 : 0, HOME_ITEM[i]);
    }
    home_info();
}

void __attribute__((noinline, optimize("Os"))) menu_home_enter(void)
{
    player_dialog = FALSE;
    developer_menu = developer_active = developer_warp_pending = FALSE;
    developer_code = 0;
    screen_clear();
    hud_logo(TRUE, HUD_LOGO_TILE);
    hud_md((HUD_COLS - FE_MD_COLS) / 2, FE_LOGO_ROW + 7, HUD_MD_TILE);     /* "MD" under the logo */
    home_draw();
    hud_string(FE_STR_COPYRIGHT, -1, 28 - fe_strings[FE_STR_COPYRIGHT].rows);
    hud_text(36, 27, 0, "V2.0");                    /* release version */
}

void __attribute__((noinline, optimize("Os"))) menu_home_update(void)
{
    if (developer_menu) { developer_update(); return; }
    u16 in = menu_keys();
    if (!player_dialog && developer_secret(in)) return;
    if (player_dialog) {
        if (in & BUTTON_B) { menu_home_enter(); return; }
        if (in & (BUTTON_UP | BUTTON_LEFT)) {
            player_choice = (player_choice + 3) & 3;
            player_dialog_draw();
        }
        if (in & (BUTTON_DOWN | BUTTON_RIGHT)) {
            player_choice = (player_choice + 1) & 3;
            player_dialog_draw();
        }
        if (in & (BUTTON_START | BUTTON_A | BUTTON_C)) {
            home_cfg.players = player_choice + 1;
            flow_apply_config();
            settings_save();
            player_dialog = FALSE;
            if (home_cursor == HOME_RUSH) flow_rush_start(0);
            else if (home_cursor == HOME_BC) bc_scene_start(home_cfg.players);
            else flow_home_start(0);
        }
        return;
    }
    if (in & BUTTON_UP) {
        home_cursor = home_cursor ? home_cursor - 1 : HOME_ITEMS - 1;
        if (home_cursor == HOME_DEVELOPER && !developer_unlocked) home_cursor--;
        home_draw();
    }
    if (in & BUTTON_DOWN) {
        home_cursor = home_cursor + 1 < HOME_ITEMS ? home_cursor + 1 : 0;
        if (home_cursor == HOME_DEVELOPER && !developer_unlocked) home_cursor++;
        home_draw();
    }
    if (in & BUTTON_B) { flow_goto(FS_SELECT); return; }
    if (!(in & (BUTTON_START | BUTTON_A | BUTTON_C))) return;
    if (home_cursor == HOME_START || home_cursor == HOME_BC || home_cursor == HOME_RUSH) {
        player_choice = home_cfg.players - 1;
        player_dialog = TRUE;
        player_dialog_draw();
    } else if (home_cursor == HOME_BACK) flow_goto(FS_SELECT);
    else if (home_cursor == HOME_OPTIONS) flow_goto(FS_SETUP);
    else if (home_cursor == HOME_DEVELOPER) developer_open();
}

/* ---- Arcade: DIP switches ---------------------------------------------------------------- */
static const char *const DIFF_ARC[8] = { "1 EASIEST", "2", "3", "4 NORMAL", "5", "6", "7", "8 HARDEST" };
static const char *const LIVES_ARC[2] = { "3", "5" };
static const MItem DIP_ITEMS[] = {
    { "DIFFICULTY", &dip_cfg.difficulty, 8, DIFF_ARC },
    { "LIVES", &dip_cfg.lives_b, 2, LIVES_ARC },
    { "BONUS LIFE", &dip_cfg.bonus, 4, BONUS },
    { "CONTINUE", &dip_cfg.cont, 2, ONOFF },
    { "DEMO SOUNDS", &dip_cfg.demo_sounds, 2, ONOFF },
    { "COLOR", &game_cfg.color, 2, COLOR_NAMES },
    { "BACK", NULL, 0, NULL },
};
#define DIP_BACK 6

/* ---- Home: options ----------------------------------------------------------------------- */
/* difficulty entries: EASY, the 8 arcade levels, HARD */
static const char *const DIFF_HOME[10] = { "EASY", "1 EASIEST", "2", "3", "4 NORMAL", "5", "6", "7", "8 HARDEST", "HARD" };
static const char *const CONT_HOME[3] = { "OFF", "LIMITED", "UNLIMITED" };
static u8 o_diff, o_lives, o_credits, o_players;
static const MItem OPT_ITEMS[] = {
    { "DIFFICULTY", &o_diff, 10, DIFF_HOME },
    { "LIVES", &o_lives, 7, NUM + 1 },
    { "BONUS LIFE", &home_cfg.bonus, 5, BONUS },
    { "CONTINUE", &home_cfg.cont, 3, CONT_HOME },
    { "CREDITS", &o_credits, 9, NUM + 1 },
    { "COLOR", &game_cfg.color, 2, COLOR_NAMES },
    { "PARALLAX", &home_cfg.parallax, 2, ONOFF },       /* docs/parallax.md */
    { "PLAYERS", &o_players, 4, PLAYER_OPTIONS },
    { "MUSIC", &home_cfg.music, 2, SOUND_SOURCES },
    { "CONTROLS", NULL, 0, NULL },
    { "SOUND TEST", NULL, 0, NULL },
    { "BACK", NULL, 0, NULL },
};
enum { OPT_CONTROLS = 9, OPT_SOUND, OPT_BACK };

static void home_from_cfg(void)
{
    u8 d = home_cfg.difficulty;
    o_diff = d == DIFF_EASY ? 0 : d == DIFF_HARD ? 9 : d + 1;
    o_players = home_cfg.players - 1;
    o_lives = home_cfg.lives - 1;
    o_credits = home_cfg.credits - 1;
}

static void home_to_cfg(void)
{
    home_cfg.difficulty = o_diff == 0 ? DIFF_EASY : o_diff == 9 ? DIFF_HARD : o_diff - 1;
    home_cfg.players = o_players + 1;
    home_cfg.lives = o_lives + 1;
    home_cfg.credits = o_credits + 1;
}

static void setup_help(void)
{
    hud_blank(0, 25, HUD_COLS);
    if (game_cfg.mode == MODE_HOME && (cursor == 0 || cursor == 6))
        hud_text(5, 25, 2, "NORMAL / BOSS RUSH ONLY");
    hud_text(4, 27, 2, "B  BACK");
}

static u8 setup_cursor;                 /* kept while a submenu is open */

void menu_setup_enter(void)
{
    if (game_cfg.mode == MODE_ARCADE) {
        menu_open(DIP_ITEMS, sizeof(DIP_ITEMS) / sizeof(MItem), 5, 20, "DIP SWITCHES");
    } else {
        home_from_cfg();
        menu_open(OPT_ITEMS, sizeof(OPT_ITEMS) / sizeof(MItem), 4, 20, "OPTIONS");
        cursor = setup_cursor; setup_cursor = 0;
        menu_draw();
    }
    setup_help();
}

static void setup_leave(FlowState to)
{
    if (game_cfg.mode == MODE_HOME) home_to_cfg();
    flow_apply_config();
    settings_save();
    flow_goto(to);
}

void menu_setup_update(void)
{
    if (game_cfg.mode == MODE_ARCADE) {
        s16 r = menu_input();
        if (r == M_CHANGED && color_mode != game_cfg.color) pal_set_mode(game_cfg.color);   /* live COLOR preview */
        if (r == M_BACK || r == DIP_BACK) setup_leave(FS_SELECT);   /* back to the boot screen */
        return;
    }
    u8 previous_cursor = cursor;
    s16 r = menu_input();
    if (cursor != previous_cursor) setup_help();
    if (r == M_CHANGED && color_mode != game_cfg.color) pal_set_mode(game_cfg.color);
    if (r == M_BACK || r == OPT_BACK) setup_leave(FS_HOME);
    else if (r == OPT_CONTROLS || r == OPT_SOUND) {
        setup_cursor = r;
        home_to_cfg();
        flow_goto(r == OPT_CONTROLS ? FS_CONTROLS : FS_SOUND);
    }
}

/* ---- Home: controls ---------------------------------------------------------------------- */
static const char *const PB_NAMES[PB_COUNT] = { "A", "B", "C", "X", "Y", "Z" };
static const char *const XB_NAMES[XB_COUNT] = { "NONE", "PREV WEAPON", "NEXT WEAPON", "BIT", "S.G.",
                                                "M.B.L.", "3WAY", "AUTO", "LOCK FIRE" };
static const MItem CTL_ITEMS[] = {
    { "FIRE LEFT", &pad_cfg.button[ACT_FIRE_L], PB_COUNT, PB_NAMES },
    { "FIRE RIGHT", &pad_cfg.button[ACT_FIRE_R], PB_COUNT, PB_NAMES },
    { "WEAPON", &pad_cfg.button[ACT_WEAPON], PB_COUNT, PB_NAMES },
    { "BUTTON X", &pad_cfg.extra[0], XB_COUNT, XB_NAMES },
    { "BUTTON Y", &pad_cfg.extra[1], XB_COUNT, XB_NAMES },
    { "BUTTON Z", &pad_cfg.extra[2], XB_COUNT, XB_NAMES },
    { "AUTOFIRE LEFT", &pad_cfg.autofire[0], 2, ONOFF },
    { "AUTOFIRE RIGHT", &pad_cfg.autofire[1], 2, ONOFF },
    { "DEFAULTS", NULL, 0, NULL },
    { "BACK", NULL, 0, NULL },
};
enum { CTL_DEFAULTS = 8, CTL_BACK };
static bool shown_six;

static void controls_info(void)
{
    shown_six = pad_six[0];
    hud_blank(0, 24, HUD_COLS);
    hud_number(5, 24, 2, home_cfg.players, 1);
    hud_text(6, 24, 2, "P");
    hud_text(4, 24, 2, shown_six ? "6 BUTTON PAD: X Y Z ACTIVE" : "3 BUTTON PAD: X Y Z NOT USED");
}

void menu_controls_enter(void)
{
    menu_open(CTL_ITEMS, sizeof(CTL_ITEMS) / sizeof(MItem), 4, 20, "CONTROLS");
    controls_info();
    hud_text(4, 27, 2, "B  BACK");
}

void menu_controls_update(void)
{
    if (pad_six[0] != shown_six) controls_info();
    s16 r = menu_input();
    if (r == CTL_DEFAULTS) { input_defaults(&pad_cfg); menu_draw(); }
    else if (r == M_BACK || r == CTL_BACK) { settings_save(); flow_goto(FS_SETUP); }
}

/* ---- Home: sound test -------------------------------------------------------------------- */
/* command ids and names: docs/re/sound.md (game use from the oracle traces and the port's own
 * calls; '?' = use not confirmed) */
static const char *const MUSIC_NAMES[25] = {
    "20 START", "21 STAGE 1", "22 STAGE 2", "23 STAGE 3", "24 STAGE 4", "25 STAGE 5",
    "26 STAGE 5-6", "27 STAGE 7", "28 STAGE 8", "29 STAGE 9", "2A STAGE CLEAR", "2B (EMPTY)",
    "2C ENDING", "2D (EMPTY)", "2E GAME OVER", "2F (EMPTY)", "30 (EMPTY)", "31 (EMPTY)",
    "32 BOSS 1", "33 BOSS 2", "34 BOSS 3", "35 WHEEL BOSS", "36 FINAL STAGE", "37 (EMPTY)",
    "38 PATCH DEMO ?",
};
static const char *const SFX_NAMES[30] = {
    "01 SHOT", "02 S.G. SHOT", "03 S.G. BURST", "04 M.B.L.", "05 AUTO", "06 AUTO VOLLEY",
    "07 ROBOT RING", "08 ROBOT RING 2", "09 PLAYER IN", "0A COMBINE", "0B SPLIT ?", "0C GAME START",
    "0D BURNING EARTH", "0E CONTINUE", "0F DEATH", "10 STOP SOUNDS", "11 BIG KILL", "12 KILL",
    "13 BOSS IN", "14 BLAST", "15 CRACK", "16 STOP SOUNDS", "17 HIT", "18 LASER", "19 STOP SOUNDS",
    "1A SPEED UP", "1B SPEED DOWN", "1C WEAPON", "1D 1UP", "1E COIN",
};
static const char *const HUCARD_NAMES[21] = {
    "00 TITLE", "01 STAGE 5", "02 STAGE 3", "03 STAGE 4", "04 STAGE 2",
    "05 STAGE 1", "06 STAGE 6", "07 STAGE 7", "08 STAGE 8", "09 JINGLE",
    "0A STAGE CLEAR", "0B GAME OVER", "0C BOSS 3", "0D WHEEL BOSS",
    "0E BOSS 2 / STAGE 9", "0F CREDITS", "10 FINAL STAGE", "11 OPENING",
    "12 BOSS 1", "13 STAGE 2", "14 STAGE 2"
};
static u8 snd_music, snd_sfx, snd_source;
static MItem SND_ITEMS[] = {
    { "MUSIC", &snd_music, 25, MUSIC_NAMES },
    { "SOUND", &snd_sfx, 30, SFX_NAMES },
    { "SOURCE", &snd_source, 2, SOUND_SOURCES },
    { "STOP", NULL, 0, NULL },
    { "BACK", NULL, 0, NULL },
};
enum { SND_SOURCE = 2, SND_STOP, SND_BACK };

void menu_sound_enter(void)
{
    sound_set_music_source(0);
    menu_open(SND_ITEMS, sizeof(SND_ITEMS) / sizeof(MItem), 8, 14, "SOUND TEST");
    hud_text(4, 20, 2, "LEFT RIGHT  CHOOSE");
    hud_text(4, 22, 2, "A  C        PLAY");
    hud_text(4, 24, 2, "B           BACK");
}

void menu_sound_update(void)
{
    u16 in = menu_keys();
    if (cursor < 2 && (in & (BUTTON_A | BUTTON_C | BUTTON_START))) {
        if (cursor == 0 && snd_source) sound_hucard_start(snd_music);
        else sound_play(cursor == 0 ? 0x20 + snd_music : 0x01 + snd_sfx);
        return;
    }
    if (cursor < 2 && !(in & (BUTTON_LEFT | BUTTON_RIGHT | BUTTON_B | BUTTON_UP | BUTTON_DOWN))) return;
    s16 r = menu_input();
    if (r == M_CHANGED && cursor == SND_SOURCE) {
        sound_play(0x00);
        snd_music = 0;
        SND_ITEMS[0].count = snd_source ? 21 : 25;
        SND_ITEMS[0].names = snd_source ? HUCARD_NAMES : MUSIC_NAMES;
        menu_draw();
    }
    if (r == SND_STOP) sound_play(0x00);
    else if (r == M_BACK || r == SND_BACK) { sound_play(0x00); flow_goto(FS_SETUP); }
}
