"""Convert BC-specific effects/pickup shapes without altering Normal sprite data."""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades
ROOT=Path(__file__).resolve().parents[1]

def append_shapes(bank,index,keys,selectors,records,palettes):
    for shape in json.loads((ROOT/'tools/data/bc_unique_shapes.json').read_text())['shapes']:
        pixels=np.array([[int(v,16) for v in row] for row in shape['rows']])
        original=np.array(shape['colors'][1:]);weights=np.bincount(pixels.ravel(),minlength=16)[1:]
        groups={0x36c8:[[1,2,3,6]],0x36b4:[[0,1,2],[3,4,5]],0x367a:[[0,1,5],[2,3,5]]}[shape['family']]
        choices=[fit_shades(original,original,weights,p,groups)for p in palettes]
        selection=min(range(2),key=lambda i:choices[i][0]);_,mapping,ramps=choices[selection];lut=[0]+[p+1 for p in mapping]
        p=np.array(lut)[pixels]
        packed=bytes((int(p[ty*8+y,tx*8+x])<<4)|int(p[ty*8+y,tx*8+x+1])for tx in range(2)for ty in range(2)for y in range(8)for x in range(0,8,2))
        key=next((code|(c<<11)for code in range(0x128,0x130)for c in range(15,-1,-1)if not index[code|(c<<11)]),None)
        assert key is not None
        bank.extend(packed);index[key]=(len(bank)//128)|(selection<<15);keys.append(key)
        selector=(shape['family'],shape['source_palette'],shape['frame']);assert selector not in selectors;selectors[selector]=key
        records.append(dict(**shape,geometry_source='bc_unique_shapes',provenance='inferred',code=key&2047,normal_colour=0,bc_colour=key>>11,palette=selection,key=key,pen_lut=lut,shade_ramps=ramps))
