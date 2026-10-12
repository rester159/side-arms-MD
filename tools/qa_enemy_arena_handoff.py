#!/usr/bin/env python3
"""Enter BC from populated Normal/Rush worlds, then restart Normal.

Uses menu inputs to start gameplay and explicit BC development-entry hooks.
"""
import argparse
import json
import struct
from pathlib import Path
from run_rom import Runner, PAD

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
r = Runner()
r.run(2600)
assert r.symbols['player'] == r.symbols['players'] == r.symbols['player_arena']
assert r.symbols['stage'] == r.symbols['level_bc']

def tap(button):
    r.run(5, PAD[button]); r.run(20)

def launch(mode):
    assert r.u32('flow_state') == 0
    tap('DOWN'); tap('START')
    assert r.u32('flow_state') == 9
    for _ in range(r.read('home_cursor', 1)[0]): tap('UP')
    for _ in range(2 if mode == 'rush' else 0): tap('DOWN')
    tap('A')
    for _ in range(r.read('player_choice', 1)[0]): tap('UP')
    tap('A')
    for frame in range(1200):
        r.run(1, PAD['START'] if frame % 40 == 0 else PAD['A'] if frame % 40 == 20 else 0)
    assert r.u32('flow_state') == (12 if mode == 'rush' else 7)
    assert not r.u32('stage_sources'), 'Normal/Rush retained BC block sources'

rows = []
for mode in ('normal', 'rush'):
    launch(mode)
    live = list(r.read('n_live', 3))
    boss = list(r.read('boss_hud', 1))
    assert any(live) or any(boss), (mode, live, boss)
    r.write('dbg_bc_native_players', b'\0\4')
    r.write('dbg_bc_native_protect', b'\0\1')
    r.write('dbg_bc_native', b'\0\1')
    for _ in range(600):
        if r.u16('dbg_bc_native_status') == 4:
            r.write('dbg_bc_native_audio_ack', b'\0\1')
        r.run(1)
        assert r.u16('dbg_bc_native_status') in (0, 4)
    assert r.read('n_live', 3) == bytes(3)
    assert not any(r.read('boss_hud', 1)), 'Normal boss survived BC adoption'
    assert any(r.read('actors', 1728))
    assert r.u32('peers'), 'Four-player BC did not acquire peer storage'
    assert r.u32('stage_sources') == r.symbols['bc_bg_sources'], 'BC did not select indexed block sources'
    r.write('dbg_bc_native', b'\0\0')
    r.run(2)
    assert not r.u32('stage_sources'), 'BC block sources survived session release'
    assert not any(r.read('enemy_arena', 2880))
    assert not r.u32('peers'), 'BC peer allocation survived session release'
    arena = r.symbols['enemy_arena'] & 0xffffff
    assert [v & 0xffffff for v in struct.unpack('>3I', r.read('pool_end', 12))] == [arena, arena+1600, arena+2560]
    rows.append(dict(source=mode, live_pools=live, boss_active=bool(boss[0]), bc_players=4, cleanup=True))
launch('normal')
assert any(r.read('n_live', 3)), 'Normal failed to populate pools after BC'
(a.output/'result.json').write_text(json.dumps(dict(handoffs=rows, normal_restarted=True), indent=2)+'\n')
print('PASS populated Normal -> BC -> Rush -> BC -> Normal; shared player/level views, peer release, pool/boss cleanup and restart')
