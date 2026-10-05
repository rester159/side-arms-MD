#include "player_local.h"

/* The combined "Side Arms" robot (item $06, docs/re/flow_player.md §5, docs/player.md).
 *
 * Merge ($2E4E): the arcade suspends every other task ($3078) while the collecting player (the
 * leader) transforms (codes $76,$72,$66,$62, 12 frames each) and its partner flies in: from the
 * partner player's position (that player is hidden; its object first plays the same transform, 20
 * frames per code) or, with no partner on screen, from a fixed entry point ($2F2E). The partner then
 * homes on the leader with 16-direction steps re-aimed every 12 frames ($311D, velocity table $3130).
 * On contact ($2F9A) both become one 32x48 sprite ($140-$146 / $180-$186 merge animation), hit points
 * $E015 = 1 with both players in play, else 2.
 * Merged: the leader moves with table B2:$86AC (5/4 px; both sticks OR'ed when the leader's is idle),
 * fires its selected weapon (8 px lower), and the partner's buttons fire the 8-way ring
 * (weapons_ring). Every hit costs a hit point; at 0 the robot splits ($223F/$32CE): reverse merge
 * animation, both bodies shown, then both respawn in place ($1960) — a partner without lives
 * explodes instead ($34F0).
 * UNVERIFIED (never exercised live): homing contact test (taken as the object/player contact box of
 * the partner template, 16 x 16 px half sizes), the fixed-point opening scripts' timing, the enemy
 * explosion the arcade plays on the object that broke the robot ($32CE, enemies module). */

u8 combined, combined_hp;

typedef enum { SEQ_NONE, SEQ_TRANSFORM, SEQ_FLY, SEQ_MERGE, SEQ_SPLIT, SEQ_SPLIT_SHOW, SEQ_EXPLODE } Seq;
static Seq seq;
static u16 seq_t;
static s16 obj_x, obj_y, obj_vx, obj_vy;    /* partner object $FA80 */
static u8 obj_anim, obj_steps;              /* opening frames left, frames left in this homing step */
static u8 seq_lead;                         /* leader id of the running sequence */
static u16 robot_code;                      /* body code computed by the last composite ($8FF0) */
static u16 obj_code; static u8 obj_colour;
static s16 tgt_x, tgt_y;                    /* $E020/$E021: leader y+8, x at merge time */

/* $3130: homing velocities (dy, dx) clockwise from right */
static const s8 HOMING[16][2] = {
    {0, 3}, {1, 3}, {2, 3}, {2, 1}, {2, 0}, {2, -1}, {2, -3}, {1, -3},
    {0, -3}, {-1, -3}, {-2, -3}, {-2, -1}, {-2, 0}, {-2, 1}, {-2, 3}, {-1, 3},
};

bool players_world_frozen(void) { return seq != SEQ_NONE; }

void combine_reset(void)
{
    seq = SEQ_NONE; combined = 0; combined_hp = 0; robot_code = 0; fire_flash = 0;
}

static Player *leader(void) { return &players[combined - 1]; }
static Player *partner(void) { return &players[combined == 1 ? 1 : 0]; }

/* robot codes: P1-led $140.. , P2-led $180.., colour 0 ($2FE4 attr $20) */
static u16 robot_base(void) { return combined == 1 ? 0x140 : 0x180; }

void combine_start(Player *lead)
{
    sound_play(0x0A);
    weapons_clear(&players[0]);
    weapons_clear(&players[1]);
    combined = lead->id + 1;
    seq_lead = lead->id;
    lead->invuln = 0; lead->entry = 0; lead->entry_latch = FALSE;
    tgt_y = lead->y + 8; tgt_x = lead->x;
    Player *q = partner();
    /* partner object: looks like the partner player (template $30E6/$31DA) */
    obj_code = q->id ? 0xE2 : 0x62; obj_colour = q->id ? P2_COLOUR : 0;
    if (q->state != PL_OFF) {
        /* $2F6B: from the partner's position; the player is hidden (a dying partner's death task
         * never runs, as in the arcade) */
        obj_x = q->x; obj_y = q->y;
        q->state = PL_OFF;
        obj_anim = 80; obj_vx = obj_vy = 0;
    } else if (level.dir_y && !level.dir_x) {
        obj_x = 0x80 - 96; obj_y = 0x08 - 16;       /* $2F4D, script: +2 px/frame down for 24 f */
        obj_anim = 24; obj_vx = 0; obj_vy = 2;
    } else {
        obj_x = 0x40 - 96; obj_y = 0x98 - 16;       /* $2F35, script: +3 px/frame right for 24 f */
        obj_anim = 24; obj_vx = 3; obj_vy = 0;
    }
    obj_steps = 0;
    seq = SEQ_TRANSFORM; seq_t = 0;
}

