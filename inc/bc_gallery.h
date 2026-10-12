#pragma once
#include "bc_world.h"

/* Ending-only actor tasks ($947E, $A9FA, $AA4F). Gallery templates repurpose
 * HP as a wait, half_x as a phase, and half_y as an orbit step count. They
 * cannot participate in gameplay contacts. Return zero for an unknown task. */
unsigned char bc_gallery_actor_step(BcActor *actor, const BcEnemyData *data,
    signed short scroll_x, unsigned char stopped, unsigned char *limited_count);

/* $9BCA-$9D24: create a gallery portrait (one or three linked parts).
 * Bases are the ending overlay's 48 sprite-base words ($3678-$36D7).
 * Returns births completed, zero for an invalid entry or full pool. */
unsigned char bc_gallery_spawn(BcActor actors[BC_ACTOR_CAPACITY], unsigned char entry,
    const BcEnemyData *data, const unsigned short bases[48]);

typedef struct {
    unsigned short remaining, camera_x;
    unsigned char entry, phase, spawn;
} BcGallery;
/* Phases: 1 entrance, 2 display, 3 final scroll, 4 gallery finished.
 * Tick returns 0 on unsupported actor/data, 1 on an actor update, 2 on the
 * inter-entry preparation frame, 3 once the final scroll completes, 4 when
 * already complete. Text/rendering and subsequent music/fades are separate. */
void bc_gallery_begin(BcGallery *gallery, BcActor actors[BC_ACTOR_CAPACITY]);
unsigned char bc_gallery_tick(BcGallery *gallery, BcActor actors[BC_ACTOR_CAPACITY],
    const BcEnemyData *data, const unsigned short bases[48], unsigned char *limited_count);
