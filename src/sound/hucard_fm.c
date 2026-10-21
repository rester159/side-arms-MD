#include "hucard_fm.h"

static unsigned short pitch_divide(unsigned long dividend, unsigned short divisor)
{
#if defined(__m68k__)
    /* Octave selection bounds divisor to 128..65535 and the largest
     * quotient to 34723. DIVU therefore cannot overflow its 16-bit result. */
    __asm__ ("divu.w %1,%0" : "+d"(dividend) : "d"(divisor) : "cc");
    return (unsigned short)dividend;
#else
    return dividend / divisor;
#endif
}

void hucard_fm_frame(const HucardScore *score, unsigned char pal, unsigned char *packet)
{
    /* Packed source pan curve: YM stereo bits in the high byte, louder
     * source-side level in the low byte. Indexed only when timbre changes. */
    static const unsigned short pan_info[256] = {
        0x0000, 0x4003, 0x4005, 0x4007, 0x4009, 0x400b, 0x400d, 0x400f, 0x4010, 0x4013, 0x4015, 0x4017, 0x4019, 0x401b, 0x401d, 0x401f,
        0x8003, 0xc003, 0xc005, 0xc007, 0xc009, 0xc00b, 0xc00d, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8005, 0xc005, 0xc005, 0xc007, 0xc009, 0xc00b, 0xc00d, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8007, 0xc007, 0xc007, 0xc007, 0xc009, 0xc00b, 0xc00d, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8009, 0xc009, 0xc009, 0xc009, 0xc009, 0xc00b, 0xc00d, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x800b, 0xc00b, 0xc00b, 0xc00b, 0xc00b, 0xc00b, 0xc00d, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x800d, 0xc00d, 0xc00d, 0xc00d, 0xc00d, 0xc00d, 0xc00d, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x800f, 0xc00f, 0xc00f, 0xc00f, 0xc00f, 0xc00f, 0xc00f, 0xc00f, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8010, 0xc010, 0xc010, 0xc010, 0xc010, 0xc010, 0xc010, 0xc010, 0xc010, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8013, 0xc013, 0xc013, 0xc013, 0xc013, 0xc013, 0xc013, 0xc013, 0xc013, 0xc013, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc015, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc017, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x8019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc019, 0xc01b, 0xc01d, 0xc01f,
        0x801b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01b, 0xc01d, 0xc01f,
        0x801d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01d, 0xc01f,
        0x801f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f, 0xc01f,
    };
    /* The single VInt producer owns this cache. Envelopes often change while
     * pitch does not; avoid repeating 32-bit divisions on those updates.
     * Period zero is normalized to 4096, so zero-initialized keys are invalid. */
    /* Keep one voice's keys and packet together, so the renderer advances
     * one cache pointer rather than several independent arrays. Word storage
     * keeps every packet aligned; caller destinations may still be odd. */
    typedef struct {
        unsigned short period, pitch, levels;
        unsigned char region, instrument;
        unsigned short packet[6];
    } VoiceCache;
#if defined(__m68k__)
    _Static_assert(sizeof(VoiceCache) == 20, "FM cache RAM budget");
#endif
    static VoiceCache cache[6];
    VoiceCache *c = cache;
    const HucardVoice *v = score->voice;
    unsigned char channel;
    unsigned char aligned = !((unsigned long)packet & 1);
    for (channel = 0; channel < 6; ++channel, ++c, ++v, packet += HUCARD_FM_VOICE_BYTES) {
        unsigned char instrument = v->instrument;
        unsigned short period = v->period ? v->period : 4096;
        unsigned char block = 0, i;
        unsigned char *voice_bytes = (unsigned char *)c->packet;
        /* PSG frequency = (7159090.909/2)/(32*period).
         * YM frequency = Fnum * clock * 2^block / (144*2^21).
         * Rounded constants use 53693175/7 and 53203424/7 master clocks. */
        if (c->period != period || c->region != pal) {
            if (period <= 4096) {
                /* Index zero is the PSG's normalized zero-period value. */
                c->pitch = hucard_fm_pitch[pal != 0][period & 4095];
            } else {
                unsigned long divisor = period;
                unsigned long numerator = pal ? 4444560UL : 4404020UL;
                /* Smallest divisor whose rounded quotient fits 11 bits:
                 * floor((numerator + floor(d/2))/d) <= 2047.
                 * Select the octave first, then divide only once. */
                unsigned short minimum = pal ? 2171 : 2151;
                while (divisor < minimum && block < 7) {
                    ++block; divisor <<= 1;
                }
                unsigned long fnum = pitch_divide(numerator + divisor/2, (unsigned short)divisor);
                if (fnum > 2047) fnum = 2047;
                c->pitch = (block << 11) | fnum;
            }
            c->period = period;
            c->region = pal;
            voice_bytes[1] = c->pitch >> 8;
            voice_bytes[2] = c->pitch;
        }
        /* YM has on/off stereo, so preserve hard pans and use the louder side
         * for soft pans. Per-side volume differences cannot be exact on YM. */
        /* Volumes are 0..31, so adding one leaves zero an invalid key. */
        unsigned short levels = (((unsigned short)v->volume << 8) | v->pan) + 1;
        unsigned char *cached = voice_bytes + 3;
        if (c->levels != levels || c->instrument != instrument) {
            const unsigned char *patch = hucard_fm_patches[instrument ? instrument - 1 : 0];
            unsigned char algorithm = hucard_fm_algorithms[instrument ? instrument - 1 : 0];
            unsigned short pan = pan_info[v->pan];
            unsigned short attenuation = 2 * (62 - v->volume - (pan & 31));
            /* Operator multipliers depend on the patch, not its envelope.
             * Populate them once per instrument (including the initial zero). */
            if (!c->levels || c->instrument != instrument) {
                voice_bytes[0] = instrument;
                for (i = 0; i < 4; ++i) cached[1+i] = patch[i];
            }
            cached[0] = (pan >> 8) | algorithm;
            for (i = 0; i < 4; ++i) {
                /* Twelve YM TL steps = +9 dB for carriers. Retain the
                 * fitted modulator depth below, so timbre stays unchanged. */
                signed short level = patch[4+i] + attenuation - 12;
                if (level < 0) level = 0;
                cached[5+i] = !v->volume || !instrument || level > 127 ? 127 : level;
            }
            /* The supported nonlinear patches (5/6, with optional feedback)
             * keep operator 1's modulation depth independent of volume. */
            if (algorithm != 7 && v->volume && instrument) cached[5] = patch[4];
            c->levels = levels;
            c->instrument = instrument;
        }
        /* Always write the destination, including a different caller buffer. */
#if defined(__m68k__)
        if (aligned) {
            __asm__ volatile (
                "move.l (%0),%%d0\n\t"
                "move.l %%d0,(%1)\n\t"
                "move.l 4(%0),%%d0\n\t"
                "move.l %%d0,4(%1)\n\t"
                "move.l 8(%0),%%d0\n\t"
                "move.l %%d0,8(%1)"
                : : "a"(voice_bytes), "a"(packet) : "d0", "cc", "memory");
        } else
#else
        (void)aligned;
#endif
        for (i = 0; i < HUCARD_FM_VOICE_BYTES; ++i) packet[i] = voice_bytes[i];
    }
}
