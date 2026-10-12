#include "bc_rules.h"
#include "bc_bullet_turn.h"

unsigned short bc_random_next(unsigned short seed)
{
    /* $6D41-$6D65 computes 3*seed modulo 65536, then adds the old low byte
     * to the product's high byte. The final carry is discarded. */
    /* Adding seed's low byte to the high byte is seed<<8 modulo65536.
     * Express that directly to avoid extracting and rebuilding both bytes. */
    return (unsigned short)(seed * 3u + ((unsigned int)seed << 8));
}

/* PCE $8F39-$8F60, direction tables $9BC7/$9BE7, captured with MPR2..6
 * mapping banks $80..$84. Conflicting directions produce no movement.
 * Diagonals deliberately use integer speeds, not normalized vectors. */
void bc_direction(unsigned char direction, unsigned char speed_up, signed char *dx, signed char *dy)
{
    /* Resolve the two source speed tables once at build time. Every input
     * nibble, including conflicting directions, retains its exact vector. */
    static const signed char vectors[32][2] = {
        {0,0},{0,-3},{3,0},{2,-2},{0,3},{0,0},{2,2},{0,0},
        {-3,0},{-2,-2},{0,0},{0,0},{-2,2},{0,0},{0,0},{0,0},
        {0,0},{0,-4},{4,0},{3,-3},{0,4},{0,0},{3,3},{0,0},
        {-4,0},{-3,-3},{0,0},{0,0},{-3,3},{0,0},{0,0},{0,0},
    };
    unsigned char index = (direction & 15) | (speed_up ? 16 : 0);
    *dx = vectors[index][0]; *dy = vectors[index][1];
}

/* PCE $808D-$8118: the 4096x4096 world is stored as 256-pixel blocks,
 * each containing 8x8 32-pixel cells. Collision is per 16-pixel subcell. */
unsigned char bc_terrain_solid(const BcTerrain *terrain, unsigned short x, unsigned short y)
{
    /* Select world bits directly. Splitting the high-byte shifts makes the
     * 68000 emit two serial shifts (including a ten-bit variable shift) for
     * every terrain probe; these masks also perform the 4096px wrapping. */
    unsigned short index = ((x >> 5) & 7) |
                           (((x & 3840) | (y & 224)) >> 2) |
                           ((y << 2) & 15360);
    unsigned short part = ((x & 16) >> 3) | ((y & 16) >> 2);
    return terrain->attributes[terrain->cells[index] * 8 + part + 1] & 15;
}

/* PCE $8F39-$902E, after the entry/state checks. Probe horizontal first,
 * then vertical, using the pre-move position; scrolling can crush a player
 * against the left/top limit. Return 1 for that crush transition. */
unsigned char bc_move_step(BcMotion *p, unsigned char direction, unsigned char speed_up,
                           unsigned short camera_x, unsigned short camera_y,
                           unsigned short scroll_dx, unsigned short scroll_dy,
                           const BcTerrain *terrain)
{
    bc_direction(direction, speed_up, &p->dx, &p->dy);
    unsigned short x = camera_x + (p->x >> 8), y = camera_y + (p->y >> 8);
    if (bc_terrain_solid(terrain, x + (p->dx < 0 ? -8 : 8), y)) {
        unsigned char forward = p->dx >= 0;
        p->dx = 0;
        if (forward && scroll_dx) {
            p->x -= scroll_dx;
            if (p->x < (16 << 8)) return 1;
        }
    }
    x = camera_x + (p->x >> 8);
    if (bc_terrain_solid(terrain, x, y + (p->dy < 0 ? -8 : 8))) {
        unsigned char forward = p->dy >= 0;
        p->dy = 0;
        if (forward && scroll_dy) {
            p->y -= scroll_dy;
            if (p->y < (32 << 8)) return 1;
        }
    }
    p->x += p->dx * 256;
    p->y += p->dy * 256;
    /* Coordinates are unsigned 8.8: compare in that format instead of
     * shifting away the fractional byte for each screen-boundary test. */
    if (p->x >= (240 << 8)) { p->x = (p->x & 255) | (240 << 8); p->dx = 0; }
    if (p->x < (16 << 8)) { p->x = (p->x & 255) | (16 << 8); p->dx = 0; }
    if (p->y < (32 << 8)) { p->y = (p->y & 255) | (32 << 8); p->dy = 0; }
    if (p->y >= (200 << 8)) { p->y = (p->y & 255) | (200 << 8); p->dy = 0; }
    return 0;
}

/* PCE $90B8-$90EF and $9838-$988B. The normal projectile routines between
 * these blocks are separate; this returns only the charge/beam decision.
 * A full beam pool consumes the released charge without launching a beam. */
BcChargeEvent bc_charge_step(BcCharge *s, unsigned char buttons, unsigned char alive,
                             unsigned char entering, unsigned char beam_busy)
{
    BcChargeEvent event = { 0, 0 };
    if (!alive || entering) return event;
    buttons &= 3;
    if (buttons == 1 || buttons == 2) {
        s->held_frames++;
        if (s->charge < 64) s->charge++;
        s->facing = buttons == 1;
        if (s->charge == 16) event.sound = 0x17;
        return event;
    }
    s->held_frames = 0;
    s->shoot_latch = 0;
    unsigned char charge = s->charge;
    s->charge = 0;
    if (charge >= 40) {
        if (!beam_busy) event.beam_segments = charge >= 60 ? 5 : charge >= 50 ? 4 : 3;
    } else if (charge >= 16) event.sound = 1;
    return event;
}

/* PCE $9889-$9987: head/body/tail templates. Reused slots retain their
 * fractional coordinates: the source writes only the integer bytes. */
void bc_beam_launch(BcBeam slots[5], unsigned char segments, unsigned char facing,
                    unsigned short player_x, unsigned short player_y)
{
    if (segments < 3 || segments > 5) return;
    for (unsigned char i = 0; i < 5; i++) if (slots[i].state) return;
    for (unsigned char i = 0; i < segments; i++) {
        BcBeam *b = &slots[i];
        bc_beam_set_x(b, player_x - 8);
        bc_beam_set_y(b, player_y - 5);
        b->vx = b->vy = 0;
        b->sprite = i == 0 ? 0x1c0 : i + 1 == segments ? 0x1bc : 0x1be;
        b->attributes = 0x81;
        b->state = 0x80; b->timer = 1; b->flags = 0;
        b->damage = 2; b->half_x = 6; b->half_y = 8;
        b->delay = i; b->accelerating = 1; b->facing = facing != 0;
    }
}

