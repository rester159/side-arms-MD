#include "bc_actor_art.h"
#include "gen/bc_recolor_keys.h"
#include "gen/bc_boss_shot_keys.h"

static inline unsigned int pack_pose(BcActorSprite s)
{
    return s.code | ((unsigned int)s.colour << 11) |
        ((unsigned int)s.flips << 16) | (s.size == 32 ? 0x40000u : 0) |
        (s.visible ? 0x80000u : 0) | (s.handled ? 0x100000u : 0);
}

#if defined(__m68k__)
__attribute__((optimize("no-bit-tests")))
#endif
static unsigned int normal_actor_pose(const BcActor *a)
{
    static const unsigned short blast[7] = {0x1c0,0x1c2,0x1c6,0x1d2,0x1d4,0x1c4,0x1d0};
    static const unsigned short jet[8] = {0x5c0,0x5c2,0x5c4,0x5c6,0x5d0,0x5e0,0x5e2,0x5e4};
    static const unsigned short drum[5] = {0x3c0,0x3c2,0x3c4,0x3e0,0x3e2};
    static const unsigned short pod[7] = {0x6c0,0x6d6,0x6c6,0x6d0,0x6e0,0x6e2,0x6e6};
    static const unsigned short trooper[3] = {0x200,0x214,0x202};
    /* Packed poses: color 0, 32x32, visible/handled. The first four
     * include X flip; XOR the source flips at selection time. Keeping
     * this packed also preserves shared flip packing for other families. */
    static const unsigned int surfacer[7] = {0x1d0250u,0x1d0252u,0x1d0240u,0x1d0242u,0x1c0256u,0x1c0264u,0x1c0266u};
    static const unsigned short boss_beam[9] = {0x120,0x121,0x120,0x122,0x123,0x122,0x124,0x125,0x124};
    static const unsigned short walker[5] = {0x2b6,0x2c0,0x2a6,0x2d2,0x2d4};
    static const unsigned short rotating_pod[8] = {0x7c0,0x7c2,0x7c4,0x7c6,0x7d0,0x7e0,0x7e2,0x7e4};
    const BcEnemy *b = &a->body;
    BcActorSprite s = {0, 0, 0, 8, 0, 16, 0, 0};
    if (!b->state || !b->sprite || b->sprite == 255) { s.handled = 1; return pack_pose(s); }
    if (b->flags & 8) return pack_pose(s); /* Composite boss frame needs a separate layout. */
    unsigned short frame = b->sprite - b->sprite_base;
#if defined(__m68k__)
    /* Rotate the two source flip bits into place with short immediate counts. */
    unsigned short horizontal = b->attributes, vertical = b->attributes;
    __asm__("rol.w #5,%0\n\trol.w #2,%1" : "+d"(horizontal), "+d"(vertical) : : "cc");
    s.flips = (horizontal & 1) | (vertical & 2);
#else
    s.flips = ((b->attributes & 0x0800) ? 1 : 0) | ((b->attributes & 0x8000) ? 2 : 0);
#endif
    switch (a->sprite_base_ref) {
    case 0x36d0: case 0x36d2: case 0x36d4: {
        /* Final serpent: unflipped source poses face left through up.
         * The generated selector replaces these stable keys with original PCE
         * head/body/tail patterns, including the protected head palette. */
        static const unsigned short serpent[5] = {0x630,0x632,0x634,0x636,0x600};
        if (frame > 32 || (frame & 7)) return pack_pose(s);
        s.code = serpent[frame >> 3] + ((a->sprite_base_ref - 0x36d0) >> 1) * 0x40;
        s.colour = a->sprite_base_ref == 0x36d0 && (b->attributes & 15) == 3 ? 8 : 3;
        s.size = 32; break;
    }
    case 0x369a: /* Eye formation: four blink/open poses in our existing bank. */
        if (frame > 24 || (frame & 7)) return pack_pose(s);
        s.code = 0x360 + (frame >> 2); s.colour = 11; s.size = 32; break;
    case 0x36ac: /* Dome laser turret, idle and recoil. */
        if (frame != 0 && frame != 8) return pack_pose(s);
        s.code = frame ? 0x542 : 0x540; s.colour = 5; s.size = 32; break;
    case 0x36b4: /* Aimed laser retains the source flip and movement. */
        if (frame) return pack_pose(s);
        s.code = 0x1b8; s.colour = 8; break;
    case 0x3696: /* Splitting pod and its three drone poses. */
        if (frame == 0 || frame == 8) {
            s.code = frame ? 0x346 : 0x344; s.colour = 5; s.size = 32;
        } else if (frame >= 16 && frame <= 20 && !(frame & 1)) {
            s.code = 0x350 + ((frame - 16) >> 1); s.colour = 5;
        } else return pack_pose(s);
        break;
    case 0x36ce: /* Round-six rain shots, before/after their top-edge turn. */
        if (frame != 0 && frame != 2) return pack_pose(s);
        /* Captured BC pose 00 is the large orb; pose 02 is the small orb. */
        s.code = frame ? 0x126 : 0x127; s.colour = 8; break;
    case 0x3694: /* Terrain-triggered shell opening into a standing robot. */
        if (frame > 24 || (frame & 7)) return pack_pose(s);
        s.code = 0x2e0 + (frame >> 2); s.colour = 0; s.size = 32; break;
    case 0x36aa: /* Turning mine: five headings, mirrored by source attributes. */
        if (frame > 8 || (frame & 1)) return pack_pose(s);
        s.code = 0x550 + (frame >> 1); s.colour = 10; break;
    case 0x369c: /* Paired shutters keep their source separation and flash. */
        if (frame) return pack_pose(s);
        s.code = 0x396; s.colour = (b->attributes & 15) == 14 ? 7 : 14;
        s.size = 32; break;
    case 0x36b0: /* Missile turret: vertical / horizontal idle and recoil. */
        if (frame > 24 || (frame & 7)) return pack_pose(s);
        s.code = (frame < 16 ? 0x514 : 0x524) + ((frame & 8) ? 2 : 0);
        s.colour = 5; s.size = 32; break;
    case 0x36b2: /* Spike turret; source flip selects the opposite mounting. */
        if (frame != 0 && frame != 8) return pack_pose(s);
        s.code = frame ? 0x532 : 0x530; s.colour = 3; s.size = 32; break;
    case 0x36ae: /* Crab turret: idle / recoil, orientation uses source flips. */
        if (frame != 0 && frame != 8) return pack_pose(s);
        s.code = frame ? 0x502 : 0x500; s.colour = 12; s.size = 32; break;
    case 0x368a:
        if (frame > 32 || (frame & 7)) return pack_pose(s);
        /* Genesis walking poses face opposite the PCE originals. Attack
         * poses already agree; retain source mirroring for both directions. */
        if (frame < 16) s.flips ^= 1;
        s.code = walker[frame >> 3]; s.colour = 9; s.size = 32; break;
    case 0x3690:
        if (frame > 56 || (frame & 7)) return pack_pose(s);
        s.code = rotating_pod[frame >> 3]; s.colour = 5; s.size = 32; break;
    case 0x369e: case 0x36a0: case 0x36a2:
    case 0x36a4: case 0x36a6: case 0x36a8:
        if (frame > 8 || (frame & 1)) return pack_pose(s);
        s.code = (a->sprite_base_ref < 0x36a4 ? 0x400 : 0x460) +
            ((a->sprite_base_ref - (a->sprite_base_ref < 0x36a4 ? 0x369e : 0x36a4)) >> 1) * 16 + (frame >> 1);
        s.colour = a->sprite_base_ref < 0x36a4 ? 5 : 6; break;
    case 0x368c:
        if (frame > 56 || (frame & 7)) return pack_pose(s);
        s.code = jet[frame >> 3]; s.colour = 6; s.size = 32; break;
    case 0x3692:
        if (frame > 32 || (frame & 7)) return pack_pose(s);
        s.code = drum[frame >> 3]; s.colour = 5; s.size = 32; break;
    case 0x368e:
        if (frame > 48 || (frame & 7)) return pack_pose(s);
        s.code = pod[frame >> 3]; s.colour = 12; s.size = 32; break;
    case 0x3686:
        if (frame > 16 || (frame & 7)) return pack_pose(s);
        s.code = trooper[frame >> 3];
        s.colour = (b->attributes & 15) == 4 ? 1 : 13; s.size = 32; break;
    case 0x3688:
        if (frame > 48 || (frame & 7)) return pack_pose(s);
        return surfacer[frame >> 3] ^ ((unsigned int)s.flips << 16);
    case 0x367c: /* Four source small-explosion frames. */
        if (frame > 6 || (frame & 1)) return pack_pose(s);
        s.code = 0x138 + frame; break;
    case 0x367e: /* Explosion plus round-four laser-impact poses; source owns timing. */
        if (frame > 48 || (frame & 7)) return pack_pose(s);
        s.code = blast[frame >> 3]; s.size = 32;
        s.colour = (b->attributes & 15) == 2 ? 7 : 8; break;
    case 0x3682:
        if (frame >= 10 && frame <= 14 && !(frame & 1)) {
            s.code = frame == 12 ? 0x309 : 0x300 + ((frame - 10) >> 1); s.colour = 5; break;
        }
        /* fall through */
    case 0x3684: /* Five directions plus source X/Y flips. */
        if (frame > 8 || (frame & 1)) return pack_pose(s);
        s.code = (a->sprite_base_ref == 0x3682 ? 0x290 : 0x280) + (frame >> 1);
        s.colour = a->sprite_base_ref == 0x3682 ? 5 : 0; break;
    case 0x3698: /* Straight enemy bullet. */
        if (frame) return pack_pose(s);
        s.code = 0x127; break;
    case 0x36cc: /* Shared chain bank: round-eight growth/turn poses precede round two. */
        if (frame <= 12 && !(frame & 1)) {
            static const unsigned short chain[7] = {0x120,0x121,0x120,0x122,0x123,0x124,0x125};
            s.code = chain[frame >> 1]; s.colour = 8; break;
        }
        if (frame < 14 || frame > 30 || (frame & 1)) return pack_pose(s);
        s.code = boss_beam[(frame - 14) >> 1]; s.colour = 8; break;
    case 0x36c8: /* Round-one boss's two radial-shot frames. */
        if (frame != 0 && frame != 2) return pack_pose(s);
        s.code = frame ? 0x122 : 0x127;
        s.colour = frame ? 8 : 7; break;
    case 0x367a: /* Pickups share the source bank with bullet impacts. */
        switch (frame) {
        case 0x20: s.code = 0x118; s.colour = 4; break; /* POW bonus chain */
        case 0x24: s.code = 0x104; s.colour = 10; break; /* expanding shots */
        case 0x26: s.code = 0x10c; s.colour = 6; break; /* straightening shots */
        case 0x28: s.code = 0x108; s.colour = 5; break; /* returning weapon */
        case 0x2a: s.code = 0x110; s.colour = 5; break; /* option */
        case 0x30: s.code = 0x134; s.colour = 0; break; /* cow */
        case 0x32: s.code = 0x135; s.colour = 5; break; /* barrel */
        case 0x34: s.code = 0x136; s.colour = 5; break; /* fruit */
        case 0x36: s.code = 0x137; s.colour = 5; break; /* extra life */
        case 0x2c: case 0x2e:
            s.code = frame == 0x2e ? 0x01f : 0x01c; s.colour = 2; break;
        default: return pack_pose(s);
        }
        break;
    default: return pack_pose(s);
    }
    s.visible = s.handled = 1;
    return pack_pose(s);
}

