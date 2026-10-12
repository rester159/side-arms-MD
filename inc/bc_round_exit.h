#pragma once
#include "bc_audio.h"

/* Source $8DB2-$8DDD: wait for the clear-track backend, inhibit new pause
 * requests, then wait seven 60-frame intervals plus one pause-check frame.
 * Handoff starts the loader; it does not claim that the next round is loaded. */
typedef struct {
    unsigned short remaining;
    unsigned char phase; /* 0 idle, 1 audio, 2 delay/pause check, 3 handoff */
    unsigned char pause_disabled;
} BcRoundExit;
/* Final serpent: direct ending request, without the 50-effect boss sequence. */
void bc_round_exit_final_begin(BcRoundExit *exit, BcAudioRequest *audio, const BcEnemyData *data);
void bc_round_exit_begin(BcRoundExit *exit, BcAudioRequest *audio,
    const BcEnemyData *data, signed short relocation);
/* Call once per source scheduler frame after begin. Returns 1 exactly once,
 * when the source would dispatch $6042. Delay counts while already paused. */
unsigned char bc_round_exit_tick(BcRoundExit *exit, BcAudioRequest *audio,
    unsigned char paused);
