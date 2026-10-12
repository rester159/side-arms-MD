#pragma once
#include <genesis.h>

/* All CRAM loads go through here so the COLOR option can apply. */
enum { COLOR_ARCADE, COLOR_VIVID };
extern u8 color_mode;
void pal_load(u16 index, const u16 *cols, u16 count);   /* queued for VBlank */
void pal_set_mode(u8 mode);                             /* re-applies the loaded palettes */
/* Presentation-only brightness, 0 black through 7 full; keeps base colors. */
void pal_fade_level(u8 level);
