#pragma once
#include "bc_rules.h"

/* Camera is 12.8 fixed point, wrapping over the source's 4096-pixel map.
 * The checkpoint stores integer high bytes; script pointers index stage data. */
typedef struct {
    unsigned int x, y;
    signed short dx, dy;
    unsigned short script, terrain_attributes, checkpoint_script;
    unsigned char checkpoint_x, checkpoint_y;
    unsigned char shot_limit, stopped, boss_active;
} BcStage;

/* $6786-$67A2: the currently loaded round supplies its eight-byte header. */
void bc_stage_checkpoint_initial(BcStage *stage, const unsigned char header[8]);
/* $737C-$73A0: restore simulation state before the renderer fills the map. */
void bc_stage_checkpoint_restore(BcStage *stage, const unsigned char header[8]);
/* $6ED4-$6F0C, after script events choose this update's scroll velocity. */
void bc_stage_scroll(BcStage *stage);

/* $7690-$76D2: inspect one event. A nonzero return identifies a native handler
 * to run now. Then call event_complete, after applying the handler's effects,
 * and inspect again in the same update. Zero ends event processing this update. */
unsigned short bc_stage_event_next(BcStage *stage, const BcEnemyData *data);
void bc_stage_event_complete(BcStage *stage);

/* Common stage controls, with the caller removing the round's code relocation
 * from handler first. Returns zero for handlers that still need translation. */
unsigned char bc_stage_control(BcStage *stage, unsigned short handler);
