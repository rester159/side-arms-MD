"""Canonical completed-scene gameplay bytes for BC comparison replays.

Transient native pointers are excluded. This is deliberately not full RAM or
video; capture mode independently verifies those against the original recording.
"""
from bc_actor_layout import read_actor_pool
from bc_weapon_layout import beam_rotation, beam_velocity_shift, player_layout, normalize_player

VELOCITY_SHIFT = beam_velocity_shift()
NATIVE_LAYOUT = player_layout(VELOCITY_SHIFT)
PLAYER_BYTES = NATIVE_LAYOUT["player_bytes"]
POINTER_START, POINTER_END = 1000, 1008
SCORE_BYTES = 35


def validate_native_layout():
    """Fail instead of silently comparing the wrong bytes after an ABI change."""
    import os
    import subprocess
    from pathlib import Path
    from run_rom import ROOT
    cc = Path(os.environ.get('GDK', Path.home()/'mars/m68k-elf'))/'bin/m68k-elf-gcc'
    source = f"""
#include "bc_player.h"
#include "bc_stage.h"
#include "bc_score.h"
#include "bc_continue.h"
_Static_assert(sizeof(BcPlayerControl)=={PLAYER_BYTES}, "scene player stride");
_Static_assert(__builtin_offsetof(BcPlayerControl,world.weapons.shots)==8, "projectile pool offset");
_Static_assert(sizeof(BcShot)=={NATIVE_LAYOUT["shot_bytes"]}, "projectile stride");
_Static_assert(__builtin_offsetof(BcShot,body.x)==0 && __builtin_offsetof(BcShot,body.y)==4, "projectile axes");
_Static_assert(__builtin_offsetof(BcPlayerControl,world.shot_index)=={NATIVE_LAYOUT["pointer_start"]}, "shot pointer exclusion");
_Static_assert(__builtin_offsetof(BcPlayerControl,world.party)=={NATIVE_LAYOUT["pointer_start"]+4}, "party pointer exclusion");
_Static_assert(sizeof(((BcWorldPlayer *)0)->party)==4, "native pointer width");
_Static_assert(sizeof(BcStage)==24, "scene stage bytes");
_Static_assert(sizeof(BcScore)==35, "scene score stride");
_Static_assert(sizeof(BcContinue)==3, "scene continue stride");
"""
    subprocess.run([str(cc), '-m68000', '-std=c11', '-fsyntax-only',
                    '-I'+str(ROOT/'inc'), '-x', 'c', '-'], input=source,
                   text=True, check=True)


def player_bytes(runner, address):
    raw = bytes(runner.ram[((address+i) & 65535) ^ 1] for i in range(PLAYER_BYTES))
    raw = normalize_player(raw, beam_rotation(), VELOCITY_SHIFT)
    return raw[:POINTER_START] + raw[POINTER_END:]


def canonical_scene_bytes(runner, players):
    assert 1 <= players <= 4
    # Keep the established solo byte sequence exactly compatible with its corpus.
    data = (read_actor_pool(runner) + runner.read('stage', 24) +
            player_bytes(runner, runner.symbols['player']) +
            runner.read('seed', 2) + runner.read('score', SCORE_BYTES) +
            runner.read('credits', 1) + runner.read('unused_continues', 4))
    if players > 1:
        assert runner.read('party_count', 1)[0] == players
        peers = runner.u32('peers')
        assert peers and not peers & 1, 'Missing or unaligned peer allocation'
        for i in range(players-1):
            data += player_bytes(runner, peers + i*PLAYER_BYTES)
        data += runner.read('peer_scores', SCORE_BYTES*(players-1))
        data += runner.read('continue_prompts', 12)
        data += runner.read('continue_pending', 1) + runner.read('continue_shown', 1)
    assert len(data) == 2682 + ((players-1)*1051 + 14 if players > 1 else 0)
    return data


def state_layout(players):
    layout = dict(actor_pool=dict(records=32, canonical_record_bytes=50),
                  stage_bytes=24,
                  player=dict(native_bytes=PLAYER_BYTES,
                              excluded_byte_ranges=[[NATIVE_LAYOUT["pointer_start"], NATIVE_LAYOUT["pointer_end"]]],
                              projectile_velocity_shift=VELOCITY_SHIFT,
                              projectile_storage_rotation=beam_rotation(),
                              projectile_canonical_rotation=0),
                  rng_seed_bytes=2, score_bytes=SCORE_BYTES,
                  credits_bytes=1, unused_continue_bytes=4,
                  total_hashed_bytes=2682)
    if players > 1:
        layout.update(peer_players=players-1, canonical_bytes_per_peer=1016,
                      peer_score_bytes=SCORE_BYTES*(players-1), continue_prompt_bytes=12,
                      continue_pending_bytes=1, continue_shown_bytes=1)
        layout['total_hashed_bytes'] += (players-1)*1051 + 14
    return layout
