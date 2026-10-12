#pragma once

/* Six-voice native score engine. All score branches are offsets into compiled
 * music data; this module contains no source CPU emulation or ROM accesses.
 * One tick is the cartridge's 113*1024 CPU-clock sound interrupt period. */
typedef struct {
    const unsigned char *score;
    const unsigned short *songs;       /* 21 x six channel offsets */
    const unsigned char *envelopes;    /* 32 x eight resolved parameters */
    const unsigned short *periods;     /* 128 source pitch periods */
} HucardScoreData;

/* Latched sound-chip output. A new note does not write its pitch until the
 * first envelope step; preserving that delay avoids shortening tied notes. */
typedef struct {
    unsigned short period;
    unsigned char volume, pan, instrument;
} HucardVoice;

typedef struct {
    HucardVoice voice[6];
    unsigned char channel[6][24]; /* 23 fields, big-endian words, alignment padding */
    unsigned short phase, tempo;
    unsigned char clock, transpose, instrument;
} HucardScore;

extern const HucardScoreData hucard_score_data;
void hucard_score_stop(HucardScore *state);
/* Commands 0..20 are the source music entries, including its three aliases. */
void hucard_score_start(HucardScore *state, const HucardScoreData *data, unsigned char song);
void hucard_score_tick(HucardScore *state, const HucardScoreData *data);
