#pragma once
#include <genesis.h>

/* Background: the arcade's 4096x4096 world map (128x128 cells of 32x32 px,
 * read by the arcade video hardware straight from ROM b_03d) streamed into a
 * 64x32 plane ring buffer through a cache of 32x32 metatiles. */

void bg_init(void);
/* Select palette zone (loads its palettes, invalidates the cache). */
void bg_set_zone(u16 zone);
/* Camera = world pixel at the top-left of the Genesis screen. */
void bg_set_camera(s16 x, s16 y);
void bg_enable(bool on);
void bg_update(void);   /* stream cells + set scroll; call once per frame */
u16 bg_cache_misses(void);

/* ---- VRAM blocks borrowed from the metatile cache (boss module) ----------
 * A cache slot is 16 consecutive tiles = exactly one 32x32 sprite. Along the
 * whole game path the view never needs more than 33 of the 56 slots, so
 * bosses borrow up to 24 free slots for their own patterns. Returns the
 * number reserved; tiles[i] = first VRAM tile of block i. Reserved blocks
 * survive zone switches until released. */
u16 bg_reserve_blocks(u16 n, u16 *tiles);
void bg_release_blocks(void);

/* ---- animated background frames (BG wheel bosses) -----------------------
 * The arcade animates the wheel bosses by jumping the BG scroll between
 * three copies of the wheel in the world map. Here the camera stays put and
 * a rectangle of world cells is replaced by one of N frame maps instead:
 * every metatile of every frame is pinned in the cache first (a few per
 * frame), the frames are pre-rendered into nametable images, and switching
 * frames is then a RAM copy + one plane DMA (no tile uploads, 60 fps safe). */
typedef struct {
    u16 zone;                   /* zone the maps refer to (switched to if needed) */
    u16 cx, cy, w, h;           /* world cell rect replaced by the frames */
    u16 nframes;
    const u16 *maps;            /* nframes x (w*h) cells, zone map format; meta >= zone metas = extra */
    u16 nextra;                 /* extra metatiles not in the zone */
    const u8 *extra_tiles;      /* nextra x 512 bytes */
    const u16 *extra_tmpl;      /* nextra x 16 nametable templates */
} BgFrames;
void bg_frames_begin(const BgFrames *f);
bool bg_frames_ready(void);     /* all frame metatiles resident */
void bg_frames_show(u16 n);     /* display frame n (ignored until ready) */
void bg_frames_end(void);       /* back to the plain world map */
