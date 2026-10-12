#!/usr/bin/env python3
"""Check linked Vivid shade order and prove a palette-only cartridge change."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from bc_background_equivalence import symbols
from build_vivid_palette import constraints
from vivid_palette import base_lut, guard, index, light, word

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True, help='Directory with rom.bin and symbol.txt')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = (ROOT/'out/release/rom.bin').read_bytes()
old = (a.baseline/'rom.bin').read_bytes()
sy = symbols(ROOT/'out/release/symbol.txt')
old_sy = symbols(a.baseline/'symbol.txt')
address = sy['vivid_lut']
assert address == old_sy['vivid_lut']
assert len(rom) == len(old) == 4*1024*1024
actual = list(struct.unpack_from('>512H', rom, address))
assert old[address:address+1024] == struct.pack('>512H', *base_lut()), 'Use the pre-guard baseline'
assert rom[address:address+1024] == (ROOT/'res/generated/vivid_lut.bin').read_bytes()
differences = [i for i, (x, y) in enumerate(zip(old, rom)) if x != y]
assert differences
assert all(address <= i < address+1024 or 0x18e <= i < 0x190 for i in differences), \
       'Unexpected change outside Vivid table and cartridge checksum'
palettes, edges, ramps = constraints()
for darker, lighter, minimum in edges:
    assert light(actual[index(lighter)])-light(actual[index(darker)]) >= minimum
# Read metadata's actual final mappings, not just its cached luminance claims.
for ramp in ramps:
    shades = [light(actual[index(v)]) for v in ramp['colors']]
    assert all(b-a >= 200 for a, b in zip(shades, shades[1:])), ramp
assert guard(actual, edges) == actual, 'Guard must be idempotent'
assert all(v & ~0xeee == 0 for v in actual)
assert actual[0] == 0
# A one-step blue ramp is below the 0.2 luma threshold used by material fitting,
# but its two distinct existing shades must still survive the display mode.
blue = [word((0, 0, n)) for n in (6, 7)]
guarded = guard(base_lut(), [(blue[0], blue[1], 114)])
assert [guarded[index(v)] for v in blue] == blue
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              baseline_sha256=hashlib.sha256(old).hexdigest(),
              palette_banks=len(palettes), ordered_pairs=len(edges), explicit_ramps=len(ramps),
              changed_rom_bytes=len(differences), only_lut_and_checksum_changed=True,
              runtime_code_unchanged=True, standard_art_and_palettes_unchanged=True,
              remaining_rom_bytes=len(rom)-sy['_etext'],
              scope='Existing converted shade ordering in Vivid. Upstream quantization and visual approval remain separate.')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
