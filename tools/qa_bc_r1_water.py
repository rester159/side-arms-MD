#!/usr/bin/env python3
"""Check R1 rock-field water phase against the linked surrounding sea."""
import argparse,json,struct
from pathlib import Path
from bc_background_equivalence import symbols,rendered_cell,compare_round
p=argparse.ArgumentParser();p.add_argument('--before',type=Path,required=True);a=p.parse_args()
old=(a.before/'rom.bin').read_bytes();new=Path('out/release/rom.bin').read_bytes()
os=symbols(a.before/'symbol.txt');ns=symbols(Path('out/release/symbol.txt'))
op=struct.unpack_from('>32H',old,os['bc_bg_palette']);np=struct.unpack_from('>32H',new,ns['bc_bg_palette'])
om=struct.unpack_from('>256H',old,os['bc_bg_remap']);nm=struct.unpack_from('>256H',new,ns['bc_bg_remap'])
assert op==np

def colors(rom,sy,pal,rem,cell):
 return [pal[(p[1]>>13&1)*16+p[0]] if p and p[0] else 0 for p in rendered_cell(rom,sy,'bc_bg',rem[cell])]
checks=0;changed=[]
for cell,(a,b) in enumerate(zip(om,nm)):
 if a==4095:assert b==4095;continue
 before=colors(old,os,op,om,cell);after=colors(new,ns,np,nm,cell)
 if before!=after:changed.append(cell)
 if cell not in (0x13,0x14,0x15):assert before==after;continue
 sea=colors(new,ns,np,nm,2 if cell==0x15 else 1)
 assert [bool(c) for c in before]==[bool(c)for c in after]
 for i,c in enumerate(before):
  if c and not c&14 and c&0xe00:
   assert after[i]==sea[i],(cell,i,c,after[i],sea[i]);checks+=1
assert changed==[19,20,21]
for n in range(2,11):compare_round(old,os,new,ns,n)
name='bc_round1_code';assert old[os[name]:os[name]+65536]==new[ns[name]:ns[name]+65536]
print(json.dumps(dict(passed=True,matched_water_pixels=checks,changed_cells=changed,palettes_and_other_scenery_unchanged=True,collision_banks_unchanged=True)))
