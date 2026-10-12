#include "bc_projectile_art.h"
#include "gen/bc_player_projectile_keys.h"

BcProjectileSprite bc_projectile_sprite(const BcBeam *b, signed short ox, signed short oy)
{
    BcProjectileSprite s = {0, 0, 0, 8, 0, 0, 0};
    s.x = (signed short)bc_beam_x(b) - 8 + ox;
    s.y = (signed short)bc_beam_y(b) - 8 + oy;
    if (!b->state) { s.handled = 1; return s; }
#if defined(__m68k__)
    /* Rotate the source flip bits into the low positions using short counts. */
    unsigned short horizontal = b->attributes, vertical = b->attributes;
    __asm__("rol.w #5,%0\n\trol.w #2,%1" : "+d"(horizontal), "+d"(vertical) : : "cc");
    s.flips = (horizontal & 1) | (vertical & 2);
#else
    s.flips = ((b->attributes & 0x0800) ? 1 : 0) | ((b->attributes & 0x8000) ? 2 : 0);
#endif
    switch (b->sprite) {
    case 0x1a8: s.code = BC_PROJECTILE_1A8_KEY & 0x7ff; s.colour = BC_PROJECTILE_1A8_KEY >> 11; break;
    case 0x1aa: s.code = BC_PROJECTILE_1AA_KEY & 0x7ff; s.colour = BC_PROJECTILE_1AA_KEY >> 11; break;
    case 0x1ac: s.code = BC_PROJECTILE_1AC_KEY & 0x7ff; s.colour = BC_PROJECTILE_1AC_KEY >> 11; break;
    case 0x1ae: s.code = BC_PROJECTILE_1AE_KEY & 0x7ff; s.colour = BC_PROJECTILE_1AE_KEY >> 11; break;
    case 0x1b0: s.code = BC_PROJECTILE_1B0_KEY & 0x7ff; s.colour = BC_PROJECTILE_1B0_KEY >> 11; break;
    case 0x1b2: s.code = BC_PROJECTILE_1B2_KEY & 0x7ff; s.colour = BC_PROJECTILE_1B2_KEY >> 11; break;
    case 0x1b4: s.code = BC_PROJECTILE_1B4_KEY & 0x7ff; s.colour = BC_PROJECTILE_1B4_KEY >> 11; break;
    case 0x1b6: s.code = BC_PROJECTILE_1B6_KEY & 0x7ff; s.colour = BC_PROJECTILE_1B6_KEY >> 11; break;
    case 0x1b8: s.code = BC_PROJECTILE_1B8_KEY & 0x7ff; s.colour = BC_PROJECTILE_1B8_KEY >> 11; break;
    case 0x1ba:
        s.code = BC_PROJECTILE_1BA_KEY & 0x7ff;
        s.colour = BC_PROJECTILE_1BA_KEY >> 11; break;
    case 0x1bc: case 0x1be: case 0x1c0:
        s.code = (b->facing ? 0x013 : 0x010) + (0x1c0 - b->sprite) / 2;
        s.flips = 0; break;
    case 0x1c2: s.code = BC_PROJECTILE_1C2_KEY & 0x7ff; s.colour = BC_PROJECTILE_1C2_KEY >> 11; break;
    case 0x1c4: s.code = BC_PROJECTILE_1C4_KEY & 0x7ff; s.colour = BC_PROJECTILE_1C4_KEY >> 11; break;
    case 0x1c6: s.code = BC_PROJECTILE_1C6_KEY & 0x7ff; s.colour = BC_PROJECTILE_1C6_KEY >> 11; break;
    case 0x1d4: s.code = BC_PROJECTILE_1D4_KEY & 0x7ff; s.colour = BC_PROJECTILE_1D4_KEY >> 11; break;
    case 0x1d6: s.code = BC_PROJECTILE_1D6_KEY & 0x7ff; s.colour = BC_PROJECTILE_1D6_KEY >> 11; break;
    case 0x1e0: s.code = BC_PROJECTILE_1E0_KEY & 0x7ff; s.colour = BC_PROJECTILE_1E0_KEY >> 11; break;
    case 0x1e2: s.code = BC_PROJECTILE_1E2_KEY & 0x7ff; s.colour = BC_PROJECTILE_1E2_KEY >> 11; break;
    case 0x1e4: s.code = BC_PROJECTILE_1E4_KEY & 0x7ff; s.colour = BC_PROJECTILE_1E4_KEY >> 11; break;
    case 0x1e6: s.code = BC_PROJECTILE_1E6_KEY & 0x7ff; s.colour = BC_PROJECTILE_1E6_KEY >> 11; break;
    default: return s;
    }
    s.handled = s.visible = 1;
    return s;
}
