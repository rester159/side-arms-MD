#pragma once
#include <genesis.h>

/* Home-mode parallax engine (docs/parallax.md), driven by video.c while the stage view is on.
 * Scroll tables: H-scroll in line mode (224 entries per plane, DMA'd in VBlank when they
 * change), V-scroll per plane or per 16-px column; the scroll-mode register itself is switched
 * from the SGDK VBlank callback, after the DMA queue has delivered the matching tables. */
void par_start(void);                   /* parallax takes over the scroll tables and plane A */
void par_stop(void);                    /* back to plane scroll (the arcade's) */
void par_frame(s16 cam_x, s16 cam_y);   /* after bg_update(): build and queue this frame's tables */
void par_vblank(void);                  /* SGDK VBlank callback */
void video_stars_draw(bool on);         /* video.c: plane A = the starfield (or blank) */

/* debug / QA: current mode (0 off, 1 star rows, 2 star columns, 3 far layer) and band flag */
extern volatile u8 par_dbg_mode, par_dbg_band;
