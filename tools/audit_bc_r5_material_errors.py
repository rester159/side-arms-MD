#!/usr/bin/env python3
"""Require each reused R5 material group to improve source color error.

Compare RGB in the native 3-bit gamut on every opaque pixel of each unique used
character. This complements linked source-shape/ramp checks, not visual approval.
"""
from pathlib import Path
import sys,json,struct,numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from arcade_source import Source,decode_bgtiles,palette_rgb
from quantize import to_md,nearest
s=Source();main=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));src=[to_md(tuple(c//17 for c in palette_rgb(main[0x14a37+i],main[0x14e37+i])))for i in range(1024)];d=json.loads(Path('res/generated/bc_r5_material_shading.json').read_text());groups={}
for label,prefix in [('old','zone10'),('new','bc_r5_material')]:
 raw=Path(f'res/generated/{prefix}_tiles.bin').read_bytes();a=np.fromfile(f'res/generated/{prefix}_attr.bin','>u2');pal=np.fromfile(f'res/generated/{prefix}_pal.bin','>u2');cols=[(int(w)>>1&7,int(w)>>5&7,int(w)>>9&7)for w in pal]
 for r in d['characters']:
  n=r['meta']*16+r['subtile'];word=int(a[n]);b=raw[n*32:(n+1)*32];px=np.frombuffer(b,np.uint8).reshape(8,4);px=np.stack((px>>4,px&15),-1).reshape(8,8);q=r['subtile'];pens=bg[r['code'],q//4*8:q//4*8+8,q%4*8:q%4*8+8];g=groups.setdefault((r['source_palette'],label),dict(colors=set(),source=set(),errors=[]))
  for p,k in zip(pens.flat,px.flat):
   if int(p)==15:continue
   c=cols[(word>>13&1)*16+int(k)];v=src[r['source_palette']*16+int(p)];g['colors'].add(c);g['source'].add(v);g['errors'].append(sum((x-y)**2 for x,y in zip(c,v)))
rows=[dict(source_palette=k[0],version=k[1],source_colors=len(g['source']),output_colors=len(g['colors']),mean_squared_rgb_error=sum(g['errors'])/len(g['errors']))for k,g in sorted(groups.items())if g['errors']]
for cl in {r['source_palette']for r in rows}:
 before=next(r for r in rows if r['source_palette']==cl and r['version']=='old')
 after=next(r for r in rows if r['source_palette']==cl and r['version']=='new')
 assert after['mean_squared_rgb_error']<before['mean_squared_rgb_error'],(cl,before,after)
Path('.local/bc-r5-shading-fix/material-errors.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
