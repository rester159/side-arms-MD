#include "bc_player.h"

static unsigned short word(const BcEnemyData *data, unsigned short address)
{
    const unsigned char *p = data->bytes + (unsigned short)(address - data->origin);
    return p[0] | ((unsigned short)p[1] << 8);
}

/* One immutable round resource is active at a time. Generic/reference
 * callers retain direct reads unless they explicitly bind matching data. */
static const unsigned char *pose_bytes;
static unsigned short pose_origin, pose_table;
static unsigned short weapon_poses[3][2], body_poses[2];

void bc_player_bind_poses(const BcEnemyData *data, unsigned short table)
{
    pose_bytes = 0;
    if (!data) return;
    for (unsigned char i = 0; i < 3; i++) {
        unsigned short address = word(data, table + i * 2);
        for (unsigned char j = 0; j < 2; j++)
            weapon_poses[i][j] = word(data, address + j * 2);
    }
    body_poses[0] = word(data, table + 18);
    body_poses[1] = word(data, table + 20);
    pose_origin = data->origin; pose_table = table; pose_bytes = data->bytes;
}

/* $8F29-$90B7. The source's checkpoint jump leaves this task entirely; the
 * caller must honor that event before running weapons or finish. */
BcPlayerControlEvent bc_player_control(BcPlayerControl *p, unsigned char direction,
    unsigned short cx, unsigned short cy, unsigned short scroll_dx, unsigned short scroll_dy,
    const BcTerrain *terrain, const BcEnemyData *data, unsigned short table)
{
    BcPlayerControlEvent event = {0, 0};
    BcWorldPlayer *w = &p->world;
    if (p->entry) {
        p->body_frame = word(data, table + (p->entry >= 16 ? 22 : 24));
        p->attributes = 0x1180;
        w->x = (w->x + 512) & 0xffffff;
        return event;
    }
    if (w->state != 0x80) {
        unsigned char old = p->death_clock++;
        if (!w->state) { event.checkpoint = old == 160; return event; }
        if (!old) {
            w->weapons.charge.charge = 0;
            for (unsigned char i = 0; i < 30; i++) w->weapons.shots[i].body.state = 0;
        }
        if (!(old & 7)) {
            p->attributes = (p->attributes & 0xff00) | 0x81;
            p->death_script += 2;
            p->body_frame = word(data, p->death_script);
            if (p->body_frame == 65535) w->state = 0;
        }
        return event;
    }
    BcMotion motion = {w->x, w->y, 0, 0};
    unsigned char crushed = bc_move_step(&motion, direction, p->speed, cx, cy, scroll_dx, scroll_dy, terrain);
    /* A source crush returns before the screen clamp. Developer protection
     * keeps this player alive, so prevent repeated scroll subtraction from
     * wrapping the coordinate and teleporting to the opposite edge. */
    if (crushed && bc_damage_disabled) {
        if (motion.x < (16 << 8)) motion.x = 16 << 8;
        if (motion.y < (32 << 8)) motion.y = 32 << 8;
    }
    w->x = (w->x & 0xff0000) | motion.x;
    w->y = (w->y & 0xff0000) | motion.y;
    p->vx = motion.dx * 256; p->vy = motion.dy * 256;
    if (crushed && !bc_damage_disabled) { w->state = 0x40; event.sound = 3; }
    return event;
}

/* $740D-$7485. This requests frame data; the Genesis renderer may cache
 * unchanged uploads without changing simulation state or these selections. */
unsigned char bc_player_finish(BcPlayerControl *p, const BcEnemyData *data, unsigned short table)
{
    unsigned char graphics = 0;
    if (p->world.state) {
        graphics = 1;
        if (p->world.state == 0x80) {
            if (p->entry) p->entry--;
            else {
                unsigned char kind = p->world.inventory.weapon;
                if (kind < 3 && data->bytes == pose_bytes &&
                    data->origin == pose_origin && table == pose_table) {
                    unsigned char recoil = p->recoil != 0;
                    p->weapon_frame = weapon_poses[kind][recoil];
                    p->body_frame = body_poses[recoil];
                } else {
                    unsigned short weapon = word(data, table + kind * 2);
                    p->weapon_frame = word(data, weapon + (p->recoil ? 2 : 0));
                    p->body_frame = word(data, table + (p->recoil ? 20 : 18));
                }
                p->attributes = p->world.weapons.charge.facing ? 0x1180 : 0x1980;
                graphics = 2;
            }
        }
    }
    if (p->recoil) p->recoil--;
    if (p->world.invulnerability) p->world.invulnerability--;
    return graphics;
}

