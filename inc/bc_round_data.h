#pragma once
#include "bc_rules.h"

/* Immutable source lookup resources. Code bytes are data for translated native
 * handlers; the cartridge never executes the source CPU instructions. */
typedef struct {
    BcEnemyData data;
    const unsigned char *sprite_bases;
    const unsigned char *header;
    unsigned short player_template, pose_table;
    signed short relocation;
    unsigned char round;
} BcRoundResource;
#define BC_ROUND_COUNT 10
extern const BcRoundResource bc_round_resources[BC_ROUND_COUNT] __attribute__((weak));

/* Optional exact final-round terrain acceleration; callers validate both sources. */
extern const unsigned char bc_final_solid[65536] __attribute__((weak));
extern const BcTerrain bc_final_terrain __attribute__((weak));

extern const unsigned char bc_round8_solid[65536] __attribute__((weak));
extern const BcTerrain bc_round8_terrain __attribute__((weak));

/* Native 16.16 containers decoded from the immutable boss-three speed tables. */
typedef struct {
    BcEnemyData source;
    signed int velocity[5][16][2];
} BcBoss3NativeVectors;
extern const BcBoss3NativeVectors bc_boss3_native_vectors[2] __attribute__((weak));
