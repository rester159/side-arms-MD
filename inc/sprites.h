#pragma once
#include <genesis.h>

/* Sprite display list in Genesis screen coordinates. Submit in front-to-back
 * order: the first sprite submitted is drawn on top. Graphics are the arcade's
 * 16x16 cells (code 0-2047, arcade colour 0-15), pre-converted at build time. */

#define SPR_FLIPX 1
#define SPR_FLIPY 2

void spr_init(void);
void spr_begin(void);
void spr_16(u16 code, u8 colour, s16 x, s16 y, u8 flags);   /* one 16x16 cell */
void spr_32(u16 code, u8 colour, s16 x, s16 y, u8 flags);   /* 2x2 cells c, c+1, c+8, c+9 */
void spr_tile32(u16 tile, u8 pal, s16 x, s16 y);  /* caller-owned VRAM patterns (bosses), pal 0/1 = PAL2/3 */
void spr_tile16(u16 tile, u8 pal, s16 x, s16 y);  /* same, 16x16 */
void spr_end(void);
u16 spr_uploads(void);
