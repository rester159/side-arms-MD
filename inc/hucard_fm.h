#pragma once
#include "hucard_score.h"

#define HUCARD_FM_VOICE_BYTES 12
#define HUCARD_FM_FRAME_BYTES (6 * HUCARD_FM_VOICE_BYTES)
extern const unsigned char hucard_fm_patches[32][8];
extern const unsigned char hucard_fm_algorithms[32];
extern const unsigned short hucard_fm_pitch[2][4096];
/* Packet: instrument, F-number high/low, pan | algorithm, four multipliers, four TLs.
 * The Z80 owns chip writes; 68000 computes these packets outside bus holds. */
void hucard_fm_frame(const HucardScore *score, unsigned char pal, unsigned char *packet);
