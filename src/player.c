#include "player_local.h"

/* The Mobilsuit (docs/re/flow_player.md, design in docs/player.md). Positions are Genesis screen
 * pixels of the 32x32 body's top-left; arcade sprite coordinates are these plus (96, 16).
 *
 * Per frame (arcade order): weapon select for both players ($1E03, previous frame's pad), then each
 * player: entry glide or movement + terrain (B2:$8368), weapon pose (B2:$8511), fire + shot update
 * (B2:$86CC), body composite (B2:$8EF5). */

Player players[2];
u32 hi_score = 100000;              /* $E600 default = ranking #1 ($0B34) */
u16 extend_setting;                  /* DSW0 bits 4-5, 0 = MAME default (100000 once) */
bool score_enabled = TRUE;          /* $E010 */
bool crushed;
volatile u16 prof_player[2];        /* debug: scanlines spent in players_update / players_draw (approx.) */

/* Arcade bounds (B2:$83A1-$83EA): y $20-$C0, x $50-$190 in sprite coords = screen y 16-176,
 * x -16-304. The Genesis screen is 64 px narrower, so x is clamped to the visible 0-288 instead. */
#define MIN_X 0
/* The arcade's left limit (sprite x $50 = screen -16) still decides the scroll crush (B2:$846F):
 * input keeps the ship on the narrower Genesis screen, a terrain push may carry it 16 px off. */
#define CRUSH_X (-16)
#define MAX_X (SCREEN_W - 32)
#define MIN_Y 16
#define MAX_Y 176
#define SCORE_MAX 999999990UL       /* 8 BCD digits shown x10 */

void players_init(void)
{
    memset(players, 0, sizeof(players));
    players[1].id = 1;
    combine_reset();
}

static void set_ref(Player *p) { p->ref_y = p->y; p->ref_x = p->x + 16; }

/* Respawn $1871: entry glide 80 frames, invulnerable 80 frames, facing right, sound $09.
 * Horizontal stage spawn point P1 (y $40, x $20), P2 (y $A0, x $20); vertical stage P1 (y 0, x $C0),
 * P2 (y 0, x $120) (descriptors $1CFA/$1D24). */
void player_spawn(Player *p)
{
    bool vertical = p->vertical = level.vertical;   /* $1896: +$28 = $E040 */
    if (vertical) { p->x = (p->id ? 0x120 : 0xC0) - 96; p->y = 0 - 16; }
    else          { p->x = 0x20 - 96;                  p->y = (p->id ? 0xA0 : 0x40) - 16; }
    p->state = PL_ALIVE;
    p->in_play = TRUE;
    p->facing_left = FALSE;
    p->entry = 80;
    p->entry_latch = FALSE;
    p->invuln = 80;
    p->fire_pose = 0;
    p->body_code = 0x62;
    if (!p->speed) p->speed = 1;
    sound_play(0x09);
}

/* $1960/$196B: back in play where the body is (robot split); control is given at once (+$2A = $4C)
 * but the 80-frame entry timer still blinks the body and limits fire to the normal shot. */
void player_respawn_in_place(Player *p)
{
    p->state = PL_ALIVE;
    p->in_play = TRUE;
    p->facing_left = FALSE;
    p->entry = 80;
    p->entry_latch = TRUE;
    p->invuln = 80;
    p->body_code = 0x62;
    set_ref(p);
}

/* $1839: speed 1, every weapon level cleared, lives = DSW setting, then the respawn */
void player_start(Player *p, u8 lives)
{
    p->speed = 1;
    memset(p->level, 0, sizeof(p->level));
    p->weapon = 0;
    p->lives = lives;
    p->score = 0;
    p->extend_idx = 0;
    if (combined) { combine_join(p); return; }
    weapons_clear(p);
    player_spawn(p);
}

/* $1B09: CONTINUE: score cleared, bonus-life pointer reset, lives restored; speed and weapons kept */
void player_continue(Player *p, u8 lives)
{
    p->score = 0;
    p->extend_idx = 0;
    p->lives = lives;
    if (combined) { combine_join(p); return; }
    player_spawn(p);
}

bool player_out_of_lives(const Player *p)
{
    return !p->in_play && p->state == PL_OFF;
}

/* $2272/$22AE: only in a real game ($E010); hi score follows the best score; one bonus life when the
 * score reaches the next entry of the DSW-selected table (sound $1D) */
void player_add_score(Player *p, u32 points)
{
    if (!score_enabled) return;
    p->score += points;
    if (p->score > SCORE_MAX) p->score = SCORE_MAX;
    if (p->score >= hi_score) hi_score = p->score;
    if (p->score >= EXTEND_TABLES[extend_setting & 3][p->extend_idx]) {
        p->lives++;
        p->extend_idx++;
        sound_play(0x1D);
    }
}

