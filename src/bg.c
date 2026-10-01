#include "bg.h"
#include "video.h"
#include "gen/assets.h"

/* Plane B (64x32 tiles) is a ring of 16x8 world cells (32x32 px). The visible
 * window of cells is kept loaded; when the camera crosses a cell boundary only
 * the entering/leaving strip is touched. Cells are written into a RAM shadow
 * of the plane and each changed strip goes to VRAM as 4 DMA transfers in
 * VBlank (columns with a 128-byte VRAM step). Metatile patterns live in a
 * 56-slot VRAM cache with reference counts (one per loaded cell).
 *
 * Boss support (docs/bosses.md): slots can be lent out as plain 16-tile VRAM
 * blocks (refs = RESERVED), and a rectangle of cells can be overridden by
 * pre-rendered animation frames (the BG wheel bosses). */

#define RING_W      16
#define RING_H      8
#define NO_SLOT     0xFF
#define MAX_META    1024
#define RESERVED    0xFF                /* slot_refs value of a lent-out slot */
#define FR_PRELOAD  6                   /* frame metatiles made resident per frame */

static const Zone *zone;
static s16 cam_x, cam_y;
static s16 lx0, ly0, lx1, ly1;          /* loaded cell rect, inclusive; empty if lx1 < lx0 */
static bool enabled = TRUE;
static u8 cell_slot[RING_H][RING_W];
static u16 slot_meta[BG_SLOTS];
static u8 slot_refs[BG_SLOTS];
static u8 meta_slot[MAX_META];
static u16 hand;                        /* clock hand for slot replacement */
static u16 misses;
static u16 shadow[32][64];              /* plane B nametable */
static u16 colbuf[16][32];              /* column-major staging for column strips */
static u16 dirty_cols, dirty_rows;      /* ring cell columns / rows to send */
static bool dirty_all;
/* look-ahead column (horizontal scrolling): the column about to enter the view is
 * loaded a few cells per frame before it is needed, so crossing a 32-px cell
 * boundary costs nothing (a whole column at once is ~40 lines of the 68000). It
 * sits just outside the loaded rect, rows ly0..ly1, loaded up to row pre_y. */
#define NO_PRE      0x7FFF
#define PRE_PER_FRAME 2
static s16 pre_x = NO_PRE, pre_y;
static s16 last_cam_x;
static s8 hdir;

/* animated frames (bg_frames_*) */
static const BgFrames *fr;
static u8 fr_state;                     /* 0 off, 1 preloading, 3 rendering, 2 ready */
static u16 fr_render;                   /* next frame image to render */
static u16 fr_meta[64];
static u16 fr_nmeta, fr_next;
static u16 *fr_img;                     /* nframes x full 64x32 plane images, or NULL */
static s16 fr_shown, fr_pending = -1;
static void frames_drop(void);

u16 bg_cache_misses(void) { return misses; }

static void flush_cache(void)
{
    frames_drop();
    for (u16 i = 0; i < BG_SLOTS; i++) {
        slot_meta[i] = 0xFFFF;
        if (slot_refs[i] != RESERVED) slot_refs[i] = 0;
    }
    memset(meta_slot, NO_SLOT, sizeof(meta_slot));
    memset(cell_slot, NO_SLOT, sizeof(cell_slot));
    memset(shadow, 0, sizeof(shadow));
    lx0 = 1; lx1 = 0; ly0 = 1; ly1 = 0;
    pre_x = NO_PRE;
    dirty_all = TRUE;
}

void bg_init(void)
{
    zone = NULL;
    flush_cache();
    dirty_all = FALSE;
}

void bg_set_zone(u16 z)
{
    zone = &zones[z];
    flush_cache();
    PAL_setColors(0, zone->pal, 32, DMA_QUEUE);
}

static u8 acquire(u16 meta)
{
    u8 s = meta_slot[meta];
    if (s != NO_SLOT) { slot_refs[s]++; return s; }
    for (u16 n = 0; n < BG_SLOTS; n++) {
        u16 i = hand;
        if (++hand == BG_SLOTS) hand = 0;
        if (slot_refs[i]) continue;
        if (slot_meta[i] != 0xFFFF) meta_slot[slot_meta[i]] = NO_SLOT;
        slot_meta[i] = meta; meta_slot[meta] = i; slot_refs[i] = 1;
        const u8 *src = meta < zone->metas ? zone->tiles + (u32)meta * 512
                                           : fr->extra_tiles + (u32)(meta - zone->metas) * 512;
        DMA_queueDmaFast(DMA_VRAM, (void *)src, (VRAM_BG_TILE + i * 16) * 32, 256, 2);
        misses++;
        return i;
    }
    return NO_SLOT;                     /* cache exhausted: cell stays blank */
}

