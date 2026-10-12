#include "bc_gallery.h"

unsigned char bc_gallery_actor_step(BcActor *a, const BcEnemyData *data,
    signed short scroll_x, unsigned char stopped, unsigned char *limited_count)
{
    unsigned short routine = a->body.state == 0x80 ? a->routine : a->death_routine;
    if (routine != 0x94ad && routine != 0xa9fa && routine != 0xaa4f) return 0;
    bc_actor_scroll(a, scroll_x, 0, stopped);
    if (routine != 0x94ad) {
        if (a->body.hp) a->body.hp--;
        else if (routine == 0xa9fa) {
            /* $AA14/$AA2A/$AA40: pause, slide right, slide left, stop. */
            if (a->half_x < 2) {
                a->body.hp = 64;
                bc_enemy_set_vx(&a->body, a->half_x ? -128 : 128);
                a->half_x++;
            } else {
                a->body.hp = 255; bc_enemy_set_vx(&a->body, 0);
            }
        } else {
            /* $AA5A: replace only the integer low bytes. Fractional/high
             * coordinate bytes survive, including the entry's scrolling. */
            const unsigned char *position = data->bytes +
                (unsigned short)(0xaa9e + a->half_x*2 - data->origin);
            bc_enemy_low_x(&a->body, 56 + position[0]);
            bc_enemy_low_y(&a->body, 72 + position[1]);
            a->body.hp = 3; a->half_x = (a->half_x+1)&15;
            if (++a->half_y == 24) {
                a->routine = 0x94ad; a->body.timer = 240;
            }
        }
    }
    if (bc_enemy_motion(&a->body, data, limited_count) != 1 && a->body.damage_lock)
        a->body.damage_lock--;
    return 1;
}

unsigned char bc_gallery_spawn(BcActor actors[BC_ACTOR_CAPACITY], unsigned char entry,
    const BcEnemyData *data, const unsigned short bases[48])
{
    if (entry >= 20) return 0;
    unsigned char parts = entry == 13 || entry == 14 ? 3 : 1;
    const unsigned char *table = data->bytes + (unsigned short)(0xa478 + entry*2 - data->origin);
    unsigned short record = table[0] | ((unsigned short)table[1] << 8);
    unsigned char born = 0;
    for (unsigned char i = 0; i < parts; i++) {
        signed short slot = bc_actor_allocate(actors, 0);
        if (slot < 0) break;
        const unsigned char *r = data->bytes + (unsigned short)(record + i*56 - data->origin);
        unsigned short ref = r[11] | ((unsigned short)r[12] << 8);
        BcActor *a = &actors[slot];
        bc_actor_template(a, r, bases[(ref-0x3678)/2]);
        unsigned short x = i == 0 ? 312 : i == 1 ? 323 : 328;
        unsigned short y = parts == 1 ? 72 : i == 0 ? 88 : i == 1 ? 83 : 72;
        bc_enemy_set_x(&a->body, x);
        bc_enemy_set_y(&a->body, y);
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
        born++;
    }
    return born;
}

void bc_gallery_begin(BcGallery *g, BcActor actors[BC_ACTOR_CAPACITY])
{
    *g = (BcGallery){32, 0, 0, 1, 1};
    for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++) actors[i] = (BcActor){0};
}

unsigned char bc_gallery_tick(BcGallery *g, BcActor actors[BC_ACTOR_CAPACITY],
    const BcEnemyData *data, const unsigned short bases[48], unsigned char *limited_count)
{
    if (g->phase == 4) return 4;
    if (g->phase < 1 || g->phase > 3) return 0;
    if (g->phase == 2 && !g->remaining) {
        g->entry++;
        g->phase = g->entry == 20 ? 3 : 1;
        g->remaining = 32; g->spawn = g->entry < 20;
        return 2;
    }
    if (g->spawn) {
        unsigned char count = g->entry == 13 || g->entry == 14 ? 3 : 1;
        if (bc_gallery_spawn(actors, g->entry, data, bases) != count) return 0;
        g->spawn = 0;
    }
    if (g->phase == 1 && !g->remaining) {
        for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++)
            if (actors[i].body.state) actors[i].body.flags &= ~32;
        g->phase = 2; g->remaining = 256;
    }
    signed short dx = g->phase == 2 ? 0 : 2048;
    if (dx) g->camera_x += 8;
    for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++) {
        BcActor *a = &actors[i];
        if (!a->body.state) continue;
        if (!bc_gallery_actor_step(a, data, dx, 0, limited_count)) return 0;
        /* $98DC-$98E6 runs even if the just-updated actor retired. */
        if (g->phase == 2 && !--a->speed) a->body.attributes |= 15;
    }
    if (!--g->remaining && g->phase == 3) { g->phase = 4; return 3; }
    return 1;
}
