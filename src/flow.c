#include "palette.h"
#include "game.h"
#include "hud.h"
#include "flow.h"
#include "gen/frontend.h"

/* Top-level flow: boot screen (Arcade / Home, flow_menu.c) -> Arcade: INSERT COIN screen and the
 * arcade attract loop (flow_attract.c); Home: the Home screen and its options (flow_menu.c);
 * both -> the game (flow_game.c). Settings and the ranking live in SRAM (below).
 * docs/frontend.md; arcade flow docs/re/flow_player.md §2. */

GameConfig game_cfg;
DipSettings dip_cfg;
HomeSettings home_cfg;
FlowState flow_state;
u8 credits;
RankEntry ranking[5];

const u32 *game_extend_table(void) { return fe_extend_tables[game_cfg.bonus & 3]; }

s8 game_rank_offset(void)
{
    u8 d = game_cfg.difficulty;
    if (d == DIFF_EASY) return fe_rank_offset[0] - 1;
    if (d == DIFF_HARD) return fe_rank_offset[7] + 1;
    return fe_rank_offset[d & 7];
}

/* B0:$80CA-$812F: music $21-$29 -> stage 0-8, $36 -> 9; $E050 = $813C[stage * 8 + difficulty] */
u8 game_bullet_speed(u8 music, u8 dflt)
{
    u16 k = music == 0x36 ? 9 : (u16)(music - 0x21);
    if (k > 9) return dflt;
    u8 d = game_cfg.difficulty;
    if (d == DIFF_EASY) return 3;                       /* the slowest level (enemies.c: 3-6) */
    if (d == DIFF_HARD) { u8 v = fe_bullet_speed[k * 8 + 7] + 1; return v > 6 ? 6 : v; }
    return fe_bullet_speed[k * 8 + (d & 7)];
}

void flow_apply_config(void)
{
    if (game_cfg.mode == MODE_ARCADE) {
        game_cfg.difficulty = dip_cfg.difficulty;
        game_cfg.lives = dip_cfg.lives_b ? FE_LIVES_B : FE_LIVES_A;
        game_cfg.bonus = dip_cfg.bonus;
        game_cfg.allow_continue = dip_cfg.cont;
        game_cfg.cont = dip_cfg.cont ? CONT_LIMITED : CONT_OFF;
        game_cfg.demo_sounds = dip_cfg.demo_sounds;
    } else {
        game_cfg.difficulty = home_cfg.difficulty;
        game_cfg.lives = home_cfg.lives;
        game_cfg.bonus = home_cfg.bonus;
        game_cfg.cont = home_cfg.cont;
        game_cfg.allow_continue = home_cfg.cont != CONT_OFF;
        game_cfg.demo_sounds = TRUE;
    }
    extend_setting = game_cfg.bonus;    /* player.c bonus-life table (DSW0 bits 4-5) */
    video_set_parallax(game_cfg.mode == MODE_HOME && home_cfg.parallax);   /* Home only (docs/parallax.md) */
    pal_set_mode(game_cfg.color);
    credits = 0;
}

static void settings_defaults(void)
{
    dip_cfg.difficulty = 3;                 /* "4 (normal)" */
    dip_cfg.lives_b = 0;                    /* 3 */
    dip_cfg.bonus = 0;                      /* MAME default: 100000 once */
    dip_cfg.cont = TRUE;
    dip_cfg.demo_sounds = TRUE;
    home_cfg.difficulty = 3;
    home_cfg.lives = 3;
    home_cfg.bonus = 0;
    home_cfg.cont = CONT_LIMITED;
    home_cfg.credits = 3;
    home_cfg.parallax = 1;
    game_cfg.mode = MODE_ARCADE;
    game_cfg.color = COLOR_VIVID;
    input_defaults(&pad_cfg);
    rush_best.bosses = 0;                   /* no Boss Rush record yet */
    rush_best.frames = 0;
}

/* ---- SRAM ---------------------------------------------------------------------------------- *
 * Cartridge SRAM (header "RA", $200001, odd bytes), byte offsets:
 *   0-3   magic: "SAR1" (v1, ranking only) or "SAR2" (v2)
 *   4-38  ranking: 5 x {score u32, 3 arcade char codes}            (same in v1 and v2)
 *   39    ranking checksum                                          (same in v1 and v2)
 *   40    settings version: 1, 2 or 3 (SET_VERSION)
 *   41-60 settings: DIP x5, Home x5, COLOR, last mode, controls x8 (versions 1-3)
 *   61-65 versions 2-3: Boss Rush record: bosses defeated, fight time in frames (u32, big endian)
 *   66    version 3: Home PARALLAX (0 / 1)
 *   61 / 66 / 67  settings checksum (version 1 / 2 / 3)
 * A v1 save keeps its ranking (settings take their defaults and are written as v3 on the next
 * save); a version-1 settings block keeps its settings (the record starts empty), a version-2
 * block its settings and record (PARALLAX starts ON); a bad checksum, an unknown settings
 * version or an out-of-range value resets that block. */
