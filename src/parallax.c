#include "video.h"
#include "bg.h"
#include "parallax.h"
#include "gen/assets.h"
#include "gen/parallax_data.h"

/* Home-mode parallax (docs/parallax.md). Not an arcade feature: Arcade mode never gets here.
 *
 * Plane A, star rows (default): the starfield's 32 rows of 8 lines are spread over four depth
 * layers (par_star_row, dim rows far). Every screen line takes the H offset of the plane row it
 * shows, so a star keeps its layer while the camera also moves vertically. Layer x = camera x *
 * speed / 16 (stateless: a teleport is a cut anyway).
 * Plane A, star columns: on the long vertical legs that begin and end at a cut
 * (par_col_legs), V-scroll runs per 16-px column, each column at its layer's speed.
 * Plane A, far layer: in a zone with a far texture (par_far), plane A shows the texture,
 * cut out of the zone's Home variant, at an offset from the world given by par_far.seg.
 * Plane B: the camera; the lines of an active BG band (bg.c) at the band camera.
 *
 * H-scroll mode: per 8-line cell (28 entries per plane, 32-byte stride) whenever every
 * boundary falls on a cell row: on horizontal legs the camera y is 16 mod 32, so plane-A rows
 * (vscroll = cam_y / 2) and band rows (32-px world rows) are cell aligned. Per line (224
 * entries per plane) on vertical / diagonal moves. Tables are DMA'd in VBlank when they change;
 * the scroll-mode register is switched by the SGDK VBlank callback, after that DMA.
 * Arithmetic: 16x16 muls / 32/16 divs only (a C 32-bit multiply is a libgcc call, ~1 line). */

volatile u8 par_dbg_mode, par_dbg_band;

enum { M_ROWS = 1, M_COLS, M_FAR };
static u8 mode;                         /* this frame's mode */
static u8 reg_h, reg_v, want_h, want_v; /* scroll-mode register (HSCROLL_*, VSCROLL_*) */
static vu8 reg_pending;
static s16 hs_a[224] __attribute__((aligned(4))), hs_b[224] __attribute__((aligned(4)));   /* line mode 224, cell mode 28 */
static s16 vsram[40];                   /* column mode: A, B per 16-px column */
static s16 last_a[PAR_STAR_LAYERS + 1], last_b[3];
static bool force_a, force_b;
static u8 tab_h;                        /* mode the tables were written for */
static s16 pa_content;                  /* plane A: -1 unknown, 0 stars, 1 + n = far layer n */
static u16 far_rows[8][64];             /* far layer: one period of plane rows */
static u8 row_layer[64];                /* plane-A row (two periods) -> its depth layer */
static s16 prev_x, prev_y, prev_bx, prev_l0;    /* last frame's inputs: unchanged -> nothing to do */
static u16 prev_z;

void par_start(void)
{
    pa_content = -1;
    force_a = force_b = TRUE;
    prev_x = 0x7FFF;
    for (u16 i = 0; i < 64; i++) row_layer[i] = par_star_row[i & 31];
    mode = 0;
}

void par_stop(void)
{
    want_h = HSCROLL_PLANE; want_v = VSCROLL_PLANE; reg_pending = TRUE;
    par_dbg_mode = 0; par_dbg_band = 0;
}

void par_vblank(void)
{
    if (!reg_pending) return;
    reg_pending = FALSE;
    reg_h = want_h; reg_v = want_v;
    VDP_setScrollingMode(reg_h, reg_v);
}

static void set_reg(u8 h, u8 v)
{
    if (h == want_h && v == want_v && (reg_pending || (h == reg_h && v == reg_v))) return;
    want_h = h; want_v = v; reg_pending = TRUE;
}

/* n copies of v, as 32-bit pairs (line mode rewrites up to 2 x 224 entries a frame) */
static void fill(s16 *d, s16 v, s16 n)
{
    if (n <= 0) return;
    if ((u32)d & 2) { *d++ = v; n--; }
    u32 vv = ((u32)(u16)v << 16) | (u16)v, *p = (u32 *)d;
    s16 k = n >> 1;
    for (; k >= 4; k -= 4) { *p++ = vv; *p++ = vv; *p++ = vv; *p++ = vv; }
    while (k-- > 0) *p++ = vv;
    if (n & 1) *(s16 *)p = v;
}

