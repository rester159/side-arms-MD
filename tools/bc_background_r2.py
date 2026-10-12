"""R2 source-shade recovery, retaining all 15 opaque colors of palettes 2/3.

BC cave and small-machine geometry uses Normal material ramps and one additional
dark-blue step. Corresponding Normal lamp/cap/rail assemblies retain source shades.
"""
import json, struct
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from bc_background_r6 import reuse_pen_order
import zones


def materials(definition):
    assert definition['normal_zone'] == 1
    src = Source()
    main = src.region('maincpu')
    bg = decode_bgtiles(src.region('bgtiles'))
    codes, colors, _ = bgmap_cells(src.region('bgmap'))
    x, y, w, h = zones.ZONES[1]['rect']
    metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                    for r in range(y, y+h) for c in range(x, x+w)})
    used = {d['meta']*16+d['subtile'] for row in definition['cells'] for d in row['characters']}
    banks = (2, 3)
    normal = np.frombuffer((ROOT/'res/generated/zone1_tiles.bin').read_bytes(), np.uint8).reshape(-1, 8, 4)
    normal = np.stack((normal >> 4, normal & 15), -1).reshape(-1, 8, 8)
    orders = {}
    for col in banks:
        counts = np.zeros((15, 16), dtype=np.int64)
        for n in sorted(used):
            code, source_col = metas[n//16]
            if source_col != col:
                continue
            k = n % 16
            source = bg[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
            for pen in range(15):
                counts[pen] += np.bincount(normal[n][source == pen], minlength=16)
        orders[col] = reuse_pen_order(counts)
    palette = []
    for col in banks:
        colors = [0]*16
        for pen in range(15):
            offset = col*16+pen
            colors[orders[col][pen]] = md_word(to_md(tuple(v//17 for v in
                palette_rgb(main[0x14a37+offset], main[0x14e37+offset]))))
        palette.extend(colors)
    cave = definition.get('bc_cave_art')
    if cave:
        for pen, color in cave.get('normal_pen_color_overrides', {}).items():
            palette[orders[2][int(pen)]] = md_word(tuple(color))
    packed, attrs, records = bytearray(), [], []
    for meta, (code, col) in enumerate(metas):
        for k in range(16):
            active = meta*16+k in used
            pens = bg[code, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
            assert not active or col in banks or np.all(pens == 15), (meta, k, col)
            bank = banks.index(col) if col in banks else 0
            px = np.array(orders.get(col, [0]*16), np.uint8)[pens]
            if not active:
                px[:] = 0
            packed.extend(((px[:, ::2] << 4) | px[:, 1::2]).tobytes())
            attrs.append(0x8000 | bank << 13 | k if px.any() else 0)
            if active:
                records.append(dict(meta=meta, subtile=k, code=code,
                                    source_palette=col, palette=bank))
    gen = ROOT/'res/generated'
    (gen/'bc_r2_material_tiles.bin').write_bytes(packed)
    (gen/'bc_r2_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H', *attrs))
    (gen/'bc_r2_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r2_material_shading.json').write_text(json.dumps(dict(
        schema=1, normal_zone=1, source_palette_banks=list(banks),
        all_retained_normal_rgb3_shades_exact=True, source_pen_luts=orders,
        shade_ramps=([dict(id='rock', colors=[palette[orders[2][p]] for p in (6,7,8,9,5,10,11)]),
                      dict(id='background', colors=[palette[orders[2][p]] for p in (13,1,2,3,4,12)])] if cave else []),
        characters=records), indent=2)+'\n')
    return packed, attrs, palette, orders


def compose(tiles, attrs, definition, orders):
    from bc_background_r3 import compose as compose_donors
    packed, templates, remap = compose_donors(tiles, attrs, definition, cell_count=89)
    art = definition.get('bc_cave_art')
    if not art:
        return packed, templates, remap
    for row in definition['cells']:
        for q_text, pattern in row.get('bc_cave_quadrants', {}).items():
            q = int(q_text)
            pens = np.array([int(p,16) for p in art['patterns'][pattern]], np.uint8).reshape(16,16)
            bank = pattern.split('/')[0]
            normal_bank = art.get('source_normal_palettes', {}).get(bank, 2)
            lut = np.array([orders[normal_bank][p] for p in art['source_pen_to_normal_pen'][bank]], np.uint8)
            pixels = lut[pens]
            for y in range(2):
                for x in range(2):
                    k = (q//2*2+y)*4+q%2*2+x
                    px = pixels[y*8:y*8+8,x*8:x*8+8]
                    start = (row['cell']*16+k)*32
                    packed[start:start+32] = ((px[:,::2]<<4)|px[:,1::2]).tobytes()
                    templates[row['cell']*16+k] = 0x8000|((normal_bank-2)<<13)|k if px.any() else 0
    return packed, templates, remap
