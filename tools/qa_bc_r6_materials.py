#!/usr/bin/env python3
"""Prove linked R6 composition and every opaque RGB3 shade against original art."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from bc_background_equivalence import symbols, compare_round, rendered_cell
from quantize import to_md
import zones

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = (ROOT/'out/release/rom.bin').read_bytes()
sy = symbols(ROOT/'out/release/symbol.txt')
old = (a.baseline/'rom.bin').read_bytes()
os = symbols(a.baseline/'symbol.txt')
d = json.loads((ROOT/'tools/data/bc_background_r6_materials.json').read_text())
code = rom[sy['bc_round6_code']:sy['bc_round6_code']+65536]
assert hashlib.sha256(code).hexdigest() == d['source_code_sha256']
src = Source()
main = src.region('maincpu')
bg = decode_bgtiles(src.region('bgtiles'))
codes, colors, _ = bgmap_cells(src.region('bgmap'))
x, y, w, h = zones.ZONES[13]['rect']
metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                for r in range(y, y+h) for c in range(x, x+w)})
source_colors = [to_md(tuple(v//17 for v in palette_rgb(
    main[0x14a37+i], main[0x14e37+i]))) for i in range(1024)]
palette = struct.unpack_from('>32H', rom, sy['bc_bg6_palette'])
remap = struct.unpack_from('>256H', rom, sy['bc_bg6_remap'])
checked = opaque = 0
used = set()
for record in d['cells']:
    cell = record['cell']
    assert list(code[0x6220+cell*8:0x6228+cell*8]) == record['source_descriptor']
    actual = rendered_cell(rom, sy, 'bc_bg6', remap[cell])
    for k, donor in enumerate(record['characters']):
        cd, col = metas[donor['meta']]
        sub = donor['subtile']
        pens = bg[cd, sub//4*8:sub//4*8+8, sub%4*8:sub%4*8+8]
        if donor['flip'] & 1:
            pens = pens[:, ::-1]
        if donor['flip'] & 2:
            pens = pens[::-1]
        for y in range(8):
            for x in range(8):
                pen = int(pens[y, x])
                value = actual[(k//4*8+y)*32+k%4*8+x]
                output_pen = value[0] if value else 0
                assert bool(output_pen) == (pen != 15), (cell, k, x, y, 'silhouette')
                checked += 1
                if pen == 15:
                    continue
                color = palette[(value[1] >> 13 & 1)*16+output_pen]
                rgb = color >> 1 & 7, color >> 5 & 7, color >> 9 & 7
                assert rgb == source_colors[col*16+pen], (cell, k, col, pen, rgb)
                opaque += 1
                used.add((col, pen))
assert [r['cell'] for r in d['cells']] == list(range(131))
assert all(v == 4095 for v in remap[131:])
assert {c for c, p in used} == {7, 14}
# The connector must remain one complete corresponding Normal object.
connector = [d['patterns'][f'{pat:02x}/8'] for pat in (0x17, 0x1f, 0x1d, 0x1e)]
for y in range(4):
    for x in range(4):
        assert connector[y//2*2+x//2][y%2*2+x%2] == dict(meta=48, subtile=y*4+x, flip=0)
for number in range(1, 11):
    name = f'bc_round{number}_code'
    assert rom[sy[name]:sy[name]+65536] == old[os[name]:os[name]+65536]
others = [compare_round(old, os, rom, sy, n) for n in range(1, 11) if n != 6]
normal = 0
for path in (ROOT/'res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:
        continue
    data = path.read_bytes()
    assert rom[sy[path.stem]:sy[path.stem]+len(data)] == old[os[path.stem]:os[path.stem]+len(data)] == data
    normal += 1
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              cells=131, source_geometry_pixels=checked, exact_rgb3_shade_pixels=opaque,
              source_palette_pen_pairs=len(used), complete_connector=True,
              source_banks_unchanged=10, other_round_cells_unchanged=sum(r['cells'] for r in others),
              normal_blobs_unchanged=normal, remaining_rom_bytes=len(rom)-sy['_etext'],
              scope='Inferred Normal character composition and exact source RGB3 shades; not user approval or PCE geometry identity.')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
