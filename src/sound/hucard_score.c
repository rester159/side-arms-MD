#include "hucard_score.h"

/* Channel fields retain source arithmetic widths. Internal stream offsets
 * and periods use big-endian words; original score operands remain little
 * endian. Other bytes are source counters/parameters, not CPU state. */
enum {
    LEFT = 2, GATE, RATIO, FLAGS, VOLUME, OCTAVE, TRANSPOSE, DETUNE, SLIDE,
    REPEAT = 11, PAN = 15, INSTRUMENT, ENV, LEVEL, MOD_CLOCK, PERIOD, TREMOLO = 22
};

static unsigned short word(const unsigned char *p)
{
    return p[0] | ((unsigned short)p[1] << 8);
}

/* Channel starts and PERIOD (offset 20) are word aligned; score operands
 * remain byte decoded because their offsets may be odd. */
#if defined(__m68k__)
typedef unsigned short __attribute__((may_alias)) ChannelWord;
_Static_assert(__builtin_offsetof(HucardScore, channel) % 2 == 0,
               "channel base must be word aligned");
_Static_assert(sizeof(((HucardScore *)0)->channel[0]) % 2 == 0,
               "channel stride must be word aligned");
#endif

static unsigned short channel_word(const unsigned char *p)
{
#if defined(__m68k__)
    return *(const ChannelWord *)p;
#else
    return ((unsigned short)p[0] << 8) | p[1];
#endif
}

static void put_word(unsigned char *p, unsigned short value)
{
#if defined(__m68k__)
    *(ChannelWord *)p = value;
#else
    p[0] = value >> 8; p[1] = value;
#endif
}

static unsigned char next(const HucardScoreData *data, unsigned char *c)
{
    unsigned short pc = channel_word(c);
    put_word(c, pc + 1);
    return data->score[pc];
}

static unsigned short next_word(const HucardScoreData *data, unsigned char *c)
{
    unsigned short pc = channel_word(c);
    put_word(c, pc + 2);
    return word(data->score + pc);
}

void hucard_score_stop(HucardScore *s)
{
    unsigned char *p = (unsigned char *)s;
    unsigned short i;
    for (i = 0; i < sizeof(*s); ++i) p[i] = 0;
    s->clock = 255;
}

void hucard_score_start(HucardScore *s, const HucardScoreData *data, unsigned char song)
{
    unsigned char i;
    hucard_score_stop(s);
    if (song >= 21) return;
    for (i = 0; i < 6; ++i) {
        put_word(s->channel[i], data->songs[song * 6 + i]);
        s->channel[i][PAN] = 0xdd;
        s->voice[i].pan = 0xdd;
    }
}

static void envelope(unsigned char *c, const unsigned char *ins, HucardVoice *voice)
{
    unsigned char phase = c[ENV] & 7;
    signed short level = c[LEVEL], delta;
    unsigned short period;
    if (phase == 4) return;
    switch (phase) {
    case 0:
        level += ins[0];
        if (level >= 248) { level = 248; ++c[ENV]; }
        break;
    case 1:
        level -= ins[1];
        if (!ins[1] || level < ins[2]) { level = ins[2]; ++c[ENV]; }
        break;
    case 3:
        if (ins[3]) {
            level -= ins[3];
            if (level < 0) { level = 0; ++c[ENV]; }
        }
        break;
    }
    c[LEVEL] = level;
    delta = (signed char)c[SLIDE];
    if (ins[5]) delta += (signed char)((c[ENV] & 64) ? -ins[5] : ins[5]);
    period = channel_word(c + PERIOD) + delta;
    put_word(c + PERIOD, period);
    if (ins[6]) {
        signed short value = c[TREMOLO];
        value += (c[ENV] & 32) ? -ins[6] : ins[6];
        c[TREMOLO] = value < 0 ? 0 : value > 255 ? 255 : value;
    }
    voice->period = (period >> 2) & 4095;
    {
        signed short volume = (c[LEVEL] < c[TREMOLO] ? c[LEVEL] : c[TREMOLO]) >> 3;
        volume += (signed char)c[VOLUME];
        voice->volume = volume > 0 ? volume : 0;
    }
    if (++c[MOD_CLOCK] == (ins[4] & 127)) {
        c[MOD_CLOCK] = 0;
        c[ENV] ^= 128;
        if (c[ENV] & 128) c[ENV] ^= 64;
        c[ENV] ^= 32;
    }
}

