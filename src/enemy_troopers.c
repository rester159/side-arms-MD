#include "enemy_int.h"

/* Troopers: the jet-pack / walker soldiers of the ground stages (docs/re/objects.md 6).
 *   trooper_tan         B0:$8314  dives in from the right, lands, then jumps / runs and shoots
 *   trooper_green_drop  B0:$8A57  falls from the top, then hops facing the player and shoots
 *   surfacing_robot     B0:$8C9E  surfaces from bubbles, launches two homing missiles, sinks
 *   trooper_hover       B0:$8DB6  hover bike: passes the player, rises and fires missile pairs
 *   trooper_yellow      B0:$90CA  walker that climbs walls and fires 3-way spreads (RNG)
 *   trooper_red         B0:$9547  invisible capsule slides to a wall, sticks to it and opens
 *                                 at random to fire missile pairs
 * Terrain handlers (+$1A, e->wall) mostly probe the terrain 5 px below / above / ahead of the
 * position the engine restored, to tell floors from walls and ceilings ($082F skip-return). */

static inline u8 speed_level(void) { return en_speed < 3 ? 3 : en_speed > 6 ? 6 : en_speed; }

/* Terrain test ($082F) with the object moved by (dy, dx) px, position restored afterwards. */
static bool solid_at(Enemy *e, s16 dy, s16 dx)
{
    s16 x = e->x, y = e->y;
    e->x += dx;
    e->y += dy;
    bool hit = en_terrain(e);
    e->x = x;
    e->y = y;
    return hit;
}

/* One enemy bullet ($05AA, $0531, $4000) in the last aim direction (+$16) from the muzzle at
 * (y+8, ax); the arcade then takes the "fired" script, or the other one when refused. */
static bool fire(Enemy *e, s16 ax)
{
    return en_bullet_at((u8)(AY(e) + 8), ax, e->r[R_AIM]) != NULL;
}

/* Homing missile $499C (native $4963 in enemy_shots.c) starting with launch step `step`. */
static void missile_init(Enemy *m, u8 ay, s16 ax, u16 step)
{
    en_init(m, TPL_499C);
    SET_AY(m, ay);
    SET_AX(m, ax);
    m->next = step;
    m->timer = 1;
}

/* Two missiles at once: one cap test ($05AA), two consecutive small records ($054B). */
static bool missile_pair(u8 ay1, s16 ax1, u16 step1, u8 ay2, s16 ax2, u16 step2)
{
    if (!en_bullet_room()) return FALSE;
    Enemy *m = en_alloc_small_group(2, 2);
    if (!m) return FALSE;
    missile_init(m, ay1, ax1, step1);
    missile_init(m + 1, ay2, ax2, step2);
    return TRUE;
}

/* ==== trooper_tan ========================================================================= */
/* Template $8365 (BG-locked, wall $840F): dives in at (dy +4, dx -3). Bullets leave from the
 * left muzzle (x) or the right one (x+16, sub-record +$23), selected by $E01F = $4C / $52. */

/* B0:$838D: after 15 frames of dive, aim; if the target is to the left (12..20) fire once. */
/* @native 838D */
void tan_dive_aim(Enemy *e)
{
    u8 d = en_aim(e);
    if (d >= 0x0C && d < 0x15 && fire(e, AX(e))) en_set_motion(e, MOT_83E7);
    else en_set_motion(e, MOT_83F1);                    /* keep diving */
}

/* B0:$840F: terrain during the dive. Solid 5 px below = landed: stick to the BG and crouch
 * ($8436: 20 f, then $843E); otherwise it hit a wall: bounce back right falling ($83F6). */
/* @native 840F */
void tan_dive_wall(Enemy *e)
{
    if (solid_at(e, 5, 0)) {
        e->flags |= EF_BGLOCK;
        en_set_motion(e, MOT_8436);
    } else en_set_motion(e, MOT_83F6);
}

/* B0:$843E: after landing, aim. Up-right (27..31): shoot from the right muzzle ($84CC);
 * left (16..22): from the left one ($84BF); otherwise just stand ($84DE). All go to $84E6. */
/* @native 843E */
void tan_land_aim(Enemy *e)
{
    u8 d = en_aim(e);
    if (d >= 0x1B) {
        if (fire(e, SUB_X16(e))) { en_set_motion(e, MOT_84CC); return; }
    } else if (d >= 0x10 && d < 0x17) {
        if (fire(e, AX(e))) { en_set_motion(e, MOT_84BF); return; }
    }
    en_set_motion(e, MOT_84DE);
}

