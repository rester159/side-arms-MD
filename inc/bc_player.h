#pragma once
#include "bc_world.h"

typedef struct {
    BcWorldPlayer world;
    unsigned short attributes, body_frame, weapon_frame, death_script;
    signed short vx, vy;
    unsigned char entry, speed, recoil, death_clock;
} BcPlayerControl;
typedef struct { unsigned char checkpoint, sound; } BcPlayerControlEvent;

/* Before weapon update. Frame identifiers retain source animation selections;
 * data/pose_table supply the original animation selections, not CPU opcodes. */
BcPlayerControlEvent bc_player_control(BcPlayerControl *player, unsigned char direction,
    unsigned short camera_x, unsigned short camera_y, unsigned short scroll_dx,
    unsigned short scroll_dy, const BcTerrain *terrain, const BcEnemyData *data,
    unsigned short pose_table);
/* Optional native-endian pose cache for immutable round data. Rebind after
 * changing the source table; NULL disables it. Other data falls back to reads. */
void bc_player_bind_poses(const BcEnemyData *data, unsigned short pose_table);
/* After weapon update: pose selection, entry/recoil/blink countdowns. Returns
 * graphics-upload request: 0 none, 1 body only, 2 body and weapon. */
unsigned char bc_player_finish(BcPlayerControl *player, const BcEnemyData *data,
                                unsigned short pose_table);
typedef struct {
    BcPlayerControlEvent control;
    BcWeaponEvent weapon;
    unsigned char graphics;
} BcPlayerFrameEvent;
/* Caller-owned output avoids copying the frame event into a party result. */
void bc_player_step_into(BcPlayerFrameEvent *event, BcPlayerControl *player,
    unsigned char held, unsigned char pressed, unsigned short camera_x,
    unsigned short camera_y, unsigned short scroll_dx, unsigned short scroll_dy,
    const BcTerrain *terrain, const BcEnemyData *data, unsigned short pose_table);
BcPlayerFrameEvent bc_player_step(BcPlayerControl *player, unsigned char held,
    unsigned char pressed, unsigned short camera_x, unsigned short camera_y,
    unsigned short scroll_dx, unsigned short scroll_dy, const BcTerrain *terrain,
    const BcEnemyData *data, unsigned short pose_table);

/* Player portion of $65D6-$6622. Stage loading resets enemies separately.
 * template_address points to the original 32-byte player initialization data.
 * Round 9 preserves the incoming weapon/power; other rounds use the template. */
void bc_player_reset(BcPlayerControl *player, unsigned char round,
    const BcEnemyData *data, unsigned short template_address);
