#!/usr/bin/env python3
"""Reconstruct compiled R2 blocks and compare every pixel to captured geometry."""
import json,re
import numpy as np
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
source=next(b for b in json.loads((ROOT/'tools/data/bc_composite_source_shapes.json').read_text())['bosses'] if b['round']==2)
meta=json.loads((ROOT/'res/generated/bc_boss2_geometry.json').read_text())
body=re.search(r'bc_boss2_patterns\[\d+\].*?= \{(.*?)\};',(ROOT/'src/gen/bc_boss_art.c').read_text(),re.S)[1]
raw=bytes(int(v,16)for v in re.findall(r'0x([0-9a-f]+)',body))
assert len(raw)==meta['block_count']*512
words=np.frombuffer((ROOT/'res/generated/bc_sprite_pal.bin').read_bytes(),'>u2')
pal=np.array([(int(w)>>1&7,int(w)>>5&7,int(w)>>9&7)for w in words])
out=ROOT/'.local/bc-boss2-shape-fix';out.mkdir(exist_ok=True)
checked=opaque=0
for pose in source['poses']:
 entry=next(p for p in meta['poses']if p['frame']==pose['frame'])
 expected=np.zeros((192,192),dtype=np.uint8);actual=expected.copy()
 for part in pose['pieces']:
  p=np.array([[int(v,16)for v in row]for row in part['rows']]);lut=np.array(entry['pen_lut'],dtype=np.uint8)
  y,x=part['y']+96,part['x']+96;dst=expected[y:y+16,x:x+16];dst[p!=0]=lut[p[p!=0]]
  assert all(entry['pen_lut'][v] for v in np.unique(p)if v),'Opaque source pen became transparent'
 for piece in meta['pieces'][entry['first']:entry['first']+entry['count']]:
  block=raw[piece['tile']*512:(piece['tile']+1)*512]
  for y in range(32):
   for x in range(32):
    b=block[((x//8)*4+y//8)*32+(y%8)*4+x%8//2];p=b>>4 if x%2==0 else b&15
    dx=31-x if piece['flags']&1 else x;dy=31-y if piece['flags']&2 else y
    actual[piece['y']+96+dy,piece['x']+96+dx]=p
 assert np.array_equal(actual,expected),hex(pose['frame'])
 for ramp in entry['shade_ramps']:
  levels=ramp['luminance'];assert all(b-a>.20 for a,b in zip(levels,levels[1:])),levels
 rgb=(pal[entry['palette']*16:entry['palette']*16+16][actual]*36).astype(np.uint8)
 Image.fromarray(rgb[24:168,24:168]).save(out/f'part-{pose["frame"]:04x}.png')
 checked+=actual.size;opaque+=np.count_nonzero(actual)
result=dict(compared_pixels=checked,opaque_pixels=int(opaque),source_geometry_exact=True,
            ordered_material_shades=True,transparent_pen_preserved=True,blocks=meta['block_count'])
(out/'geometry.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
