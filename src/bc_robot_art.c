#include "bc_robot_art.h"
#include "gen/bc_player_death_keys.h"

static unsigned short word(const BcEnemyData *data, unsigned short address)
{
    const unsigned char *p = data->bytes + (unsigned short)(address - data->origin);
    return p[0] | ((unsigned short)p[1] << 8);
}

void bc_robot_art_init(BcRobotArt *art, const BcEnemyData *data,
    unsigned short pose_table, unsigned short death_script, const unsigned short death[8])
{
    /* BC's second entry pose is the side-facing transform (Normal 0x72),
     * not Normal's later front-facing transform (0x76). */
    static const unsigned short bodies[4] = {0x22, 0x26, 0x62, 0x72};
    static const unsigned short death_codes[5] = BC_PLAYER_DEATH_CODES;
    (void)death; /* Normal's eight-frame order is not the BC sequence. */
    for (unsigned char i = 0; i < 4; i++) {
        art->source[i] = word(data, pose_table + 18 + i * 2);
        art->genesis[i] = bodies[i];
    }
    for (unsigned char i = 0; i < 5; i++) {
        art->source[4 + i] = word(data, death_script + 2 + i * 2);
        art->genesis[4 + i] = death_codes[i];
    }
}

BcRobotSprite bc_robot_sprite(const BcRobotArt *art, const BcPlayerControl *p,
    unsigned char id, signed short viewport_x, signed short viewport_y)
{
    BcRobotSprite sprite = {0, 0, 0, 0, 0, 0};
    if (id >= 4) return sprite;
    sprite.x = (signed short)(p->world.x >> 8) - 16 + viewport_x;
    sprite.y = (signed short)(p->world.y >> 8) - 16 + viewport_y;
    if (!p->world.state || !p->body_frame) { sprite.handled = 1; return sprite; }
    for (unsigned char i = 0; i < 9; i++) {
        if (art->source[i] != p->body_frame) continue;
        sprite.code = art->genesis[i];
        if (i < 4) {
            if (p->attributes & 0x0800) sprite.code -= 2;
            if (id & 1) sprite.code += 0x80;
            sprite.colour = id == 2 ? 3 : id == 3 ? 7 : id ? 4 : 0;
        } else sprite.colour = 8;
        sprite.visible = sprite.handled = 1;
        return sprite;
    }
    return sprite;
}
