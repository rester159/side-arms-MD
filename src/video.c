#include "video.h"
#include "bg.h"
#include "sprites.h"
#include "parallax.h"
#include "gen/assets.h"

static bool stars_on, want_stars;
static s16 star_x, star_y;
static s16 v_cam_x, v_cam_y;
static bool par_want, par_running;

void video_stars_draw(bool on)
{
    static u16 row[64];
    for (u16 y = 0; y < 32; y++) {
        const u16 *src = star_map + y * 64;
        for (u16 x = 0; x < 64; x++) row[x] = on ? src[x] : 0;    /* tile | palette, low priority */
        VDP_setTileMapDataRect(BG_A, row, 0, y, 64, 1, 64, DMA_QUEUE_COPY);
    }
    stars_on = on;
}

void video_init(void)
{
    VDP_setEnable(FALSE);
    VDP_setScreenWidth320();
    VDP_setPlaneSize(64, 32, FALSE);
    VDP_setBGAAddress(VRAM_PLANE_A);
    VDP_setBGBAddress(VRAM_PLANE_B);
    VDP_setWindowAddress(VRAM_WINDOW);
    VDP_setSpriteListAddress(VRAM_SAT);
    VDP_setHScrollTableAddress(VRAM_HSCROLL);
    VDP_setScrollingMode(HSCROLL_PLANE, VSCROLL_PLANE);
    VDP_setWindowVPos(FALSE, 0);
    VDP_setBackgroundColor(0);
    VDP_clearPlane(BG_A, TRUE);
    VDP_clearPlane(BG_B, TRUE);
    VDP_clearPlane(WINDOW, TRUE);
    PAL_setColors(0, palette_black, 64, CPU);
    /* Plane A: the arcade starfield generator's 512x256 period = one 64x32 plane. */
    VDP_loadTileData((const u32 *)star_tiles, 0, STAR_TILE_COUNT, DMA);
    stars_on = want_stars = FALSE;
    bg_init();
    spr_init();
    SYS_setVBlankCallback(par_vblank);  /* scroll-mode switches land after the scroll tables' DMA */
    VDP_setEnable(TRUE);
}

void video_set_camera(s16 cam_x, s16 cam_y) { v_cam_x = cam_x; v_cam_y = cam_y; bg_set_camera(cam_x, cam_y); }

void video_set_layers(bool bg, bool stars)
{
    bg_enable(bg);
    want_stars = stars;
}

void video_set_parallax(bool on)
{
    par_want = on;
    bg_set_home(on);                    /* zone variants + bands (reloads the zone on a change) */
}

void video_stars_step(s16 dx, s16 dy) { star_x += dx; star_y += dy; }

void video_frame(void)
{
    /* Home parallax runs while the stage view (BG + stars) is on; menus and scenes stay plain */
    bool par = par_want && want_stars && bg_is_enabled();
    if (par != par_running) {
        par_running = par;
        bg_scroll_external(par);
        if (par) par_start();
        else { par_stop(); stars_on = FALSE; }       /* plane A may hold a far layer: redraw */
    }
    if (want_stars != stars_on && !par) video_stars_draw(want_stars);
    if (par) {
        bg_update();                    /* streams the view, band state for this camera */
        s16 vx, vy;
        bg_view(&vx, &vy);              /* = the camera, except on a zone switch's first frame */
        par_frame(vx, vy);
        return;
    }
    VDP_setHorizontalScrollVSync(BG_A, -star_x);
    VDP_setVerticalScrollVSync(BG_A, star_y);
    bg_update();
}
