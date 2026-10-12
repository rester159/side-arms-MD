#!/usr/bin/env python3
"""Native shared-arena ownership/reset checks using explicit development hooks.

This is a mode-transition test, not a natural playthrough or speed benchmark.
"""
import argparse
import hashlib
import json
import struct
from run_rom import ROOT, Runner

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=__import__('pathlib').Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
r = Runner()
r.run(2600)
arena = r.symbols['enemy_arena'] & 0xffffff
for symbol, offset in [('actors', 0), ('en_small', 0), ('en_big', 1600), ('en_item', 2560)]:
    assert r.symbols[symbol] & 0xffffff == arena + offset, symbol
rows = []
for players in range(1, 5):
    for round_number in (0, 7, 9):
        r.write('dbg_bc_native_players', struct.pack('>H', players))
        r.write('dbg_bc_native_start_round', struct.pack('>H', round_number))
        r.write('dbg_bc_native_protect', b'\0\1')
        r.write('dbg_bc_native', b'\0\1')
        for _ in range(800):
            if r.u16('dbg_bc_native_status') == 4:
                r.write('dbg_bc_native_audio_ack', b'\0\1')
            r.run(1)
            assert r.u16('dbg_bc_native_status') in (0, 4), (players, round_number)
        assert r.read('party_count', 1)[0] == players
        assert any(r.read('actors', 1728)), 'BC did not populate the shared arena'
        assert r.read('actors', 1728) == r.read('en_small', 1728)
        r.write('dbg_bc_native', b'\0\0')
        r.run(2)
        assert not any(r.read('enemy_arena', 2880)), 'BC state leaked into Normal pools'
        assert r.read('n_live', 3) == bytes(3)
        ends = struct.unpack('>3I', r.read('pool_end', 12))
        assert [value & 0xffffff for value in ends] == [arena, arena + 1600, arena + 2560]
        assert not r.u32('peers'), 'BC peer allocation survived exit'
        assert r.u32('flow_state') == 0
        rows.append(dict(players=players, round=round_number + 1, populated=True, reset=True))
result = dict(rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),
              cases=rows, arena_bytes=2880, removed_duplicate_bytes=1728,
              scope='Development-hook mode transitions; no natural-play or FPS claim')
(a.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print('PASS shared native arena aliases, 12 BC entry/exit/reentry cases, pool metadata reset and peer release')
