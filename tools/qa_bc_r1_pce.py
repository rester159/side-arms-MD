#!/usr/bin/env python3
"""Check linked BC R1 art against independently decoded original PCE cells."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from bc_background_equivalence import symbols, rendered_cell, compare_round
from inspect_bc_background import source_cell

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--before', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = Path('out/release/rom.bin').read_bytes()
sy = symbols(Path('out/release/symbol.txt'))
old = (a.before/'rom.bin').read_bytes()
os = symbols(a.before/'symbol.txt')
ref = Path('.local/pce-reference/play-task-round1')
code = (ref/'code-002160.bin').read_bytes()
vram = np.frombuffer((ref/'f002880-vram.bin').read_bytes(), '<u2')
source_words = np.frombuffer((ref/'f002880-palette.bin').read_bytes(), '<u2')
colors = np.array([tuple(int(w)>>s & 7 for s in (3,6,0)) for w in source_words], np.uint8)
pal = struct.unpack_from('>32H', rom, sy['bc_bg_palette'])
rgb = [tuple(w>>s & 7 for s in (1,5,9)) for w in pal]
remap = struct.unpack_from('>256H', rom, sy['bc_bg_remap'])
vivid = struct.unpack_from('>32H', rom, sy['bc_bg_vivid_palette'])
from vivid_palette import light
for offset in (0,16):
    for i in range(offset+1,offset+16):
        for j in range(offset+1,offset+16):
            if pal[i]!=pal[j] and all(x<=y for x,y in zip(rgb[i],rgb[j])):
                assert light(vivid[j])-light(vivid[i]) >= min(200,light(pal[j])-light(pal[i])), 'Vivid merged a shade step'

assert rom[sy['bc_round1_code']:sy['bc_round1_code']+65536] == code
assert all(v == 4095 for v in remap[63:])
correspondence = {}
pixels = exact = opaque = protected = 0
for cell in range(63):
    source = source_cell(code, vram, colors, cell)
    actual = rendered_cell(rom, sy, 'bc_bg', remap[cell])
    for y in range(32):
        for x in range(32):
            src = tuple(map(int, source[y,x]))
            pixel = actual[y*32+x]
            dst = rgb[(pixel[1]>>13&1)*16+pixel[0]] if pixel and pixel[0] else (0,0,0)
            assert bool(any(src)) == bool(pixel and pixel[0]), (cell,x,y,'silhouette')
            bank = code[0x6221+cell*8+(y//16*2+x//16)*2]>>4
            # A source color has one output everywhere in its palette, avoiding
            # independent character fits that would introduce tile seams.
            key = (bank,src)
            assert correspondence.setdefault(key,dst) == dst, (cell,x,y,'color seam')
            if bank in (4,5,9,10):
                assert src == dst, (cell,x,y,'protected original shade')
                protected += 1
            pixels += 1
            if any(src):
                opaque += 1
                exact += src == dst
for name,size in [('bc_round1_code',65536),('vivid_lut',1024),('zone0_vivid_pal',64)]:
    assert old[os[name]:os[name]+size] == rom[sy[name]:sy[name]+size], name
normal = 0
for path in Path('res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:
        continue
    size = path.stat().st_size
    assert old[os[path.stem]:os[path.stem]+size] == rom[sy[path.stem]:sy[path.stem]+size], path.stem
    normal += 1
rounds = [compare_round(old,os,rom,sy,n) for n in range(2,11)]
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
    geometry_pixels=pixels, protected_palette_pixels=protected,
    exact_standard_color_pixels=exact, opaque_pixels=opaque,
    normal_blobs_unchanged=normal, other_bc_rounds_unchanged=rounds)
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
