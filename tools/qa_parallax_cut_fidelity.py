#!/usr/bin/env python3
"""Verify generated Home far-layer variants reproduce source pixels when locked."""
import argparse,json
from pathlib import Path
import numpy as np
from parallax_split import far_layers,world,bg_tiles,home_variant,to_meta
from zones import ZONES
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
W,code,color,flags=world();tiles=bg_tiles();results=[]
for zi,f in far_layers().items():
 zx,zy,zw,zh=ZONES[zi]['rect'];metas=sorted({(code[r,c],color[r,c])for r in range(zy,zy+zh)for c in range(zx,zx+zw)});mid={v:i for i,v in enumerate(metas)}
 variants,zmap=home_variant(zi,code,color,flags,mid,lambda col:0)
 checked=cut=retained=0
 for c,r in f['cut']:
  entry=zmap[(r-zy)*zw+c-zx]&1023
  assert entry>=len(metas)
  old=tiles[code[r,c]];new=variants[entry-len(metas)][1];fl=int(flags[r,c]);old=to_meta(old,fl);new=to_meta(new,fl)
  source=W[r*32:r*32+32,c*32:c*32+32];yy,xx=np.indices((32,32));texture=f['T'][(yy+r*32)%f['P'],(xx+c*32)%f['P']]
  removed=(old!=15)&(new==15);expected=f['cells'][(c,r)]
  assert np.array_equal(removed,expected),(zi,c,r,'variant cut mask')
  assert np.array_equal(old[~removed],new[~removed]),(zi,c,r,'uncut art modified')
  composed=np.where(removed,texture,source)
  assert np.array_equal(composed,source),(zi,c,r,'locked reconstruction')
  wrong_old=np.isin(source,list(f['tcol']))&(source!=texture)
  assert not np.any(removed&wrong_old)
  checked+=1024;cut+=int(removed.sum());retained+=int(wrong_old.sum())
 assert not f['hud_cut']
 results.append(dict(zone=zi,cells=len(f['cut']),checked_pixels=checked,cut_pixels=cut,nonperiodic_pixels_preserved=retained,locked_source_exact=True,hud_cells_cut=0,segments=f['segs']))
report=dict(passed=True,results=results,scope='Actual generated Home variant pens and locked far-texture reconstruction; runtime palette conversion, moving-layer aesthetics and timing require separate checks.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
