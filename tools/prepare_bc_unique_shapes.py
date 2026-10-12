#!/usr/bin/env python3
"""Export three BC-specific shapes from exact live actor/SAT/VRAM captures."""
import hashlib,json,struct
from pathlib import Path
import numpy as np
from qa_bc_factory import actor
ROOT=Path(__file__).resolve().parents[1]
ids={'actor-36c8-00-p1','actor-36b4-00-p9','actor-367a-28-p0'}
source=ROOT/'.local/bc-asset-matching-review/expanded/manifest.json'
shapes=[]
for r in json.loads(source.read_text())['records']:
    if r['id'] not in ids:continue
    cap=ROOT/'.local/pce-reference'/r['capture'];stem=f'f{r["frame"]:06d}'
    paths={k:cap/(stem+'-'+k+'.bin') for k in ('ram','sat','vram','palette')}
    ram=paths['ram'].read_bytes();program=(cap/'code-002160.bin').read_bytes();sat=struct.unpack('<256H',paths['sat'].read_bytes())
    matches=[]
    for slot in range(32):
        a=actor(ram,slot,program);b=a.body
        if b.state and a.sprite_base_ref==r['ref'] and b.sprite-b.sprite_base==r['offset'] and b.attributes&15==r['palette']:
            want=(((b.y>>8)-8+64)&1023,((b.x>>8)-8+32)&1023,b.sprite,b.attributes)
            if any(tuple(sat[j:j+4])==want for j in range(0,256,4)):matches.append(a)
    assert matches,r['id'];a=matches[0]
    vram=np.fromfile(paths['vram'],'<u2');palette=np.fromfile(paths['palette'],'<u2');pat=a.body.sprite>>1
    pixels=[[sum(((int(vram[pat*64+y+p*16])>>(15-x))&1)<<p for p in range(4)) for x in range(16)]for y in range(16)]
    words=palette[256+r['palette']*16:272+r['palette']*16]
    rgb=[[(int(w)>>3)&7,(int(w)>>6)&7,int(w)&7]for w in words]
    print(r['id'],{p:rgb[p] for row in pixels for p in row if p})
    shapes.append(dict(id=r['id'],family=r['ref'],frame=r['offset'],source_palette=r['palette'],size=16,rows=[''.join(format(p,'x')for p in row)for row in pixels],colors=rgb,source_capture=r['capture'],source_frame=r['frame'],source_pattern=int(a.body.sprite),source_attributes=int(a.body.attributes),source_hashes={k:hashlib.sha256(p.read_bytes()).hexdigest()for k,p in paths.items()}))
assert {r['id']for r in shapes}==ids
(ROOT/'tools/data/bc_unique_shapes.json').write_text(json.dumps(dict(schema=1,shapes=shapes),indent=2)+'\n')
