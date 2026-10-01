#include "boss_int.h"

/* The three sprite bosses (docs/re/objects.md 6.1):
 *   type 0  $69D0  section 1      code $4A0 c14, 3 bars, 1 px/f vertical tracking
 *   type 1  $6C12  sections 3, 5  code $4C0 c14, 6 bars, 2 px/f
 *   type 2  $6DB4  sections 7-9   code $4E0 c5,  8 bars, 3 px/f + charges at the player
 * One 8x4-cell (128x64) body at x $140, y $60 (templates $69F7/$6C39/$6DDB),
 * 20 hits per bar, laser bursts (task $3522) and homing missiles (task $36B6).
 *
 * Genesis: the body is eight 32x32 hardware sprites whose patterns sit in VRAM
 * blocks borrowed from the BG metatile cache (boss.c bc_*): 8 per colour the
 * boss shows (normal, hit flash c8, and c0 for the type-2 charge) + 8 for the
 * death explosions. Colour 15 (the arcade's flash partner) is an all-black
 * palette, so those frames simply hide the body. */

typedef void (*Fn)(void);
static const u16 CODE[3] = { 0x4A0, 0x4C0, 0x4E0 };
static const u8 NORMAL[3] = { 14, 14, 5 };          /* $6A17 / $6C59 / $6DFB */
static const u8 BARS[3] = { 3, 6, 8 };               /* template +$10 */
static const u8 LAST_SCORE[3] = { 0x58, 0x60, 0x68 };   /* $6AF9 / $6D3C / $6F93: 30000 / 50000 / 80000 */
static const s8 SPEED[3] = { 1, 2, 3 };              /* $6ACC / $6D0F / $6ED8 dy */
static const u8 LIM_LO[3] = { 0x20, 0x28, 0x30 };    /* $6A9A / $6CDD / $6EA6 */
static const u8 LIM_HI[3] = { 0xA0, 0x98, 0x90 };    /* $6AAF / $6CF2 / $6EBB */
static const u8 STEPS[3] = { 8, 11, 10 };            /* +$12: 8-frame steps per decision */
static const s8 CHARGE_DY[5] = { 2, 1, 0, -1, -2 };  /* $6F69 $6F5C $6F4F $6F42 $6F35 ($61-$65) */

static struct {
    bool on;
    u8 type;
    s16 y, x;                   /* raw top-left of the 8x4 body */
    s8 dy, dx;
    u8 t;                       /* frames left in the current step */
    u8 colour;
    Fn next;                    /* runs when the step ends */
    u8 c11, c12, c13, charge;
    u8 bars, hp, score_idx;
    bool immune, nocontact;
    bool weapons;
    u16 laser_t, missile_t;
    u8 laser_i, missile_i, missile_phase;
    u8 rng;                     /* $E00A */
    u8 prefetch;                /* body blocks loaded ahead so far */
} b;

static void step(u8 frames, s8 dy, s8 dx, u8 colour, Fn next)
{
    b.t = frames; b.dy = dy; b.dx = dx; b.colour = colour; b.next = next;
}

/* ---------------------------------------------------------------- behaviour */
static void decide(void);
static void intro(void);

static void intro_b(void) { step(1, 0, 0, 15, intro); }

/* $6A24: flash c14/c15 for +$11 = $40 loops (128 frames), then the weapon tasks start */
static void intro(void)
{
    if (--b.c11) { step(1, 0, 0, NORMAL[b.type], intro_b); return; }
    b.weapons = TRUE;
    b.laser_t = 60; b.laser_i = 0;                  /* $3531: wait 60 first */
    b.missile_t = 60; b.missile_i = 0; b.missile_phase = 0;
    decide();
}

static void wait_check(void);
static void hold(void) { step(8, 0, 0, NORMAL[b.type], wait_check); }

/* $6AB9: the rest of the +$12 budget is spent holding still */
static void wait_check(void)
{
    if (!b.c12 || !--b.c12) { decide(); return; }
    hold();
}

static void move_up(void);
static void move_down(void);
static void moved_up(void)
{
    b.c12--;
    if (!--b.c13) { wait_check(); return; }
    if (b.y < LIM_LO[b.type]) { hold(); return; }
    move_up();
}
static void moved_down(void)
{
    b.c12--;
    if (!--b.c13) { wait_check(); return; }
    if (b.y >= LIM_HI[b.type]) { hold(); return; }
    move_down();
}
static void move_up(void) { step(8, -SPEED[b.type], 0, NORMAL[b.type], moved_up); }
static void move_down(void) { step(8, SPEED[b.type], 0, NORMAL[b.type], moved_down); }

