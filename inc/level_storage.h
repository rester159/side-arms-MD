#pragma once
#include "bc_stage.h"

/* BC's fixed-point camera/checkpoint/script state belongs to the level engine.
 * Its content decoder remains a rules policy, like Normal's event decoder. */
extern BcStage level_bc;
