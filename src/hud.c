#include "game.h"
#include "hud.h"
#include "gen/assets.h"
#include "gen/frontend.h"

/* Window-plane text and the in-game HUD (docs/frontend.md; arcade HUD
 * docs/re/flow_player.md §7). */

/* ---- window shadow ------------------------------------------------------ */
static u16 win[HUD_ROWS][HUD_COLS];         /* nametable entries, 0 = transparent */
static u32 dirty;                           /* rows to send */
static u8 used[HUD_ROWS];                   /* non-blank cells per row */
static u32 used_mask;                       /* rows with used[] != 0 */
static u32 forced;                          /* rows shown even when blank */
static bool sprites_on;
static volatile u32 win_mask;               /* rows showing the window (read by the H-int) */
static volatile u16 win_reg;                /* register $12 value currently set */

/* Window split. In game the window shows a top block of rows (scores) and a
 * bottom block (weapon bars): VDP register $12 can show either as one block
 * (bit 7 = 0: rows 0..V-1, bit 7 = 1: rows V..end), so the VBlank interrupt
 * sets the top block and a single H-int between the blocks switches to the
 * bottom block (2 register writes per frame). Any other row mask (text in the
 * middle rows) uses an H-int every 8 lines (counter 7: end of lines 7, 15, ...,
 * 223) that sets $80 (window from line 0, on) or $00 (off) for the row that
 * starts next. Every write is a single register write (no address/data pair).
 * The 28 interrupts of the general mode cost ~20 lines of 68000 time a frame. */
static volatile u16 split_top, split_bot;   /* simple mode: top rows 0..top-1, bottom rows bot..27 */
static volatile bool split_simple;
static bool split_valid;                    /* next_* computed for frame_mask */
/* The row mask and split of the next frame: computed by hud_frame() during the frame and
 * applied by the VBlank interrupt, together with the nametable DMA of the same rows. (Applied at
 * once, a cleared row would vanish one frame before its text and new text would show one frame
 * late: blinking text measured 23 on / 13 off instead of 24 / 12.) */
static u32 frame_mask;
static volatile u32 next_mask;
static volatile u16 next_top, next_bot;
static volatile bool next_simple, next_ready;

HINTERRUPT_CALLBACK hud_hint(void)
{
    if (split_simple) {
        u16 want = 0x80 | split_bot;
        if (want != win_reg) { win_reg = want; *(vu16 *)VDP_CTRL_PORT = 0x9200 | want; }
        return;
    }
    u16 row = (GET_VCOUNTER + 1) >> 3;
    if (row >= HUD_ROWS) row = 0;
    u16 want = (win_mask >> row) & 1 ? 0x80 : 0x00;
    if (want != win_reg) {
        win_reg = want;
        *(vu16 *)VDP_CTRL_PORT = 0x9200 | want;
    }
}

/* VBlank interrupt: the next frame's first window state and H-int spacing */
static void hud_vint(void)
{
    if (next_ready) {
        win_mask = next_mask;
        split_top = next_top; split_bot = next_bot; split_simple = next_simple;
        next_ready = FALSE;
    }
    if (split_simple) {
        u16 top = split_top, bot = split_bot;
        win_reg = top;                                  /* up mode: rows 0..top-1 */
        *(vu16 *)VDP_CTRL_PORT = 0x9200 | top;
        /* one H-int between the blocks; the counter reloads in VBlank, so a second one
         * (at 2N+1) only rewrites the same value */
        u16 n = bot >= HUD_ROWS ? 255 : (top * 8 + bot * 8) / 2;
        *(vu16 *)VDP_CTRL_PORT = 0x8A00 | (n > 255 ? 255 : n);
    } else {
        u16 want = (win_mask & 1) ? 0x80 : 0x00;
        win_reg = want;
        *(vu16 *)VDP_CTRL_PORT = 0x9200 | want;
        *(vu16 *)VDP_CTRL_PORT = 0x8A00 | 7;
    }
}

void hud_rows(u32 mask) { forced = mask; }
u32 hud_rows_get(void) { return win_mask; }
void hud_sprites(bool on) { sprites_on = on; }