/* $9B09-$9B8F leaves the carry from its signed 24-bit addition set during
 * the following offscreen check. Keep that observable one-pixel distinction. */
static unsigned char beam_axis(unsigned int *position, BcBeamVelocity velocity)
{
#if defined(__m68k__)
    unsigned int value = *position, step = (unsigned int)velocity;
    /* The low byte retains old source padding. Add the 24-bit carry to that
     * byte without carrying into the position, then extract and clear it. */
    /* step's low byte is zero: ADDX folds padding plus carry into it. */
    __asm__("add.l %1,%0\n\taddx.b %0,%1\n\t"
            "andi.w #255,%1\n\tclr.b %0"
        : "+d"(value), "+d"(step) : : "cc");
    *position = value;
    return (unsigned short)((value >> 16) + (unsigned short)step + 16) >= 0x120;
#else
#if BC_BEAM_ALIGNED
    unsigned int source = (*position >> 8) | (*position << 24);
#else
    unsigned int source = *position;
#endif
    unsigned int sum = source + ((unsigned int)velocity & 0xffffff);
    unsigned int next = sum & 0xffffff;
#if BC_BEAM_ALIGNED
    *position = next << 8;
#else
    *position = next;
#endif
    return (unsigned short)((next >> 8) + 16 + (sum >> 24)) >= 0x120;
#endif
}

/* Returning shots discard the offscreen result. Their position still wraps
 * to the same 24 source bits, including clearing old container padding. */
static inline __attribute__((always_inline)) void beam_move(unsigned int *position,
    BcBeamVelocity velocity)
{
#if defined(__m68k__)
    *position = (*position + (unsigned int)velocity) & 0xffffff00u;
#elif BC_BEAM_ALIGNED
    *position = (*position + ((unsigned int)velocity << 8)) & 0xffffff00u;
#else
    *position = (*position + (unsigned int)velocity) & 0xffffffu;
#endif
}

/* Map a zero facing byte to source sprite bit 11 without a long shift. */
static inline __attribute__((always_inline)) unsigned short projectile_left_flip(unsigned char facing)
{
#if defined(__m68k__)
    unsigned short bits;
    __asm__("tst.b %1\n\tseq %0\n\text.w %0\n\tandi.w #2048,%0"
        : "=d"(bits) : "d"(facing) : "cc");
    return bits;
#else
    return facing ? 0 : 0x800;
#endif
}

static inline __attribute__((always_inline)) unsigned char projectile_timer_due(unsigned char *timer)
{
#if defined(__m68k__)
    unsigned char expired;
    __asm__("subq.b #1,%1\n\tseq %0"
        : "=d"(expired), "+m"(*timer) : : "cc");
    return expired != 0;
#else
    return !--*timer;
#endif
}

/* $998A-$99B9 and $9A9F-$9B95. The newly launched slots are updated in the
 * launch frame. The rear segments accelerate one update after the preceding
 * segment, producing the source beam's spacing without spawning extra shots. */
void bc_beam_step(BcBeam *b)
{
    if (!b->state) return;
    if (b->accelerating) {
        if (b->delay) b->delay--;
        else {
            b->vx = bc_beam_velocity(b->facing ? 0x1000 : -0x1000);
            b->accelerating = 0;
        }
    }
    if (projectile_timer_due(&b->timer)) {
        b->timer = 4;
        b->attributes = (b->attributes & 0x77ff) |
                         (b->sprite != 0x1be ? projectile_left_flip(b->facing) : 0);
    }
    unsigned char outside = beam_axis(&b->x, b->vx);
    if (outside && !(b->flags & 2)) { b->state = 0; return; }
    outside = beam_axis(&b->y, b->vy);
    if (outside && !(b->flags & 2)) b->state = 0;
}

/* $9106/$92B5 classify five power tiers; the 5x5 launch tables retain the
 * original descending volley order. Zero table entries are straight shots. */
unsigned char bc_shot_fire(BcShot slots[28], unsigned char kind, unsigned char power,
                           unsigned char facing, unsigned short px, unsigned short py)
{
    static const unsigned char spread[25] = {
        0,0,0,0,0, 3,19,0,0,0, 0,4,20,0,0, 3,19,6,22,0, 0,4,20,7,23
    };
    static const signed char ring[25] = {
        0,0,0,0,0, 3,-3,0,0,0, 0,6,-6,0,0, 3,-3,9,-9,0, 0,6,-6,12,-12
    };
    if (kind > 1) return 0;
    unsigned char tier = (power >= 1) + (power >= 3) + (power >= 7) + (power >= 15);
    unsigned char created = 0;
    BcShot *s = slots, *end = slots + 28;
    /* Earlier records stay occupied until this entire volley has launched. */
    for (signed char member = tier; member >= 0; member--) {
        while (s != end && s->body.state) s++;
        if (s == end) break;
        BcBeam *b = &s->body;
        s->kind = kind; s->tier = tier; s->phase = s->animation = 0;
        bc_beam_set_x(b, px + (facing ? 16 : -16));
        bc_beam_set_y(b, py - 5);
        b->state = 0x80; b->timer = 1; b->flags = 0; b->damage = 1;
        b->half_x = kind ? 4 : 3; b->half_y = kind ? 4 : 8;
        b->sprite = kind ? 0x1ae : 0x1b8; b->attributes = 0x81;
        b->facing = facing != 0; b->accelerating = 1;
        if (!kind) {
            unsigned char pattern = spread[tier * 5 + member];
            b->delay = pattern & 15;
            b->vx = bc_beam_velocity((pattern ? 2 : 8) * (facing ? 256 : -256));
            b->vy = bc_beam_velocity(pattern ? ((pattern & 0xf0) ? -1024 : 1024) : 0);
        } else {
            b->delay = 0;
            b->vx = bc_beam_velocity(facing ? 3072 : -3072);
            b->vy = bc_beam_velocity(ring[tier * 5 + member] * 256);
        }
        created++;
    }
    return created;
}

/* $923E: shared impact animation, including impacts on terrain. */
void bc_shot_impact(BcShot *s)
{
    s->body.state = 0x40;
    s->body.vx = s->body.vy = 0;
    s->body.flags |= 1;
    s->body.timer = 1;
    s->body.accelerating = 0;
    s->phase = 1; s->animation = 0;
}

