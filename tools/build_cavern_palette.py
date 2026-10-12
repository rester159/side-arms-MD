#!/usr/bin/env python3
"""Repack the Normal cavern for two raster palettes after BC donor generation.

The reviewed allocation is fixed data; pixels come from the user's arcade ROM
and the ordinary Genesis conversion. Route ownership is regenerated from level
legs. Off-route opaque pixels keep opacity and use the nearest available color.
"""
from pathlib import Path
import argparse, hashlib, json, struct
import numpy as np
from arcade_source import ROOT, Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md
import zones, parallax_split

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--generated',type=Path,default=ROOT/'res/generated')
p.add_argument('--output',type=Path)
a=p.parse_args();g=a.generated;out=a.output or g;out.mkdir(parents=True,exist_ok=True)
recipe=json.loads((Path(__file__).parent/'data/normal_cavern_raster.json').read_text())
for name,want in recipe['input_sha256'].items():
    assert hashlib.sha256((g/name).read_bytes()).hexdigest()==want, f'Unreviewed cavern input: {name}'
s=Source();main=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));code,cls,flags=bgmap_cells(s.region('bgmap'))
colors=[to_md(tuple(c//17 for c in palette_rgb(main[0x14a37+i],main[0x14e37+i])))for i in range(1024)]
word=lambda c:int(c[0])*2+int(c[1])*32+int(c[2])*512
rgb=lambda w:(int(w)>>1&7,int(w)>>5&7,int(w)>>9&7)
x,y,w,h=zones.ZONES[10]['rect'];metas=sorted({(int(code[r,c]),int(cls[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
pal=np.concatenate((np.fromfile(g/'zone10_pal.bin','>u2'),np.fromfile(g/'sprite_pal.bin','>u2')))
slots=np.array([region+[list(map(int,pal[b*16:b*16+16]))for b in (2,3)]for region in recipe['slots']])
home,_=parallax_split.home_variant(10,code,cls,flags,{k:i for i,k in enumerate(metas)},lambda c:min(range(15),key=lambda pen:sum(colors[c*16+pen])))
# Reproduce center-based zone retention along every integer route position.
visible=np.zeros((4096,4096),bool);active=None

def contains(z,cx,cy):
    zx,zy,zw,zh=zones.ZONES[z]['rect'];return zx<=cx<zx+zw and zy<=cy<zy+zh

for section in json.loads((g/'levels.json').read_text())['sections']:
    for leg in section['legs']:
        sx,sy=leg['start'];ex,ey=leg['end'];length=max(abs(ex-sx),abs(ey-sy));dx=(ex>sx)-(ex<sx);dy=(ey>sy)-(ey<sy)
        for n in range(length+1):
            camx=sx+dx*n+96;camy=sy+dy*n+16;cx=(camx+160)//32;cy=(camy+112)//32
            if active is None or not contains(active,cx,cy):
                candidates=[i for i in range(len(zones.ZONES))if i not in zones.RUNTIME_OMITTED_ZONES and contains(i,cx,cy)]
                if candidates:active=candidates[0]
            if active==10:visible[max(0,camy):min(4096,camy+224),max(0,camx):min(4096,camx+320)]=True

def masks_for(stem,count):
    grid=np.fromfile(g/(stem+'_map.bin'),'>u2').reshape(h,w);result=[]
    for region in (0,1):
        vis=visible.copy()
        if region:vis[:2048]=False;vis[:,:1536]=False
        else:vis[2048:,1536:]=False
        mask=np.zeros((count,32,32),bool)
        for yy in range(h):
            for xx in range(w):
                cell=int(grid[yy,xx]);m=cell&4095
                if stem.endswith('h'):
                    if m<len(metas):continue
                    m-=len(metas)
                view=vis[(y+yy)*32:(y+yy+1)*32,(x+xx)*32:(x+xx+1)*32]
                if cell&0x4000:view=view[:,::-1]
                if cell&0x8000:view=view[::-1]
                mask[m]|=view
        result.append(mask)
    return result

ramps={c:{word(colors[c*16+i])for i in range(1,7)}for c in (10,11)}
outputs={};changed=0;checked=0
for stem,patterns in [('zone10',[(i,bg[cd])for i,(cd,_)in enumerate(metas)]),('zone10h',home)]:
    masks=masks_for(stem,len(patterns));attrs=np.fromfile(g/(stem+'_attr.bin'),'>u2');raw=np.fromfile(g/(stem+'_tiles.bin'),'u1').reshape(-1,8,4);pens=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8);newpens=np.zeros_like(pens);newattrs=attrs.copy()
    for m,(owner,pattern)in enumerate(patterns):
        cl=metas[owner][1]
        for k in range(16):
            n=m*16+k;px=pens[n];oldbank=int(attrs[n])>>13&3;old=pal[oldbank*16+px];sp=pattern[k//4*8:k//4*8+8,k%4*8:k%4*8+8];src=np.array([word(colors[cl*16+int(q)])for q in sp.flat]).reshape(8,8);desired=old.copy()
            if cl in ramps:
                selected=np.isin(src,list(ramps[cl]));desired[selected]=src[selected]
            live=[mask[m,k//4*8:k//4*8+8,k%4*8:k%4*8+8]&(px!=0)for mask in masks];choices=[]
            for b in (oldbank,)+tuple(b for b in range(4)if b!=oldbank):
                result=np.zeros((8,8),np.uint8);valid=True
                for yy,xx in zip(*np.nonzero(px)):
                    allowed=set(range(1,16));needed=False
                    for region in (0,1):
                        if live[region][yy,xx]:allowed&={i for i in range(1,16)if slots[region,b,i]==desired[yy,xx]};needed=True
                    if not allowed:valid=False;break
                    if needed:result[yy,xx]=min(allowed)
                    else:
                        region=int(live[1].sum()>live[0].sum());target=rgb(int(desired[yy,xx]));result[yy,xx]=min(range(1,16),key=lambda i:sum((a-c)**2 for a,c in zip(rgb(slots[region,b,i]),target)))
                if valid:choices.append((b,result));break
            assert choices,(stem,m,k,'no shared subtile allocation')
            b,result=choices[0];newpens[n]=result;newattrs[n]=(int(attrs[n])&0x9fff)|(b<<13) if px.any() else 0
            assert np.array_equal(result!=0,px!=0)
            for region in (0,1):
                assert np.array_equal(slots[region,b,result][live[region]],desired[live[region]])
                checked+=int(live[region].sum())
            changed+=int(np.any(result!=px)or newattrs[n]!=attrs[n])
    outputs[stem+'_tiles.bin']=((newpens[:,:,::2]<<4)|newpens[:,:,1::2]).tobytes();outputs[stem+'_attr.bin']=newattrs.astype('>u2').tobytes()
# Far patterns must use slots whose colors do not change at the split.
raw=np.fromfile(g/'zone10_far_tiles.bin','u1').reshape(-1,8,4);pens=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8);attrs=np.fromfile(g/'zone10_far_map.bin','>u2');newpens=pens.copy();newattrs=attrs.copy();assigned={}
for n,attr in enumerate(attrs):
    tid=int(attr)&2047;oldbank=int(attr)>>13&3;px=pens[tid];wanted=pal[oldbank*16+px]
    for b in (0,1):
        mapping={int(c):next((i for i in range(1,16)if slots[0,b,i]==c==slots[1,b,i]),None)for c in np.unique(wanted[px!=0])}
        if all(i is not None for i in mapping.values()):break
    else:raise AssertionError('No stable far palette')
    result=np.zeros_like(px)
    for c,i in mapping.items():result[(px!=0)&(wanted==c)]=i
    if tid in assigned:assert np.array_equal(assigned[tid],result)
    assigned[tid]=result;newpens[tid]=result;newattrs[n]=(int(attr)&0x9fff)|(b<<13)
outputs['zone10_far_tiles.bin']=((newpens[:,:,::2]<<4)|newpens[:,:,1::2]).tobytes();outputs['zone10_far_map.bin']=newattrs.astype('>u2').tobytes()
for region,name in enumerate(['zone10_pal.bin','zone10_lower_pal.bin']):outputs[name]=slots[region,:2].astype('>u2').tobytes()
for name,data in outputs.items():
    assert hashlib.sha256(data).hexdigest()==recipe['output_sha256'][name],f'Conversion differs from reviewed result: {name}'
for name,data in outputs.items():(out/name).write_bytes(data)
report=dict(checked_region_pixels=checked,changed_subtiles=changed,outputs={name:hashlib.sha256(data).hexdigest()for name,data in outputs.items()},scope='Normal cavern only; route-mask exact colors and unchanged opacity; BC donors built before this step')
(out/'normal_cavern_raster.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

header=(ROOT/'inc/gen/cave_palette_data.h') if a.output is None else out/'cave_palette_data.h'
header.parent.mkdir(parents=True,exist_ok=True)
changed=[b*16+i for b in range(2)for i in range(16)if slots[0,b,i]!=slots[1,b,i]]
assert changed==[9,10,11,12,13,14,15,29,30,31]
header.write_text('/* Generated by build_cavern_palette.py; do not edit. */\n#pragma once\n'+
    'static const u16 cave_slots[10] = {'+','.join(map(str,changed))+'};\n'+
    'static const u16 cave_lower[32] = {'+','.join(hex(int(c))for c in slots[1,:2].flat)+'};\n')
