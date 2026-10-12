#pragma once
#include "bc_runtime.h"
#include "bc_wave.h"

/* Shared stage/actors, independent robots/weapons. The owner handles lives,
 * respawns and score presentation. Clear a waiting bit after resetting that
 * player; otherwise its checkpoint request stays latched without repeating. */
typedef struct {
    BcParty contacts;
    BcPlayerControl *players[BC_PARTY_CAPACITY];
    unsigned char waiting;
    BcWaveQueue waves;
} BcPartyControl;
typedef struct {
    BcPlayerFrameEvent players[BC_PARTY_CAPACITY];
    unsigned short handler, stage_events;
    unsigned char status, next_slot, checkpoints;
} BcPartyFrameResult;
/* Bind distinct, non-null player objects. Returns zero without changes for
 * invalid input. One player retains the original single-player contact path. */
unsigned char bc_party_bind(BcPartyControl *party,
    BcPlayerControl *const players[BC_PARTY_CAPACITY], unsigned char count,
    BcPartyContactSink sink, void *context);
BcPartyFrameResult bc_runtime_party_frame(BcPartyControl *party, BcFrameCursor *cursor,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcStageEventData *stage_data, BcActorStepData *actor_data,
    unsigned short pose_table, const unsigned char held[BC_PARTY_CAPACITY],
    const unsigned char pressed[BC_PARTY_CAPACITY], unsigned char *limited_count,
    BcRuntimeEvents *events);

/* Direct output avoids copying the party result into the scene. */
void bc_runtime_party_frame_into(BcPartyFrameResult *result, BcPartyControl *party, BcFrameCursor *cursor,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcStageEventData *stage_data, BcActorStepData *actor_data,
    unsigned short pose_table, const unsigned char held[BC_PARTY_CAPACITY],
    const unsigned char pressed[BC_PARTY_CAPACITY], unsigned char *limited_count,
    BcRuntimeEvents *events);