/* $A0B5-$A0C3 schedules the response; movement already happened this frame. */
void bc_shot_hit(BcShot *s)
{
    if (s->body.state != 0x80) return;
    s->body.state = 0x40;
    s->phase = 3;
    s->body.accelerating = 1;
}

/* Caller has already checked the live slot; return retirement directly. */
static inline __attribute__((always_inline)) unsigned char shot_step_live(BcShot *s, unsigned short camera_x, unsigned short camera_y,
                   const BcTerrain *terrain)
{
    BcBeam *b = &s->body;
    if (s->phase == 3) bc_shot_impact(s);
    if (b->accelerating) {
        unsigned char probe = 1;
        if (!s->kind && b->delay) {
            if (--b->delay) probe = 0;
            else { b->vx = bc_beam_velocity(b->facing ? 2048 : -2048); b->vy = 0; }
        }
        if (probe && bc_terrain_solid(terrain, camera_x + (bc_beam_x(b)), camera_y + (bc_beam_y(b))))
            bc_shot_impact(s);
        else if (s->kind && ++b->delay >= 11) {
            b->vx = b->vy = 0; b->flags |= 1; b->timer = 1;
            b->accelerating = 0; s->phase = 2; s->animation = 0;
        }
    }
    if (projectile_timer_due(&b->timer)) {
        unsigned short sprite;
        if (s->phase == 1) {
            if (s->animation >= 2) { b->state = 0; return 1; }
            sprite = 0x1d4 + s->animation * 2;
        } else if (s->phase == 2) {
            /* Options select the larger flight sprite at power 4, but clear
             * the source expansion tier. Their expansion still starts small. */
            unsigned char first = s->tier >= 3 && !(b->flags & 12) ? 1 : 0;
            if (s->animation + first >= 3) { b->state = 0; return 1; }
            sprite = 0x1b0 + (s->animation + first) * 2;
        } else sprite = s->kind ? (s->tier >= 3 ? 0x1b6 : 0x1ae) : (s->tier >= 3 ? 0x1ba : 0x1b8);
        b->timer = 4; b->sprite = sprite;
        b->attributes = (b->attributes & 0x77ff) |
            (s->kind && s->phase != 1 ? projectile_left_flip(b->facing) : 0);
        if (s->phase) s->animation++;
    }
    unsigned char outside = beam_axis(&b->x, b->vx);
    if (outside && !(b->flags & 2)) { b->state = 0; return 1; }
    outside = beam_axis(&b->y, b->vy);
    if (outside && !(b->flags & 2)) { b->state = 0; return 1; }
    return 0;
}

void bc_shot_step(BcShot *s, unsigned short camera_x, unsigned short camera_y,
    const BcTerrain *terrain)
{
    if (s->body.state) (void)shot_step_live(s, camera_x, camera_y, terrain);
}

/* $82BE-$837A, shared 16-direction aiming. Negative deltas use one's
 * complement rather than absolute value: preserve the one-unit bias. */
unsigned char bc_aim16(unsigned short tx, unsigned short ty, unsigned short sx, unsigned short sy)
{
    static const unsigned char direction[32] = {
        0,1,2,3,4,0,0,0, 8,7,6,5,4,0,0,0,
        0,15,14,13,12,0,0,0, 8,9,10,11,12,0,0,0
    };
    tx += 256; ty += 256; sx += 256; sy += 256;
    unsigned short dx = tx - sx, dy = ty - sy;
    unsigned char quadrant = 0, angle = 0;
    if (tx < sx) { dx = (unsigned short)~dx; quadrant = 8; }
    if (ty < sy) { dy = (unsigned short)~dy; quadrant |= 16; }
    if (dx < (unsigned short)(dy * 5)) {
        angle++;
        if ((unsigned short)(dx * 2) < (unsigned short)(dy * 3)) {
            angle++;
            if ((unsigned short)(dx * 3) < (unsigned short)(dy * 2)) {
                angle++;
                if ((unsigned short)(dx * 5) < dy) angle++;
            }
        }
    }
    return direction[quadrant | angle];
}

unsigned char bc_return_fire(BcReturn slots[28], unsigned char power, unsigned char facing,
                             unsigned short px, unsigned short py, unsigned char *active)
{
    unsigned char limit = 2 * ((power >= 1) + (power >= 3) + (power >= 7) + (power >= 15));
    if (*active >= limit) return 0;
    unsigned char i = 0;
    while (i < 28 && slots[i].body.state) i++;
    if (i == 28) return 0;
    BcReturn *s = &slots[i];
    s->kind = 2; s->tier = s->phase = 0;
    BcBeam *b = &s->body;
    bc_beam_set_x(b, px + (facing ? 16 : -16));
    bc_beam_set_y(b, py - 5);
    b->vx = bc_beam_velocity(facing ? 2048 : -2048); b->vy = 0;
    b->state = 0x80; b->timer = 1; b->flags = 2; b->damage = 1;
    b->half_x = b->half_y = 5;
    b->sprite = 0x1a8; b->attributes = 0x81;
    b->delay = 12; b->accelerating = 1; b->facing = facing != 0;
    s->launch_wait = 16; s->animation = 0;
    (*active)++;
    return 1;
}

static unsigned short return_distance(unsigned short target, unsigned short source)
{
    return bc_unsigned_distance(target, source);
}

/* $953A-$95E9: sixteen straight updates, then retarget every update. The
 * catch test precedes motion and terminates via the source's $FF script. */
void bc_return_step(BcReturn *s, unsigned short px, unsigned short py, unsigned char *active)
{
    static const signed short vector[32] = {
        2048,0, 1890,782, 1447,1447, 782,1890,
        0,2048, -782,1890, -1447,1447, -1890,782,
        -2048,0, -1890,-782, -1447,-1447, -782,-1890,
        0,-2048, 782,-1890, 1447,-1447, 1890,-782
    };
    static const unsigned short sprite[8] = {0x1a8,0x1aa,0x1ac,0x1aa,0x1a8,0x1aa,0x1ac,0x1aa};
    static const unsigned short flip[8] = {0,0,0,0x8000,0x8000,0x8800,0x800,0x800};
    BcBeam *b = &s->body;
    if (!b->state) return;
    if (s->launch_wait) s->launch_wait--;
    else {
        unsigned short x = bc_beam_x(b), y = bc_beam_y(b);
        unsigned char d = bc_aim16(px, py, x, y);
        b->delay = d; b->vx = bc_beam_velocity(vector[d * 2]); b->vy = bc_beam_velocity(vector[d * 2 + 1]);
        if (return_distance(px, x) < 16 && return_distance(py, y) < 16) {
            (*active)--; b->timer = 0; b->state = 0;
            return;
        }
    }
    if (projectile_timer_due(&b->timer)) {
        unsigned char k = s->animation;
        b->timer = 4; b->sprite = sprite[k];
        b->attributes = (b->attributes & 0x77ff) | flip[k];
        s->animation = (k + 1) & 7;
    }
    beam_move(&b->x, b->vx);
    beam_move(&b->y, b->vy);
}