/* Nametable words of map entry e (meta | b14 hflip | b15 vflip) whose
 * metatile sits in cache slot s; stride = words per destination row.
 * Hot path (88 cells per camera jump, 8 per scrolled strip): one unrolled
 * loop per flip case. Template words are 0 (blank) or priority | palette |
 * tile 0-15, so adding base | flip bits cannot carry into the flip bits. */
#define CW(d, v) do { u16 _v = (v); (d) = _v ? _v + b : 0; } while (0)
static void cell_words(u16 e, u8 s, u16 *dst, u16 stride)
{
    u16 meta = e & 0x0FFF;
    const u16 *t = meta < zone->metas ? zone->tmpl + meta * 16 : fr->extra_tmpl + (meta - zone->metas) * 16;
    u16 b = VRAM_BG_TILE + s * 16;
    switch (e & 0xC000) {
    case 0:
        for (u16 y = 0; y < 4; y++, dst += stride, t += 4) { CW(dst[0], t[0]); CW(dst[1], t[1]); CW(dst[2], t[2]); CW(dst[3], t[3]); }
        break;
    case 0x4000:
        b |= TILE_ATTR_HFLIP_MASK;
        for (u16 y = 0; y < 4; y++, dst += stride, t += 4) { CW(dst[0], t[3]); CW(dst[1], t[2]); CW(dst[2], t[1]); CW(dst[3], t[0]); }
        break;
    case 0x8000:
        b |= TILE_ATTR_VFLIP_MASK; t += 12;
        for (u16 y = 0; y < 4; y++, dst += stride, t -= 4) { CW(dst[0], t[0]); CW(dst[1], t[1]); CW(dst[2], t[2]); CW(dst[3], t[3]); }
        break;
    default:
        b |= TILE_ATTR_HFLIP_MASK | TILE_ATTR_VFLIP_MASK; t += 12;
        for (u16 y = 0; y < 4; y++, dst += stride, t -= 4) { CW(dst[0], t[3]); CW(dst[1], t[2]); CW(dst[2], t[1]); CW(dst[3], t[0]); }
        break;
    }
}
#undef CW

static void load_cell(s16 cx, s16 cy)
{
    u16 rx = cx & (RING_W - 1), ry = cy & (RING_H - 1);
    u16 *dst = &shadow[ry * 4][rx * 4];
    u8 s = NO_SLOT;
    s16 zx = cx - zone->x0, zy = cy - zone->y0;
    if (zx >= 0 && zy >= 0 && zx < (s16)zone->w && zy < (s16)zone->h) {
        u16 e = zone->map[zy * zone->w + zx];
        s = acquire(e & 0x0FFF);
        if (s != NO_SLOT) cell_words(e, s, dst, 64);
    }
    if (s == NO_SLOT)
        for (u16 y = 0; y < 4; y++, dst += 64) dst[0] = dst[1] = dst[2] = dst[3] = 0;
    cell_slot[ry][rx] = s;
}

static void drop_cell(s16 cx, s16 cy)
{
    u16 rx = cx & (RING_W - 1), ry = cy & (RING_H - 1);
    u8 s = cell_slot[ry][rx];
    if (s != NO_SLOT && slot_refs[s]) slot_refs[s]--;
    cell_slot[ry][rx] = NO_SLOT;
}

static void column(s16 x, s16 y0, s16 y1, bool load)
{
    for (s16 y = y0; y <= y1; y++) { if (load) load_cell(x, y); else drop_cell(x, y); }
    if (load) dirty_cols |= 1 << (x & (RING_W - 1));
}

static void row(s16 y, s16 x0, s16 x1, bool load)
{
    for (s16 x = x0; x <= x1; x++) { if (load) load_cell(x, y); else drop_cell(x, y); }
    if (load) dirty_rows |= 1 << (y & (RING_H - 1));
}

static void pre_drop(void)
{
    if (pre_x == NO_PRE) return;
    for (s16 y = ly0; y < pre_y; y++) drop_cell(pre_x, y);
    pre_x = NO_PRE;
}

/* load the look-ahead column's remaining rows (all of them if n is large) */
static void pre_load(u16 n)
{
    for (; n && pre_y <= ly1; n--, pre_y++) load_cell(pre_x, pre_y);
    if (pre_y > ly1) dirty_cols |= 1 << (pre_x & (RING_W - 1));     /* complete: send it */
}

