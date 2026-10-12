#pragma once
#include "bc_player.h"

typedef struct {
    unsigned short source[9], genesis[9];
} BcRobotArt;
typedef struct {
    unsigned short code;
    signed short x, y;
    unsigned char colour, visible, handled;
} BcRobotSprite;
/* Four living poses followed by five source-timed death frames. */
void bc_robot_art_init(BcRobotArt *art, const BcEnemyData *data,
    unsigned short pose_table, unsigned short death_script,
    const unsigned short genesis_death_codes[8]);
/* BC positions are centers; Genesis sprite submissions use top-left pixels.
 * This is artwork selection only and never mutates simulation state. */
BcRobotSprite bc_robot_sprite(const BcRobotArt *art, const BcPlayerControl *player,
    unsigned char player_id, signed short viewport_x, signed short viewport_y);
/* Submit our existing Genesis robot art through the normal sprite cache. */
unsigned char bc_robot_draw(const BcRobotArt *art, const BcPlayerControl *player,
    unsigned char player_id, signed short viewport_x, signed short viewport_y,
    unsigned char submerged);