/* $9C2D-$9CA7: replace a missing option first, otherwise refill the one with
 * less HP (upper wins ties). Only integer coordinates are initialized. */
unsigned char bc_option_collect(BcShot slots[30], unsigned char facing,
                                 unsigned short px, unsigned short py)
{
    unsigned char i = 28;
    if (slots[28].body.state == 0x80) {
        if (slots[29].body.state != 0x80) i = 29;
        else {
            if ((slots[28].tier & slots[29].tier) == 3) return 0;
            if (slots[28].tier > slots[29].tier) i = 29;
        }
    }
    BcShot *s = &slots[i];
    BcBeam *b = &s->body;
    s->kind = 4; s->tier = 3; s->phase = s->animation = 0; s->launch_wait = i - 28;
    bc_beam_set_x(b, px);
    bc_beam_set_y(b, py);
    b->vx = b->vy = 0; b->state = 0x80; b->timer = 1;
    b->flags = 3; b->damage = 10; b->half_x = b->half_y = 3;
    b->attributes = 0x81; b->sprite = 0x1c2;
    b->delay = 0; b->accelerating = 1;
    /* Facing selects the initial script, but the first update selects it again
     * from current player facing before reading an animation frame. */
    (void)facing;
    return i + 1;
}

/* $9CA8-$9D59. The original trail stores low coordinate bytes only; X retains
 * its spawn high byte, while Y combines the trail byte with current player Y's
 * high byte. Do not replace this with full-width delayed player coordinates. */
static inline unsigned char __attribute__((always_inline)) option_step_live(BcShot *s, unsigned char facing, unsigned char hx,
                     unsigned char hy, unsigned short py)
{
    BcBeam *b = &s->body;
    if (s->phase == 3) {
        if (--s->tier) { b->state = 0x80; s->phase = 0; }
        else {
            b->timer = 1; b->attributes = (b->attributes & 0xff00) | 0x81;
            b->accelerating = 0; s->phase = 1; s->animation = 0;
        }
    }
    if (b->accelerating) {
        if (b->delay != 14 && ++b->delay == 14) b->flags = 2;
        bc_beam_low_x(b, hx);
        unsigned short y = (py & 0xff00) | hy;
        y += s->launch_wait ? b->delay * 2 : -b->delay * 2;
        bc_beam_set_y(b, y);
    }
    if (projectile_timer_due(&b->timer)) {
        if (s->phase == 1) {
            if (s->animation == 4) { b->state = 0; return 1; }
            b->sprite = 0x1e0 + s->animation++ * 2; b->timer = 4;
            b->attributes &= 0x77ff;
        } else {
            b->sprite = 0x1c0 + s->tier * 2; b->timer = 2;
            b->attributes = (b->attributes & 0x77ff) | projectile_left_flip(facing);
        }
    }
    /* With this source flag, neither offscreen result can retire the option.
     * Keep its exact position update without computing unused bounds. */
    if (b->flags & 2) {
        beam_move(&b->x, b->vx);
        beam_move(&b->y, b->vy);
        return 0;
    }
    unsigned char outside = beam_axis(&b->x, b->vx);
    if (outside && !(b->flags & 2)) { b->state = 0; return 1; }
    outside = beam_axis(&b->y, b->vy);
    if (outside && !(b->flags & 2)) { b->state = 0; return 1; }
    return 0;
}

void bc_option_step(BcShot *s, unsigned char facing, unsigned char hx,
                     unsigned char hy, unsigned short py)
{
    if (s->body.state) (void)option_step_live(s, facing, hx, hy, py);
}

/* $9650-$9837: each option permits two owned shots. The option weapon is the
 * next main family (straight -> expanding -> returning -> straight), with its
 * own power threshold. Ownership remains attached until the slot retires. */
static unsigned char option_fire(BcWeapons *w, unsigned char kind,
                                 unsigned char power, unsigned char facing)
{
    if (kind > 2) return 0;
    unsigned char created = 0;
    for (unsigned char side = 0; side < 2; side++) {
        BcBeam *option = &w->shots[28 + side].body;
        if (option->state != 0x80 || w->option_shots[side] >= 2) continue;
        unsigned char slot = 0;
        while (slot < 28 && w->shots[slot].body.state) slot++;
        if (slot == 28) continue;
        unsigned short x = (bc_beam_x(option)) - (facing ? 16 : -16);
        unsigned short y = (bc_beam_y(option)) + 5;
        unsigned char family = (kind + 1) % 3;
        unsigned char old_delay = w->shots[slot].body.delay;
        if (family == 2) {
            unsigned char count = 0;
            bc_return_fire(w->shots, 1, facing, x, y, &count);
            w->returning++;
        } else {
            bc_shot_fire(w->shots, family, 0, facing, x, y);
            w->shots[slot].tier = power >= 4 ? 3 : 0;
            if (family == 1) w->shots[slot].body.vy = bc_beam_velocity(side ? 1536 : -1536);
            /* $97C8 does not initialize $2DCC: the straight option shot
             * inherits its terrain-probe delay from the reused slot. */
            else w->shots[slot].body.delay = old_delay;
        }
        w->shots[slot].body.flags |= side ? 4 : 8;
        w->option_shots[side]++; created++;
    }
    return created;
}

void bc_weapons_record_position(BcWeapons *w, unsigned short px, unsigned short py)
{
#if defined(__m68k__)
    /* The trail begins at an odd byte, so its odd offsets are word-aligned.
     * Copy backward in aligned longwords, preserving the overlapping source. */
    _Static_assert((__builtin_offsetof(BcWeapons, trail) & 1) &&
                   __alignof__(BcWeapons) >= 2, "trail copy alignment");
    __asm__ volatile ("move.b 13(%1),15(%1)\n\t"
                      "move.l 9(%1),11(%1)\n\t"
                      "move.l 5(%1),7(%1)\n\t"
                      "move.l 1(%1),3(%1)\n\t"
                      "move.b 0(%1),2(%1)"
        : "+m"(w->trail) : "a"(w->trail) : "cc");
#else
    for (unsigned char i = 15; i >= 2; i--) w->trail[i] = w->trail[i - 2];
#endif
    w->trail[0] = px; w->trail[1] = py;
}

