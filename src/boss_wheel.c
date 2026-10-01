#include "boss_int.h"
#include "bg.h"

/* BG wheel bosses $7192 / $719C / $71A6 (sections 2, 4, 9; docs/re/levels.md 2,
 * docs/re/objects.md 6.1). The wheel itself is background art. In the arcade it
 * turns because the scroll jumps between three copies of the wheel drawn in
 * the world map ($700B, tables $70D2/$70E2/$70F2), every 8/5/3/1 frames as the
 * core loses bars. Eight pods (template $721C, 2x2 $430-$436) ride a 24-point
 * orbit ($7102) one notch per turn and fire (#1 aimed bullets, #2 beams, #3
 * homing missiles); the core ($73DD, $490-$496) in the middle takes 4 bars of
 * 20 hits. Its death moves the camera to the next section ($74E0).
 *
 * Genesis: bg_frames_* (bg.c) keeps the camera still and swaps pre-rendered
 * frames of the wheel rectangle (built at build time from the three copies by
 * tools/build_bosses.py) - a RAM copy and one plane DMA per turn. */

typedef struct {
    s16 y, x;
    u8 t, i, n;
    const BossStep *st;
    u16 code; u8 colour;
    bool locked;                /* flags b5: moves with the background */
    u8 delay;
} Obj;

static struct {
    bool on;
    u8 type;
    bool spinning;              /* $E0D0 != 0 */
    u8 c2, turn, orbit;         /* $E0D2, $E0D1, $E0D3 */
    u8 rng;                     /* $E00B */
    Obj pod[8];
    Obj core;
    u8 core_state;              /* 0 waiting, 1 armouring up, 2 vulnerable, 3 dying */
    u8 c12, bars, hp, score_idx;
    bool immune;
} w;

static void obj_load(Obj *o) { const BossStep *s = &o->st[o->i]; o->t = s->frames; o->code = s->code; o->colour = s->colour; }
static void obj_run(Obj *o, const BossStep *st, u8 n) { o->st = st; o->n = n; o->i = 0; obj_load(o); }

/* ---------------------------------------------------------------- pods */

/* $726C: every pod step rolls $E00B += $4D; >= $E6 fires (if under the bullet cap) */
static void pod_decide(Obj *o)
{
    if (boss_rng(&w.rng, 0x4D) >= 0xE6 && boss_can_fire()) {
        switch (w.type) {
        case 0:                                         /* $7281: bullet $4000, aimed, at (y+8, x) */
            pj_bullet(o->y + 8, o->x, boss_aim(o->y, o->x), 0xFF);
            break;
        case 1: {                                       /* $72D5: beam pair $7333 at (y+8, x / x+16) */
            pj_beam(o->y + 8, o->x, pod_beam_steps, 2, TRUE, TRUE, 12, 8, -1);
            s8 a = pj_last();
            pj_beam(o->y + 8, o->x + 16, pod_beam_steps, 2, TRUE, FALSE, 12, 8, -1);
            pj_link(a, pj_last());
            break;
        }
        default:                                        /* $736E: homing missile, heading left */
            pj_missile(o->y + 8, o->x + 16, 0x10, missile_launch_left, 2);
            break;
        }
        obj_run(o, pod_fire_steps, 5);                  /* $73C1: $430-$436, then 15 frames */
        return;
    }
    obj_run(o, pod_idle_steps, 1);                      /* $73D5 */
}

static void pod_update(Obj *o)
{
    if (o->locked && (frame & 1)) { o->y -= level.dir_y; o->x -= level.dir_x; }   /* $2784: BG lock */
    if (--o->t) return;
    if (o->delay) {                                     /* $723F: hidden for the start delay */
        o->t = o->delay; o->delay = 0;
        return;
    }
    if (!o->locked) {                                   /* $7256: lock to the BG, 250 frames idle */
        o->locked = TRUE;
        static const BossStep idle250 = { 250, 5, 0x430, 0, 0 };   /* $7264 */
        obj_run(o, &idle250, 1);
        return;
    }
    if (++o->i < o->n) { obj_load(o); return; }
    pod_decide(o);
}

/* ---------------------------------------------------------------- core */

static void core_update(void)
{
    Obj *o = &w.core;
    if (o->locked && (frame & 1)) { o->y -= level.dir_y; o->x -= level.dir_x; }
    if (--o->t) return;
    switch (w.core_state) {
    case 0:                                             /* $7400: two waits of +$11 = $7A */
        if (o->delay) { o->t = o->delay; o->delay = 0; return; }
        o->locked = TRUE; w.core_state = 1; w.c12 = 0x10;
        /* fall through */
    case 1:                                             /* $7417: 15 turns of armour, immune */
        if (o->n && ++o->i < o->n) { obj_load(o); return; }
        if (--w.c12) { obj_run(o, core_idle_steps, 4); return; }
        w.core_state = 2; w.immune = FALSE;             /* $7441 */
        obj_run(o, core_idle_steps, 4);
        return;
    case 2:                                             /* $7451 (and the hit flash $74A1) */
        if (++o->i < o->n) { obj_load(o); return; }
        obj_run(o, core_idle_steps, 4);
        return;
    default:                                            /* death flash $75AA, then gone */
        if (++o->i < o->n) { obj_load(o); return; }
        w.on = FALSE;
        return;
    }
}

