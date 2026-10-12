#!/usr/bin/env python3
"""Check source pens against linked cartridge pixels and displayed shade ramps."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from arcade_source import ROOT, Source, decode_sprites
from bc_background_equivalence import symbols
from vivid_palette import index, light


def unpack(data, size):
    pixels = np.empty((size, size), np.uint8)
    for y in range(size):
        for x in range(size):
            tile = (x // 8) * (size // 8) + y // 8
            value = data[tile * 32 + y % 8 * 4 + x % 8 // 2]
            pixels[y, x] = value & 15 if x & 1 else value >> 4
    return pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rom = (ROOT / 'out/release/rom.bin').read_bytes()
    sy = symbols(ROOT / 'out/release/symbol.txt')
    words = lambda name, n: struct.unpack_from(f'>{n}H', rom, sy[name])
    palette = words('bc_sprite_pal', 32)
    normal_palette = words('sprite_pal', 32)
    vivid = words('vivid_lut', 512)
    gallery = []
    for i, c in enumerate(normal_palette):
        level = (((c & 14)*3 + ((c >> 4)&14)*6 + ((c >> 8)&14))//10)&14
        green = 14 if level == 14 else (level*5//14)*2
        blue = 14 if level == 14 else (level*2//14)*2
        gallery.append(level | green << 4 | blue << 8 if i & 15 else 0)
    source = decode_sprites(Source().region('sprites'))
    records = json.loads((ROOT / 'res/generated/bc_sprite_recolors.json').read_text())
    checked = ramps = visible_steps = 0
    rows = []
    for record in records:
        size = record['size']
        bank = 'spr_big' if size == 32 else 'spr_bank'
        entry = struct.unpack_from('>H', rom, sy[bank+'_index'] + record['key']*2)[0]
        assert entry & 32767, record['id']
        assert entry >> 15 == record['palette'], record['id']
        address = sy[bank] + ((entry & 32767)-1)*size*size//2
        pixels = unpack(rom[address:address+size*size//2], size)
        kind = record.get('geometry_source', 'normal')
        if kind == 'normal':
            code = record['code']
            pens = source[code] if size == 16 else np.block([
                [source[code], source[code+1]], [source[code+8], source[code+9]]])
        else:
            pens = np.array([[int(p, 16) for p in row] for row in record['rows']])
        assert np.array_equal(pixels, np.array(record['pen_lut'])[pens]), record['id']
        checked += pixels.size
        colors = gallery if kind == 'normal' and record['source_palette'] == 15 else palette
        offset = (entry >> 15)*16
        shift = 1 if kind == 'bc_unique_shapes' else 0
        present = []
        for ramp in record['shade_ramps']:
            values = []
            actual_visible = 0
            for group, expected in zip(ramp['pens'], ramp['luminance']):
                source_pens = [p+shift for p in group]
                chosen = {colors[offset+record['pen_lut'][p]] for p in source_pens}
                assert len(chosen) == 1, (record['id'], group)
                value = chosen.pop()
                assert abs(light(value)/1000-expected) < .001, (record['id'], group)
                mask = np.isin(pens, source_pens)
                if mask.any():
                    assert {colors[offset+int(p)] for p in pixels[mask]} == {value}
                    actual_visible += 1
                values.append(value)
            for displayed in (values, [vivid[index(v)] for v in values]):
                assert all(light(b)-light(a) >= 190 for a, b in zip(displayed, displayed[1:])), record['id']
            ramps += 1
            visible_steps += actual_visible
            present.append(actual_visible)
        rows.append(dict(id=record['id'], geometry_source=kind, visible_steps_per_ramp=present))
    report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
                  records=len(records), linked_pixel_checks=checked, ordered_ramps=ramps,
                  visible_shade_steps=visible_steps, modes=['Standard', 'Vivid'],
                  scope='All generated ordinary BC recolors and unique/beam shapes, including gallery variants. Source geometry and linked pens checked; shade ordering checked against actual linked palettes. Boss imports, unrecolored Normal assets, semantic matches and subjective hue fidelity are separate.',
                  assets=rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'assets'}, indent=2))


if __name__ == '__main__':
    main()