/* Only live slots enter the task dispatcher. Inline the task so repeated
 * frame arguments stay with the caller; traversal keeps source slot order. */
static inline void __attribute__((always_inline)) weapon_live_step(BcWeapons *w, BcShot *s,
    unsigned short px, unsigned short py, unsigned short cx, unsigned short cy,
    const BcTerrain *terrain)
{
    unsigned char retired;
    if (s->kind < 2) retired = shot_step_live(s, cx, cy, terrain);
    else {
        if (s->kind == 2) bc_return_step(s, px, py, &w->returning);
        else if (s->kind == 3) bc_beam_step(&s->body);
        else if (s->kind == 4) {
            retired = option_step_live(s, w->charge.facing, w->trail[14], w->trail[15], py);
            goto retirement;
        }
        retired = !s->body.state;
    }
retirement:
    if (retired && (s->body.flags & 12)) {
        if (s->body.flags & 8) w->option_shots[0]--;
        else w->option_shots[1]--;
    }
}

void bc_weapons_step_into(BcWeaponEvent *event, BcWeapons *w, unsigned char held,
    unsigned char pressed, unsigned char alive, unsigned char entering,
    unsigned char kind, unsigned char power, unsigned short px,
    unsigned short py, unsigned short cx, unsigned short cy,
    const BcTerrain *terrain)
{
    *event = (BcWeaponEvent){0};
    /* $90B8: entry suppresses the entire weapon task; death still updates
     * existing shots. Source order is charge, ordinary fire, beam, all slots. */
    if (alive && entering) return;
    if (alive) {
        unsigned char busy = 0;
        /* Charge only consults beam occupancy on a charged release. Ordinary
         * fire and short releases cannot use these five slot reads. */
        if (w->charge.charge >= 40 && ((held & 3) == 0 || (held & 3) == 3))
            for (unsigned char i = 20; i < 25; i++) busy |= w->shots[i].body.state;
        BcChargeEvent charge = bc_charge_step(&w->charge, held, 1, 0, busy);
        event->charge_sound = charge.sound;
        held &= 3;
        if ((held == 1 || held == 2) && (pressed & 3)) {
            if (kind < 2) {
                event->shots = bc_shot_fire(w->shots, kind, power, w->charge.facing, px, py);
                /* The expanding weapon issues recoil/sound even if no slot
                 * is free; the straightening weapon returns immediately. */
                unsigned char volley = 1 + (power >= 1) + (power >= 3) + (power >= 7) + (power >= 15);
                if (event->shots == volley || kind == 1) { event->shot_sound = 5; event->recoil = 3; }
            } else if (kind == 2) {
                event->shots = bc_return_fire(w->shots, power, w->charge.facing, px, py, &w->returning);
                if (event->shots) { event->shot_sound = 6; event->recoil = 3; }
            }
        }
        if (pressed & 3) event->option_shots = option_fire(w, kind, power, w->charge.facing);
        /* Option fire happens before the source checks the reserved beam
         * slots, so a new option shot can consume a just-released beam. */
        if (charge.beam_segments) {
            busy = 0;
            for (unsigned char i = 20; i < 25; i++) busy |= w->shots[i].body.state;
        }
        if (charge.beam_segments && !busy) {
            /* Conversion is only on launch, not on every projectile update. */
            BcBeam beam[5];
            for (unsigned char i = 0; i < 5; i++) beam[i] = w->shots[20 + i].body;
            bc_beam_launch(beam, charge.beam_segments, w->charge.facing, px, py);
            for (unsigned char i = 0; i < charge.beam_segments; i++) {
                w->shots[20 + i].body = beam[i]; w->shots[20 + i].kind = 3;
            }
            event->beam_segments = charge.beam_segments;
            event->shot_sound = 7; event->recoil = 10;
        }
    }
    BcShot *shot = w->shots;
    BcShot *end = shot + 30;
    while (shot != end) {
        if (shot->body.state) {
            weapon_live_step(w, shot, px, py, cx, cy, terrain);
        } else if (shot <= end - 6 && !(shot[1].body.state | shot[2].body.state |
                   shot[3].body.state | shot[4].body.state | shot[5].body.state)) {
            /* No task can change these empty slots while they are skipped. */
            shot += 6;
            continue;
        }
        shot++;
    }
    return;
}

BcWeaponEvent bc_weapons_step(BcWeapons *w, unsigned char held,
    unsigned char pressed, unsigned char alive, unsigned char entering,
    unsigned char kind, unsigned char power, unsigned short px,
    unsigned short py, unsigned short cx, unsigned short cy,
    const BcTerrain *terrain)
{
    BcWeaponEvent event;
    bc_weapons_step_into(&event, w, held, pressed, alive, entering, kind, power,
        px, py, cx, cy, terrain);
    return event;
}

/* $8990-$8A28. Weapon power and life counters are bytes in the original;
 * preserve their wrapping increments rather than imposing a new cap. */
BcPickupEvent bc_pickup_apply(BcInventory *p, BcWeapons *w, unsigned char item,
                              unsigned short px, unsigned short py)
{
    BcPickupEvent event = {0, 0, 0, 0, 0};
    if (item < 1 || item > 9) return event;
    event.consumed = 1; event.sound = 8;
    if (item == 1) {
        event.score_id = 3 + p->bonus_chain * 2;
        if (p->bonus_chain != 4) p->bonus_chain++;
    } else if (item <= 4) {
        p->weapon = item - 2; p->power++;
    } else if (item == 5) {
        event.option_slot = bc_option_collect(w->shots, w->charge.facing, px, py);
    } else if (item <= 8) {
        event.score_id = 28 - item * 2;
    } else {
        p->lives++; p->life_pickups++;
        event.refresh_lives = 1; event.sound = 22;
    }
    return event;
}

/* $A01E-$A0E6: shot-slot order matters. Invulnerable targets still consume
 * ordinary shots, then continue scanning; the first damaging hit ends the
 * scan. Enemy movement, cooldown tick, death/score and player contact are
 * separate tasks. Returning shots and charged beams pierce (source $2D90). */
/* The shared builder emits the native implementation too. Each BC source
 * slot remains a literal displacement, and count is published once at return. */