static void step(HucardScore *s, const HucardScoreData *data, unsigned char *c,
                 unsigned char envelope_allowed, HucardVoice *voice)
{
    unsigned short guard;
    /* Internal stream offsets are aligned native words. */
    if (!channel_word(c)) return;
    if (c[INSTRUMENT]) s->instrument = c[INSTRUMENT] - 1;
    if (c[LEFT] > 1) {
        --c[LEFT];
        if (c[GATE] && !--c[GATE] && !(c[FLAGS] & 4)) c[ENV] = (c[ENV] & 248) | 3;
        /* Resolve envelope data only when this step will consume it. The
         * source-selected instrument still updates above, even while silent. */
        if (envelope_allowed && (c[ENV] & 7) != 4)
            envelope(c, data->envelopes + s->instrument * 8, voice);
        return;
    }
    /* The compiler checks boundaries; cap control-only paths as a fail-silent
     * guard instead of allowing malformed data to hang an interrupt. */
    for (guard = 0; guard < 1000; ++guard) {
        unsigned char op = next(data, c), slot, count;
        unsigned short target;
        if (op >= 31) {
            unsigned char pitch = op & 31, tied = c[FLAGS] & 4;
            unsigned short length = ((c[FLAGS] & 8) ? 2 : 3) << ((op >> 5) - 1);
            if (c[FLAGS] & 1) {
                if ((op >> 5) > 1) length += length >> 1;
                c[FLAGS] &= ~1;
            }
            c[LEFT] = length;
            target = (length * c[RATIO]) >> 8;
            c[GATE] = target < 2 ? 2 : target;
            if (!pitch) { c[GATE] = 1; return; }
            c[FLAGS] = (c[FLAGS] & ~4) | ((c[FLAGS] & 2) << 1);
            if (!tied) {
                unsigned char note = pitch - 1 + (c[OCTAVE] & 127) +
                    ((c[OCTAVE] & 128) ? 24 : 0) + s->transpose + c[TRANSPOSE];
                unsigned short period = data->periods[note & 127] + (signed char)c[DETUNE];
                put_word(c + PERIOD, period << 2);
                c[LEVEL] = 0;
                c[ENV] &= 224;
            }
            if ((c[FLAGS] & 16) || ((data->envelopes[s->instrument * 8 + 4] & 128) && !tied)) {
                c[MOD_CLOCK] = 0;
                c[TREMOLO] = 255;
                c[ENV] &= 7;
                voice->volume = 0;
            }
            c[FLAGS] &= ~16;
            return;
        }
        switch (op) {
        case 0: s->tempo = next_word(data, c); s->phase = 0; s->clock = 0; break;
        case 1: c[RATIO] = next(data, c); break;
        case 2: c[VOLUME] = (next(data, c) & 31) - 31; break;
        case 3:
            count = next(data, c) + 1;
            if (count != c[INSTRUMENT]) {
                c[INSTRUMENT] = count; c[FLAGS] |= 16;
                s->instrument = count - 1;
                voice->instrument = count;
                voice->volume = 0;
            }
            break;
        case 4: c[FLAGS] ^= 8; break;
        case 5: c[FLAGS] ^= 2; break;
        case 6: c[FLAGS] |= 1; break;
        case 7: c[OCTAVE] = (c[OCTAVE] & 128) | next(data, c); break;
        case 8: c[OCTAVE] |= 128; break;
        case 9: c[OCTAVE] &= 127; break;
        case 10: s->transpose = next(data, c); break;
        case 11: c[TRANSPOSE] = next(data, c); break;
        case 12: c[DETUNE] = next(data, c); break;
        case 13: c[SLIDE] = next(data, c); break;
        case 14: case 15: case 16: case 17:
            slot = op - 14 + REPEAT; count = next(data, c); target = next_word(data, c);
            if (c[slot]) --c[slot]; else c[slot] = count;
            if (c[slot]) put_word(c, target);
            break;
        case 18: case 19: case 20: case 21:
            slot = op - 18 + REPEAT; target = next_word(data, c);
            if (c[slot] == 1) { c[slot] = 0; put_word(c, target); }
            break;
        case 22: target = next_word(data, c); put_word(c, target); break;
        case 23: put_word(c, 0); voice->volume = 0; voice->pan = 0xdd; return;
        case 24: c[FLAGS] ^= 128; break;
        case 25: c[PAN] = next(data, c); voice->pan = c[PAN]; break;
        default: put_word(c, 0); return;
        }
    }
    put_word(c, 0);
}

void hucard_score_tick(HucardScore *s, const HucardScoreData *data)
{
    unsigned char first = 1;
    s->phase += s->tempo;
    while (s->clock != s->phase >> 8) {
        unsigned char i;
        ++s->clock;
        for (i = 0; i < 6; ++i) step(s, data, s->channel[i], first, &s->voice[i]);
        first = 0;
    }
}
