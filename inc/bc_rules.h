#pragma once

/* Practice damage immunity is independent of respawn contact suppression. */
extern unsigned char bc_damage_disabled;

/* Native rules recovered from Side Arms Special's Before Christ program.
 * These are independent of rendering and supply the BC mode's rule policy.
 * PCE input bits: I=1, II=2; direction nibble: U=1, R=2, D=4, L=8. */
typedef struct {
    unsigned char charge;
    unsigned char held_frames;
    unsigned char shoot_latch;
    unsigned char facing;                    /* 0 = left, 1 = right */
} BcCharge;

typedef struct {
    unsigned char beam_segments;             /* 0, 3, 4 or 5 */
    unsigned char sound;                     /* original command: 0, 1 or 0x17 */
} BcChargeEvent;

typedef struct {
    unsigned short x, y;              /* 8.8 screen coordinates */
    signed char dx, dy;
} BcMotion;

typedef struct {
    const unsigned char *cells;        /* 128x128 metatiles, original block order */
    const unsigned char *attributes;   /* 8-byte records, four 16x16 subcells */
} BcTerrain;

void bc_direction(unsigned char direction, unsigned char speed_up, signed char *dx, signed char *dy);
/* $6D41: one original RNG task update; low/high bytes correspond to $6C/$6D. */
unsigned short bc_random_next(unsigned short seed);
BcChargeEvent bc_charge_step(BcCharge *state, unsigned char buttons, unsigned char alive,
                             unsigned char entering, unsigned char beam_busy);
unsigned char bc_terrain_solid(const BcTerrain *terrain, unsigned short x, unsigned short y);
unsigned char bc_move_step(BcMotion *motion, unsigned char direction, unsigned char speed_up,
                           unsigned short camera_x, unsigned short camera_y,
                           unsigned short scroll_dx, unsigned short scroll_dy,
                           const BcTerrain *terrain);

/* Native projectile velocities share the aligned position scale. */
#define BC_BEAM_VELOCITY_SHIFT 8
#if defined(__m68k__)
typedef signed int BcBeamVelocity;
#else
typedef signed short BcBeamVelocity;
#endif
static inline __attribute__((always_inline)) BcBeamVelocity bc_beam_velocity(signed short source)
{
#if defined(__m68k__)
    return (unsigned int)(signed int)source << BC_BEAM_VELOCITY_SHIFT;
#else
    return source;
#endif
}

/* Charged-beam slots, independent of sprite layout. Source positions are
 * unsigned 24-bit (16.8); native storage rotates the full container below. */
typedef struct {
    unsigned int x, y;
    BcBeamVelocity vx, vy;
    unsigned short sprite, attributes;
    unsigned char state, timer, flags, damage, half_x, half_y;
    unsigned char delay, accelerating, facing;
} BcBeam;

/* Native position storage rotates the full source word left eight bits.
 * Pixel words are aligned; fraction and old padding remain independently
 * recoverable. Host source-reference fixtures retain their original layout. */
#define BC_BEAM_STORAGE_ROTATE 8
#if defined(__m68k__) || defined(BC_TEST_ALIGNED_BEAMS)
#define BC_BEAM_ALIGNED 1
#else
#define BC_BEAM_ALIGNED 0
#endif
static inline __attribute__((always_inline)) unsigned short bc_beam_x(const BcBeam *b)
{
#if defined(__m68k__)
    typedef unsigned short __attribute__((may_alias)) BeamPixelWord;
    return *(const BeamPixelWord *)&b->x;
#elif BC_BEAM_ALIGNED
    return b->x >> 16;
#else
    return b->x >> 8;
#endif
}
static inline __attribute__((always_inline)) unsigned short bc_beam_y(const BcBeam *b)
{
#if defined(__m68k__)
    typedef unsigned short __attribute__((may_alias)) BeamPixelWord;
    return *(const BeamPixelWord *)&b->y;
#elif BC_BEAM_ALIGNED
    return b->y >> 16;
#else
    return b->y >> 8;
#endif
}
static inline __attribute__((always_inline)) void bc_beam_set_x(BcBeam *b, unsigned short pixels)
{
#if BC_BEAM_ALIGNED
    b->x = ((unsigned int)pixels << 16) | (b->x & 0xff00);
#else
    b->x = ((unsigned int)pixels << 8) | (b->x & 255);
#endif
}
static inline __attribute__((always_inline)) void bc_beam_set_y(BcBeam *b, unsigned short pixels)
{
#if BC_BEAM_ALIGNED
    b->y = ((unsigned int)pixels << 16) | (b->y & 0xff00);
#else
    b->y = ((unsigned int)pixels << 8) | (b->y & 255);
#endif
}
static inline __attribute__((always_inline)) void bc_beam_low_x(BcBeam *b, unsigned char pixel)
{
#if BC_BEAM_ALIGNED
    b->x = (b->x & 0xff00ff00u) | ((unsigned int)pixel << 16);
#else
    b->x = (b->x & 0xff00ff) | ((unsigned int)pixel << 8);
#endif
}
/* Source packing compares the entire shifted value, including old padding. */
static inline __attribute__((always_inline)) unsigned char bc_beam_same_y(const BcBeam *a, const BcBeam *b)
{
#if BC_BEAM_ALIGNED
    return !((a->y ^ b->y) & 0xffff00ffu);
#else
    return (a->y >> 8) == (b->y >> 8);
#endif
}
static inline __attribute__((always_inline)) unsigned char bc_beam_index_outside(const BcBeam *b)
{
#if BC_BEAM_ALIGNED
    return ((b->x | b->y) & 0xff000000u) != 0;
#else
    return ((b->x | b->y) & 0xff0000) != 0;
#endif
}