/* B0:$84E6: hop to the left ($850B, 7-frame arcs dx -2) with terrain handler $8551. */
/* @native 84E6 */
void tan_hop(Enemy *e)
{
    e->flags |= EF_BGLOCK;
    e->wall = AI_8551;
    en_set_motion(e, MOT_850B);
}

/* B0:$8551: hop landed (floor 5 px below): crouch and small hop ($8587, wall $85B9);
 * hit a wall: fall back to the right ($8538). */
/* @native 8551 */
void tan_hop_wall(Enemy *e)
{
    if (solid_at(e, 5, 0)) {
        e->wall = AI_85B9;
        en_set_motion(e, MOT_8587);
    } else en_set_motion(e, MOT_8538);
}

/* B0:$85B9: small hop landed: jump straight up facing the target ($85FA left / $8616 right,
 * then $8632 at the top), wall $8703. Hit a wall: fall back right ($85A5). */
/* @native 85B9 */
void tan_hop2_wall(Enemy *e)
{
    if (solid_at(e, 5, 0)) {
        e->wall = AI_8703;
        en_set_motion(e, en_target_x2 < X2(e) ? MOT_85FA : MOT_8616);
    } else en_set_motion(e, MOT_85A5);
}

/* B0:$8632: top of the vertical jump: aim. Right (0..4): right muzzle ($86DB); left-down
 * (12..16): left muzzle ($86B3); otherwise no shot ($86EA). Then it falls back (dy 0..4). */
/* @native 8632 */
void tan_jump_aim(Enemy *e)
{
    u8 d = en_aim(e);
    if (d < 0x05) {
        if (fire(e, SUB_X16(e))) { en_set_motion(e, MOT_86DB); return; }
    } else if (d >= 0x0C && d < 0x11) {
        if (fire(e, AX(e))) { en_set_motion(e, MOT_86B3); return; }
    }
    en_set_motion(e, MOT_86EA);
}

/* B0:$8703: terrain while jumping / falling.
 * - floor 5 px below: if the target is within $10 (x/2) jump again ($85FA); otherwise run
 *   away from it: target left -> run right ($877B, wall $88C2), else run left ($88EF, $8A2A).
 * - floor not below but solid 5 px above (ceiling): shoot / fall now ($8632).
 * - a wall: crouch and small hop again ($8587). */
/* @native 8703 */
void tan_jump_wall(Enemy *e)
{
    if (solid_at(e, 5, 0)) {
        u8 tx = en_target_x2, x2 = X2(e);
        bool left = tx < x2;
        u8 dist = left ? (u8)(x2 - tx) : (u8)(tx - x2);
        if (dist < 0x10) en_set_motion(e, MOT_85FA);
        else if (left) {
            e->wall = AI_88C2;
            en_set_motion(e, MOT_877B);
        } else {
            e->wall = AI_8A2A;
            en_set_motion(e, MOT_88EF);
        }
    } else if (solid_at(e, -5, 0)) tan_jump_aim(e);
    else en_set_motion(e, MOT_8587);
}

/* Running right ($877B: crouch 16 f, then 12/10/12-frame strides): at each stride it aims and
 * fires backwards from the left muzzle. The arcade clamps the direction to 16..20 in A, but
 * $05AA overwrites A and the bullet uses +$16, so the shot is simply aimed (kept as is). */
/* @native 8788 */
void tan_run_r1(Enemy *e)
{
    en_aim(e);
    en_set_motion(e, fire(e, AX(e)) ? MOT_87E3 : MOT_87E8);
}

/* @native 87F0 */
void tan_run_r2(Enemy *e)
{
    en_aim(e);
    en_set_motion(e, fire(e, AX(e)) ? MOT_884B : MOT_8850);
}

/* @native 885D */
void tan_run_r3(Enemy *e)
{
    en_aim(e);
    en_set_motion(e, fire(e, AX(e)) ? MOT_88B8 : MOT_88BD);      /* then drift down (1, 1) */
}

/* B0:$88C2: running right hit terrain: floor below -> next run cycle; a wall -> run left. */
/* @native 88C2 */
void tan_run_r_wall(Enemy *e)
{
    en_set_motion(e, solid_at(e, 5, 0) ? MOT_877B : MOT_88EF);
}

