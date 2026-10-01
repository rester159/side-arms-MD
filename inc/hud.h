#pragma once
#include <genesis.h>

/* Text / HUD on the window plane (VRAM_WINDOW, high priority), 40x28 cells.
 *
 * The window plane is switched on per 8-pixel row by an H-interrupt (every 8
 * lines, register $12 = $80 "window from line 0" or $00 "no window"): rows
 * holding text (plus forced rows) show the window, the others show plane A's
 * starfield. All VRAM writes go through SGDK's DMA queue (flushed in VBlank);
 * the H-int only writes register $12.
 *
 * Glyphs are the arcade's 2bpp text-layer chars (a_10j; codes 0-1023, colour
 * 0-63 = arcade palette 768 + 4c), converted on first use with the build-time
 * pen LUT (txt_lut) into PAL2/PAL3. Two tile pools:
 *   game pool    HUD rows (0-2, 25-27) and all rows while sprites are in use:
 *                VRAM_FONT_TILE area + spare VRAM, always resident;
 *   screen pool  rows 3-24 on front-end screens (no sprites): the sprite
 *                pattern area, released by hud_screen_reset(). */

#define HUD_COLS 40
#define HUD_ROWS 28
#define HUD_ROW_BIT(r)  (1UL << (r))
#define HUD_ROWS_TOP    (HUD_ROW_BIT(0) | HUD_ROW_BIT(1) | HUD_ROW_BIT(2))
#define HUD_ROWS_BOTTOM (HUD_ROW_BIT(25) | HUD_ROW_BIT(26) | HUD_ROW_BIT(27))
#define HUD_ROWS_GAME   (HUD_ROWS_TOP | HUD_ROWS_BOTTOM)
#define HUD_ROWS_ALL    0x0FFFFFFFUL

/* arcade text chars */
#define CH_SPACE   0x27
#define CH_LIFE    0x40     /* lives icon, also the ranking diamond */
#define CH_BAR     0x9B     /* naming cursor letter */

/* VRAM use (tiles). Game pool ranges: 1352-1407, 1520-1535 (window rows
 * 28-31, never displayed), 1940-1951 (SAT bytes $280-$3FF: 80 sprites use
 * $280), 2033-2047 (after the sprite module's last 32x32 slot). */
#define HUD_BAR_TILE        1312            /* 2 x 20 weapon-bar tiles, streamed */
#define HUD_LOGO_TILE       1056            /* logo on front-end screens (sprite area) */
#define HUD_SCREEN_TILE     (1056 + 176)    /* screen pool: 80 tiles + 1664..1791 */

void hud_init(void);
void hud_frame(void);                       /* once per frame: queue the window/tile DMA */

void hud_rows(u32 mask);                    /* rows always shown; rows holding text are shown anyway */
u32 hud_rows_get(void);
void hud_sprites(bool on);                  /* sprites in use: all text goes to the game pool */
void hud_clear(u32 rows);                   /* blank these rows */
void hud_screen_reset(void);                /* blank rows 3-24, release the screen pool, hide the logo */

/* Genesis cell coordinates (40x28) */
void hud_codes(s16 col, s16 row, u8 colour, const u16 *codes, u16 n);   /* arcade char codes */
void hud_text(s16 col, s16 row, u8 colour, const char *s);   /* ASCII: A-Z 0-9 space . , : - + = ' " _ / ? ( ) < > # */
void hud_blank(s16 col, s16 row, u16 n);
void hud_string(u16 id, s16 col, s16 row);  /* build-time arcade string (gen/frontend.h); col/row < 0: its place */
void hud_string_clear(u16 id, s16 col, s16 row);
void hud_number(s16 col, s16 row, u8 colour, u32 v, u16 width);  /* right-aligned, leading blanks */
void hud_score(s16 col, s16 row, u8 colour, u32 points);         /* arcade score format ($0627), 8 cells */
void hud_logo(bool on, u16 vram_tile);      /* SIDE ARMS logo (rows 3-10); tiles uploaded at vram_tile */

/* Arcade text-layer position (64-col layer, visible cols 8-55, rows 2-29) ->
 * Genesis cell: (col - 12, row - 2), the 320-px view centred in the arcade's 384. */
#define HUD_ARCADE_COL(c)   ((s16)(c) - 12)
#define HUD_ARCADE_ROW(r)   ((s16)(r) - 2)

/* In-game panel: scores, lives, weapon bars, speed meters, per-player
 * messages, boss hit bars. Native 40-column layout:
 *   row 0   1UP  P1 score     HI hi score       2UP  P2 score
 *   row 1   P1 lives icons                      P2 lives icons
 *   row 2                          boss bars (right-aligned, arcade $D137)
 *   row 25  P1 NAMING / CONTINUE / GAME OVER    P2 ...
 *   row 26  P1 weapon bar (20 cells)            P2 weapon bar
 *   row 27  P1 SPEED + meter                    P2 SPEED + meter */
enum { HUD_MSG_NONE, HUD_MSG_NAMING, HUD_MSG_CONTINUE, HUD_MSG_GAMEOVER };
typedef struct {
    bool score;                 /* show the score */
    bool bar;                   /* weapon bar + speed meter + lives */
    u8 msg;                     /* HUD_MSG_* */
    u8 msg_arg;                 /* CONTINUE: 0-10; NAMING: 1 = label visible (blink) */
    u8 name[3];                 /* NAMING: letters as arcade codes */
} HudPlayer;
typedef struct {
    bool on;
    bool twoup;                 /* show the 2UP label */
    u32 hi;
    u8 boss_bars;               /* boss hit bars (0 = none) */
    HudPlayer pl[2];
} HudPanel;
void hud_panel(const HudPanel *p);          /* call every frame while it is shown (diffs internally) */
void hud_panel_off(void);
