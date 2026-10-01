#include "game.h"
#include "hud.h"
#include "flow.h"
#include "gen/frontend.h"
#include "boss.h"

extern BossHud boss_hud __attribute__((weak));

/* Credits, start/NAMING, Earth intro, stage, continue and game over.
 * docs/re/flow_player.md §2.2-§2.5; each player has its own small state
 * machine (the arcade runs one task per player: $169E / $16AC, $1A2C / $1A3A). */

void enemies_clear(void) __attribute__((weak));
void enemies_update(void) __attribute__((weak));
void enemies_draw(void) __attribute__((weak));
void bosses_reset(void) __attribute__((weak));
void bosses_update(void) __attribute__((weak));
void bosses_draw(void) __attribute__((weak));

typedef enum { PS_IDLE, PS_NAMING, PS_NAMED, PS_PLAYING, PS_CONTINUE, PS_GAMEOVER } PState;

typedef struct {
    PState st;
    u16 timer;              /* NAMING: $F238 ticks (one per 2 frames); others: frames */
    u8 sub;                 /* frame parity / step counter */
    u8 letter;              /* letters done (0-3) */
    u8 cur;                 /* current letter 0-27 */
    u8 name[3];             /* arcade char codes */
    bool debounce;          /* +$26 */
    u8 hold;                /* joystick repeat delay ($1788: 6 f) */
    u8 count;               /* CONTINUE value 10..0 */
    u32 best;               /* best score of this game, kept over continues ($1A96) */
} PFlow;

static PFlow pf[2];
static bool game_active;    /* $E010 */
static bool stage_running;  /* $E011 */
static bool intro_busy;     /* $E012 */
static u16 timer;

bool game_stage_running(void) { return stage_running || game_in_demo(); }

void flow_game_reset(void)
{
    memset(pf, 0, sizeof(pf));
    game_active = stage_running = intro_busy = FALSE;
    players_init();
}

/* ---- coins / start --------------------------------------------------------------- */
static void coin(void)
{
    /* $08DF/$09CA: a coin adds a credit (max 9), sound $1E */
    if (credits < 9) credits++;
    sound_play(0x1E);
}

static void begin_naming(u16 i)
{
    PFlow *f = &pf[i];
    memset(f, 0, sizeof(*f));
    f->st = PS_NAMING;
    f->timer = stage_running ? 0x100 : 0x150;          /* $16F6: join / game start */
    f->cur = 27;                                        /* $1727: letters start at $9B */
    f->name[0] = f->name[1] = f->name[2] = CH_BAR;
}

/* Arcade: a coin from pad C (on the attract / credit screens) or from Start when there is no
 * credit ("Start adds a coin"). TRUE when this pad inserted one. */
static bool arcade_coin(u16 i, bool c_too)
{
    if (game_cfg.mode != MODE_ARCADE) return FALSE;
    bool c = (c_too && (pad_raw[i].pressed & BUTTON_C)) || ((pad[i].pressed & IN_START) && !credits);
    if (c) coin();
    return c;
}

/* Start pressed and paid for. Arcade: a credit is taken ($16B8); with none, Start inserts a coin
 * instead (the next Start starts). Home: a new game is free (it fills the credits, new_game);
 * a 2P join or a LIMITED continue takes a credit, an UNLIMITED continue is free. */
static bool can_pay(u16 i, bool cont)
{
    if (!(pad[i].pressed & IN_START)) return FALSE;
    if (game_cfg.mode == MODE_HOME) {
        if (!game_active) return TRUE;
        if (cont && game_cfg.cont == CONT_UNLIMITED) return TRUE;
        if (!credits) return FALSE;
        credits--;
        return TRUE;
    }
    if (arcade_coin(i, FALSE)) return FALSE;
    credits--;
    return TRUE;
}

/* continue offered when the player runs out of lives */
static bool continue_offered(void)
{
    if (!game_cfg.allow_continue) return FALSE;
    if (game_cfg.mode == MODE_HOME) return game_cfg.cont == CONT_UNLIMITED || credits;
    return TRUE;                        /* arcade: a coin can still be inserted */
}

static void new_game(void)
{
    /* $12AE: scores cleared, game active ($E010: scoring on), intro pending */
    flow_game_reset();
    game_active = TRUE;
    intro_busy = TRUE;
    score_enabled = TRUE;
    extend_setting = game_cfg.bonus;
    if (game_cfg.mode == MODE_HOME) credits = home_cfg.credits - 1;     /* the starter's credit */
}

