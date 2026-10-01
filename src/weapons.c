#include "player_local.h"

/* Weapons of the Mobilsuit (docs/re/flow_player.md §5, docs/player.md).
 *
 * Each player owns MAX_SHOTS shot slots. Every weapon uses a fixed slot range and its own update
 * rule, exactly as the arcade does (B2:$86CC-$8D11): the slot range a weapon scans decides how many
 * shots can be alive and in which groups a volley may start. Shot records come from the ROM tables,
 * converted at build time (tools/build_player.py -> gen/player_data.h). Index 0 of a record pair is
 * facing left (button 1), 1 facing right (button 2). */

u8 fire_flash;

/* ---- shot primitives ------------------------------------------------------------------------- */

/* B2:$938F: spawn a record relative to the body (the robot leader fires 8 px lower, $93A5) */
static void spawn_at(Shot *s, const ShotRec *r, s16 x, s16 y, u8 kind)
{
    s->x = x + r->dx; s->y = y + r->dy;
    s->vx = r->vx; s->vy = r->vy;
    s->code = r->code; s->colour = r->colour;
    s->half_w = r->half_w; s->half_h = r->half_h;
    s->active = 1; s->kind = kind; s->damage = 1; s->pierce = FALSE;
    s->life = 0; s->timer = 0; s->phase = 0; s->delay = 0;
}

static void spawn(const Player *p, Shot *s, const ShotRec *r, u8 kind)
{
    spawn_at(s, r, p->x, p->y + (is_leader(p) ? 8 : 0), kind);
}

/* B2:$9467: explode (also used by shot_hit) — codes $1C-$1E, colour 5, 16 frames */
void shot_explode(Shot *s)
{
    s->active = 2; s->life = 16; s->code = 0x1C; s->colour = 5;
}

/* B2:$9480 */
static void explode_tick(Shot *s)
{
    if (--s->life == 0) s->active = 0;
    else if (s->life == 10 || s->life == 5) s->code++;
}

/* B2:$93FB: linear step; off the arcade screen (sprite y >= $F4 incl. wrap above 0, 9-bit x < $30
 * or >= $1C0) frees the slot; terrain (probe $949C at (x+8, y+8), the map's column origin adds 16)
 * explodes it. Screen = arcade sprite - (96, 16). */
static s16 probe_x, probe_y;                /* camera + probe offset, set once per frame */

static void shot_move(Shot *s)
{
    s->y += s->vy;
    if ((u16)(s->y + 16) >= 0xF4) { s->active = 0; return; }
    s->x += s->vx;
    if ((u16)(s->x + 96 - 0x30) >= 0x1C0 - 0x30) { s->active = 0; return; }
    if (terrain_solid(probe_x + s->x, probe_y + s->y)) shot_explode(s);
}

void shot_hit(Player *p, Shot *s)
{
    (void)p;
    if (s->pierce) return;                  /* M.B.L. +$07 = $4D: no explosion on hit ($2500) */
    shot_explode(s);
}

static bool free_range(const Player *p, u8 first, u8 n)
{
    for (u8 i = first; i < first + n; i++) if (p->shots[i].active) return FALSE;
    return TRUE;
}

static Shot *first_free(Player *p, u8 n)
{
    for (u8 i = 0; i < n; i++) if (!p->shots[i].active) return &p->shots[i];
    return NULL;
}

/* ---- update loops (one per weapon, each scans its own slot range) ---------------------------- */

static void upd_linear(Player *p, u8 n)     /* $879B (4), $8876 (7), $8C43 (8), $8CED (9) */
{
    for (u8 i = 0; i < n; i++) {
        Shot *s = &p->shots[i];
        if (s->active == 1) shot_move(s);
        else if (s->active) explode_tick(s);
    }
}

static void upd_mbl(Player *p)              /* B2:$8B1E: 6 slots, segments wait their launch delay */
{
    for (u8 i = 0; i < 6; i++) {
        Shot *s = &p->shots[i];
        if (s->active == 1) { if (s->delay) s->delay--; else shot_move(s); }
        else if (s->active) explode_tick(s);
    }
}

static void upd_sg(Player *p)               /* B2:$8973: 7 slots, fuse 15 then burst */
{
    bool burst = FALSE;
    for (u8 i = 0; i < 7; i++) {
        Shot *s = &p->shots[i];
        if (s->active == 2) { explode_tick(s); continue; }
        if (!s->active) continue;
        if (s->timer) {
            if (--s->timer) shot_move(s);
            else { burst = TRUE; s->code = 0x80; }      /* $899C: burst, sound $03 */
        } else {
            s->phase++;                                 /* $89A8: $80 -> $81 (2) -> $82 (4) -> gone (6) */
            if (s->phase == 2 || s->phase == 4) s->code++;
            else if (s->phase == 6) s->active = 0;
        }
    }
    /* the arcade queues $03 once per pellet in the same frame; one command sounds the same */
    if (burst) sound_play(0x03);
}

