#include "enemy_int.h"
#include "sprites.h"

/* Enemy engine: object pools, motion steps, terrain, collisions, spawning, aiming, enemy
 * bullets and drawing. Behaviour from docs/re/objects.md (arcade addresses cited); the
 * per-family behaviour functions live in enemy_*.c, pickups in items.c, effects in fx.c.
 *
 * Each object plays a motion script: a list of steps (show sprite code/colour for N frames,
 * moving dy/dx px per frame) generated from the arcade's scripts by tools/build_enemies.py.
 * A control step can call a family behaviour function (the arcade's "native" steps), which
 * typically aims at the player and picks the next script. */

Enemy en_small[N_SMALL], en_big[N_BIG], en_item[N_ITEM];
u8 en_target_y = 0x78, en_target_x2 = 0xE0;     /* B2:$820F: no player -> ($78, $E0) */
u8 en_rng;
u8 en_rnd[7];               /* $E009-$E00F */
u8 en_rng_div;              /* the RNG steps once every 3 frames (the credit task's turn, $08E3) */
s8 en_scroll_dx, en_scroll_dy;
u16 enemy_spawned, enemy_dropped, en_missing_count;
volatile u16 en_prof_update, en_prof_draw;     /* debug: scanlines spent in update / draw */
volatile u16 en_prof_nobj;                     /* debug: live objects at the start of the update */
volatile u8 en_dbg_nodraw;                     /* test hook: skip enemies_draw (profiling) */

static u8 cont;             /* the behaviour function asked to keep moving this frame */
static s16 last_sx, last_sy;    /* camera and scroll direction at the end of the last update */
static s8 last_dir_x, last_dir_y;
static u8 n_live[3];        /* live objects per pool */
static u8 bullets_live;     /* live category-0 objects ($E400) */
static u8 pending_letter;   /* item letter for the next carrier ($E048) */
u8 en_target_tick;          /* $E027: the target is re-chosen when it is a multiple of 8 */
static u16 native_step;     /* step of the native being run (for en_native_missing) */

void fx_update(void);
void fx_draw(void);
void fx_clear(void);

/* ------------------------------------------------------------------------------------------ */
/* pools                                                                                       */

static Enemy *pool_base(u8 pool, u16 *n)
{
    if (pool == EP_BIG) { *n = N_BIG; return en_big; }
    if (pool == EP_ITEM) { *n = N_ITEM; return en_item; }
    *n = N_SMALL; return en_small;
}

/* $0528 / $0531 / $0583: first free slot, lowest address first */
Enemy *en_alloc(u8 pool)
{
    u16 n;
    Enemy *e = pool_base(pool, &n);
    for (; n; n--, e++)
        if (!e->live) return e;
    return NULL;
}

/* $054B/$0561/$057A and the snake allocator $5575: n consecutive free records starting at a
 * multiple of align */
Enemy *en_alloc_small_group(u8 n, u8 align)
{
    for (u16 i = 0; i + n <= N_SMALL; i += align) {
        u16 k = 0;
        while (k < n && !en_small[i + k].live) k++;
        if (k == n) return &en_small[i];
    }
    return NULL;
}

void en_init(Enemy *e, u16 init)
{
    const EnemyInit *t = &enemy_inits[init];
    e->live = 1;
    /* the pool is where the slot is (a template may be copied into any pool) */
    e->pool = (e >= en_big && e < en_big + N_BIG) ? EP_BIG : (e >= en_item && e < en_item + N_ITEM) ? EP_ITEM : EP_SMALL;
    e->flags = t->flags;
    e->cat = t->cat;
    e->x = t->x; e->y = t->y;
    e->dy = t->dy; e->dx = t->dx;
    e->timer = t->timer;
    e->colour = t->colour;
    e->code = t->code;
    e->next = t->next;
    e->hp = t->hp;
    e->item = t->item;
    memcpy(e->box, t->box, 4);
    memcpy(e->r, t->r, 10);
    e->wall = t->wall;
    e->death = t->death;
    e->sub_x = AX(e) + 16; e->sub_y = AY(e);
    if (e->cat == 0) bullets_live++;
    n_live[e->pool]++;
    enemy_spawned++;
}

