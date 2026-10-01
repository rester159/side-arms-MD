#pragma once
#include <genesis.h>

/* VRAM layout (H40, 64x32 planes):
 *   tiles    0..159    blank + starfield
 *   tiles  160..1055   BG metatile cache, 56 slots x 16 tiles
 *   tiles 1056..1311   sprite patterns, 64 x 16x16
 *   tiles 1312..1407   HUD font / glyphs
 *   tiles 1664..1791   sprite patterns, 8 x 32x32 (free 0xD000 block)
 *   tiles 1953..2032   sprite patterns, 5 x 32x32 (H-scroll table only uses
 *                      its first 4 bytes in plane-scroll mode)
 *   0xB000 window (HUD, high), 0xC000 plane A (stars, low),
 *   0xE000 plane B (background, high), 0xF000 SAT, 0xF400 H-scroll. */
#define VRAM_BG_TILE        160
#define BG_SLOTS            56
#define VRAM_SPR_TILE       1056
#define VRAM_FONT_TILE      1312
#define VRAM_SPR_BIG_TILE   1664
#define VRAM_SPR_BIG2_TILE  1953
#define VRAM_WINDOW         0xB000
#define VRAM_PLANE_A        0xC000
#define VRAM_PLANE_B        0xE000
#define VRAM_SAT            0xF000
#define VRAM_HSCROLL        0xF400

#define SCREEN_W            320
#define SCREEN_H            224
/* The arcade screen is 384x224; arcade scroll S shows world [S+64, S+448) x
 * [S+16, S+240). The Genesis view is centred in it: camera = S + (96, 16). */
#define ARCADE_VIEW_X       96
#define ARCADE_VIEW_Y       16

void video_init(void);
void video_set_camera(s16 cam_x, s16 cam_y);    /* world pixel at screen top-left */
void video_set_layers(bool bg, bool stars);
void video_stars_step(s16 dx, s16 dy);          /* starfield parallax */
void video_frame(void);                         /* push scroll / plane updates */
