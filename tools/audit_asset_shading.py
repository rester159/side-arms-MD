#!/usr/bin/env python3
"""Compare converted assets to their original source colors, including lost shades.

Read-only audit. Quantization to the Genesis 3-bit gamut is measured separately
from subsequent palette-fitting losses. A collision is a diagnostic, not by
itself a claim that a whole asset is unacceptable.
"""
from pathlib import Path
import argparse,hashlib,json,struct
import numpy as np
from arcade_source import ROOT,Source,decode_bgtiles,decode_sprites,bgmap_cells,palette_rgb
from quantize import to_md
from bc_background_equivalence import symbols
import zones
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
rom=(ROOT/'out/release/rom.bin').read_bytes()
linked=symbols(ROOT/'out/release/symbol.txt')
verified_blobs=set()
def blob(name):
 data=(ROOT/'res/generated'/f'{name}.bin').read_bytes()
 assert rom[linked[name]:linked[name]+len(data)]==data,('generated asset is not current ROM',name)
 verified_blobs.add(name)
 return data
# Appended BC keys use a different geometry and/or palette. Comparing them to
# the arcade color encoded in the spare lookup key reports fictitious losses.
bc_keys={16:set(),32:set()}
for name in ('bc_sprite_recolors','bc_serpent_shapes','bc_player_projectile_shapes','bc_player_death_shapes','bc_boss_shots'):
 for record in json.loads((ROOT/'res/generated'/f'{name}.json').read_text()):
  bc_keys[record.get('size',16)].add(record['key'])