Enemy *en_spawn(u8 pool, u16 init)
{
    Enemy *e = en_alloc(pool);
    if (e) en_init(e, init);
    return e;
}

void en_remove(Enemy *e)
{
    if (!e->live) return;
    if (e->cat == 0 && bullets_live) bullets_live--;
    if (n_live[e->pool]) n_live[e->pool]--;
    e->live = 0;
    cont = 0;
}

void enemies_clear(void)
{
    memset(en_small, 0, sizeof(en_small));
    memset(en_big, 0, sizeof(en_big));
    memset(en_item, 0, sizeof(en_item));
    bullets_live = 0;
    last_sx = level.scroll_x; last_sy = level.scroll_y;
    n_live[0] = n_live[1] = n_live[2] = 0;
    pending_letter = 0;
    fx_clear();
}

u8 enemy_bullets_live(void) { return bullets_live; }

/* ------------------------------------------------------------------------------------------ */
/* motion                                                                                      */

/* Load step idx ($2435 small / $27EE big): show steps set sprite, speed and duration; control
 * steps jump, remove the object, or run a behaviour function. */
static void step_to(Enemy *e, u16 idx)
{
    for (u16 guard = 0; guard < 32; guard++) {
        const MStep *s = &en_mot[idx];
        if (s->dur) {
            e->code = s->code; e->colour = s->colour;
            e->dy = s->dy; e->dx = s->dx;
            e->timer = s->dur;
            e->next = idx + 1;
            cont = 1;
            return;
        }
        if (MS_CTL(s) == MS_GOTO) { idx = MS_ARG(s); continue; }
        if (MS_CTL(s) == MS_KILL) { en_remove(e); return; }
        /* native: the arcade leaves the pointer on this step with the timer at 0 */
        e->next = idx + 1; e->timer = 0;
        native_step = idx;
        cont = 0;
        en_ai_table[MS_ARG(s)](e);
        return;
    }
    en_remove(e);
}

void en_set_motion(Enemy *e, u16 step) { step_to(e, step); }
void en_continue(Enemy *e) { (void)e; cont = 1; }

/* A native with no C implementation: keep the current motion and retry it later. */
void en_native_missing(Enemy *e)
{
    en_missing_count++;
    e->next = native_step;
    e->timer = 16;
    cont = 1;
}

/* Death ($25EF small / $2AAD big): no more collisions; run the death script or native. */
void en_die(Enemy *e)
{
    e->flags |= EF_SHOTPROOF | EF_NOCONTACT;
    if (e->flags & EF_NATIVEDEATH) {
        cont = 0;
        en_ai_table[e->death](e);
        return;
    }
    if (e->death == 0xFFFF) { en_remove(e); return; }
    e->next = e->death;
    e->timer = 1;
}

static void award(Enemy *e, Player *p)
{
    u32 pts = en_score_points[e->r[R_SCORE] >> 3];          /* $2272, table $2337 */
    if (pts && p) player_add_score(p, pts);
}

/* Destroyed by a player ($2A17 big: sound $11 + item drop; $25E3 small: sound $12). */
void en_kill_by(Enemy *e, Player *p)
{
    if (e->pool == EP_BIG) {
        sound_play(0x11);
        award(e, p);
        if (e->r[R_LETTER]) en_drop_letter(e);
    } else {
        sound_play(0x12);
        award(e, p);
    }
    en_die(e);
}

/* $07C0 (small: probe x+8, y+8) / $082F (big: probe x, y+16) in arcade sprite coordinates, plus
 * the 16-px column offset of the terrain map (levels.md 4). The y offset is an 8-bit add, so a
 * probe below the bottom edge wraps to the top of the screen. World wraps at 4096. */
