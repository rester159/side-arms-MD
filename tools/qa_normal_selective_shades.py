"""Verify exact source-color repairs and every affected shared-palette consumer."""
from pathlib import Path
import argparse,hashlib,json,struct,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from arcade_source import Source,decode_bgtiles,bgmap_cells,palette_rgb
from quantize import to_md,md_word
from bc_background_equivalence import symbols
import zones
parser=argparse.ArgumentParser();parser.add_argument('--baseline',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
recipe=json.loads((ROOT/'tools/data/normal_selective_shade_repairs.json').read_text());rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt');oldrom=(args.baseline/'rom.bin').read_bytes();oldsy=symbols(args.baseline/'symbol.txt')
assert len(rom)==len(oldrom)
assert sy==oldsy, 'Linked symbol addresses changed'
allowed=np.zeros(len(rom),dtype=bool);allowed[0x18e:0x190]=True

s=Source();m=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));codes,cols,_=bgmap_cells(s.region('bgmap'));colors=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(m[0x14a37+i],m[0x14e37+i]))))for i in range(1024)])
lut=np.array(struct.unpack_from('>512H',rom,sy['vivid_lut']))
def vivid(v):return lut[(v>>1&7)|((v>>5&7)<<3)|((v>>9&7)<<6)]
def decode(root,z,home=False):
 p=np.frombuffer((root/f'zone{z}_pal.bin').read_bytes(),'>u2');suffix='h'if home else '';a=np.frombuffer((root/f'zone{z}{suffix}_attr.bin').read_bytes(),'>u2');b=np.frombuffer((root/f'zone{z}{suffix}_tiles.bin').read_bytes(),'u1').reshape(-1,8,4);px=np.stack((b>>4,b&15),-1).reshape(-1,8,8);return p[((a>>13&1)*16)[:,None,None]+px],px!=0,a,p
reports=[]
for r in recipe['repairs']:
 z=r['zone'];before=args.baseline;after=ROOT/'res/generated'
 for name,digest in r['input_sha256'].items():
  stem=f'zone{z}h_{name[5:]}'if name.startswith('home_')else f'zone{z}_{name}';raw=(before/(stem+'.bin')).read_bytes();assert hashlib.sha256(raw).hexdigest()==digest;assert oldrom[oldsy[stem]:oldsy[stem]+len(raw)]==raw;candidate=(after/(stem+'.bin')).read_bytes();assert len(candidate)==len(raw);assert sy[stem]==oldsy[stem];assert rom[sy[stem]:sy[stem]+len(candidate)]==candidate;allowed[sy[stem]:sy[stem]+len(candidate)]=True
 old,mask,oa,op=decode(before,z);new,nmask,na,npal=decode(after,z);assert np.array_equal(mask,nmask);assert np.array_equal(oa&0xdfff,na&0xdfff);assert np.array_equal(op[1:4],npal[1:4]);assert np.array_equal(op[17:19],npal[17:19])
 x,y,w,h=zones.ZONES[z]['rect'];metas=sorted({(int(codes[yy,xx]),int(cols[yy,xx]))for yy in range(y,y+h)for xx in range(x,x+w)})
 count=0
 for meta,(cd,cl)in enumerate(metas):
  sl=slice(meta*16,(meta+1)*16)
  for k in range(16):
   n=meta*16+k;src=bg[cd,k//4*8:k//4*8+8,k%4*8:k%4*8+8];assert np.array_equal(mask[n],src!=15);source=colors[cl*16+src.astype(int)];selected=mask[n]&np.isin(source,r['source_colors'].get(str(cl),[]));assert np.array_equal(new[n][selected],source[selected]);assert np.array_equal(old[n][~selected],new[n][~selected]);count+=int((mask[n]&(old[n]!=new[n])).sum())
  for f in (lambda x:x,vivid):
   a,b=f(old[sl]),f(new[sl]);live=mask[sl]
   for value in np.unique(b[live]):assert len(np.unique(a[live&(b==value)]))<=1
 home_tiles=0
 if 'home_tiles'in r['input_sha256']:
  ho,hm,ha,_=decode(before,z,True);hn,hmm,hna,_=decode(after,z,True);assert np.array_equal(hm,hmm);assert np.array_equal(ha&0xdfff,hna&0xdfff);assert np.array_equal(ho,hn);home_tiles=len(ha)
 assert count==r['restored_pixels'];reports.append(dict(zone=z,repaired_pixels=count,home_variant_subtiles_preserved=home_tiles))
wheel_extras=[]
for name in ('wheel0_frames','wheel0h_frames','wheel1_frames','wheel1h_frames','wheel2_frames'):
 z,cx,cy,w,h,n,mp,extra,tiles,attrs=struct.unpack_from('>6HIHII',rom,sy[name])
 if not extra:continue
 def wheel_colors(data):
  palette=np.array(struct.unpack_from('>32H',data,sy[f'zone{z}_pal']))
  attributes=np.array(struct.unpack_from('>'+str(extra*16)+'H',data,attrs))
  raw=np.frombuffer(data[tiles:tiles+extra*512],'u1').reshape(-1,8,4)
  pens=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8)
  return palette[((attributes>>13&1)*16)[:,None,None]+pens]
 assert np.array_equal(wheel_colors(oldrom),wheel_colors(rom)),('wheel extra colors changed',name)
 wheel_extras.append(dict(name=name,zone=z,unchanged_subtiles=extra*16))
delta=np.frombuffer(rom,'u1')!=np.frombuffer(oldrom,'u1');assert not delta[~allowed].any(),'Unrelated ROM bytes changed'
result=dict(passed=True,offline_only=False,rom_sha256=hashlib.sha256(rom).hexdigest(),baseline_rom_sha256=hashlib.sha256(oldrom).hexdigest(),changed_rom_bytes=int(delta.sum()),only_graphics_and_checksum_changed=True,zones=reports,total_pixels=sum(r['repaired_pixels']for r in reports),scope='Independent source/linked-ROM comparison. Exact selected source colors, unchanged other pixels/opacity/geometry, fixed star pens, no new Standard/Vivid shade merges per metatile. Home variants preserve every displayed pixel. Runtime code, audio, all other graphics and symbol addresses unchanged. Native gameplay checks are separate.')
result['wheel_extra_colors']=wheel_extras
args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
