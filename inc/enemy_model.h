#pragma once
#include <genesis.h>

/* Storage accommodates Home 3P/4P. Allocation retains arcade limits (16 small, 9 big)
 * for 1P/2P; full pools drop new objects, as in the arcade (docs/re/objects.md 1.1). */
enum { EP_SMALL, EP_BIG, EP_ITEM };
#define N_SMALL  40     /* 1x1 objects: enemy bullets, missiles, bombs, snake segments ($F000) */
#define N_BIG    24     /* 2x2 enemies ($F600-$FA7F) */
#define N_ITEM    8     /* pickups, hidden bonuses, mines, orb fragments ($FF00) */

/* Object flags: same bit meanings as the arcade record's +$09 (the generator copies them). */
#define EF_SHOTPROOF    0x01    /* player shots pass through */
#define EF_NOCONTACT    0x02    /* no contact with the players */
#define EF_NOTERRAIN    0x04    /* no terrain test */
#define EF_BGLOCK       0x20    /* moves with the background (camera) */
#define EF_KILLREQ      0x40    /* dies on its next update */
#define EF_NATIVEDEATH  0x80    /* death = behaviour function instead of a death script */

typedef struct Enemy {
    u8 live;            /* 0 = free slot */
    u8 pool;            /* EP_* */
    u8 flags;           /* EF_* */
    u8 cat;             /* arcade category (+$07); 0 = enemy bullet (counted for the cap) */
    s16 x, y;           /* Genesis screen px of the sprite's top-left (arcade sprite - (96, 16)) */
    s8 dy, dx;          /* px per frame */
    u8 timer;           /* frames left in the current motion step */
    u8 colour;
    u16 code;           /* arcade sprite code (2x2 objects: top-left cell) */
    u16 next;           /* motion step loaded when the timer runs out */
    u8 hp;
    u8 item;            /* 0 = hostile, else pickup code (player_apply_item) */
    u8 box[4];          /* shot box half-h, half-w/2; contact box half-h, half-w/2 (arcade +$0C-$0F) */
    u8 r[10];           /* per-family state (arcade +$10..+$19): r[5] score index, r[6] last aim, r[8] carried letter */
    u8 wall;            /* AI id of the terrain handler (0 = none) */
    u8 sub_y;           /* 2x2 objects: arcade y of the top cells after the last move (+$22) */
    u16 death;          /* death script step, or AI id when flags & EF_NATIVEDEATH */
    s16 sub_x;          /* 2x2 objects: arcade x of the right cells after the last move (+$23) */
    u16 spare;
} Enemy;
