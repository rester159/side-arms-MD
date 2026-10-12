#!/usr/bin/env python3
"""Verify linked foundry art against Normal source pixels and explicit contours."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from bc_background_equivalence import symbols, compare_round, rendered_cell
from inspect_bc_background import source_cell, cell_index
from quantize import to_md
from vivid_palette import light, word as color_word, index
import zones

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = (ROOT/'out/release/rom.bin').read_bytes()
sy = symbols(ROOT/'out/release/symbol.txt')
old = (a.baseline/'rom.bin').read_bytes()
os = symbols(a.baseline/'symbol.txt')
d = json.loads((ROOT/'tools/data/bc_background_r7_materials.json').read_text())
code = rom[sy['bc_round7_code']:sy['bc_round7_code']+65536]
assert hashlib.sha256(code).hexdigest() == d['source_code_sha256']
capture = ROOT/'.local/pce-reference/round07-reference'
for suffix in ('vram', 'palette'):
    assert hashlib.sha256((capture/f'f002400-{suffix}.bin').read_bytes()).hexdigest() == d[f'source_{suffix}_sha256']
vram = np.fromfile(capture/'f002400-vram.bin', '<u2')
pce_words = np.fromfile(capture/'f002400-palette.bin', '<u2')
pce_colors = np.array([(int(w)>>3&7, int(w)>>6&7, int(w)&7) for w in pce_words], np.uint8)
# The engine clamps the extra Genesis left margin to map column 16.
# Reject accidental reintroduction of palette-consuming fallback cells there.
for cy in range(48, 56):
    for cx in range(16, 128):
        assert code[0xc000 + cell_index(cx * 32, cy * 32)] not in (86, 88)
assert not any(r.get('defensive_margin') for r in d['cells'])
assert not d['new_bc_art']['color_adjustments']
src = Source()
main = src.region('maincpu')
bg = decode_bgtiles(src.region('bgtiles'))
codes, colors, _ = bgmap_cells(src.region('bgmap'))
x, y, w, h = zones.ZONES[14]['rect']
metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                for r in range(y, y+h) for c in range(x, x+w)})
source_colors = [to_md(tuple(v//17 for v in palette_rgb(
    main[0x14a37+i], main[0x14e37+i]))) for i in range(1024)]
palette = struct.unpack_from('>32H', rom, sy['bc_bg7_palette'])
remap = struct.unpack_from('>256H', rom, sy['bc_bg7_remap'])
checked = opaque = imported_opaque = contour_rows = cleared = 0
for record in d['cells']:
    cell = record['cell']
    assert list(code[0x6220+cell*8:0x6228+cell*8]) == record['source_descriptor']
    actual = rendered_cell(rom, sy, 'bc_bg7', remap[cell])
    expected = np.full((32, 32), -1, dtype=np.int32)
    for k, donor in enumerate(record['characters']):
        cd, col = metas[donor['meta']]
        sub = donor['subtile']
        pens = bg[cd, sub//4*8:sub//4*8+8, sub%4*8:sub%4*8+8].astype(np.int32)
        remove = np.isin(pens, donor.get('clear_pens', []))
        if str(k//8*2+(k%4)//2) not in record.get("new_bc_quadrants", {}):
            cleared += int(remove.sum())
        pens[remove] = 15
        assert col == 17 or np.all(pens == 15), (cell, k, col)
        if donor['flip'] & 1:
            pens = pens[:, ::-1]
        if donor['flip'] & 2:
            pens = pens[::-1]
        expected[k//4*8:k//4*8+8, k%4*8:k%4*8+8] = np.where(pens == 15, -1, pens+col*16)
    for q, bounds in enumerate(record['quadrant_bounds']):
        if bounds is None:
            continue
        assert not record.get('defensive_margin')
        reference = source_cell(code, vram, pce_colors, cell)
        for y, (lo, hi) in enumerate(bounds):
            source_row = reference[q//2*16+y, q%2*16:q%2*16+16]
            live = np.flatnonzero(source_row.any(1))
            assert (lo, hi) == ((int(live.min()), int(live.max())) if len(live) else (16, -1))
            row = expected[q//2*16+y, q%2*16:q%2*16+16]
            row[:lo] = -1
            row[hi+1:] = -1
            contour_rows += 1
    for q_text, pattern in record.get('new_bc_quadrants', {}).items():
        q = int(q_text)
        pixels = np.array(d['new_bc_art']['patterns'][pattern]).reshape(16, 16)
        colors = np.array(d['new_bc_art']['palette_rgb3'])
        reference = source_cell(code, vram, pce_colors, cell)[q//2*16:q//2*16+16, q%2*16:q%2*16+16]
        assert np.array_equal(colors[pixels], reference), (cell, q, 'imported BC art differs from reference')
        expected[q//2*16:q//2*16+16, q%2*16:q%2*16+16] = np.where(pixels == 0, -1, pixels+1024)
    for pos, source in enumerate(expected.ravel()):
        value = actual[pos]
        pen = value[0] if value else 0
        assert bool(pen) == (source != -1), (cell, pos, 'silhouette')
        checked += 1
        if source == -1:
            continue
        word = palette[(value[1] >> 13 & 1)*16+pen]
        rgb = word >> 1 & 7, word >> 5 & 7, word >> 9 & 7
        expected_rgb = tuple(d["new_bc_art"]["palette_rgb3"][source-1024]) if source >= 1024 else source_colors[source]
        if source >= 1024:
            expected_rgb = {tuple(a):tuple(b) for a,b in d['new_bc_art'].get('color_adjustments', [])}.get(expected_rgb, expected_rgb)
        assert rgb == expected_rgb, (cell, pos, source, rgb)
        if source >= 1024:
            imported_opaque += 1
        else:
            opaque += 1
changes = {tuple(a):tuple(b) for a,b in d['new_bc_art'].get('color_adjustments', [])}
warm = [color_word(changes.get(tuple(c), tuple(c))) for c in d['new_bc_art']['warm_shade_ramp_rgb3']]
vivid_lut = struct.unpack_from('>512H', rom, sy['vivid_lut'])
for ramp in (warm, [vivid_lut[index(c)] for c in warm]):
    assert len(set(ramp)) == 7
    assert all(light(a) < light(b) for a,b in zip(ramp, ramp[1:]))
# Retain the full green and blue ladders used by the repaired machinery.
for source_ramp in ([color_word((0, g, 0)) for g in range(1, 6)],
                    [color_word((0, 0, b)) for b in range(2, 5)]):
    for ramp in (source_ramp, [vivid_lut[index(c)] for c in source_ramp]):
        assert len(set(ramp)) == len(ramp)
        assert all(light(a) < light(b) for a, b in zip(ramp, ramp[1:]))
assert {r['cell'] for r in d['cells']} == {i for i, v in enumerate(remap) if v != 4095}
for number in range(1, 11):
    name = f'bc_round{number}_code'
    assert rom[sy[name]:sy[name]+65536] == old[os[name]:os[name]+65536]
others = [compare_round(old, os, rom, sy, n) for n in range(1, 11) if n != 7]
normal = 0
for path in (ROOT/'res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:
        continue
    raw = path.read_bytes()
    assert rom[sy[path.stem]:sy[path.stem]+len(raw)] == old[os[path.stem]:os[path.stem]+len(raw)] == raw
    normal += 1
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              cells=len(d['cells']), primary_cells=sum(not r.get("defensive_margin", False) for r in d["cells"]),
              defensive_margin_cells=sum(bool(r.get("defensive_margin")) for r in d["cells"]),
              geometry_pixels=checked, exact_retained_rgb3_shade_pixels=opaque,
              new_bc_pixels_with_declared_palette_adjustments=imported_opaque,
              standard_and_vivid_warm_shades=7, standard_and_vivid_green_shades=5, standard_and_vivid_blue_shades=3, reference_contour_rows=contour_rows, omitted_backdrop_pixels=cleared,
              source_banks_unchanged=10, other_round_cells_unchanged=sum(r['cells'] for r in others),
              normal_blobs_unchanged=normal, bytes_after_etext_including_trailing_data=len(rom)-sy['_etext'],
              scope='Normal donor pixels plus new BC wall/machine geometry/shades; source fidelity only, not whole-scene visual approval.')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report, indent=2))
