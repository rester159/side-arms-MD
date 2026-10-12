#!/usr/bin/env python3
"""Audit a linked material palette fit against original source-color pairs."""
import argparse,hashlib,itertools,json,struct
from pathlib import Path
import numpy as np
from arcade_source import ROOT,Source,decode_bgtiles,bgmap_cells,palette_rgb
from quantize import to_md
from bc_background_equivalence import symbols,rendered_cell
import zones
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--art-only',action='store_true',help='For the aggregate material verifier, which separately checks unrelated blobs');p.add_argument('--zone',type=int,choices=(6,19,20),default=6);p.add_argument('--changed-zones',type=int,nargs='+');a=p.parse_args();z=a.zone;changed_zones=a.changed_zones or [z]
recipe=json.loads((ROOT/f'tools/data/normal_zone{z}_palette_fit.json').read_text());minimum_pairs=recipe.get('recovered_source_pairs',40)
old=(a.baseline/'rom.bin').read_bytes();rom=(ROOT/'out/release/rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt');sy=symbols(ROOT/'out/release/symbol.txt')
s=Source();main=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));code,col,_=bgmap_cells(s.region('bgmap'));colors=np.array([to_md(tuple(v//17 for v in palette_rgb(main[0x14a37+i],main[0x14e37+i])))for i in range(1024)])
x,y,w,h=zones.ZONES[z]['rect'];metas=sorted({(int(code[r,c]),int(col[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
def rgb(words):return np.stack((words>>1&7,words>>5&7,words>>9&7),axis=-1)
def decode(data,table):
 pal=np.array(struct.unpack_from('>32H',data,table[f'zone{z}_pal']));attrs=np.array(struct.unpack_from('>'+str(len(metas)*16)+'H',data,table[f'zone{z}_attr']));start=table[f'zone{z}_tiles'];raw=np.frombuffer(data[start:start+len(metas)*512],'u1').reshape(-1,8,4);pens=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8);words=pal[((attrs>>13&1)*16)[:,None,None]+pens]
 return words,pens,pal,attrs
before,bp,opal,oa=decode(old,os);after,ap,npal,na=decode(rom,sy)
assert np.array_equal(bp!=0,ap!=0);assert np.array_equal(oa&~0x2000,na&~0x2000);assert np.array_equal(opal[1:4],npal[1:4]);assert np.array_equal(opal[17:19],npal[17:19])
lut=np.array(struct.unpack_from('>512H',rom,sy['vivid_lut']));assert old[os['vivid_lut']:os['vivid_lut']+1024]==rom[sy['vivid_lut']:sy['vivid_lut']+1024]
source=[]
for cd,cl in metas:
 for k in range(16):source.append(colors[cl*16+bg[cd,k//4*8:k//4*8+8,k%4*8:k%4*8+8].astype(int)])
source=np.array(source);live=bp!=0
lookup=lambda v:lut[(v>>1&7)|((v>>5&7)<<3)|((v>>9&7)<<6)]
def collisions(original,rendered,mask):
 result=set()
 for color in np.unique(rendered[mask]):
  group=sorted(set(map(tuple,original[mask&(rendered==color)])))
  result.update(itertools.combinations(group,2))
 return result
modes={}
for mode,prior,current in [('standard',before,after),('vivid',lookup(before),lookup(after))]:
 recovered=0;improved=[]
 for m in range(len(metas)):
  sl=slice(m*16,(m+1)*16);b=collisions(source[sl],prior[sl],live[sl]);c=collisions(source[sl],current[sl],live[sl]);assert not c-b,(mode,m,'new source-color merges',c-b);recovered+=len(b-c)
  if b-c:improved.append(m)
 assert recovered>=minimum_pairs,(mode,recovered)
 modes[mode]=dict(recovered_source_pairs=recovered,new_source_pair_merges=0,improved_metatiles=improved)
def errors(words):
 delta=source[live].astype(float)-rgb(words)[live]
 return dict(mean_squared_channel_error=float(np.mean(delta**2)),weighted_squared_error=float(np.sum((delta*np.array([3,4,2]))**2)),exact_pixels=int(np.all(delta==0,axis=1).sum()))
err_before,err_after=errors(before),errors(after)
if z in (19,20):
 assert err_after['mean_squared_channel_error']<err_before['mean_squared_channel_error']
 assert err_after['exact_pixels']>err_before['exact_pixels']
# This fit deliberately trades a small RGB-channel error increase for recovering
# source shade distinctions; report both metrics rather than hiding the tradeoff.
linked=[]
for path in (ROOT/'res/generated').glob('*.bin'):
 name=path.stem
 if name not in sy or name not in os:continue
 raw=path.read_bytes();assert rom[sy[name]:sy[name]+len(raw)]==raw,name
 if not a.art_only and name not in {f'zone{zone}_{suffix}' for zone in changed_zones for suffix in ('tiles','attr','pal')}:assert old[os[name]:os[name]+len(raw)]==raw,('unrelated asset changed',name)
 linked.append(name)
def cells(data,table,n):
 prefix='bc_bg'+(str(n)if n>1 else '');pal=struct.unpack_from('>32H',data,table[prefix+'_palette']);entries=struct.unpack_from('>256H',data,table[prefix+'_remap']);return {c:[(bool(v and v[0]),pal[(v[1]>>13&1)*16+v[0]]if v and v[0]else 0,v[1]&0x8000 if v and v[0]else 0)for v in rendered_cell(data,table,prefix,e)]for c,e in enumerate(entries)if e!=4095}
count=0
for n in range(1,11):
 b=cells(old,os,n);assert b==cells(rom,sy,n),('BC art changed',n);count+=len(b);name=f'bc_round{n}_code';assert old[os[name]:os[name]+65536]==rom[sy[name]:sy[name]+65536]
result=dict(passed=True,zone=z,rom_sha256=hashlib.sha256(rom).hexdigest(),baseline_sha256=hashlib.sha256(old).hexdigest(),modes=modes,before=err_before,after=err_after,unchanged_bc_cells=count,linked_blobs_verified=len(linked),unrelated_blobs_checked=not a.art_only,geometry_unchanged=True,stars_unchanged=True,vivid_lut_unchanged=True)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