/* $2516-$2548 (small objects), $293A-$296C (big), $2D1D-$2D43 (bosses): a kill by a player's shot
 * is credited ($E0A2) to the shot's owner, unless that player has no lives left (+$0B = 0), then to
 * the other player. This happens with the combined robot, whose ring fires into the partner's shot
 * slots: a partner without lives (out of play) leaves the points to the leader. */
Player *player_credit(Player *shooter)
{
    return shooter->lives ? shooter : &players[!shooter->id];
}

/* $2657: item codes */
void player_apply_item(Player *p, u8 item)
{
    switch (item) {
    case 0x80: if (p->speed < 3) p->speed++; sound_play(0x1A); break;          /* SPEED UP */
    case 0x81: if (p->speed > 1) p->speed--; sound_play(0x1B); break;          /* SPEED DOWN */
    case 0x01: if (p->level[WPN_BIT] < 3) p->level[WPN_BIT]++;
               weapons_build_bits(p); sound_play(0x1C); break;                 /* $26C2 */
    case 0x02: if (p->level[WPN_SG] < 3) p->level[WPN_SG]++; sound_play(0x1C); break;
    case 0x03: if (p->level[WPN_MBL] < 2) p->level[WPN_MBL]++; sound_play(0x1C); break;
    case 0x04: if (p->level[WPN_3WAY] < 2) p->level[WPN_3WAY]++; sound_play(0x1C); break;
    case 0x10: case 0x11: p->level[WPN_AUTO] = item; sound_play(0x1C); break;  /* $2716/$271D */
    case 0x06: if (!combined) combine_start(p); break;                         /* $2735 */
    case 0x08:                              /* $2747: +1 life to $E0A2, which the contact test
                                               sets to the touching player ($2568/$2573) */
        p->lives++;
        sound_play(0x1D);
        break;
    default: break;                         /* $07: collect only */
    }
}

void player_kill_now(Player *p)
{
    sound_play(0x0F);
    if (combined) { combine_hit(); return; }       /* $2231: the robot loses a hit point */
    p->state = PL_DYING;
    p->speed = 1;                           /* $2254 */
    p->death_frame = 0xFF;                  /* first frame of the animation is drawn next frame */
    p->death_timer = 1;
    weapons_clear(p);                       /* $2260: orbiters and every shot */
}

/* $222C, as called by enemy contact ($2617): ignored while invulnerable */
void player_kill(Player *p)
{
    if (p->state != PL_ALIVE || p->invuln) return;
    player_kill_now(p);
}

static bool solid_at(s16 x, s16 y)
{
    /* B2:$84B5 probes one point: (x, y+16) in arcade world terms; the map's column origin adds 16 */
    return terrain_solid(cam_x() + x + 16, cam_y() + y + 16);
}

/* B2:$8368-$84B4: move by the speed table, clamp, then (outside the entry timer) the terrain test.
 * Blocked: keep the new x with the old y, else old x with the new y, else both old. The +$22/+$23
 * scratch writes of those retries also move the orbit reference (B2:$840F/$8421), kept. */
void player_move(Player *p, u8 dir, const s8 (*table)[2])
{
    crushed = FALSE;
    s16 ny = p->y + table[dir][0], nx = p->x + table[dir][1];
    if (ny < MIN_Y) ny = MIN_Y;
    if (ny > MAX_Y) ny = MAX_Y;
    if (nx < MIN_X) nx = MIN_X;
    if (nx > MAX_X) nx = MAX_X;
    p->x = nx; p->y = ny;
    p->body_code = p->facing_left ? 0x20 : 0x22;    /* B2:$8393 */
    if (p->entry) return;                   /* $8402: no terrain test while the entry timer runs */
    if (!solid_at(nx, ny)) return;
    p->ref_y = ny;
    if (!solid_at(nx, p->old_y)) { p->y = p->old_y; return; }
    p->ref_x = nx;
    if (!solid_at(p->old_x, ny)) { p->x = p->old_x; return; }
    p->x = p->old_x; p->y = p->old_y;
    if (!solid_at(p->x, p->y)) return;
    /* B2:$8451: the scroll pushed terrain into us: pushed 1 px back, crushed past the screen edge
     * or if still inside terrain */
    if (level.dir_x) { p->x--; if (p->x < CRUSH_X) goto crush; }
    if (level.dir_y) { p->y--; if (p->y < MIN_Y) goto crush; }
    if (!solid_at(p->x, p->y)) return;
crush:
    /* B2:$8495: the dying body keeps the x of the last drawn composite (sprite +$40), i.e. the
     * position before the push (arcade stage 2: dies at sprite x $50, not $4F) */
    p->x = p->old_x;
    crushed = TRUE;
    player_kill_now(p);
}

