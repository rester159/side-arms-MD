#!/usr/bin/env python3
"""Compare exported beam geometry/shade ranks with independent captured references."""
import argparse,hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--references',type=Path,required=True);args=p.parse_args()
shapes=json.loads((ROOT/'tools/data/bc_beam_shapes.json').read_text())['shapes']
built={r['id']:r for r in json.loads((ROOT/'res/generated/bc_sprite_recolors.json').read_text())}
idx=np.fromfile(ROOT/'res/generated/spr_bank_index.bin','>u2');bank=(ROOT/'res/generated/spr_bank.bin').read_bytes();palette=np.fromfile(ROOT/'res/generated/bc_sprite_pal.bin','>u2');checked=0
for r in shapes:
    path=args.references/(r['id']+'.png');assert hashlib.sha256(path.read_bytes()).hexdigest()==r['reference_sha256']
    rgb=np.array(Image.open(path).convert('RGB').crop((0,0,128,128)).resize((16,16),Image.Resampling.NEAREST))
    refmask=np.any(rgb!=0,axis=2);rec=built[r['id']];entry=int(idx[rec['key']]);raw=bank[((entry&32767)-1)*128:(entry&32767)*128]
    pens=np.zeros((16,16),int)
    for y in range(16):
        for x in range(16):
            b=raw[((x//8)*2+y//8)*32+y%8*4+x%8//2];pens[y,x]=b>>4 if x%2==0 else b&15
    assert np.array_equal(pens!=0,refmask),r['id']
    source_light=rgb@np.array([.299,.587,.114]);w=palette[16+pens];light=(w>>1&7)*.299+(w>>5&7)*.587+(w>>9&7)*.114
    previous=-1
    for level in sorted(set(source_light[refmask])):
        shades=set(light[(source_light==level)&refmask]);assert len(shades)==1
        value=shades.pop();assert value>previous,(r['id'],level,value,previous);previous=value
    checked+=256
print(json.dumps(dict(shapes=len(shapes),reference_pixels=checked,source_geometry_preserved=True,source_shade_order_preserved=True),indent=2))
