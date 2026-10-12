"""Compose the BC foundry from corresponding Normal art and exact source shades.

BC-specific structures use original BC geometry and exact source colors. Offline
per-character palette packing preserves every shade and opaque black.
"""
import json
import struct
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from bc_background_r6 import reuse_pen_order
import zones


def materials(definition):
    assert definition['normal_zone'] == 14 and definition['source_palette'] == 17
    src = Source()
    main = src.region('maincpu')
    bg = decode_bgtiles(src.region('bgtiles'))
    codes, colors, _ = bgmap_cells(src.region('bgmap'))
    x, y, w, h = zones.ZONES[14]['rect']
    metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                    for r in range(y, y+h) for c in range(x, x+w)})
    used = {d['meta']*16+d['subtile'] for row in definition['cells'] for d in row['characters']}
    normal = np.frombuffer((ROOT/'res/generated/zone14_tiles.bin').read_bytes(), np.uint8).reshape(-1, 8, 4)
    normal = np.stack((normal >> 4, normal & 15), -1).reshape(-1, 8, 8)
    counts = np.zeros((15, 16), dtype=np.int64)
    for n in sorted(used):
        cd, col = metas[n//16]
        k = n % 16
        pens = bg[cd, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
        assert col == 17 or np.all(pens == 15), (n, col)
        for pen in range(15):
            counts[pen] += np.bincount(normal[n][pens == pen], minlength=16)
    lut = reuse_pen_order(counts)
    palette = [0]*32
    for pen in range(15):
        offset = 17*16+pen
        palette[lut[pen]] = md_word(to_md(tuple(v//17 for v in
            palette_rgb(main[0x14a37+offset], main[0x14e37+offset]))))
    packed, attrs = bytearray(), []
    for meta, (cd, col) in enumerate(metas):
        for k in range(16):
            pens = bg[cd, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
            px = np.array(lut, np.uint8)[pens] if meta*16+k in used else np.zeros((8, 8), np.uint8)
            packed.extend(((px[:, ::2] << 4) | px[:, 1::2]).tobytes())
            attrs.append(0x8000 | k if px.any() else 0)
    gen = ROOT/'res/generated'
    (gen/'bc_r7_material_tiles.bin').write_bytes(packed)
    (gen/'bc_r7_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H', *attrs))
    (gen/'bc_r7_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r7_material_shading.json').write_text(json.dumps(dict(
        schema=1, normal_zone=14, source_palette=17, source_pen_lut=lut,
        all_retained_source_rgb3_shades_exact=True), indent=2)+'\n')
    return packed, attrs, palette, lut


def compose(tiles, definition, lut, palette):
    raw = np.frombuffer(tiles, np.uint8).reshape(-1, 8, 4)
    chars = np.stack((raw >> 4, raw & 15), -1).reshape(-1, 8, 8)
    packed, templates, remap = bytearray(), [], [4095]*256
    pending = []
    banks = [[tuple(c) for c in bank] for bank in definition["output_palette_banks_rgb3"]]
    bank_words = [{md_word(c) for c in bank} for bank in banks]
    counts = [np.zeros((15, 16), dtype=np.int64) for bank in banks]
    adjustments = {tuple(a): tuple(b) for a, b in definition["new_bc_art"].get("color_adjustments", [])}
    for meta, row in enumerate(definition['cells']):
        assert remap[row['cell']] == 4095
        remap[row['cell']] = meta
        image = np.zeros((32, 32), np.uint8)
        for k, donor in enumerate(row['characters']):
            px = chars[donor['meta']*16+donor['subtile']].copy()
            px[np.isin(px, [lut[p] for p in donor.get('clear_pens', [])])] = 0
            if donor['flip'] & 1:
                px = px[:, ::-1]
            if donor['flip'] & 2:
                px = px[::-1]
            image[k//4*8:k//4*8+8, k%4*8:k%4*8+8] = px
        for q, bounds in enumerate(row['quadrant_bounds']):
            if bounds is None:
                continue
            assert len(bounds) == 16
            for y, (lo, hi) in enumerate(bounds):
                assert (lo, hi) == (16, -1) or 0 <= lo <= hi < 16
                line = image[q//2*16+y, q%2*16:q%2*16+16]
                line[:lo] = 0
                line[hi+1:] = 0
        words = np.array(palette, np.uint16)[image]
        opaque = image != 0
        imported_quadrants = row.get('new_bc_quadrants', {})
        for q_text, pattern in imported_quadrants.items():
            q = int(q_text)
            pixels = np.array(definition['new_bc_art']['patterns'][pattern], np.uint8).reshape(16, 16)
            colors = [md_word(adjustments.get(tuple(c), tuple(c))) for c in definition['new_bc_art']['palette_rgb3']]
            region = np.s_[q//2*16:q//2*16+16, q%2*16:q%2*16+16]
            words[region] = np.array(colors, np.uint16)[pixels]
            opaque[region] = pixels != 0
        for k in range(16):
            region = np.s_[k//4*8:k//4*8+8, k%4*8:k%4*8+8]
            values, mask = words[region].copy(), opaque[region].copy()
            required = set(int(w) for w in values[mask])
            choices = [b for b, available in enumerate(bank_words) if required <= available]
            assert choices, (row['cell'], k, required, 'no exact character palette')
            bank = choices[0]
            preferred = image[region]
            if str(k//8*2+(k%4)//2) not in imported_quadrants:
                for index, color in enumerate(banks[bank]):
                    hit = mask & (values == md_word(color))
                    counts[bank][index] += np.bincount(preferred[hit], minlength=16)
            pending.append((values, mask, bank, k))
    # Assign pen numbers without changing RGB or opacity, maximizing reuse of
    # existing donor bytes. Opaque black remains distinct from transparent pen 0.
    pen_maps = [reuse_pen_order(c) for c in counts]
    palette[:] = [0]*32
    encoders = []
    for b, colors in enumerate(banks):
        encoder = {}
        for i, color in enumerate(colors):
            pen = pen_maps[b][i]
            encoder[md_word(color)] = pen
            palette[b*16+pen] = md_word(color)
        encoders.append(encoder)
    for values, mask, bank, k in pending:
        px = np.zeros((8, 8), np.uint8)
        for value in set(int(w) for w in values[mask]):
            px[mask & (values == value)] = encoders[bank][value]
        packed.extend(((px[:, ::2] << 4) | px[:, 1::2]).tobytes())
        templates.append(0x8000 | (bank<<13) | k if mask.any() else 0)
    (ROOT/'res/generated/bc_r7_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    return packed, templates, remap
