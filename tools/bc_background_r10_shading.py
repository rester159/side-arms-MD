"""Preserve both original Normal final-chamber source palettes exactly."""
import json
import struct
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from bc_background_r6 import reuse_pen_order
import zones


def materials(selected_metas):
    src = Source()
    main = src.region('maincpu')
    bg = decode_bgtiles(src.region('bgtiles'))
    codes, colors, _ = bgmap_cells(src.region('bgmap'))
    x, y, w, h = zones.ZONES[21]['rect']
    metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                    for r in range(y, y+h) for c in range(x, x+w)})
    used = {meta*16+k for meta in selected_metas for k in range(16)}
    banks = (23, 24)
    normal = np.frombuffer((ROOT/'res/generated/zone21_tiles.bin').read_bytes(), np.uint8).reshape(-1, 8, 4)
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
    (gen/'bc_r10_material_tiles.bin').write_bytes(packed)
    (gen/'bc_r10_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H', *attrs))
    (gen/'bc_r10_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r10_material_shading.json').write_text(json.dumps(dict(
        schema=1, normal_zone=21, source_palette_banks=list(banks),
        all_source_rgb3_shades_exact=True, source_pen_luts=orders,
        characters=records), indent=2)+'\n')
    return packed, attrs, palette
