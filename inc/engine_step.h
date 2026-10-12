#pragma once

/* Shared, statically typed simulation scheduler. A phase returns zero to
 * continue or its rules-specific stop reason. Direct phase expressions keep
 * the 68000 compiler's interprocedural constants visible: no runtime vtable,
 * escaped callback context, or per-entity dispatch is required.
 * Publish status only after the final executed phase, so phases observe
 * the same caller-owned result throughout the transaction. */
#define ENGINE_STEP(output, level_phase, player_phase, actor_phase, finish_phase) do { \
    unsigned char engine_status = (level_phase); \
    if (!engine_status) engine_status = (player_phase); \
    if (!engine_status) engine_status = (actor_phase); \
    if (!engine_status) engine_status = (finish_phase); \
    (output) = engine_status; \
} while (0)
