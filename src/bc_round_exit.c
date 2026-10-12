#include "bc_round_exit.h"

void bc_round_exit_begin(BcRoundExit *exit, BcAudioRequest *audio,
    const BcEnemyData *data, signed short relocation)
{
    exit->remaining = 0;
    exit->phase = 1;
    exit->pause_disabled = 0;
    bc_audio_request(audio, data, 0x8db2 + relocation);
}

void bc_round_exit_final_begin(BcRoundExit *exit, BcAudioRequest *audio, const BcEnemyData *data)
{
    exit->remaining = 0; exit->phase = 1; exit->pause_disabled = 1;
    bc_audio_request(audio, data, 0xa5ff);
}

unsigned char bc_round_exit_tick(BcRoundExit *exit, BcAudioRequest *audio,
    unsigned char paused)
{
    if (exit->phase == 1) {
        if (audio->state != 2) return 0;
        audio->state = 0;
        exit->pause_disabled = 1;
        /* $3AB6 calls the 60-frame wait seven times, then $3A88 waits one. */
        exit->remaining = 421;
        exit->phase = 2;
        return 0;
    }
    if (exit->phase != 2) return 0;
    if (exit->remaining) exit->remaining--;
    if (exit->remaining || paused) return 0;
    exit->phase = 3;
    return 1;
}