/* 16x16=32 muls.w (SGDK's C muls() can become a libgcc __mulsi3 call once inlined) */
static inline s32 mul16(s16 a, s16 b)
{
    s32 r = a;
    asm ("muls.w %1, %0" : "+d" (r) : "d" (b) : "cc");
    return r;
}

/* plane A = far layer f (tiles + 64x32 map from one period of rows) */
static void load_far(const ParFar *f)
{
    DMA_queueDma(DMA_VRAM, (void *)f->tiles, VRAM_FAR_TILE * 32, f->ntiles * 16, 2);
    for (u16 ty = 0; ty < f->h && ty < 8; ty++)
        for (u16 x = 0; x < 64; x++)
            far_rows[ty][x] = f->map[ty * f->w + (x % f->w)] + VRAM_FAR_TILE;
    /* one DMA per period of rows (the period divides the plane's 32 rows) */
    for (u16 y = 0; y < 32; y += f->h)
        DMA_queueDmaFast(DMA_VRAM, far_rows[0], VRAM_PLANE_A + y * 128, 64 * f->h, 2);
}

static const ParFar *far_for(s16 cam_x, s16 cam_y, s16 *off)
{
    u16 z = bg_zone_index();
    for (u16 i = 0; i < PAR_FAR_COUNT; i++) {
        const ParFar *f = &par_far[i];
        if (f->zone != z) continue;
        if (cam_x < f->rx0 || cam_x > f->rx1 || cam_y < f->ry0 || cam_y > f->ry1) return NULL;
        *off = 0;
        for (u16 k = 0; k < f->nseg; k++) {
            const ParSeg *s = &f->seg[k];
            if (cam_y != s->y || cam_x < s->x0) continue;
            s16 x = cam_x > s->x1 ? s->x1 : cam_x;
            *off = s->off0 + divs(mul16(x - s->x0, s->num), s->den);
        }
        return f;
    }
    return NULL;
}

static bool in_col_leg(s16 cam_x, s16 cam_y)
{
    for (u16 i = 0; i < PAR_COL_LEGS; i++) {
        const ParColLeg *l = &par_col_legs[i];
        if (cam_x == l->x && cam_y >= l->y0 && cam_y <= l->y1) return TRUE;
    }
    return FALSE;
}

