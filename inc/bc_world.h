#pragma once
#include "bc_rules.h"

#define BC_ACTOR_CAPACITY 32

/* Shared enemy slots. Routine values identify translated source handlers;
 * they are identifiers, never executable HuC6280 code in the Genesis build. */
typedef struct {
    BcEnemy body;
    unsigned short routine, death_routine, sprite_base_ref;
    unsigned char half_x, half_y, pickup, speed, auxiliary;
    unsigned char direction, wait, phase, turn, fired, probe_x, probe_y, dash_started;
    unsigned char health_fraction; /* co-op boss damage remainder; occupies padding */
} BcActor;

/* First free slot in source scan order, or -1 when full. Does not reserve it. */
signed short bc_actor_allocate(const BcActor actors[BC_ACTOR_CAPACITY], unsigned char reverse);
/* Apply the source's 19-byte enemy template. sprite_base is resolved from its
 * RAM/ROM reference by the stage loader. Reused fields are deliberately retained. */
void bc_actor_template(BcActor *actor, const unsigned char record[19], unsigned short sprite_base);
/* $8A29-$8A57. Returns before the immediate common update and subsequent
 * limited-shot counter increment, which the world task must perform in order. */
signed short bc_actor_spawn_bullet(BcActor actors[BC_ACTOR_CAPACITY], unsigned char parent,
    unsigned char direction, const BcEnemyData *data, unsigned short template_address,
    unsigned short sprite_base, unsigned short speed_table);

typedef struct BcParty BcParty;
typedef struct {
    unsigned int x, y; /* 16.8 player coordinates */
    BcWeapons weapons;
    BcInventory inventory;
    unsigned char state, invulnerability;
    const BcShotIndex *shot_index; /* temporary enemy-loop cache; NULL outside */
    BcParty *party; /* NULL for 1P; otherwise a validated 2–4-member context */
} BcWorldPlayer;
/* Round-three stop-and-reaim enemy; caller performs the immediate common task. */
signed short bc_actor_spawn_reaim(BcActor actors[BC_ACTOR_CAPACITY], unsigned char position,
    const BcWorldPlayer *player, const BcEnemyData *data, unsigned short sprite_base);
typedef struct {
    unsigned char retired, score_pending, score_id, sound;
    unsigned char refresh_lives, pickup, option_absorbed, player_died;
} BcActorEvent;
#define BC_PARTY_CAPACITY 4
typedef void (*BcPartyContactSink)(unsigned char player, const BcActorEvent *event, void *context);
struct BcParty {
    BcWorldPlayer *players[BC_PARTY_CAPACITY];
    unsigned char count;
    /* Actor-pass cache: 0 uncached, 1 no living players, 2 all living players
     * protected, 3 at least one vulnerable, 4 protected with no indexed shots.
     * Invalidated on player death; discarded after each actor pass. */
    unsigned char contact_policy;
    /* Nonempty contact events, including immediate child updates, in order.
     * The sink must not move actors/shots or change collision state. */
    BcPartyContactSink contact;
    void *context;
    /* Conservative union of living players' indexed shots, valid only within
     * the actor pass. Stale consumed shots may widen it but cannot hide hits.
     * 0 means uncached, 1 a nonempty union, 2 all living shot indices empty. */
    unsigned char shot_bounds_valid;
    unsigned char shot_min_x, shot_max_x, shot_min_y, shot_max_y, shot_half_x, shot_half_y;
    /* Vulnerable bodies only, valid within an actor pass while policy is 3.
     * Death invalidates the policy; newly protected bodies may safely leave
     * this union wider until the next pass. Integer coordinates are 16-bit. */
    unsigned char body_bounds_valid;
    unsigned short body_min_x, body_max_x, body_min_y, body_max_y;
};
/* Original single-player common task ($9EB1-$A217), after family AI.
 * Emits score/audio/HUD commands for the world scheduler to consume. */
/* Caller-owned event avoids returning/copying a structure for each actor. */
/* Round-three reaim AI plus common task, after the caller applies scrolling. */
void bc_actor_reaim_common(BcActorEvent *event, BcActor *actor, BcWorldPlayer *player,
    const BcEnemyData *data, unsigned char *limited_count);