/* Death animation B2:$822E (8 x 5 frames) then the death task $1A2D: the selected weapon's level is
 * lost and the selection goes back to 0, orbit rebuilt, one life; respawn at once if any left. */
static void death_step(Player *p)
{
    if (--p->death_timer) return;
    if (++p->death_frame < 8) { p->death_timer = 5; return; }
    p->state = PL_OFF;
    p->level[p->weapon] = 0;
    p->weapon = 0;
    weapons_build_bits(p);
    if (p->lives) p->lives--;
    if (p->lives) player_spawn(p);
    else p->in_play = FALSE;                /* front end: CONTINUE / GAME OVER */
}

static void update(Player *p)
{
    u8 in = pad[p->id].held;
    if (combined) { combine_update_player(p, in); return; }
    if (p->state == PL_DYING) { death_step(p); return; }
    if (p->state != PL_ALIVE) return;
    p->old_x = p->x; p->old_y = p->y;
    if (p->invuln) p->invuln--;             /* $829C */
    bool glide = FALSE;
    if (p->entry) {
        p->entry--;
        if (!p->entry_latch) {
            /* B2:$829F: glide 3/2/1/0 px per frame with codes $62/$66/$72/$76 (-2 facing left);
             * a direction once the timer is below 60 hands control back from the next frame on */
            if (p->entry < 60 && (in & 0x0F)) p->entry_latch = TRUE;
            u8 e = p->entry;
            s16 step = e >= 60 ? 3 : e >= 40 ? 2 : e >= 20 ? 1 : 0;
            p->body_code = e >= 60 ? 0x62 : e >= 40 ? 0x66 : e >= 20 ? 0x72 : 0x76;
            if (p->facing_left) p->body_code -= 2;
            if (p->vertical) p->y += step; else p->x += step;
            glide = TRUE;
        }
    }
    if (!glide) {
        player_move(p, in & 0x0F, MOVE_TABLE[p->speed - 1]);
        if (crushed) return;
        weapons_pose(p);
    }
    weapons_fire(p, in);
    /* B2:$8EF5 composite: firing pose (+4) only once the entry timer is over; the orbit reference
     * follows the drawn body (not refreshed on hidden blink frames) */
    if (!p->entry) {
        if (p->fire_pose) {
            p->fire_pose--;
            p->body_code += 4;
            if (p->weapon == WPN_MBL && p->att_valid) p->att_code++;
        }
        set_ref(p);
    } else if (p->entry & 1) set_ref(p);
}

/* Test hook for the headless runner: the host writes an arcade item code (or $FF = kill, $FE =
 * start a game with 3 lives, $FD = score 10000 points) per player; applied at the start of the next
 * player update. */
volatile u8 dbg_player_cmd[2];

static u16 lines_since(u16 v0)
{
    u16 v1 = GET_VCOUNTER;
    return v1 >= v0 ? v1 - v0 : v1 + 262 - v0;
}

static void update_all(void);
void players_update(void)
{
    u16 v0 = GET_VCOUNTER;
    update_all();
    prof_player[0] = lines_since(v0);
}

static void update_all(void)
{
    for (u16 i = 0; i < 2; i++) {
        u8 c = dbg_player_cmd[i];
        if (!c) continue;
        dbg_player_cmd[i] = 0;
        if (c == 0xFF) player_kill(&players[i]);
        else if (c == 0xFE) player_start(&players[i], 3);
        else if (c == 0xFD) player_add_score(&players[i], 10000);
        else player_apply_item(&players[i], c);
    }
    if (combine_update()) return;           /* merge/split sequence: everything else is suspended */
    for (u16 i = 0; i < 2; i++) if (players[i].in_play) weapon_select(&players[i]);
    update(&players[0]);
    update(&players[1]);
    players[0].prev_held = pad[0].held;
    players[1].prev_held = pad[1].held;
}

static void draw(const Player *p)
{
    weapons_draw(p);
    if (p->state == PL_DYING) {
        if (p->death_frame < 8) { spr_32(DEATH_CODES[p->death_frame], 8, p->x, p->y, 0); return; }
    } else if (p->state != PL_ALIVE) return;
    if (is_leader(p)) { combine_draw_robot(p); return; }
    /* B2:$8F02: the entry timer blinks the body, hidden on even values (OBS die2 f1044-f1061);
     * the respawn frame itself (80) is drawn because the arcade respawns after the composite */
    if (p->entry && !(p->entry & 1) && p->entry < 80) return;
    spr_32(p->body_code + (p->id ? P2_CODE : 0), p->id ? P2_COLOUR : 0, p->x, p->y, 0);
}

void players_draw(void)
{
    u16 v0 = GET_VCOUNTER;
    if (!combine_draw()) {
        draw(&players[0]);
        draw(&players[1]);
    }
    prof_player[1] = lines_since(v0);
}
