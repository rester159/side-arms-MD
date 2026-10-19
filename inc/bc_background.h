#pragma once
#include <genesis.h>

/* Logical BC blocks can use either retained Normal tiles or BC-only storage. */
extern const u8 * const bc_bg_sources[];

/* R1 retains Normal stage 1's original Vivid transform. */
extern const u16 bc_bg_palette[32], bc_bg_vivid_palette[32];