/* Running left ($88EF): the same, firing from the right muzzle (clamp to 28..31 is dead too). */
/* @native 88FC */
void tan_run_l1(Enemy *e)
{
    en_aim(e);
    en_set_motion(e, fire(e, SUB_X16(e)) ? MOT_8953 : MOT_8958);
}

/* @native 8960 */
void tan_run_l2(Enemy *e)
{
    en_aim(e);
    en_set_motion(e, fire(e, SUB_X16(e)) ? MOT_89B7 : MOT_89BC);
}

/* @native 89C9 */
void tan_run_l3(Enemy *e)
{
    en_aim(e);
    en_set_motion(e, fire(e, SUB_X16(e)) ? MOT_8A20 : MOT_8A25);
}

/* B0:$8A2A: running left hit terrain: floor below -> next cycle; a wall -> run right. */
/* @native 8A2A */
void tan_run_l_wall(Enemy *e)
{
    en_set_motion(e, solid_at(e, 5, 0) ? MOT_88EF : MOT_877B);
}

/* ==== trooper_green_drop ================================================================== */
/* Template $8AA4 (BG-locked, wall $8B88). r[0] (+$10): bit 1 = facing right (sprite $206
 * instead of $200), bit 0 = hop to the right. The spawn sets it and the fall step. */

/* B0:$8C7F: hop by r[0] (table $8C91: crouch 12 f, then 7-frame arcs dy -3..+3, dx -/+2). */
/* @native 8C7F */
void green_hop(Enemy *e)
{
    en_set_motion(e, MOTTAB_8C91_4[e->r[0] & 3]);
}

/* B0:$8B88: terrain.
 * - floor 5 px below: rise 5 px, face the target and aim. Facing left it shoots from the
 *   left muzzle if the direction is 10..22 ($8B6E); facing right from the right muzzle if
 *   it is >= 26 or < 7 ($8B7B). Both then hop ($8C7F), as does a refused / no shot.
 * - solid 5 px above (ceiling): drop straight down ($8B64 / $8B69 by facing).
 * - a wall: turn round (facing and hop direction) and hop. */
/* @native 8B88 */
void green_wall(Enemy *e)
{
    if (solid_at(e, 5, 0)) {
        e->y -= 5;                                       /* $8B96: y+5-10, not restored */
        if (en_target_x2 < X2(e)) {
            e->r[0] &= ~2;
            u8 d = en_aim(e);
            if (d >= 0x0A && d < 0x17 && fire(e, AX(e))) { en_set_motion(e, MOT_8B6E); return; }
        } else {
            e->r[0] |= 2;
            u8 d = en_aim(e);
            if ((d >= 0x1A || d < 0x07) && fire(e, SUB_X16(e))) { en_set_motion(e, MOT_8B7B); return; }
        }
        green_hop(e);
    } else if (solid_at(e, -5, 0)) {
        en_set_motion(e, (e->r[0] & 2) ? MOT_8B69 : MOT_8B64);
    } else {
        e->r[0] ^= 3;
        green_hop(e);
    }
}

/* ==== surfacing_robot ===================================================================== */
/* Template $8CCC (BG-locked, shot-proof, no terrain): 20 f of bubbles, then $8CF9. */

/* B0:$8CF9: tangible, emerge ($8D09: 3 x 10 f). */
/* @native 8CF9 */
void surf_emerge(Enemy *e)
{
    e->flags &= ~EF_SHOTPROOF;
    en_set_motion(e, MOT_8D09);
}

/* B0:$8D1B: one missile from (y, x) going up-left ($4A27 -> step $4A2C, heading 20 from the
 * template), cap tested; then 2 x 17 f ($8D53). */
/* @native 8D1B */
void surf_missile1(Enemy *e)
{
    if (en_bullet_room()) {
        Enemy *m = en_alloc(EP_SMALL);
        if (m) missile_init(m, AY(e), AX(e), MOT_4A2C);
    }
    en_set_motion(e, MOT_8D53);
}

/* B0:$8D60: second missile going up-right (heading $1C, $4A2F -> step $4A34), then submerge
 * ($8D9C: 5 x 10 f, kill). */
/* @native 8D60 */
void surf_missile2(Enemy *e)
{
    if (en_bullet_room()) {
        Enemy *m = en_alloc(EP_SMALL);
        if (m) {
            missile_init(m, AY(e), AX(e), MOT_4A34);
            m->r[0] = 0x1C;
        }
    }
    en_set_motion(e, MOT_8D9C);
}

