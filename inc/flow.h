#pragma once
#include <genesis.h>

/* Top-level game flow (docs/frontend.md; arcade: docs/re/flow_player.md §2).
 * flow.c: boot, mode select, settings, ranking/SRAM; flow_attract.c: warning,
 * title/ranking, attract demo; flow_game.c: credits, start/NAMING, Earth intro,
 * stage, continue, game over; flow_scene.c: fixed background scenes. */

typedef enum { MODE_ARCADE, MODE_HOME } GameMode;

typedef struct {
    u8 mode;                /* GameMode */
    u8 difficulty;          /* 0-7 = arcade DSW0 "~DSW0 & 7" ($E6CF), 3 = default */
    u8 lives;               /* lives per credit ($E032; arcade 3 or 5, $09ED) */
    u8 bonus;               /* bonus-life table 0-3 ($09EF) */
    bool allow_continue;    /* DSW1 bit 6 ($1AB9) */
    bool demo_sounds;       /* DSW1 bit 7 ($02FA) */
} GameConfig;
extern GameConfig game_cfg;

typedef enum {
    FS_SELECT, FS_SETUP, FS_WARNING, FS_TITLE, FS_DEMO, FS_CREDIT, FS_INTRO, FS_PLAY,
} FlowState;
extern FlowState flow_state;

extern u8 credits;              /* arcade mode, 0-9 ($E635-$E637) */

/* bonus lives: 0-terminated score list for the chosen table */
const u32 *game_extend_table(void);
/* enemy rank offset for the difficulty (B0:$8049) */
s8 game_rank_offset(void);
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
void flow_credit_enter(void);
void flow_credit_update(void);
void flow_intro_enter(void);
void flow_intro_update(void);
void flow_play_update(void);
void flow_game_draw(void);
void flow_game_reset(void);
bool flow_try_start(u16 player);      /* attract: coin/start handling; TRUE if a game started */
void flow_coin_check(void);           /* arcade: pad C on an idle pad inserts a coin */

/* ---- stage / background helpers (flow_scene.c) -------------------------- */
void scene_load_set(u16 set);         /* stream a scene set's tiles + palette (several frames) */
bool scene_ready(void);
void scene_show(u16 scene);           /* plane B = this scene (bg.c switched off) */
void scene_off(void);
void scene_update(void);              /* per frame: tile streaming, map resend */
void scene_invalidate(void);          /* its VRAM was reused */
void stage_video_on(void);            /* back to bg.c streaming for the current camera */
void stage_sprites_on(void);          /* sprite VRAM is the sprite cache again */
