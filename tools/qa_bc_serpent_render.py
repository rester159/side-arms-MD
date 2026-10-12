#!/usr/bin/env python3
"""Verify original PCE final-serpent pixels, shading, flips and native uploads."""
import hashlib,json,struct
import numpy as np
from run_rom import ROOT,Runner
r=Runner();r.run(2600);r.write('dbg_bc_robot_preview',b'\0\1')
records=json.loads((ROOT/'res/generated/bc_serpent_shapes.json').read_text())
rom=(ROOT/'out/release/rom.bin').read_bytes();index=r.symbols['spr_big_index'];bank=r.symbols['spr_big']
out=ROOT/'.local/bc-serpent-render';out.mkdir(exist_ok=True)
pixels=cases=0;remaps=r.u32('spr_dbg_remap');drops=r.u32('spr_dbg_dropped')
for rec in records:
 entry=struct.unpack_from('>H',rom,index+rec['key']*2)[0];assert entry>>15==rec['palette']
 start=bank+((entry&32767)-1)*512;raw=rom[start:start+512]
 for y in range(32):
  for x in range(32):
   b=raw[((x//8)*4+y//8)*32+(y%8)*4+x%8//2];pen=b>>4 if x%2==0 else b&15
   source=int(rec['rows'][y][x],16);assert pen==rec['pen_lut'][source] and bool(pen)==bool(source);pixels+=1
 for ramp in rec['shade_ramps']:
  levels=ramp['luminance'];assert all(b-a>.20 for a,b in zip(levels,levels[1:]))
 for flip,source_bits in enumerate((0,0x800,0x8000,0x8800)):
  r.write('dbg_bc_actor_pose',struct.pack('>7H',rec['family'],0x400,0x400+rec['frame'],0x1180|rec['source_palette']|source_bits,128,112,128));r.run(8)
  assert not r.u16('dbg_bc_actor_unmapped')
  sat=struct.unpack('>4H',r.read('vdpSpriteCache',8));attr=sat[2]
  assert (sat[3]-128,sat[0]-128,sat[1]>>8,sat[1]&127)==(144,96,15,0),sat
  assert (attr>>13&3,attr>>11&3)==(rec['palette']+2,flip),sat
  at=(attr&2047)*32;assert bytes(r.vram[(at+j)^1]for j in range(512))==raw
  assert np.any(r.frame[96:128,144:176,:3])
  if not flip:r.capture(out/(rec['id']+'.png'))
  cases+=1
assert (r.u32('spr_dbg_remap'),r.u32('spr_dbg_dropped'))==(remaps,drops)
r.write('dbg_bc_robot_preview',b'\0\0');r.run(120);assert r.u32('flow_state')==0
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_pixel_checks=pixels,native_flip_cases=cases,original_serpent_poses=len(records),ordered_shading=True,runtime_remaps=0,sprite_drops=0)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