/* ==== trooper_hover ======================================================================= */
/* Template $8E0A (no terrain). From the right ($8E32) or from the left ($8F83). Distances are
 * in x/2 units against the target. Missile pairs ($054B) leave at (y+4) and (y+8), 8 frames
 * apart (launch steps $4B09/$4B0E going left, $4AFC/$4B01 going right). */

static bool hover_missiles(Enemy *e, s16 ax, bool left)
{
    u8 y = AY(e);
    return left ? missile_pair((u8)(y + 4), ax, MOT_4B09, (u8)(y + 8), ax, MOT_4B0E)
                : missile_pair((u8)(y + 4), ax, MOT_4AFC, (u8)(y + 8), ax, MOT_4B01);
}

/* from the right: B0:$8E3F: closer than $40 -> rise and fire left ($8E62 -> $8E6F); else keep
 * flying left 3 f ($8E54) and look again */
/* @native 8E3F */
void hover_r_approach(Enemy *e)
{
    u8 tx = en_target_x2, x2 = X2(e);
    u8 dist = tx >= x2 ? (u8)(tx - x2) : (u8)(x2 - tx);
    en_set_motion(e, dist < 0x40 ? MOT_8E62 : MOT_8E54);
}

/* B0:$8E32: the target is already left of it and within $40: fly past it (70 f, $8EE8) */
/* @native 8E32 */
void hover_r_enter(Enemy *e)
{
    if ((u8)(X2(e) - en_target_x2) < 0x40) en_set_motion(e, MOT_8EE8);
    else hover_r_approach(e);
}

/* B0:$8E6F: missiles from x going left, then $8ECA; refused: leave at once ($8ED8) */
/* @native 8E6F */
void hover_r_fire(Enemy *e)
{
    en_set_motion(e, hover_missiles(e, AX(e), TRUE) ? MOT_8ECA : MOT_8ED8);
}

/* @native 8ED2 */
void hover_r_leave(Enemy *e) { en_set_motion(e, MOT_8ED8); }     /* off to the right */

/* @native 8EF0 */
void hover_r_turn(Enemy *e) { en_set_motion(e, MOT_8EF6); }      /* passed it: rise */

/* B0:$8F03: missiles from x+16 going right (back at the target), then $8F5E; refused: $8F71 */
/* @native 8F03 */
void hover_r_fire_back(Enemy *e)
{
    en_set_motion(e, hover_missiles(e, SUB_X16(e), FALSE) ? MOT_8F5E : MOT_8F71);
}

/* @native 8F6B */
void hover_r_exit(Enemy *e) { en_set_motion(e, MOT_8F71); }      /* off to the left */

/* from the left: B0:$8F8E: closer than $40 -> rise and fire right ($8FB1); else fly right */
/* @native 8F8E */
void hover_l_approach(Enemy *e)
{
    u8 tx = en_target_x2, x2 = X2(e);
    u8 dist = tx >= x2 ? (u8)(tx - x2) : (u8)(x2 - tx);
    en_set_motion(e, dist < 0x40 ? MOT_8FB1 : MOT_8FA3);
}

/* B0:$8F83: the target is right of it and within $40: fly past it ($9037) */
/* @native 8F83 */
void hover_l_enter(Enemy *e)
{
    if ((u8)(en_target_x2 - X2(e)) < 0x40) en_set_motion(e, MOT_9037);
    else hover_l_approach(e);
}

/* B0:$8FBE: missiles from x going right, then $9019; refused: leave left ($9027) */
/* @native 8FBE */
void hover_l_fire(Enemy *e)
{
    en_set_motion(e, hover_missiles(e, AX(e), FALSE) ? MOT_9019 : MOT_9027);
}

/* @native 9021 */
void hover_l_leave(Enemy *e) { en_set_motion(e, MOT_9027); }

/* @native 903F */
void hover_l_turn(Enemy *e) { en_set_motion(e, MOT_9045); }

/* B0:$9052: missiles from x+16 going left, then $90AD; refused: leave right ($90C0) */
/* @native 9052 */
void hover_l_fire_back(Enemy *e)
{
    en_set_motion(e, hover_missiles(e, SUB_X16(e), TRUE) ? MOT_90AD : MOT_90C0);
}

/* @native 90BA */
void hover_l_exit(Enemy *e) { en_set_motion(e, MOT_90C0); }

