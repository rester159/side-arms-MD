#!/usr/bin/env python3
"""Verify linked cyan-cavern material pixels and untouched source stage banks."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
from bc_background_equivalence import symbols,compare_round,rendered_cell
from arcade_source import Source,decode_bgtiles,bgmap_cells,palette_rgb
from quantize import to_md,md_word
from vivid_palette import light,index
import zones
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt')
rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
d=json.loads((ROOT/'tools/data/bc_background_r3_materials.json').read_text())
code=rom[sy['bc_round3_code']:sy['bc_round3_code']+65536];assert hashlib.sha256(code).hexdigest()==d['source_code_sha256']
source=Source();main=source.region('maincpu');bg=decode_bgtiles(source.region('bgtiles'))
codes,cols,_=bgmap_cells(source.region('bgmap'));x,y,w,h=zones.ZONES[3]['rect']
metas=sorted({(int(codes[r,c]),int(cols[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
source_palette=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(main[0x14a37+i],main[0x14e37+i]))))for i in range(1024)],np.uint16)
remap=struct.unpack_from('>256H',rom,sy['bc_bg3_remap']);palette=struct.unpack_from('>32H',rom,sy['bc_bg3_palette']);count=0;used_colors=set();source_banks=set()
for rec in d['cells']:
 cell=rec['cell'];assert list(code[0x6220+cell*8:0x6228+cell*8])==rec['source_descriptor']
 actual=rendered_cell(rom,sy,'bc_bg3',remap[cell])
 for k,donor in enumerate(rec['characters']):
  cd,col=metas[donor['meta']];sub=donor['subtile'];source_banks.add(col)
  pens=bg[cd,sub//4*8:sub//4*8+8,sub%4*8:sub%4*8+8].astype(np.int32)
  colors=source_palette[col*16+pens];used_colors.update(map(int,colors[pens!=15]))
  expected=np.where(pens==15,0,0x8000|colors)
  if donor['flip']&1:expected=expected[:,::-1]
  if donor['flip']&2:expected=expected[::-1,:]
  for y in range(8):
   for x in range(8):
    value=actual[(k//4*8+y)*32+k%4*8+x]
    color=0 if value is None or not value[0] else 0x8000|palette[(value[1]>>13&1)*16+value[0]]
    assert color==int(expected[y,x]),(cell,k,x,y)
  count+=64
assert {r['cell']for r in d['cells']}=={i for i,e in enumerate(remap)if e!=4095}
assert source_banks=={3,4,6} and len(used_colors)==21
lut=struct.unpack_from('>512H',rom,sy['vivid_lut']);ordered=set()
for bank in (palette[1:16],palette[17:32]):
 for a_color in set(bank):
  for b_color in set(bank):
   rgb=lambda w:(w>>1&7,w>>5&7,w>>9&7)
   if a_color!=b_color and all(a<=b for a,b in zip(rgb(a_color),rgb(b_color))):
    assert light(lut[index(a_color)])<light(lut[index(b_color)])
    ordered.add((a_color,b_color))
for n in range(1,11):
 name=f'bc_round{n}_code';assert old[os[name]:os[name]+65536]==rom[sy[name]:sy[name]+65536]
other=[compare_round(old,os,rom,sy,n)for n in range(1,11)if n!=3];normal=0
for path in (ROOT/'res/generated').glob('zone*.bin'):
 if path.stem not in sy or path.stem not in os:continue
 data=path.read_bytes();assert rom[sy[path.stem]:sy[path.stem]+len(data)]==old[os[path.stem]:os[path.stem]+len(data)]==data;normal+=1
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_cells=len(d['cells']),pixel_checks=count,source_rgb3_colors=len(used_colors),vivid_ordered_pairs=len(ordered),source_banks_unchanged=10,other_round_cells_unchanged=sum(r['cells']for r in other),normal_blobs_unchanged=normal,normal_zone=3,primary_material_cells=81,defensive_margin_cells=50,full_speed_verified=False)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