/* Attract screens: TRUE when they must stop (a game started or the credit screen opened). */
bool flow_try_start(u16 i)
{
    if (game_cfg.mode == MODE_ARCADE) {
        bool c = arcade_coin(i, TRUE);
        /* $08DF: with credits the credit task opens the credit screen ($12AE) */
        if (credits && flow_state != FS_CREDIT) { flow_demo_abort(); flow_goto(FS_CREDIT); return TRUE; }
        if (c) return FALSE;
    }
    if (!can_pay(i, FALSE)) return FALSE;
    flow_demo_abort();                  /* before the next screen sets up its video */
    new_game();
    begin_naming(i);
    flow_goto(FS_INTRO);
    return TRUE;
}

/* Home screen START GAME: free start, the credits are filled (new_game) */
void flow_home_start(u16 i)
{
    new_game();
    begin_naming(i);
    flow_goto(FS_INTRO);
}

/* ---- credit screen ($12AE) ----------------------------------------------------- */
static void credit_draw(void)
{
    hud_string(credits >= 2 ? FE_STR_ONE_OR_TWO : FE_STR_ONE_PLAYER, -1, -1);
    if (credits < 2) hud_blank(fe_strings[FE_STR_ONE_PLAYER].col + 13, fe_strings[FE_STR_ONE_PLAYER].row, 1);
    hud_number(21, 24, 4, credits, 3);
}

void flow_credit_enter(void)
{
    hud_sprites(FALSE);
    hud_screen_reset();
    hud_string_clear(FE_STR_COPYRIGHT, -1, -1);   /* $04CE: title text gone */
    video_set_layers(FALSE, TRUE);
    scene_load_set(1);
    scene_show(FE_SCENE_EARTH);         /* $134D: scroll $B00,$E00 */
    hud_string(FE_STR_PUSH_START, -1, -1);
    /* $1646 + $1380: "1ST BONUS ZZ0000 PTS", ZZ = first bonus score / 10000 */
    const FeString *b = &fe_strings[FE_STR_BONUS];
    u16 codes[32];
    u32 first = game_extend_table()[0] / 10000;
    u16 z = 0;
    for (u16 k = 0; k < b->cols && k < 32; k++) {
        u16 c = fe_string_codes[b->offset + k];
        if (c == 0x23) c = z++ ? first % 10 : (first / 10) % 10;
        codes[k] = c;
    }
    hud_codes(b->col, b->row, b->colour, codes, b->cols);
    hud_string(FE_STR_CREDIT, -1, -1);
    credit_draw();
}

static void game_panel(void);

void flow_credit_update(void)
{
    static u8 shown_credits;
    game_panel();
    if (flow_try_start(0) || flow_try_start(1)) return;
    if (credits != shown_credits) { shown_credits = credits; credit_draw(); }
}

/* ---- per-player flow ---------------------------------------------------------- */
static void spawn(u16 i)
{
    /* $1823-$1871: score cleared, speed 1, weapons cleared, lives, spawn */
    player_start(&players[i], game_cfg.lives);
    memcpy(players[i].name, pf[i].name, 3);
    pf[i].st = PS_PLAYING;
    pf[i].best = 0;
}

static void stage_start(void);

static u8 letter_code(u8 n)
{
    /* $80-$9B: A-Z, blank, bar; shown with the identical A-Z glyphs $0A-$23 */
    return n < 26 ? 0x0A + n : n == 26 ? CH_SPACE : CH_BAR;
}

static void naming(u16 i)
{
    PFlow *f = &pf[i];
    if (f->sub++ & 1) return;           /* the arcade task loops every 2 frames ($181D) */
    u8 in = pad[i].held;
    f->timer--;
    if (!f->timer) { f->st = PS_NAMED; f->timer = 60; return; }
    if (f->hold) { f->hold--; }
    else if (in & (IN_RIGHT | IN_LEFT)) {
        /* $1760: right = next letter, left = previous, wrapping $80..$9B;
         * then a 6-frame pause ($1788) */
        if (in & IN_RIGHT) f->cur = f->cur == 27 ? 0 : f->cur + 1;
        else f->cur = f->cur ? f->cur - 1 : 27;
        f->name[f->letter] = letter_code(f->cur);
        f->hold = 3;
    }
    /* $178B: any of buttons 1-3 confirms; released in between */
    if (!(in & (IN_FIRE_L | IN_FIRE_R | IN_WEAPON))) { f->debounce = FALSE; return; }
    if (f->debounce) return;
    f->debounce = TRUE;
    if (++f->letter == 3) { f->st = PS_NAMED; f->timer = 60; return; }
    f->cur = 27;                        /* next cell starts at $9B */
}

