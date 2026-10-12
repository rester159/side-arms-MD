#pragma once

typedef struct {
    unsigned char digits[8], high[8], queue[16];
    unsigned char read, write, next_life;
} BcScore;
typedef struct {
    unsigned char consumed, refresh_score, refresh_high, life_awarded, sound;
} BcScoreEvent;

/* Source queue overwrites on wrap; $FF remains its empty sentinel. */
void bc_score_enqueue(BcScore *score, unsigned char command, unsigned char playing);
/* $6501-$650A: continue clears points and the extend cursor, preserving high
 * score and the queue/read/write records outside the source clear range. */
void bc_score_continue(BcScore *score);
/* One score-task iteration, including its RNG update and at most one award. */
/* A null seed skips RNG work for peer score queues; the leader advances it. */
BcScoreEvent bc_score_step(BcScore *score, unsigned short *random_seed, unsigned char *lives);
/* Home bonus policy; count zero disables score extends. Decimal thresholds
 * are shared by the party, while each score keeps its own next_life cursor.
 * A null random_seed skips RNG work, as with bc_score_step. */
BcScoreEvent bc_score_step_extends(BcScore *score, unsigned short *random_seed,
    unsigned char *lives, const unsigned char table[][8], unsigned char count);

/* Ending overlay $60DE-$6122: award (reserves+1) * 2^unused_continues
 * units of 10,000, using the source's three decimal columns and wrap.
 * Returns the three-digit bonus count for its presentation. Does not consume
 * queued scores, award lives, advance RNG or update the high-score task.
 * Source-valid continue counts are 0..5. Out-of-play players get no bonus. */
unsigned short bc_score_completion_bonus(BcScore *score, unsigned char reserves,
    unsigned char unused_continues);
