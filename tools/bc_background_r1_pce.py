"""Convert original BC R1 background characters to native Genesis resources.

Read the local verified PCE capture; source-derived art stays in ignored generated
resources. Keep every source pixel position and quadrant. Only palette fitting
is required: Genesis reserves two 16-color banks for scenery.
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
from bc_palette_fit import fit
from quantize import md_word, nearest

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT / '.local/pce-reference/play-task-round1'
HASHES = {
    'code-002160.bin': 'c5623ff8faab5175a48afeda4c7ab032d018295107fe74c71d30c7c8e2fe0c0a',
    'f002880-vram.bin': 'c82ae1ddf916d8a9bc825c397413fccdc9be31c642cce7ddea6ced25f50fca4f',
    'f002880-palette.bin': 'cab76d543ba74342da2e6689956a64abc3d7bba15ca9d7f73fac9f87e32a64bf',
}


def source():
    files = {}
    for name, expected in HASHES.items():
        raw = (CAPTURE/name).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == expected, name
        files[name] = raw
    code = files['code-002160.bin']
    vram = np.frombuffer(files['f002880-vram.bin'], '<u2')
    words = np.frombuffer(files['f002880-palette.bin'], '<u2')
    colors = [tuple(int(w)>>s & 7 for s in (3,6,0)) for w in words]
    characters = []
    for cell in range(63):
        for ty in range(4):
            for tx in range(4):
                at = 0x6220 + cell*8 + (ty//2*2+tx//2)*2
                pattern, attributes = code[at:at+2]
                tile = 0x1c0 + (pattern&248)*4 + (pattern&7)*2
                tile += ty%2*16 + tx%2
                pens = np.zeros((8,8), np.uint8)
                for y in range(8):
                    lo, hi = int(vram[tile*16+y]), int(vram[tile*16+y+8])
                    for x in range(8):
                        pens[y,x] = ((lo>>(7-x)&1) | (lo>>(15-x)&1)<<1 |
                                     (hi>>(7-x)&1)<<2 | (hi>>(15-x)&1)<<3)
                characters.append((attributes>>4, pens))
    return colors, characters


def compose():
    colors, characters = source()
    histograms = defaultdict(Counter)
    for bank, pens in characters:
        for pen, count in zip(*np.unique(pens, return_counts=True)):
            if pen:
                histograms[bank][colors[bank*16+int(pen)]] += int(count)
    # Original cave rock, stone floor and red earth fit together exactly in
    # fifteen opaque colors. Protect them rather than flattening their relief.
    terrain = sorted(set().union(*(histograms[b] for b in (4,9,10))))
    assert len(terrain) == 15
    water = sorted(histograms[5])
    banks = sorted(histograms)
    # One assignment per original palette prevents seams where identical source
    # pixels recur in different characters. No geometry or texture substitution.
    palettes, assignment = fit([histograms[b] for b in banks], 2, 15,
        fixed=[water, terrain],
        pinned=[1 if b in (4,9,10,12,13) else 0 for b in banks])
    target = dict(zip(banks, map(int, assignment)))
    packed, attrs = bytearray(), []
    exact = opaque = 0
    mappings = {}
    for bank in banks:
        mappings[bank] = [0] + [1+nearest(colors[bank*16+p], palettes[target[bank]]) for p in range(1,16)]
    for n, (bank, pens) in enumerate(characters):
        lut = mappings.get(bank, [0]*16)
        px = np.array(lut, np.uint8)[pens]
        for pen, count in zip(*np.unique(pens, return_counts=True)):
            if pen:
                opaque += int(count)
                exact += int(count) * (colors[bank*16+int(pen)] == palettes[target[bank]][lut[int(pen)]-1])
        packed.extend(((px[:,::2]<<4)|px[:,1::2]).tobytes())
        attrs.append(0x8000 | target.get(bank,0)<<13 | n%16 if px.any() else 0)
    palette = [w for bank in palettes for w in [0]+[md_word(c) for c in bank]+[0]*(15-len(bank))]
    gen = ROOT/'res/generated'
    (gen/'bc_r1_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r1_pce_conversion.json').write_text(json.dumps(dict(
        source_hashes=HASHES, geometry='original PCE pixel positions',
        source_palette_to_genesis=target, pen_maps=mappings, palettes=palettes,
        exact_color_pixels=exact, opaque_pixels=opaque,
        protected_source_palettes=[4,5,9,10]), indent=2)+'\n')
    return packed, attrs, palette, list(range(63))+[4095]*193


def vivid_palette(palette):
    from vivid_palette import base_lut, guard, index, light, rgb
    from itertools import combinations
    edges = []
    for offset in (0,16):
        colors = sorted(set(palette[offset+1:offset+16]), key=light)
        for a,b in combinations(colors,2):
            if all(x<=y for x,y in zip(rgb(a),rgb(b))):
                edges.append((a,b,min(200,light(b)-light(a))))
    lut = guard(base_lut(),edges)
    return [lut[index(c)] for c in palette]