static void upd_3way(Player *p)             /* B2:$8BB2: 9 slots; level 2 shots cycle codes $18-$1B */
{
    bool anim = p->level[WPN_3WAY] != 1;
    for (u8 i = 0; i < 9; i++) {
        Shot *s = &p->shots[i];
        if (s->active == 1) {
            shot_move(s);
            /* $8BCD: applied after the move even if it just exploded (arcade quirk: a level-2
             * explosion shows the 3WAY cell in colour 5) */
            if (anim && s->active) s->code = 0x18 | (frame & 3);
        } else if (s->active) explode_tick(s);
    }
}

/* ---- orbiters, launcher, select ------------------------------------------------------------- */

void weapons_clear(Player *p)
{
    memset(p->shots, 0, sizeof(p->shots));
    p->bits_valid = FALSE;
    p->att_valid = FALSE;
}

/* $1F26: orbiter 0 starts at step 0; level 2: orbiter 1 at 16; level 3: 10 and 22 */
void weapons_build_bits(Player *p)
{
    p->bit_step[0] = 0;
    if (p->level[WPN_BIT] == 2) p->bit_step[1] = BIT_START_L2;
    else if (p->level[WPN_BIT] >= 3) { p->bit_step[1] = BIT_START_L3[0]; p->bit_step[2] = BIT_START_L3[1]; }
}

/* $1E03, run before the player update with LAST frame's pad. Slot 0 with a weapon owned picks the
 * first owned slot. Otherwise the arcade's latch is inverted: the selection steps when button 3 is
 * RELEASED (and once right after the first weapon is picked up, the latch being clear) — OBS weap
 * f1012/f1013 and f1000/f1001. Changing slot clears every shot and rebuilds the orbit. */
void weapon_select(Player *p)
{
    if (!p->weapon) {
        for (u8 i = 1; i <= 5; i++) if (p->level[i]) { p->weapon = i; break; }
        pad_weapon_req[p->id] = 0;
        return;
    }
    /* Genesis 6-button extra (not in the arcade): X / Y / Z pick the previous / next owned
     * weapon or a given one if owned, at once; same effects as a button-3 step */
    u8 req = pad_weapon_req[p->id];
    if (req) {
        pad_weapon_req[p->id] = 0;
        u8 w = p->weapon;
        if (req == XB_PREV || req == XB_NEXT)
            for (u8 n = 0; n < 5; n++) {
                w = req == XB_NEXT ? (w == 5 ? 1 : w + 1) : (w == 1 ? 5 : w - 1);
                if (p->level[w]) break;
            }
        else if (req >= XB_BIT && req <= XB_AUTO && p->level[req - XB_BIT + WPN_BIT]) w = req - XB_BIT + WPN_BIT;
        if (w != p->weapon && p->level[w]) {
            sound_play(0x1C);
            p->weapon = w;
            weapons_clear(p);
            weapons_build_bits(p);
        }
        return;
    }
    if (p->prev_held & IN_WEAPON) { p->select_latch = FALSE; return; }
    if (p->select_latch) return;
    p->select_latch = TRUE;
    sound_play(0x1C);
    u8 w = p->weapon;
    for (u8 n = 0; n < 5; n++) {
        w = w == 5 ? 1 : w + 1;
        if (p->level[w]) break;
    }
    if (!p->level[w]) return;               /* nothing owned: the arcade would hang ($1E62) */
    p->weapon = w;
    weapons_clear(p);
    weapons_build_bits(p);
}

/* B2:$8511: weapon pose on the body code and the attachments, before firing */
void weapons_pose(Player *p)
{
    switch (p->weapon) {
    case WPN_BIT: {
        /* B2:$85EF: each orbiter steps once per frame around the last drawn body (y, x+16) */
        u8 n = p->level[WPN_BIT];
        s16 ry = p->ref_y + (combined ? 8 : 0);
        for (u8 k = 0; k < n && k < 3; k++) {
            u8 i = p->bit_step[k];
            if (i >= 32) i = 0;
            const BitStep *b = &BIT_PATH[i];
            p->bit_y[k] = ry + b->dy; p->bit_x[k] = p->ref_x + b->dx; p->bit_code[k] = b->code;
            p->bit_step[k] = i + 1;
        }
        p->bits_valid = TRUE;
        break;
    }
    case WPN_MBL:                           /* B2:$8583: pose +$10, launcher code 4/6 beside the body */
        if (combined) break;
        p->body_code += 0x10;
        p->att_code = p->body_code - 0x2C;
        p->att_y = p->y;
        p->att_x = p->x + (p->facing_left ? -16 : 32);
        p->att_valid = TRUE;
        break;
    case WPN_3WAY: p->body_code += 0x20; break;     /* B2:$85D6 */
    case WPN_AUTO: p->body_code += 0x30; break;     /* B2:$85E1 */
    }
}

