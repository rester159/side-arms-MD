"""Verify the partial zone0/5 shade repairs against its retained input cartridge."""
from pathlib import Path
import json,sys,struct,itertools,argparse,hashlib
import numpy as np
sys.path.insert(0,'tools')
from arcade_source import Source,decode_bgtiles,bgmap_cells,palette_rgb
from quantize import to_md,md_word,_dist
import parallax_split,zones
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();baseline=str(args.baseline/'res/generated')+'/';folder=args.output.parent;folder.mkdir(parents=True,exist_ok=True);s=Source();main=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));code,col,flags=bgmap_cells(s.region('bgmap'));md=np.array([to_md(tuple(int(c)//17 for c in palette_rgb(main[0x14a37+i],main[0x14e37+i])))for i in range(1024)])
records=[]
for z in (0,5):
 x,y,w,h=zones.ZONES[z]['rect'];metas=sorted({(int(code[r,c]),int(col[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
 words=np.fromfile(baseline+f'zone{z}_pal.bin','>u2');pal=np.array([(v>>1&7,v>>5&7,v>>9&7)for v in words]);proposal=np.array([[(v>>1&7,v>>5&7,v>>9&7)for v in b]for b in json.loads(Path(f'tools/data/normal_zone{z}_palette_fit.json').read_text())['banks']]);lut=np.fromfile(baseline+'vivid_lut.bin','>u2')
 def packed(a):return a[...,0]*2+a[...,1]*32+a[...,2]*512
 def vivid(a):return lut[a[...,0]+a[...,1]*8+a[...,2]*64]
 def pairs(src,dst,mask):
  out=set()
  for v in np.unique(dst[mask]):out.update(itertools.combinations(sorted(map(int,np.unique(src[mask&(dst==v)]))),2))
  return out
 assert z not in parallax_split.home_zones() and z not in parallax_split.far_layers()

 for kind,patterns,prefix in [('base',[(i,bg[cd])for i,(cd,cl)in enumerate(metas)],f'zone{z}')]:
  raw=np.fromfile(baseline+''+prefix+'_tiles.bin','u1').reshape(-1,8,4);pens=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8);attrs=np.fromfile(baseline+''+prefix+'_attr.bin','>u2')
  cr=np.fromfile('res/generated/'+prefix+'_tiles.bin','u1').reshape(-1,8,4);cp=np.stack((cr>>4,cr&15),-1).reshape(-1,8,8);cattrs=np.fromfile('res/generated/'+prefix+'_attr.bin','>u2');cw=np.fromfile(f'res/generated/zone{z}_pal.bin','>u2');cpl=np.array([(w>>1&7,w>>5&7,w>>9&7)for w in cw]);assert np.array_equal(cattrs,attrs)
  for m,(owner,pattern)in enumerate(patterns):
   src=[];old=[];new=[];live=[]
   for k in range(16):
    i=m*16+k;b=int(attrs[i]>>13&1);sp=pattern[k//4*8:k//4*8+8,k%4*8:k%4*8+8];rgb=md[metas[owner][1]*16+sp.astype(int)];src.append(rgb);old.append(pal[b*16+pens[i]]);new.append(proposal[b][_dist(rgb.reshape(-1,3),proposal[b]).argmin(1)].reshape(8,8,3));live.append(sp!=15)
   src=np.array(src);old=np.array(old);new=np.array(new);live=np.array(live);sw=packed(src);row=dict(zone=z,kind=kind,meta=m,owner=owner)
   for mode,convert in [('standard',packed),('vivid',vivid)]:
    before=pairs(sw,convert(old),live);after=pairs(sw,convert(new),live);row[mode]=dict(new_source_pair_merges=len(after-before),removed_source_pair_merges=len(before-after))
   ordering={}
   source_colors=np.unique(src[live],axis=0)
   for mode,convert in [('standard',packed),('vivid',vivid)]:
    ow=convert(old);nw=convert(new)
    luma=lambda words:3*(words>>1&7)+6*(words>>5&7)+(words>>9&7)
    ol=luma(ow);nl=luma(nw);checked=0;broken=[]
    for ca in source_colors:
     for cb in source_colors:
      if not(np.all(ca<=cb)and np.any(ca<cb)):continue
      ma=live&np.all(src==ca,axis=-1);mb=live&np.all(src==cb,axis=-1)
      if ol[ma].max()<=ol[mb].min():
       checked+=1
       if nl[ma].max()>nl[mb].min():broken.append([list(map(int,ca)),list(map(int,cb))])
    ordering[mode]=dict(ordered_source_pairs_checked=checked,new_luminance_inversions=broken)
   row['ordering']=ordering
   actual=np.array([cpl[(int(cattrs[m*16+k])>>13&1)*16+cp[m*16+k]]for k in range(16)])
   assert np.array_equal(cp[m*16:(m+1)*16]!=0,live),(kind,m,'opacity')
   assert np.array_equal(actual[live],new[live]),(kind,m,'expected source-fit pixels')
   records.append(row)
 assert all(not r[m]['new_source_pair_merges'] and not r['ordering'][m]['new_luminance_inversions']for r in records for m in ('standard','vivid'))
from bc_background_equivalence import symbols
before=(args.baseline/'out/release/rom.bin').read_bytes();current=Path('out/release/rom.bin').read_bytes();bs=symbols(args.baseline/'out/release/symbol.txt');cs=symbols(Path('out/release/symbol.txt'))
assert len(before)==len(current)==4194304
allowed={'zone0_tiles','zone0_pal','zone5_tiles','zone5_pal'};changed=[];unchanged=[]
baseline_files={f.stem:f for f in (args.baseline/'res/generated').glob('*.bin')}
current_files={f.stem:f for f in Path('res/generated').glob('*.bin')}
assert {name for name in baseline_files if name in bs} == {name for name in current_files if name in cs}, 'Linked resource additions/removals require separate review'
for f in (args.baseline/'res/generated').glob('*.bin'):
 if f.stem not in cs:continue
 oldbytes=f.read_bytes();newbytes=Path('res/generated',f.name).read_bytes();assert len(oldbytes)==len(newbytes)
 assert before[bs[f.stem]:bs[f.stem]+len(oldbytes)]==oldbytes
 assert current[cs[f.stem]:cs[f.stem]+len(newbytes)]==newbytes
 if oldbytes!=newbytes:
  assert f.stem in allowed,f.name
  changed.append(f.stem)
 else:unchanged.append(f.stem)
assert allowed==set(changed)
# Normal patterns may be reused by BC. Repacking its shared bank relocates
# code/data, so verify BC materials by resolved source pointers instead.
from bc_background_equivalence import compare_round
bc_rounds=[compare_round(before,bs,current,cs,n) for n in range(1,11)]
summary={str(z):{mode:{field:sum(r[mode][field]for r in records if r['zone']==z)for field in ('new_source_pair_merges','removed_source_pair_merges')}for mode in ('standard','vivid')}for z in (0,5)}
out=dict(passed=True,rom_sha256=hashlib.sha256(current).hexdigest(),baseline_rom_sha256=hashlib.sha256(before).hexdigest(),summary=summary,records=records,changed_blobs=sorted(changed),unchanged_linked_blobs=sorted(unchanged),bc_rounds=bc_rounds,scope='Independent source-fit pixels and opacity; no new source-pair merges or tested componentwise-source luminance reversals in Standard/Vivid. Same attributes and global Vivid LUT; resolved BC cell pens, palettes and collision data match. All other linked binary artwork matches. Shared BC storage repacks and code/data relocate; code/timing equivalence requires native checks. No Home/far layers use these zones. Native visuals and subjective completeness separate.')
args.output.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(dict(passed=True,rom_sha256=out['rom_sha256'],summary=summary,changed_blobs=changed)))