void par_frame(s16 cam_x, s16 cam_y)
{
    /* the camera is still in 50-70% of frames: the tables, VSRAM and the register stay valid */
    s16 l0 = 0, l1 = 0, bx = cam_x;
    bool band = bg_band_lines(&l0, &l1, &bx);
    if (!band) l0 = l1 = 0;
    u16 z = bg_zone_index();
    if (cam_x == prev_x && cam_y == prev_y && bx == prev_bx && l0 == prev_l0 && z == prev_z) return;
    prev_x = cam_x; prev_y = cam_y; prev_bx = bx; prev_l0 = l0; prev_z = z;

    s16 off = 0;
    const ParFar *far = far_for(cam_x, cam_y, &off);
    u8 m = far ? M_FAR : in_col_leg(cam_x, cam_y) ? M_COLS : M_ROWS;
    if (m != mode) { mode = m; force_a = force_b = TRUE; }
    par_dbg_mode = m;

    /* plane A content */
    s16 want_pa = far ? 1 + (s16)(far - par_far) : 0;
    if (want_pa != pa_content) {
        if (far) load_far(far);
        else DMA_queueDma(DMA_VRAM, (void *)star_map, VRAM_PLANE_A, 64 * 32, 2);   /* 512-aligned blob */
        pa_content = want_pa;
    }

    /* plane B band and the H-scroll mode */
    par_dbg_band = band;
    s16 vs = (s16)(mul16(cam_y, PAR_STAR_V_SPEED) >> 4);
    u8 h = HSCROLL_TILE;
    if ((m == M_ROWS && (vs & 7)) || ((l0 | l1) & 7)) h = HSCROLL_LINE;
    if (h != tab_h) { tab_h = h; force_a = force_b = TRUE; }
    s16 n = h == HSCROLL_LINE ? 224 : 28, sh = h == HSCROLL_LINE ? 0 : 3;

    /* plane A */
    if (m == M_FAR) {
        s16 x = cam_x - off;
        if (force_a || x != last_a[0]) { fill(hs_a, -x, n); last_a[0] = x; force_a = TRUE; }
        VDP_setVerticalScrollVSync(BG_A, cam_y);
    } else if (m == M_COLS) {
        /* columns: A at its layer's speed, B at the camera; A's H-scroll stays 0 (16-px aligned,
         * so the partly shown left column never needs a V-scroll value) */
        s16 ly[PAR_STAR_LAYERS];
        for (u16 d = 0; d < PAR_STAR_LAYERS; d++) ly[d] = (s16)(mul16(cam_y, par_star_speed[d]) >> 4);
        for (u16 c = 0; c < 20; c++) {
            vsram[c * 2] = ly[par_star_col[c]];
            vsram[c * 2 + 1] = cam_y;
        }
        DMA_queueDmaFast(DMA_VSRAM, vsram, 0, 40, 2);
        if (force_a) fill(hs_a, 0, n);
    } else {
        s16 lx[PAR_STAR_LAYERS];
        bool same = !force_a && vs == last_a[PAR_STAR_LAYERS];
        for (u16 d = 0; d < PAR_STAR_LAYERS; d++) {
            lx[d] = (s16)(mul16(cam_x, par_star_speed[d]) >> 4);
            if (lx[d] != last_a[d]) same = FALSE;
        }
        if (!same) {
            /* entry i shows plane row ((i * step + vs) >> 3); runs of 8 / step entries per row.
             * row_layer[] (two periods, so no wrap) gives each row's layer; nw / nl hold the
             * layers' H-scroll values as words / word pairs (the first version of this loop
             * took ~7 lines for 28 entries, ~40 for 224) */
            s16 nw[PAR_STAR_LAYERS];
            u32 nl[PAR_STAR_LAYERS];
            for (u16 d = 0; d < PAR_STAR_LAYERS; d++) { u16 w = -lx[d]; nw[d] = w; nl[d] = ((u32)w << 16) | w; }
            const u8 *ro = &row_layer[(vs >> 3) & 31];
            s16 *dst = hs_a;
            if (h == HSCROLL_LINE) {
                /* the partial first row, full rows as 4 long stores, the partial last row */
                s16 run = 8 - (vs & 7), left = n - run, v = nw[*ro++];
                while (run--) *dst++ = v;
                for (; left >= 8; left -= 8) {
                    u32 vv = nl[*ro++], *d = (u32 *)dst;   /* 68000: long access needs only an even address */
                    d[0] = vv; d[1] = vv; d[2] = vv; d[3] = vv;
                    dst += 8;
                }
                v = nw[*ro];
                while (left-- > 0) *dst++ = v;
            } else {
                for (s16 i = n; i > 0; i--) *dst++ = nw[*ro++];
            }
            for (u16 d = 0; d < PAR_STAR_LAYERS; d++) last_a[d] = lx[d];
            last_a[PAR_STAR_LAYERS] = vs;
            force_a = TRUE;
        }
        VDP_setVerticalScrollVSync(BG_A, vs);
    }
    if (m != M_COLS) VDP_setVerticalScrollVSync(BG_B, cam_y);

    /* plane B */
    if (force_b || cam_x != last_b[0] || bx != last_b[1] || l0 != last_b[2]) {
        s16 e0 = l0 >> sh, e1 = l1 >> sh;
        fill(hs_b, -cam_x, e0);
        fill(hs_b + e0, -bx, e1 - e0);
        fill(hs_b + e1, -cam_x, n - e1);
        last_b[0] = cam_x; last_b[1] = bx; last_b[2] = l0;
        force_b = TRUE;
    }

    /* queue: tables first, then the mode switch (VBlank callback, after the DMA flush) */
    u16 stride = h == HSCROLL_LINE ? 4 : 32;
    if (force_a) DMA_queueDmaFast(DMA_VRAM, hs_a, VRAM_HSCROLL, n, stride);
    if (force_b) DMA_queueDmaFast(DMA_VRAM, hs_b, VRAM_HSCROLL + 2, n, stride);
    force_a = force_b = FALSE;
    set_reg(h, m == M_COLS ? VSCROLL_COLUMN : VSCROLL_PLANE);
}
