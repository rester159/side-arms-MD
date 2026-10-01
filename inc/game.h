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
extern Pad pad[2];
void input_update(void);

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