unsigned int bc_actor_pose(const BcActor *a)
{
    return bc_recolored_pose(a->sprite_base_ref,
        a->body.sprite - a->body.sprite_base, a->body.attributes,
        normal_actor_pose(a));
}

unsigned int bc_actor_boss_pose(const BcActor *a)
{
    return bc_original_boss_shot(a->sprite_base_ref,
        a->body.sprite - a->body.sprite_base, a->body.attributes,
        bc_actor_pose(a));
}

static BcActorSprite sprite_from_pose(const BcActor *a, signed short ox, signed short oy, unsigned int pose)
{
    BcActorSprite s = {pose & 0x7ff, 0, 0, (pose >> 11) & 15,
        (pose >> 16) & 3, pose & 0x40000u ? 32 : 16,
        !!(pose & 0x80000u), !!(pose & 0x100000u)};
    if (s.visible) {
        s.x = (signed short)(bc_enemy_x(&a->body)) - s.size / 2 + ox;
        s.y = (signed short)(bc_enemy_y(&a->body)) - s.size / 2 + oy;
    }
    return s;
}

BcActorSprite bc_actor_sprite(const BcActor *a, signed short ox, signed short oy)
{
    return sprite_from_pose(a, ox, oy, bc_actor_pose(a));
}

BcActorSprite bc_actor_boss_sprite(const BcActor *a, signed short ox, signed short oy)
{
    return sprite_from_pose(a, ox, oy, bc_actor_boss_pose(a));
}
