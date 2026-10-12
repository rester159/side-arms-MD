"""Exact source shades for the selected Normal cyan-cavern characters.

Source palette 4's used rock colors are a subset of palette 6. Thus palette 6
plus palette 3 cover every selected character in two banks without fitting.
"""
import json
import struct
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from bc_background_r6 import reuse_pen_order
from quantize import to_md, md_word
import zones


def materials(definition):
    src = Source()
    main = src.region('maincpu')
    bg = decode_bgtiles(src.region('bgtiles'))
    codes, colors, _ = bgmap_cells(src.region('bgmap'))
    x, y, w, h = zones.ZONES[3]['rect']
    metas = sorted({(int(codes[r,c]), int(colors[r,c]))
                    for r in range(y,y+h) for c in range(x,x+w)})
    used = {d['meta']*16+d['subtile'] for row in definition['cells'] for d in row['characters']}
    source_colors = np.array([md_word(to_md(tuple(v//17 for v in
        palette_rgb(main[0x14a37+i], main[0x14e37+i])))) for i in range(1024)], np.uint16)
    banks = [list(dict.fromkeys(map(int, source_colors[col*16:col*16+15]))) for col in (6,3)]
    assert all(len(bank)<=15 for bank in banks)
    gen = ROOT/'res/generated'
    normal = np.frombuffer((gen/'zone3_tiles.bin').read_bytes(), np.uint8).reshape(-1,8,4)
    normal = np.stack((normal>>4, normal&15), -1).reshape(-1,8,8)
    counts = [np.zeros((15,16), dtype=np.int64) for bank in banks]
    selected = {}
    for n in sorted(used):
        cd,col = metas[n//16];k=n%16
        pens = bg[cd,k//4*8:k//4*8+8,k%4*8:k%4*8+8].astype(np.int32)
        values = source_colors[col*16+pens];mask=pens!=15
        required = set(map(int, values[mask]))
        choices = [b for b,bank in enumerate(banks) if required<=set(bank)]
        assert choices, (n,col,required)
        bank = choices[0]
        selected[n] = (values,mask,bank)
        for i,color in enumerate(banks[bank]):
            counts[bank][i] += np.bincount(normal[n][mask & (values==color)], minlength=16)
    orders = [reuse_pen_order(count) for count in counts]
    palette = [0]*32
    for b,bank in enumerate(banks):
        for i,color in enumerate(bank):palette[b*16+orders[b][i]]=color
    packed,attrs = bytearray(),[]
    for n in range(len(metas)*16):
        px=np.zeros((8,8),np.uint8);bank=0
        if n in selected:
            values,mask,bank=selected[n]
            for i,color in enumerate(banks[bank]):px[mask & (values==color)]=orders[bank][i]
        packed.extend(((px[:,::2]<<4)|px[:,1::2]).tobytes())
        attrs.append(0x8000 | bank<<13 | n%16 if px.any() else 0)
    (gen/'bc_r3_material_tiles.bin').write_bytes(packed)
    (gen/'bc_r3_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H', *attrs))
    (gen/'bc_r3_material_pal.bin').write_bytes(struct.pack('>32H', *palette))
    (gen/'bc_r3_material_shading.json').write_text(json.dumps(dict(
        schema=1,normal_zone=3,source_palette_banks=[6,3],selected_characters=len(selected),
        all_source_rgb3_shades_exact=True),indent=2)+'\n')
    return packed,attrs,palette
