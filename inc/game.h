#pragma once
#include <genesis.h>

/* ---- input (input.c) ----------------------------------------------------- */
enum {
    IN_RIGHT = 1, IN_LEFT = 2, IN_DOWN = 4, IN_UP = 8,
    IN_FIRE_L = 0x10,   /* pad A: fire left  (arcade button 1) */
    IN_FIRE_R = 0x20,   /* pad B: fire right (arcade button 2) */
    IN_WEAPON = 0x40,   /* pad C: weapon select (arcade button 3) */
    IN_START = 0x80,
};
typedef struct { u8 held, pressed; } Pad;
extern Pad pad[2];                  /* logical game inputs (IN_*), after the control mapping */
void input_update(void);

/* Physical pad (SGDK BUTTON_* bits: A B C X Y Z MODE START + directions). Menus read these
 * (A / C / Start = select, B = back), the game reads pad[]. */
typedef struct { u16 held, pressed; } RawPad;
extern RawPad pad_raw[2];
extern bool pad_six[2];             /* a 6-button pad is plugged in (JOY_getJoypadType) */

/* Control mapping (Home OPTIONS > CONTROLS, saved in SRAM; docs/frontend.md). */
enum { PB_A, PB_B, PB_C, PB_X, PB_Y, PB_Z, PB_COUNT };          /* physical buttons */
enum { ACT_FIRE_L, ACT_FIRE_R, ACT_WEAPON, ACT_COUNT };        /* remappable actions */
enum {                              /* X / Y / Z extra functions (6-button pads) */
    XB_NONE, XB_PREV, XB_NEXT,      /* previous / next owned weapon */
    XB_BIT, XB_SG, XB_MBL, XB_3WAY, XB_AUTO,                  /* that weapon, if owned */
    XB_LOCK,                        /* hold: fire towards the current facing without turning */
    XB_COUNT
};
typedef struct {
    u8 button[ACT_COUNT];           /* PB_* per action; X/Y/Z fall back to A/B/C on a 3-button pad */
    u8 extra[3];                    /* XB_* for X, Y, Z */
    u8 autofire[2];                 /* per fire button (left, right): held = repeated presses */
} PadConfig;
extern PadConfig pad_cfg;
void input_defaults(PadConfig *c);
void input_clear_requests(void);    /* drop pending X/Y/Z weapon requests (attract demo) */
extern u8 pad_weapon_req[2];        /* XB_PREV..XB_AUTO pressed on X/Y/Z; consumed by weapon_select() */

/* ---- camera / level (level.c) ------------------------------------------- */
typedef enum { SCROLL_RUN, SCROLL_HALT } ScrollMode;
typedef struct {
    u16 section;            /* 0-9 */
    u16 next_event;
    s16 scroll_x, scroll_y; /* arcade scroll units; camera = scroll + (96, 16) */
    s8 dir_x, dir_y;        /* -1 / 0 / +1 */
    bool vertical;          /* arcade $E040 'V'/'H': last axis switched on in the + direction */
    ScrollMode mode;
    u8 rank;                /* enemy bullet speed / cap rank (arcade $E050/$E017) */
    u16 tick;               /* frames in section */
} Level;
extern Level level;
void level_start(u16 section);
void level_update(void);
void level_resume(void);            /* boss defeated */
static inline s16 cam_x(void);
static inline s16 cam_y(void);
bool terrain_solid(s16 wx, s16 wy); /* world pixel */

#include "player.h"

/* ---- game ---------------------------------------------------------------- */
extern u16 frame;
void game_init(void);
void game_update(void);
void game_draw(void);
void sound_play(u8 id);     /* arcade sound command numbers (docs/re/sound.md) */

#include "video.h"
static inline s16 cam_x(void) { return level.scroll_x + ARCADE_VIEW_X; }
static inline s16 cam_y(void) { return level.scroll_y + ARCADE_VIEW_Y; }
