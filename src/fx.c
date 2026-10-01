#include "enemy_int.h"
#include "sprites.h"

/* Free-standing explosions (for bosses and anything that explodes without an enemy slot).
 * Enemies explode inside their own slot through their death script, as in the arcade, because
 * the slot stays busy (and blocks spawns) until the explosion ends. The animations are the
 * arcade's shared death scripts: $4D5E (2x2, colour 8), $4D87 (2x2, colour 7), $4DAB (1x1).
 *
 * The arcade has no score pop-ups for enemy kills (the score only changes in the HUD), so none
 * are drawn here. */

#define N_FX 8
typedef struct { s16 x, y; u16 step, code; u8 timer, colour, big, bg; } Fx;
static Fx fx[N_FX];
static u16 fx_live;         /* explosions running (skip the loops when none) */

void fx_clear(void) { memset(fx, 0, sizeof(fx)); fx_live = 0; }

static void load(Fx *f, u16 idx)
{
    for (u16 guard = 0; guard < 8; guard++) {
        const MStep *s = &en_mot[idx];
        if (s->dur) {
            f->code = s->code; f->colour = s->colour; f->timer = s->dur;
            f->step = idx + 1;
            return;
        }
        if (MS_CTL(s) != MS_GOTO) break;
        idx = MS_ARG(s);
    }
    f->timer = 0;               /* kill / anything else ends the effect */
}

void fx_explosion(s16 x, s16 y, u8 kind, bool bg_locked)
{
    for (u16 i = 0; i < N_FX; i++) {
        Fx *f = &fx[i];
        if (f->timer) continue;
        f->x = x; f->y = y;
        f->big = kind != FX_SMALL;
        f->bg = bg_locked;
        load(f, kind == FX_BIG ? MOT_4D5E : kind == FX_BIG7 ? MOT_4D87 : MOT_4DAB);
        if (f->timer) fx_live++;
        return;
    }
}

void fx_update(void)
{
    if (!fx_live) return;
    for (u16 i = 0; i < N_FX; i++) {
        Fx *f = &fx[i];
        if (!f->timer) continue;
        if (f->bg) { f->x -= en_scroll_dx; f->y -= en_scroll_dy; }
        if (--f->timer == 0) {
            load(f, f->step);
            if (!f->timer) fx_live--;
        }
    }
}

void fx_draw(void)
{
    if (!fx_live) return;
    for (u16 i = 0; i < N_FX; i++) {
        Fx *f = &fx[i];
        if (!f->timer) continue;
        if (f->big) spr_32(f->code, f->colour, f->x, f->y, 0);
        else spr_16(f->code, f->colour, f->x, f->y, 0);
    }
}