/* ==== trooper_yellow ====================================================================== */
/* Template $9113 (shot-proof until it lands). The spawn picks the side: from the left it walks
 * right (wall $92BC), from the right it walks left (wall $94C3); both halves of the arcade code
 * are the same routine mirrored, so one C routine with a side description. */

typedef struct {
    s8 dir;                 /* walking direction: +1 right, -1 left */
    u8 walk_wall, climb_wall;
    u16 walk, climb, fall, ceiling_fall, fire_near, fire_far;
} YellowSide;

static const YellowSide YELLOW_R = {     /* came from the left: $92BC / $92FA */
    1, AI_92BC, AI_92FA, MOT_9235, MOT_9262, MOT_92A8, MOT_94AF, MOT_9215, MOT_9222 };
static const YellowSide YELLOW_L = {     /* came from the right: $94C3 / $9503 */
    -1, AI_94C3, AI_9503, MOT_943C, MOT_9469, MOT_94AF, MOT_92A8, MOT_941C, MOT_9429 };

/* 3-way spread: one cap test, 3 consecutive small records ($0561), directions aim-1, aim,
 * aim+1 (the arcade reads 3 consecutive words of the 33-entry direction table), all at (y, ax) */
static bool yellow_spread(Enemy *e, s16 ax, u8 d)
{
    if (!en_bullet_room()) return FALSE;
    Enemy *b = en_alloc_small_group(3, 2);
    if (!b) return FALSE;
    const u16 *tab = en_bullet_dirs[speed_level() - 3];
    for (u16 i = 0; i < 3; i++) {
        en_init(b + i, TPL_4000);
        SET_AY(b + i, AY(e));
        SET_AX(b + i, ax);
        b[i].next = tab[(u8)(d - 1 + i) & 31];
        b[i].timer = 1;
    }
    return TRUE;
}

/* B0:$9138 / $9341: standing on the floor with the way ahead free. RNG $E008 += $99; when it is
 * below $50, the trooper is well inside the screen (x/2 in $38..$C3) and the target is left /
 * above it (aim >= $11), fire a 3-way spread from the left (aim < $18) or right muzzle; else
 * (or refused) walk on ($9235 / $943C: 18 f at 2 px/f, then the floor test again). */
static void yellow_land(Enemy *e, const YellowSide *s)
{
    e->wall = s->walk_wall;
    en_rng += 0x99;
    u8 x2 = X2(e);
    if (en_rng < 0x50 && x2 >= 0x38 && x2 < 0xC4) {
        u8 d = en_aim(e);
        if (d >= 0x11) {
            bool near = d < 0x18;
            if (yellow_spread(e, near ? AX(e) : SUB_X16(e), d)) {
                en_set_motion(e, near ? s->fire_near : s->fire_far);
                return;
            }
        }
    }
    en_set_motion(e, s->walk);
}

/* On the floor: a wall 5 px ahead -> climb it ($9262 / $9469: 8 f at dy -1, wall = climb
 * handler); otherwise $9138. */
static void yellow_ground(Enemy *e, const YellowSide *s)
{
    if (solid_at(e, 0, 5 * s->dir)) {
        e->wall = s->climb_wall;
        en_set_motion(e, s->climb);
    } else yellow_land(e, s);
}

/* B0:$92BC / $94C3 (terrain handler and end of each walk cycle): BG-locked and shootable from
 * now on. Floor within 5 px -> on the floor; within 10 px -> stays where it is (on the floor);
 * no floor -> step 5 px down and fall ($92A8 / $94AF). */
static void yellow_walk_wall(Enemy *e, const YellowSide *s)
{
    e->flags = (e->flags | EF_BGLOCK) & ~EF_SHOTPROOF;
    if (!solid_at(e, 5, 0) && !solid_at(e, 10, 0)) {
        e->y += 5;
        en_set_motion(e, s->fall);
        return;
    }
    yellow_ground(e, s);
}

/* B0:$92FA / $9503 (climbing): a ceiling 5 px above -> fall back away from the wall (the
 * arcade uses the other side's fall script, $94AF / $92A8, keeping this handler); otherwise
 * the floor logic (climb on while the wall is there, then fire / walk). */
static void yellow_climb_wall(Enemy *e, const YellowSide *s)
{
    if (solid_at(e, -5, 0)) en_set_motion(e, s->ceiling_fall);
    else yellow_ground(e, s);
}

/* @native 92BC */
void yellow_r_wall(Enemy *e) { yellow_walk_wall(e, &YELLOW_R); }

