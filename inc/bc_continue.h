#pragma once

typedef struct {
    unsigned char digit, remaining, state;
} BcContinue;
enum { BC_CONT_WAITING = 1, BC_CONT_ACCEPTED, BC_CONT_EXPIRED };
/* $6488-$64C3: ten digits, ninety updates each. Start is checked before
 * decrementing the last update, so it wins at the timeout boundary. */
void bc_continue_begin(BcContinue *prompt, unsigned char available);
unsigned char bc_continue_tick(BcContinue *prompt, unsigned char start);
