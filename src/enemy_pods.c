#include "enemy_int.h"

/* Spinning pods and segmented snakes (docs/re/objects.md 6):
 *   pod_column_pow  B0:$A905   four POW-carrying pods that stop and shoot
 *   pod_vertical    B0:$AAB3   pods rising/falling at the player's column, shooting until they
 *                              pass the player's height, then turning away
 *   snake_chain_a   $5575      8 linked segments (head, 6 body, tail), template $57FE
 *   snake_chain_b   $5A9C      the claw chain, same engine, template $5D25 */

/* ---- pod column (4 pods, all carrying POW) ----------------------------------------------- */

/* B0:$A9A1: on entry, if the target is near the right edge (x/2 within $30 below $E0) the pod
 * takes the long sweep $AA65, else it slows to a stop ($AA06) */
/* @native A9A1 */
void podcol_enter(Enemy *e)
{
    u8 d = (u8)(0xE0 - en_target_x2);
    en_set_motion(e, d < 0x30 ? MOT_AA65 : MOT_AA06);
}

/* B0:$A9B3: after each 24-frame spin: up to 7 aimed bullets (one per spin), then leave right */
/* @native A9B3 */
void podcol_spin(Enemy *e)
{
    if (++e->r[0] >= 8) { en_set_motion(e, MOT_AA4B); return; }
    en_fire_aimed(e);                                   /* only if the bullet cap allows */
    en_set_motion(e, MOT_AA1A);
}

/* ---- vertical pod ------------------------------------------------------------------------- */

/* B0:$AC24: past the player's height: turn away horizontally, towards the side the target is
 * not on (target x/2 >= $A0 -> sweep right first, $AC92; else $AC32) */
static void podv_turn(Enemy *e)
{
    en_set_motion(e, en_target_x2 >= 0xA0 ? MOT_AC92 : MOT_AC32);
}

/* B0:$AB59 (moving down): while the target is not above it, shoot every 24 frames */
/* @native AB59 */
void podv_down(Enemy *e)
{
    if (en_target_y < AY(e)) { podv_turn(e); return; }
    en_fire_aimed(e);
    en_set_motion(e, MOT_AB2E);
}

/* B0:$ABD4 (moving up) */
/* @native ABD4 */
void podv_up(Enemy *e)
{
    if (en_target_y >= AY(e)) { podv_turn(e); return; }
    en_fire_aimed(e);
    en_set_motion(e, MOT_ABA9);
}

/* B0:$AC49: sweeping right at 4 px/f until x/2 >= $B4, then turn back and leave left */
/* @native AC49 */
void podv_sweep_right(Enemy *e) { en_set_motion(e, X2(e) < 0xB4 ? MOT_AC56 : MOT_AC64); }

/* B0:$ACA9: same, but the way back ends in $ACEF */
/* @native ACA9 */
void podv_sweep_right2(Enemy *e) { en_set_motion(e, X2(e) < 0xB4 ? MOT_ACB6 : MOT_ACC4); }

/* B0:$ACEF: sweeping left until x/2 < $4C, then turn and leave right */
/* @native ACEF */
void podv_sweep_left(Enemy *e) { en_set_motion(e, X2(e) >= 0x4C ? MOT_ACFC : MOT_AD0A); }

/* ---- snakes ------------------------------------------------------------------------------- */
/* The segments sit in consecutive small-object slots, head first. Role r[1]: $48 head, $4D body,
 * $54 tail; heading r[0] = even direction 0..30. At the end of each step:
 *   head: steers one notch (2) towards the player while it is inside a box in the middle of
 *         the screen, else towards the screen centre ($78, $80); after a promotion it flashes for
 *         r[2] steps and only then becomes vulnerable (hp 1 / 3)
 *   body: takes the heading of the segment before it, hp refilled to 250 (practically immune)
 *   tail: same, and fires a straight bullet $4C6E at the player when its heading points away
 *         from the player (aim + 16, or that - 2: the arcade's third test repeats the first)
 * Killing the head promotes the next segment; with only a head, body and tail left the last two
 * blow up too. */

typedef struct {
    const u16 *head_flash, *head, *body, *tail;   /* step tables by heading/2 */
    u8 box_y0, box_y1, box_x0, box_x1;            /* head steering box (y, x/2) */
    u8 promoted_hp;
    u16 boom, boom_next, boom_tail;               /* explosions: dying head / its two followers */
} SnakeKind;