static inline bool in_terrain(Enemy *e, bool big)
{
    s16 wx = level.scroll_x + AX(e) + (big ? 16 : 24);
    s16 wy = level.scroll_y + (u8)(AY(e) + (big ? 16 : 8));
    return terrain_solid(wx & 0xFFF, wy & 0xFFF);
}

bool en_terrain(Enemy *e) { return in_terrain(e, e->pool == EP_BIG); }

/* $2487-$24D6 small / $2856-$28F4 big: move, remove when off the arcade screen */
static inline __attribute__((always_inline)) bool move(Enemy *e, const bool big)
{
    u8 ry = (u8)(e->y + e->dy + 16);
    if (big ? (ry >= 0xF1 && ry < 0xF8) : ry >= 0xF1) { en_remove(e); return FALSE; }
    e->y = en_y_from_arcade(ry);
    e->x += e->dx;
    s16 ax = e->x + 96;
    if (ax < (big ? 0x20 : 0x30) || ax >= 0x1C0) { en_remove(e); return FALSE; }
    return TRUE;
}

/* ------------------------------------------------------------------------------------------ */
/* collisions (docs/re/objects.md 7): centre-to-centre boxes in arcade (y, x/2) units          */

static inline u16 absdiff(s16 a, s16 b) { return a > b ? a - b : b - a; }

/* Flying player shots this frame (P1's first) and the players' contact points, collected once
 * per frame instead of per object. */
typedef struct { Shot *s; s16 cx, cy; s16 hw, hh; } LiveShot;
static LiveShot live_shots[2 * MAX_SHOTS];
static u16 n_live_shots, live_p2;
static s16 shots_x0, shots_x1, shots_y0, shots_y1; /* box around every live shot (with its size) */
static u8 pl_alive[2], pl_y[2], pl_x2[2];          /* arcade y and x/2 of each player (+$02, +$17) */

static void collect_shots(void)
{
    LiveShot *l = live_shots;
    u16 n = 0;                                      /* counters, not pointer differences: */
    shots_x0 = shots_y0 = 0x7FFF;                   /* those cost a 32-bit multiply here */
    shots_x1 = shots_y1 = -0x7FFF;
    for (u16 pi = 0; pi < 2; pi++) {
        Player *p = &players[pi];
        if (pi) live_p2 = n;
        pl_alive[pi] = p->state == PL_ALIVE;
        pl_y[pi] = (u8)(p->y + 16);
        pl_x2[pi] = (u8)((u16)(p->x + 96) >> 1);
        /* no player-state test: $222C clears a dead player's shots, and the combined robot's ring
         * flies in the slots of a partner that is hidden (PL_OFF) or out of lives ($2525: shot
         * state only) */
        Shot *s = p->shots;
        for (u16 k = 0; k < MAX_SHOTS; k++, s++) {
            if (s->active != 1) continue;
            s16 cx = s->x + 8, cy = s->y + 8, hw = s->half_w, hh = s->half_h;
            l->s = s; l->cx = cx; l->cy = cy; l->hw = hw; l->hh = hh;
            if (cx - hw < shots_x0) shots_x0 = cx - hw;
            if (cx + hw > shots_x1) shots_x1 = cx + hw;
            if (cy - hh < shots_y0) shots_y0 = cy - hh;
            if (cy + hh > shots_y1) shots_y1 = cy + hh;
            l++; n++;
        }
    }
    n_live_shots = n;
}