void combine_hit(void)
{
    if (seq != SEQ_NONE) return;
    if (combined_hp && --combined_hp) return;
    /* $223F: split */
    weapons_clear(&players[0]);
    weapons_clear(&players[1]);
    seq = SEQ_SPLIT; seq_t = 0;
}

void combine_join(Player *p)
{
    /* $1B41/$1853: a player starting or continuing while merged is the partner: the robot splits
     * (no hit) and both come back in place */
    p->in_play = TRUE;
    if (seq == SEQ_NONE) {
        weapons_clear(&players[0]);
        weapons_clear(&players[1]);
        seq = SEQ_SPLIT; seq_t = 0;
    }
}

static u8 aim(void)
{
    /* $06E8-ish: 16-sector direction from the object to the target, clockwise from right */
    s16 dy = tgt_y - obj_y, dx = tgt_x - obj_x;
    s16 ay = dy < 0 ? -dy : dy, ax = dx < 0 ? -dx : dx;
    u8 o;                                   /* octant-ish angle 0-4 within the quadrant */
    if (ay * 5 < ax) o = 0;                 /* < ~11 deg */
    else if (ay * 3 < ax * 2) o = 1;        /* < ~34 deg */
    else if (ay * 2 < ax * 3) o = 2;        /* < ~56 deg */
    else if (ay < ax * 5) o = 3;            /* < ~79 deg */
    else o = 4;
    if (dx >= 0) return dy >= 0 ? o : (16 - o) & 15;
    return dy >= 0 ? 8 - o : 8 + o;
}

static bool touching(void)
{
    /* contact $2617: |(ly+8) - oy| < +$0E (16), |(lx/2+4) - ox/2| < +$0F (8 = 16 px) */
    s16 dy = tgt_y - obj_y, dx = tgt_x + 8 - obj_x;
    if (dy < 0) dy = -dy;
    if (dx < 0) dx = -dx;
    return dy < 16 && dx < 16;
}

static void merge_done(void)
{
    Player *l = leader();
    combined_hp = players[0].in_play && players[1].in_play ? 1 : 2;   /* $304E: $E018 == $81 */
    weapons_build_bits(&players[0]);
    weapons_build_bits(&players[1]);
    l->ref_y = l->y; l->ref_x = l->x + 16;
    robot_code = robot_base() + 6;
    seq = SEQ_NONE;
}

static void split_done(void)
{
    Player *l = leader(), *q = partner();
    q->x = l->x; q->y = l->y + 32;
    player_respawn_in_place(l);
    combined = 0;
    if (q->lives) { player_respawn_in_place(q); seq = SEQ_NONE; }
    else { seq = SEQ_EXPLODE; seq_t = 0; }          /* $343D: partner without lives explodes */
    weapons_build_bits(&players[0]);
    weapons_build_bits(&players[1]);
}

/* Merge / split sequences. TRUE while one runs (the rest of the game is suspended). */
bool combine_update(void)
{
    if (seq == SEQ_NONE) return FALSE;
    seq_t++;
    switch (seq) {
    case SEQ_TRANSFORM:                     /* leader: 4 codes x 12 frames ($0210 waits) */
        if (seq_t >= 48) { seq = SEQ_FLY; seq_t = 0; }
        break;
    case SEQ_FLY:
        if (obj_anim) {
            obj_anim--;
            obj_x += obj_vx; obj_y += obj_vy;
        } else {
            if (!obj_steps) {               /* re-aim every 12 frames */
                const s8 *v = HOMING[aim()];
                obj_vy = v[0]; obj_vx = v[1]; obj_steps = 12;
            }
            obj_steps--;
            obj_x += obj_vx; obj_y += obj_vy;
        }
        if (touching()) { sound_play(0x0B); seq = SEQ_MERGE; seq_t = 0; }
        break;
    case SEQ_MERGE:                         /* $302C: 4 codes x 12 frames */
        if (seq_t >= 48) merge_done();
        break;
    case SEQ_SPLIT:                         /* $335D: reverse, 4 x 12 frames */
        if (seq_t >= 48) { seq = SEQ_SPLIT_SHOW; seq_t = 0; }
        break;
    case SEQ_SPLIT_SHOW:                    /* $341D: both bodies, 12 frames */
        if (seq_t >= 12) split_done();
        break;
    case SEQ_EXPLODE:                       /* 8 codes x 6 frames */
        if (seq_t >= 6 * PARTNER_EXPLODE_N) seq = SEQ_NONE;
        break;
    default: break;
    }
    return TRUE;
}

