#!/usr/bin/env python3
"""Verify every imported PCE boss body: source pixels, hardware poses and reprises."""
import argparse,hashlib,json,re,struct
import numpy as np
from run_rom import ROOT,Runner
from qa_bc_factory import actor

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--boss',type=int,choices=range(1,10));args=parser.parse_args()
meta=json.loads((ROOT/'res/generated/bc_boss_geometry.json').read_text())
attacks=json.loads((ROOT/'tools/data/bc_boss_attack_shapes.json').read_text())['attacks']
sources=json.loads((ROOT/'tools/data/bc_composite_source_shapes.json').read_text())['bosses']
rom=(ROOT/'out/release/rom.bin').read_bytes();r=Runner();r.run(2600)
out=ROOT/'.local/bc-all-original-bosses';out.mkdir(exist_ok=True)
shifts=[-0xdd7,0x7ef,0x527,0x4c4,0x153b,-0x586,0xec9,0xcaa,0]
reports=[];pixels=opaque=0
for bank,source in zip(meta['banks'],sources):
 n=bank['round'];assert n==source['round']
 if args.boss and n!=args.boss:continue
 name='bc_boss_patterns' if n==1 else f'bc_boss{n}_patterns';address=r.symbols[name]
 raw=rom[address:address+bank['block_count']*512]
 for pose in source['poses']+[a['pose']for a in attacks if a['round']==n]:
  p=next(p for p in bank['poses']if p['frame']==pose['frame'])
  expected=np.zeros((192,192),np.uint8);actual=expected.copy();lut=np.array(p['pen_lut'],np.uint8)
  for part in pose['pieces']:
   z=np.array([[int(v,16)for v in row]for row in part['rows']]);y,x=part['y']+96,part['x']+96
   dst=expected[y:y+16,x:x+16];dst[z!=0]=lut[z[z!=0]]
   assert all(lut[v] for v in np.unique(z)if v),'Opaque pixel lost'
  for piece in bank['pieces'][p['first']:p['first']+p['count']]:
   block=raw[piece['tile']*512:(piece['tile']+1)*512]
   for y in range(32):
    for x in range(32):
     b=block[((x//8)*4+y//8)*32+(y%8)*4+x%8//2];pen=b>>4 if x%2==0 else b&15
     xx=31-x if piece['flags']&1 else x;yy=31-y if piece['flags']&2 else y
     actual[piece['y']+96+yy,piece['x']+96+xx]=pen
  assert np.array_equal(expected,actual),(n,hex(p['frame']))
  for ramp in p['shade_ramps']:
   levels=ramp['luminance'];assert all(b-a>.20 for a,b in zip(levels,levels[1:]))
  pixels+=actual.size;opaque+=np.count_nonzero(actual)
 original=[]
 for source_round in ((n,9)if n!=9 else (9,)):
  r.write('dbg_bc_boss_preview',struct.pack('>H',n));r.write('dbg_bc_boss_source_round',struct.pack('>H',source_round))
  r.write('dbg_bc_actor_pose',bytes(224));r.write('dbg_bc_robot_preview',b'\0\1');r.run(12)
  slots=list(reversed([i for i,v in enumerate(r.read('slot_refs',56))if v==255]))
  assert len(slots)==bank['block_count'],(n,len(slots))
  for i,slot in enumerate(slots[:bank['block_count']]):
   at=(160+slot*16)*32;assert bytes(r.vram[(at+j)^1]for j in range(512))==raw[i*512:(i+1)*512]
  for j,p in enumerate(bank['poses']):
   frame=p['frame']+(shifts[n-1]if source_round==9 else 0)
   r.write('dbg_bc_actor_pose',struct.pack('>7H',p['family'],0,frame,0x88,152,112,128));r.run(4)
   assert not r.u16('dbg_bc_actor_unmapped'),(n,hex(frame))
   if p['count']:
    sat=struct.unpack('>'+str(p['count']*4)+'H',r.read('vdpSpriteCache',p['count']*8))
    pieces=bank['pieces'][p['first']:p['first']+p['count']]
    assert [(sat[i*4+3]-128,sat[i*4]-128,sat[i*4+2]>>13&3,sat[i*4+2]>>11&3,sat[i*4+2]&2047)for i in range(p['count'])]==[(184+q['x'],112+q['y'],p['palette']+2,q['flags'],160+slots[q['tile']]*16)for q in pieces],(n,hex(frame))
   if p['family']!=bank['family'] and source_round==n:r.capture(out/f'attack-{n}-{p["frame"]:04x}.png')
   if source_round==n:original.append(r.frame.copy())
   else:assert np.array_equal(original[j],r.frame),(n,'reprise')
  # Compose a native preview from the same live actor positions as the source capture.
  folder=ROOT/'.local/pce-reference'/source['capture'];stem=f'f{source["capture_frame"]:06d}'
  ram=(folder/f'{stem}-ram.bin').read_bytes();code=(folder/'code-002160.bin').read_bytes()
  r.write('dbg_bc_actor_pose',bytes(224));slot=0
  for i in range(32):
   a=actor(ram,i,code);b=a.body
   if not b.state or a.sprite_base_ref!=bank['family'] or not b.flags&8:continue
   assert slot<16
   frame=b.sprite+(shifts[n-1]if source_round==9 else 0)
   r.write('dbg_bc_actor_pose',struct.pack('>7H',bank['family'],0,frame,b.attributes,b.x>>8,b.y>>8,b.state),slot*14);slot+=1
  r.run(8);assert not r.u16('dbg_bc_actor_unmapped')
  r.capture(out/f'boss-{n}-source-round-{source_round}.png')
  r.write('dbg_bc_robot_preview',b'\0\0');r.run(40)
  assert 255 not in r.read('slot_refs',56)
 reports.append(dict(boss=n,blocks=bank['block_count'],poses=len(bank['poses']),source_geometry_exact=True))
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),rom_bytes=len(rom),compared_pixels=pixels,opaque_pixels=int(opaque),bosses=reports,composite_attack_poses_verified=sum(1 for a in attacks if not args.boss or a['round']==args.boss),ordinary_attack_verification="qa_bc_boss_shots.py and qa_bc_boss_attack_captures.py",final_serpent_verification="qa_bc_serpent_render.py and qa_bc_serpent_captures.py")
(out/(f'bodies-{args.boss}.json' if args.boss else 'bodies.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
