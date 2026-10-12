"""Compose BC chambers from whole Normal characters, retaining palette banks."""

def compose(tiles, attrs, definition):
    packed = bytearray()
    templates = []
    cells = {row['cell']: row for row in definition['cells']}
    for cell in range(49):
        for ty in range(4):
            for tx in range(4):
                pattern = cells[cell]['patterns'][ty // 2 * 2 + tx // 2]
                donor = definition['patterns'][f'{pattern:02x}'][ty % 2 * 2 + tx % 2]
                if donor is None:
                    packed.extend(bytes(32))
                    templates.append(0)
                    continue
                source = donor['normal_meta'] * 16 + donor['subtile']
                raw = tiles[source * 32:(source + 1) * 32]
                if donor['flip'] & 1:
                    raw = bytes((raw[y * 4 + 3 - x] & 15) << 4 |
                                raw[y * 4 + 3 - x] >> 4
                                for y in range(8) for x in range(4))
                if donor['flip'] & 2:
                    raw = b''.join(raw[y * 4:(y + 1) * 4] for y in range(7, -1, -1))
                packed.extend(raw)
                templates.append((attrs[source] & 0xe000) | ty * 4 + tx if attrs[source] else 0)
    return packed, templates, list(range(49)) + [4095] * 207

def materials(definition):
    """Keep the selected Normal geometry and its pre-fit RGB3 material shades.

    Every selected quadrant uses source palette 16: fifteen opaque source pens
    fit in one hardware bank. Bijective numbering maximizes reuse without
    flattening two source shades into one converted Normal pen.
    """
    import json
    import struct
    import numpy as np
    from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
    from bc_background_r6 import reuse_pen_order
    from quantize import to_md, md_word
    import zones

    src = Source()
    main = src.region('maincpu')
    bg = decode_bgtiles(src.region('bgtiles'))
    codes, colors, _ = bgmap_cells(src.region('bgmap'))
    x, y, w, h = zones.ZONES[19]['rect']
    metas = sorted({(int(codes[r, c]), int(colors[r, c]))
                    for r in range(y, y+h) for c in range(x, x+w)})
    used = {d['normal_meta']*16+d['subtile'] for parts in definition['patterns'].values() for d in parts if d is not None}
    gen = ROOT/'res/generated'
    normal = np.frombuffer((gen/'zone19_tiles.bin').read_bytes(), np.uint8).reshape(-1, 8, 4)
    normal = np.stack((normal >> 4, normal & 15), -1).reshape(-1, 8, 8)
    counts = np.zeros((15, 16), dtype=np.int64)
    for n in sorted(used):
        cd, col = metas[n//16]
        assert col == 16
        k = n % 16
        pens = bg[cd, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
        for pen in range(15):
            counts[pen] += np.bincount(normal[n][pens == pen], minlength=16)
    lut = reuse_pen_order(counts)
    palette = [0]*32
    for pen in range(15):
        offset = 16*16+pen
        palette[lut[pen]] = md_word(to_md(tuple(v//17 for v in
            palette_rgb(main[0x14a37+offset], main[0x14e37+offset]))))
    packed, attrs = bytearray(), []
    for meta, (cd, col) in enumerate(metas):
        for k in range(16):
            pens = bg[cd, k//4*8:k//4*8+8, k%4*8:k%4*8+8]
            px = np.array(lut, np.uint8)[pens] if meta*16+k in used else np.zeros((8, 8), np.uint8)
            packed.extend(((px[:, ::2] << 4) | px[:, 1::2]).tobytes())
            attrs.append(0x8000 | k if px.any() else 0)
    (gen/'bc_r9_material_tiles.bin').write_bytes(packed)
    (gen/'bc_r9_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H', *attrs))
    (gen/'bc_r9_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r9_material_shading.json').write_text(json.dumps(dict(
        schema=1, normal_zone=19, source_palette=16, source_pen_lut=lut,
        all_source_rgb3_shades_exact=True), indent=2)+'\n')
    return packed, attrs, palette
