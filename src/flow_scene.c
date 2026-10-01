#include "game.h"
#include "bg.h"
#include "sprites.h"
#include "flow.h"
#include "gen/assets.h"
#include "gen/frontend.h"

/* Fixed background views of the front end (title city $0BD1, Earth intro
 * $13BC), pre-rendered at build time (tools/build_frontend.py) into plane B
 * maps whose tiles live in the BG metatile-cache VRAM while bg.c is switched
 * off. stage_video_on() hands plane B and that VRAM back to bg.c. */

#define STREAM_BYTES 6144               /* tile DMA per frame */

static s16 loaded = -1, loading = -1;
static u16 load_pos;                    /* tiles sent */
static s16 shown = -1;
static u8 resend;

void scene_load_set(u16 set)
{
    if (loaded == (s16)set || loading == (s16)set) return;
    bg_enable(FALSE);                   /* bg.c must not touch its cache VRAM meanwhile */
    loading = set; loaded = -1; load_pos = 0;
}

bool scene_ready(void) { return loading < 0 && loaded >= 0; }

void scene_show(u16 scene)
{
    if (shown == (s16)scene && !resend) return;
    shown = scene;
    resend = 2;                         /* also after bg.c's own clear of plane B */
    video_set_camera(0, 0);
}

void scene_off(void)
{
    if (shown < 0) return;
    shown = -1; resend = 0;
    bg_enable(TRUE);                    /* toggling makes bg.c clear plane B */
    bg_enable(FALSE);
}

void scene_update(void)
{
    if (loading >= 0) {
        const FeSceneSet *s = &fe_scene_sets[loading];
        u16 n = s->count - load_pos;
        if (n > STREAM_BYTES / 32) n = STREAM_BYTES / 32;
        DMA_queueDma(DMA_VRAM, (void *)(s->tiles + (u32)load_pos * 32), (VRAM_BG_TILE + load_pos) * 32, n * 16, 2);
        load_pos += n;
        if (load_pos >= s->count) {
            PAL_setColors(0, s->pal, 32, DMA_QUEUE);
            loaded = loading; loading = -1;
        }
        return;                         /* maps wait for their tiles */
    }
    if (resend && shown >= 0 && fe_scenes[shown].set == loaded) {
        DMA_queueDma(DMA_VRAM, (void *)fe_scenes[shown].map, VRAM_PLANE_B, 64 * 28, 2);
        resend--;
    }
}

/* bg.c streams the world again: flush its metatile cache (its VRAM was
 * overwritten) by selecting the zone under the camera, like its auto_zone. */
void stage_video_on(void)
{
    s16 cx = (cam_x() + SCREEN_W / 2) >> 5, cy = (cam_y() + SCREEN_H / 2) >> 5;
    u16 z = 0;
    for (u16 i = 0; i < ZONE_COUNT; i++) {
        const Zone *q = &zones[i];
        if (cx >= (s16)q->x0 && cy >= (s16)q->y0 && cx < (s16)(q->x0 + q->w) && cy < (s16)(q->y0 + q->h)) { z = i; break; }
    }
    shown = -1; resend = 0; loaded = -1; loading = -1;
    bg_set_zone(z);
    video_set_camera(cam_x(), cam_y());
    video_set_layers(TRUE, TRUE);
}

void stage_sprites_on(void)
{
    spr_init();                         /* the front end used sprite VRAM for text */
}

/* something else (the demo logo) overwrote the scene tiles */
void scene_invalidate(void)
{
    shown = -1; resend = 0; loaded = -1; loading = -1;
}
