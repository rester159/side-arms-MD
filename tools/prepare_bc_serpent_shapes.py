#!/usr/bin/env python3
"""Extract all final-serpent poses from the loaded original PCE pattern bank."""
import argparse,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'.local/pce-reference/round10-reference'
paths={k:folder/f'f002160-{k}.bin'for k in ('ram','vram','palette','sat')}
raw={k:p.read_bytes()for k,p in paths.items()}
vram=struct.unpack('<32768H',raw['vram']);palette=struct.unpack('<512H',raw['palette'])
shapes=[]
for family,base,pals in ((0x36d0,0x288,(3,4)),(0x36d2,0x2b0,(5,)),(0x36d4,0x2d8,(6,))):
 for pal in pals:
  for frame in range(0,40,8):
   pattern=(base+frame)>>1
   rows=[''.join(format(sum(((vram[(pattern+(y//16)*2+x//16)*64+y%16+c*16]>>(15-x%16))&1)<<c for c in range(4)),'x')for x in range(32))for y in range(32)]
   colors=[[v>>3&7,v>>6&7,v&7]for v in palette[256+pal*16:272+pal*16]]
   shapes.append(dict(id=f'actor-{family:04x}-{frame:02x}-p{pal}',family=family,frame=frame,source_palette=pal,size=32,rows=rows,colors=colors,source_pattern=base+frame,source_capture='round10-reference',source_frame=2160,source_hashes={k:hashlib.sha256(v).hexdigest()for k,v in raw.items()}))
text=json.dumps(dict(schema=1,shapes=shapes),indent=2)+'\n';dest=ROOT/'tools/data/bc_serpent_shapes.json'
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args()
if args.check:assert dest.read_text()==text
else:dest.write_text(text)
print('20 original serpent poses, including both head palettes')
