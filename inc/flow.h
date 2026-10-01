#pragma once
#include <genesis.h>

/* Top-level game flow (docs/frontend.md; arcade: docs/re/flow_player.md §2).
 * flow.c: boot, mode select, settings, ranking/SRAM; flow_attract.c: warning,
 * title/ranking, attract demo; flow_game.c: credits, start/NAMING, Earth intro,
 * stage, continue, game over; flow_scene.c: fixed background scenes. */

typedef enum { MODE_ARCADE, MODE_HOME } GameMode;

/* Difficulty: 0-7 = the arcade's DIP levels 1-8 ("~DSW0 & 7", $E6CF; 3 = default "4"); the Home
 * options add two presets beyond them (not arcade): EASY = one step below level 1 (enemy bullet
 * cap offset -4 instead of B0:$8049's -3, slowest bullets), HARD = one step above level 8 (cap
 * offset +4, bullet speed one level above level 8's, max 6). */
enum { DIFF_EASY = 8, DIFF_HARD = 9 };
enum { CONT_OFF, CONT_LIMITED, CONT_UNLIMITED };     /* Home continues */
#define BONUS_NONE 4                                 /* Home: no bonus life (extend_setting 4) */

typedef struct {            /* Arcade: DIP switches (hidden DIP screen), saved in SRAM */
    u8 difficulty;          /* 0-7 */
    u8 lives_b;             /* 0: $09ED[0] lives (3), 1: $09ED[1] (5) */
    u8 bonus;               /* bonus-life table 0-3 ($09EF) */
    u8 cont;                /* allow continue (DSW1 bit 6, $1AB9) */
    u8 demo_sounds;         /* DSW1 bit 7 ($02FA) */
} DipSettings;
typedef struct {            /* Home: options, saved in SRAM */
    u8 difficulty;          /* 0-7, DIFF_EASY, DIFF_HARD */
    u8 lives;               /* 1-7 */
    u8 bonus;               /* 0-3, BONUS_NONE */
    u8 cont;                /* CONT_* */
    u8 credits;             /* 1-9 credits per game (start, 2P join, LIMITED continues), default 3 */
} HomeSettings;
extern DipSettings dip_cfg;
extern HomeSettings home_cfg;

typedef struct {            /* settings in effect (from dip_cfg or home_cfg, flow_apply_config) */
    u8 mode;                /* GameMode */
    u8 difficulty;          /* see above */
    u8 lives;               /* lives per credit ($E032) */
    u8 bonus;               /* bonus-life table 0-3, BONUS_NONE */
    bool allow_continue;
    u8 cont;                /* Home: CONT_* */
    bool demo_sounds;
    u8 color;               /* COLOR option (palette.h): 0 ARCADE, 1 VIVID; not an arcade setting */
} GameConfig;
extern GameConfig game_cfg;
void flow_apply_config(void);         /* game_cfg from the mode's settings */
void settings_save(void);             /* settings + ranking to SRAM */

typedef enum {
    FS_SELECT, FS_SETUP, FS_WARNING, FS_TITLE, FS_DEMO, FS_CREDIT, FS_INTRO, FS_PLAY,
    FS_COIN,                /* Arcade: INSERT COIN screen (entry of the Arcade mode) */
    FS_HOME,                /* Home: logo + MD, START GAME / OPTIONS / BACK */
    FS_CONTROLS, FS_SOUND,  /* Home options submenus */
} FlowState;
extern FlowState flow_state;

extern u8 credits;              /* arcade: coins, 0-9 ($E635-$E637); Home: credits left this game */

/* bonus lives: 0-terminated score list for the chosen table */
const u32 *game_extend_table(void);
/* enemy rank offset for the difficulty (B0:$8049) */
s8 game_rank_offset(void);
/* enemy bullet speed level loaded with a stage music (B0:$80CA, table $813C) */
u8 game_bullet_speed(u8 music, u8 dflt);
/* TRUE while the attract demo runs (input is recorded, sounds follow the DIP) */
bool game_in_demo(void);
/* TRUE when stage logic runs (demo or game): enemies/bosses may update */
bool game_stage_running(void);

void flow_init(void);
void flow_update(void);
void flow_draw(void);

/* ---- shared between the flow modules --------------------------------- */
typedef struct { u32 score; u8 name[3]; } RankEntry;
extern RankEntry ranking[5];
u8 ranking_insert(u32 score, const u8 name[3]);     /* 1-5, 0 = not ranked ($1C02) */

void flow_goto(FlowState s);
void flow_title_enter(void);
void flow_title_update(void);
void flow_warning_enter(void);
void flow_warning_update(void);
void flow_demo_enter(void);
void flow_demo_update(void);
void flow_demo_draw(void);
void flow_demo_abort(void);           /* end the attract demo now (a coin / start) */
void flow_credit_enter(void);
void flow_credit_update(void);
void flow_intro_enter(void);
void flow_intro_update(void);
void flow_play_update(void);
void flow_game_draw(void);
void flow_game_reset(void);
bool flow_try_start(u16 player);      /* attract: coin/start handling; TRUE if a game started */
void flow_coin_enter(void);           /* Arcade INSERT COIN screen (flow_attract.c) */
void flow_coin_update(void);
/* menus (flow_menu.c) */
void menu_select_enter(void);
void menu_select_update(void);
void menu_home_enter(void);           /* Home screen */
void menu_home_update(void);
void flow_home_start(u16 player);     /* Home: a new game (credits filled), intro + NAMING */
void menu_setup_enter(void);          /* DIP screen (Arcade) / OPTIONS (Home) */
void menu_setup_update(void);
void menu_controls_enter(void);
void menu_controls_update(void);
void menu_sound_enter(void);
void menu_sound_update(void);
/* SRAM (flow.c) */
void sram_load(void);

/* ---- stage / background helpers (flow_scene.c) -------------------------- */
void scene_load_set(u16 set);         /* stream a scene set's tiles + palette (several frames) */
bool scene_ready(void);
void scene_show(u16 scene);           /* plane B = this scene (bg.c switched off) */
void scene_off(void);
void scene_update(void);              /* per frame: tile streaming, map resend */
void scene_invalidate(void);          /* its VRAM was reused */
void stage_video_on(void);            /* back to bg.c streaming for the current camera */
void stage_sprites_on(void);          /* sprite VRAM is the sprite cache again */
