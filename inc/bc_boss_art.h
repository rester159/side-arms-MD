#pragma once
#include "bc_world.h"
void bc_boss_art_init(void);
void bc_boss_art_init_sequence(void);
void bc_boss_art_queue_encounter(unsigned char encounter);
/* Load an encounter bank while retaining its source round frame addresses. */
void bc_boss_art_init_encounter(unsigned char encounter, unsigned char source_round);
void bc_boss_art_init_round(unsigned char round);
/* 1 = recognized (including the source's empty collision-only composite). */
unsigned char bc_boss_draw(const BcActor *actor, signed short ox, signed short oy);
