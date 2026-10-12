#include "bc_hud.h"
#include "hud.h"

static u8 last_score[8], last_high[8], last_lives;
static u8 life_offset;
void bc_hud_show_total_lives(unsigned char enabled) { life_offset = enabled != 0; }

/* Score records have byte alignment. MOVEP reads alternating bytes safely
 * even from odd addresses; the two lanes cover exactly the eight digits. */
static inline u8 digits_equal(const u8 *a, const u8 *b)
{
#if defined(__m68k__)
    unsigned int result, other;
    __asm__("movep.l 0(%2),%0\n\t"
            "movep.l 0(%3),%1\n\t"
            "cmp.l %1,%0\n\t"
            "bne.s 1f\n\t"
            "movep.l 1(%2),%0\n\t"
            "movep.l 1(%3),%1\n\t"
            "cmp.l %1,%0\n"
            "1:\tseq %0"
        : "=&d"(result), "=&d"(other)
        : "a"(a), "a"(b), "m"(*(const u8 (*)[8])a), "m"(*(const u8 (*)[8])b)
        : "cc");
    return (u8)result;
#else
    return !memcmp(a, b, 8);
#endif
}

static void score_digits(s16 col, const u8 digits[8], u8 previous[8])
{
    if (digits_equal(digits, previous)) return;
    u16 codes[8];
    u16 first = 0;
    while (first < 7 && !digits[first]) first++;
    for (u16 i = first; i < 8; i++) codes[i] = digits[i];
    /* Decimal source digits already include the units place. Avoid the
     * arcade HUD's extra fixed trailing zero or a binary conversion. */
    hud_blank(col, 0, first);
    hud_codes(col + first, 0, 0, codes + first, 8 - first);
    memcpy(previous, digits, 8);
}

void bc_hud_begin(void)
{
    hud_begin_fixed(1);
    memset(last_score, 255, sizeof(last_score));
    memset(last_high, 255, sizeof(last_high));
    last_lives = 255;
    hud_text(1, 0, 0, "P1");
    hud_text(15, 0, 0, "HI");
    hud_text(29, 0, 0, "LIVES");
}

void bc_hud_draw(const BcScore *score, unsigned char lives)
{
    score_digits(4, score->digits, last_score);
    score_digits(18, score->high, last_high);
    if (lives != last_lives) {
        hud_number(35, 0, 0, lives & 128 ? 0 : lives + life_offset, 3);
        last_lives = lives;
    }
    hud_frame();
}

static u8 party_digits[4][8], party_lives[4];
void bc_hud_party_begin(unsigned char count)
{
    hud_begin_fixed(count > 2 ? 2 : 1);
    memset(party_digits, 255, sizeof(party_digits));
    memset(party_lives, 254, sizeof(party_lives));
    hud_blank(0, 0, HUD_COLS); hud_blank(0, 1, HUD_COLS);
    for (u8 i = 0; i < count; i++) {
        s16 col = (i & 1)*20, row = i >> 1;
        char label[3] = {'P', '1'+i, 0};
        hud_text(col, row, 0, label); hud_text(col+12, row, 0, "L");
    }
}

void bc_hud_party_draw(const BcScore *const scores[4], const unsigned char lives[4], unsigned char count)
{
    for (u8 i = 0; i < count; i++) {
        s16 col = (i & 1)*20, row = i >> 1;
        if (!digits_equal(scores[i]->digits, party_digits[i])) {
            u16 codes[8], first = 0;
            while (first < 7 && !scores[i]->digits[first]) first++;
            for (u16 j = first; j < 8; j++) codes[j] = scores[i]->digits[j];
            hud_blank(col+3, row, first);
            hud_codes(col+3+first, row, 0, codes+first, 8-first);
            memcpy(party_digits[i], scores[i]->digits, 8);
        }
        if (party_lives[i] != lives[i]) {
            hud_blank(col+13, row, 3);
            if (lives[i] & 128) hud_text(col+13, row, 0, "OUT");
            else hud_number(col+13, row, 0, lives[i] + life_offset, 3);
            party_lives[i] = lives[i];
        }
    }
    hud_frame();
}