void bg_set_camera(s16 x, s16 y) { cam_x = x; cam_y = y; }

/* $C80C bit 0: the arcade can switch the BG layer off (attract screens). */
void bg_enable(bool on)
{
    if (on == enabled) return;
    enabled = on;
    pre_drop();
    for (s16 y = ly0; y <= ly1; y++)
        for (s16 x = lx0; x <= lx1; x++) drop_cell(x, y);
    lx0 = 1; lx1 = 0; ly0 = 1; ly1 = 0;
    memset(shadow, 0, sizeof(shadow));
    dirty_all = TRUE;
}

static bool zone_has(const Zone *z, s16 cx, s16 cy)
{
    return cx >= (s16)z->x0 && cy >= (s16)z->y0 && cx < (s16)(z->x0 + z->w) && cy < (s16)(z->y0 + z->h);
}

/* Palette zones follow the camera: zones are scroll runs, so the camera
 * leaves one only through a teleport (or into empty map). */
static void auto_zone(void)
{
    s16 cx = (cam_x + SCREEN_W / 2) >> 5, cy = (cam_y + SCREEN_H / 2) >> 5;
    if (zone && zone_has(zone, cx, cy)) return;
    for (u16 i = 0; i < ZONE_COUNT; i++)
        if (zone_has(&zones[i], cx, cy)) { bg_set_zone(i); return; }
}

static void release_cells(const u8 *o)
{
    for (u16 i = 0; i < RING_H * RING_W; i++, o++)
        if (*o != NO_SLOT && slot_refs[*o] && slot_refs[*o] != RESERVED) slot_refs[*o]--;
}

/* Camera jump (teleport, section start, warp): reload the whole view, ~88 cells.
 * The new cells are acquired before the old ones are released, so metatiles both
 * views use stay resident (no needless re-upload); every ring cell of the rect is
 * rewritten, the ring outside the rect is never visible, so no plane clear. */
static void load_all(s16 x0, s16 y0, s16 x1, s16 y1)
{
    pre_drop();
    u8 old[RING_H][RING_W];
    bool released = FALSE;
    memcpy(old, cell_slot, sizeof(old));
    memset(cell_slot, NO_SLOT, sizeof(cell_slot));
    for (s16 y = y0; y <= y1; y++) {
        u16 ry = y & (RING_H - 1);
        s16 zy = y - zone->y0;
        const u16 *mrow = (zy >= 0 && zy < (s16)zone->h) ? zone->map + zy * zone->w : NULL;
        for (s16 x = x0; x <= x1; x++) {
            u16 rx = x & (RING_W - 1);
            u16 *dst = &shadow[ry * 4][rx * 4];
            s16 zx = x - zone->x0;
            u8 sl = NO_SLOT;
            if (mrow && zx >= 0 && zx < (s16)zone->w) {
                u16 e = mrow[zx];
                sl = acquire(e & 0x0FFF);
                if (sl == NO_SLOT && !released) {       /* cache full: release the old view now */
                    release_cells(&old[0][0]);
                    released = TRUE;
                    sl = acquire(e & 0x0FFF);
                }
                if (sl != NO_SLOT) cell_words(e, sl, dst, 64);
            }
            if (sl == NO_SLOT)
                for (u16 k = 0; k < 4; k++, dst += 64) dst[0] = dst[1] = dst[2] = dst[3] = 0;
            cell_slot[ry][rx] = sl;
        }
    }
    if (!released) release_cells(&old[0][0]);
    dirty_all = TRUE;
}

static void send(void)
{
    if (fr_pending >= 0) {                          /* a pre-rendered wheel frame */
        DMA_queueDmaFast(DMA_VRAM, fr_img + (u32)fr_pending * (sizeof(shadow) / 2), VRAM_PLANE_B, sizeof(shadow) / 2, 2);
        fr_pending = -1;
        dirty_all = FALSE; dirty_cols = dirty_rows = 0;
        return;
    }
    if (dirty_all) {
        DMA_queueDmaFast(DMA_VRAM, shadow, VRAM_PLANE_B, sizeof(shadow) / 2, 2);
        dirty_all = FALSE; dirty_cols = dirty_rows = 0;
        return;
    }
    u16 n = 0;
    for (u16 rx = 0; dirty_cols && rx < RING_W; rx++) {
        if (!(dirty_cols & (1 << rx))) continue;
        dirty_cols &= ~(1 << rx);
        for (u16 k = 0; k < 4; k++) {
            u16 tx = rx * 4 + k;
            u16 *cb = colbuf[n++ & 15];
            for (u16 ty = 0; ty < 32; ty++) cb[ty] = shadow[ty][tx];
            DMA_queueDmaFast(DMA_VRAM, cb, VRAM_PLANE_B + tx * 2, 32, 128);
        }
    }
    for (u16 ry = 0; dirty_rows && ry < RING_H; ry++) {
        if (!(dirty_rows & (1 << ry))) continue;
        dirty_rows &= ~(1 << ry);
        DMA_queueDmaFast(DMA_VRAM, shadow[ry * 4], VRAM_PLANE_B + ry * 4 * 128, 4 * 64, 2);
    }
}

