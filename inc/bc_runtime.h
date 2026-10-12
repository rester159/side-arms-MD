#pragma once
#include "bc_stage.h"
#include "bc_world.h"
#include "bc_score.h"
#include "bc_player.h"
#include "bc_palette.h"
#include "bc_audio.h"

typedef struct {
    BcEnemyData data;
    unsigned short hover_base, curve_base, hopper_base, launcher_base;
    signed short relocation;
    unsigned char round;
    unsigned short jumper_base, item_base;
    BcScore *score;
    unsigned char playing;
    unsigned short fast_curve_base, boss_base;
    BcPalette *palette;
    BcAudioRequest *audio;
    /* Immediate birth effects, in actor order; score is already enqueued. */
    void (*birth_sink)(unsigned char slot, const BcActorEvent *event, void *context);
    void *birth_context;
    unsigned short ceiling_base;
    unsigned short segment_bases[6]; /* $369E..$36A8 */
    unsigned short *random_state; /* shared RNG for grouped stage births */
    unsigned short fixed_turret_base;
    unsigned short walker_base;
    unsigned short orbiter_base, terrain_jumper_base, terrain_hopper_base;
    unsigned short turret_bases[3]; /* burst, spread, terrain-impact shot */
    /* Resolve scene resources before the event executes its immediate births. */
    void (*prepare_event)(unsigned short handler);
} BcStageEventData;
typedef struct {
    /* Legacy single/two-actor diagnostics. Group births use birth_sink. */
    BcActorEvent actor_event;
    unsigned short handler;
    signed short slot;
    unsigned char status; /* 0 no event, 1 completed, 2 unsupported, 3 awaiting audio */
    BcActorEvent second_actor_event;
    /* Ordinary formation size: 1,2,4,5,8. Zero for bosses,
     * pickups, controls and audio waits. slot < 0 means allocation failed. */
    unsigned char wave_size;
} BcStageEventResult;
/* Execute one due script event, including immediate birth update and pointer
 * advancement. Repeat completed events within the same frame. An unsupported
 * event retains its script pointer and all simulation state for the caller. */
BcStageEventResult bc_runtime_stage_event(BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player,
    const BcStageEventData *data, unsigned char *limited_count);

/* Repeat a previously classified ordinary wave at the current camera.
 * Its script address must come from a successful wave_size > 0 source event.
 * Stage state/pointer is copied; immediate actor effects remain real. */
BcStageEventResult bc_runtime_stage_replay(const BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player,
    const BcStageEventData *data, unsigned char *limited_count, unsigned short script);

typedef void (*BcActorEventSink)(unsigned char slot, const BcActorStepEvent *event, void *context);
/* Process slots in original ascending order, including children born into
 * later slots. Returns 32 when complete or the first unsupported slot. Resume
 * from that slot only after its missing handler has been implemented. The
 * event sink must not create/move main shots or change their collision flags:
 * projectile candidates/positions are cached for the duration of this loop.
 * Sinks also must not change player life state or invulnerability; the party
 * contact classification is cached until a native collision invalidates it. */
unsigned char bc_runtime_actor_loop(BcActor actors[BC_ACTOR_CAPACITY], unsigned char first,
    BcWorldPlayer *player, const BcActorStepData *data, unsigned char *limited_count,
    unsigned char limited_max, signed short scroll_dx, signed short scroll_dy,
    unsigned char stopped, BcActorEventSink sink, void *context);

typedef struct {
    unsigned short center_y;
    unsigned char remaining, wait;
} BcDefeatSequence;

/* Sink for ordered score insertion, optionally forwarding the same event to
 * audio/HUD consumers. Child score commands precede the parent's command. */
typedef struct {
    BcScore *score;
    unsigned char playing;
    /* Opt in only when next consumes score/audio/boss effects, not per-actor
     * observations. Zero retains delivery of every completed actor update. */
    unsigned char effects_only;
    BcActorEventSink next;
    void *context;
    BcDefeatSequence *defeat;
} BcRuntimeEvents;
void bc_runtime_actor_events(unsigned char slot, const BcActorStepEvent *event, void *context);

typedef struct {
    BcPlayerFrameEvent player_event;
    unsigned char status; /* 0 complete, 1 checkpoint, 2 unsupported actor */
    unsigned char next_slot;
} BcPlayResult;
/* Source $7407 through $9E69. Stage events/scroll and score consumption are
 * separate tasks; this combines player, weapons, enemy loop and option trail.
 * Updates data->boss_active to the countdown used by the enemy loop. */
BcPlayResult bc_runtime_play(BcPlayerControl *player, BcActor actors[BC_ACTOR_CAPACITY],
    BcStage *stage, BcActorStepData *data, unsigned short pose_table,
    unsigned char held, unsigned char pressed, unsigned char *limited_count,
    BcRuntimeEvents *events);

typedef struct {
    BcPlayResult play;
    unsigned short handler, stage_events;
    /* 0 complete, 1 checkpoint, 2 unsupported actor, 3 unsupported stage,
     * 4 awaiting audio, 5 malformed/nonterminating stage script. */
    unsigned char status;
} BcFrameResult;
typedef struct {
    unsigned short stage_events;
    unsigned char scrolling;
} BcFrameCursor;
/* Main gameplay task: due stage events, camera movement, then player/actors.
 * Score/RNG task, boss-defeat task, pause and checkpoint loading belong to
 * the caller. Audio waits retain the event pointer and do not scroll or play.
 * Actor data is updated in place with this frame's camera, terrain table and
 * boss countdown. Keep a separate context for each running game/session.
 * Zero the cursor on stage load; retain it across audio waits. The caller
 * must keep the loaded code/map and supplied resources alive. */
BcFrameResult bc_runtime_frame(BcFrameCursor *cursor, BcPlayerControl *player,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcStageEventData *stage_data, BcActorStepData *actor_data,
    unsigned short pose_table, unsigned char held, unsigned char pressed,
    unsigned char *limited_count, BcRuntimeEvents *events);

/* Task 2's first phase: fifty effects, one every three unpaused scheduler
 * ticks. Completion is handed back to the stage/music transition owner. */
void bc_runtime_defeat_begin(BcDefeatSequence *sequence, unsigned short center_y);
/* Returns 1 when an explosion is due, 2 for the fiftieth/final explosion.
 * Allocation must be attempted for either result, even when the pool is full. */
unsigned char bc_runtime_defeat_tick(BcDefeatSequence *sequence, unsigned char paused);

typedef struct {
    BcActorEvent actor_event;
    signed short slot;
    unsigned char completion; /* 0 running/idle, 1 resumed scrolling, 2 transition required */
} BcDefeatTaskResult;
/* Run once per scheduler tick after the tick on which defeat was requested. */
BcDefeatTaskResult bc_runtime_defeat_step(BcDefeatSequence *sequence, BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player, const BcEnemyData *data,
    signed short relocation, unsigned short sprite_base, unsigned short *random_state,
    unsigned char *limited_count, unsigned char paused, BcRuntimeEvents *events);

/* Gameplay state rebuilt by the checkpoint loader. Life decrement, game-over,
 * display/audio loading and scheduling remain the scene owner's responsibility. */
void bc_runtime_checkpoint_reset(BcFrameCursor *cursor, BcPlayerControl *player,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcEnemyData *data, unsigned char round, unsigned short player_template,
    const unsigned char header[8], unsigned char *limited_count);
