#!/usr/bin/env python3
"""Validate BC-specific shape pixels against captured source VRAM and ROM banks."""
import hashlib,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
shapes=json.loads((ROOT/'tools/data/bc_unique_shapes.json').read_text())['shapes']
records={r['id']:r for r in json.loads((ROOT/'res/generated/bc_sprite_recolors.json').read_text())}
index=np.fromfile(ROOT/'res/generated/spr_bank_index.bin','>u2');bank=(ROOT/'res/generated/spr_bank.bin').read_bytes()
count=0;opaque_black=0
for shape in shapes:
    cap=ROOT/'.local/pce-reference'/shape['source_capture'];stem=f'f{shape["source_frame"]:06d}'
    for kind,digest in shape['source_hashes'].items():assert hashlib.sha256((cap/(stem+'-'+kind+'.bin')).read_bytes()).hexdigest()==digest
    vram=np.fromfile(cap/(stem+'-vram.bin'),'<u2');base=(shape['source_pattern']>>1)*64
    rec=records[shape['id']];entry=int(index[rec['key']]);raw=bank[((entry&32767)-1)*128:(entry&32767)*128]
    for y in range(16):
        for x in range(16):
            source=sum(((int(vram[base+y+plane*16])>>(15-x))&1)<<plane for plane in range(4))
            assert source==int(shape['rows'][y][x],16)
            at=((x//8)*2+y//8)*32+(y%8)*4+(x%8)//2
            output=(raw[at]>>4)if x%2==0 else(raw[at]&15)
            assert output==rec['pen_lut'][source]
            assert bool(output)==bool(source)
            opaque_black+=bool(source and max(shape['colors'][source])==0);count+=1
    for ramp in rec['shade_ramps']:
        levels=ramp['luminance'];assert all(b>a for a,b in zip(levels,levels[1:]))
assert opaque_black>0
print(json.dumps(dict(shapes=len(shapes),verified_pixels=count,opaque_black_pixels=opaque_black,source_opacity_preserved=True,ordered_shading=True),indent=2))