/* @native 92FA */
void yellow_r_climb(Enemy *e) { yellow_climb_wall(e, &YELLOW_R); }

/* @native 922F */
void yellow_r_walk(Enemy *e) { en_set_motion(e, MOT_9235); }

/* @native 94C3 */
void yellow_l_wall(Enemy *e) { yellow_walk_wall(e, &YELLOW_L); }

/* @native 9503 */
void yellow_l_climb(Enemy *e) { yellow_climb_wall(e, &YELLOW_L); }

/* @native 9436 */
void yellow_l_walk(Enemy *e) { en_set_motion(e, MOT_943C); }

/* ==== trooper_red ========================================================================= */
/* Template $95AD: an invisible probe (code 0) slides from the spawn point ($9591: left /
 * right / up / down at 4 px/f) until it meets terrain. There it shows one frame (vertical
 * probes also jump 28 px back) and becomes a BG-locked capsule ignoring terrain: $2F0 (opens
 * to the lower right, $9651..) or $2E0 (opens to the lower left, $9733..). */

/* @native 95D2 */
void red_hit_l(Enemy *e) { en_set_motion(e, MOT_95D8); }

/* @native 95F3 */
void red_hit_r(Enemy *e) { en_set_motion(e, MOT_95F9); }

/* @native 9614 */
void red_hit_up(Enemy *e) { en_set_motion(e, MOT_961A); }       /* 1 f at dy +28 */

/* @native 9635 */
void red_hit_down(Enemy *e) { en_set_motion(e, MOT_963B); }     /* 1 f at dy -28 */

/* B0:$95E0 / $9622: capsule $2F0, closed 80 f then 50 f ($9651) */
/* @native 95E0 9622 */
void red_stick_a(Enemy *e)
{
    e->flags |= EF_BGLOCK | EF_NOTERRAIN;
    en_set_motion(e, MOT_9651);
}

/* B0:$9601 / $9643: capsule $2E0 ($9733) */
/* @native 9601 9643 */
void red_stick_b(Enemy *e)
{
    e->flags |= EF_BGLOCK | EF_NOTERRAIN;
    en_set_motion(e, MOT_9733);
}

/* B0:$9671 / $9753: closed: shot-proof, wait 50 f ($967F / $9761) */
/* @native 9671 */
void red_close_a(Enemy *e)
{
    e->flags |= EF_SHOTPROOF;
    en_set_motion(e, MOT_967F);
}

/* @native 9753 */
void red_close_b(Enemy *e)
{
    e->flags |= EF_SHOTPROOF;
    en_set_motion(e, MOT_9761);
}

/* B0:$965E / $9740: every 50 f, RNG $E008 += $63; below $64 (100/256) it closes up and then
 * opens, else it waits another 50 f */
/* @native 965E */
void red_wait_a(Enemy *e)
{
    en_rng += 0x63;
    if (en_rng >= 0x64) en_set_motion(e, MOT_9656);
    else red_close_a(e);
}

/* @native 9740 */
void red_wait_b(Enemy *e)
{
    en_rng += 0x63;
    if (en_rng >= 0x64) en_set_motion(e, MOT_9738);
    else red_close_b(e);
}

/* B0:$9687 / $9769: shootable, the soldier leans out (4 x 8 f, dy +1, dx +1 / -1) */
/* @native 9687 */
void red_open_a(Enemy *e)
{
    e->flags &= ~EF_SHOTPROOF;
    en_set_motion(e, MOT_9697);
}

/* @native 9769 */
void red_open_b(Enemy *e)
{
    e->flags &= ~EF_SHOTPROOF;
    en_set_motion(e, MOT_9779);
}

/* B0:$96AE / $9790: two missiles from (y, x) and (y, x+16), going up-right ($4B16/$4B1B) or
 * up-left ($4B23/$4B28); then pull back in (20 f + 4 x 8 f) and close ($9671 / $9753). */
/* @native 96AE */
void red_fire_a(Enemy *e)
{
    missile_pair(AY(e), AX(e), MOT_4B16, SUB_Y(e), SUB_X16(e), MOT_4B1B);   /* +$22/+$23 */
    en_set_motion(e, MOT_9717);
}

/* @native 9790 */
void red_fire_b(Enemy *e)
{
    missile_pair(AY(e), AX(e), MOT_4B23, SUB_Y(e), SUB_X16(e), MOT_4B28);   /* +$22/+$23 */
    en_set_motion(e, MOT_97F9);
}