static inline __attribute__((always_inline)) void collide(Enemy *e, const bool big)
{
    /* $2500: small objects test on even frames, $291E: big ones on odd frames (every frame
     * while the combined robot is out, $E014) */
    if ((frame & 1) != (big ? 1 : 0) && !(big && combined)) return;
    e->r[R_X2] = AX2(e);                                /* $2505 / $2929: +$17 = x/2 */
    if (!(e->flags & EF_SHOTPROOF) && n_live_shots) {
        /* $2525/$29C7: every flying shot of P1 then P2; each overlapping shot costs 1 HP.
         * Centre to centre in screen px (the object's centre is x+8 / x+16). */
        s16 cx = e->x + (big ? 16 : 8), cy = e->y + (big ? 16 : 8);
        s16 bh = e->box[0], bw = 2 * e->box[1];
        /* quick reject against the box around all shots */
        if (cy + bh <= shots_y0 || cy - bh >= shots_y1 || cx + bw <= shots_x0 || cx - bw >= shots_x1)
            goto contact;
        LiveShot *l = live_shots;
        for (u16 k = 0; k < n_live_shots; k++, l++) {
            if (absdiff(cy, l->cy) >= (u16)(bh + l->hh)) continue;
            if (absdiff(cx, l->cx) >= (u16)(bw + l->hw)) continue;
            if (l->s->active != 1) continue;            /* exploded earlier this frame */
            Player *p = &players[k >= live_p2 ? 1 : 0];
            shot_hit(p, l->s);
            if (--e->hp) continue;
            if (big || !e->item) en_kill_by(e, player_credit(p));
            else en_die(e);                             /* $25DD: pickups/bonuses die without score */
            return;
        }
    }
contact:
    if (e->flags & EF_NOCONTACT) return;
    /* $2617 small: |(py+8) - oy| < E, |(px/2+4) - ox/2| < F;  $2AD5 big: |py-oy|, |px2-ox2| */
    u8 oy = AY(e), ox2 = X2(e);
    for (u16 pi = 0; pi < 2; pi++) {
        if (!pl_alive[pi]) continue;
        u8 py = pl_y[pi], px2 = pl_x2[pi];
        if (!big) { py += 8; px2 += 4; }
        if (absdiff(py, oy) >= e->box[2]) continue;
        if (absdiff(px2, ox2) >= e->box[3]) continue;
        Player *p = &players[pi];
        if (p->state != PL_ALIVE) continue;             /* killed earlier this frame */
        if (!big && e->item) { en_pickup(e, p); return; }
        if (p->invuln) continue;
        player_kill(p);
        en_kill_by(e, p);
        return;
    }
}

/* ------------------------------------------------------------------------------------------ */
/* per-object update ($23CB small / $2784 big)                                                 */

static inline __attribute__((always_inline)) void update(Enemy *e, const bool big)
{
    if (e->flags & EF_KILLREQ) { en_die(e); return; }
    if (e->flags & EF_BGLOCK) { e->x -= en_scroll_dx; e->y -= en_scroll_dy; }
    s16 sx = e->x, sy = e->y;
    u8 scol = e->colour;
    u16 scode = e->code;
    if (--e->timer == 0) {
        step_to(e, e->next);
        if (!e->live || !cont) return;
    }
    for (u16 pass = 0; ; pass++) {
        if (!move(e, big)) return;
        if (big) { e->sub_x = AX(e) + 16; e->sub_y = AY(e); }      /* $285F-$28F4 */
        if ((e->flags & EF_NOTERRAIN) || pass >= 2 || !in_terrain(e, big)) break;
        /* $2905/$24E7: back to the saved position, then the family's terrain handler */
        e->x = sx; e->y = sy; e->colour = scol; e->code = (e->code & 0xFF) | (scode & 0x700);
        if (!e->wall) break;
        cont = 0;
        en_ai_table[e->wall](e);
        if (!e->live || !cont) return;
    }
    collide(e, big);
}

/* ------------------------------------------------------------------------------------------ */
/* aiming                                                                                      */

/* $0715: direction 0..31 from (ay, ax2) to (ty, tx2) in (y, x/2) space: octant + 5-sector
 * ratio test, table $0780 */
