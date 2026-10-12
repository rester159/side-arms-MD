"""Verify exact shared-palette background repairs against a retained build."""
from pathlib import Path
import json,sys,itertools,argparse,hashlib
import numpy as np
sys.path.insert(0,'tools')
from arcade_source import Source,decode_bgtiles,bgmap_cells,palette_rgb
from quantize import to_md,md_word
import zones,parallax_split
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();p=args.baseline;report=json.loads(Path('tools/data/normal_background_sprite_palette_repairs.json').read_text());s=Source();main=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));code,col,flags=bgmap_cells(s.region('bgmap'));colors=np.array([md_word(to_md(tuple(c//17 for c in palette_rgb(main[0x14a37+i],main[0x14e37+i]))))for i in range(1024)],np.uint16);sprite=np.fromfile('res/generated/sprite_pal.bin','>u2');lut=np.fromfile('res/generated/vivid_lut.bin','>u2')
def rgb(w):return np.stack((w>>1&7,w>>5&7,w>>9&7),-1).astype(int)
def vivid(w):return lut[(w>>1&7)|((w>>5&7)<<3)|((w>>9&7)<<6)]
def lum(w):return 3*(w>>1&7)+6*(w>>5&7)+(w>>9&7)
def merged_pairs(src,dst,mask):
 result=set()
 for value in np.unique(dst[mask]):result.update(itertools.combinations(sorted(map(int,np.unique(src[mask&(dst==value)]))),2))
 return result
def decode(folder,stem,pal):
 raw=np.fromfile(folder/(stem+'_tiles.bin'),'u1').reshape(-1,8,4);pens=np.empty((len(raw),8,8),np.uint8);pens[:,:,::2]=raw>>4;pens[:,:,1::2]=raw&15;attrs=np.fromfile(folder/(stem+'_attr.bin'),'>u2');return pal[((attrs>>13&3)*16)[:,None,None]+pens],pens!=0,attrs
rows=[]
for record in report['records']:
 z=record['zone'];kind=record['kind'];stem=f'zone{z}'+('h'if kind=='home'else'')
 if not record['changes']:continue
 x,y,w,h=zones.ZONES[z]['rect'];metas=sorted({(int(code[r,c]),int(col[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
 patterns=[(i,bg[cd])for i,(cd,cl)in enumerate(metas)]
 if kind=='home':patterns,_=parallax_split.home_variant(z,code,col,flags,{key:i for i,key in enumerate(metas)},lambda cl:min(range(15),key=lambda n:sum(rgb(colors[cl*16+n]))))
 palette=np.concatenate((np.fromfile(f'res/generated/zone{z}_pal.bin','>u2'),sprite));old,mask,attrs=decode(p/'res/generated',stem,palette);new,live,na=decode(Path('res/generated'),stem,palette);assert np.array_equal(mask,live);assert np.array_equal(attrs&0x9fff,na&0x9fff)
 for m,(owner,pattern)in enumerate(patterns):
  sl=slice(m*16,(m+1)*16);before=old[sl];after=new[sl];valid=live[sl];src=np.array([colors[metas[owner][1]*16+pattern[k//4*8:k//4*8+8,k%4*8:k%4*8+8].astype(int)]for k in range(16)]);changed=valid&(before!=after);assert np.array_equal(after[changed],src[changed]);inversions=[]
  values=np.unique(src[valid])
  for mode,convert in [('standard',lambda a:a),('vivid',vivid)]:
   assert not (merged_pairs(src,convert(after),valid)-merged_pairs(src,convert(before),valid)),(z,kind,m,mode,'new source-pair merge')
   a=lum(convert(before));b=lum(convert(after))
   for lo in values:
    for hi in values:
     if not(np.all(rgb(lo)<=rgb(hi))and np.any(rgb(lo)<rgb(hi))):continue
     ml=valid&(src==lo);mh=valid&(src==hi)
     if a[ml].max()<=a[mh].min()and b[ml].max()>b[mh].min():inversions.append(dict(mode=mode,source_words=[int(lo),int(hi)]))
  if changed.any()or inversions:rows.append(dict(zone=z,kind=kind,meta=m,exact_pixels=int(changed.sum()),new_brightness_inversions=inversions))
assert not any(r['new_brightness_inversions']for r in rows)
assert sum(r['exact_pixels']for r in rows)==117
result=dict(passed=not any(r['new_brightness_inversions']for r in rows),rows=rows,scope='Independent decode of proposed and retained pixels with all4 palette-bank bits; exact changed-source RGB3, same opacity/non-palette template bits, no new source-pair merges and componentwise-source brightness ordering in Standard/Vivid.')
from bc_background_equivalence import symbols,compare_round
before=(p/'out/release/rom.bin').read_bytes();after=Path('out/release/rom.bin').read_bytes();bs=symbols(p/'out/release/symbol.txt');cs=symbols(Path('out/release/symbol.txt'))
allowed={f"zone{r['zone']}"+('h'if r['kind']=='home'else'')+'_'+suffix for r in report['records']for suffix in ('tiles','attr')}
changed=[];unchanged=[]
old_files={f.stem:f for f in (p/'res/generated').glob('*.bin')};new_files={f.stem:f for f in Path('res/generated').glob('*.bin')}
assert {n for n in old_files if n in bs}=={n for n in new_files if n in cs}
for name,f in old_files.items():
 if name not in bs:continue
 a=f.read_bytes();b=new_files[name].read_bytes();assert len(a)==len(b);assert before[bs[name]:bs[name]+len(a)]==a;assert after[cs[name]:cs[name]+len(b)]==b
 if a!=b:
  assert name in allowed,name
  changed.append(name)
 else:unchanged.append(name)
assert set(changed)==allowed
result.update(rom_sha256=hashlib.sha256(after).hexdigest(),baseline_rom_sha256=hashlib.sha256(before).hexdigest(),changed_blobs=changed,unchanged_blobs=unchanged,bc_rounds=[compare_round(before,bs,after,cs,n)for n in range(1,11)])
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print('exact pixels',sum(r['exact_pixels']for r in rows),'linked BC rounds',len(result['bc_rounds']))
