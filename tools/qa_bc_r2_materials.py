#!/usr/bin/env python3
"""Prove linked R2 composition and every opaque RGB3 shade against original art."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from bc_background_equivalence import symbols, compare_round, rendered_cell
from quantize import to_md, md_word
from inspect_bc_background import source_cell
from vivid_palette import light, index
import zones

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = (ROOT/'out/release/rom.bin').read_bytes()
sy = symbols(ROOT/'out/release/symbol.txt')
old = (a.baseline/'rom.bin').read_bytes()
os = symbols(a.baseline/'symbol.txt')
d = json.loads((ROOT/'tools/data/bc_background_r2_materials.json').read_text())
code = rom[sy['bc_round2_code']:sy['bc_round2_code']+65536]
assert hashlib.sha256(code).hexdigest() == d['source_code_sha256']
src = Source()
main = src.region('maincpu')
bg = decode_bgtiles(src.region('bgtiles'))
codes, colors, _ = bgmap_cells(src.region('bgmap'))
x, y, w, h = zones.ZONES[1]['rect']
metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                for r in range(y, y+h) for c in range(x, x+w)})
source_colors = [to_md(tuple(v//17 for v in palette_rgb(
    main[0x14a37+i], main[0x14e37+i]))) for i in range(1024)]
palette = struct.unpack_from('>32H', rom, sy['bc_bg2_palette'])
remap = struct.unpack_from('>256H', rom, sy['bc_bg2_remap'])
art = d['bc_cave_art']
cap = ROOT/'.local/pce-reference/round02-reference'
for kind in ('vram','palette'):
    assert hashlib.sha256((cap/f'f002400-{kind}.bin').read_bytes()).hexdigest() == art[f'source_{kind}_sha256']
vram = np.fromfile(cap/'f002400-vram.bin','<u2')
pw = np.fromfile(cap/'f002400-palette.bin','<u2')
pce_colors = np.array([(int(w)>>3&7,int(w)>>6&7,int(w)&7) for w in pw],np.uint8)
checked = opaque = imported = 0
used = set()
for record in d['cells']:
    cell = record['cell']
    assert list(code[0x6220+cell*8:0x6228+cell*8]) == record['source_descriptor']
    actual = rendered_cell(rom, sy, 'bc_bg2', remap[cell])
    for k, donor in enumerate(record['characters']):
        if str(k//8*2+(k%4)//2) in record.get('bc_cave_quadrants', {}):
            continue
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
    reference = source_cell(code,vram,pce_colors,cell)
    for q_text, pattern in record.get('bc_cave_quadrants', {}).items():
        q = int(q_text)
        bank, pat = pattern.split('/')
        assert record['source_descriptor'][q*2] == int(pat,16)
        assert record['source_descriptor'][q*2+1]>>4 == int(bank)
        pens = np.array([int(v,16) for v in art['patterns'][pattern]]).reshape(16,16)
        source_palette = np.array(art['source_rgb3_banks'][bank])
        assert np.array_equal(source_palette[pens], reference[q//2*16:q//2*16+16,q%2*16:q%2*16+16]), (cell,q,'source cave contour')
        for y in range(16):
            for x in range(16):
                pen = int(pens[y,x]);pos = (q//2*16+y)*32+q%2*16+x
                value = actual[pos];output_pen = value[0] if value else 0
                assert bool(output_pen) == (pen != 0), (cell,q,x,y,'cave silhouette')
                checked += 1
                if not pen:continue
                normal_pen = art['source_pen_to_normal_pen'][bank][pen]
                normal_bank = art.get('source_normal_palettes',{}).get(bank,2)
                overrides = art.get('normal_pen_color_overrides',{}) if normal_bank == 2 else {}
                expected = tuple(overrides.get(str(normal_pen), source_colors[normal_bank*16+normal_pen]))
                color = palette[(value[1]>>13&1)*16+output_pen]
                assert (color>>1&7,color>>5&7,color>>9&7) == expected
                imported += 1
assert [r['cell'] for r in d['cells']] == list(range(89))
assert all(v == 4095 for v in remap[89:])
assert {c for c, p in used} <= {2, 3}
old_remap = struct.unpack_from('>256H', old, os['bc_bg2_remap'])
old_palette = struct.unpack_from('>32H', old, os['bc_bg2_palette'])
rebuilt_housings = (0x3d,0x40,0x41,0x42,0x44,0x4c,0x4f,0x50,0x51)
def colors_for(pixels, colors):
    return [colors[(p[1]>>13&1)*16+p[0]] if p and p[0] else -1 for p in pixels]
for cell in range(89):
    previous = rendered_cell(old, os, 'bc_bg2', old_remap[cell])
    current = rendered_cell(rom, sy, 'bc_bg2', remap[cell])
    if cell not in rebuilt_housings and not any(v.split('/')[0] in ('12','13') for v in d['cells'][cell].get('bc_cave_quadrants',{}).values()):
        assert colors_for(previous, old_palette) == colors_for(current, palette), (cell, 'unexpected art change outside housing repair')
    row = d['cells'][cell]
    for pos,(old_pixel,new_pixel) in enumerate(zip(previous,current)):
        q = pos//512*2+(pos%32)//16
        if cell not in rebuilt_housings and str(q) not in row.get('bc_cave_quadrants',{}):
            assert bool(old_pixel and old_pixel[0]) == bool(new_pixel and new_pixel[0]), (cell,pos,'retained silhouette')
# The compound housings must join their corresponding complete material halves,
# rather than repeat the upright lamp in all three distinct BC arrangements.
def material_pixels(cell):
    return [palette[(p[1]>>13&1)*16+p[0]] if p and p[0] else -1
            for p in rendered_cell(rom, sy, 'bc_bg2', remap[cell])]
lamp, cap = material_pixels(0x38), material_pixels(0x3c)
assert material_pixels(0x44) == cap[:512] + lamp[:512], 'upper housing/lamp join'
assert material_pixels(0x4f) == lamp[512:] + cap[512:], 'rods/lower housing join'
assert material_pixels(0x4c) == sum([lamp[y*32:y*32+32] for y in range(31,-1,-1)], []), 'inverted lamp housing'
for cell in (0x40,0x41,0x42):
    assert material_pixels(cell)[512:] == material_pixels(0x4d)[:512], (cell,'upper cap')
for cell in (0x50,0x51):
    assert material_pixels(cell)[:512] == cap[512:], (cell,'lower cap')
assert material_pixels(0x3d) == material_pixels(0x39)[:512] + material_pixels(0x3e)[:512], 'circle/rail join'
shading = json.loads((ROOT/'res/generated/bc_r2_material_shading.json').read_text())
vivid = struct.unpack_from('>512H',rom,sy['vivid_lut'])
for ramp in shading['shade_ramps']:
    for values in (ramp['colors'],[vivid[index(c)] for c in ramp['colors']]):
        assert len(set(values)) == len(values)
        assert all(light(a)<light(b) for a,b in zip(values,values[1:]))
machine_ramps = {'blue': [7,8,9,10], 'olive': [1,2,3,4]}
for name, pens in machine_ramps.items():
    values = [md_word(source_colors[3*16+pen]) for pen in pens]
    assert all(value in palette[16:] for value in values), (name,'missing machine shade')
    for ramp in (values, [vivid[index(value)] for value in values]):
        assert len(set(ramp)) == len(ramp), (name,'merged machine shade')
        assert all(light(a)<light(b) for a,b in zip(ramp,ramp[1:])), (name,'reversed machine shade')

for number in range(1, 11):
    prefix = 'bc_bg'+(str(number) if number>1 else '')
    entries = struct.unpack_from('>256H',rom,sy[prefix+'_remap'])
    assert all(v==4095 or not v&0xc000 for v in entries), (number, 'whole-cell flags conflict with canonical character storage')
    name = f'bc_round{number}_code'
    assert rom[sy[name]:sy[name]+65536] == old[os[name]:os[name]+65536]
others = [compare_round(old, os, rom, sy, n) for n in range(1, 11) if n != 2]
normal = 0
for path in (ROOT/'res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:
        continue
    data = path.read_bytes()
    assert rom[sy[path.stem]:sy[path.stem]+len(data)] == old[os[path.stem]:os[path.stem]+len(data)] == data
    normal += 1
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              cells=89, source_geometry_pixels=checked, exact_retained_normal_shade_pixels=opaque, bc_geometry_material_pixels=imported,
              source_palette_pen_pairs=len(used), unchanged_machinery_silhouettes_verified=True,
              rebuilt_housing_cells=list(rebuilt_housings), housing_joins_verified=True,
              source_banks_unchanged=10, other_round_cells_unchanged=sum(r['cells'] for r in others),
              normal_blobs_unchanged=normal, remaining_rom_bytes=len(rom)-sy['_etext'],
              scope='BC cave and small-machine contours with distinct Normal material ramps; complete Normal housing/cap/rail combinations. Visual suitability remains inferred.')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
