#include "enemy_int.h"

/* Ground / fixed enemies and their projectiles (docs/re/objects.md 6):
 *   bomb_column        B0:$9815   4 hidden bombs that drop when the player passes under them
 *   turret_crab        B0:$9B27   BG-locked turret, 3-way aimed spread
 *   turret_missile     B0:$9CB7   BG-locked turret, one homing missile
 *   turret_spike       B0:$9EAD   BG-locked turret, bursts of 4 aimed bullets
 *   turret_dome_laser  B0:$A008   BG-locked dome, aimed laser $A14E
 *   eye_turret         B0:$B65D   5 blinking eyes that shoot, then dash at the player
 *   orb_burst          B0:$B15D   drifting orb that bursts into 8 fragments
 *   mine_homing        B0:$BAF6   small homing mine
 *   barrier_pair       B0:$BD66   two shutters opening and closing
 * Turret orientation (+$10, r[0]) decides the sprite and the muzzle; the spawn position and
 * orientation come from the generator (spawn tables $9B7C/$9D08/$9F02/$A05D). */

/* arcade $E00F: the turrets' "random" byte (stepped every 3 frames with the RNG, enemies.c),
 * += $63 at every decision */
static u8 turret_roll(void) { return EN_E00F = (u8)(EN_E00F + 0x63); }

static inline u8 speed_level(void) { return en_speed < 3 ? 3 : en_speed > 6 ? 6 : en_speed; }

/* Bullet $4000 at (ay, ax), aimed at the target from e ($05AA + $0531 + $06E8 + table $E050) */
static bool shoot_from(Enemy *e, u8 ay, s16 ax)
{
    if (!en_bullet_room()) return FALSE;
    Enemy *b = en_alloc(EP_SMALL);
    if (!b) return FALSE;
    en_init(b, TPL_4000);
    SET_AY(b, ay);
    SET_AX(b, ax);
    b->next = en_bullet_dirs[speed_level() - 3][en_aim(e) & 31];
    b->timer = 1;
    return TRUE;
}

/* Homing turn shared by the bomb and the missiles: heading r[0] in 16 directions; aim (even),
 * turn one notch (2) towards it unless already on target, then play the step for the heading */
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

/* ==== bomb column ========================================================================= */
/* The spawn ($9815) puts 4 bombs in 4 consecutive small records: hidden (code 0), shot-proof,
 * no contact, BG-locked. Only the first one runs $984A; the others wait on a 255-frame timer. */

/* B0:$984A: while the target is more than $18 (x/2 units) away horizontally, stay hidden and
 * look again every 3 frames ($994D). Otherwise all four arm (tangible) and start falling
 * ($9955, dy 1 -> 5 px/f), the neighbours after 20/40/60 frames. */
/* @native 984A */
void bomb_wait(Enemy *e)
{
    u8 x2 = X2(e);                              /* stale +$17, as the arcade */
    u8 d = en_target_x2 >= x2 ? en_target_x2 - x2 : x2 - en_target_x2;
    if (d >= 0x18) { en_set_motion(e, MOT_994D); return; }
    for (u16 k = 0; k < 4; k++) {
        Enemy *b = e + k;
        if (b >= en_small + N_SMALL || !b->live) continue;
        b->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT);
        if (k) b->timer = 20 * k;              /* their next step is the fall $9955 */
    }
    en_set_motion(e, MOT_9955);
}

/* B0:$9883 (terrain handler and death): intangible, 1 HP; the first time (+$11 = 2) it lands
 * ($9ADA, 28 frames, then $98A0), the second time it explodes ($9B03). */
/* @native 9883 */
void bomb_hit(Enemy *e)
{
    e->flags |= EF_SHOTPROOF | EF_NOCONTACT;
    e->hp = 1;
    en_set_motion(e, --e->r[1] ? MOT_9ADA : MOT_9B03);
}

/* B0:$98A0: after landing: tangible again, heading up ($18), bounce up ($9AF1) and home */
/* @native 98A0 */
void bomb_bounce(Enemy *e)
{
    e->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT);
    e->r[0] = 0x18;
    en_set_motion(e, MOT_9AF1);
}

/* B0:$98B4: homing flight, tables $990D (on target) / $98ED (turning) */
/* @native 98B4 */
void bomb_home(Enemy *e) { home(e, MOTTAB_990D_16, MOTTAB_98ED_16); }

/* ==== turret crab ========================================================================= */
/* B0:$9BDC every 50 frames (then 39/28-frame cycles): $E00F += $63; below $64 it fires a 3-way
 * spread (aim-1, aim, aim+1) from 3 consecutive small records ($05AA once, then $0561). The
 * muzzle is the bottom edge for orientation $6D (hanging), else the top; x + 8. */
