#include "game.h"

/* Pads. The physical pad (pad_raw, SGDK BUTTON_* bits) goes through the control mapping
 * (pad_cfg, Home OPTIONS > CONTROLS) into the logical inputs the game reads (pad[], IN_*):
 *   default   A = fire left (arcade button 1), B = fire right (button 2), C = weapon select
 *             (button 3), Start = start / coin;
 *   6-button  X / Y / Z: previous / next / a given weapon (pad_weapon_req, weapon_select()) or a
 *             "lock" fire button that fires towards the current facing without turning;
 *   autofire  per fire button: a held button becomes one press every 4 frames (on 2, off 2),
 *             the cadence of the arcade's AUTO weapon $10 (1 shot / 4 frames, B2:$8BEA); the
 *             arcade itself fires one normal shot per press (latch +$06, B2:$86E2). */
Pad pad[2];
u8 pad_fire_held[2];
RawPad pad_raw[2];
bool pad_six[2];
PadConfig pad_cfg;
u8 pad_weapon_req[2];
volatile u8 dbg_pad_override;     /* test hook: host tool writes pad[] directly */

static const u16 PB_BIT[PB_COUNT] = { BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_X, BUTTON_Y, BUTTON_Z };
static const u16 XYZ_BIT[3] = { BUTTON_X, BUTTON_Y, BUTTON_Z };
static const u8 ACT_IN[ACT_COUNT] = { IN_FIRE_L, IN_FIRE_R, IN_WEAPON };
static u8 af_t[2][2];             /* autofire: frames the fire button has been held */

void input_defaults(PadConfig *c)
{
    c->button[ACT_FIRE_L] = PB_A;
    c->button[ACT_FIRE_R] = PB_B;
    c->button[ACT_WEAPON] = PB_C;
    c->extra[0] = XB_PREV;
    c->extra[1] = XB_NEXT;
    c->extra[2] = XB_LOCK;
    c->autofire[0] = c->autofire[1] = 0;
}

void input_clear_requests(void) { pad_weapon_req[0] = pad_weapon_req[1] = 0; }

static u8 map(u16 i, u16 r, u16 pressed)
{
    u8 b = 0;
    if (r & BUTTON_RIGHT) b |= IN_RIGHT;
    if (r & BUTTON_LEFT) b |= IN_LEFT;
    if (r & BUTTON_DOWN) b |= IN_DOWN;
    if (r & BUTTON_UP) b |= IN_UP;
    if (r & BUTTON_START) b |= IN_START;
    for (u16 a = 0; a < ACT_COUNT; a++) {
        u8 btn = pad_cfg.button[a];
        if (btn >= PB_COUNT || (btn >= PB_X && !pad_six[i])) btn = a;   /* A / B / C */
        if (r & PB_BIT[btn]) b |= ACT_IN[a];
    }
    const Player *p = &players[i];
    if (pad_six[i])
        for (u16 k = 0; k < 3; k++) {
            u8 x = pad_cfg.extra[k];
            if (x == XB_LOCK) {
                if (r & XYZ_BIT[k]) b |= p->facing_left ? IN_FIRE_L : IN_FIRE_R;
            } else if (x != XB_NONE && x < XB_COUNT && (pressed & XYZ_BIT[k])) pad_weapon_req[i] = x;
        }
    pad_fire_held[i] = b & (IN_FIRE_L | IN_FIRE_R);
    /* The combined leader still uses the press latch (B2:$831F, $86E2). Keep held
     * input separately for the ring, which repeats on frame phase ($8D51), like AUTO ($8BEA). */
    bool af = p->in_play && p->state == PL_ALIVE && p->weapon != WPN_AUTO &&
              (!combined || combined == i + 1);
    for (u16 k = 0; k < 2; k++) {
        u8 bit = k ? IN_FIRE_R : IN_FIRE_L;
        if (!(b & bit)) { af_t[i][k] = 0; continue; }
        if (af && pad_cfg.autofire[k] && (af_t[i][k]++ & 2)) b &= ~bit;
    }
    return b;
}

void input_update(void)
{
    if (dbg_pad_override) {
        /* the host wrote pad[]: the menus see the default buttons */
        for (u16 i = 0; i < 2; i++) {
            pad_fire_held[i] = pad[i].held & (IN_FIRE_L | IN_FIRE_R);
            u16 r = 0, p = 0;
            for (u16 k = 0; k < 8; k++) {
                static const u16 RAW[8] = { BUTTON_RIGHT, BUTTON_LEFT, BUTTON_DOWN, BUTTON_UP,
                                            BUTTON_A, BUTTON_B, BUTTON_C, BUTTON_START };
                if (pad[i].held & (1 << k)) r |= RAW[k];
                if (pad[i].pressed & (1 << k)) p |= RAW[k];
            }
            pad_raw[i].held = r; pad_raw[i].pressed = p;
        }
        return;
    }
    for (u16 i = 0; i < 2; i++) {
        u16 j = i ? JOY_2 : JOY_1;
        u16 r = JOY_readJoypad(j);
        pad_six[i] = JOY_getJoypadType(j) == JOY_TYPE_PAD6;
        pad_raw[i].pressed = r & ~pad_raw[i].held;
        pad_raw[i].held = r;
        u8 b = map(i, r, pad_raw[i].pressed);
        pad[i].pressed = b & ~pad[i].held;
        pad[i].held = b;
    }
}