#if defined(__m68k__)
#define ESI_FUNCTION void __attribute__((optimize("no-reorder-blocks", "no-thread-jumps")))
#else
#define ESI_FUNCTION void
#endif
#define ESI_NAME bc_shot_index
#define ESI_ARGUMENTS (BcShotIndex *index, const BcWeapons *weapons)
#define ESI_PREPARE
#define ESI_AFTER_ROW_INIT
#define ESI_COUNT_TYPE unsigned int
#define ESI_MIN_X index->min_x
#define ESI_MAX_X index->max_x
#define ESI_MIN_Y index->min_y
#define ESI_MAX_Y index->max_y
#define ESI_MIN_INIT 255
#define ESI_MAX_INIT 0
#define ESI_TRACK_HALF_X 1
#define ESI_MAX_HALF_X index->half_x
#define ESI_HALF_X source->body.half_x
#define ESI_TRACK_HALF_Y 1
#define ESI_MAX_HALF_Y index->half_y
#define ESI_HALF_Y source->body.half_y
#define ESI_HAS_ROWS 0
#define ESI_OWNER_INDEX_TYPE unsigned char
#define ESI_OWNER_COUNT 1
#define ESI_OWNER_TYPE const BcWeapons
#define ESI_OWNER_AT(i) weapons
#define ESI_PREPARE_OWNER(p, i)
#define ESI_SCAN_OWNER 1
#define ESI_UNROLL28 1
#define ESI_SOURCE_TYPE const BcShot
#define ESI_SOURCE_AT(p, i) (&(p)->shots[i])
#define ESI_SLOT_TYPE unsigned char
#define ESI_SOURCE_LIVE(s) __builtin_expect(((s)->body.state == 0x80), 1)
#if defined(__m68k__)
#define ESI_SOURCE_ELIGIBLE(s) __builtin_expect(!(((s)->body.flags & 1) | ((const unsigned char *)&(s)->body.x)[0] | ((const unsigned char *)&(s)->body.y)[0]), 1)
#define ESI_PREPARE_X(s) unsigned char x = ((const unsigned char *)&(s)->body.x)[1];
#define ESI_PREPARE_Y(s) unsigned char y = ((const unsigned char *)&(s)->body.y)[1];
#else
#define ESI_SOURCE_ELIGIBLE(s) (!((s)->body.flags & 1) && !bc_beam_index_outside(&(s)->body))
#define ESI_PREPARE_X(s) unsigned char x = bc_beam_x(&(s)->body);
#define ESI_PREPARE_Y(s) unsigned char y = bc_beam_y(&(s)->body);
#endif
#define ESI_BOX_RECORD 0
#define ESI_RECORD_SLOT index->slots[n]
#define ESI_RECORD_X index->x[n]
#define ESI_RECORD_Y index->y[n]
#define ESI_X_MIN x
#define ESI_X_MAX x
#define ESI_Y_MIN y
#define ESI_Y_MAX y
#define ESI_ADVANCE_OUTPUT
#define ESI_PUBLISH_COUNT index->count
#include "enemy_shot_index_impl.h"

/* Compact native index and source-slot fallback are storage policies of the
 * shared query. The native collector and its 91-byte index are unchanged. */
#define ESQ_NAME enemy_shots_indexed
#define ESQ_RESULT BcHitEvent
#define ESQ_ARGUMENTS (BcTarget *e, BcWeapons *w, const BcShotIndex *index, unsigned char near)
#define ESQ_EMPTY {0, 0, 0, 0}
#define ESQ_TARGET_ELIGIBLE (!(e->flags & 1))
#define ESQ_PREPARE unsigned char count = index ? index->count : 28; \
    unsigned short rx = index ? e->half_x + index->half_x : 0; \
    unsigned short ry = index ? e->half_y + index->half_y : 0;
#define ESQ_HAS_CANDIDATES count
#define ESQ_TARGET_BROAD (!index || near || !(e->x > (unsigned short)(index->max_x + rx) || \
    (unsigned short)(e->x + rx) < index->min_x || \
    e->y > (unsigned short)(index->max_y + ry) || \
    (unsigned short)(e->y + ry) < index->min_y))
#define ESQ_ORDER 2
#define ESQ_COUNT_TYPE unsigned char
#define ESQ_COUNT count
#define ESQ_CANDIDATE_BROAD(n) (!index || (bc_unsigned_distance(e->x, index->x[n]) < rx && \
    bc_unsigned_distance(e->y, index->y[n]) < ry))
#define ESQ_SLOT_TYPE unsigned char
#define ESQ_SLOT(n) (index ? index->slots[n] : (n))
#define ESQ_SOURCE_TYPE BcShot
#define ESQ_SOURCE(i) (&w->shots[i])
#define ESQ_SOURCE_LIVE(s) ((s)->body.state == 0x80)
#define ESQ_SOURCE_ELIGIBLE(s) (index || (!((s)->body.flags & 1) && !bc_beam_index_outside(&(s)->body)))
#define ESQ_EXACT(n,s) (bc_unsigned_distance(e->x, index ? index->x[n] : bc_beam_x(&(s)->body)) < \
    (unsigned char)(e->half_x + (s)->body.half_x) && \
    bc_unsigned_distance(e->y, index ? index->y[n] : bc_beam_y(&(s)->body)) < \
    (unsigned char)(e->half_y + (s)->body.half_y))
#define ESQ_OWNER_TYPE unsigned char
#define ESQ_OWNER(i) 0
#define ESQ_CONTACT(r) ((r).contacts++)
#define ESQ_CONSUMES(s) ((s)->kind < 2)
#define ESQ_CONSUME(owner,s) bc_shot_hit(s)
#define ESQ_PROTECTED (e->cooldown || e->damage_lock)
#define ESQ_HP_TYPE unsigned char
#define ESQ_HP e->hp
#define ESQ_DAMAGE_TYPE unsigned char
#define ESQ_DAMAGE(s) ((s)->body.damage)
#define ESQ_DEPLETED(old,damage,now) ((old) <= (damage))
#define ESQ_RECORD_DAMAGE(r,i,dead) do { (r).damaged = 1; (r).depleted = (dead); (r).slot = (i); } while (0)
#define ESQ_DEATH(owner) ((void)0)
#define ESQ_STOP_ON_DAMAGE 1
#include "enemy_shot_query_impl.h"

