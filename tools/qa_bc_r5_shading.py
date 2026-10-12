#!/usr/bin/env python3
"""Verify source geometry and protected original shades in the linked R5 art."""
from pathlib import Path
import argparse,hashlib,json,struct
from vivid_palette import light,index,word
import numpy as np
from arcade_source import ROOT,Source,decode_bgtiles,palette_rgb
from bc_background_equivalence import symbols,rendered_cell
from bc_background_r5_shading import water_masks
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'.local/bc-r5-shading-fix/shading.json');args=parser.parse_args()
s=Source();main=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'))
from quantize import to_md
source_rgb=[to_md(tuple(c//17 for c in palette_rgb(main[0x14a37+i],main[0x14e37+i]))) for i in range(1024)]
rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt');pal=struct.unpack_from('>32H',rom,sy['bc_bg5_palette']);colors=[(w>>1&7,w>>5&7,w>>9&7)for w in pal];remap=struct.unpack_from('>256H',rom,sy['bc_bg5_remap'])
recipe=json.loads((ROOT/'tools/data/bc_background_r5_materials.json').read_text());metadata=json.loads((ROOT/'res/generated/bc_r5_material_shading.json').read_text());records={(r['meta'],r['subtile']):r for r in metadata['characters']}
protected={10:{1,2,3,4,5,6,14},11:{0,1,2,3,4,5,6,8,9,10,11,14},21:{7,8,9,10,11,14}}
water=water_masks(recipe)
canonical=rendered_cell(rom,sy,'bc_bg5',remap[0x43])
water_checked=0
checked=opaque=ramps=blue_adjusted=0;blue_colors={};ramps_seen={10:set(),11:set()}
for cell in recipe['cells']:
 actual=rendered_cell(rom,sy,'bc_bg5',remap[cell['cell']])
 for k,d in enumerate(cell['characters']):
  r=records[d['meta'],d['subtile']];n=d['subtile'];pens=bg[r['code'],n//4*8:n//4*8+8,n%4*8:n%4*8+8]
  if d['flip']&1:pens=pens[:,::-1]
  if d['flip']&2:pens=pens[::-1,:]
  for y in range(8):
   for x in range(8):
    p=int(pens[y,x]);got=actual[(k//4*8+y)*32+k%4*8+x];pen=got[0]if got else 0
    assert bool(pen)==(p!=15),(cell['cell'],k,x,y,'source silhouette')
    checked+=1
    if p==15:continue
    opaque+=1;rgb=colors[(got[1]>>13&1)*16+pen]
    if water[cell['cell']][k//4*8+y,k%4*8+x]:
     target=canonical[((k//4*8+y)%16)*32+(k%4*8+x)%16]
     assert rgb==colors[(target[1]>>13&1)*16+target[0]]
     water_checked+=1
     continue
    expected=tuple(metadata['palettes'][r['palette']][r['pen_lut'][p]-1]);assert rgb==expected
    cl=r['source_palette']
    if cl==21 and p in (14,12,13,10,11,8,9,7):
     blue_colors[p]=rgb
     if p in (12,13):
      assert source_rgb[cl*16+p]==(0,0,3) and rgb==(0,1,3)
      blue_adjusted+=1
    if p in protected.get(cl,set()):
     assert rgb==source_rgb[cl*16+p],(cl,p,rgb,source_rgb[cl*16+p])
     ramps+=1
     if cl in ramps_seen and p in range(2,7):ramps_seen[cl].add(rgb)
assert all(len(v)==5 for v in ramps_seen.values()),ramps_seen
blue_ramp=[blue_colors[p]for p in (14,12,10,8,7)]
assert len(set(blue_ramp))==5 and blue_adjusted>0
lut=struct.unpack_from('>512H',rom,sy['vivid_lut'])
for a,b in zip(blue_ramp,blue_ramp[1:]):
 assert light(word(a))<light(word(b))
 assert light(lut[index(word(a))])<light(lut[index(word(b))])
r=dict(normalized_water_pixels=water_checked,blue_ramp_steps=5,blue_approximated_pixels=blue_adjusted,blue_intermediate_rgb3=[0,1,3],passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_geometry_pixels=checked,opaque_pixels=opaque,protected_shade_pixels=ramps,pink_ramp_steps=len(ramps_seen[10]),purple_ramp_steps=len(ramps_seen[11]),neutral_rock_highlight_exact=True,scope='R5 source geometry, actual packed palette conversion, protected rock/blue ramps. Other levels and unprotected material shades remain separate work.')
out=args.output;out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
