#include "bc_continue.h"

void bc_continue_begin(BcContinue *p, unsigned char available)
{
    *p = (BcContinue){9, 90, available ? BC_CONT_WAITING : BC_CONT_EXPIRED};
}

unsigned char bc_continue_tick(BcContinue *p, unsigned char start)
{
    if (p->state != BC_CONT_WAITING) return p->state;
    if (start) p->state = BC_CONT_ACCEPTED;
    else if (!--p->remaining) {
        if (!p->digit) p->state = BC_CONT_EXPIRED;
        else { p->digit--; p->remaining = 90; }
    }
    return p->state;
}