BcHitEvent bc_enemy_shots_indexed(BcTarget *e, BcWeapons *w, const BcShotIndex *index)
{
    return enemy_shots_indexed(e, w, index, 0);
}

/* Caller has just checked this same target/index rectangle. Live shot tests
 * and ordered consumption remain in the shared implementation. */
BcHitEvent bc_enemy_shots_indexed_near(BcTarget *e, BcWeapons *w, const BcShotIndex *index)
{
    return enemy_shots_indexed(e, w, index, 1);
}

BcHitEvent bc_enemy_shots(BcTarget *e, BcWeapons *w)
{
    return bc_enemy_shots_indexed(e, w, 0);
}

static unsigned char enemy_byte(const BcEnemyData *data, unsigned short address)
{
    return data->bytes[(unsigned short)(address - data->origin)];
}

static inline unsigned short enemy_word(const BcEnemyData *data, unsigned short address)
{
    unsigned short offset = address - data->origin;
#if defined(__m68k__)
    unsigned short value;
    /* Independently wrap both offsets, including a word crossing offset65535.
     * Byte loads also support odd source addresses on the 68000. */
    __asm__("move.b %1,%0\n\tlsl.w #8,%0\n\tmove.b %2,%0"
        : "=&d"(value)
        : "m"(data->bytes[(unsigned short)(offset + 1)]), "m"(data->bytes[offset])
        : "cc");
    return value;
#else
    return data->bytes[offset] | ((unsigned short)data->bytes[(unsigned short)(offset + 1)] << 8);
#endif
}

static unsigned char enemy_retire(BcEnemy *e, unsigned char *limited_count)
{
    if (e->flags & 4) (*limited_count)--;
    e->state = 0;
    return 1;
}

static __attribute__((always_inline)) inline void enemy_move_axis(unsigned int *position,
    signed int velocity)
{
    /* Velocities already use the aligned position scale. */
    unsigned int delta = (unsigned int)velocity;
#if defined(__m68k__)
    __asm__("add.l %1,%0" : "+m"(*position) : "d"(delta) : "cc");
#else
    *position += delta;
#endif
}

static __attribute__((always_inline)) inline unsigned char enemy_integer_high(const unsigned int *position)
{
#if defined(__m68k__)
    return *(const unsigned char *)position;
#else
    return (unsigned char)(*position >> 24);
#endif
}

static inline __attribute__((always_inline)) unsigned char enemy_timer_due(unsigned char *timer)
{
#if defined(__m68k__)
    __asm__ goto ("subq.b #1,%0\n\tbeq %l[expired]"
        : : "m"(*timer) : "cc", "memory" : expired);
    return 0;
expired:
    return 1;
#else
    return !--*timer;
#endif
}

/* $9EB1-$A009. This interprets animation records, not CPU instructions.
 * Boss records retain their composite-frame address as the sprite identifier. */
unsigned char bc_enemy_motion(BcEnemy *e, const BcEnemyData *data, unsigned char *limited_count)
{
    if (enemy_timer_due(&e->timer)) {
        unsigned short pc = e->animation;
        unsigned char duration = enemy_byte(data, pc);
        if (duration == 255) return enemy_retire(e, limited_count);
        if (!duration) {
            pc = enemy_word(data, pc + 1);
            e->animation = pc;
            duration = enemy_byte(data, pc);
        }
        e->timer = duration;
        unsigned char frame = enemy_byte(data, pc + 1);
        if (e->flags & 8) {
            e->sprite = pc;
            e->animation += (unsigned char)((frame << 2) + 2);
        } else {
            e->sprite = frame == 255 ? 255 : e->sprite_base + (frame & 63);
            e->attributes = (e->attributes & 0x77ff) | ((unsigned short)(frame & 128) << 8) |
                            ((unsigned short)(frame & 64) << 5);
            e->animation += 2;
        }
    }
    if (e->state == 0x40) return 2;
    if (e->move_delay) e->move_delay--;
    else {
        /* Stationary axes need neither velocity scaling nor a long add.
         * Moving axes preserve source 24-bit wrap in the aligned container. */
        if (e->motion_vx) enemy_move_axis(&e->x, e->motion_vx);
        if (e->motion_vy) enemy_move_axis(&e->y, e->motion_vy);
    }
    /* Both integer high bytes zero imply the interior 0..255 square.
     * Bitwise OR uses one native branch for this common interior case.
     * Keep the original wrapped bounds for every edge/outside coordinate. */
    if (!(e->flags & 32) && (enemy_integer_high(&e->x) | enemy_integer_high(&e->y)) &&
        ((unsigned short)((bc_enemy_x(e)) + 32) >= 320 ||
         (unsigned short)((bc_enemy_y(e)) + 16) >= 272)) return enemy_retire(e, limited_count);
    return 0;
}

/* $A1DF-$A217. Exhausting a boss bar starts a protected interval; only
 * exhausting the final bar enters its death handler. Score application is a
 * separate task, exposed as an event for the original score-code lookup. */
BcDeathEvent bc_enemy_depleted(BcEnemy *e)
{
    BcDeathEvent event = {0, 0, 0};
    if (e->flags & 8) {
        if (--e->bars) {
            e->damage_lock = e->cooldown = 30;
            e->hp = 10;
            event.sound = 4;
            e->damage_lock--;
            return event;
        }
        e->damage_lock = 100;
    }
    event.award_score = 1; event.score_id = e->score_id;
    e->state = 0x40;
    if (e->damage_lock) e->damage_lock--;
    return event;
}

/* $A0E9-$A1DE. Debug invincibility ($49) is deliberately not a gameplay rule.
 * The two options are checked before killing the player, and absorption starts
 * a 16-update protection interval. An ordinary unprotected enemy dies on contact
 * even when an option absorbs the hit; composite enemies survive the contact. */
unsigned char bc_damage_disabled;

BcPlayerContactEvent bc_enemy_player(BcEnemy *e, unsigned char half_x,
    unsigned char half_y, unsigned char pickup, BcPlayerContact *p)
{
    BcPlayerContactEvent event = {0, 0, 0, 0};
    if (e->state != 0x80 || (e->flags & 2) || p->state != 0x80 || p->invulnerability)
        return event;
    unsigned short x = bc_enemy_x(e);
    unsigned short dx = bc_unsigned_distance(x, p->x);
    if (dx >= (unsigned char)(half_x + 5)) return event;
    unsigned short y = bc_enemy_y(e);
    unsigned short dy = bc_unsigned_distance(y, p->y);
    if (dy >= (unsigned char)(half_y + 8))
        return event;
    if (bc_damage_disabled && !pickup) return event;
    event.contact = 1;
    if (pickup) { event.pickup = pickup; return event; }
    for (unsigned char i = 0; i < 2; i++) {
        if (p->options[i] != 0x80) continue;
        p->options[i] = 0x40;
        p->invulnerability = 16;
        event.option = i + 1;
        event.sound = 12;
        break;
    }
    if (!event.option) { p->state = 0x40; event.sound = 3; }
    if (!e->cooldown && !(e->flags & 8)) e->state = 0x40;
    return event;
}


