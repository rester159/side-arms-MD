#!/usr/bin/env python3
"""Extract original composite boss attacks from live PCE actor/VRAM captures."""
import argparse,hashlib,json,struct
from pathlib import Path
from qa_bc_factory import actor
ROOT=Path(__file__).resolve().parents[1]
SOURCES=((4,'round4-defeat',7680,3,0x36c8,0xab1d),
         (5,'round5-defeat',11760,3,0x36ca,0xaf7d),
         (5,'round5-defeat',11520,3,0x36ca,0xaf97),
         (5,'round5-defeat',12480,3,0x36ca,0xafc9))
result=[]
for number,capture,frame,slot,family,pose in SOURCES:
 folder=ROOT/'.local/pce-reference'/capture;stem=f'f{frame:06d}'
 paths={kind:folder/f'{stem}-{kind}.bin'for kind in ('ram','vram','palette')};paths['code']=folder/'code-002160.bin'
 raw={k:p.read_bytes()for k,p in paths.items()};a=actor(raw['ram'],slot,raw['code']);b=a.body
 assert b.state==128 and a.sprite_base_ref==family and b.sprite==pose and b.flags&8
 vram=struct.unpack('<32768H',raw['vram']);palette=struct.unpack('<512H',raw['palette']);record=raw['code'][pose-0x4000:]
 pieces=[]
 for i in range(record[1]):
  y,x,off,flags=struct.unpack_from('bbBB',record,2+4*i);assert not flags&~0x88
  pattern=(b.sprite_base+off)>>1;rows=[]
  for py in range(16):
   sy=15-py if flags&128 else py;row=[]
   for px in range(16):
    sx=15-px if flags&8 else px
    row.append(sum(((vram[pattern*64+sy+c*16]>>(15-sx))&1)<<c for c in range(4)))
   rows.append(''.join(format(v,'x')for v in row))
  pieces.append(dict(x=x,y=y,pattern=pattern,flags=flags,rows=rows))
 x0=min(p['x']for p in pieces);y0=min(p['y']for p in pieces);w=max(p['x']+16 for p in pieces)-x0;h=max(p['y']+16 for p in pieces)-y0
 pal=b.attributes&15;colors=[[v>>3&7,v>>6&7,v&7]for v in palette[256+pal*16:272+pal*16]]
 result.append(dict(round=number,capture=capture,capture_frame=frame,source_hashes={k:hashlib.sha256(v).hexdigest()for k,v in raw.items()},pose=dict(frame=pose,family=family,source_palette=pal,colors=colors,bounds=[x0,y0,w,h],pieces=pieces)))
text=json.dumps(dict(schema=1,attacks=result),indent=2)+'\n';dest=ROOT/'tools/data/bc_boss_attack_shapes.json'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
if args.check:assert dest.read_text()==text
else:dest.write_text(text)
print(f'{len(result)} original PCE composite attack poses; captured geometry and palette evidence')