/* ---- glyph pools ------------------------------------------------------- */
#define HASH 256
#define RANGES 4
typedef struct {
    u16 base[RANGES], n[RANGES];
    u16 used, cap;
    u16 key[HASH], val[HASH];               /* key = (code | colour << 10) + 1, 0 = empty */
} GlyphPool;
static GlyphPool game_pool, screen_pool;

static void pool_reset(GlyphPool *p, const u16 *ranges, u16 nr)
{
    memset(p, 0, sizeof(*p));
    for (u16 i = 0; i < nr; i++) { p->base[i] = ranges[2 * i]; p->n[i] = ranges[2 * i + 1]; p->cap += p->n[i]; }
}

static u16 pool_tile(const GlyphPool *p, u16 slot)
{
    for (u16 i = 0; i < RANGES; i++) {
        if (slot < p->n[i]) return p->base[i] + slot;
        slot -= p->n[i];
    }
    return 0;
}

/* staged tile uploads: a run of consecutive VRAM tiles, sent with one
 * DMA_QUEUE_COPY (the data is copied into SGDK's DMA buffer at once) */
#define STAGE_MAX 32
static u32 stage[STAGE_MAX][8];
static u16 stage_tile, stage_n;

static void stage_flush(void)
{
    if (!stage_n) return;
    VDP_loadTileData(stage[0], stage_tile, stage_n, DMA_QUEUE_COPY);
    stage_n = 0;
}

static u32 *stage_slot(u16 tile)
{
    if (stage_n && (stage_n == STAGE_MAX || tile != stage_tile + stage_n)) stage_flush();
    if (!stage_n) stage_tile = tile;
    return stage[stage_n++];
}

static void convert(u32 *dst, u16 code, u8 colour)
{
    const u8 *src = font_pens + (u32)code * 32;
    const u8 *lut = txt_lut + (u16)colour * 256;
    u8 *d = (u8 *)dst;
    for (u16 i = 0; i < 32; i++) d[i] = lut[src[i]];
}

/* Nametable entry for (code, colour): converted and uploaded on first use. */
static u16 glyph(GlyphPool *p, u16 code, u8 colour)
{
    code &= 0x3FF; colour &= 63;
    if (font_blank[code]) return 0;
    u16 k = (code | (colour << 10)) + 1;
    u16 h = (code * 7 + colour * 31) & (HASH - 1);
    while (p->key[h]) {
        if (p->key[h] == k) return p->val[h];
        h = (h + 1) & (HASH - 1);
    }
    if (p->used >= p->cap)              /* full: the colour-0 glyph if resident, else blank */
        return colour ? glyph(p, code, 0) : 0;
    u16 tile = pool_tile(p, p->used++);
    convert(stage_slot(tile), code, colour);
    p->key[h] = k;
    p->val[h] = TILE_ATTR_FULL(PAL2 + (txt_pal[colour] & 1), 1, 0, 0, tile);
    return p->val[h];
}

static GlyphPool *pool_for(s16 row)
{
    return (sprites_on || row <= 2 || row >= 25) ? &game_pool : &screen_pool;
}

/* ---- text ---------------------------------------------------------------- */
static bool cell_ok(s16 col, s16 row) { return col >= 0 && col < HUD_COLS && row >= 0 && row < HUD_ROWS; }

static void put(s16 col, s16 row, u16 v)
{
    if (!cell_ok(col, row) || win[row][col] == v) return;
    if (!win[row][col]) { if (!used[row]++) used_mask |= HUD_ROW_BIT(row); }
    else if (!v) { if (!--used[row]) used_mask &= ~HUD_ROW_BIT(row); }
    win[row][col] = v;
    dirty |= HUD_ROW_BIT(row);
}

void hud_codes(s16 col, s16 row, u8 colour, const u16 *codes, u16 n)
{
    if (row < 0 || row >= HUD_ROWS) return;
    GlyphPool *p = pool_for(row);
    for (u16 i = 0; i < n; i++, col++)
        if (cell_ok(col, row)) put(col, row, glyph(p, codes[i], colour));
}

void hud_blank(s16 col, s16 row, u16 n)
{
    for (u16 i = 0; i < n; i++) put(col + i, row, 0);
}

