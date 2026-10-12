"""Import PCE boss-shot variants without changing regular enemy choices."""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades
ROOT=Path(__file__).resolve().parents[1]


def append_shapes(bank,index,keys,selectors,palettes):
    cache={}
    for key in keys:
        entry=int(index[key]);offset=((entry&32767)-1)*128
        cache.setdefault((entry>>15,bytes(bank[offset:offset+128])),key)
    records=[]; boss_selectors=[]
    for shape in json.loads((ROOT/'tools/data/bc_boss_shot_shapes.json').read_text())['shapes']:
        pixels=np.array([[int(v,16)for v in row]for row in shape['rows']])
        colors=np.array(shape['colors'][1:]);weights=np.bincount(pixels.ravel(),minlength=16)[1:]
        # Captured material ramps differ between homing shells and light shots.
        groups=([[0,1,2,5],[3,4]] if shape['family']==0x3682 else
                [[0,1,2,3,6],[4,5]])
        options=[fit_shades(colors,colors,weights,p,groups)for p in palettes]
        selected=min(range(2),key=lambda i:options[i][0]);_,mapping,ramps=options[selected]
        lut=[0]+[v+1 for v in mapping];p=np.array(lut)[pixels]
        packed=bytes(int(p[ty*8+y,tx*8+x])<<4|int(p[ty*8+y,tx*8+x+1])for tx in range(2)for ty in range(2)for y in range(8)for x in range(0,8,2))
        signature=(selected,packed)
        if signature in cache:key=cache[signature]
        else:
            key=next((code|(c<<11)for code in range(0x128,0x140)for c in range(15,-1,-1)if not index[code|(c<<11)]),None)
            assert key is not None
            bank.extend(packed);index[key]=(len(bank)//128)|(selected<<15);keys.append(key);cache[signature]=key
        selector=(shape['family'],shape['source_palette'],shape['frame'])
        previous=selectors.get(selector)
        if shape['boss_context_only']:boss_selectors.append((*selector,key))
        else:selectors[selector]=key
        records.append(dict(**shape,key=key,palette=selected,pen_lut=lut,shade_ramps=ramps,previous_key=previous,geometry_source='original_pce_boss_shot'))
    (ROOT/'res/generated/bc_boss_shots.json').write_text(json.dumps(records,indent=2)+'\n')
    lines=['/* Generated PCE variants for shared boss/enemy projectile families. */',
           '#pragma once',
           'static unsigned int bc_original_boss_shot(unsigned short family, unsigned short frame, unsigned short attributes, unsigned int pose)',
           '{', '    if (!(pose & 0x80000u)) return pose;']
    for family,palette,frame,key in boss_selectors:
        lines.append(f'    if (family == 0x{family:04x} && frame == {frame} && (attributes & 15) == {palette}) return (pose & ~0x7fffu) | 0x{key:04x}u;')
    lines+=['    return pose;', '}']
    (ROOT/'src/gen/bc_boss_shot_keys.h').write_text('\n'.join(lines)+'\n')