void bc_beam_launch(BcBeam slots[5], unsigned char segments, unsigned char facing,
                    unsigned short player_x, unsigned short player_y);
void bc_beam_step(BcBeam *beam);

/* The two spread weapons share the original 28-slot allocation search.
 * kind 0 is the straightening spread; kind 1 is the expanding spread. */
typedef struct {
    BcBeam body;
    unsigned char kind, tier, phase, animation, launch_wait;
} BcShot;
unsigned char bc_shot_fire(BcShot slots[28], unsigned char kind, unsigned char power,
                           unsigned char facing, unsigned short player_x,
                           unsigned short player_y);
void bc_shot_impact(BcShot *shot);
void bc_shot_hit(BcShot *shot); /* enemy collision after this frame's shot update */
void bc_shot_step(BcShot *shot, unsigned short camera_x, unsigned short camera_y,
                   const BcTerrain *terrain);

/* Returning weapon (ID 2). Its active counter is distinct from pool occupancy. */
typedef BcShot BcReturn;
unsigned char bc_return_fire(BcReturn slots[28], unsigned char power, unsigned char facing,
                             unsigned short player_x, unsigned short player_y,
                             unsigned char *active);
void bc_return_step(BcReturn *shot, unsigned short player_x, unsigned short player_y,
                     unsigned char *active);
/* Option bodies occupy slots 28/29 (kind 4). Returns slot+1, or zero when both
 * are full. tier stores remaining HP; launch_wait stores upper/lower side. */
unsigned char bc_option_collect(BcShot slots[30], unsigned char facing,
                                 unsigned short player_x, unsigned short player_y);
void bc_option_step(BcShot *option, unsigned char facing, unsigned char history_x,
                     unsigned char history_y, unsigned short player_y);
unsigned char bc_aim16(unsigned short target_x, unsigned short target_y,
                       unsigned short source_x, unsigned short source_y);


/* One pool per player, shared by main shots, option shots, beams and options. */
typedef struct {
    BcShot shots[30];
    BcCharge charge;
    unsigned char returning;
    unsigned char option_shots[2], trail[16]; /* newest coordinate pair first */
} BcWeapons;
typedef struct {
    unsigned char shots, beam_segments, shot_sound, charge_sound, recoil, option_shots;
} BcWeaponEvent;
BcWeaponEvent bc_weapons_step(BcWeapons *weapons, unsigned char held,
    unsigned char pressed, unsigned char alive, unsigned char entering,
    unsigned char kind, unsigned char power, unsigned short player_x,
    unsigned short player_y, unsigned short camera_x, unsigned short camera_y,
    const BcTerrain *terrain);
/* Direct output for the integrated player task. */
void bc_weapons_step_into(BcWeaponEvent *event, BcWeapons *w, unsigned char held,
    unsigned char pressed, unsigned char alive, unsigned char entering,
    unsigned char kind, unsigned char power, unsigned short px,
    unsigned short py, unsigned short cx, unsigned short cy,
    const BcTerrain *terrain);
/* The source records its trail in the enemy task, after all enemy updates. */
void bc_weapons_record_position(BcWeapons *weapons, unsigned short player_x,
                                 unsigned short player_y);

typedef struct {
    unsigned char weapon, power, bonus_chain, lives, life_pickups;
} BcInventory;
typedef struct {
    unsigned char consumed, score_id, sound, option_slot, refresh_lives;
} BcPickupEvent;
/* Original item IDs 1..9. Score IDs are commands to the separate score task. */
BcPickupEvent bc_pickup_apply(BcInventory *inventory, BcWeapons *weapons,
    unsigned char item, unsigned short player_x, unsigned short player_y);

