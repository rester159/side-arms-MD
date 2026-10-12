#include "bc_palette.h"

void bc_palette_boss(BcPalette *palette, const BcEnemyData *data)
{
    const unsigned char *source = data->bytes + (unsigned short)(0x4ffd - data->origin);
    palette->effect = 1;
    for (unsigned char bank = 0; bank < 16; bank++) {
        for (unsigned char color = 0; color < 8; color++) {
            palette->colors[bank * 16 + color] = source[0] | ((unsigned short)source[1] << 8);
            source += 2;
        }
    }
}
