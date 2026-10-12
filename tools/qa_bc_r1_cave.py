#!/usr/bin/env python3
"""Verify linked R1 cave quadrant joins and isolation from an earlier ROM."""
import argparse,json,struct
from pathlib import Path
from bc_background_equivalence import symbols,rendered_cell,compare_round
from bc_background_r1_cave import CELLS
p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);a=p.parse_args()
rom=Path('out/release/rom.bin').read_bytes();sy=symbols(Path('out/release/symbol.txt'))
old=(a.before/'rom.bin').read_bytes();os=symbols(a.before/'symbol.txt')
remap=struct.unpack_from('>256H',rom,sy['bc_bg_remap']);previous=struct.unpack_from('>256H',old,os['bc_bg_remap'])
source=rom[sy['bc_round1_code']:sy['bc_round1_code']+65536]
seen={};checks=0
for cell,patterns in CELLS.items():
 pixels=rendered_cell(rom,sy,'bc_bg',remap[cell])
 for q,key in enumerate(patterns):
  at=0x6220+cell*8+q*2
  assert (source[at],source[at+1]>>4)==key,('source topology',cell,q)
  block=[pixels[(q//2*16+y)*32+q%2*16+x] for y in range(16) for x in range(16)]
  if key in seen:assert block==seen[key],('broken shared quadrant',cell,q,key)
  seen[key]=block;checks+=1
changed=[]
for cell,(x,y) in enumerate(zip(previous,remap)):
 if x==4095:assert y==4095;continue
 if rendered_cell(old,os,'bc_bg',x)!=rendered_cell(rom,sy,'bc_bg',y):
  assert cell in CELLS,('unrelated cell changed',cell);changed.append(cell)
for name,n in [('bc_round1_code',65536),('bc_bg_palette',64)]:assert old[os[name]:os[name]+n]==rom[sy[name]:sy[name]+n]
for n in range(2,11):compare_round(old,os,rom,sy,n)
print(json.dumps(dict(passed=True,quadrant_checks=checks,changed_cells=changed,other_rounds_unchanged=True,collision_banks_unchanged=True)))