#define SRAM_MAGIC_V1 0x53415231UL      /* "SAR1" */
#define SRAM_MAGIC    0x53415232UL      /* "SAR2" */
#define RANK_OFS      4
#define RANK_LEN      (5 * 7)
#define SET_OFS       (RANK_OFS + RANK_LEN + 1)
#define SET_VERSION   3
#define SET_VALUES    20                /* settings bytes after the version byte */
#define SET_LEN_V1    (1 + SET_VALUES)
#define SET_LEN_V2    (SET_LEN_V1 + 5)  /* + Boss Rush record */
#define SET_LEN       (SET_LEN_V2 + 1)  /* + Home PARALLAX */
#define RUSH_MAX_BOSSES 16

static u8 sram_sum(const u8 *b, u16 n)
{
    u8 s = 0x5A;
    for (u16 i = 0; i < n; i++) s = (u8)((s << 1) | (s >> 7)) ^ b[i];
    return s;
}

/* settings block <-> bytes; each value with its count (valid range 0..count-1, +min) */
static u8 *const SET_VAL[SET_VALUES] = {
    &dip_cfg.difficulty, &dip_cfg.lives_b, &dip_cfg.bonus, &dip_cfg.cont, &dip_cfg.demo_sounds,
    &home_cfg.difficulty, &home_cfg.lives, &home_cfg.bonus, &home_cfg.cont, &home_cfg.credits,
    &game_cfg.color, &game_cfg.mode,
    &pad_cfg.button[0], &pad_cfg.button[1], &pad_cfg.button[2],
    &pad_cfg.extra[0], &pad_cfg.extra[1], &pad_cfg.extra[2], &pad_cfg.autofire[0], &pad_cfg.autofire[1],
};
static const u8 SET_MIN[SET_VALUES] = { 0, 0, 0, 0, 0,  0, 1, 0, 0, 1,  0, 0,  0, 0, 0, 0, 0, 0, 0, 0 };
static const u8 SET_MAX[SET_VALUES] = { 7, 1, 3, 1, 1,  9, 7, 4, 2, 9,  1, 1,  5, 5, 5,
                                         XB_COUNT - 1, XB_COUNT - 1, XB_COUNT - 1, 1, 1 };

static void sram_save(void)
{
    u8 rb[RANK_LEN], sb[SET_LEN];
    for (u16 i = 0; i < 5; i++) {
        u32 v = ranking[i].score;
        rb[i * 7 + 0] = v >> 24; rb[i * 7 + 1] = v >> 16; rb[i * 7 + 2] = v >> 8; rb[i * 7 + 3] = v;
        memcpy(rb + i * 7 + 4, ranking[i].name, 3);
    }
    sb[0] = SET_VERSION;
    for (u16 i = 0; i < SET_VALUES; i++) sb[1 + i] = *SET_VAL[i];
    u32 t = rush_best.frames;
    sb[SET_LEN_V1] = rush_best.bosses;
    sb[SET_LEN_V1 + 1] = t >> 24; sb[SET_LEN_V1 + 2] = t >> 16; sb[SET_LEN_V1 + 3] = t >> 8; sb[SET_LEN_V1 + 4] = t;
    sb[SET_LEN_V2] = home_cfg.parallax;
    SRAM_enable();
    SRAM_writeLong(0, SRAM_MAGIC);
    for (u16 i = 0; i < RANK_LEN; i++) SRAM_writeByte(RANK_OFS + i, rb[i]);
    SRAM_writeByte(RANK_OFS + RANK_LEN, sram_sum(rb, RANK_LEN));
    for (u16 i = 0; i < SET_LEN; i++) SRAM_writeByte(SET_OFS + i, sb[i]);
    SRAM_writeByte(SET_OFS + SET_LEN, sram_sum(sb, SET_LEN));
    SRAM_disable();
}

void settings_save(void) { sram_save(); }

