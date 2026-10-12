#pragma once
#include "bc_world.h"

typedef struct {
    unsigned short code;
    signed short x, y;
    unsigned char colour, flips, size, visible, handled;
} BcActorSprite;
/* Existing Genesis creatures, pickups and projectile/effect art selected by
 * BC source frames. Unmapped families remain explicit. Simulation is read-only. */
/* Packed pose: code[0:10], colour[11:14], flips[16:17], large[18],
 * visible[19], handled[20]. No coordinates or mutable cache residency. */
unsigned int bc_actor_pose(const BcActor *actor);
/* Original PCE shared-projectile variants, selected only during boss encounters. */
unsigned int bc_actor_boss_pose(const BcActor *actor);
BcActorSprite bc_actor_boss_sprite(const BcActor *actor, signed short viewport_x,
    signed short viewport_y);
BcActorSprite bc_actor_sprite(const BcActor *actor, signed short viewport_x,
    signed short viewport_y);
/* Packed result: low byte unmapped art, high byte live actors (both <=32). */
unsigned short bc_actors_draw(const BcActor actors[BC_ACTOR_CAPACITY],
    signed short viewport_x, signed short viewport_y);

/* Ending portraits use installed scene banks 0/1 for source palette 15. */
unsigned char bc_gallery_draw(const BcActor actors[BC_ACTOR_CAPACITY],
    signed short viewport_x, signed short viewport_y);
