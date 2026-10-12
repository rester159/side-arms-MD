#!/usr/bin/env python3
"""Classify actual Genesis material reuse; this does not prove PCE tile identity."""
import hashlib
import json
import struct
from collections import Counter
from pathlib import Path
import numpy as np
from bc_background_assets import arrays
ROOT=Path(__file__).resolve().parents[1]
def decode(raw,attrs,meta):
    result=np.zeros((32,32),np.uint16)
    for i in range(16):
        attr=attrs[meta*16+i]
        data=np.array(list(raw[(meta*16+(attr&2047))*32:(meta*16+(attr&2047)+1)*32]),np.uint8).reshape(8,4)
        pens=np.stack((data>>4,data&15),axis=-1).reshape(8,8).astype(np.uint16)
        if attr&0x800:pens=pens[:,::-1]
        if attr&0x1000:pens=pens[::-1,:]
        # Attribute zero is the renderer's blank-cell sentinel.
        if attr:pens|=attr&0xe000
        else:pens[:]=0
        result[i//4*8:i//4*8+8,i%4*8:i%4*8+8]=pens
    return result
inventory=json.loads((ROOT/'.local/bc-asset-matching-review/match-inventory.json').read_text())
rows=[]
for rnd in inventory['rounds']:
    number=rnd['round'];zone=0 if number==1 else 3 if number==3 else 6 if number==4 else 10 if number==5 else 13 if number==6 else 14 if number==7 else 16 if number==8 else 19 if number==9 else 21 if number==10 else 1
    raw=(ROOT/f'res/generated/zone{zone}_tiles.bin').read_bytes()
    attrs=struct.unpack('>'+str(len(raw)//32)+'H',(ROOT/f'res/generated/zone{zone}_attr.bin').read_bytes())
    candidates={}
    for meta in range(len(raw)//512):
        original=decode(raw,attrs,meta)
        for flip,view in [('none',original),('horizontal',original[:,::-1]),('vertical',original[::-1,:]),('both',original[::-1,::-1])]:
            candidates.setdefault(view.tobytes(),[]).append(dict(meta=meta,flip=flip))
    suffix=str(number) if number>1 else '';prefix='bc_bg'+suffix
    path=ROOT/f'src/gen/bc_background{suffix}.c';built=arrays(path)
    for mapping in rnd['mappings']:
        cell=mapping['source_cell'];entry=built[prefix+'_remap'][cell];art=entry&4095
        assert art!=4095
        pixels=decode(built[prefix+'_tiles'],built[prefix+'_templates'],art)
        if entry&0x4000:pixels=pixels[:,::-1]
        if entry&0x8000:pixels=pixels[::-1,:]
        matches=candidates.get(pixels.tobytes(),[])
        proposed=mapping['normal_meta']
        match=next((m for m in matches if m['meta']==proposed),matches[0] if matches else None)
        rows.append(dict(id=f'bg-r{number:02d}-{cell:02x}',round=number,source_cell=cell,
                         normal_zone=zone,proposed_meta=proposed,
                         reuse='exact' if match and match['flip']=='none' else 'flipped' if match else 'adapted',
                         matched_normal=match,pce_identity_verified=False,
                         geometry_sha256=hashlib.sha256(pixels.tobytes()).hexdigest()))
report=dict(schema=1,scope='Rendered pen geometry, palette bank and priority compared to current Normal Genesis tiles. Source PCE identity is not inferred.',
            counts=dict(Counter(r['reuse'] for r in rows)),tiles=rows)
path=ROOT/'tools/data/bc_background_reuse_audit.json'
path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report['counts']))