u8 en_aim_at(u8 ay, u8 ax2, u8 ty, u8 tx2)
{
    u8 c = 0, e, d;
    if (ty >= ay) e = ty - ay; else { e = ay - ty; c = 4; }
    if (tx2 >= ax2) d = tx2 - ax2; else { d = ax2 - tx2; c += 2; }
    if (d < e) {
        u8 t = d; d = e; e = t;
        if (c == 0 || c == 4) c++;
    } else if (c == 2 || c == 6) c++;
    u8 b = (d >> 3) & 0x1F, a = b, l = 0;
    if (a < e) { l = 1; a += 2 * b;
        if (a < e) { l = 2; a += 2 * b;
            if (a < e) { l = 3; a += 2 * b;
                if (a < e) l = 4; } } }
    return en_aim_table[(c << 3) | l];
}

u8 en_aim(Enemy *e)
{
    u8 d = en_aim_at(AY(e), X2(e), en_target_y, en_target_x2);
    e->r[R_AIM] = d;
    return d;
}

u8 enemy_aim(s16 x, s16 y)
{
    return en_aim_at((u8)(y + 16), (u8)((x + 96) >> 1), en_target_y, en_target_x2);
}

static u8 weapon_weight(const Player *p)
{
    /* B2:$8195: BIT 1, S.G. 1, M.B.L. 2, 3WAY 2, AUTO 4 */
    return (p->level[1] ? 1 : 0) + (p->level[2] ? 1 : 0) + (p->level[3] ? 2 : 0) +
           (p->level[4] ? 2 : 0) + (p->level[5] ? 4 : 0);
}

/* B2:$813A: every 8 frames pick the player the enemies aim at */
static void choose_target(void)
{
    if (++en_target_tick & 7) return;
    Player *a = &players[0], *b = &players[1], *t;
    bool ina = a->state != PL_OFF, inb = b->state != PL_OFF;
    if (!ina && !inb) { en_target_y = 0x78; en_target_x2 = 0xE0; return; }
    if (!inb) t = a;
    else if (!ina) t = b;
    else {
        bool vertical = level.dir_y && level.mode == SCROLL_RUN;      /* $E088 != 0 */
        u8 va, vb, lim;
        if (vertical) { va = (u8)(a->y + 16); vb = (u8)(b->y + 16); lim = 0x80; }
        else { va = (u8)((a->x + 96) >> 1); vb = (u8)((b->x + 96) >> 1); lim = 0x60; }
        if (vb >= va) t = vb >= lim ? b : NULL;
        else t = va >= lim ? a : NULL;
        if (!t) t = weapon_weight(a) >= weapon_weight(b) ? a : b;
    }
    en_target_y = (u8)(t->y + 16);
    en_target_x2 = (u8)((t->x + 96) >> 1);
}

/* ------------------------------------------------------------------------------------------ */
/* enemy bullets ($05AA cap, $0531, template $4000, direction tables $4022-$40EE)              */

/* $05AA: live enemy bullets < $E017 = max(0, script rank + difficulty offset $8049) */
s8 game_rank_offset(void) __attribute__((weak));
bool en_bullet_room(void)
{
    s16 cap = level.rank + (game_rank_offset ? game_rank_offset() : 0);
    return bullets_live < cap;
}

Enemy *en_bullet_at(u8 ay, s16 ax, u8 dir)
{
    if (!en_bullet_room()) return NULL;
    Enemy *b = en_alloc(EP_SMALL);
    if (!b) return NULL;
    en_init(b, TPL_4000);
    SET_AY(b, ay);
    SET_AX(b, ax);
    u8 lv = en_speed < 3 ? 3 : en_speed > 6 ? 6 : en_speed;
    b->next = en_bullet_dirs[lv - 3][dir & 31];
    b->timer = 1;
    return b;
}

Enemy *en_fire_aimed(Enemy *e)
{
    u8 d = en_aim(e);
    return en_bullet_at((u8)(AY(e) + 8), AX(e), d);
}

bool enemy_bullet_spawn(s16 x, s16 y, u8 dir)
{
    return en_bullet_at((u8)(y + 16), x + 96, dir) != NULL;
}

