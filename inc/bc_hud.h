#pragma once
#include "bc_score.h"
void bc_hud_begin(void);
void bc_hud_draw(const BcScore *score, unsigned char lives);
void bc_hud_party_begin(unsigned char count);
void bc_hud_party_draw(const BcScore *const scores[4], const unsigned char lives[4], unsigned char count);

/* Select before begin: source counts reserves; Home displays total lives. */
void bc_hud_show_total_lives(unsigned char enabled);