void hud_clear(u32 rows)
{
    for (u16 r = 0; r < HUD_ROWS; r++)
        if (rows & HUD_ROW_BIT(r)) hud_blank(0, r, HUD_COLS);
}

static u16 ascii(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'Z') return 0x0A + c - 'A';
    if (c >= 'a' && c <= 'z') return 0x0A + c - 'a';
    switch (c) {
    case '.': return 0x2B;
    case ',': return 0x2A;
    case ':': return 0x2C;
    case '-': return 0x37;
    case '=': return 0x38;
    case '+': return 0x36;
    case '\'': return 0x39;
    case '"': return 0x3A;
    case '_': return 0x3B;
    case '/': return 0x45;
    case '?': return 0x35;
    case '(': return 0x30;
    case ')': return 0x31;
    case '<': return 0x32;
    case '>': return 0x33;
    case '#': return 0x2F;
    case '*': return 0x42;      /* star */
    case '^': return CH_LIFE;   /* diamond */
    case '@': return 0x4F;      /* copyright */
    default: return CH_SPACE;
    }
}

void hud_text(s16 col, s16 row, u8 colour, const char *s)
{
    if (row < 0 || row >= HUD_ROWS) return;
    GlyphPool *p = pool_for(row);
    for (; *s; s++, col++)
        if (cell_ok(col, row)) put(col, row, glyph(p, ascii(*s), colour));
}

void hud_string(u16 id, s16 col, s16 row)
{
    const FeString *s = &fe_strings[id];
    if (col < 0) col = s->col;
    if (row < 0) row = s->row;
    for (u16 r = 0; r < s->rows; r++)
        hud_codes(col, row + r, s->colour, fe_string_codes + s->offset + r * s->cols, s->cols);
}

void hud_string_clear(u16 id, s16 col, s16 row)
{
    const FeString *s = &fe_strings[id];
    if (col < 0) col = s->col;
    if (row < 0) row = s->row;
    for (u16 r = 0; r < s->rows; r++) hud_blank(col, row + r, s->cols);
}

/* Decimal digits without 32-bit division (the 68000 has none: libgcc's divide
 * costs ~1000 cycles a call, and a score update needed 16 of them). n <= 10. */
static void to_digits(u32 v, u8 *d, u16 n)
{
    static const u32 POW10[10] = { 1, 10, 100, 1000, 10000, 100000, 1000000, 10000000, 100000000, 1000000000 };
    for (s16 i = n - 1; i >= 0; i--) {
        u32 p = POW10[i];
        u8 k = 0;
        while (v >= p) { v -= p; k++; }
        d[n - 1 - i] = k;                       /* most significant first; overflow piles into d[0] */
    }
}

/* Nametable entries of the digits 0-9 in colour 0 of the game pool (scores, counters):
 * looked up once, since scores change on most kills (3 numbers a frame in 2P) */
static u16 digit_cache[10];

static u16 digit(GlyphPool *p, u8 d, u8 colour)
{
    if (p != &game_pool || colour) return glyph(p, d, colour);
    if (!digit_cache[d]) digit_cache[d] = glyph(p, d, 0);
    return digit_cache[d];
}

void hud_number(s16 col, s16 row, u8 colour, u32 v, u16 width)
{
    if (row < 0 || row >= HUD_ROWS || width > 10) return;
    GlyphPool *p = pool_for(row);
    u8 d[10];
    to_digits(v, d, width);
    bool lead = TRUE;
    for (u16 i = 0; i < width; i++) {
        if (d[i] || i == width - 1) lead = FALSE;
        put(col + i, row, lead ? 0 : digit(p, d[i] > 9 ? 9 : d[i], colour));
    }
}

/* $0627: 7 digits (points / 10) with leading zeros left blank, then a fixed
 * '0'; a zero score shows nothing. Points are multiples of 10, so the shown
 * digits are digits 1-7 of the points. */