/* type 2 charge ($6EF0): 1-frame steps c0/c8 at (dy, -4) while y is in [$30,$90)
 * and x/2 >= $28, then back right at +4 px/f until x/2 >= $9E ($6F27/$6F76) */
static void charge(void);
static void retreat(void)
{
    if ((b.x >> 1) >= 0x9E) { decide(); return; }
    step(1, 0, 4, NORMAL[2], retreat);
}
static void charge_b(void) { step(1, CHARGE_DY[b.charge], -4, 8, charge); }
static void charge(void)
{
    if (b.y < 0x30 || b.y >= 0x90 || (b.x >> 1) < 0x28) { retreat(); return; }
    step(1, CHARGE_DY[b.charge], -4, 0, charge_b);
}

/* $6A3F / $6C81 / $6E23: vulnerable again; track the target's Y in 8-frame steps */
static void decide(void)
{
    b.immune = b.nocontact = FALSE;
    if (b.type == 2 && boss_rng(&b.rng, 0x63) < 0x46) {     /* $6E2D: ~27% charge */
        u8 d = boss_aim(b.y, b.x);
        b.charge = d < 0x0D ? 0 : d < 0x0F ? 1 : d < 0x12 ? 2 : d < 0x14 ? 3 : 4;
        charge();
        return;
    }
    s16 ty, tx;
    boss_target(&ty, &tx);
    s16 diff = (u8)(b.y + 16) - (u8)ty;
    bool up = diff >= 0;                                     /* boss lower than the target */
    u8 ad = diff < 0 ? -diff : diff;
    b.c12 = STEPS[b.type];
    if (ad < 16) { hold(); return; }
    if (b.type == 0) b.c13 = (ad & 0xC0) ? 8 : ((ad & 0x38) >> 3) + 1;
    else if (b.type == 1) b.c13 = (ad & 0x80) ? 8 : ((ad & 0x70) >> 4) + 1;
    else b.c13 = ((ad & 0xE0) >> 5) + 1;
    if (up) move_up(); else move_down();
}

/* bar emptied ($6AE4/$6D27/$6F7E): next bar of 20 hits after a c8/c15 flash */
static void dead(void);
static void flash(void);
static void flash_b(void) { step(1, 0, 0, 15, b.c11 ? flash : decide); }
static void flash(void) { b.c11--; step(1, 0, 0, 8, flash_b); }

static void death_flash(void);
static void death_flash_b(void) { step(1, 0, 0, 15, --b.c11 ? death_flash : dead); }
static void death_flash(void) { step(1, 0, 0, 8, death_flash_b); }
static void dead(void) { b.on = FALSE; }

static void bar_lost(void)
{
    b.bars--;
    boss_hud_set(TRUE, b.bars, 20);
    if (!b.bars) {
        /* $6B4E: last bar - clear the screen, explosions, 4 POW, flash 40 times */
        s16 cy = (u8)(b.y + 16), cx2 = (u8)((b.x >> 1) + 0x18);
        b.weapons = FALSE;
        boss_wipe();
        boss_blast_task(blasts_sprite, sizeof(blasts_sprite), cy, cx2);
        boss_pows(cy, cx2, 0x10, 0x18, 0x28);
        b.immune = b.nocontact = TRUE;
        b.c11 = 0x27;                    /* $6B51: +$11 = $28, decremented before the first flash */
        death_flash();
        boss_hud_set(FALSE, 0, 0);
        return;
    }
    if (b.bars == 1) b.score_idx = LAST_SCORE[b.type];
    b.immune = b.nocontact = TRUE;      /* death sets flags |= 3 ($2DEE) until decide() */
    b.hp = 20;
    b.c11 = 6;                           /* $6B0F: 6 x (c8, c15) */
    flash();
}

/* ---------------------------------------------------------------- weapons */

/* task $3522/$3527/$352C: 8 beam records from 4 body cells every table[i] x 6 frames */
static void lasers(void)
{
    sound_play(SND_LASER);
    static BossStep st[8];
    s8 even = -1;
    for (u16 i = 0; i < 8; i++) {
        const BossBeam *bm = &laser_beams[i];
        st[i] = (BossStep){ bm->frames, bm->colour, bm->code, bm->dy, bm->dx };
        /* template $3613: immune, contact 9 x 4*2; odd records get "no contact" ($3555);
         * the death handler $3651 also removes the next record (the pair's other half) */
        pj_beam(b.y + 16 * bm->row, b.x + 16 * bm->col, &st[i], 1, FALSE, !(i & 1), 9, 8, -1);
        if (!(i & 1)) even = pj_last();
        else pj_link(even, pj_last());
    }
}