static void player_flow(u16 i)
{
    PFlow *f = &pf[i];
    Player *p = &players[i];
    switch (f->st) {
    case PS_IDLE:
        if (game_active && can_pay(i, FALSE)) begin_naming(i);   /* join ($16B8) */
        break;
    case PS_NAMING:
        naming(i);
        break;
    case PS_NAMED:
        /* $17E4: the name stays 60 f; then wait for the intro ($17F7), start
         * the stage if it is not running yet ($180C), spawn */
        if (f->timer) { f->timer--; break; }
        if (intro_busy) break;
        if (!stage_running) stage_start();
        spawn(i);
        break;
    case PS_PLAYING:
        if (p->score > f->best) f->best = p->score;
        if (!player_out_of_lives(p)) break;
        /* $1A81: out of lives */
        if (continue_offered()) {
            f->st = PS_CONTINUE; f->count = 10; f->timer = 60;
            sound_play(0x0E);           /* $1AE2 */
        } else {
            ranking_insert(f->best, f->name);
            f->st = PS_GAMEOVER; f->timer = 210;
            sound_play(0x2E);
        }
        break;
    case PS_CONTINUE:
        /* $1ACA: 10 -> 0, one step per 60 f (Start + credit polled every 6 f) */
        if (can_pay(i, TRUE)) {
            /* $1B09: score cleared, lives refilled, respawn */
            player_continue(p, game_cfg.lives);
            f->st = PS_PLAYING;
            break;
        }
        if (--f->timer) break;
        if (!f->count) {
            /* $1B5F: ranking ($1C02), GAME OVER 210 f, sound $2E */
            ranking_insert(f->best, f->name);
            f->st = PS_GAMEOVER; f->timer = 210;
            sound_play(0x2E);
            break;
        }
        f->count--; f->timer = 60;
        sound_play(0x0E);
        break;
    case PS_GAMEOVER:
        if (--f->timer) break;
        f->st = PS_IDLE;                /* $1BCA: back to the start watcher */
        break;
    }
}

static void players_flow(void)
{
    for (u16 i = 0; i < 2; i++) player_flow(i);
    if (game_active)
        for (u16 i = 0; i < 2; i++)
            if (players[i].score > hi_score) hi_score = players[i].score;   /* $2272 */
    /* $1BD9: nobody playing, continuing or naming -> attract from the WARNING */
    if (game_active && pf[0].st == PS_IDLE && pf[1].st == PS_IDLE) {
        game_active = stage_running = FALSE;
        flow_goto(game_cfg.mode == MODE_HOME ? FS_HOME : FS_WARNING);
    }
}

static void game_panel(void)
{
    HudPanel hp;
    memset(&hp, 0, sizeof(hp));
    hp.on = TRUE;
    hp.hi = hi_score;
    hp.twoup = game_active || flow_state == FS_CREDIT || pf[1].st != PS_IDLE;    /* $12AE sets $E010 */
    if (&boss_hud && boss_hud.active) hp.boss_bars = boss_hud.bars;
    for (u16 i = 0; i < 2; i++) {
        PFlow *f = &pf[i];
        HudPlayer *h = &hp.pl[i];
        h->score = game_active;
        h->bar = f->st == PS_PLAYING || f->st == PS_CONTINUE || f->st == PS_GAMEOVER;
        switch (f->st) {
        case PS_NAMING:
            h->msg = HUD_MSG_NAMING;
            h->msg_arg = (f->timer & 4) ? 1 : 0;                /* $1740: blink */
            memcpy(h->name, f->name, 3);
            h->name[f->letter] = letter_code(f->cur);
            break;
        case PS_NAMED:
            h->msg = HUD_MSG_NAMING; h->msg_arg = 0;          /* label off, name stays */
            memcpy(h->name, f->name, 3);
            break;
        case PS_CONTINUE: h->msg = HUD_MSG_CONTINUE; h->msg_arg = f->count; break;
        case PS_GAMEOVER: h->msg = HUD_MSG_GAMEOVER; break;
        default: break;
        }
    }
    hud_panel(&hp);
}

