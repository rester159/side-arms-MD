#!/usr/bin/env python3
"""Export missing BC beam shapes from canonical, live-SAT-verified references."""
import hashlib,json
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
src=ROOT/'.local/bc-asset-matching-review'
records=[]
for r in json.loads((src/'expanded/manifest.json').read_text())['records']:
    if r['ref']!=0x36cc:continue
    path=src/r['sheet']
    rgb=Image.open(path).convert('RGB').crop((0,0,128,128)).resize((16,16),Image.Resampling.NEAREST)
    colors=[(0,0,0)]+([(218,0,0),(255,72,0),(255,145,0),(255,255,0),(255,255,255)] if r['palette']==1 else [(0,36,145),(0,72,255),(0,145,255),(0,255,255),(255,255,255)])
    rows=[''.join(str(colors.index(rgb.getpixel((x,y)))) for x in range(16)) for y in range(16)]
    records.append(dict(id=r['id'],family=r['ref'],frame=r['offset'],source_palette=r['palette'],size=16,rows=rows,source_capture=r['capture'],source_frame=r['frame'],reference_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
assert len(records)==25
(ROOT/'tools/data/bc_beam_shapes.json').write_text(json.dumps(dict(schema=1,description='Canonical BC-only beam geometry and ordered shade ranks; 0 transparent, 1 darkest, 5 brightest. Ordinary Genesis beam bank lacks these growth/turn/corner poses.',shapes=records),indent=2)+'\n')
print('Exported',len(records),'beam shapes')
