"""Pack missing BC beam geometry into spare sprite keys, preserving Normal data."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def append_shapes(bank,index,keys,selectors,records,palettes):
    shapes=json.loads((ROOT/'tools/data/bc_beam_shapes.json').read_text())['shapes']
    cache={}
    for shape in shapes:
        # Existing PAL3 colors: dark-to-light red/orange or blue/cyan/white.
        lut=[0]+([10,3,14,6,2] if shape['source_palette']==1 else [7,5,15,4,2])
        pixels=[[lut[int(v)] for v in row] for row in shape['rows']]
        assert len(pixels)==16 and all(len(row)==16 for row in pixels)
        packed=bytes((pixels[ty*8+y][tx*8+x]<<4)|pixels[ty*8+y][tx*8+x+1]
                     for tx in range(2) for ty in range(2) for y in range(8) for x in range(0,8,2))
        if packed in cache:key=cache[packed]
        else:
            key=next((code|(c<<11) for code in range(0x120,0x126) for c in range(15,-1,-1) if not index[code|(c<<11)]),None)
            assert key is not None,'No spare BC beam sprite key'
            bank.extend(packed);index[key]=(len(bank)//128)|32768;keys.append(key);cache[packed]=key
        selector=(shape['family'],shape['source_palette'],shape['frame'])
        assert selector not in selectors
        selectors[selector]=key
        light=[sum(a*b for a,b in zip(palettes[1][pen-1],(.299,.587,.114))) for pen in lut[1:]]
        assert all(b>a for a,b in zip(light,light[1:]))
        records.append(dict(**shape,geometry_source='bc_beam_shapes',provenance='inferred',code=key&2047,normal_colour=8,bc_colour=key>>11,palette=1,key=key,pen_lut=lut,shade_ramps=[dict(pens=[[i] for i in range(1,6)],luminance=light)]))
