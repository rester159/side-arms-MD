#!/usr/bin/env python3
"""Replay the Home intro and verify scene maps, tile uploads and CRAM."""
import argparse
import ctypes as C
import hashlib
import json
import struct
from pathlib import Path
from run_rom import ROOT, Runner, PAD

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--rom', type=Path, default=ROOT/'out/release/rom.bin')
p.add_argument('--mode', type=int, choices=(0, 1), default=0)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
r = Runner(rom=a.rom)
rom = a.rom.read_bytes()
cram = (C.c_uint16*64).in_dll(r.lib, 'cram')
zram = (C.c_uint8*0x2000).in_dll(r.lib, 'zram')
lut = struct.unpack_from('>512H', rom, r.symbols['vivid_lut'])

def packed(word):
    return (word >> 1 & 7) | (word >> 5 & 7) << 3 | (word >> 9 & 7) << 6

maps = {i: rom[r.symbols[f'fe_scene{i}_map']:r.symbols[f'fe_scene{i}_map']+3584]
        for i in range(1, 16)}
palettes = {}
for i in range(1, 16):
    name = 'fe_earth_pal' if i in (1, 2) and 'fe_earth_pal' in r.symbols else 'fe_set1_pal'
    raw = struct.unpack_from('>32H', rom, r.symbols[name])
    palettes[i] = [packed(lut[packed(w)] if a.mode else w) for w in raw]

def tap(button):
    r.run(5, PAD[button]); r.run(15)

r.run(2600); tap('DOWN'); tap('START')
assert r.u32('flow_state') == 9
r.write('home_cfg', b'\1', 7)  # Select the integrated HuCard soundtrack.
r.write('game_cfg', bytes([a.mode]), 7)  # GameConfig.color; u8 fields.
r.write('color_mode', bytes([a.mode]))
tap('A')
assert r.read('player_dialog', 1) == b'\1'
tap('DOWN'); tap('DOWN')  # Default two-player selection -> four.
r.run(5, PAD['A'])
assert r.read('color_mode', 1) == bytes([a.mode])
seen = set(); sequence = []; unknown = 0; captures = []
for frame in range(1600):
    r.run(1, PAD['START'] if frame % 40 == 0 else PAD['A'] if frame % 40 == 20 else 0)
    assert not zram[0x1b0a], ('HuCard underrun', frame)
    state = r.u32('flow_state')
    if state == 7:
        break
    if state != 6:
        continue
    actual_map = bytes(r.vram[(0xe000+j)^1] for j in range(3584))
    matches = [i for i, expected in maps.items() if actual_map == expected]
    if not matches:
        unknown += 1
        continue
    i = matches[0]
    assert list(cram[:32]) == palettes[i], ('palette mismatch', frame, i)
    if sequence and sequence[-1]['scene'] == i:
        sequence[-1]['frames'] += 1
    else:
        sequence.append(dict(scene=i, frames=1))
    if i not in seen:
        at = r.symbols['fe_set1_tiles']
        # Palette placement is not a reliable tile length; source descriptor is.
        descriptor = r.symbols['fe_scene_sets']+10
        tile_ptr, count, pal_ptr = struct.unpack_from('>IHI', rom, descriptor)
        assert tile_ptr == at
        actual_tiles = bytes(r.vram[(160*32+j)^1] for j in range(count*32))
        assert actual_tiles == rom[at:at+count*32], ('tile upload', i)
        r.capture(a.output/f'scene-{i}.png'); captures.append(i); seen.add(i)
else:
    raise AssertionError('intro did not reach gameplay')
assert seen == set(range(1, 16)), seen
assert r.u16('player_limit') == 4
result = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(), mode=a.mode,
              players=4, hucard=True, underruns=0, sequence=sequence,
              frames_to_play=frame+1, unmatched_intro_frames=unknown,
              scenes=sorted(seen), captures=captures)
(a.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k != 'sequence'}, indent=2))
