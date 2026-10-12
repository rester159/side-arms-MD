#pragma once
#include "enemy_model.h"
#include "bc_world.h"

/* One engine-owned actor arena. A session uses exactly one typed view;
 * BC and Normal retain their different record formats and slot ordering.
 * Do not read inactive mode records or retain their pointers across modes. */
typedef union {
    struct {
        Enemy small[N_SMALL], big[N_BIG], item[N_ITEM];
    } normal;
    BcActor bc[BC_ACTOR_CAPACITY];
} EnemyArena;
extern EnemyArena enemy_arena;
#define en_small (enemy_arena.normal.small)
#define en_big   (enemy_arena.normal.big)
#define en_item  (enemy_arena.normal.item)
