#pragma once
#include <genesis.h>
#include "player.h"
void spr_shots(const Shot *shot, u16 n);

/* Sprite display list in Genesis screen coordinates. Submit in front-to-back
 * order: the first sprite submitted is drawn on top. Graphics are the arcade's
 * 16x16 cells (code 0-2047, arcade colour 0-15), pre-converted at build time. */

#define SPR_FLIPX 1
#define SPR_FLIPY 2

void spr_init(void);
void spr_begin(void);
/* BC cached-key entry points require this frame-begin variant. */
void spr_bc_begin(void);
void spr_16(u16 code, u8 colour, s16 x, s16 y, u8 flags);   /* one 16x16 cell */
void spr_32(u16 code, u8 colour, s16 x, s16 y, u8 flags);   /* 2x2 cells c, c+1, c+8, c+9 */
void spr_tile32(u16 tile, u8 pal, s16 x, s16 y);  /* caller-owned VRAM patterns (bosses), pal 0/1 = PAL2/3 */
void spr_tile32_flags(u16 tile, u8 pal, s16 x, s16 y, u8 flags); /* shared/mirrored resident boss blocks */
void spr_tile16(u16 tile, u8 pal, s16 x, s16 y);  /* same, 16x16 */
void spr_end(void);
/* Lower only sprites intersecting the top window so its prompt stays legible. */
void spr_under_window(u16 height);
u16 spr_uploads(void);
/* Three identical BC straight shots spaced eight pixels apart, rendered as
 * one exact 32x16 composite. ascending describes original submission order. */
void spr_bc_straight3(s16 x, s16 y, u8 flags, u8 ascending);

/* Mark a submission range, then select installed scene banks 0/1 for it.
 * Preserves each sprite's bank parity, pattern, priority and flips. */
u16 spr_mark(void);
void spr_scene_palettes(u16 first);

/* Precomputed (code & 0x7ff) | ((colour & 15) << 11), same rendering rules. */
void spr_key16(u16 key, s16 x, s16 y, u8 flags);
void spr_key32(u16 key, s16 x, s16 y, u8 flags);

/* Specialized cached-key entry points for BC actor rendering. */
void spr_bc_key16(u16 key, s16 x, s16 y, u8 flags);
void spr_bc_key32(u16 key, s16 x, s16 y, u8 flags);

/* A bucket remains at a stable address across cache resets/evictions, but its
 * contents are always checked by full key. Refresh when key or size changes. */
void *spr_bc_bucket(u16 key, u8 size);
void spr_bc_hint32(void *bucket, u16 key, s16 x, s16 y, u8 flags);

/* Precomputed hardware X/Y flip bits0x0800/0x1000, used by cached BC actors. */
void spr_bc_bits16(u16 key, s16 x, s16 y, u16 bits);
void spr_bc_bits32(void *bucket, u16 key, s16 x, s16 y, u16 bits);

/* Cropped BC poses selected once by the actor pose cache. Coordinates retain
 * the original 32x32 origin; these functions preserve its visible pixels. */
void spr_bc_surfacer32(s16 x, s16 y, u16 bits);
void spr_bc_pod32(s16 x, s16 y, u16 bits);
void spr_bc_spike32(void *bucket, s16 x, s16 y, u16 bits);

/* Last picture needed substantial pattern streaming; avoid extra catch-up. */
bool spr_stream_busy(void);