/* ---- lent VRAM blocks ---------------------------------------------------- */
u16 bg_reserve_blocks(u16 n, u16 *tiles)
{
    u16 got = 0;
    for (s16 i = BG_SLOTS - 1; i >= 0 && got < n; i--) {
        if (slot_refs[i]) continue;                 /* in use or already lent */
        if (slot_meta[i] != 0xFFFF) meta_slot[slot_meta[i]] = NO_SLOT;
        slot_meta[i] = 0xFFFF;
        slot_refs[i] = RESERVED;
        tiles[got++] = VRAM_BG_TILE + i * 16;
    }
    return got;
}

void bg_release_blocks(void)
{
    for (u16 i = 0; i < BG_SLOTS; i++)
        if (slot_refs[i] == RESERVED) slot_refs[i] = 0;
}

/* ---- animated frames -------------------------------------------------------- */
static void frames_drop(void)
{
    if (fr_img) { MEM_free(fr_img); fr_img = NULL; }
    fr_state = 0;
    fr_pending = -1;
}

void bg_frames_begin(const BgFrames *f)
{
    bg_frames_end();
    if (!zone || zone != &zones[f->zone]) bg_set_zone(f->zone);
    fr = f; fr_state = 1; fr_next = 0; fr_nmeta = 0; fr_shown = -1;
    u16 n = f->w * f->h * f->nframes;
    for (u16 i = 0; i < n; i++) {
        u16 m = f->maps[i] & 0x0FFF, k = 0;
        while (k < fr_nmeta && fr_meta[k] != m) k++;
        if (k == fr_nmeta && fr_nmeta < 64) fr_meta[fr_nmeta++] = m;
    }
}

bool bg_frames_ready(void) { return fr_state == 2; }

/* Write rows j0..j1-1 of frame n's cells into a 64x32 nametable image (ring layout). */
static void frame_cells(u16 n, u16 *plane, u16 j0, u16 j1)
{
    const u16 *m = fr->maps + (n * fr->h + j0) * fr->w;
    for (u16 j = j0; j < j1; j++) {
        u16 ry = (fr->cy + j) & (RING_H - 1);
        for (u16 i = 0; i < fr->w; i++, m++) {
            u16 rx = (fr->cx + i) & (RING_W - 1);
            u8 s = meta_slot[*m & 0x0FFF];
            u16 *dst = plane + ry * 4 * 64 + rx * 4;
            if (s != NO_SLOT) cell_words(*m, s, dst, 64);
            else for (u16 y = 0; y < 4; y++, dst += 64) dst[0] = dst[1] = dst[2] = dst[3] = 0;
        }
    }
}

/* Pre-render every frame as a whole plane image once all metatiles are pinned:
 * the camera is still, so the rest of the plane is the current shadow. A turn
 * of the wheel is then one 4 KB DMA and no CPU work. */
static bool frames_render(void)
{
    if (!fr_img) {
        fr_img = MEM_alloc(fr->nframes * sizeof(shadow));
        fr_render = 0;
        if (!fr_img) return TRUE;                   /* no heap: frames are drawn into the shadow */
    }
    /* a slice per call so no frame overruns: the copy, then 2 cell rows at a time */
    u16 steps = 1 + (fr->h + 1) / 2;
    u16 f = fr_render / steps, k = fr_render % steps;
    u16 *img = fr_img + (u32)f * (sizeof(shadow) / 2);
    if (!k) memcpy(img, shadow, sizeof(shadow));
    else frame_cells(f, img, (k - 1) * 2, k * 2 < fr->h ? k * 2 : fr->h);
    return ++fr_render >= fr->nframes * steps;
}

