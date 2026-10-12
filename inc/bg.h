#pragma once
#include <genesis.h>
#include "gen/assets.h"

/* Background: the arcade's 4096x4096 world map (128x128 cells of 32x32 px,
 * read by the arcade video hardware straight from ROM b_03d) streamed into a
 * 64x32 plane ring buffer through a cache of 32x32 metatiles. */

void bg_init(void);
/* Select palette zone (loads its palettes, invalidates the cache). */
void bg_set_zone(u16 zone);
/* Explicit stage artwork, independent of Normal mode's camera zones. Data
 * must remain alive until bg_init/bg_set_zone. NULL cells uses art->map;
 * otherwise cells is the BC 16x16 block map (64 bytes/block), and remap maps
 * its 256 cell IDs to Genesis metatile entries. Coordinates wrap at 4096 px.
 * Call with display off for initial uploads. No collision state is changed. */
/* NULL sources uses contiguous art->tiles. Otherwise each entry points to a
 * DMA-aligned 512-byte block; the table has art->metas entries. */
/* min_cell_x extends the first authored column leftward for visuals only. */
/* min_cell_x packs optional visual maximum column in bits 8..14.
 * Bit 15 mirrors columns 0/7 into the margins of a 256px vertical shaft. */
void bg_set_stage(const Zone *art, const u8 *cells, const u16 *remap,
                  const u8 * const *sources, u16 min_cell_x);
/* Camera = world pixel at the top-left of the Genesis screen. */
void bg_set_camera(s16 x, s16 y);
void bg_enable(bool on);
/* Stop background streaming and borrow a cleared 32x32 tile page from its
 * existing RAM shadow for scene presentation. Do not call bg_update while
 * borrowed; bg_init must precede returning to gameplay background use. */
u16 *bg_scene_page(void);
void bg_update(void);   /* stream cells + set scroll; call once per frame */
u16 bg_cache_misses(void);

/* ---- Home parallax (docs/parallax.md, parallax.c) -------------------------
 * bg_set_home: use the zones' Home variants (texture cells cut out for a far
 * layer) and the distant-scenery bands. bg_scroll_external: plane-B scroll is
 * written by parallax.c (line scroll), not by bg_update(). bg_band_lines: the
 * screen lines [l0, l1) of the active band and its camera x. */
void bg_set_home(bool on);
void bg_scroll_external(bool on);
bool bg_is_enabled(void);
bool bg_is_home(void);
void bg_view(s16 *x, s16 *y);           /* camera of the picture on screen (a zone switch shows the old one a frame longer) */                  /* Home zone variants selected */
u16 bg_zone_index(void);                /* 0xFFFF: none */
bool bg_band_lines(s16 *l0, s16 *l1, s16 *x);

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
