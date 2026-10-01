#include "boss_int.h"
#include "hud.h"

/* Final boss $5FC3 (section 10): a chain of eight 2x2 segments (template $6372)
 * entering from the right edge 13 frames apart ($5FDD). Every segment steps
 * 14 frames along one of 16 headings, then decides ($60AB):
 *   head ($48)  steers one notch (heading +-2) towards the player while it is in
 *               the central box y $56-$91, x/2 $66-$87, else towards the screen
 *               centre ($78, $80); fires an 8-way burst from the $F000 half
 *               when that half is empty; 20 hits ($6023);
 *   body ($4D)  copies the heading of the segment ahead, HP refilled to 250;
 *   tail ($54)  same, and fires the other 8 directions from the $F100 half.
 * Killing the head ($602E) makes the next segment the head; it shows the hurt
 * colour for 8 steps and then gets 20 HP. When the head dies with the tail two
 * segments behind, the last three explode and the ending task $3B8A runs. */

enum { R_OFF, R_HEAD = 0x48, R_BODY = 0x4D, R_TAIL = 0x54, R_DYING = 1 };

typedef struct {
    u8 role;
    s16 y, x;
    s8 dy, dx;
    u8 t, i, n;
    const BossStep *st;
    u16 code; u8 colour;
    u8 heading, c12, hp, score_idx;
    bool immune, nocontact, started;
} Seg;

static struct {
    bool on;
    Seg seg[8];
} f;

static void seg_load(Seg *s) { const BossStep *st = &s->st[s->i]; s->t = st->frames; s->code = st->code; s->colour = st->colour; s->dy = st->dy; s->dx = st->dx; }
static void seg_run(Seg *s, const BossStep *st, u8 n) { s->st = st; s->n = n; s->i = 0; seg_load(s); }

static void seg_motion(Seg *s, u8 table)
{
    const u16 *m = &final_motion[(table * 16 + (s->heading >> 1)) * 2];   /* u16: 272 steps */
    seg_run(s, &final_steps[m[0]], m[1]);
}

/* $60D0 / $61A7: 8 bullets ($4000) from the segment, directions start, start+4, ...
 * taken from the stage's bullet table, only when the previous burst is gone */
static void burst(Seg *s, u8 bank, u8 first)
{
    if (pj_bank_live(bank)) return;
    for (u16 k = 0; k < 8; k++) pj_bullet(s->y, s->x, first + 4 * k, bank);
}

static void decide(u16 k)
{
    Seg *s = &f.seg[k];
    switch (s->role) {
    case R_BODY:
        s->hp = FINAL_HP;
        s->heading = f.seg[k - 1].heading;              /* (ix-$70): the segment ahead */
        seg_motion(s, 2);
        return;
    case R_TAIL:
        burst(s, 1, 2);
        s->hp = FINAL_HP;
        s->heading = f.seg[k - 1].heading;
        seg_motion(s, 3);
        return;
    case R_HEAD: {
        burst(s, 0, 0);
        if (s->c12 && !--s->c12) s->hp = FINAL_HEAD_HP;     /* $6276 */
        s16 ty, tx;
        boss_target(&ty, &tx);
        if (s->y < 0x56 || s->y >= 0x92 || (s->x >> 1) < 0x66 || (s->x >> 1) >= 0x88) { ty = 0x78; tx = 0x100; }
        u8 want = boss_aim_at(s->y, s->x, ty, tx) & 0x1E;
        if (s->heading != want) {
            if (((s->heading - want) & 0x1E) < 0x10) s->heading -= 2; else s->heading += 2;
            s->heading &= 0x1E;
        }
        seg_motion(s, s->c12 ? 1 : 0);                   /* hurt colour 8 ($62F2) / normal c3 ($6312) */
        return;
    }
    }
}

static const BossStep blank_step = { 11, 0, 0, 0, 0 };    /* $69A2/$69A7: 11 hidden frames */

/* death motions: the head explodes at once ($69AC), the next segment after one
 * blank step ($69A2 + 5), the tail after two ($699D + 5); 7 x 7-frame blasts */
static void explode(Seg *s, u8 blanks)
{
    s->role = R_DYING; s->immune = s->nocontact = TRUE;
    s->c12 = blanks;
    if (blanks) { s->c12--; seg_run(s, &blank_step, 1); }
    else seg_run(s, final_blast_steps, 7);
}

/* $602E: the head's death */
static void head_dead(u16 k)
{
    if (k + 2 < 8 && f.seg[k + 2].role == R_TAIL) {
        explode(&f.seg[k], 0);
        explode(&f.seg[k + 1], 1);                      /* $69A2 + 5: one blank step first */
        explode(&f.seg[k + 2], 2);                      /* $699D + 5: two blank steps */
        boss_defeated();
        ending_start();                                 /* task $3B8A */
        return;
    }
    explode(&f.seg[k], 0);                              /* $69AC */
    if (k + 1 < 8) { f.seg[k + 1].role = R_HEAD; f.seg[k + 1].c12 = 8; }
}

void fboss_reset(void) { memset(&f, 0, sizeof(f)); }

