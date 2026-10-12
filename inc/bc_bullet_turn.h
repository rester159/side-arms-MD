#pragma once
#include "bc_rules.h"

static inline unsigned short bc_bullet_turn_word(const BcEnemyData *data, unsigned short address)
{
    return data->bytes[(unsigned short)(address-data->origin)] |
        ((unsigned short)data->bytes[(unsigned short)(address+1-data->origin)] << 8);
}

/* Homing turn after an empty terrain probe; no position/contact work here. */
static inline __attribute__((always_inline)) void bc_enemy_bullet_turn(BcEnemy *e, BcBulletFlight *b,
    unsigned short px, unsigned short py, const BcEnemyBulletData *data)
{
    if (!--b->turn_timer) {
        b->turn_timer = 5;
        unsigned char aim = bc_aim16(px, py, bc_enemy_x(e), bc_enemy_y(e));
        if (aim != b->direction) {
            unsigned char difference = b->direction - aim;
            signed char turn = ((difference >> 2) & 2) - 1;
            b->direction = (b->direction + turn) & 15;
            e->animation = bc_bullet_turn_word(&data->data, data->direction_animations + b->direction * 2);
            e->timer = 1;
            unsigned short vector = bc_bullet_turn_word(&data->data, data->speed_table + b->speed) + b->direction * 4;
            bc_enemy_set_vx(e, (signed short)bc_bullet_turn_word(&data->data, vector));
            bc_enemy_set_vy(e, (signed short)bc_bullet_turn_word(&data->data, vector + 2));
        }
    }
}
