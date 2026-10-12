"""Replace the BC final-serpent adaptations with original PCE geometry."""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades
ROOT=Path(__file__).resolve().parents[1]
def append_shapes(big,index,selectors,palettes):
 records=[]
 for shape in json.loads((ROOT/'tools/data/bc_serpent_shapes.json').read_text())['shapes']:
  pixels=np.array([[int(v,16)for v in row]for row in shape['rows']])
  colors=np.array(shape['colors'][1:]);weights=np.bincount(pixels.ravel(),minlength=16)[1:]
  opts=[fit_shades(colors,colors,weights,p,[[0,1,2,5],[3,4]])for p in palettes]
  selected=min(range(2),key=lambda i:opts[i][0]);_,mapping,ramps=opts[selected]
  lut=[0]+[v+1 for v in mapping];p=np.array(lut)[pixels]
  packed=bytes(int(p[ty*8+y,tx*8+x])<<4|int(p[ty*8+y,tx*8+x+1])for tx in range(4)for ty in range(4)for y in range(8)for x in range(0,8,2))
  code=(0x630,0x632,0x634,0x636,0x600)[shape['frame']//8]+((shape['family']-0x36d0)//2)*0x40
  key=next(code|(c<<11)for c in range(15,-1,-1)if not index[code|(c<<11)])
  big.extend(packed);index[key]=(len(big)//512)|(selected<<15)
  selectors[(shape['family'],shape['source_palette'],shape['frame'])]=key
  records.append(dict(**shape,key=key,palette=selected,pen_lut=lut,shade_ramps=ramps,geometry_source='original_pce_final_serpent'))
 (ROOT/'res/generated/bc_serpent_shapes.json').write_text(json.dumps(records,indent=2)+'\n')
