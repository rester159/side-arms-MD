#pragma once
#include "bc_rules.h"

/* Source palette words remain PCE-format simulation/reference data.
 * The Genesis renderer must map them to its own palette allocation. */
typedef struct {
    unsigned short colors[256];
    unsigned char effect;
} BcPalette;
/* $414C-$418F: install the lower eight colors in each of sixteen palettes. */
void bc_palette_boss(BcPalette *palette, const BcEnemyData *data);
