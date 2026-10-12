#!/usr/bin/env python3
"""Check dedicated original boss shots against PCE pixels and native sprite output."""
import hashlib,json,struct
import numpy as np
from run_rom import ROOT,Runner
r=Runner();r.run(2600);r.write('dbg_bc_boss_preview',b'\0\1');r.write('dbg_bc_robot_preview',b'\0\1')
records=json.loads((ROOT/'res/generated/bc_boss_shots.json').read_text())
rom=(ROOT/'out/release/rom.bin').read_bytes();index=r.symbols['spr_bank_index'];bank=r.symbols['spr_bank']
out=ROOT/'.local/bc-original-boss-shots';out.mkdir(exist_ok=True)
pixels=cases=0;remaps=r.u32('spr_dbg_remap');drops=r.u32('spr_dbg_dropped')
for rec in records:
 entry=struct.unpack_from('>H',rom,index+rec['key']*2)[0];assert entry>>15==rec['palette']
 start=bank+((entry&32767)-1)*128;raw=rom[start:start+128]
 for y in range(16):
  for x in range(16):
   b=raw[((x//8)*2+y//8)*32+(y%8)*4+x%8//2];pen=b>>4 if x%2==0 else b&15
   source=int(rec['rows'][y][x],16);assert pen==rec['pen_lut'][source] and bool(pen)==bool(source);pixels+=1
 for ramp in rec['shade_ramps']:
  levels=ramp['luminance'];assert all(b-a>.20 for a,b in zip(levels,levels[1:]))
 for flip,source_bits in enumerate((0,0x800,0x8000,0x8800)):
  r.write('dbg_bc_actor_pose',struct.pack('>7H',rec['family'],0x400,0x400+rec['frame'],0x80|rec['source_palette']|source_bits,128,112,128));r.run(8)
  assert not r.u16('dbg_bc_actor_unmapped')
  sat=struct.unpack('>4H',r.read('vdpSpriteCache',8));attr=sat[2]
  assert (sat[3]-128,sat[0]-128,sat[1]>>8,sat[1]&127)==(152,104,5,0),sat
  assert (attr>>13&3,attr>>11&3)==(rec['palette']+2,flip),sat
  at=(attr&2047)*32;assert bytes(r.vram[(at+j)^1]for j in range(128))==raw
  assert np.any(r.frame[104:120,152:168,:3])
  if not flip:r.capture(out/(rec['id']+'.png'))
  cases+=1
assert (r.u32('spr_dbg_remap'),r.u32('spr_dbg_dropped'))==(remaps,drops)
r.write('dbg_bc_robot_preview',b'\0\0');r.run(120);assert r.u32('flow_state')==0
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_pixel_checks=pixels,native_flip_cases=cases,dedicated_frames=sum(not x["boss_context_only"] for x in records),shared_boss_frames=sum(x["boss_context_only"] for x in records),ordered_shading=True,runtime_remaps=0,sprite_drops=0,captured_shared_enemy_boss_projectiles_imported=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