/* $8A61 and $8B17 (round 1; linked at $884A/$8900 in later rounds).
 * The homing family turns by one direction at a time, rather than snapping
 * its velocity directly toward the target. Terrain is checked before turning. */
unsigned char bc_enemy_bullet_flight(BcEnemy *e, BcBulletFlight *b, unsigned char homing,
    unsigned short px, unsigned short py, unsigned short cx, unsigned short cy,
    const BcTerrain *terrain, const BcEnemyBulletData *data)
{
    b->probe_x = b->probe_y = 0;
    if (bc_terrain_solid(terrain, cx + (bc_enemy_x(e)), cy + (bc_enemy_y(e)))) {
        e->state = 0x40;
        return 1;
    }
    if (homing) bc_enemy_bullet_turn(e, b, px, py, data);
    return 0;
}

unsigned char bc_enemy_bullet_prepare(BcEnemyBullet *b, unsigned char homing,
    unsigned short px, unsigned short py, unsigned short cx, unsigned short cy,
    const BcTerrain *terrain, const BcEnemyBulletData *data)
{
    BcBulletFlight flight = {b->direction, b->speed, b->turn_timer, b->probe_x, b->probe_y};
    unsigned char hit = bc_enemy_bullet_flight(&b->body, &flight, homing,
        px, py, cx, cy, terrain, data);
    b->direction = flight.direction; b->speed = flight.speed;
    b->turn_timer = flight.turn_timer; b->probe_x = flight.probe_x; b->probe_y = flight.probe_y;
    return hit;
}

/* $8A72 / $8E95: first death update stops flight and replaces the animation.
 * Subsequent death updates use only the common animation task. */
unsigned char bc_enemy_bullet_death(BcEnemyBullet *b, unsigned char homing,
                                   const BcEnemyBulletData *data)
{
    bc_enemy_set_vx(&b->body, bc_enemy_set_vy(&b->body, 0));
    b->body.timer = 1;
    b->body.animation = data->death_animation;
    b->body.sprite_base = data->death_sprite_base;
    if (homing) b->body.attributes = 0x0081;
    return homing ? 4 : 0;
}

/* $AD31-$AE28. The crossing test intentionally uses low coordinate bytes, as
 * the source does, while aiming uses the full coordinates. */
void bc_enemy_curve_flight(BcEnemy *body, BcCurveFlight *e, unsigned short px, unsigned short py,
    const BcEnemyData *data, unsigned short speed_table,
    unsigned short approach_animation, unsigned short turn_animation)
{
    if (--e->wait) return;
    unsigned char velocity = 0;
    if (e->phase < 2) {
        unsigned char low = e->phase ? 5 : 6, high = e->phase ? 11 : 10;
        unsigned char aim = bc_aim16(px, py, bc_enemy_x(body), bc_enemy_y(body));
        e->direction = aim < low ? low : aim > high ? high : aim;
        velocity = 1;
        if (!e->phase) {
            body->timer = 1; body->animation = approach_animation;
            e->wait = 40; e->phase = (unsigned char)px >= 144 ? 2 : 1;
        } else { e->wait = 1; e->phase++; }
    } else if (e->phase == 2) {
        unsigned char x = bc_enemy_x(body);
        e->wait = 1;
        if ((unsigned char)px < x && x >= 32) return;
        e->turn = e->direction >= 8 ? 0x55 : 0x44;
        body->timer = 1; body->animation = turn_animation; e->phase++;
    } else if (!e->direction) {
        e->escaping = 1;
    } else {
        e->direction = (e->direction + (e->turn == 0x55 ? 1 : -1)) & 15;
        e->wait = 4; velocity = 1;
    }
    if (velocity) {
        unsigned short vector = enemy_word(data, speed_table + e->speed) + e->direction * 4;
        bc_enemy_set_vx(body, (signed short)enemy_word(data, vector));
        bc_enemy_set_vy(body, (signed short)enemy_word(data, vector + 2));
    }
}

void bc_enemy_curve_prepare(BcCurveEnemy *e, unsigned short px, unsigned short py,
    const BcEnemyData *data, unsigned short speed_table,
    unsigned short approach_animation, unsigned short turn_animation)
{
    BcCurveFlight f = {e->direction, e->speed, e->wait, e->phase,
                       e->turn, e->escaping, e->fired};
    bc_enemy_curve_flight(&e->body, &f, px, py, data, speed_table,
        approach_animation, turn_animation);
    e->direction = f.direction; e->wait = f.wait; e->phase = f.phase;
    e->turn = f.turn; e->escaping = f.escaping;
}

/* $AE2B-$AE51, including $8272's firing gate. A request consumes the one-shot
 * latch even if the separate enemy allocator cannot find a free slot. */
BcEnemyFireEvent bc_enemy_curve_fire(const BcEnemy *body, BcCurveFlight *e, unsigned short px,
    unsigned short py, unsigned char count, unsigned char maximum)
{
    BcEnemyFireEvent event = {0, 0};
    unsigned short x = bc_enemy_x(body), y = bc_enemy_y(body);
    if (e->fired || ((x | y) & 0xff00) || y < 16 || y >= 224 || count >= maximum)
        return event;
    unsigned char distance = (unsigned char)x - (unsigned char)px;
    if (distance < 64 || distance >= 128) return event;
    event.fire = 1; event.direction = bc_aim16(px, py, x, y); e->fired = 1;
    return event;
}

BcEnemyFireEvent bc_enemy_curve_escape(BcCurveEnemy *e, unsigned short px,
    unsigned short py, unsigned char count, unsigned char maximum)
{
    BcCurveFlight f = {e->direction, e->speed, e->wait, e->phase,
                       e->turn, e->escaping, e->fired};
    BcEnemyFireEvent result = bc_enemy_curve_fire(&e->body, &f, px, py, count, maximum);
    e->fired = f.fired;
    return result;
}