void fboss_start(void)
{
    fboss_reset();
    f.on = TRUE;
    boss_shift = 0;
    for (u16 k = 0; k < 8; k++) {
        Seg *s = &f.seg[k];
        s->role = k == 0 ? R_HEAD : k == 7 ? R_TAIL : R_BODY;   /* $6005-$6020 */
        s->y = 0x70; s->x = 0x1BF;
        s->t = final_start[k];
        s->heading = 0x10;
        s->hp = k == 0 ? FINAL_HEAD_HP : FINAL_HP;
        s->score_idx = k == 5 ? FINAL_LAST_SCORE_IDX : FINAL_SCORE_IDX;
    }
    boss_hud_set(FALSE, 0, 0);                          /* no bar display for the chain */
    bc_reserve(24);
    bs_reserve(1);                                      /* burst bullets */
}

bool fboss_update(void)
{
    if (!f.on) return FALSE;
    bool any = FALSE;
    for (u16 k = 0; k < 8; k++) {
        Seg *s = &f.seg[k];
        if (s->role == R_OFF) continue;
        any = TRUE;
        if (!--s->t) {
            if (!s->started) { s->started = TRUE; seg_run(s, final_entry_steps, 1); }
            else if (++s->i < s->n) seg_load(s);
            else if (s->role == R_DYING) {
                if (s->st != &blank_step) { s->role = R_OFF; continue; }
                if (s->c12) { s->c12--; seg_run(s, &blank_step, 1); }
                else seg_run(s, final_blast_steps, 7);
            }
            else decide(k);
        }
        s->y += s->dy; s->x += s->dx;
        if (!(frame & 1) || s->role == R_DYING || !s->started) continue;
        /* 2x2 tests on odd frames: shots $29C7 (P = (y+8, x+8), $0A / 5*2), contact $2AD5 */
        if (!s->immune) {
            Player *who = NULL;
            u8 n = boss_shots(s->y + 8, s->x + 8, 10, 10, &who);
            while (n-- && s->role != R_DYING) {
                if (--s->hp) continue;
                sound_play(SND_KILL_BIG);
                boss_score(who, s->score_idx);
                if (s->role == R_HEAD) head_dead(k);
            }
        }
        if (!s->nocontact) boss_touch(s->y, s->x, 10, 10, 0, 0);
    }
    if (!any) f.on = FALSE;
    return f.on;
}

void fboss_draw(void)
{
    if (!f.on) return;
    for (u16 k = 0; k < 8; k++) {
        Seg *s = &f.seg[k];
        if (s->role != R_OFF && s->code) bc_draw(s->code, s->colour, to_gx(s->x), to_gy(s->y));
    }
}

/* ======================================================================= ending */

/* Task $3B8A: 120 frames, sound $2C, "CONGRATURATIONS ... THE END" for 26 s,
 * clear, 1 s, staff roll ($3BF9) for 9 s, clear, 1 s, then $0B84 restarts the
 * title cycle - the game does not loop back to stage 1. Text: the HUD's
 * window plane (arcade text column c -> HUD column c - 12, row r -> r - 2). */
#pragma weak hud_text
static struct { bool on, done; u16 t; u8 phase; } end;

void ending_reset(void) { memset(&end, 0, sizeof(end)); }
bool boss_ending_active(void) { return end.on; }
bool boss_game_cleared(void) { return end.done; }

static void text_block(const char *const *lines, u16 n, u8 col, u8 row, u8 colour, bool show)
{
    static const char blank[] = "                                        ";   /* 40 */
    if (!hud_text) return;
    for (u16 i = 0; i < n; i++) {
        u16 len = strlen(lines[i]);
        if (!len) continue;
        hud_text(col - 12, row - 2 + i, colour, show ? lines[i] : blank + 40 - len);
    }
}

void ending_start(void)
{
    end.on = TRUE; end.done = FALSE; end.phase = 0; end.t = 120;   /* $0224 */
}

static void ending_update(void)
{
    if (!end.on || --end.t) return;
    switch (end.phase++) {
    case 0:
        sound_play(SND_ENDING);
        text_block(ending_congrats, ENDING_CONGRATS_LINES, ENDING_CONGRATS_COL, ENDING_CONGRATS_ROW, 2, TRUE);
        end.t = 0x1A * 60;                              /* $0241 x $1A */
        break;
    case 1:
        text_block(ending_congrats, ENDING_CONGRATS_LINES, ENDING_CONGRATS_COL, ENDING_CONGRATS_ROW, 2, FALSE);
        end.t = 60;
        break;
    case 2:
        text_block(ending_staff, ENDING_STAFF_LINES, ENDING_STAFF_COL, ENDING_STAFF_ROW, 0, TRUE);
        end.t = 9 * 60;
        break;
    case 3:
        text_block(ending_staff, ENDING_STAFF_LINES, ENDING_STAFF_COL, ENDING_STAFF_ROW, 0, FALSE);
        end.t = 60;
        break;
    default:
        end.on = FALSE; end.done = TRUE;                /* $0B84: back to the title cycle */
        break;
    }
}

/* the ending outlives the boss object: driven from here every frame */
void boss_ending_tick(void) { ending_update(); }
