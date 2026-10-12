#!/usr/bin/env python3
"""Verify R1 ledge shade ordering, fixed contours and cross-round isolation."""
from pathlib import Path
import sys,json,struct,hashlib,argparse
from PIL import Image
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from bc_background_equivalence import symbols,rendered_cell,compare_round
from vivid_palette import index,light
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
p=args.output;p.mkdir(parents=True,exist_ok=True);old=(args.baseline/'rom.bin').read_bytes();new=(root/'out/release/rom.bin').read_bytes();os=symbols(args.baseline/'symbol.txt');ns=symbols(root/'out/release/symbol.txt')
changed=[];pixels=0;warm=0
palold=struct.unpack_from('>32H',old,os['bc_bg_palette']);palnew=struct.unpack_from('>32H',new,ns['bc_bg_palette']);assert palold[:31]==palnew[:31] and palnew[31]==0x464
lut=struct.unpack_from('>512H',new,ns['vivid_lut']);assert old[os['vivid_lut']:os['vivid_lut']+1024]==new[ns['vivid_lut']:ns['vivid_lut']+1024]
def cell(rom,s,c):
 e=struct.unpack_from('>H',rom,s['bc_bg_remap']+c*2)[0];return rendered_cell(rom,s,'bc_bg',e)
def image(rom,s,c,vivid=False):
 pal=struct.unpack_from('>32H',rom,s['bc_bg_palette']);colors=[]
 for v in cell(rom,s,c):
  w=pal[(v[1]>>13&1)*16+v[0]] if v and v[0] else 0
  if vivid:w=lut[index(w)]
  colors.append(tuple((w>>shift&7)*36 for shift in (1,5,9)))
 im=Image.new('RGB',(32,32));im.putdata(colors);return im
for c in range(63):
 a=cell(old,os,c);b=cell(new,ns,c)
 assert all(bool(x and x[0])==bool(y and y[0]) for x,y in zip(a,b)),('opacity',c)
 for x,y in zip(a,b):
  if x and x[0] in (1,2,12,13,14) and x[1]&0x2000:
   assert x==y,('warm material',c);warm+=1
 if a!=b:
  changed.append(c);pixels+=sum(x!=y for x,y in zip(a,b))
assert set(changed)=={32,33,34,58,59},changed
others=[compare_round(old,os,new,ns,n)for n in range(2,11)]
normal=0
for f in (root/'res/generated').glob('zone*.bin'):
 if f.stem in os and f.stem in ns:
  raw=f.read_bytes();assert old[os[f.stem]:os[f.stem]+len(raw)]==new[ns[f.stem]:ns[f.stem]+len(raw)]==raw;normal+=1
for n in range(1,11):
 k=f'bc_round{n}_code';assert old[os[k]:os[k]+65536]==new[ns[k]:ns[k]+65536]
d=json.loads((root/'tools/data/bc_background_r1_contours.json').read_text())
from arcade_source import Source, decode_bgtiles, bgmap_cells
from bc_background_r1 import _inside
import zones
src=Source();codes,colors,_=bgmap_cells(src.region('bgmap'))
x,y,w,h=zones.ZONES[0]['rect']
metas=sorted({(int(codes[j,i]),int(colors[j,i]))for j in range(y,y+h)for i in range(x,x+w)})
assert metas[34]==(30,0), 'Normal donor identity changed'
source=decode_bgtiles(src.region('bgtiles'))[30]
levels={2:0,3:1,4:2,5:3}
stone_pixels=0
for text,left in d['cell_crops'].items():
 actual=cell(new,ns,int(text,16))
 for y in range(32):
  for x in range(32):
   sx=left+x
   if sx>=80:sx-=80
   if _inside(sx,y,d['warm_outline']):continue
   ramp=d['stone_base_ramp']
   for layer in d['stone_relief']:
    if _inside(sx,y,layer['points']):ramp=layer['ramp']
   expected=ramp[levels[int(source[y,sx%32])]]
   value=actual[y*32+x]
   assert value and value[0]==expected and value[1]&0x2000, (text,x,y,'source texture')
   stone_pixels+=1
for ramp in [d['stone_base_ramp']]+[r['ramp']for r in d['stone_relief']]:
 for vivid in (False,True):
  words=[palnew[16+v]for v in ramp]
  if vivid:words=[lut[index(w)]for w in words]
  assert len(set(words))==4 and all(light(x)<light(y)for x,y in zip(words,words[1:])),(ramp,words)
for name,rom,s,vivid in [('before',old,os,False),('current',new,ns,False),('vivid',new,ns,True)]:
 im=Image.new('RGB',(96,32))
 for i,c in enumerate((32,33,34)):im.paste(image(rom,s,c,vivid),(i*32,0))
 im.save(p/(name+'.png'))
r=dict(passed=True,rom_sha256=hashlib.sha256(new).hexdigest(),changed_cells=changed,changed_pixels=pixels,source_stone_pixels=stone_pixels,preserved_opacity_pixels=63*1024,preserved_warm_pixels=warm,other_round_cells_unchanged=sum(x['cells']for x in others),normal_blobs_unchanged=normal,source_banks_unchanged=10,standard_vivid_ramp_levels=4,vivid_lut_unchanged=True)
(p/'isolation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