void hud_score(s16 col, s16 row, u8 colour, u32 points)
{
    if (row < 0 || row >= HUD_ROWS) return;
    u8 d[9];
    to_digits(points, d, 9);                    /* d[0] = 10^8 ... d[8] = units */
    bool any = FALSE;
    for (u16 i = 1; i < 8; i++) if (d[i]) any = TRUE;
    if (!any) { hud_blank(col, row, 8); return; }
    GlyphPool *p = pool_for(row);
    bool lead = TRUE;
    for (u16 i = 1; i < 8; i++) {
        if (d[i]) lead = FALSE;
        put(col + i - 1, row, lead ? 0 : digit(p, d[i], colour));
    }
    put(col + 7, row, digit(p, 0, colour));
}

/* ---- logo ($0DF5) ---------------------------------------------------------- */
static bool logo_on;
#define LOGO_ROWS (0xFFUL << FE_LOGO_ROW)

/* a pre-rendered block (map entries: 0 blank, else (tile + 1) | palette bit 13 | flips), its
 * tiles uploaded at vram_tile */
static void image(const u16 *m, u16 cols, u16 rows, s16 col, s16 row, const u8 *tiles, u16 ntiles, u16 vram_tile)
{
    DMA_queueDma(DMA_VRAM, (void *)tiles, vram_tile * 32, ntiles * 16, 2);
    for (u16 r = 0; r < rows; r++)
        for (u16 c = 0; c < cols; c++, m++) {
            u16 e = *m;
            put(col + c, row + r, e ? (0x8000 | ((2 + ((e >> 13) & 1)) << 13) | (e & 0x1800) |
                                     ((e & 0x7FF) - 1 + vram_tile)) : 0);
        }
}

void hud_logo(bool on, u16 vram_tile)
{
    if (!on) {
        if (logo_on) hud_clear(LOGO_ROWS);
        logo_on = FALSE;
        return;
    }
    image(fe_logo_map, 32, 8, FE_LOGO_COL, FE_LOGO_ROW, fe_logo_tiles, FE_LOGO_TILES, vram_tile);
    logo_on = TRUE;
}

void hud_md(s16 col, s16 row, u16 vram_tile)
{
    image(fe_md_map, FE_MD_COLS, FE_MD_ROWS, col, row, fe_md_tiles, FE_MD_TILES, vram_tile);
}

void hud_screen_reset(void)
{
    static const u16 r[] = { HUD_SCREEN_TILE, 1312 - HUD_SCREEN_TILE, 1664, 128 };
    hud_clear(HUD_ROWS_ALL & ~HUD_ROWS_GAME);
    logo_on = FALSE;
    pool_reset(&screen_pool, r, 2);
}

/* ---- in-game panel ----------------------------------------------------------- */
#define COL_P(i)    ((i) * 20)
static const s16 SCORE_COL[2] = { 4, 32 };
static const s16 LABEL_COL[2] = { 0, 28 };
#define HI_LABEL_COL 14
#define HI_COL       17

static struct {
    bool on, twoup;
    u32 hi, score[2];
    bool score_on[2], bar_on[2];
    u8 lives[2], msg[2], arg[2], name[2][3];
    u8 slot[2][5], speed[2], phase[2];
    u8 boss;
} cur;

void hud_panel_off(void)
{
    if (!cur.on) return;
    cur.on = FALSE;
    hud_clear(HUD_ROWS_GAME);
}

static void bar_slot(u16 i, u16 s, u8 state)
{
    /* $1E7C: 4 cells per weapon, colour $20 none / $25 owned / $23-$24 selected;
     * glyphs are streamed into this player's 20 bar tiles */
    u16 tile = HUD_BAR_TILE + i * 20 + s * 4;
    /* fe_bar_tiles is 512-byte aligned (data.s): a 128-byte run never crosses 128 KB */
    DMA_queueDmaFast(DMA_VRAM, (void *)(fe_bar_tiles + (state * 20 + s * 4) * 32), tile * 32, 64, 2);
    for (u16 k = 0; k < 4; k++)
        put(COL_P(i) + s * 4 + k, 26, TILE_ATTR_FULL(PAL2 + (fe_bar_pal[state] & 1), 1, 0, 0, tile + k));
    cur.slot[i][s] = state;
}

static u16 speed_cache[2][3][4];

