"""Use the matching Normal flash and import the four unmatched BC death poses."""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades

ROOT = Path(__file__).resolve().parents[1]

def append_shapes(big, index, palettes):
    records = []
    codes = (0x7e0, 0x1a6, 0x7e2, 0x7e3, 0x7e4)
    shapes = json.loads((ROOT / 'tools/data/bc_player_death_shapes.json').read_text())['shapes']
    assert [s['source_pose'] for s in shapes] == [0xb500, 0xb680, 0xb800, 0xb980, 0xbb00]
    for position, (shape, code) in enumerate(zip(shapes, codes)):
        key = code | (8 << 11)
        if position == 1:
            assert index[key], 'Matching Normal explosion must already exist'
            records.append(dict(**shape, code=code, key=key, colour=8,
                                geometry_source='matching_normal_explosion'))
            continue
        assert not index[key], 'Reserved BC death key collides with an existing sprite'
        pixels = np.array([[int(v, 16) for v in row] for row in shape['rows']])
        colors = np.array(shape['colors'][1:])
        weights = np.bincount(pixels.ravel(), minlength=16)[1:]
        # The fire is one ordered dark-red -> orange -> yellow -> white ramp.
        options = [fit_shades(colors, colors, weights, palette, [list(range(15))])
                   for palette in palettes]
        selected = min(range(2), key=lambda i: options[i][0])
        _, mapping, ramps = options[selected]
        lut = [0] + [pen + 1 for pen in mapping]
        pens = np.array(lut)[pixels]
        packed = bytes(int(pens[ty*8+y, tx*8+x]) << 4 | int(pens[ty*8+y, tx*8+x+1])
                       for tx in range(4) for ty in range(4)
                       for y in range(8) for x in range(0, 8, 2))
        big.extend(packed)
        assert len(big) // 512 < 32768
        index[key] = len(big) // 512 | selected << 15
        records.append(dict(**shape, code=code, key=key, colour=8, palette=selected,
                            pen_lut=lut, shade_ramps=ramps,
                            geometry_source='original_pce_player_death'))
    (ROOT / 'res/generated/bc_player_death_shapes.json').write_text(json.dumps(records, indent=2) + '\n')
    (ROOT / 'src/gen/bc_player_death_keys.h').write_text(
        '/* Generated BC death sequence; colour 8, Normal data unchanged. */\n'
        '#pragma once\n#define BC_PLAYER_DEATH_CODES {' +
        ', '.join(f'0x{code:03x}' for code in codes) + '}\n')