/* ------------------------------------------------------------------------------------------ */
/* spawning (script records -> objects, docs/re/objects.md 3)                                  */

static Enemy *place(Enemy *e, u16 ref)
{
    en_init(e, ref & SO_INDEX);
    if (ref & SO_SETS_P) pending_letter = 'P';                  /* $A91B */
    if ((ref & SO_TAKES_LETTER) && pending_letter) {            /* $08D2 */
        e->r[R_LETTER] = pending_letter;
        pending_letter = 0;
    }
    return e;
}

volatile u16 en_dbg_spawn;     /* test hook: (section << 10) | (index + 1) spawns that event */
volatile u8 en_dbg_mute;       /* test hook: ignore the level's spawn events */

static void spawn_event(u16 section, u16 index);

void enemy_spawn_event(u16 section, u16 index)
{
    if (!en_dbg_mute) spawn_event(section, index);
}

static void spawn_event(u16 section, u16 index)
{
    if (section >= 10 || index >= en_spawn_sections[section].n) return;
    const SpawnEvent *ev = &en_spawn_sections[section].ev[index];
    const u16 *obj = &en_spawn_objs[ev->first];
    switch (ev->kind) {
    case SPK_LETTER:                                            /* $82CC-$830E */
        pending_letter = (u8)ev->arg;
        break;
    case SPK_SEQ:
        /* one allocation per object; the routine returns at the first failure ($0384) */
        for (u16 i = 0; i < ev->count; i++) {
            Enemy *e = en_alloc(enemy_inits[obj[i] & SO_INDEX].pool);
            if (!e) { enemy_dropped += ev->count - i; return; }
            place(e, obj[i]);
        }
        break;
    case SPK_GROUP: {                                           /* $057A bombs, $5575 snakes */
        Enemy *e = en_alloc_small_group(ev->count, (u8)ev->arg);
        if (!e) { enemy_dropped += ev->count; return; }
        for (u16 i = 0; i < ev->count; i++) place(e + i, obj[i]);
        break;
    }
    case SPK_EYE: {                                             /* $B65D: slots $F780-$F980 */
        for (u16 i = 3; i < 8; i++)
            if (en_big[i].live) { enemy_dropped += 5; return; }
        en_rng += 0x4D;                                         /* $B6DB */
        const u8 *f = en_eye_formations[ev->arg][(en_rng & 0x0E) >> 1];
        for (u16 i = 0; i < 5; i++) {
            Enemy *e = place(&en_big[3 + i], obj[i]);
            u8 xb = f[2 * i + 1];
            SET_AY(e, f[2 * i]);
            SET_AX(e, ((xb & 0x80) << 1) | (u8)((xb << 1) | (xb >> 7)));   /* RLCA, carry = x bit 8 */
        }
        break;
    }
    case SPK_BARRIER: {                                         /* $BD66: two shutters, start phase */
        Enemy *a = en_alloc(EP_BIG);                            /* picked by $E008 & 6 */
        if (!a) { enemy_dropped += 2; return; }
        place(a, obj[0]);
        u8 k = (en_rng & 6) >> 1;
        a->next = MOTPTR_BDAD_4[k];
        Enemy *b = en_alloc(EP_BIG);
        if (!b) { enemy_dropped++; return; }
        place(b, obj[1]);
        b->next = MOTPTR_BDB5_4[k];
        break;
    }
    case SPK_ORB:                                               /* $B15D: only with $FF00-$FFE0 free */
        for (u16 i = 0; i < N_ITEM; i++)
            if (en_item[i].live) return;
        if (!en_spawn(EP_BIG, obj[0] & SO_INDEX)) enemy_dropped++;
        break;
    default:
        break;
    }
}

