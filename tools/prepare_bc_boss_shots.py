#!/usr/bin/env python3
"""Preserve original PCE boss shots, with shared families scoped to encounters."""
import argparse,hashlib,json,struct
from pathlib import Path
from qa_bc_factory import actor
ROOT=Path(__file__).resolve().parents[1]
SOURCES=((1,'actor-step-hopper',9240,6,0x36c8,0),(1,'actor-step-hopper',9240,17,0x36c8,2),
         (6,'round6-defeat',7680,3,0x36ce,0),(6,'round6-defeat',7680,5,0x36ce,2),
         (1,'actor-step-hopper',7920,12,0x3682,0),(1,'actor-step-hopper',8640,16,0x3682,2),
         (1,'actor-step-hopper',7800,11,0x3682,4),(1,'actor-step-hopper',7560,10,0x3682,6),
         (1,'actor-step-hopper',7920,11,0x3682,8),
         (9,'round9-final',27120,5,0x3682,0),(9,'round9-final',27360,7,0x3682,2),
         (3,'round3-defeat',8160,6,0x3682,4),(3,'round3-defeat',7680,8,0x3682,6),
         (3,'round3-defeat',7680,9,0x3682,8),(7,'round7-defeat',9120,3,0x3698,0))
shapes=[]
for number,capture,frame,slot,family,offset in SOURCES:
 folder=ROOT/'.local/pce-reference'/capture;stem=f'f{frame:06d}'
 paths={k:folder/f'{stem}-{k}.bin'for k in ('ram','vram','palette')};paths['code']=folder/'code-002160.bin'
 raw={k:p.read_bytes()for k,p in paths.items()};a=actor(raw['ram'],slot,raw['code']);b=a.body
 assert b.state==128 and a.sprite_base_ref==family and b.sprite-b.sprite_base==offset and not b.flags&8
 vram=struct.unpack('<32768H',raw['vram']);palette=struct.unpack('<512H',raw['palette']);pal=b.attributes&15;pattern=b.sprite>>1
 rows=[''.join(format(sum(((vram[pattern*64+y+c*16]>>(15-x))&1)<<c for c in range(4)),'x')for x in range(16))for y in range(16)]
 colors=[[v>>3&7,v>>6&7,v&7]for v in palette[256+pal*16:272+pal*16]]
 shapes.append(dict(id=f'boss-shot-{family:04x}-{offset:02x}-p{pal}',round=number,family=family,frame=offset,source_palette=pal,boss_context_only=family in (0x3682,0x3698),size=16,rows=rows,colors=colors,source_capture=capture,source_frame=frame,source_pattern=b.sprite,source_attributes=b.attributes,source_hashes={k:hashlib.sha256(v).hexdigest()for k,v in raw.items()}))
text=json.dumps(dict(schema=1,scope='Original boss shots; shared families require boss context',shapes=shapes),indent=2)+'\n';dest=ROOT/'tools/data/bc_boss_shot_shapes.json'
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
if args.check:assert dest.read_text()==text
else:dest.write_text(text)
print([(s['id'],sorted({int(v,16)for row in s['rows']for v in row}))for s in shapes])