/* @native 9BDC */
void crab_think(Enemy *e)
{
    bool hang = e->r[0] == 0x6D;
    Enemy *b;
    if (turret_roll() < 0x64 && en_bullet_room() && (b = en_alloc_small_group(3, 2)) != NULL) {
        u8 d = en_aim(e) - 1;
        u8 ay = hang ? SUB_Y16(e) : AY(e);           /* $9C46: +$42 */
        const u16 *tab = en_bullet_dirs[speed_level() - 3];
        for (u16 k = 0; k < 3; k++, b++) {
            en_init(b, TPL_4000);
            SET_AY(b, ay);
            SET_AX(b, AX(e) + 8);
            /* the arcade reads 3 consecutive table words; past entry 31 it would read the next
             * table, here the direction wraps (UNCONFIRMED edge case) */
            b->next = tab[(u8)(d + k) & 31];
            b->timer = 1;
        }
        en_set_motion(e, hang ? MOT_9C99 : MOT_9CA6);
        return;
    }
    en_set_motion(e, hang ? MOT_9C9E : MOT_9CAB);
}

/* ==== turret missile ====================================================================== */
/* B0:$9D78: $E00F += $63; below $C8 it launches one homing missile ($499C) whose start heading,
 * first leg and muzzle depend on the orientation: $61 down from the bottom edge, $62 up from
 * the top, $63 right from the right edge, $64 left from the left edge. The missile then homes
 * with $4B50 (enemy_shots.c). */
typedef struct { u8 heading; s8 dy, dx; } MissileMuzzle;
static const MissileMuzzle MUZZLE[4] = {
    { 0x08, 16, 8 },        /* $61: (y+16, x+8), step $4B30 */
    { 0x18, 0, 8 },         /* $62: (y, x+8),    step $4B38 */
    { 0x00, 8, 16 },        /* $63: (y+8, x+16), step $4B40 */
    { 0x10, 8, 0 },         /* $64: (y+8, x),    step $4B48 */
};

/* @native 9D78 */
void mturret_think(Enemy *e)
{
    static const u16 fire[4] = { MOT_9E79, MOT_9E86, MOT_9E93, MOT_9EA0 };
    static const u16 idle[4] = { MOT_9E7E, MOT_9E8B, MOT_9E98, MOT_9EA5 };
    static const u16 leg[4] = { MOT_4B30, MOT_4B38, MOT_4B40, MOT_4B48 };
    u8 o = e->r[0] - 0x61;
    if (o > 3) o = 3;                           /* anything else is treated as $64 */
    Enemy *m;
    if (turret_roll() < 0xC8 && en_bullet_room() && (m = en_alloc(EP_SMALL)) != NULL) {
        en_init(m, TPL_499C);
        m->r[0] = MUZZLE[o].heading;
        m->next = leg[o];
        m->timer = 1;
        SET_AY(m, AY(e) + MUZZLE[o].dy);
        SET_AX(m, AX(e) + MUZZLE[o].dx);
        if (o == 0) SET_AY(m, SUB_Y16(e));                       /* $9DBE: +$42 */
        else if (o == 2) { SET_AY(m, SUB_Y(e) + 8); SET_AX(m, SUB_X16(e)); }   /* $9E16/$9E1E: +$22/+$23 */
        en_set_motion(e, fire[o]);
        return;
    }
    en_set_motion(e, idle[o]);
}

/* ==== turret spike ======================================================================== */
/* B0:$9F62: one aimed bullet every 22 frames, 4 in a row (+$11 counts), then a 60-frame rest
 * ($9FCA, counter reset) and again. No bullet slot also means rest. Muzzle: bottom edge for
 * orientation $61, else the top; x + 8. */
/* @native 9F62 */
void spike_think(Enemy *e)
{
    bool down = e->r[0] == 0x61;
    if (e->r[1] != 4) {
        e->r[1]++;
        if (shoot_from(e, down ? SUB_Y16(e) : AY(e), AX(e) + 8)) {     /* $9F9C: +$42 */
            en_set_motion(e, down ? MOT_9FDE : MOT_9FF3);
            return;
        }
    }
    e->r[1] = 0;                                /* $9FCA */
    en_set_motion(e, down ? MOT_9FEB : MOT_A000);
}

/* ==== dome laser ========================================================================== */
/* B0:$A0BD: $E00F += $63; at $B4 or more (and a bullet slot free under the cap) it fires the
 * laser $A14E (category $7F, BG-locked) aimed through the 32-entry table $A16E; muzzle as the
 * spike turret. */