/* $8FF0, run at the end of EVERY merged player's update (twice a frame with a partner in play):
 * robot body code, muzzle flash +$1A while the shared fire timer $E016 is >= 8 after its decrement,
 * else +$1C */
static void robot_composite(void)
{
    robot_code = robot_base() + 6;
    if (fire_flash) {
        fire_flash--;
        robot_code += fire_flash >= 8 ? 0x1A : 0x1C;
    }
}

/* Per-frame update of either player while merged (B2:$831F leader / $8D14 partner) */
void combine_update_player(Player *p, u8 in)
{
    Player *l = leader(), *q = partner();
    if (p == l) {
        p->old_x = p->x; p->old_y = p->y;
        u8 dir = in & 0x0F;
        if (!dir && players[0].lives && players[1].lives)
            dir = (pad[0].held | pad[1].held) & 0x0F;          /* $8342 */
        player_move(p, dir, MOVE_TABLE[3]);
        if (crushed || !combined) return;
        weapons_pose(p);
        weapons_fire(p, in);
        if (!q->in_play) weapons_ring(p, pad_fire_held[p->id]); /* $8D25: no partner: leader fires it */
        p->ref_y = p->y; p->ref_x = p->x + 16;                 /* $9053 */
        robot_composite();
    } else if (p->in_play) {
        p->x = l->x; p->y = l->y + 32;                         /* $9063: partner record follows */
        weapons_ring(p, pad_fire_held[p->id]);
        robot_composite();
    }
}

static void draw_robot_at(const Player *l, u16 code)
{
    spr_32(code, 0, l->x, l->y, 0);
    spr_16(code + 16, 0, l->x, l->y + 32, 0);
    spr_16(code + 17, 0, l->x + 16, l->y + 32, 0);
}

void combine_draw_robot(const Player *l)
{
    draw_robot_at(l, robot_code ? robot_code : robot_base() + 6);
}

bool combine_draw(void)
{
    if (seq == SEQ_NONE) return FALSE;
    weapons_draw(&players[0]);
    weapons_draw(&players[1]);
    Player *l = &players[seq_lead];
    switch (seq) {
    case SEQ_TRANSFORM: case SEQ_FLY: {
        static const u8 T[4] = { 0x76, 0x72, 0x66, 0x62 };
        u16 off = l->id ? P2_CODE : 0;
        u8 col = l->id ? P2_COLOUR : 0;
        u16 i = seq == SEQ_TRANSFORM ? seq_t / 12 : 3;
        if (i > 3) i = 3;
        spr_32(T[i] + off, col, l->x, l->y, 0);
        if (seq == SEQ_FLY) {
            u16 c = obj_code;
            if (obj_anim && obj_vx == 0 && obj_vy == 0)        /* template opening: $76,$72,$66,$62 */
                c = T[(80 - obj_anim) / 20 & 3] + (obj_code & 0x80);
            spr_32(c, obj_colour, obj_x, obj_y, 0);
        }
        break;
    }
    case SEQ_MERGE: case SEQ_SPLIT: {
        u16 i = seq_t / 12; if (i > 3) i = 3;
        if (seq == SEQ_SPLIT) i = 3 - i;
        draw_robot_at(l, robot_base() + 2 * i);
        break;
    }
    case SEQ_SPLIT_SHOW: {                  /* $33CB: leader $62/$E2, partner $E2/$62 below */
        Player *q = partner();
        spr_32(l->id ? 0xE2 : 0x62, l->id ? P2_COLOUR : 0, l->x, l->y, 0);
        spr_32(q->id ? 0xE2 : 0x62, q->id ? P2_COLOUR : 0, l->x, l->y + 32, 0);
        break;
    }
    case SEQ_EXPLODE: {
        /* leader already back in play; partner explodes where its body was */
        const Player *lead = &players[seq_lead], *q = &players[!seq_lead];
        spr_32(lead->body_code + (lead->id ? P2_CODE : 0), lead->id ? P2_COLOUR : 0, lead->x, lead->y, 0);
        u16 i = seq_t / 6; if (i >= PARTNER_EXPLODE_N) i = PARTNER_EXPLODE_N - 1;
        spr_32(PARTNER_EXPLODE[i], 8, q->x, q->y, 0);
        break;
    }
    default: break;
    }
    return TRUE;
}