/* ---- firing ---------------------------------------------------------------------------------- */

static void fired(Player *p, u8 pose, u8 snd)
{
    p->fire_pose = pose; fire_flash = pose;
    if (snd) sound_play(snd);
}

static void fire_normal(Player *p, const ShotRec *rec)  /* B2:$876C: first free of slots 0-3 */
{
    Shot *s = first_free(p, 4);
    if (!s) return;
    spawn(p, s, &rec[!p->facing_left], SHOT_NORMAL);
    fired(p, 5, 0x01);
}

static void fire_bit(Player *p)             /* B2:$87C2 */
{
    const ShotRec *r = &SR_BIT[!p->facing_left];
    if (free_range(p, 4, 3)) {              /* one shot per orbiter in slots 4/5/6 ($93DD) */
        for (u8 k = 0; k < p->level[WPN_BIT] && k < 3; k++)
            spawn_at(&p->shots[4 + k], r, p->bit_x[k], p->bit_y[k], SHOT_BIT);
        fired(p, 5, 0);
    }
    fire_normal(p, SR_BIT_NORMAL);          /* B2:$8842 plus the normal shot */
}

static bool fire_sg(Player *p)              /* B2:$889D: all 7 slots must be free */
{
    if (!free_range(p, 0, 7)) return FALSE;
    u8 lv = p->level[WPN_SG], side = !p->facing_left;
    const ShotRec *r = lv == 1 ? SR_SG1[side] : lv == 2 ? SR_SG2[side] : SR_SG3[side];
    u8 n = lv == 1 ? 3 : lv == 2 ? 5 : 7;
    for (u8 i = 0; i < n; i++) {
        spawn(p, &p->shots[i], &r[i], SHOT_SG);
        p->shots[i].timer = 15;
    }
    fired(p, 8, 0x02);
    return TRUE;
}

static void fire_mbl(Player *p)             /* B2:$89E4: slots 0, 3 and 5 must be free */
{
    if (p->shots[0].active || p->shots[3].active || p->shots[5].active) return;
    const ShotRec *r = &SR_MBL[!p->facing_left];
    s16 y = p->y + (combined ? 16 : 0);     /* $8A22 */
    for (u8 i = 0; i < 6; i++) {
        Shot *s = &p->shots[i];
        spawn_at(s, r, p->x, y, SHOT_MBL);
        s->code = r->code + (i == 0 ? 0 : i == 5 ? 2 : 1);  /* head, body x4, tail */
        s->pierce = TRUE;                   /* +$07 = $4D */
        s->delay = i;                       /* released one frame apart */
    }
    if (p->level[WPN_MBL] == 1) {           /* $8AF8: level 1 drops two body segments */
        p->shots[3].active = p->shots[4].active = 0;
        p->shots[5].delay = 3;
    }
    fired(p, 15, 0x04);
}

static void fire_volley(Player *p, const ShotRec *r, u8 kind, u8 pose, u8 snd)
{
    /* B2:$8B51 / $8C8C: three slots of one group (0-2, 3-5, 6-8) must be free */
    for (u8 g = 0; g < 9; g += 3) {
        if (!free_range(p, g, 3)) continue;
        for (u8 i = 0; i < 3; i++) spawn(p, &p->shots[g + i], &r[i], kind);
        fired(p, pose, snd);
        return;
    }
}

/* B2:$8BEA: AUTO fires while exactly one fire button is held, on frame phase, regardless of the
 * press latch. $10: 1 shot / 4 frames (slots 0-7); $11: 3-shot volley / 8 frames. */
static void fire_auto(Player *p, u8 in)
{
    bool v11 = p->level[WPN_AUTO] == 0x11;
    u8 b = in & (IN_FIRE_L | IN_FIRE_R);
    if (b && b != (IN_FIRE_L | IN_FIRE_R)) {
        p->facing_left = (in & IN_FIRE_L) != 0;
        if (!(frame & (v11 ? 7 : 3))) {
            if (v11) fire_volley(p, SR_AUTO11[!p->facing_left], SHOT_AUTO, 2, 0x06);
            else {
                Shot *s = first_free(p, 8);
                if (s) { spawn(p, s, &SR_AUTO10[!p->facing_left], SHOT_AUTO); fired(p, 2, 0x05); }
            }
        }
    }
    upd_linear(p, v11 ? 9 : 8);
}

