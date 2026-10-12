#include "bc_wave.h"

unsigned char bc_wave_copies(BcWaveScale *scale, unsigned char players,
    unsigned char size)
{
    if (!players || players > 4 ||
        (size != 1 && size != 2 && size != 4 && size != 5 && size != 8)) return 0;
    if (players <= 2) return 1;
    unsigned char quarters = scale->remainder[size] + (players == 3 ? 2 : 5);
    scale->remainder[size] = quarters & 3;
    return 1 + (quarters >> 2);
}
