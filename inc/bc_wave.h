#pragma once

/* Fractional formation counts, indexed by source formation size. Linked
 * enemies must be repeated as a whole group. Bind/reset on a new run/round. */
typedef struct { unsigned char remainder[9]; } BcWaveScale;
/* Total copies including the original: 1/1/1.5/2.25 for 1/2/3/4 players,
 * exact over four waves of each size. Zero for non-wave events/invalid input,
 * without changing state. Call once per successfully allocated source wave;
 * replayed copies must not recursively earn more copies. This plans counts,
 * not allocation: the scheduler must retain copies when the pool is full. */
unsigned char bc_wave_copies(BcWaveScale *scale, unsigned char players,
    unsigned char wave_size);

#include "bc_runtime.h"
#define BC_WAVE_QUEUE_CAPACITY 8
#define BC_WAVE_SPACING 8
/* Script addresses are ordinary events already executed successfully. */
typedef struct {
    unsigned short script;
    unsigned char size, copies;
} BcPendingWave;
typedef struct {
    BcWaveScale scale;
    BcPendingWave pending[BC_WAVE_QUEUE_CAPACITY];
    unsigned char head, count, delay;
    unsigned short originals, extras, blocked;
} BcWaveQueue;
/* Returns zero without mutation if no room. Caller reserves room before
 * executing a source event, so its successful birth can always be recorded. */
unsigned char bc_wave_enqueue(BcWaveQueue *queue, unsigned char players,
    unsigned short script, unsigned char size);
/* One attempt per frame, after source stage/audio events and before actors.
 * Failed allocation retains the exact pending record. */
void bc_wave_service(BcWaveQueue *queue, BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player,
    const BcStageEventData *data, unsigned char *limited_count);
/* Pending ordinary enemies must precede source cleanup/stop/boss events. */
unsigned char bc_wave_barrier(unsigned char round, unsigned short handler,
    signed short relocation);