/* @native A0BD */
void dome_think(Enemy *e)
{
    bool down = e->r[0] == 0x61;
    Enemy *l;
    if (turret_roll() >= 0xB4 && en_bullet_room() && (l = en_alloc(EP_SMALL)) != NULL) {
        en_init(l, TPL_A14E);
        l->next = MOTPTR_A16E_32[en_aim(e) & 31];
        l->timer = 1;
        SET_AY(l, down ? SUB_Y16(e) : AY(e));        /* $A0F6: +$42 */
        SET_AX(l, AX(e) + 8);
        en_set_motion(e, down ? MOT_A134 : MOT_A141);
        return;
    }
    en_set_motion(e, down ? MOT_A139 : MOT_A146);
}

/* B0:$A3F0 (laser terrain handler and death): a 2x2 burn ($A432) at (y-8, x-8) if a big slot
 * is free, and the beam ends in a small spark ($A41D). */
/* @native A3F0 */
void laser_end(Enemy *e)
{
    Enemy *f = en_alloc(EP_BIG);
    if (f) {
        en_init(f, TPL_A432);
        f->pool = EP_BIG;                       /* generated TPL_ inits are tagged small */
        SET_AY(f, AY(e) - 8);
        SET_AX(f, AX(e) - 8);
    }
    en_set_motion(e, MOT_A41D);
}

/* ==== eye turret ========================================================================== */
/* Five eyes in big slots 3-7 (B0:$B65D; the first has +$10 = $4D, the others start 2-5 frames
 * later). Each blinks (code / blank) +$11 times, intangible; then it opens and shoots. */

/* B0:$B953: dash at the target in one of 16 headings (table $B966) */
static void eye_leave(Enemy *e)
{
    en_set_motion(e, MOTTAB_B966_16[(en_aim(e) & 0x1E) >> 1]);
}

/* B0:$B88E: +$12 counts the shots; at 0, or once the leader died (+$10 = $47), dash away.
 * Otherwise one aimed bullet from the centre (y+8, x+8) and a 40-frame cycle ($B8EE / $B8F8). */
/* @native B88E */
void eye_fire(Enemy *e)
{
    if (--e->r[2] == 0 || e->r[0] == 0x47) { eye_leave(e); return; }
    en_set_motion(e, shoot_from(e, (u8)(AY(e) + 8), AX(e) + 8) ? MOT_B8EE : MOT_B8F8);
}

/* B0:$B879: end of a blink cycle */
/* @native B879 */
void eye_blink(Enemy *e)
{
    if (--e->r[1]) { en_set_motion(e, MOT_B84E); return; }
    e->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT);
    eye_fire(e);
}

/* B0:$B90F (death): when the leader ($4D) dies, every other eye still alive (category $41 in
 * slots $F800-$F980) is told to leave at its next shot ($47). Then the big explosion. */
/* @native B90F */
void eye_death(Enemy *e)
{
    if (e->r[0] == 0x4D)
        for (u16 i = 4; i < 8; i++)
            if (en_big[i].live && en_big[i].cat == 0x41) en_big[i].r[0] = 0x47;
    en_set_motion(e, MOT_4D5E);
}

/* ==== orb burst =========================================================================== */
/* The orb drifts left 2 px/f for 60 frames. Then ($B2DE), or when shot ($B49E), the 256-byte
 * block $B1DE (8 records) is copied over the whole item pool $FF00-$FFFF: 8 fragments at the
 * orb centre (y+8, x+8). */
static const u16 FRAG_TPL[8] = { TPL_B1DE, TPL_B1FE, TPL_B21E, TPL_B23E,
                                 TPL_B25E, TPL_B27E, TPL_B29E, TPL_B2BE };

static void orb_fragments(Enemy *e)
{
    for (u16 k = 0; k < N_ITEM; k++) {
        Enemy *f = &en_item[k];
        en_remove(f);                           /* the copy overwrites whatever was there */
        en_init(f, FRAG_TPL[k]);
        f->pool = EP_ITEM;
        /* +$1A of these records is not a terrain handler (they ignore terrain) but the circle
         * entry used by $B398, see FRAG_CIRCLE */
        f->wall = 0;
        SET_AY(f, AY(e) + 8);
        SET_AX(f, AX(e) + 8);
    }
}

/* B0:$B2DE: natural burst: radial fragments (template motions), orb explodes */
/* @native B2DE */
void orb_burst(Enemy *e)
{
    orb_fragments(e);
    e->flags |= EF_SHOTPROOF | EF_NOCONTACT;
    en_set_motion(e, MOT_4D5E);
}

