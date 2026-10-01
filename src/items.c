#include "enemy_int.h"

/* Pickups, the POW capsule cycle and the hidden bonuses (docs/re/objects.md 4). */

/* $2A23: carried letter -> pickup, in this order */
static const char LETTERS[12] = { 'P', 't', 'b', 'm', '3', 'y', 's', 'A', 'C', 'T', 'I', 'M' };

/* A destroyed carrier leaves its pickup at its centre ($2A81-$2AAA: y+8, x+8, pool $FF00). */
void en_drop_letter(Enemy *e)
{
    for (u16 i = 0; i < 12; i++) {
        if (LETTERS[i] != e->r[R_LETTER]) continue;
        Enemy *p = en_alloc(EP_ITEM);
        if (!p) return;
        en_init(p, en_letter_inits[i]);
        p->x = e->x + 8;
        p->y = e->y + 8;
        return;
    }
}

/* POW capsule ($4DCF) at Genesis screen (x, y), top-left: the bosses' death drops
 * ($6BBA-$6C11 / $754F-$75A3, boss module). Dropped when the 8 pickup slots are full. */
void item_spawn_pow(s16 x, s16 y)
{
    Enemy *p = en_alloc(EP_ITEM);
    if (!p) return;
    en_init(p, en_letter_inits[0]);
    p->x = x;
    p->y = y;
}

/* $2657: a player touched a pickup. The effect itself (and its sound $1A/$1B/$1C/$1D) belongs
 * to the player module; then the pickup vanishes through $25E3 (sound $12, its score). The
 * alpha capsule (item 6) vanishes at once and starts the combined robot ($2735). */
void en_pickup(Enemy *e, Player *p)
{
    u8 item = e->item;
    if (item == 0x06) {
        en_remove(e);
        player_apply_item(p, item);
        return;
    }
    player_apply_item(p, item);
    sound_play(0x12);
    {
        u32 pts = en_score_points[e->r[R_SCORE] >> 3];
        if (pts) player_add_score(p, pts);
    }
    en_remove(e);
}

/* POW capsule ($4DCF): every time it is shot empty it turns into the next form of the chain
 * (handlers $4E01, $4E54, ... $50D8; table en_pow_chain from the ROM). r[9] = forms done. */
/* @native 4E01 */
void pow_turn(Enemy *e)
{
    u8 f = e->r[9] < POW_FORMS ? e->r[9] : POW_FORMS - 1;
    e->flags |= EF_SHOTPROOF | EF_NOCONTACT;            /* intangible while turning */
    en_set_motion(e, en_pow_chain[f].trans);
}

/* end of a turn animation: the new form ($4E1C ...) */
void pow_settle(Enemy *e)
{
    u8 f = e->r[9] < POW_FORMS ? e->r[9] : POW_FORMS - 1;
    const PowForm *pf = &en_pow_chain[f];
    if (pf->idle != 0xFFFF) {
        e->item = pf->item;
        e->hp = pf->hp;
        e->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT);
        e->r[9] = f + 1;
        en_set_motion(e, pf->idle);
        return;
    }
    /* $50F3: last form, AUTO type picked at random, no longer shootable */
    e->flags = (e->flags | EF_SHOTPROOF) & ~EF_NOCONTACT;   /* OR 3, XOR 2 */
    en_rng += 0x6F;
    if (en_rng & 0x80) { e->item = 0x11; en_set_motion(e, MOT_5129); }
    else { e->item = 0x10; en_set_motion(e, MOT_511C); }
}

/* Pickups vanish through death script $513C; their native death $5136 does the same. */
/* @native 5136 */
void pickup_vanish(Enemy *e)
{
    en_remove(e);
}

/* Hidden bonuses ($52FF ... $5421): invisible, BG-locked, shootable. Shot empty they reveal
 * their pickup in place. */
/* @native 5327 */
void hidden_alpha_reveal(Enemy *e)
{
    e->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT);
    en_set_motion(e, MOT_5293);                          /* alpha capsule $112-$117 */
}

static void reveal(Enemy *e, u16 anim)
{
    e->flags &= ~(EF_SHOTPROOF | EF_NOCONTACT | EF_NATIVEDEATH);
    e->death = MOT_513C;
    en_set_motion(e, anim);
}

/* @native 535F */
void hidden_cow_reveal(Enemy *e) { reveal(e, MOT_5378); }      /* cow $134, 10000 */
/* @native 53AD */
void hidden_barrel_reveal(Enemy *e) { reveal(e, MOT_53C6); }   /* barrel $135, 3000 */
/* @native 53FB */
void hidden_fruit_reveal(Enemy *e) { reveal(e, MOT_5414); }    /* fruit $136, 3000 */
/* @native 5449 */
void hidden_1up_reveal(Enemy *e) { reveal(e, MOT_5462); }      /* 1UP $137 */
