#pragma once
#include "player.h"
#include "bc_player.h"

/* One engine-owned live player/weapon arena. Rules retain their native record
 * formats; inactive views must not be read or retained across session changes.
 * Extra BC records are allocated only after the boot font buffers are released. */
typedef union {
    Player normal[MAX_PLAYERS];
    BcPlayerControl bc;
} PlayerArena;
extern PlayerArena player_arena;
extern BcPlayerControl *peers;
extern u16 players_bc_count; /* zero while the Normal union member is active */
#define normal_players (player_arena.normal)
bool players_bc_acquire(u16 count);
void players_bc_release(void);
