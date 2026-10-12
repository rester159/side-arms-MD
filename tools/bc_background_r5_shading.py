"""Repack reused Normal-zone-10 geometry with its original source shade ramps.

Fit only characters used by BC R5. Its scene has no starfield, so unused star
colors and unrelated Normal machinery need not displace visible material shades.
This is offline conversion; no runtime palette fitting or pixel conversion.
"""
import json,struct
import numpy as np
from arcade_source import ROOT,Source,decode_bgtiles,bgmap_cells,palette_rgb
from quantize import to_md,nearest,md_word
from bc_palette_fit import fit
import zones

def materials(definition, gold_pens=(2,4,6), blue_pens=(7,8), weight_power=0.7):
    src=Source();main=src.region('maincpu')
    colors=[to_md(tuple(c//17 for c in palette_rgb(main[0x14a37+i],main[0x14e37+i]))) for i in range(1024)]
    bg=decode_bgtiles(src.region('bgtiles'));codes,cols,_=bgmap_cells(src.region('bgmap'))
    x,y,w,h=zones.ZONES[10]['rect']
    metas=sorted({(codes[r,c],cols[r,c]) for r in range(y,y+h) for c in range(x,x+w)})
    used={d['meta']*16+d['subtile'] for row in definition['cells'] for d in row['characters']}
    fixed=[list(dict.fromkeys([(0,0,0)]+[colors[11*16+i] for i in (0,1,2,3,4,5,6,8,9,10,11,14)]+[colors[21*16+i] for i in blue_pens])),
           list(dict.fromkeys([colors[10*16+i] for i in (0,1,2,3,4,5,6,14)]+[colors[3*16+i] for i in gold_pens]))]
    blocks=[];pinned=[]
    for meta,(code,col) in enumerate(metas):
        for y in range(4):
            for x in range(4):
                hist={}
                for pen,n in zip(*np.unique(bg[code,y*8:y*8+8,x*8:x*8+8],return_counts=True)):
                    if pen!=15:
                        c=colors[int(col)*16+int(pen)];hist[c]=hist.get(c,0)+int(n)
                active=meta*16+y*4+x in used
                blocks.append(hist if active else {})
                pinned.append((1 if int(col)==10 else 0 if int(col) in (11,21) else -1) if active else -1)
    pals,assign=fit(blocks,2,15,fixed=fixed,pinned=pinned,weight_power=weight_power)
    tiles=bytearray();attrs=[];records=[]
    for meta,(code,col) in enumerate(metas):
        for y in range(4):
            for x in range(4):
                k=y*4+x;bank=int(assign[meta*16+k])
                lut=[0 if pen==15 else 1+nearest(colors[int(col)*16+pen],pals[bank]) for pen in range(16)]
                if int(col)==21 and meta*16+k in used:
                    # Keep all five dark-to-light blue steps. The weighted
                    # nearest fit merges source (0,0,3) into the darkest step.
                    # Existing (0,1,3) costs one green level instead, preserving
                    # the intermediate shade without changing any palette or
                    # another material's colors.
                    blue_step=next(i+1 for i,c in enumerate(pals[bank]) if tuple(c)==(0,1,3))
                    for pen in (12,13):
                        assert colors[21*16+pen]==(0,0,3)
                        lut[pen]=blue_step
                pens=bg[code,y*8:y*8+8,x*8:x*8+8];px=np.array(lut,np.uint8)[pens]
                tiles.extend(((px[:,::2]<<4)|px[:,1::2]).tobytes())
                attrs.append(0x8000|(bank<<13)|k if px.any() else 0)
                if meta*16+k in used:records.append(dict(meta=meta,subtile=k,code=int(code),source_palette=int(col),palette=bank,pen_lut=lut,source_pens=list(map(int,np.unique(pens)))))
    palette=[v for bank in pals for v in [0]+[md_word(c) for c in bank]+[0]*(15-len(bank))]
    gen=ROOT/'res/generated'
    (gen/'bc_r5_material_tiles.bin').write_bytes(tiles)
    (gen/'bc_r5_material_attr.bin').write_bytes(struct.pack('>'+str(len(attrs))+'H',*attrs))
    (gen/'bc_r5_material_pal.bin').write_bytes(struct.pack('>32H',*palette))
    (gen/'bc_r5_material_shading.json').write_text(json.dumps(dict(schema=1,normal_zone=10,protected_ramps=fixed,palettes=pals,characters=records,shade_adjustments=[dict(source_palette=21,source_pens=[12,13],source_rgb3=[0,0,3],output_rgb3=[0,1,3],reason='Preserve all five blue shade steps with a one-green-level approximation; all other materials unchanged.')]),indent=2)+'\n')
    return tiles,attrs,palette


def water_masks(definition):
    """Water ownership from the donor palette, excluding the surface gradient."""
    meta = json.loads((ROOT/'res/generated/bc_r5_material_shading.json').read_text())
    records = {(r['meta'], r['subtile']): r for r in meta['characters']}
    bg = decode_bgtiles(Source().region('bgtiles'))
    masks = []
    for row in definition['cells']:
        cell = np.zeros((32, 32), bool)
        for k, donor in enumerate(row['characters']):
            rec = records[donor['meta'], donor['subtile']]
            q = donor['subtile']
            pens = bg[rec['code'], q//4*8:q//4*8+8, q%4*8:q%4*8+8]
            if donor['flip'] & 1: pens = pens[:, ::-1]
            if donor['flip'] & 2: pens = pens[::-1]
            if rec['source_palette'] == 11:
                cell[k//4*8:k//4*8+8, k%4*8:k%4*8+8] = np.isin(pens, [0,8,9,10,11])
        masks.append(cell)
    return masks


def normalize_water(packed, templates, definition):
    """Keep embedded water in world phase after donor characters are flipped.

    Cell $43 is the uninterrupted 16-pixel water repeat. All map cells are
    32-pixel aligned, so this correction is entirely offline. Rock pixels,
    the shoreline gradient, palettes and source collision remain untouched.
    """
    cells = []
    for c in range(len(definition['cells'])):
        cell = np.zeros((32,32), np.uint8)
        for k in range(16):
            raw = np.frombuffer(packed[(c*16+k)*32:(c*16+k+1)*32], np.uint8).reshape(8,4)
            px = np.stack((raw>>4, raw&15), -1).reshape(8,8)
            assert not templates[c*16+k] & 0x1800
            cell[k//4*8:k//4*8+8, k%4*8:k%4*8+8] = px
        cells.append(cell)
    texture = np.tile(cells[0x43][:16,:16], (2,2))
    assert np.array_equal(texture, cells[0x43])
    for c, mask in enumerate(water_masks(definition)):
        cells[c][mask] = texture[mask]
        for k in range(16):
            if mask[k//4*8:k//4*8+8,k%4*8:k%4*8+8].any():
                assert templates[c*16+k] & 0x2000 == 0
            px = cells[c][k//4*8:k//4*8+8,k%4*8:k%4*8+8]
            packed[(c*16+k)*32:(c*16+k+1)*32] = ((px[:,::2]<<4)|px[:,1::2]).tobytes()
    return packed
