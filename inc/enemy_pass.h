#pragma once

/* Shared ordered live-record pass. The compile-time policies preserve the
 * caller's typed induction expressions: no opaque cursor, cached end, actor
 * adapter or per-record indirect call. In particular, a Normal end expression
 * is evaluated freshly after every update and BC keeps actor == &pool[slot].
 *
 * The sole traversal loop owns order, advance and the nonzero live-state gate.
 * Policy work is inside that loop: continue advances it, break ends the pass,
 * and return exits the caller. The surrounding do/while only makes this macro
 * a statement; there is no inner one-shot loop to intercept break/continue. */
/* Equivalent compile-time gate spellings retain each caller's original CFG.
 * These do not introduce a loop, so policy break/continue still target CORE. */
#define ENEMY_PASS_LIVE_IF(LIVE, ...) if (LIVE) { __VA_ARGS__ }
#define ENEMY_PASS_SKIP_FREE(LIVE, ...) if (!(LIVE)) continue; __VA_ARGS__

#define ENEMY_PASS_CORE(INIT, WITHIN, ADVANCE, SELECT, GATE, LIVE, ...) \
    do { \
        for (INIT; WITHIN; ADVANCE) { \
            SELECT \
            GATE(LIVE, __VA_ARGS__) \
        } \
    } while (0)

/* RECORD is an already-declared typed pointer. FRESH_END must be a pure
 * expression in this pool; it may change during policy work (birth/death). */
#define ENEMY_PASS_POINTER(RECORD, POOL, FRESH_END, STATE, ...) \
    ENEMY_PASS_CORE(RECORD = (POOL), RECORD < (FRESH_END), RECORD++, \
                    , ENEMY_PASS_LIVE_IF, RECORD->STATE, __VA_ARGS__)

/* SELECT runs only after the ordinal bound passes, so even first >= capacity
 * never forms an out-of-range pointer. CAPACITY must fit INDEX_TYPE. The
 * state-member path is relative to TYPE, e.g. body.state in the BC policy. */
#define ENEMY_PASS_INDEX(TYPE, INDEX_TYPE, RECORD, SLOT, POOL, FIRST, CAPACITY, STATE, ...) \
    ENEMY_PASS_CORE(INDEX_TYPE SLOT = (FIRST), SLOT < (CAPACITY), SLOT++, \
                    TYPE *RECORD = &(POOL)[SLOT];, ENEMY_PASS_SKIP_FREE, RECORD->STATE, __VA_ARGS__)