void bc_actor_common_into(BcActorEvent *event, BcActor *actor, BcWorldPlayer *player,
    const BcEnemyData *data, unsigned char *limited_count);
BcActorEvent bc_actor_common(BcActor *actor, BcWorldPlayer *player,
    const BcEnemyData *data, unsigned char *limited_count);

/* Co-op common task: motion, animation and protection timers advance once.
 * Contacts run in player-slot order. Each slot owns its score/pickup/audio
 * event; null or inactive players do not collide. Stop when the actor retires,
 * dies or exhausts a boss bar. Retirement from motion is reported in event[0].
 * player_count must be 1..4. AI targeting remains the caller's responsibility. */
void bc_actor_party_common_into(BcActorEvent events[BC_PARTY_CAPACITY],
    BcActor *actor, BcWorldPlayer *const players[BC_PARTY_CAPACITY],
    unsigned char player_count, const BcEnemyData *data, unsigned char *limited_count);

/* Round-1 $AA50/$ACF3 turning-attacker births. Template $ABB1 starts at
 * -2.5 pixels/update; $AE54 starts at -2. Caller selects one of five Y lanes
 * and runs the immediate common update on success. */
signed short bc_actor_spawn_curve(BcActor actors[BC_ACTOR_CAPACITY], unsigned char y,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base);

typedef struct {
    BcActorEvent child_event;
    signed short child_slot;
    unsigned char fire_requested;
} BcCurveActorEvent;
/* Round-1 living actor AI, ending before its own common update. A spawned
 * bullet receives its immediate common update before the limited count rises. */
BcCurveActorEvent bc_actor_curve_prepare(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *player, const BcEnemyData *data, unsigned char *limited_count,
    unsigned char limited_max, unsigned short bullet_sprite_base);

/* Shared explosion setup ($8E95/$8EB5/$8EC1). kind: 0 small, 1 large,
 * 2 alternate large palette. Returns sound command 4; common update follows. */
unsigned char bc_actor_explosion(BcActor *actor, unsigned char kind,
    unsigned short sprite_base, unsigned short animation);

/* $9E82-$9E8F/$81C6-$8208: before family dispatch, offset world-relative
 * actors by signed 8.8 scroll, preserving 24-bit wrap and stage-stop gating. */
void bc_actor_scroll(BcActor *actor, signed short dx, signed short dy, unsigned char stopped);

typedef struct {
    BcEnemyData data;
    unsigned short bullet_base, small_explosion_base, large_explosion_base;
    signed short relocation;
    unsigned char round;
    BcTerrain terrain;
    unsigned short camera_x, camera_y, bullet_death_base;
    unsigned short *random_state;
    unsigned short homing_inherited_base;
    unsigned char boss_active;
    unsigned short boss_spread_base, homing_base;
    unsigned char scheduler_counter;
    unsigned short boss_beam_base;
} BcActorStepData;
/* Bind immutable round tables; rebind after changing round/data/relocation. NULL disables. */
void bc_actor_bind_segments(const BcActorStepData *data);
/* Live R3/R9 boss-three homing shot only; caller applies scrolling first. */
void bc_actor_boss3_homing_common(BcActorEvent *event, BcActor *actor,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *limited_count);
/* Immediate terrain/common update after the round-two/four walker template. */
void bc_actor_walker_birth(BcActorEvent *result, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *player, const BcActorStepData *data,
    unsigned char *limited_count, unsigned char limited_max);

typedef struct {
    BcActorEvent actor_event, child_event;
    signed short child_slot;
    unsigned char setup_sound, fire_requested, handled;
    /* Only [0, extra_count) child entries are initialized. */
    unsigned char extra_count;
    signed short extra_slots[10];
    BcActorEvent extra_events[10];
    unsigned char boss_defeat; /* 1 ordinary explosion sequence, 2 final ending */
    unsigned short boss_center_y;
} BcActorStepEvent;
/* Full update for translated handlers. Unsupported handlers return handled=0
 * without mutating state; the scheduler must not silently skip them. */