static void core_bar_lost(void)
{
    w.bars--;
    boss_hud_set(TRUE, w.bars, 20);
    if (!w.bars) {
        /* $74E0: wipe, camera to the next section (copy 3 = its start), explosions, POW */
        Obj *o = &w.core;
        boss_defeated();
        boss_wipe();
        w.spinning = FALSE;
        bg_frames_end();
        level_start(level.section + 1);
        level_halt();
        boss_blast_task(blasts_wheel, sizeof(blasts_wheel), 0x78, 0xA8);
        boss_pows(0x78, 0xA8, 0, 0x28, 0x24);
        w.core_state = 3; w.immune = TRUE;
        static BossStep fl[32];                         /* $75AA: 16 x ($440 c8, $440 c15) */
        for (u16 i = 0; i < 32; i++) fl[i] = (BossStep){ 1, (i & 1) ? 15 : 8, 0x440, 0, 0 };
        obj_run(o, fl, 32);
        boss_hud_set(FALSE, 0, 0);
        return;
    }
    if (w.bars == 1) w.score_idx = 0x60;               /* $747D: 50000 */
    w.hp = 20;
    w.c2 = 0;                                           /* $748F */
    sound_play(SND_CRACK);                              /* task $365F (text-layer cracks: not drawn) */
    obj_run(&w.core, core_hit_steps, 16);               /* 12 flash frames, then the idle loop */
}

/* ---------------------------------------------------------------- the wheel */

/* $700B: one turn every 1/3/5/8/12 frames for core bars 1/2/3/4/more */
static void spin(void)
{
    static const u8 PERIOD[5] = { 1, 3, 5, 8, 12 };
    u8 e = PERIOD[w.bars >= 1 && w.bars <= 4 ? w.bars - 1 : 4];
    if (++w.c2 >= e) w.c2 = 0;
    if (w.c2) return;
    if (++w.turn >= 3) w.turn = 0;
    bg_frames_show(w.turn);                             /* arcade: scroll = copy[turn] */
    if (++w.orbit >= 24) w.orbit = 0;
    for (u16 k = 0; k < 8; k++) {                       /* $7086: pod k at orbit point turn+3k */
        const u16 *p = &wheel_orbit[((w.orbit + 3 * k) % 24) * 2];
        w.pod[k].y = p[0]; w.pod[k].x = p[1];
    }
}

void wboss_reset(void)
{
    if (w.spinning) bg_frames_end();
    memset(&w, 0, sizeof(w));
}

void wboss_start(u8 type)
{
    wboss_reset();
    boss_wipe();                                        /* $71B3: the big-object area is cleared */
    sound_play(SND_WHEEL);
    w.on = TRUE; w.type = type;
    boss_shift = 0;
    for (u16 k = 0; k < 8; k++) {                       /* $71C0: template $721C, x $1BF */
        Obj *o = &w.pod[k];
        o->y = wheel_pod_start[2 * k]; o->x = 0x1BF; o->t = 1; o->delay = wheel_pod_start[2 * k + 1];
    }
    w.core.y = 0x70; w.core.x = 0x1BF; w.core.t = 0x7A; w.core.delay = 0x7A;   /* $73DD, $7202 */
    w.bars = 4; w.hp = 20; w.score_idx = 0x38; w.immune = TRUE;
    boss_hud_set(TRUE, w.bars, 20);                     /* $089C */
    bc_reserve(10);                                     /* pods 4 + core 5 patterns (+1); wheel 1 pins 44 of 56 slots */
    bs_reserve(1);                                      /* pod shots */
}

bool wboss_update(void)
{
    if (!w.on) return FALSE;
    /* task $3B3A: once the halt lands, start turning ($E0D0 = $61-$63) */
    if (!w.spinning && level.mode == SCROLL_HALT && w.core_state < 3) {
        const WheelInfo *wi = &wheel_info[w.type];
        w.spinning = TRUE; w.c2 = w.turn = w.orbit = 0;
        level.scroll_x = wi->copy_x[0]; level.scroll_y = wi->copy_y[0];
        video_set_camera(cam_x(), cam_y());
        bg_frames_begin(bg_is_home() && wi->frames_home ? wi->frames_home : wi->frames);   /* Home: sockets filled */
    }
    if (w.spinning) spin();
    for (u16 k = 0; k < 8; k++) if (w.core_state < 3) pod_update(&w.pod[k]);
    core_update();
    if (!w.on) return FALSE;
    /* core: shots on odd frames ($29C7: P = (y+8, x+8), +$0C/+$0D = $12/2), no contact */
    if ((frame & 1) && !w.immune) {
        Player *who = NULL;
        u8 n = boss_shots(w.core.y + 8, w.core.x + 8, 0x12, 4, &who);
        while (n-- && !w.immune && w.bars) {
            sound_play(SND_HIT);
            if (--w.hp == 0) { boss_score(who, w.score_idx); core_bar_lost(); }
        }
        if (w.bars) boss_hud.hits = w.hp;
    }
    return TRUE;
}

void wboss_draw(void)
{
    if (!w.on) return;
    if (w.core.code && w.core.colour != 15) bc_draw(w.core.code, w.core.colour, to_gx(w.core.x), to_gy(w.core.y));
    if (w.core_state >= 3) return;
    for (u16 k = 0; k < 8; k++) {
        Obj *o = &w.pod[k];
        if (o->code) bc_draw(o->code, o->colour, to_gx(o->x), to_gy(o->y));
    }
}