s=Source();main=s.region('maincpu');lo=main[0x14a37:0x14e37];hi=main[0x14e37:0x15237]
arc=np.array([palette_rgb(lo[i],hi[i])for i in range(1024)],np.uint8)
md=np.array([to_md(tuple(int(c)//17 for c in rgb))for rgb in arc],np.uint8)
def colors(words):return np.array([((int(c)>>1&7),(int(c)>>5&7),(int(c)>>9&7))for c in words],np.uint8)
def pens(data,size):
 out=np.zeros((size,size),np.uint8)
 for y in range(size):
  for x in range(size):
   k=(x//8)*(size//8)+y//8
   b=data[k*32+y%8*4+x%8//2];out[y,x]=b&15 if x%2 else b>>4
 return out

def measure(source,actual,mask):
 src=source[mask];dst=actual[mask];groups={}
 for x,y in zip(src,dst):groups.setdefault(tuple(map(int,y)),set()).add(tuple(map(int,x)))
 collided=[dict(output=list(k),source=sorted(v))for k,v in groups.items()if len(v)>1]
 return dict(source_gamut_colors=len(set(map(tuple,src))),output_colors=len(set(map(tuple,dst))),merged_source_colors=sum(len(r['source'])-1 for r in collided),collisions=collided,mean_squared_channel_error=float(np.mean((src.astype(float)-dst)**2))if len(src)else 0)
rows=[];bg=decode_bgtiles(s.region('bgtiles'));code,col,flags=bgmap_cells(s.region('bgmap'))
for z,config in enumerate(zones.ZONES):
 if z in zones.RUNTIME_OMITTED_ZONES:continue
 x,y,w,h=config['rect'];metas=sorted({(code[r,c],col[r,c])for r in range(y,y+h)for c in range(x,x+w)})
 raw=blob(f'zone{z}_tiles');attrs=np.frombuffer(blob(f'zone{z}_attr'),'>u2');pal=colors(np.concatenate((np.frombuffer(blob(f'zone{z}_pal'),'>u2'),np.frombuffer(blob('sprite_pal'),'>u2'))))
 palettes=[pal];masks=None
 if z==10:
  from cavern_audit_geometry import region_masks
  lower=(ROOT/'res/generated/zone10_lower_pal.bin').read_bytes()
  assert rom[linked['cave_lower']:linked['cave_lower']+len(lower)]==lower, 'stale cavern raster palette'
  verified_blobs.add('cave_lower')
  palettes.append(colors(np.concatenate((np.frombuffer(lower,'>u2'),np.frombuffer(blob('sprite_pal'),'>u2')))))
  grid=np.frombuffer(blob('zone10_map'),'>u2').reshape(h,w)
  sections=json.loads((ROOT/'res/generated/levels.json').read_text())['sections']
  masks=region_masks(sections,grid,len(metas))
 for m,(cd,cl)in enumerate(metas):
  source=bg[cd]
  for region,palette in enumerate(palettes):
   mask=source!=15
   if masks is not None:mask=mask&masks[region][m]
   if masks is not None and not mask.any():continue
   actual=np.zeros((32,32,3),np.uint8)
   for k in range(16):
    word=int(attrs[m*16+k]);data=raw[(m*16+(word&15))*32:(m*16+(word&15)+1)*32];px=np.frombuffer(data,np.uint8).reshape(8,4);px=np.stack((px>>4,px&15),-1).reshape(8,8);actual[k//4*8:k//4*8+8,k%4*8:k%4*8+8]=palette[(word>>13&3)*16+px]
   r=measure(md[int(cl)*16+source.astype(np.int32)],actual,mask)
   row=dict(kind='background',zone=z,meta=m,code=int(cd),color=int(cl),checked_pixels=int(mask.sum()),**r)
   if masks is not None:row['cavern_region']=region
   rows.append(row)
spr=decode_sprites(s.region('sprites'));raw=blob('spr_bank');index=np.frombuffer(blob('spr_bank_index'),'>u2');pal=colors(np.frombuffer(blob('sprite_pal'),'>u2'));allkeys=np.flatnonzero(index);keys=sorted(set(map(int,allkeys))-bc_keys[16])
for key in keys:
 key=int(key);entry=int(index[key]);cd=key&2047;cl=key>>11;source=spr[cd];px=pens(raw[((entry&32767)-1)*128:(entry&32767)*128],16);actual=pal[(entry>>15)*16+px];r=measure(md[512+cl*16+source.astype(np.int32)],actual,source!=15);rows.append(dict(kind='sprite16',key=key,code=cd,color=cl,**r))
def walk(o, pairs):
    if isinstance(o,dict):
        cd=o.get('code');cl=o.get('color',o.get('colour'))
        if isinstance(cd,int) and isinstance(cl,int):pairs.add((cd&2047,cl&15))
        for v in o.values():walk(v,pairs)
    elif isinstance(o,list):
        for v in o:walk(v,pairs)
pairs={(0x396,7)}
for name in ['metasprites.json','spawns.json','player.json','player_sprites.json']:
    path=ROOT/'res/generated'/name
    if path.exists():walk(json.loads(path.read_text()),pairs)
matches=json.loads((ROOT/'tools/bc_sprite_matches.json').read_text())
poses={row['id']:row for row in matches['poses']}
for match in matches['extra_pair_matches']:
    row=poses[match];pairs.add((row['normal_code'],row['normal_colour']))
keyset=set(map(int,keys))
bigkeys={cd|(cl<<11) for cd,cl in pairs if all((((cd+a)&2047)|(cl<<11))in keyset for a in (0,1,8,9))}
bigkeys.update(k for k in keyset if not(k&9) and all((((k&2047)+a)&2047)|(k&~2047) in keyset for a in (1,8,9)))
raw=blob('spr_big');index=np.frombuffer(blob('spr_big_index'),'>u2')
for key in sorted(bigkeys-bc_keys[32]):
    entry=int(index[key])
    if not entry:continue  # Small-only additions have no original large-bank entry.
    cd=key&2047;cl=key>>11
    source=np.block([[spr[cd],spr[(cd+1)&2047]],[spr[(cd+8)&2047],spr[(cd+9)&2047]]])
    px=pens(raw[((entry&32767)-1)*512:(entry&32767)*512],32);actual=pal[(entry>>15)*16+px]
    r=measure(md[512+cl*16+source.astype(np.int32)],actual,source!=15)
    rows.append(dict(kind='sprite32',key=key,code=cd,color=cl,**r))
def asset_id(row):
 return (row['zone'],row['meta']) if row['kind']=='background' else row['key']
summary={kind:dict(assets=len({asset_id(r)for r in rows if r['kind']==kind}),
                  palette_contexts=sum(r['kind']==kind for r in rows),
                  with_palette_merges=len({asset_id(r)for r in rows if r['kind']==kind and r['merged_source_colors']>0}))
         for kind in ['background','sprite16','sprite32']}
report=dict(schema=3,rom_sha256=hashlib.sha256(rom).hexdigest(),summary=summary,linked_blobs_verified=sorted(verified_blobs),excluded_bc_small_keys=len(set(map(int,allkeys))&bc_keys[16]),excluded_bc_large_keys=len({int(k)for k in np.flatnonzero(index)}&bc_keys[32]),excluded_scene_only_zones=sorted(zones.SCENE_ONLY_ZONES),excluded_shadowed_zones=sorted(zones.SHADOWED_ZONE_PARENTS),scope='Cavern zone10 uses linked upper/lower palettes and per-region authored-route masks; off-route cavern pixels and raster execution timing are excluded. Context counts distinguish shared metatiles observed in both palettes. Other linked original Normal background zones (the offline Earth bank is replaced in-game by separately checked frontend scenes; unreachable shadowed zones are omitted from the cartridge) and original-key 16x16/32x32 sprite banks, including original-geometry launcher additions. BC recolor/import lookup keys are excluded: they do not encode their source palettes. BC variants and authored organic assets have separate audits. Every examined blob is checked against the linked ROM.',assets=rows)
(a.output/'audit.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(summary,indent=2))