static void draw_speed(u16 i, u8 speed, u8 phase)
{
    /* $275D: 12 cells after the label, speed x ($78,$79,$7A,$7B); colours flash
     * $27/$29/$2B <-> $28/$2A/$2C with frame bit 2 ($1EE2) */
    static const u16 seg[4] = { 0x78, 0x79, 0x79, 0x7B };     /* $7A draws like $79 */
    for (u16 k = 0; k < 3; k++) {
        s16 col = COL_P(i) + 8 + k * 4;
        if (k < speed) {
            /* the 24 entries (2 phases x 3 colours x 4 glyphs) flash every 4 frames:
             * looked up once, then reused (game pool glyphs live until hud_init) */
            u16 *e = speed_cache[phase ? 1 : 0][k];
            if (!e[0]) for (u16 n = 0; n < 4; n++) e[n] = glyph(&game_pool, seg[n], 0x27 + k * 2 + (phase ? 1 : 0));
            for (u16 n = 0; n < 4; n++) put(col + n, 27, e[n]);
        }
        else hud_blank(col, 27, 4);
    }
    cur.speed[i] = speed; cur.phase[i] = phase;
}

static void draw_msg(u16 i, const HudPlayer *h)
{
    s16 c = COL_P(i);
    hud_blank(c, 25, 20);
    switch (h->msg) {
    case HUD_MSG_NAMING:      /* $16F6: "NAMING" blinking, three letters two cells apart */
        if (h->msg_arg) hud_codes(c + 1, 25, 0, fe_string_codes + fe_strings[FE_STR_NAMING].offset, 6);
        for (u16 k = 0; k < 3; k++) { u16 ch = h->name[k]; hud_codes(c + 8 + k * 2, 25, 0, &ch, 1); }
        break;
    case HUD_MSG_CONTINUE:    /* $1D4E: "CONTINUE" + 2 digits */
        hud_codes(c + 3, 25, 0, fe_string_codes + fe_strings[FE_STR_CONTINUE].offset, 8);
        hud_number(c + 11, 25, 0, h->msg_arg, 2);
        break;
    case HUD_MSG_GAMEOVER:    /* $1D6C, colour 4 */
        hud_string(FE_STR_GAMEOVER, c + 3, 25);
        break;
    }
    cur.msg[i] = h->msg; cur.arg[i] = h->msg_arg;
    memcpy(cur.name[i], h->name, 3);
}

