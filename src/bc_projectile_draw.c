#include "bc_projectile_art.h"
#include "gen/bc_player_projectile_keys.h"
#include "sprites.h"
#include "game.h"

/* Keep this loop outside the large scene frame: measured 68000 builds spend
 * less time drawing the same shots when LTO cannot fold it into that caller. */
/* Separate cores deliberately preserve register allocation: a shared pack-guard
 * version spills more registers and regresses both long four-player replays.
 * Keep grouping, fallback, and ordinary per-shot submission order identical. */
static inline unsigned char __attribute__((always_inline)) projectile_draw_core_solo(const BcWeapons *weapons, signed short ox, signed short oy, unsigned char pack)
{
    unsigned char unmapped = 0;
    const BcShot *end = weapons->shots + 30;
    /* Advance by one record directly. An indexed byte loop makes the 68000
     * repeatedly multiply the slot by sizeof(BcShot), including empty slots. */
    for (const BcShot *shot = weapons->shots; shot < end; shot++) {
        const BcBeam *body = &shot->body;
        if (!body->state) {
            /* Skip only wholly empty spans. Live triples may still cross
             * any span boundary and keep their original packing/order. */
            if (shot <= end - 6 && !(shot[1].body.state | shot[2].body.state |
                shot[3].body.state | shot[4].body.state | shot[5].body.state)) shot += 5;
            continue;
        }
        /* A live straight-shot triple has known artwork. Check grouping
         * before asking the general mapper to materialize a sprite record. */
        if (pack && body->sprite == 0x1b8 && shot < end - 2) {
            const BcBeam *b = &shot[1].body, *c = &shot[2].body;
            s16 x = bc_beam_x(body), bx = bc_beam_x(b), cx = bc_beam_x(c);
            if (b->state && c->state && b->sprite == 0x1b8 && c->sprite == 0x1b8 &&
                !((body->attributes ^ b->attributes) & 0x8800) &&
                !((body->attributes ^ c->attributes) & 0x8800) &&
                bc_beam_same_y(body, b) && bc_beam_same_y(body, c) &&
                ((bx-x == 8 && cx-bx == 8) || (x-bx == 8 && bx-cx == 8))) {
                unsigned char flips = ((body->attributes & 0x0800) ? 1 : 0) |
                                      ((body->attributes & 0x8000) ? 2 : 0);
                spr_bc_straight3((cx < x ? cx : x)-8+ox,
                    (signed short)bc_beam_y(body)-8+oy, flips, bx > x);
                shot += 2; continue;
            }
        }
        BcProjectileSprite sprite = bc_projectile_sprite(body, ox, oy);
        /* The mapper preserves source flips except for directional beam art.
         * Submit those hardware bits directly, avoiding a round trip through
         * logical flags in the single-projectile path. */
        if (sprite.visible) spr_bc_bits16((sprite.code & 0x7ff) | ((unsigned short)(sprite.colour & 15) << 11),
            sprite.x, sprite.y,
            (body->sprite == 0x1bc || body->sprite == 0x1be || body->sprite == 0x1c0)
                ? 0 : (body->attributes & 0x0800) | ((body->attributes >> 3) & 0x1000));
        else if (!sprite.handled) unmapped++;
    }
    return unmapped;
}

static inline unsigned char __attribute__((always_inline)) projectile_draw_core_multi(const BcWeapons *weapons, signed short ox, signed short oy, unsigned char pack)
{
    unsigned char unmapped = 0;
    const BcShot *end = weapons->shots + 30;
    /* Advance by one record directly. An indexed byte loop makes the 68000
     * repeatedly multiply the slot by sizeof(BcShot), including empty slots. */
    for (const BcShot *shot = weapons->shots; shot < end; shot++) {
        const BcBeam *body = &shot->body;
        if (!body->state) {
            /* Skip only wholly empty spans. Live triples may still cross
             * any span boundary and keep their original packing/order. */
            if (shot <= end - 6 && !(shot[1].body.state | shot[2].body.state |
                shot[3].body.state | shot[4].body.state | shot[5].body.state)) shot += 5;
            continue;
        }
        /* A live straight-shot triple has known artwork. Check grouping
         * before asking the general mapper to materialize a sprite record. */
        if (pack && body->sprite == 0x1b8 && shot < end - 2) {
            const BcBeam *b = &shot[1].body, *c = &shot[2].body;
            s16 x = bc_beam_x(body), bx = bc_beam_x(b), cx = bc_beam_x(c);
            int spacing = bx - x;
            if (b->state && c->state && b->sprite == 0x1b8 && c->sprite == 0x1b8 &&
                !((body->attributes ^ b->attributes) & 0x8800) &&
                !((body->attributes ^ c->attributes) & 0x8800) &&
                bc_beam_same_y(body, b) && bc_beam_same_y(body, c) &&
                ((spacing == 8 || spacing == -8) && cx - bx == spacing)) {
                unsigned char flips = ((body->attributes & 0x0800) ? 1 : 0) |
                                      ((body->attributes & 0x8000) ? 2 : 0);
                spr_bc_straight3((cx < x ? cx : x)-8+ox,
                    (signed short)bc_beam_y(body)-8+oy, flips, bx > x);
                shot += 2; continue;
            }
        }
        if (body->sprite == 0x1b8) {
            spr_bc_bits16(BC_PROJECTILE_1B8_KEY, (signed short)bc_beam_x(body)-8+ox,
                (signed short)bc_beam_y(body)-8+oy,
                (body->attributes & 0x0800) | ((body->attributes >> 3) & 0x1000));
            continue;
        }
        if (body->sprite == 0x1d4 || body->sprite == 0x1d6) {
            spr_bc_bits16(body->sprite == 0x1d4 ? BC_PROJECTILE_1D4_KEY : BC_PROJECTILE_1D6_KEY,
                (signed short)bc_beam_x(body)-8+ox,
                (signed short)bc_beam_y(body)-8+oy,
                (body->attributes & 0x0800) | ((body->attributes >> 3) & 0x1000));
            continue;
        }
        BcProjectileSprite sprite = bc_projectile_sprite(body, ox, oy);
        /* The mapper preserves source flips except for directional beam art.
         * Submit those hardware bits directly, avoiding a round trip through
         * logical flags in the single-projectile path. */
        if (sprite.visible) spr_bc_bits16((sprite.code & 0x7ff) | ((unsigned short)(sprite.colour & 15) << 11),
            sprite.x, sprite.y,
            (body->sprite == 0x1bc || body->sprite == 0x1be || body->sprite == 0x1c0)
                ? 0 : (body->attributes & 0x0800) | ((body->attributes >> 3) & 0x1000));
        else if (!sprite.handled) unmapped++;
    }
    return unmapped;
}

static unsigned char __attribute__((noinline)) projectile_draw_solo(const BcWeapons *weapons, signed short ox, signed short oy)
{
    return projectile_draw_core_solo(weapons, ox, oy, 0);
}

#if defined(__m68k__)
__attribute__((optimize("no-bit-tests")))
#endif
static unsigned char __attribute__((noinline)) projectile_draw_multi(const BcWeapons *weapons, signed short ox, signed short oy)
{
    return projectile_draw_core_multi(weapons, ox, oy, 1);
}

unsigned char __attribute__((noinline)) bc_projectiles_draw(const BcWeapons *weapons, signed short ox, signed short oy)
{
    if (game_player_limit() > 1) return projectile_draw_multi(weapons, ox, oy);
    return projectile_draw_solo(weapons, ox, oy);
}
