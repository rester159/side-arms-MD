#include "bc_score.h"
#include "bc_rules.h"

/* $6DA6: the source shifts its command three times in an eight-bit register.
 * IDs 26..31 consequently read the first six following threshold records. */
static const unsigned char points[32][7] = {
    {0,0,0,0,0,0,0}, {0,0,0,0,0,5,0}, {0,0,0,0,1,0,0}, {0,0,0,0,2,0,0},
    {0,0,0,0,3,0,0}, {0,0,0,0,4,0,0}, {0,0,0,0,5,0,0}, {0,0,0,0,8,0,0},
    {0,0,0,1,0,0,0}, {0,0,0,1,6,0,0}, {0,0,0,3,0,0,0}, {0,0,0,3,2,0,0},
    {0,0,0,5,0,0,0}, {0,0,0,8,0,0,0}, {0,0,1,0,0,0,0}, {0,0,1,5,0,0,0},
    {0,0,2,0,0,0,0}, {0,0,3,0,0,0,0}, {0,0,5,0,0,0,0}, {0,0,8,0,0,0,0},
    {0,1,0,0,0,0,0}, {0,1,5,0,0,0,0}, {0,2,0,0,0,0,0}, {0,3,0,0,0,0,0},
    {0,5,0,0,0,0,0}, {1,0,0,0,0,0,0}, {0,0,5,0,0,0,0}, {0,1,0,0,0,0,0},
    {0,2,0,0,0,0,0}, {0,4,0,0,0,0,0}, {0,8,0,0,0,0,0}, {1,2,0,0,0,0,0}
};
static const unsigned char thresholds[10][8] = {
    {0,0,0,5,0,0,0,0}, {0,0,1,0,0,0,0,0}, {0,0,2,0,0,0,0,0}, {0,0,4,0,0,0,0,0},
    {0,0,8,0,0,0,0,0}, {0,1,2,0,0,0,0,0}, {0,1,6,0,0,0,0,0}, {0,2,0,0,0,0,0,0},
    {0,4,0,0,0,0,0,0}, {9,9,9,9,9,9,9,9}
};

void bc_score_enqueue(BcScore *s, unsigned char command, unsigned char playing)
{
    if (!playing) return;
    s->queue[s->write] = command;
    s->write = (s->write + 1) & 15;
}

static signed char compare(const unsigned char *left, const unsigned char *right)
{
    for (unsigned char i = 0; i < 8; i++) {
        if (left[i] != right[i]) return left[i] < right[i] ? -1 : 1;
    }
    return 0;
}

/* Scores have byte alignment, including odd-addressed party entries. MOVEP
 * compares the two interleaved halves without aligned longword loads. Equal
 * score/high records are the common case between scoring events. */
static unsigned char same_score(const BcScore *s)
{
#if defined(__m68k__)
    _Static_assert(__builtin_offsetof(BcScore, high) == 8 && sizeof(s->digits) == 8,
        "MOVEP score equality requires adjacent eight-byte records");
    unsigned long even, odd, other;
    __asm__ ("movep.l 0(%3),%0\n\t"
             "movep.l 8(%3),%2\n\t"
             "eor.l %2,%0\n\t"
             "movep.l 1(%3),%1\n\t"
             "movep.l 9(%3),%2\n\t"
             "eor.l %2,%1\n\t"
             "or.l %1,%0"
        : "=&d"(even), "=&d"(odd), "=&d"(other)
        : "a"(s), "m"(*s) : "cc");
    return even == 0;
#else
    for (unsigned char i = 0; i < 8; i++)
        if (s->digits[i] != s->high[i]) return 0;
    return 1;
#endif
}

void bc_score_continue(BcScore *s)
{
    for (unsigned char i = 0; i < 8; i++) s->digits[i] = 0;
    s->next_life = 0;
}

/* $6CB3-$6D3B: seven decimal digits are added; the leading comparison byte
 * is preserved, and overflow from the most significant added digit is lost. */
BcScoreEvent bc_score_step_extends(BcScore *s, unsigned short *seed, unsigned char *lives,
    const unsigned char table[][8], unsigned char count)
{
    BcScoreEvent event = {0, 0, 0, 0, 0};
    if (seed) *seed = bc_random_next(*seed);
    unsigned char command = s->queue[s->read];
    if (command != 255) {
        s->queue[s->read] = 255; s->read = (s->read + 1) & 15;
        event.consumed = event.refresh_score = 1;
        unsigned char carry = 0;
        for (signed char i = 7; i > 0; i--) {
            unsigned char value = s->digits[(unsigned char)i] + points[command & 31][i - 1] + carry;
            carry = value >= 10;
            s->digits[(unsigned char)i] = value - carry * 10;
        }
        if (s->next_life < count && compare(s->digits, table[s->next_life]) >= 0) {
            s->next_life++; (*lives)++;
            event.life_awarded = 1; event.sound = 22;
        }
    }
    if (!same_score(s) && compare(s->digits, s->high) > 0) {
        for (unsigned char i = 0; i < 8; i++) s->high[i] = s->digits[i];
        event.refresh_high = 1;
    }
    return event;
}

BcScoreEvent bc_score_step(BcScore *s, unsigned short *seed, unsigned char *lives)
{
    return bc_score_step_extends(s, seed, lives, thresholds, 10);
}

unsigned short bc_score_completion_bonus(BcScore *s, unsigned char reserves,
    unsigned char unused_continues)
{
    if ((reserves & 128) || unused_continues > 5) return 0;
    unsigned short units = ((unsigned short)(reserves + 1) << unused_continues) % 1000;
    unsigned short remaining = units;
    unsigned char carry = 0;
    /* The ending touches only ten-thousands through millions. Carry out of
     * column one is discarded, as in the overlay's DEY/BNE loop. */
    for (signed char i = 3; i > 0; i--) {
        unsigned char value = s->digits[(unsigned char)i] + remaining % 10 + carry;
        remaining /= 10;
        carry = value >= 10;
        s->digits[(unsigned char)i] = value - carry * 10;
    }
    return units;
}