static void frames_preload(void)
{
    for (u16 k = 0; k < FR_PRELOAD && fr_next < fr_nmeta; k++, fr_next++)
        if (acquire(fr_meta[fr_next]) == NO_SLOT) fr_meta[fr_next] = 0xFFFF;   /* cache full: shows blank */
    if (fr_next < fr_nmeta) return;
    fr_state = 3;
}

void bg_frames_show(u16 n)
{
    if (fr_state != 2 || n == (u16)fr_shown || n >= fr->nframes) return;
    fr_shown = n;
    if (fr_img) { fr_pending = n; return; }         /* sent by send() */
    frame_cells(n, &shadow[0][0], 0, fr->h);
    dirty_all = TRUE;
}

void bg_frames_end(void)
{
    if (!fr) return;
    for (u16 k = 0; k < fr_next; k++) {
        if (fr_meta[k] == 0xFFFF) continue;
        u8 s = meta_slot[fr_meta[k]];
        if (s != NO_SLOT && slot_refs[s] && slot_refs[s] != RESERVED) slot_refs[s]--;
    }
    frames_drop();
    fr = NULL;
    if (zone && lx1 >= lx0) load_all(lx0, ly0, lx1, ly1);   /* restore the plain map (shadow is intact) */
}

void bg_update(void)
{
    if (fr_state == 1 && zone) frames_preload();
    else if (fr_state == 3 && frames_render()) fr_state = 2;
    if (enabled) auto_zone();
    if (enabled && zone) {
        s16 nx0 = cam_x >> 5, ny0 = cam_y >> 5;
        s16 nx1 = (cam_x + SCREEN_W - 1) >> 5, ny1 = (cam_y + SCREEN_H - 1) >> 5;
        if (cam_x != last_cam_x) hdir = cam_x > last_cam_x ? 1 : -1;
        last_cam_x = cam_x;
        /* the look-ahead column is only valid for the current rows and direction */
        if (pre_x != NO_PRE && (ny0 != ly0 || ny1 != ly1 || pre_x != (hdir > 0 ? lx1 + 1 : lx0 - 1)))
            pre_drop();
        if (nx0 != lx0 || ny0 != ly0 || nx1 != lx1 || ny1 != ly1) {
            s16 dx = nx0 - lx0, dy = ny0 - ly0;
            if (lx1 < lx0 || dx > 1 || dx < -1 || dy > 1 || dy < -1) {
                load_all(nx0, ny0, nx1, ny1);   /* camera jump (teleport / stage start) */
            } else {
                /* entering column = the look-ahead column: only its missing rows */
                if (pre_x != NO_PRE && pre_x >= nx0 && pre_x <= nx1) {
                    pre_load(0xFFFF);
                    if (pre_x > lx1) lx1 = pre_x; else lx0 = pre_x;
                    pre_x = NO_PRE;
                }
                for (s16 x = lx0; x < nx0; x++) column(x, ly0, ly1, FALSE);
                for (s16 x = nx1 + 1; x <= lx1; x++) column(x, ly0, ly1, FALSE);
                s16 kx0 = lx0 > nx0 ? lx0 : nx0, kx1 = lx1 < nx1 ? lx1 : nx1;
                for (s16 y = ly0; y < ny0; y++) row(y, kx0, kx1, FALSE);
                for (s16 y = ny1 + 1; y <= ly1; y++) row(y, kx0, kx1, FALSE);
                s16 ky0 = ly0 > ny0 ? ly0 : ny0, ky1 = ly1 < ny1 ? ly1 : ny1;
                for (s16 y = ny0; y < ky0; y++) row(y, nx0, nx1, TRUE);
                for (s16 y = ky1 + 1; y <= ny1; y++) row(y, nx0, nx1, TRUE);
                for (s16 x = nx0; x < kx0; x++) column(x, ky0, ky1, TRUE);
                for (s16 x = kx1 + 1; x <= nx1; x++) column(x, ky0, ky1, TRUE);
            }
            lx0 = nx0; ly0 = ny0; lx1 = nx1; ly1 = ny1;
        }
        /* start / continue the look-ahead column (horizontal moves; the ring has 16 columns) */
        if (!fr && hdir && lx1 >= lx0 && lx1 - lx0 + 2 <= RING_W) {
            if (pre_x == NO_PRE) { pre_x = hdir > 0 ? lx1 + 1 : lx0 - 1; pre_y = ly0; }
            if (pre_y <= ly1) pre_load(PRE_PER_FRAME);
        }
    }
    send();
    VDP_setHorizontalScrollVSync(BG_B, -cam_x);
    VDP_setVerticalScrollVSync(BG_B, cam_y);
}