static const SnakeKind SNAKE_A = {                 /* $5660 / death $5616 */
    MOTTAB_577E_16, MOTTAB_579E_16, MOTTAB_57BE_16, MOTTAB_57DE_16,
    0x48, 0xA8, 0x40, 0xB8, 1, MOT_5A78, MOT_5A73, MOT_5A6E };
static const SnakeKind SNAKE_B = {                 /* $5B87 / death $5B3D */
    MOTTAB_5CA5_16, MOTTAB_5CC5_16, MOTTAB_5CE5_16, MOTTAB_5D05_16,
    0x58, 0xA0, 0x48, 0xB0, 3, MOT_5F9F, MOT_5F9A, MOT_5F95 };

enum { ROLE_HEAD = 0x48, ROLE_BODY = 0x4D, ROLE_TAIL = 0x54 };

static u8 prev_heading(Enemy *e)
{
    return e > en_small ? e[-1].r[0] : e->r[0];
}

static void snake_step(Enemy *e, const SnakeKind *k)
{
    u8 h;
    switch (e->r[1]) {
    case ROLE_BODY:
        e->hp = 0xFA;
        e->r[0] = h = prev_heading(e);
        en_set_motion(e, k->body[(h & 0x1E) >> 1]);
        return;
    case ROLE_TAIL: {
        e->hp = 0xFA;
        e->r[0] = h = prev_heading(e);
        u8 away = (en_aim(e) + 0x10) & 0x1E;
        if ((h == away || h == ((away - 2) & 0x1E)) && en_bullet_room()) {
            Enemy *b = en_alloc(EP_SMALL);
            if (b) {
                en_init(b, TPL_4C6E);
                b->x = e->x; b->y = e->y;
                b->colour = e->colour;                       /* $56EA: the whole attr byte */
                b->code = (b->code & 0xFF) | (e->code & 0x700);
                b->next = MOTPTR_4C4E_16[(e->r[R_AIM] & 0xFE) >> 1];
                b->timer = 1;
            }
        }
        en_set_motion(e, k->tail[(h & 0x1E) >> 1]);
        return;
    }
    case ROLE_HEAD: {
        if (e->r[2] && --e->r[2] == 0) e->hp = k->promoted_hp;
        u8 ty = en_target_y, tx = en_target_x2;
        u8 y = AY(e), x2 = X2(e);
        if (y < k->box_y0 || y >= k->box_y1 || x2 < k->box_x0 || x2 >= k->box_x1) { ty = 0x78; tx = 0x80; }
        u8 want = en_aim_at(y, x2, ty, tx) & 0xFE;
        e->r[R_AIM] = want;
        h = e->r[0];
        if (h != want) {
            if (((h - want) & 0x1E) < 0x10) h -= 2; else h += 2;
            h &= 0x1E;
            e->r[0] = h;
        }
        en_set_motion(e, (e->r[2] ? k->head_flash : k->head)[h >> 1]);
        return;
    }
    }
}

/* @native 5660 */
void snake_a_step(Enemy *e) { snake_step(e, &SNAKE_A); }
/* @native 5B87 */
void snake_b_step(Enemy *e) { snake_step(e, &SNAKE_B); }

static void snake_hit(Enemy *e, const SnakeKind *k)
{
    if (e->r[1] != ROLE_HEAD) {
        /* body/tail "death" just makes it tangible again ($5616: flags ^= 3) */
        e->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT);
        return;
    }
    u16 i = en_index(e, en_small);
    Enemy *n1 = i + 1 < N_SMALL ? e + 1 : NULL, *n2 = i + 2 < N_SMALL ? e + 2 : NULL;
    if (n1 && n2 && n2->live && n2->r[1] == ROLE_TAIL) {
        n1->flags ^= EF_SHOTPROOF | EF_NOCONTACT;
        n2->flags ^= EF_SHOTPROOF | EF_NOCONTACT;
        n1->timer = 1; n1->next = k->boom_next;
        n2->timer = 1; n2->next = k->boom_tail;
    }
    if (n1) { n1->r[1] = ROLE_HEAD; n1->r[2] = 8; }
    en_set_motion(e, k->boom);
}

/* @native 5616 */
void snake_a_hit(Enemy *e) { snake_hit(e, &SNAKE_A); }
/* @native 5B3D */
void snake_b_hit(Enemy *e) { snake_hit(e, &SNAKE_B); }
