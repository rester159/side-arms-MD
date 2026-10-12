#pragma once
#include "bc_rules.h"

/* Exact eight-byte source BIOS playback request, retained for the Genesis
 * music backend to map to a track/segment. No audio is played by this module. */
typedef struct {
    unsigned short handler;
    unsigned char parameters[8];
    unsigned char state; /* 0 idle, 1 awaiting backend, 2 backend acknowledged */
} BcAudioRequest;
/* Round-nine loader request, before the stage-script/player loop. */
unsigned char bc_audio_round_start(BcAudioRequest *request, const BcEnemyData *data, unsigned char round);
unsigned char bc_audio_stage_handler(unsigned short canonical);
void bc_audio_request(BcAudioRequest *request, const BcEnemyData *data,
    unsigned short handler);
/* Gallery / staff-roll requests from the ending overlay. */
void bc_audio_ending_request(BcAudioRequest *request, unsigned char credits);
void bc_audio_acknowledge(BcAudioRequest *request);

/* Existing Genesis soundtrack replacement for verified stage/boss/clear requests.
 * Returns 255 for unknown handler/parameters; no request mutation. */
unsigned char bc_audio_music_command(const BcAudioRequest *request, signed short relocation);

/* Player-event replacement effects in the existing Genesis sound bank.
 * Zero means no event; 255 means no mapping. */
unsigned char bc_audio_player_command(unsigned char source);
unsigned char bc_audio_actor_command(unsigned char source);