/* Caller-owned output avoids copying the ten-child event buffer per actor.
 * Only entries below extra_count are initialized, as in bc_actor_step. */
/* Internal actor-loop helper: requires handled=1 and otherwise empty envelope. */
void bc_actor_curve_common_into(BcActorStepEvent *event, BcActor *actor,
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *limited_count, unsigned char maximum);
void bc_actor_segment_common_into(BcActorStepEvent *event, BcActor *actor,
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *limited_count, unsigned char maximum);

void bc_actor_turret_common_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *player, const BcActorStepData *data,
    unsigned char *limited_count, unsigned char maximum);

/* Requires the caller's empty, handled event envelope and completed scroll. */
void bc_actor_diver_common_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *player, const BcActorStepData *data,
    unsigned char *limited_count, unsigned char maximum);

void bc_actor_walker_common_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *player, const BcActorStepData *data,
    unsigned char *limited_count, unsigned char maximum, unsigned short handler);

void bc_actor_step_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *limited_count,
    unsigned char limited_max, signed short scroll_dx, signed short scroll_dy,
    unsigned char stopped);
BcActorStepEvent bc_actor_step(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *limited_count,
    unsigned char limited_max, signed short scroll_dx, signed short scroll_dy,
    unsigned char stopped);


/* Round-1 $ABF1-$AC26: hovering shooter birth, before common update. */
signed short bc_actor_spawn_hover(BcActor actors[BC_ACTOR_CAPACITY], unsigned char y,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base);

/* Round-1 $B25A-$B28C: stationary launcher birth, before common update. */
signed short bc_actor_spawn_launcher(BcActor actors[BC_ACTOR_CAPACITY], unsigned char x,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base);

/* Round-1 $B0DA-$B11C: hopper birth from either X lane, before common update. */
signed short bc_actor_spawn_hopper(BcActor actors[BC_ACTOR_CAPACITY], unsigned char x,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base);

/* Round-1 stage-event birth dispatch. sprite_base resolves the selected
 * template's graphics reference. Returns slot, -1 full, or -2 unsupported.
 * The caller runs the immediate common update before advancing the script. */
signed short bc_actor_stage_birth(BcActor actors[BC_ACTOR_CAPACITY], unsigned short handler,
    const BcEnemyData *data, unsigned short sprite_base);

/* Round-1 $AE9A-$AED0: terrain jumper birth, before common update. */
signed short bc_actor_spawn_jumper(BcActor actors[BC_ACTOR_CAPACITY], unsigned char y,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base);

/* $888C-$88C8: stage item capsule, reverse allocation and table coordinates. */
signed short bc_actor_spawn_item(BcActor actors[BC_ACTOR_CAPACITY], unsigned char item,
    unsigned char position, const BcEnemyData *data, unsigned short template_address,
    unsigned short positions, unsigned short sprite_base);

/* $8DE3-$8E59: allocate one boss-defeat explosion before its common update.
 * Failed allocation leaves RNG untouched; success consumes two RNG values. */
signed short bc_actor_spawn_boss_effect(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned short center_y, const BcEnemyData *data, signed short relocation,
    unsigned short sprite_base, unsigned short *random_state);

/* Live round-ten serpent AI after scrolling. Caller supplies an empty event
 * envelope. Only fire_requested, extra_count and indexed extra events change. */
void bc_actor_final_serpent_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *player, const BcActorStepData *data,
    unsigned char *limited_count, BcActorStepEvent *event);

/* Live canonical $8A61, after source scrolling. Overwrites every event field. */
void bc_actor_straight_common_into(BcActorEvent *event, BcActor *actor,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *limited_count);

/* The caller guarantees solid is an exact 256x256 row-major subcell map. */
void bc_actor_straight_map_into(BcActorEvent *event, BcActor *actor,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *count,
    const unsigned char *solid);

/* Live canonical $8B17 after scrolling; preserves terrain-before-turn order. */
void bc_actor_homing_common_into(BcActorEvent *event, BcActor *actor,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *count);

/* Homing counterpart of the validated row-major terrain helper. */
void bc_actor_homing_map_into(BcActorEvent *event, BcActor *actor,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *count,
    const unsigned char *solid);
