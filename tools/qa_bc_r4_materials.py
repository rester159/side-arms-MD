#!/usr/bin/env python3
"""Verify linked round-four colors/geometry, character flips and unchanged stages."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
from bc_background_equivalence import symbols,compare_round,rendered_cell
from bc_background_r4_shading import source_images,PRIMARY
from inspect_bc_background import cell_index
from vivid_palette import light,index
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt')
rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
palette=np.array(struct.unpack_from('>32H',rom,sy['bc_bg4_palette']),np.uint16)
expected=source_images();colors=[((int(c)>>1&7)*36,(int(c)>>5&7)*36,(int(c)>>9&7)*36)for c in palette]
remap=struct.unpack_from('>256H',rom,sy['bc_bg4_remap']);assert {i for i,v in enumerate(remap)if v!=4095}==set(PRIMARY)
checked=0
for cell in PRIMARY:
    pixels=rendered_cell(rom,sy,'bc_bg4',remap[cell])
    rgb=[(0,0,0)if v is None or v[0]==0 else colors[(v[1]>>13&1)*16+v[0]]for v in pixels]
    assert rgb==list(map(tuple,np.asarray(expected[cell]).reshape(-1,3))),cell
    assert set(rgb)<=set(colors)
    checked+=1024
# The three former filler IDs occur only in the extra left margin, never in
# the valid stage strip. The runtime now repeats valid source column 16 there.
code=rom[sy['bc_round4_code']:sy['bc_round4_code']+65536]
assert code[0x6218:0x621a]==bytes([2,3])
invalid={24,45,60};margin=[]
for y in range(768,1024,32):
 for x in range(480,2624,32):
  cell=code[0xc000+cell_index(x,y)]
  if cell in invalid:
   assert x==480,(cell,x,y)
   margin.append((cell,x,y))
  if x>=512:assert cell in PRIMARY,(cell,x,y)
assert {c for c,_,_ in margin}==invalid
lut=struct.unpack_from('>512H',rom,sy['vivid_lut']);ordered=set()
for bank in (palette[1:16],palette[17:32]):
 for a_color in map(int,set(bank)):
  for b_color in map(int,set(bank)):
   rgb=lambda w:(w>>1&7,w>>5&7,w>>9&7)
   if a_color!=b_color and all(a<=b for a,b in zip(rgb(a_color),rgb(b_color))):
    assert light(lut[index(a_color)])<light(lut[index(b_color)])
    ordered.add((a_color,b_color))
for n in range(1,11):
    name=f'bc_round{n}_code';assert old[os[name]:os[name]+65536]==rom[sy[name]:sy[name]+65536],name
other=[compare_round(old,os,rom,sy,n)for n in range(1,11)if n!=4]
normal=0
for path in (ROOT/'res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:continue
    data=path.read_bytes();assert rom[sy[path.stem]:sy[path.stem]+len(data)]==old[os[path.stem]:os[path.stem]+len(data)]==data,path.name;normal+=1
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_cells=len(PRIMARY),pixel_checks=checked,source_rgb3_colors=len(set(colors)-{(0,0,0)}),vivid_ordered_pairs=len(ordered),invalid_margin_cells=margin,source_banks_unchanged=10,other_round_cells_unchanged=sum(r['cells']for r in other),normal_blobs_unchanged=normal,normal_zone=6,full_speed_verified=False,adaptation='Corresponding Normal ledges and machinery; resize the isolated boulder and select whole machinery characters, preserving original pre-fit RGB3 shades; extend the first valid stage column into the extra left margin.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
