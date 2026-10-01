#include "enemy_int.h"

/* Enemy projectiles shared by several families (docs/re/objects.md 5). */

/* Enemy bullet $4000 on terrain ($4940): intangible, then the small spark $494E. */
/* @native 4940 */
void bullet_hits_wall(Enemy *e)
{
    e->flags |= EF_SHOTPROOF | EF_NOCONTACT | EF_NOTERRAIN;
    en_set_motion(e, MOT_494E);
}

/* Homing missile ($499C, $4B89): heading r[0] in 16 directions (even values 0..30). At the end
 * of each motion step it aims (to an even direction) and, unless already on target, turns one
 * notch (2) towards it; then it plays the step for its heading: tables $49DC (on target) /
 * $49BC (turning) for $499C, $4BA9 for $4B89 ($4963 / $4B50). */
static void home(Enemy *e, const u16 *straight, const u16 *turning)
{
    u8 want = en_aim(e) & 0xFE;
    e->r[R_AIM] = want;
    u8 h = e->r[0];
    if (h == want) { en_set_motion(e, straight[(h & 0x1E) >> 1]); return; }
    if (((h - want) & 0x1E) < 0x10) h -= 2; else h += 2;
    h &= 0x1E;
    e->r[0] = h;
    en_set_motion(e, turning[h >> 1]);
}

/* @native 4963 */
void missile_home(Enemy *e) { home(e, MOTTAB_49DC_16, MOTTAB_49BC_16); }

/* @native 4B50 */
void boss_missile_home(Enemy *e) { home(e, MOTTAB_4BA9_16, MOTTAB_4BA9_16); }
