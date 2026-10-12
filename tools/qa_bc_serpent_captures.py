#!/usr/bin/env python3
"""Check the preserved final-serpent bank against independent live pose captures."""
import json,struct
from pathlib import Path
from qa_bc_factory import actor
ROOT=Path(__file__).resolve().parents[1]
records=json.loads((ROOT/'tools/data/bc_serpent_shapes.json').read_text())['shapes']
lookup={(r['family'],r['frame'],r['source_palette']):r for r in records}
uses=0;poses=set()
for name in ('round10-reference','round10-head','round10-protected','round10-ending-complete'):
 folder=ROOT/'.local/pce-reference'/name;code=(folder/'code-002160.bin').read_bytes()
 for path in sorted(folder.glob('*-ram.bin')):
  ram=path.read_bytes();v=struct.unpack('<32768H',path.with_name(path.name.replace('-ram','-vram')).read_bytes())
  for slot in range(32):
   a=actor(ram,slot,code);b=a.body
   if b.state!=128 or a.sprite_base_ref not in (0x36d0,0x36d2,0x36d4) or b.sprite in (0,255):continue
   key=(a.sprite_base_ref,b.sprite-b.sprite_base,b.attributes&15);rec=lookup[key];pattern=b.sprite>>1
   assert b.attributes&0x1100==0x1100
   rows=[''.join(format(sum(((v[(pattern+y//16*2+x//16)*64+y%16+c*16]>>(15-x%16))&1)<<c for c in range(4)),'x')for x in range(32))for y in range(32)]
   assert rows==rec['rows'],(name,path.name,slot,key)
   uses+=1;poses.add(key)
result=dict(verified_actor_uses=uses,live_pose_palette_combinations=len(poses),bank_pose_palette_combinations=len(records),unobserved_live_combinations=[list(k)for k in lookup if k not in poses],source_geometry_exact=True)
(ROOT/'.local/bc-serpent-render/captures.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
