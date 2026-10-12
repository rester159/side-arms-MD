#!/usr/bin/env python3
"""Find source-visible BC cells replaced by entirely black generated scenery.
This detects omissions, not correctness of nonblank object matches.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
from inspect_bc_background import source_cell
from bc_background_assets import arrays
ROOT=Path(__file__).resolve().parents[1]
def visible(data,prefix,cell):
    block=data[prefix+'_remap'][cell]&4095;assert block!=4095
    count=0
    for tile in range(16):
        attr=data[prefix+'_templates'][block*16+tile]
        if not attr:continue
        bank=(attr>>13&1)*16
        raw=data[prefix+'_tiles'][(block*16+tile)*32:(block*16+tile+1)*32]
        for byte in raw:
            for pen in (byte>>4,byte&15):
                count+=bool(pen and data[prefix+'_palette'][bank+pen])
    return count
inventory=json.loads((ROOT/'.local/bc-asset-matching-review/match-inventory.json').read_text())
misses=[];checked=0;sources=[]
for rnd in inventory['rounds']:
    number=rnd['round'];cap=Path(rnd['source_capture'])
    code=(cap/'code-002160.bin').read_bytes()
    vram=np.frombuffer((cap/'f002400-vram.bin').read_bytes(),'<u2')
    words=np.frombuffer((cap/'f002400-palette.bin').read_bytes(),'<u2')
    palette=np.array([((int(w)>>3&7)*36,(int(w)>>6&7)*36,(int(w)&7)*36)for w in words],np.uint8)
    suffix=str(number)if number>1 else '';prefix='bc_bg'+suffix
    path=ROOT/f'src/gen/bc_background{suffix}.c';data=arrays(path)
    sources.append(dict(round=number,code_sha256=hashlib.sha256(code).hexdigest(),generated_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    for row in rnd['mappings']:
        cell=row['source_cell'];source_count=int(np.any(source_cell(code,vram,palette,cell),axis=2).sum())
        actual_count=visible(data,prefix,cell);checked+=1
        if source_count and not actual_count:
            misses.append(dict(round=number,cell=cell,source_visible_pixels=source_count,normal_meta=row['normal_meta']))
report=dict(passed=not misses,checked_cells=checked,omissions=misses,sources=sources,
            scope='Entirely blank substitutions only; nonblank geometry and source identity remain unverified.')
out=ROOT/'.local/bc-background-visibility.json';out.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='sources'},indent=2))
raise SystemExit(bool(misses))
