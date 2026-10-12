#!/usr/bin/env python3
"""Verify linked pink/purple cavern material pixels and untouched source stage banks."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
from bc_background_equivalence import symbols,compare_round,rendered_cell
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt')
rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
d=json.loads((ROOT/'tools/data/bc_background_r5_materials.json').read_text())
code=rom[sy['bc_round5_code']:sy['bc_round5_code']+65536];assert hashlib.sha256(code).hexdigest()==d['source_code_sha256']
raw=(ROOT/'res/generated/bc_r5_material_tiles.bin').read_bytes();attrs=np.fromfile(ROOT/'res/generated/bc_r5_material_attr.bin','>u2');remap=struct.unpack_from('>256H',rom,sy['bc_bg5_remap']);count=0
for rec in d['cells']:
 cell=rec['cell'];assert list(code[0x6220+cell*8:0x6228+cell*8])==rec['source_descriptor']
 actual=rendered_cell(rom,sy,'bc_bg5',remap[cell])
 for k,donor in enumerate(rec['characters']):
  source=donor['meta']*16+donor['subtile'];data=raw[source*32:(source+1)*32];packed=np.frombuffer(data,np.uint8).reshape(8,4);pens=np.stack((packed>>4,packed&15),-1).reshape(8,8)
  if donor['flip']&1:pens=pens[:,::-1]
  if donor['flip']&2:pens=pens[::-1,:]
  for y in range(8):
   for x in range(8):
    expected=(int(pens[y,x]),int(attrs[source])&0xe000)if any(data)else None
    assert actual[(k//4*8+y)*32+k%4*8+x]==expected,(cell,k,x,y)
  count+=64
assert {r['cell']for r in d['cells']}=={i for i,e in enumerate(remap)if e!=4095}
assert rom[sy['bc_bg5_palette']:sy['bc_bg5_palette']+64]==(ROOT/'res/generated/bc_r5_material_pal.bin').read_bytes()
for n in range(1,11):
 name=f'bc_round{n}_code';assert old[os[name]:os[name]+65536]==rom[sy[name]:sy[name]+65536]
other=[compare_round(old,os,rom,sy,n)for n in range(1,11)if n!=5];normal=0
for path in (ROOT/'res/generated').glob('zone*.bin'):
 if path.stem not in sy or path.stem not in os:continue
 data=path.read_bytes();assert rom[sy[path.stem]:sy[path.stem]+len(data)]==old[os[path.stem]:os[path.stem]+len(data)]==data;normal+=1
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_cells=len(d['cells']),pixel_checks=count,material_palette_words=32,source_banks_unchanged=10,other_round_cells_unchanged=sum(r['cells']for r in other),normal_blobs_unchanged=normal,normal_zone=10,primary_material_cells=73,defensive_margin_cells=0,full_speed_verified=False)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