void sram_load(void)
{
    u8 rb[RANK_LEN], sb[SET_LEN];
    for (u16 i = 0; i < 5; i++) {
        ranking[i].score = fe_default_ranking[i].score;
        memcpy(ranking[i].name, fe_default_ranking[i].name, 3);
    }
    settings_defaults();
    SRAM_enableRO();
    u32 magic = SRAM_readLong(0);
    bool v2 = magic == SRAM_MAGIC;
    bool rank_ok = v2 || magic == SRAM_MAGIC_V1;
    for (u16 i = 0; rank_ok && i < RANK_LEN; i++) rb[i] = SRAM_readByte(RANK_OFS + i);
    rank_ok = rank_ok && SRAM_readByte(RANK_OFS + RANK_LEN) == sram_sum(rb, RANK_LEN);
    for (u16 i = 0; v2 && i < SET_LEN; i++) sb[i] = SRAM_readByte(SET_OFS + i);
    /* settings version 1 (21 bytes + checksum) or 2 (26 bytes + checksum) */
    u16 len = !v2 ? 0 : sb[0] == 1 ? SET_LEN_V1 : sb[0] == 2 ? SET_LEN_V2 : sb[0] == SET_VERSION ? SET_LEN : 0;
    bool set_ok = len && SRAM_readByte(SET_OFS + len) == sram_sum(sb, len);
    SRAM_disable();
    for (u16 i = 0; set_ok && i < SET_VALUES; i++)
        if (sb[1 + i] < SET_MIN[i] || sb[1 + i] > SET_MAX[i]) set_ok = FALSE;
    if (rank_ok)
        for (u16 i = 0; i < 5; i++) {
            const u8 *b = rb + i * 7;
            ranking[i].score = ((u32)b[0] << 24) | ((u32)b[1] << 16) | ((u16)b[2] << 8) | b[3];
            memcpy(ranking[i].name, b + 4, 3);
        }
    if (set_ok)
        for (u16 i = 0; i < SET_VALUES; i++) *SET_VAL[i] = sb[1 + i];
    if (set_ok && len == SET_LEN && sb[SET_LEN_V2] <= 1) home_cfg.parallax = sb[SET_LEN_V2];
    if (set_ok && len >= SET_LEN_V2 && sb[SET_LEN_V1] <= RUSH_MAX_BOSSES) {
        const u8 *b = sb + SET_LEN_V1 + 1;
        rush_best.bosses = sb[SET_LEN_V1];
        rush_best.frames = ((u32)b[0] << 24) | ((u32)b[1] << 16) | ((u16)b[2] << 8) | b[3];
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
    sram_save();
    return i + 1;
}

/* ---- dispatch ------------------------------------------------------------------ */
void flow_goto(FlowState s)
{
    flow_state = s;
    switch (s) {
    case FS_SELECT:   menu_select_enter(); break;
    case FS_SETUP:    menu_setup_enter(); break;
    case FS_CONTROLS: menu_controls_enter(); break;
    case FS_SOUND:    menu_sound_enter(); break;
    case FS_COIN:     flow_coin_enter(); break;
    case FS_HOME:     menu_home_enter(); break;
    case FS_WARNING:  flow_warning_enter(); break;
    case FS_TITLE:    flow_title_enter(); break;
    case FS_DEMO:     flow_demo_enter(); break;
    case FS_CREDIT:   flow_credit_enter(); break;
    case FS_INTRO:    flow_intro_enter(); break;
    case FS_PLAY:     break;
    case FS_RUSH:     break;
    case FS_RUSH_END: flow_rush_end_enter(); break;
    }
}

void flow_init(void)
{
    hud_init();
    sram_load();
    flow_apply_config();
    flow_game_reset();
    flow_goto(FS_SELECT);
}

void flow_update(void)
{
    /* soft reset: A+B+C+Start on pad 1 -> boot screen */
    if ((pad[0].held & (IN_FIRE_L | IN_FIRE_R | IN_WEAPON | IN_START)) == (IN_FIRE_L | IN_FIRE_R | IN_WEAPON | IN_START)
        && pad[0].pressed && flow_state != FS_SELECT) {
        sound_play(0x00);
        if (flow_state == FS_RUSH) flow_rush_abort();
        flow_game_reset();
        flow_goto(FS_SELECT);
        return;
    }
    switch (flow_state) {
    case FS_SELECT:   menu_select_update(); break;
    case FS_SETUP:    menu_setup_update(); break;
    case FS_CONTROLS: menu_controls_update(); break;
    case FS_SOUND:    menu_sound_update(); break;
    case FS_COIN:     flow_coin_update(); break;
    case FS_HOME:     menu_home_update(); break;
    case FS_WARNING:  flow_warning_update(); break;
    case FS_TITLE:    flow_title_update(); break;
    case FS_DEMO:     flow_demo_update(); break;
    case FS_CREDIT:   flow_credit_update(); break;
    case FS_INTRO:    flow_intro_update(); break;
    case FS_PLAY:     flow_play_update(); break;
    case FS_RUSH:     flow_rush_update(); break;
    case FS_RUSH_END: flow_rush_end_update(); break;
    }
}

void flow_draw(void)
{
    if (flow_state == FS_DEMO) flow_demo_draw();
    else if (flow_state == FS_PLAY) flow_game_draw();
    else if (flow_state == FS_RUSH) flow_rush_draw();
    scene_update();
    hud_frame();
}