/* Enemy fields used by the projectile scan, after movement and cooldown tick. */
typedef struct {
    unsigned short x, y;
    unsigned char half_x, half_y, flags, hp, cooldown, damage_lock;
} BcTarget;
typedef struct {
    unsigned char contacts, damaged, depleted, slot; /* slot = 0..27 when damaged */
} BcHitEvent;
BcHitEvent bc_enemy_shots(BcTarget *target, BcWeapons *weapons);
/* Temporary collision index, valid while projectile positions do not change.
 * Source slot order is retained; hits still recheck live state. */
typedef struct {
    unsigned char slots[28], count;
    /* Eligibility rejects nonzero coordinate high bytes; cached pixels fit
     * exactly in one byte. Keep full-width target math in collision tests. */
    unsigned char x[28], y[28];
    unsigned char min_x, max_x, min_y, max_y, half_x, half_y;
} BcShotIndex;
void bc_shot_index(BcShotIndex *index, const BcWeapons *weapons);
BcHitEvent bc_enemy_shots_indexed(BcTarget *target, BcWeapons *weapons,
    const BcShotIndex *index);
/* Requires the same target/index bounds to have passed immediately before calling. */
BcHitEvent bc_enemy_shots_indexed_near(BcTarget *target, BcWeapons *weapons,
                                     const BcShotIndex *index);

#define BC_ENEMY_STORAGE_SHIFT 8
#define BC_ENEMY_VELOCITY_SHIFT 8

/* Common enemy animation/motion state; family-specific AI runs before this.
 * Positions store the unsigned 24-bit (16.8) source value shifted left eight
 * bits. Integer pixels are word-aligned; the low byte always stays zero. */
typedef struct {
    unsigned int x, y;
    signed int motion_vx, motion_vy; /* signed16 source velocity multiplied by256 */
    unsigned short sprite, attributes, animation, sprite_base;
    unsigned char state, timer, flags, move_delay;
    unsigned char hp, bars, cooldown, damage_lock, score_id;
} BcEnemy;

/* The stored low byte is zero; extracting bits8..23 recovers signed16
 * without signed-division rounding code. */
static inline __attribute__((always_inline)) signed short bc_enemy_vx(const BcEnemy *enemy)
{
    return (signed short)((unsigned int)enemy->motion_vx >> 8);
}
static inline __attribute__((always_inline)) signed short bc_enemy_set_vx(BcEnemy *enemy, signed int value)
{
    signed short source = (signed short)value;
    enemy->motion_vx = (signed int)source * 256;
    return source;
}

static inline __attribute__((always_inline)) signed short bc_enemy_vy(const BcEnemy *enemy)
{
    return (signed short)((unsigned int)enemy->motion_vy >> 8);
}
static inline __attribute__((always_inline)) signed short bc_enemy_set_vy(BcEnemy *enemy, signed int value)
{
    signed short source = (signed short)value;
    enemy->motion_vy = (signed int)source * 256;
    return source;
}

/* Keep actor pixel reads distinct from player/weapon coordinate formats.
 * Preserve the unsigned expression type and current storage representation. */
static inline __attribute__((always_inline)) unsigned int bc_enemy_x(const BcEnemy *enemy)
{
#if defined(__m68k__)
    typedef unsigned short __attribute__((may_alias)) CoordinateWord;
    return *(const CoordinateWord *)&enemy->x;
#else
    return enemy->x >> 16;
#endif
}
static inline __attribute__((always_inline)) unsigned int bc_enemy_y(const BcEnemy *enemy)
{
#if defined(__m68k__)
    typedef unsigned short __attribute__((may_alias)) CoordinateWord;
    return *(const CoordinateWord *)&enemy->y;
#else
    return enemy->y >> 16;
#endif
}

/* Source births replace integer pixels but retain the reused slot fraction. */
static inline __attribute__((always_inline)) void bc_enemy_set_x(BcEnemy *enemy, unsigned int pixels)
{
    enemy->x = (pixels << 16) | (enemy->x & 0xff00);
}
static inline __attribute__((always_inline)) void bc_enemy_copy_x(BcEnemy *enemy, const BcEnemy *source)
{
    enemy->x = (source->x & 0xffff0000u) | (enemy->x & 0xff00);
}
static inline __attribute__((always_inline)) void bc_enemy_low_x(BcEnemy *enemy, unsigned char pixel_byte)
{
    enemy->x = (enemy->x & 0xff00ff00u) | ((unsigned int)pixel_byte << 16);
}
static inline __attribute__((always_inline)) void bc_enemy_set_y(BcEnemy *enemy, unsigned int pixels)
{
    enemy->y = (pixels << 16) | (enemy->y & 0xff00);
}
static inline __attribute__((always_inline)) void bc_enemy_copy_y(BcEnemy *enemy, const BcEnemy *source)
{
    enemy->y = (source->y & 0xffff0000u) | (enemy->y & 0xff00);
}
static inline __attribute__((always_inline)) void bc_enemy_low_y(BcEnemy *enemy, unsigned char pixel_byte)
{
    enemy->y = (enemy->y & 0xff00ff00u) | ((unsigned int)pixel_byte << 16);
}

