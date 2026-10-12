#!/usr/bin/env python3
"""Check linked chamber materials against independent Normal pixel decoding."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from bc_background_equivalence import symbols, compare_round, rendered_cell
from arcade_source import Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from vivid_palette import light, index as color_index
import zones

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
old = (a.baseline / 'rom.bin').read_bytes()
os = symbols(a.baseline / 'symbol.txt')
rom = (ROOT / 'out/release/rom.bin').read_bytes()
sy = symbols(ROOT / 'out/release/symbol.txt')
d = json.loads((ROOT / 'tools/data/bc_background_r9_materials.json').read_text())
code = rom[sy['bc_round9_code']:sy['bc_round9_code'] + 65536]
assert hashlib.sha256(code).hexdigest() == d['source_code_sha256']
# Decode before zone-wide palette fitting, so inherited shade loss cannot pass.
source=Source();main=source.region('maincpu');bg=decode_bgtiles(source.region('bgtiles'))
codes,cols,_=bgmap_cells(source.region('bgmap'))
x,y,w,h=zones.ZONES[19]['rect']
metas=sorted({(int(codes[r,c]),int(cols[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
source_palette=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(main[0x14a37+i],main[0x14e37+i]))))for i in range(1024)],np.uint16)
remap=struct.unpack_from('>256H',rom,sy['bc_bg9_remap'])
palette=struct.unpack_from('>32H',rom,sy['bc_bg9_palette'])

checked = 0
for rec in d['cells']:
    cell = rec['cell']
    assert list(code[0x6220 + cell * 8:0x6228 + cell * 8]) == rec['source_descriptor']
    assert rec['patterns'] == rec['source_descriptor'][::2]
    block = remap[cell]
    assert block != 4095
    actual = rendered_cell(rom, sy, 'bc_bg9', block)
    for y in range(4):
        for x in range(4):
            k = y * 4 + x
            pat = rec['patterns'][y // 2 * 2 + x // 2]
            donor = d['patterns'][f'{pat:02x}'][y % 2 * 2 + x % 2]
            expected = np.zeros((8, 8), np.uint16)
            if donor is not None:
                cd,col=metas[donor['normal_meta']];k_source=donor['subtile']
                assert col==16
                pens=bg[cd,k_source//4*8:k_source//4*8+8,k_source%4*8:k_source%4*8+8].astype(np.int32)
                expected=np.where(pens==15,0,0x8000|source_palette[col*16+pens])
                if donor['flip'] & 1:
                    expected = expected[:, ::-1]
                if donor['flip'] & 2:
                    expected = expected[::-1, :]
            for py in range(8):
                for px in range(8):
                    value=actual[(y*8+py)*32+x*8+px]
                    color=0 if value is None or not value[0] else 0x8000|palette[(value[1]>>13&1)*16+value[0]]
                    assert color==int(expected[py,px]), (cell,k,px,py)
            checked += 64
assert {r['cell'] for r in d['cells']} == {i for i, e in enumerate(remap) if e != 4095}
lut=struct.unpack_from('>512H',rom,sy['vivid_lut'])
source_colors=set(map(int,source_palette[16*16:16*16+15]))
assert source_colors<=set(palette[1:16])
ordered=0
for a_color in source_colors:
    for b_color in source_colors:
        rgb=lambda w: (w>>1&7,w>>5&7,w>>9&7)
        if a_color!=b_color and all(a<=b for a,b in zip(rgb(a_color),rgb(b_color))):
            assert light(lut[color_index(a_color)])<light(lut[color_index(b_color)])
            ordered+=1
for n in range(1, 11):
    name = f'bc_round{n}_code'
    assert old[os[name]:os[name] + 65536] == rom[sy[name]:sy[name] + 65536]
unchanged = [compare_round(old, os, rom, sy, n) for n in range(1, 11) if n != 9]
normal = 0
for path in (ROOT / 'res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:
        continue
    data = path.read_bytes()
    assert rom[sy[path.stem]:sy[path.stem] + len(data)] == old[os[path.stem]:os[path.stem] + len(data)] == data
    normal += 1
result = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(), source_cells=49,
              pixel_checks=checked, source_rgb3_colors=len(source_colors), vivid_ordered_pairs=ordered, source_banks_unchanged=10,
              other_round_cells_unchanged=sum(r['cells'] for r in unchanged),
              normal_blobs_unchanged=normal, normal_zone=19, full_speed_verified=False)
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
