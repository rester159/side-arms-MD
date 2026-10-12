#!/usr/bin/env python3
"""Verify restored Normal machinery shades against the preceding ROM."""
import sys,json,struct,hashlib,argparse
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parent))
from arcade_source import Source,decode_bgtiles,bgmap_cells,palette_rgb
from bc_background_equivalence import symbols,compare_round,rendered_cell
from quantize import to_md,md_word
from vivid_palette import index,light
import zones
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=args.output;out.parent.mkdir(parents=True,exist_ok=True);old=(args.baseline/'rom.bin').read_bytes();rom=(root/'out/release/rom.bin').read_bytes();os=symbols(args.baseline/'symbol.txt');sy=symbols(root/'out/release/symbol.txt')
def data(r,s,name,size):return r[s[name]:s[name]+size]
for name in ['zone16_map','vivid_lut','star_tiles','star_map','spr_bank','spr_big','sprite_pal','bc_sprite_pal']:
 size=(root/f'res/generated/{name}.bin').stat().st_size
 assert data(old,os,name,size)==data(rom,sy,name,size),name
normal=0
for p in (root/'res/generated').glob('zone*.bin'):
 if p.stem in ('zone16_tiles','zone16_attr','zone16_pal'):continue
 assert data(old,os,p.stem,p.stat().st_size)==p.read_bytes()==data(rom,sy,p.stem,p.stat().st_size),p.name
 normal+=1
src=Source();m=src.region('maincpu');bg=decode_bgtiles(src.region('bgtiles'));code,col,_=bgmap_cells(src.region('bgmap'));x,y,w,h=zones.ZONES[16]['rect'];metas=sorted({(int(code[r,c]),int(col[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
colors=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(m[0x14a37+i],m[0x14e37+i]))))for i in range(1024)])
def decode(r,s):
 pal=np.array(struct.unpack_from('>32H',r,s['zone16_pal']));attrs=np.array(struct.unpack_from('>'+str(len(metas)*16)+'H',r,s['zone16_attr']));raw=np.frombuffer(data(r,s,'zone16_tiles',len(metas)*512),'u1').reshape(-1,8,4);px=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8);return pal[((attrs>>13&1)*16)[:,None,None]+px],px,pal
before,bp,opal=decode(old,os);after,ap,npal=decode(rom,sy);assert np.array_equal(bp!=0,ap!=0)
assert np.array_equal(opal[1:4],npal[1:4]);assert np.array_equal(opal[17:19],npal[17:19])
changed=blue=0;cells=set()
for meta,(cd,cl)in enumerate(metas):
 for k in range(16):
  i=meta*16+k;sp=bg[cd,k//4*8:k//4*8+8,k%4*8:k%4*8+8];source=colors[cl*16+sp.astype(int)];delta=after[i]!=before[i]
  if delta.any():
   assert cl==19;assert np.array_equal(after[i][delta],source[delta]);changed+=int(delta.sum());cells.add(meta)
  if cl==19:
   mask=(sp!=15)&((source>>9&7)>(source>>1&7))&((source>>9&7)>(source>>5&7))
   assert np.array_equal(after[i][mask],source[mask]);blue+=int(mask.sum())
assert changed==526
vivid=struct.unpack_from('>512H',rom,sy['vivid_lut'])
blue_ramp=[md_word(c) for c in [(0,0,2),(0,2,3),(0,2,4),(0,3,5)]]
for ramp in (blue_ramp,[vivid[index(c)] for c in blue_ramp]):
 assert len(set(ramp))==4 and all(light(b)>light(a)for a,b in zip(ramp,ramp[1:]))
bc=[compare_round(old,os,rom,sy,n)for n in range(1,11) if n!=8]
# R8 reuses the Normal pen ordering to improve character deduplication. Its
# palette indices may permute; compare resolved color, opacity and priority.
def r8(r,s):
 pal=struct.unpack_from('>32H',r,s['bc_bg8_palette']);entries=struct.unpack_from('>256H',r,s['bc_bg8_remap']);result={}
 for c,e in enumerate(entries):
  if e==4095:continue
  result[c]=[(bool(v and v[0]),pal[(v[1]>>13&1)*16+v[0]] if v and v[0] else 0,v[1]&0x8000 if v and v[0] else 0)for v in rendered_cell(r,s,'bc_bg8',e)]
 return result
r8_before=r8(old,os);assert r8_before==r8(rom,sy)
bc.append(dict(cells=len(r8_before)))
assert data(old,os,'bc_round8_code',65536)==data(rom,sy,'bc_round8_code',65536)
report=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_blue_pixels=blue,exact_restored_pixels=changed,changed_metatiles=sorted(cells),unchanged_normal_blobs=normal,unchanged_bc_cells=sum(r['cells']for r in bc),palette_star_slots_unchanged=True,vivid_lut_unchanged=True,transparent_mask_unchanged=True)
out.write_text(json.dumps(report,indent=2)+'\n');print(report)
