#include "palette.h"
#include "gen/assets.h"

/* COLOR option. ARCADE = colours as converted from the arcade palette.
 * VIVID = each colour mapped through vivid_lut (build time: saturation x1.4,
 * brightness x1.15, greys kept neutral) for a punchier picture; a deliberate,
 * optional deviation from the arcade colours. */

u8 color_mode = COLOR_VIVID;
static u16 source[64];              /* palettes as loaded (before the mode mapping) */
static u16 shown[64];

/* Genesis colour word 0000BBB0GGG0RRR0 -> vivid_lut index BBBGGGRRR */
static inline u16 lut_index(u16 c) { return ((c >> 1) & 7) | (((c >> 5) & 7) << 3) | (((c >> 9) & 7) << 6); }

static void push(u16 index, u16 count)
{
    for (u16 i = index; i < index + count; i++)
        shown[i] = color_mode == COLOR_VIVID ? vivid_lut[lut_index(source[i])] : source[i];
    PAL_setColors(index, shown + index, count, DMA_QUEUE);
}

void pal_load(u16 index, const u16 *cols, u16 count)
{
    memcpy(source + index, cols, count * 2);
    push(index, count);
}

void pal_set_mode(u8 mode)
{
    color_mode = mode;
    push(0, 64);
}
