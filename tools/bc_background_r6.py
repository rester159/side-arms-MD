"""R6 reuses Normal zone-13 characters with both original source palettes.

Only two source palettes are used, so all 15 opaque colors in each fit exactly.
Keep the original Genesis material hues and every RGB3 shade; no palette fitter
or runtime conversion is needed. PCE data describes placement, not pixels.
"""
import json
import struct
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
import zones


def reuse_pen_order(counts):
    """Bijective opaque-pen numbering maximizing byte reuse with Normal art.

    Assigning a different index does not change a color: its palette entry is
    moved with it. No two source shades may merge to save storage.
    """
    size = 1 << 15
    score = [-1]*size
    previous = [None]*size
    score[0] = 0
    for mask in range(size-1):
        source = mask.bit_count()
        for target in range(15):
            bit = 1 << target
            if mask & bit:
                continue
            after = mask | bit
            candidate = score[mask]+int(counts[source, target+1])
            if candidate > score[after]:
                score[after] = candidate
                previous[after] = (mask, target+1)
    result = [0]*16
    mask = size-1
    for source in range(14, -1, -1):
        mask, result[source] = previous[mask]
    assert sorted(result[:15]) == list(range(1, 16)) and result[15] == 0
    return result


def materials(definition):
    assert definition['normal_zone'] == 13
    src = Source()
    main = src.region('maincpu')
    bg = decode_bgtiles(src.region('bgtiles'))
    codes, colors, _ = bgmap_cells(src.region('bgmap'))
    x, y, w, h = zones.ZONES[13]['rect']
    metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                    for r in range(y, y+h) for c in range(x, x+w)})
    used = {d['meta']*16+d['subtile'] for row in definition['cells'] for d in row['characters']}
    banks = (7, 14)
    normal = np.frombuffer((ROOT/'res/generated/zone13_tiles.bin').read_bytes(), np.uint8).reshape(-1, 8, 4)
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
    (gen/'bc_r6_material_tiles.bin').write_bytes(packed)
    (gen/'bc_r6_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H', *attrs))
    (gen/'bc_r6_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r6_material_shading.json').write_text(json.dumps(dict(
        schema=1, normal_zone=13, source_palette_banks=list(banks),
        all_source_rgb3_shades_exact=True, source_pen_luts=orders,
        characters=records), indent=2)+'\n')
    return packed, attrs, palette