/* B0:$B49E (death): the fragments instead stream at the target: from the aim direction a,
 * c = (a-2) & $1E picks 3 neighbouring headings of table $B569 for fragments 0-1, 2-5, 6-7,
 * started 9/13/1/5/9/13/9/13 frames later. */
/* @native B49E */
void orb_death(Enemy *e)
{
    static const u8 delay[8] = { 9, 13, 1, 5, 9, 13, 9, 13 };
    static const u8 group[8] = { 0, 0, 1, 1, 1, 1, 2, 2 };
    orb_fragments(e);
    u8 c = (u8)((en_aim(e) - 2) & 0x1E) >> 1;
    for (u16 k = 0; k < N_ITEM; k++) {
        en_item[k].next = MOTPTR_B569_18[c + group[k]];
        en_item[k].timer = delay[k];
    }
    en_set_motion(e, MOT_4D5E);
}

/* fragment k continues on the shared circle $B3E6..$B409 from step k (record +$1A = $B3E1+5k) */
static const u16 FRAG_CIRCLE[8] = { MOT_B3E6, MOT_B3EB, MOT_B3F0, MOT_B3F5,
                                    MOT_B3FA, MOT_B3FF, MOT_B404, MOT_B409 };

/* B0:$B398: end of the first radial leg: one aimed bullet from the fragment's own position,
 * then join the circle (the arcade sets the pointer and returns: it starts next frame) */
/* @native B398 */
void frag_leg(Enemy *e)
{
    shoot_from(e, AY(e), AX(e));
    e->next = FRAG_CIRCLE[en_index(e, en_item) & 7];
    e->timer = 1;
}

/* B0:$B411: end of a circle: after the third one (+$10), every item-pool object is switched to
 * $B458 (the last shot) at once */
/* @native B411 */
void frag_circle(Enemy *e)
{
    if (++e->r[0] != 3) { en_set_motion(e, MOT_B3E6); return; }
    for (u16 k = 0; k < N_ITEM; k++) {
        if (!en_item[k].live) continue;
        en_item[k].next = MOT_B458;
        en_item[k].timer = 1;
    }
}

/* B0:$B45B: last aimed bullet, then the small explosion ($4DAB) */
/* @native B45B */
void frag_last(Enemy *e)
{
    shoot_from(e, AY(e), AX(e));
    en_set_motion(e, MOT_4DAB);
}

/* ==== homing mine ========================================================================= */
/* B0:$BB79: first heading from the aim (16 directions, table $BBB3: 40 frames). The heading is
 * not stored, so the first check below compares with +$10 = 0. */
/* @native BB79 */
void mine_start(Enemy *e)
{
    en_set_motion(e, MOTTAB_BBB3_16[(en_aim(e) & 0x1E) >> 1]);
}

static void mine_go(Enemy *e, u8 d)
{
    e->r[0] = d;
    en_set_motion(e, MOTTAB_BBD3_16[d >> 1]);   /* 24 frames */
}

/* B0:$BB8C: aim again and go */
/* @native BB8C */
void mine_aim(Enemy *e) { mine_go(e, en_aim(e) & 0x1E); }

/* B0:$BBA2: same heading -> keep going; else spin in place 32 frames ($BCC3), then $BB8C */
/* @native BBA2 */
void mine_check(Enemy *e)
{
    u8 d = en_aim(e) & 0x1E;
    if (d == e->r[0]) mine_go(e, d);
    else en_set_motion(e, MOT_BCC3);
}

/* ==== barrier pair ======================================================================== */
/* Two shutter halves ($BDBD left, $BDDD right). Each cycle: closed for a while, then it opens
 * (no contact, $BE31/$BEB7: 24 f opening, 70 f open, 52 f closing), then contact again while
 * closed ($BE71/$BEF7 -> 50 f hold and back). */
/* @native BE23 */
void barrier_l_open(Enemy *e) { e->flags |= EF_NOCONTACT; en_set_motion(e, MOT_BE31); }
/* @native BE61 */
void barrier_l_close(Enemy *e) { e->flags &= ~EF_NOCONTACT; en_set_motion(e, MOT_BE71); }
/* @native BEA9 */
void barrier_r_open(Enemy *e) { e->flags |= EF_NOCONTACT; en_set_motion(e, MOT_BEB7); }
/* @native BEE7 */
void barrier_r_close(Enemy *e) { e->flags &= ~EF_NOCONTACT; en_set_motion(e, MOT_BEF7); }