static void weapons_update(void)
{
    if (!b.weapons) return;
    if (!--b.laser_t) {
        lasers();
        b.laser_i = (b.laser_i + 1) & 15;
        b.laser_t = laser_wait[b.type * 16 + b.laser_i] * 6;
    }
    /* task $36B6/$36BB/$36C0: missile up from cell 12 if y >= $30, a frame later one
     * down if y < $A0 (each only under the bullet cap), then wait table[i] x 6 */
    if (!--b.missile_t) {
        s16 my = b.y + 16, mx = b.x + 64;
        if (b.missile_phase == 0) {
            if (b.y >= 0x30 && boss_can_fire()) {
                pj_missile(my, mx, 0x18, missile_launch_up, 1);
                b.missile_phase = 1; b.missile_t = 1;
                return;
            }
        }
        if (b.y < 0xA0 && boss_can_fire()) pj_missile(my, mx, 0x08, missile_launch_down, 1);
        b.missile_phase = 0;
        if (b.missile_i != 15) b.missile_i++;
        b.missile_t = missile_wait[b.type * 16 + b.missile_i] * 6;
    }
}

/* ---------------------------------------------------------------- framework */

void sboss_reset(void) { memset(&b, 0, sizeof(b)); }

void sboss_start(u8 type)
{
    sboss_reset();
    sound_play(SND_BOSS_IN);                        /* $69D0: sounds $13 then $32/$33/$34 */
    sound_play(0x32 + type);
    b.on = TRUE; b.type = type;
    b.y = 0x60; b.x = 0x140;                        /* template: y $60, x $40 + bit 8 */
    b.bars = BARS[type]; b.hp = 20; b.score_idx = 0x38;
    b.immune = b.nocontact = TRUE;                  /* flags $87 */
    b.c11 = 0x40;
    boss_shift = 32;
    boss_hud_set(TRUE, b.bars, 20);                 /* $0897 */
    bc_reserve(type == 2 ? 24 : 16);                /* 8 per body colour; the death blasts reuse them */
    bs_reserve(3);                                  /* beams, missiles */
    step(1, 0, 0, NORMAL[type], intro_b);
}

bool sboss_update(void)
{
    if (!b.on) return FALSE;
    /* load every colour of the body during the intro (4 blocks per frame) */
    for (u16 n = 0; n < 4 && b.prefetch < 24 && boss_body_colours[b.type][b.prefetch >> 3] != 255; n++, b.prefetch++) {
        u16 k = b.prefetch & 7;
        bc_prefetch(CODE[b.type] + 16 * (k >> 2) + 2 * (k & 3), boss_body_colours[b.type][b.prefetch >> 3]);
    }
    weapons_update();
    if (!--b.t) b.next();
    if (!b.on) return FALSE;
    b.y += b.dy; b.x += b.dx;
    /* boss collisions on odd frames ($2B0B) */
    if (frame & 1) {
        if (!b.immune) {
            Player *who = NULL;
            u8 n = boss_shots(b.y + 0x18, b.x + 0x3C, 16, 6, &who);   /* $2D92: +$0C/+$0D = $10/3 */
            while (n-- && !b.immune) {
                sound_play(SND_HIT);
                if (--b.hp == 0) { boss_score(who, b.score_idx); bar_lost(); }
            }
            if (b.on && b.bars) boss_hud.hits = b.hp;
        }
        if (!b.nocontact) boss_touch(b.y + 16, b.x + 48, 24, 48, 0, 0);   /* $2E16: +$0E/+$0F = $18/$18 */
    }
    return TRUE;
}

void sboss_draw(void)
{
    if (!b.on || b.colour == 15) return;
    s16 x = to_gx(b.x), y = to_gy(b.y);
    for (u16 k = 0; k < 8; k++)                     /* 8x4 cells = 4x2 blocks of 2x2 */
        bc_draw_resident(CODE[b.type] + 16 * (k >> 2) + 2 * (k & 3), b.colour, x + 32 * (k & 3), y + 32 * (k >> 2));
}
