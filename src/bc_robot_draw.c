#include "bc_robot_art.h"
#include "sprites.h"

unsigned char bc_robot_draw(const BcRobotArt *art, const BcPlayerControl *player,
    unsigned char player_id, signed short viewport_x, signed short viewport_y,
    unsigned char submerged)
{
    BcRobotSprite sprite = bc_robot_sprite(art, player, player_id, viewport_x, viewport_y);
    if (sprite.visible) spr_bc_key32((sprite.code & 0x7ff) | ((unsigned short)(sprite.colour & 15) << 11) |
        (submerged && player->world.state == 0x80 && !player->entry ? 0x8000 : 0),
        sprite.x, sprite.y, 0);
    return sprite.handled;
}