/* A raw arcade script record (the attract demo, flow_attract.c). CALL records ($FE) of a spawn
 * routine create the same objects as a stage spawn event calling that routine. Template SPAWN
 * records ($2080) put the template into a $FF00 slot at y = cmd while the camera scrolls
 * horizontally, else at y $F0 and x = (cmd & $FE) * 2 (bit 7 -> x bit 8). */
void enemy_spawn_record(u8 cmd, u16 target)
{
    if (cmd == 0xFE) {
        /* CALL of a spawn routine: same objects as a stage event that calls it */
        u16 lo = 0, hi = en_routine_count;
        while (lo < hi) {
            u16 mid = (lo + hi) >> 1;
            if (en_routines[mid].addr < target) lo = mid + 1; else hi = mid;
        }
        if (lo < en_routine_count && en_routines[lo].addr == target)
            spawn_event(en_routines[lo].section, en_routines[lo].index);
        return;
    }
    if (cmd >= 0xFB) return;
    u16 lo = 0, hi = en_template_count;
    while (lo < hi) {
        u16 mid = (lo + hi) >> 1;
        if (en_templates[mid].addr < target) lo = mid + 1; else hi = mid;
    }
    if (lo >= en_template_count || en_templates[lo].addr != target) return;
    Enemy *e = en_spawn(EP_ITEM, en_templates[lo].init);
    if (!e) { enemy_dropped++; return; }
    if (level.dir_x && level.mode == SCROLL_RUN) SET_AY(e, cmd);
    else {
        u8 c = cmd & 0xFE;
        SET_AY(e, 0xF0);
        s16 x = (u8)((c << 1) | (c >> 7));
        if ((cmd & 0x80) && AX(e) >= 0x100) x |= 0x100;
        SET_AX(e, x);
    }
}

/* ------------------------------------------------------------------------------------------ */
/* frame                                                                                       */


static void update_all(void);

void enemies_update(void)
{
    if (players_world_frozen()) return;     /* combined-robot merge: every other task waits ($3078) */
    u16 l0 = GET_VCOUNTER;
    en_prof_nobj = n_live[0] + n_live[1] + n_live[2];
    update_all();
    en_prof_update = (GET_VCOUNTER - l0) & 0xFF;
}

static void update_all(void)
{
    if (en_dbg_spawn) { u16 r = en_dbg_spawn; en_dbg_spawn = 0; spawn_event(r >> 10, (r & 0x3FF) - 1); }
    /* $23D3/$278C: BG-locked objects move against this frame's scroll step ($E088/$E089). That
     * is the camera's movement, except on a teleport frame, where it is the step taken before
     * the jump (the direction in force at the end of the last frame). */
    {
        s16 dx = (level.scroll_x - last_sx) & 0xFFF, dy = (level.scroll_y - last_sy) & 0xFFF;
        if (dx >= 0x800) dx -= 0x1000;
        if (dy >= 0x800) dy -= 0x1000;
        bool jump = dx < -1 || dx > 1 || dy < -1 || dy > 1;
        if (jump) {
            en_scroll_dx = (frame & 1) ? last_dir_x : 0;
            en_scroll_dy = (frame & 1) ? last_dir_y : 0;
        } else { en_scroll_dx = dx; en_scroll_dy = dy; }
        last_sx = level.scroll_x; last_sy = level.scroll_y;
        last_dir_x = level.dir_x; last_dir_y = level.dir_y;
    }
    choose_target();
    collect_shots();
    /* $21B2: small objects, big objects, (boss), pickups */
    Enemy *e;
    if (n_live[EP_SMALL]) for (e = en_small; e < en_small + N_SMALL; e++) if (e->live) update(e, FALSE);
    if (n_live[EP_BIG]) for (e = en_big; e < en_big + N_BIG; e++) if (e->live) update(e, TRUE);
    if (n_live[EP_ITEM]) for (e = en_item; e < en_item + N_ITEM; e++) if (e->live) update(e, FALSE);
    fx_update();
    /* the credit task (slot 6) runs after the main loop's object update in each frame */
    if (++en_rng_div >= 3) {
        /* $08E3: $E008 += 1, then each next byte += the previous one + an odd constant (the
         * running sum starts at 1, as observed in MAME) */
        static const u8 ADD[7] = { 0x03, 0x05, 0x07, 0x0B, 0x0D, 0x11, 0x13 };
        en_rng_div = 0;
        en_rng++;
        u8 a = 1;
        for (u16 k = 0; k < 7; k++) { a += en_rnd[k] + ADD[k]; en_rnd[k] = a; }
    }
}