void hud_panel(const HudPanel *p)
{
    if (!p->on) { hud_panel_off(); return; }
    if (!cur.on) {
        memset(&cur, 0xFF, sizeof(cur));
        cur.on = TRUE;
        cur.boss = 0;
        hud_clear(HUD_ROWS_GAME);
        hud_string(FE_STR_ONEUP, LABEL_COL[0], 0);
        hud_string(FE_STR_HI, HI_LABEL_COL, 0);
    }
    if (p->twoup != cur.twoup) {
        if (p->twoup) hud_string(FE_STR_TWOUP, LABEL_COL[1], 0); else hud_blank(LABEL_COL[1], 0, 3);
        cur.twoup = p->twoup;
    }
    if (p->hi != cur.hi) { hud_score(HI_COL, 0, 0, p->hi); cur.hi = p->hi; }
    if (p->boss_bars != cur.boss) {
        /* $089F: one group $6C-$6F per remaining bar, right-aligned (colour 0) */
        static const u16 grp[4] = { 0x6C, 0x6D, 0x6E, 0x6F };
        u8 n = p->boss_bars > 8 ? 8 : p->boss_bars;
        hud_blank(0, 2, HUD_COLS);
        for (u16 k = 0; k < n; k++) hud_codes(HUD_COLS - 4 * (k + 1), 2, 0, grp, 4);
        cur.boss = p->boss_bars;
    }
    for (u16 i = 0; i < 2; i++) {
        const HudPlayer *h = &p->pl[i];
        const Player *pl = &players[i];
        u32 sc = h->score ? pl->score : 0;
        if (h->score != cur.score_on[i] || sc != cur.score[i]) {
            hud_score(SCORE_COL[i], 0, 0, sc);
            cur.score[i] = sc; cur.score_on[i] = h->score;
        }
        /* $067B: lives - 1 icons, at most 5 */
        u8 lv = h->bar && pl->lives > 1 ? pl->lives - 1 : 0;
        if (lv > 5) lv = 5;
        if (lv != cur.lives[i]) {
            static const u16 icon = CH_LIFE;
            for (u16 k = 0; k < 5; k++) {
                if (k < lv) hud_codes(LABEL_COL[i] + k, 1, 0, &icon, 1);
                else hud_blank(LABEL_COL[i] + k, 1, 1);
            }
            cur.lives[i] = lv;
        }
        if (h->msg != cur.msg[i] || h->msg_arg != cur.arg[i] || memcmp(h->name, cur.name[i], 3))
            draw_msg(i, h);
        if (h->bar != cur.bar_on[i]) {
            if (!h->bar) { hud_blank(COL_P(i), 26, 20); hud_blank(COL_P(i), 27, 20); }
            else {
                static const u16 speed_label[8] = { 0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77 };
                hud_codes(COL_P(i), 27, 0x2F, speed_label, 8);      /* $19F0 attr $2F */
                for (u16 s = 0; s < 5; s++) cur.slot[i][s] = 0xFF;
                cur.speed[i] = 0xFF;
            }
            cur.bar_on[i] = h->bar;
        }
        if (h->bar) {
            u8 flash = (frame & 4) ? 3 : 2;
            for (u16 s = 0; s < 5; s++) {
                u8 st = pl->level[s + 1] ? 1 : 0;
                if (pl->weapon == s + 1) st = flash;
                if (st != cur.slot[i][s]) bar_slot(i, s, st);
            }
            u8 sp = pl->speed > 3 ? 3 : pl->speed, ph = (frame & 4) ? 1 : 0;
            if (sp != cur.speed[i] || ph != cur.phase[i]) draw_speed(i, sp, ph);
        }
    }
}

/* ---- frame / init --------------------------------------------------------- */
void hud_frame(void)
{
    stage_flush();
    u32 m = forced | used_mask;
    if (m != frame_mask || !split_valid) {
        frame_mask = m;
        /* top block + bottom block (possibly empty)? */
        u16 top = 0, bot = HUD_ROWS;
        while (top < HUD_ROWS && (m >> top) & 1) top++;
        while (bot > top && (m >> (bot - 1)) & 1) bot--;
        bool simple = TRUE;
        for (u16 r = top; r < bot; r++) if ((m >> r) & 1) { simple = FALSE; break; }
        SYS_disableInts();
        next_mask = m; next_top = top; next_bot = bot; next_simple = simple; next_ready = TRUE;
        SYS_enableInts();
        split_valid = TRUE;
    }
    for (u16 r = 0; dirty && r < HUD_ROWS; r++) {
        if (!(dirty & HUD_ROW_BIT(r))) continue;
        dirty &= ~HUD_ROW_BIT(r);
        DMA_queueDmaFast(DMA_VRAM, win[r], VRAM_WINDOW + r * 128, HUD_COLS, 2);
    }
}

void hud_init(void)
{
    static const u16 g[] = { 1352, 56, 1520, 16, 1940, 12, 2033, 15 };
    memset(win, 0, sizeof(win));
    memset(used, 0, sizeof(used));
    used_mask = 0;
    split_valid = FALSE;
    frame_mask = 0;
    next_ready = FALSE;
    memset(&cur, 0, sizeof(cur));
    forced = 0;
    sprites_on = FALSE;
    dirty = HUD_ROWS_ALL;
    stage_n = 0;
    pool_reset(&game_pool, g, 4);
    memset(speed_cache, 0, sizeof(speed_cache));
    memset(digit_cache, 0, sizeof(digit_cache));
    hud_screen_reset();
    win_mask = 0;
    win_reg = 0;
    VDP_setWindowHPos(FALSE, 0);
    VDP_setWindowVPos(FALSE, 0);
    split_simple = FALSE;
    SYS_setHIntCallback(hud_hint);
    SYS_setVIntCallback(hud_vint);
    VDP_setHIntCounter(7);
    VDP_setHInterrupt(TRUE);
}
