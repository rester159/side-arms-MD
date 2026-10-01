#include "game.h"

/* Pads: A = fire left (arcade button 1), B = fire right (button 2),
 * C = weapon select (button 3), Start = start. */
Pad pad[2];
volatile u8 dbg_pad_override;     /* test hook: host tool writes pad[] directly */

static u8 read(u16 j)
{
    u16 p = JOY_readJoypad(j);
    u8 b = 0;
    if (p & BUTTON_RIGHT) b |= IN_RIGHT;
    if (p & BUTTON_LEFT) b |= IN_LEFT;
    if (p & BUTTON_DOWN) b |= IN_DOWN;
    if (p & BUTTON_UP) b |= IN_UP;
    if (p & BUTTON_A) b |= IN_FIRE_L;
    if (p & BUTTON_B) b |= IN_FIRE_R;
    if (p & BUTTON_C) b |= IN_WEAPON;
    if (p & BUTTON_START) b |= IN_START;
    return b;
}

void input_update(void)
{
    if (dbg_pad_override) return;
    for (u16 i = 0; i < 2; i++) {
        u8 b = read(i ? JOY_2 : JOY_1);
        pad[i].pressed = b & ~pad[i].held;
        pad[i].held = b;
    }
}