void weapons_fire(Player *p, u8 in)
{
    probe_x = cam_x() + 24; probe_y = cam_y() + 8;
    /* B2:$86E2: buttons 1/2 fire left/right; one shot per press (latch +$06 cleared only when both
     * are released). The press sets the facing and the plain firing pose for this frame. */
    bool press = FALSE;
    if (!(in & (IN_FIRE_L | IN_FIRE_R))) p->fire_latch = FALSE;
    else if (!p->fire_latch) {
        p->fire_latch = TRUE; press = TRUE;
        p->facing_left = (in & IN_FIRE_L) != 0;
        if (!p->entry) p->body_code = p->facing_left ? 0x20 : 0x22;
        else if (p->facing_left) p->body_code -= 2;         /* $871C (twice if already left) */
    }
    /* while the entry timer runs only the normal shot exists ($8722) */
    switch (p->entry ? WPN_NONE : p->weapon) {
    case WPN_BIT:
        if (press) fire_bit(p);
        upd_linear(p, 7);
        break;
    case WPN_SG:
        /* $88B7: a press while pellets are out runs the M.B.L. loop instead (pellets keep moving,
         * fuses pause, slot 6 freezes for that frame) — arcade quirk, kept */
        if (press && !fire_sg(p)) upd_mbl(p);
        else upd_sg(p);
        break;
    case WPN_MBL:
        if (press) fire_mbl(p);
        upd_mbl(p);
        break;
    case WPN_3WAY:
        if (press) fire_volley(p, SR_3WAY[!p->facing_left], SHOT_3WAY, 5, 0x01);
        upd_3way(p);
        break;
    case WPN_AUTO:
        fire_auto(p, in);
        break;
    default:
        if (press) fire_normal(p, SR_NORMAL);
        upd_linear(p, 4);
        break;
    }
}

/* ---- combined robot ring (B2:$8D51 P1-led, $8DE6 P2-led) -------------------------------------- *
 * Fired by the partner's buttons (by the leader's when no partner is in play) into the partner's
 * shot slots, every 4 frames while a fire button is held and all 8 slots are free; patterns A/B
 * alternate. Origin: the partner record sits at (leader y+32, x) and fires 16 px lower, minus 32 when
 * the partner has lives; the leader itself fires 8+16 px lower. */
void weapons_ring(Player *src, u8 in)
{
    probe_x = cam_x() + 24; probe_y = cam_y() + 8;
    Player *lead = &players[combined - 1], *part = &players[combined == 1 ? 1 : 0];
    bool p2led = combined == 2;
    Player *owner = part;                   /* shots land in the partner's slots */
    if ((in & (IN_FIRE_L | IN_FIRE_R)) && !(frame & 3) && free_range(owner, 0, 8)) {
        src->ring_toggle++;
        const ShotRec *r = (p2led ? SR_RING_P2 : SR_RING_P1)[src->ring_toggle & 1];
        s16 y = src == lead ? lead->y + 8 : lead->y + 32 - (part->lives ? 32 : 0);
        for (u8 i = 0; i < 8; i++) spawn_at(&owner->shots[i], &r[i], lead->x, y, SHOT_RING);
        fire_flash = 0x0B;
        sound_play(p2led ? 0x08 : 0x07);
    }
    if (!p2led) { upd_linear(owner, 8); return; }
    /* $8E66 boomerang: out 9 frames, hover 10, reverse at 20, back 8, burst $080-$082, gone at 35 */
    for (u8 i = 0; i < 8; i++) {
        Shot *s = &owner->shots[i];
        if (s->active == 2) { explode_tick(s); continue; }
        if (!s->active) continue;
        u8 t = ++s->timer;
        if (t == 20) { s->vx = -s->vx; s->vy = -s->vy; }
        if (t < 10 || (t >= 20 && t < 29)) shot_move(s);
        if (t < 29) { if (s->active == 1) s->code = (s->code & 0x100) | 0x98 | (frame & 7); }
        else if (t == 29) s->code = 0x80;
        else if (t == 31 || t == 33) s->code++;
        else if (t == 35) s->active = 0;
    }
}

/* ---- drawing --------------------------------------------------------------------------------- */

void weapons_draw(const Player *p)
{
    for (u16 i = 0; i < MAX_SHOTS; i++) {
        const Shot *s = &p->shots[i];
        if (s->active) spr_16(s->code, s->colour, s->x, s->y, 0);
    }
    if (p->state != PL_ALIVE) return;
    if (p->weapon == WPN_BIT && p->bits_valid)          /* orbiters: colour 3 ($8632) */
        for (u8 k = 0; k < p->level[WPN_BIT] && k < 3; k++)
            spr_16(p->bit_code[k], 3, p->bit_x[k], p->bit_y[k], 0);
    if (p->weapon == WPN_MBL && p->att_valid && !combined)
        spr_16(p->att_code + (p->id ? P2_CODE : 0), p->id ? P2_COLOUR : 0, p->att_x, p->att_y, 0);
}
