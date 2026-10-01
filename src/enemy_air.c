#include "enemy_int.h"

/* Homing fliers: drum ship (drum_homing, spawn B0:$AD32-$AD42) and jet (jet_homing, B0:$A4DA-
 * $A4EA), docs/re/objects.md 6. Both enter from the right and aim at the target, then keep the
 * chosen heading in 24-frame spin cycles while the target is still to their left; once it is
 * not, they U-turn, fire one aimed bullet and leave to the right. Headings are picked from the
 * aim direction (0..31) by thresholds. */

/* first value of the table whose limit is above v (the arcade's chain of "cp n / jr c") */
static u16 pick(u8 v, const u8 *lim, const u16 *mot, u16 n)
{
    for (u16 i = 0; i < n; i++)
        if (v < lim[i]) return mot[i];
    return mot[n];
}

/* ---- drum ship -------------------------------------------------------------------------- */

/* B0:$AD83: after the 24-frame entry, aim and take one of 5 headings */
static const u8 ENTRY_LIM[4] = { 0x0D, 0x0F, 0x12, 0x14 };
static const u16 DRUM_ENTRY[5] = { MOT_AE54, MOT_AE29, MOT_ADFE, MOT_ADD3, MOT_ADA8 };

/* @native AD83 */
void drum_enter(Enemy *e)
{
    en_set_motion(e, pick(en_aim(e), ENTRY_LIM, DRUM_ENTRY, 4));
}

/* B0:$AE7F: aim again (heading kept in r[0]) ... */
static const u8 STEER_LIM[8] = { 0x09, 0x0B, 0x0D, 0x0F, 0x12, 0x14, 0x16, 0x18 };
static const u16 DRUM_STEER[9] = { MOT_B027, MOT_AFFC, MOT_AFD1, MOT_AFA6, MOT_AF7B, MOT_AF50,
                                   MOT_AF25, MOT_AEFA, MOT_AF25 };
/* $B052: U-turn by heading, ends with $B103 */
static const u16 DRUM_UTURN[9] = { MOT_B0E7, MOT_B0E7, MOT_B0CB, MOT_B0CB, MOT_B0CB, MOT_B093,
                                   MOT_B093, MOT_B0AF, MOT_B093 };

/* @native AE85 */
void drum_steer_keep(Enemy *e)
{
    /* $AE85: once the target is not left of it any more, turn back */
    if (en_target_x2 >= X2(e)) en_set_motion(e, pick(e->r[0], STEER_LIM, DRUM_UTURN, 8));
    else en_set_motion(e, pick(e->r[0], STEER_LIM, DRUM_STEER, 8));
}

/* @native AE7F */
void drum_steer(Enemy *e)
{
    e->r[0] = en_aim(e);
    drum_steer_keep(e);
}

/* @native B103 */
void drum_leave(Enemy *e) { en_set_motion(e, MOT_B109); }   /* 16 frames at dx +4 */

/* $B111: one aimed bullet, then off to the right */
/* @native B111 */
void drum_fire(Enemy *e)
{
    en_fire_aimed(e);
    en_set_motion(e, MOT_B158);
}

/* ---- jet -------------------------------------------------------------------------------- */

static const u16 JET_ENTRY[5] = { MOT_A5FC, MOT_A5D1, MOT_A5A6, MOT_A57B, MOT_A550 };
static const u16 JET_STEER[9] = { MOT_A7CF, MOT_A7A4, MOT_A779, MOT_A74E, MOT_A723, MOT_A6F8,
                                  MOT_A6CD, MOT_A6A2, MOT_A6CD };
static const u16 JET_UTURN[9] = { MOT_A88F, MOT_A88F, MOT_A873, MOT_A873, MOT_A873, MOT_A83B,
                                  MOT_A83B, MOT_A857, MOT_A83B };

/* @native A52B */
void jet_enter(Enemy *e)
{
    en_set_motion(e, pick(en_aim(e), ENTRY_LIM, JET_ENTRY, 4));
}

/* @native A62D */
void jet_steer_keep(Enemy *e)
{
    if (en_target_x2 >= X2(e)) en_set_motion(e, pick(e->r[0], STEER_LIM, JET_UTURN, 8));
    else en_set_motion(e, pick(e->r[0], STEER_LIM, JET_STEER, 8));
}

/* @native A627 */
void jet_steer(Enemy *e)
{
    e->r[0] = en_aim(e);
    jet_steer_keep(e);
}

/* @native A8AB */
void jet_leave(Enemy *e) { en_set_motion(e, MOT_A8B1); }

/* @native A8B9 */
void jet_fire(Enemy *e)
{
    en_fire_aimed(e);
    en_set_motion(e, MOT_A900);
}
