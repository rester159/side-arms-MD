#!/usr/bin/env python3
"""Ensure BC scenery preserves its Normal Genesis material palette."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from bc_background_assets import arrays
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,help='Optionally require all non-palette scenery data unchanged')
a=p.parse_args();rows=[]
for number in range(1,11):
    suffix=str(number) if number>1 else ''
    path=ROOT/f'src/gen/bc_background{suffix}.c'
    prefix='bc_bg'+suffix
    data=arrays(path)
    source=ROOT/f'res/generated/zone{0 if number==1 else 3 if number==3 else 6 if number==4 else 10 if number==5 else 16 if number==8 else 19 if number==9 else 21 if number==10 else 1}_pal.bin'
    if number==2:source=ROOT/'res/generated/bc_r2_material_pal.bin'
    if number==5:source=ROOT/'res/generated/bc_r5_material_pal.bin'
    if number==6:source=ROOT/'res/generated/bc_r6_material_pal.bin'
    if number==7:source=ROOT/'res/generated/bc_r7_material_pal.bin'
    expected=list(struct.unpack('>32H',source.read_bytes()))
    assert data[prefix+'_palette']==expected,(number,'palette differs from Normal materials')
    row=dict(round=number,source=str(source.relative_to(ROOT)),palette_words=32)
    if a.baseline:
        old=arrays(a.baseline/path.name)
        assert old.keys()==data.keys()
        for name,values in data.items():
            if name!=prefix+'_palette':assert values==old[name],(number,name,'scenery geometry changed')
        row['changed_palette_words']=sum(x!=y for x,y in zip(old[prefix+'_palette'],expected))
        row['geometry_unchanged']=True
    row['generated_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    rows.append(row)
report=dict(passed=True,rounds=rows,tile_identity_verified=False)
print(json.dumps(report,indent=2))