typedef struct { const unsigned char *bytes; unsigned short origin; } BcEnemyData;
/* 0 = collision phase follows, 1 = retired, 2 = death animation (no motion). */
unsigned char bc_enemy_motion(BcEnemy *enemy, const BcEnemyData *data,
                               unsigned char *limited_count);
typedef struct { unsigned char award_score, score_id, sound; } BcDeathEvent;
BcDeathEvent bc_enemy_depleted(BcEnemy *enemy);

/* Enemy/player contact, before the shared damage-lock countdown. Option slots
 * absorb one contact each, in slot order. Pickup application is a separate task. */
typedef struct {
    unsigned short x, y;
    unsigned char state, invulnerability, options[2];
} BcPlayerContact;
typedef struct {
    unsigned char contact, pickup, option, sound; /* option: 1 or 2 when consumed */
} BcPlayerContactEvent;
BcPlayerContactEvent bc_enemy_player(BcEnemy *enemy, unsigned char half_x,
    unsigned char half_y, unsigned char pickup, BcPlayerContact *player);

/* Enemy shot families: straight flight and five-update homing turns. */
typedef struct {
    BcEnemy body;
    unsigned char direction, speed, turn_timer, probe_x, probe_y;
} BcEnemyBullet;
typedef struct {
    BcEnemyData data;
    unsigned short speed_table, direction_animations, death_animation, death_sprite_base;
} BcEnemyBulletData;
/* Flight state can be adapted without copying the enemy's full body. */
typedef struct {
    unsigned char direction, speed, turn_timer, probe_x, probe_y;
} BcBulletFlight;
unsigned char bc_enemy_bullet_flight(BcEnemy *enemy, BcBulletFlight *flight,
    unsigned char homing, unsigned short player_x, unsigned short player_y,
    unsigned short camera_x, unsigned short camera_y,
    const BcTerrain *terrain, const BcEnemyBulletData *data);
/* Runs before bc_enemy_motion; 1 means terrain scheduled the death handler. */
unsigned char bc_enemy_bullet_prepare(BcEnemyBullet *bullet, unsigned char homing,
    unsigned short player_x, unsigned short player_y, unsigned short camera_x,
    unsigned short camera_y, const BcTerrain *terrain, const BcEnemyBulletData *data);
/* Returns a sound command (zero for the silent straight-shot impact). */
unsigned char bc_enemy_bullet_death(BcEnemyBullet *bullet, unsigned char homing,
                                   const BcEnemyBulletData *data);

/* Round-1 turning attacker ($AD31): staged approach, tracking and exit turn.
 * escaping requests the separate $AE2B escape/fire handler on future updates. */
typedef struct {
    BcEnemy body;
    unsigned char direction, speed, wait, phase, turn, escaping, fired;
} BcCurveEnemy;
/* Steering adapter excludes the body; native actors update it in place. */
typedef struct {
    unsigned char direction, speed, wait, phase, turn, escaping, fired;
} BcCurveFlight;
void bc_enemy_curve_flight(BcEnemy *body, BcCurveFlight *flight,
    unsigned short player_x, unsigned short player_y, const BcEnemyData *data,
    unsigned short speed_table, unsigned short approach_animation,
    unsigned short turn_animation);
void bc_enemy_curve_prepare(BcCurveEnemy *enemy, unsigned short player_x,
    unsigned short player_y, const BcEnemyData *data, unsigned short speed_table,
    unsigned short approach_animation, unsigned short turn_animation);
typedef struct { unsigned char fire, direction; } BcEnemyFireEvent;
BcEnemyFireEvent bc_enemy_curve_fire(const BcEnemy *body, BcCurveFlight *flight,
    unsigned short player_x, unsigned short player_y,
    unsigned char limited_count, unsigned char limited_max);
BcEnemyFireEvent bc_enemy_curve_escape(BcCurveEnemy *enemy, unsigned short player_x,
    unsigned short player_y, unsigned char limited_count, unsigned char limited_max);

/* Unsigned distance uses the subtract carry, including coordinates on opposite
 * sides of0x8000. A signed absolute value would lose those far distances. */
static inline __attribute__((always_inline)) unsigned short bc_unsigned_distance(unsigned short x, unsigned short y)
{
#if defined(__m68k__)
    __asm__("sub.w %1,%0\n\tbcc.s 1f\n\tneg.w %0\n1:" : "+d"(x) : "d"(y) : "cc");
    return x;
#else
    return x >= y ? x - y : y - x;
#endif
}