/* ---- Earth intro ($13BC) -------------------------------------------------------- */
#define S(n) FE_SCENE_##n
static const u8 BURN[12] = { S(BURN0), S(BURN1), S(BURN2), S(BURN3), S(BURN4), S(BURN5),
                             S(BURN6), S(BURN7), S(BURN8), S(BURN9), S(BURN10), S(BURN11) };

/* intro timeline, frames from the intro start (all from $13BC-$1558):
 *   0    Earth (B00,E00)                              30 f
 *   30   24 x { Earth 2 f, flash (C80) 2 f }          96 f
 *   126  burnt (E00) 2 f, 23 x { flash 2 f, burnt 2 f } 94 f
 *   220  burnt, 30 + 12 f; sound $0D
 *   262  12 burning scenes x 9 f (sound $0D before the 6th)   108 f
 *   370  burnt Earth; intro over ($E012 = 0), 60 f
 *   430  6 x { "THE BATTLE FOR SURVIVAL HAS STARTED." 24 f, off 12 f }  216 f
 *   646  stage start ($155A) */
static u8 intro_scene(u16 t, u8 *snd)
{
    *snd = 0;
    if (t < 30) return S(EARTH);
    if (t < 126) return ((t - 30) & 2) ? S(EARTH_FLASH) : S(EARTH);
    if (t < 220) return ((t - 126) & 2) ? S(EARTH_FLASH) : S(EARTH_BURNT);
    if (t < 262) return S(EARTH_BURNT);
    if (t < 370) {
        u16 k = (t - 262) / 9;
        if (t == 262 || t == 262 + 5 * 9) *snd = 0x0D;     /* $144D, $14AC */
        return BURN[k];
    }
    return S(EARTH_BURNT);
}

void flow_intro_enter(void)
{
    hud_sprites(FALSE);
    hud_screen_reset();
    hud_string_clear(FE_STR_COPYRIGHT, -1, -1);   /* $04CE: title text gone */
    video_set_layers(FALSE, TRUE);
    scene_load_set(1);
    scene_show(FE_SCENE_EARTH);
    sound_play(0x20);                   /* $13DE: intro music, sound $0C */
    sound_play(0x0C);
    timer = 0;
}

void flow_intro_update(void)
{
    if (!scene_ready()) { game_panel(); return; }      /* tiles streaming in */
    u8 snd;
    u8 sc = intro_scene(timer, &snd);
    scene_show(sc);
    if (snd) sound_play(snd);
    if (timer == 370) intro_busy = FALSE;               /* $153C */
    if (timer >= 430) {
        u16 k = (timer - 430) % 36;
        if (k == 0) hud_string(FE_STR_BATTLE, -1, -1);  /* $1545 */
        if (k == 24) hud_string_clear(FE_STR_BATTLE, -1, -1);
    }
    timer++;
    players_flow();
    if (flow_state != FS_INTRO) return;
    if (timer >= 646 && !stage_running) stage_start();
    game_panel();
}

/* ---- stage ($155A) ----------------------------------------------------------------- */
static void stage_start(void)
{
    hud_screen_reset();
    level_start(0);                     /* $158E: script $815C */
    stage_video_on();
    stage_sprites_on();
    if (enemies_clear) enemies_clear();
    if (bosses_reset) bosses_reset();
    stage_running = TRUE;
    intro_busy = FALSE;
    hud_sprites(TRUE);
    flow_state = FS_PLAY;
}

bool boss_game_cleared(void) __attribute__((weak));

void flow_play_update(void)
{
    /* the combined-robot merge suspends the world ($3078) */
    bool frozen = players_world_frozen();
    if (!frozen) level_update();
    players_update();
    if (!frozen) {
        if (enemies_update) enemies_update();
        if (bosses_update) bosses_update();
    }
    players_flow();
    if (flow_state != FS_PLAY) return;
    if (boss_game_cleared && boss_game_cleared()) {
        /* ending over: the arcade restarts the attract cycle ($0B84) */
        for (u16 i = 0; i < 2; i++)
            if (pf[i].st == PS_PLAYING || pf[i].st == PS_CONTINUE) ranking_insert(pf[i].best, pf[i].name);
        game_active = stage_running = FALSE;
        memset(pf, 0, sizeof(pf));
        flow_goto(game_cfg.mode == MODE_HOME ? FS_HOME : FS_WARNING);
        return;
    }
    game_panel();
}

void flow_game_draw(void)
{
    players_draw();
    if (bosses_draw) bosses_draw();
    if (enemies_draw) enemies_draw();
}