/* ------------------------------------------------------------------------------------------ */
/* drawing                                                                                     */

/* Arcade draw order (MAME): F000-F6FF on top, then F800-FEFF, FE00-FFFF, F700-F7FF at the
 * bottom (objects.md 8): small objects, big slots 0-1, big 4-8, pickups, big 2-3.
 * The Genesis shows at most 20 sprites / 320 px per line; when a 16-px band of the screen
 * would exceed that, the order inside each group rotates every frame so the VDP drops a
 * different object each frame (flicker) instead of the same one for good. */
/* Cheap per-band estimate: 16-px units of sprite width in each 32-line band of the screen
 * (an object counts in the bands its top and bottom lines fall in). */
static bool overloaded(void)
{
    if (n_live[EP_SMALL] + n_live[EP_ITEM] + 2 * n_live[EP_BIG] <= 18) return FALSE;
    u8 band[10];
    memset(band, 0, sizeof(band));
    for (u16 i = 0; i < 2; i++) {
        if (players[i].state == PL_OFF) continue;
        u16 b = (u16)(players[i].y + 32) >> 5;
        if (b < 9) { band[b] += 2; band[b + 1] += 2; }
    }
    Enemy *e = en_big;
    for (u16 i = 0; i < N_BIG; i++, e++) {
        if (!e->live || !e->code) continue;
        u16 b = (u16)(e->y + 32) >> 5;
        if (b < 9) { band[b] += 2; band[b + 1] += 2; }
    }
    e = en_small;
    for (u16 i = 0; i < N_SMALL + N_ITEM; i++, e++) {
        if (i == N_SMALL) e = en_item;
        if (!e->live || !e->code) continue;
        u16 t = (u16)(e->y + 32) >> 5, b = (u16)(e->y + 47) >> 5;
        if (t < 10) band[t]++;
        if (b != t && b < 10) band[b]++;
    }
    for (u16 i = 0; i < 10; i++) if (band[i] > 20) return TRUE;
    return FALSE;
}

/* rot < n: start index of the rotation (no division: 68000 has no 32-bit divide) */
static void draw_small(Enemy *base, u16 n, u16 rot)
{
    Enemy *e = base + rot, *end = base + n;
    for (u16 k = 0; k < n; k++, e++) {
        if (e == end) e = base;
        if (e->live && e->code) spr_16(e->code, e->colour, e->x, e->y, 0);
    }
}

static void draw_big(u16 i)
{
    Enemy *e = &en_big[i];
    if (e->live && e->code) spr_32(e->code, e->colour, e->x, e->y, 0);
}

static const u8 BIG_ORDER[N_BIG] = { 0, 1, 4, 5, 6, 7, 8, 2, 3 };

void enemies_draw(void)
{
    if (en_dbg_nodraw) return;
    u16 l0 = GET_VCOUNTER;
    u16 rot = overloaded() ? frame : 0;
    draw_small(en_small, N_SMALL, rot & 15);
    fx_draw();
    u16 r7 = rot & 7;
    if (r7 == 7) r7 = 0;
    for (u16 k = 0; k < 7; k++) {
        draw_big(BIG_ORDER[r7]);
        if (++r7 == 7) r7 = 0;
    }
    draw_small(en_item, N_ITEM, rot & 7);
    draw_big(2); draw_big(3);
    en_prof_draw = (GET_VCOUNTER - l0) & 0xFF;
}
