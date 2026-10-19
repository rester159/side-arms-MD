#!/usr/bin/env python3
"""Compare linked first-stage background data and Vivid colors to a local v1.2 ROM."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from bc_background_equivalence import symbols, compare_round
from vivid_palette import base_lut, index

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--reference', type=Path, required=True, help='User-supplied v1.2 cartridge')
p.add_argument('--before', type=Path, required=True, help='v2 ROM/symbol directory')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = Path('out/release/rom.bin').read_bytes()
syms = symbols(Path('out/release/symbol.txt'))
reference = a.reference.read_bytes()
checked = {}
for kind in ('tiles', 'attr', 'map', 'pal'):
    name = 'zone0_' + kind
    data = Path('res/generated', name + '.bin').read_bytes()
    assert rom[syms[name]:syms[name]+len(data)] == data
    offset = reference.find(data)
    assert offset >= 0, (kind, 'does not match v1.2')
    checked[kind] = dict(bytes=len(data), reference_offset=offset)
lut = base_lut()
assert reference.find(struct.pack('>512H', *lut)) >= 0, 'Vivid transform differs from v1.2'
palette = struct.unpack_from('>32H', rom, syms['zone0_pal'])
expected = tuple(lut[index(v)] for v in palette)
assert struct.unpack_from('>32H', rom, syms['zone0_vivid_pal']) == expected
sprite = struct.unpack_from('>32H', rom, syms['sprite_pal'])
assert struct.unpack_from('>32H', rom, syms['sprite0_vivid_pal']) == tuple(lut[index(v)] for v in sprite)
before = (a.before/'rom.bin').read_bytes()
old_syms = symbols(a.before/'symbol.txt')
assert rom[syms['vivid_lut']:syms['vivid_lut']+1024] == before[old_syms['vivid_lut']:old_syms['vivid_lut']+1024]
rounds = [compare_round(before, old_syms, rom, syms, n) for n in range(1, 11)]
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              reference_sha256=hashlib.sha256(reference).hexdigest(),
              first_stage=checked, vivid_words=64, shared_vivid_lut_unchanged=True,
              bc_rounds_unchanged=rounds)
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