/* $7407-$7485. Enemy and score tasks remain separate so their original
 * execution order and the eight-update option trail can be reproduced.
 * Keep this update separate: inlining into the party scheduler increases
 * measured register/temporary costs on the 68000. */
void __attribute__((noinline)) bc_player_step_into(BcPlayerFrameEvent *event, BcPlayerControl *p, unsigned char held,
    unsigned char pressed, unsigned short cx, unsigned short cy,
    unsigned short scroll_dx, unsigned short scroll_dy, const BcTerrain *terrain,
    const BcEnemyData *data, unsigned short table)
{
    event->control = bc_player_control(p, held >> 4, cx, cy, scroll_dx, scroll_dy, terrain, data, table);
    if (event->control.checkpoint) {
        /* Normal updates overwrite every output field. Only the checkpoint
         * exit needs empty weapon/graphics results without running those tasks. */
        event->weapon = (BcWeaponEvent){0};
        event->graphics = 0;
        return;
    }
    BcWorldPlayer *w = &p->world;
    bc_weapons_step_into(&event->weapon, &w->weapons, held, pressed, w->state == 0x80,
        p->entry, w->inventory.weapon, w->inventory.power, w->x >> 8, w->y >> 8, cx, cy, terrain);
    if (event->weapon.recoil) p->recoil = event->weapon.recoil;
    event->graphics = bc_player_finish(p, data, table);
    return;
}

BcPlayerFrameEvent bc_player_step(BcPlayerControl *p, unsigned char held,
    unsigned char pressed, unsigned short cx, unsigned short cy,
    unsigned short scroll_dx, unsigned short scroll_dy, const BcTerrain *terrain,
    const BcEnemyData *data, unsigned short table)
{
    BcPlayerFrameEvent event;
    bc_player_step_into(&event, p, held, pressed, cx, cy, scroll_dx, scroll_dy, terrain, data, table);
    return event;
}

void bc_player_reset(BcPlayerControl *p, unsigned char round,
    const BcEnemyData *data, unsigned short template_address)
{
    const unsigned char *t = data->bytes + (unsigned short)(template_address - data->origin);
    BcWorldPlayer *w = &p->world;
    unsigned char weapon = w->inventory.weapon, power = w->inventory.power;
    /* $55/$57 and the option trail lie outside the source clear ranges. */
    for (unsigned char i = 0; i < 30; i++) {
        BcShot empty = {0};
        w->weapons.shots[i] = empty;
    }
    w->weapons.charge.charge = 0;
    w->weapons.charge.facing = t[0x16] == 0x52;
    w->weapons.returning = 0;
    w->weapons.option_shots[0] = w->weapons.option_shots[1] = 0;
    w->inventory.bonus_chain = 0;
    w->inventory.weapon = round == 9 ? weapon : t[0x11];
    w->inventory.power = round == 9 ? power : t[0x1a];
    w->state = t[0];
    w->x = ((unsigned int)t[1] << 16) | ((unsigned short)t[2] << 8) | t[3];
    w->y = ((unsigned int)t[4] << 16) | ((unsigned short)t[5] << 8) | t[6];
    p->attributes = ((unsigned short)t[7] << 8) | t[8];
    p->body_frame = ((unsigned short)t[9] << 8) | t[10];
    p->vx = ((unsigned short)t[11] << 8) | t[12];
    p->vy = ((unsigned short)t[13] << 8) | t[14];
    p->weapon_frame = ((unsigned short)t[18] << 8) | t[19];
    p->recoil = t[20]; p->speed = t[21]; p->entry = t[25];
    w->invulnerability = t[27]; p->death_clock = t[29];
    p->death_script = t[30] | ((unsigned short)t[31] << 8);
}
