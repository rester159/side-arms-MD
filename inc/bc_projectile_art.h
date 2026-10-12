#pragma once
#include "bc_rules.h"

typedef struct {
    unsigned short code;
    signed short x, y;
    unsigned char colour, flips, visible, handled;
} BcProjectileSprite;
BcProjectileSprite bc_projectile_sprite(const BcBeam *body,
    signed short viewport_x, signed short viewport_y);
/* Returns the number of live source frames that have no art mapping. */
unsigned char bc_projectiles_draw(const BcWeapons *weapons,
    signed short viewport_x, signed short viewport_y);
