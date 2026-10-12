"""Append original BC weapon shapes where no corresponding Normal art is verified."""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades
ROOT = Path(__file__).resolve().parents[1]

def append_shapes(bank, index, keys, palettes):
    records = []
    definitions = ['/* Generated BC-only weapon keys. */', '#pragma once']
    for shape in json.loads((ROOT/'tools/data/bc_player_projectile_shapes.json').read_text())['shapes']:
        pixels = np.array([[int(v,16) for v in row] for row in shape['source_rows']])
        colors = np.array(shape['source_colors'][1:])
        reuse = {}
        if shape['decision'] in ('keep', 'recolor'):
            # Reuse the Normal pen regions, including its existing shade detail.
            entry = index[shape['normal_code'] | shape['normal_colour'] << 11]
            assert entry
            block = bank[((entry & 32767)-1)*128:(entry & 32767)*128]
            normal = np.array([[(block[((x//8)*2+y//8)*32+y%8*4+x%8//2]
                                >> (4 if x%2==0 else 0)) & 15
                               for x in range(16)] for y in range(16)])
            difference = int(np.count_nonzero((normal != 0) != (pixels != 0)))
            allowed = shape.get('silhouette_difference_pixels', 0) if shape['decision']=='keep' else 0
            assert difference == allowed, 'Silhouette differs from the reviewed correspondence'
            targets = np.zeros((15,3), dtype=float)
            source_colors = np.array(shape['source_colors'])
            for pen in range(1,16):
                if np.any(normal == pen):
                    targets[pen-1] = source_colors[pixels[normal == pen]].mean(axis=0)
            colors = targets
            pixels = normal
            reuse = dict(normal_rows=[''.join(format(int(v),'x') for v in row) for row in normal])
            if shape['decision'] == 'keep':
                key = shape['normal_code'] | shape['normal_colour'] << 11
                records.append(dict(**shape, **reuse, key=key, palette=entry>>15,
                                    pen_lut=list(range(16)), shade_ramps=[]))
                definitions.append(f'#define BC_PROJECTILE_{shape["source_pose"]:03X}_KEY 0x{key:04x}u')
                continue
        weights = np.bincount(pixels.ravel(), minlength=16)[1:]
        choices = [fit_shades(colors, colors, weights, palette, [list(range(15))]) for palette in palettes]
        selected = min(range(2), key=lambda i: choices[i][0])
        _, mapping, ramps = choices[selected]
        lut = [0]+[v+1 for v in mapping]
        pens = np.array(lut)[pixels]
        packed = bytes(int(pens[ty*8+y,tx*8+x])<<4 | int(pens[ty*8+y,tx*8+x+1])
                       for tx in range(2) for ty in range(2) for y in range(8) for x in range(0,8,2))
        key = next(code|(colour<<11) for code in range(0x128,0x140)
                   for colour in range(15,-1,-1) if not index[code|(colour<<11)])
        bank.extend(packed); index[key] = len(bank)//128 | selected<<15; keys.append(key)
        records.append(dict(**shape, **reuse, key=key, palette=selected, pen_lut=lut, shade_ramps=ramps))
        definitions.append(f'#define BC_PROJECTILE_{shape["source_pose"]:03X}_KEY 0x{key:04x}u')
    (ROOT/'src/gen/bc_player_projectile_keys.h').write_text('\n'.join(definitions)+'\n')
    (ROOT/'res/generated/bc_player_projectile_shapes.json').write_text(json.dumps(records,indent=2)+'\n')
