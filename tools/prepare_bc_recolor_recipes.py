#!/usr/bin/env python3
"""Export reproducible pen-color recipes from the local reviewed BC captures.
Only palette colors are transferred; Genesis pixel positions remain untouched.
Normal mapping source is an explicit pre-recolor snapshot, never the selector.
"""
import argparse, ctypes as C, json, subprocess, tempfile
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np
from PIL import Image
from qa_bc_factory import Actor
from resolve_bc_art_decisions import identity
ROOT=Path(__file__).resolve().parents[1]

def pixels(raw, code, size):
    cells=[raw[(code+a)*128:(code+a+1)*128] for a in ([0,1,8,9] if size==32 else [0])]
    out=np.zeros((size,size),dtype=np.uint8)
    for y in range(size):
        for x in range(size):
            cell=cells[(y//16)*2+x//16] if size==32 else cells[0]
            b=cell[((x%16)//8*2+(y%16)//8)*32+(y%8)*4+(x%8)//2]
            out[y,x]=b>>4 if x%2==0 else b&15
    return out

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--normal-art-source',type=Path,required=True)
    args=ap.parse_args()
    cards=json.loads((ROOT/'.local/bc-asset-review/review-manifest.json').read_text())
    decisions={r['id']:r for r in json.loads((ROOT/'tools/data/bc_art_resolved_decisions.json').read_text())['decisions']}
    initial=json.loads((ROOT/'.local/bc-asset-matching-review/enemy-pose-identity/manifest.json').read_text())['records']
    attributes={(r['sprite_base_ref'],r['source_offset'],r['source_palette']):r['source_attributes'] for r in initial}
    raw=(ROOT/'res/generated/sprite_pens.bin').read_bytes()
    # Pool corresponding material pens across reviewed poses, avoiding animation
    # flicker. Gallery and gameplay palettes must never share a color recipe.
    votes=defaultdict(lambda:defaultdict(Counter)); rows=[]
    with tempfile.TemporaryDirectory() as td:
        dylib=Path(td)/'pose.dylib'
        subprocess.run(['cc','-shared','-fPIC','-I'+str(ROOT/'inc'),str(args.normal_art_source),'-o',str(dylib)],check=True)
        lib=C.CDLL(str(dylib));lib.bc_actor_pose.argtypes=[C.POINTER(Actor)];lib.bc_actor_pose.restype=C.c_uint
        for card in cards:
            dec=decisions[card['id']]
            if dec['decision']!='recolor':continue
            ref,frame,pal=identity(card['id']);a=Actor();a.sprite_base_ref=ref
            a.body.state=1;a.body.sprite_base=0x100;a.body.sprite=0x100+frame;a.body.attributes=attributes.get((ref,frame,pal),pal)
            if card['id'].startswith('sprite-0x'):a.body.attributes=int(card['id'].split('-')[-1],16)
            pose=lib.bc_actor_pose(C.byref(a));assert pose&0x80000
            size=32 if pose&0x40000 else 16;code=pose&2047;colour=pose>>11&15
            pens=pixels(raw,code,size);flips=pose>>16&3
            if flips&1:pens=pens[:,::-1]
            if flips&2:pens=pens[::-1]
            l=card['left'];s=l['size'];x=l['x'];y=l['y']
            rgb=np.array(Image.open(ROOT/'.local/bc-asset-matching-review'/l['sheet']).convert('RGB').crop((x,y,x+s,y+s)).resize((size,size),Image.Resampling.NEAREST))
            rgb=np.rint(rgb.astype(float)*7/255).astype(int)
            group=(ref,pal,colour,size,ref==0x3690 and frame in (0x10,0x30))
            for pen,target in zip(pens.flat,rgb.reshape(-1,3)):
                if pen!=15 and max(target)>0:votes[group][int(pen)][tuple(target)]+=1
            rows.append(dict(id=card['id'],family=ref,frame=frame,source_palette=pal,code=code,normal_colour=colour,size=size,provenance=dec['provenance'],group=group))
    for row in rows:
        group=row.pop('group')
        # Most frequent BC color at each Genesis material pen. This is a draft
        # color transfer from reviewed shapes, not an assertion of pixel identity.
        row['pen_targets']={str(p):[int(c) for c in counts.most_common(1)[0][0]] for p,counts in sorted(votes[group].items())}
    target=ROOT/'tools/data/bc_recolor_recipes.json'
    target.write_text(json.dumps(dict(schema=1,method='pooled corresponding material pens; fixed Genesis palette approximation',recipes=rows),indent=2)+'\n')
    print(f'Exported {len(rows)} reviewed/inferred recipes to {target}')
if __name__=='__main__':main()
