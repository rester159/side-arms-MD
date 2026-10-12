#!/usr/bin/env python3
"""Verify source-exact material repairs and unchanged surrounding linked art."""
import argparse,hashlib,json,struct,subprocess,sys
from pathlib import Path
import numpy as np
from arcade_source import ROOT,Source,decode_bgtiles,bgmap_cells,palette_rgb
from bc_background_equivalence import symbols,rendered_cell
from quantize import to_md,md_word
from vivid_palette import index,light
import zones

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--zones',type=int,nargs='+');p.add_argument('--sprite-shade-baseline',type=Path,help='Explicit pre-repair sprite banks; independently verify exact Normal shade exceptions');p.add_argument('--selective-shade-baseline',type=Path,help='Verify the selective repacking layer independently, then check preceding material repairs against its exact input ROM');a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();rom=(ROOT/'out/release/rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt');sy=symbols(ROOT/'out/release/symbol.txt')
actual_rom_hash=hashlib.sha256(rom).hexdigest();selective_shades=None;selective_inputs={}
if a.selective_shade_baseline:
 selective_output=a.output.with_name(a.output.stem+'-selective.json')
 subprocess.run([sys.executable,str(ROOT/'tools/qa_normal_selective_shades.py'),'--baseline',str(a.selective_shade_baseline),'--output',str(selective_output)],check=True)
 selective_shades=json.loads(selective_output.read_text())
 assert selective_shades['rom_sha256']==actual_rom_hash and selective_shades['only_graphics_and_checksum_changed']
 rom=(a.selective_shade_baseline/'rom.bin').read_bytes();assert hashlib.sha256(rom).hexdigest()==selective_shades['baseline_rom_sha256']
 # The independent verifier requires identical symbol addresses and proves
 # every byte outside these exact graphics/checksum ranges is unchanged.
 for repair in json.loads((ROOT/'tools/data/normal_selective_shade_repairs.json').read_text())['repairs']:
  z=repair['zone']
  for name in repair['input_sha256']:
   stem=f'zone{z}h_{name[5:]}'if name.startswith('home_')else f'zone{z}_{name}'
   selective_inputs[stem]=(a.selective_shade_baseline/(stem+'.bin')).read_bytes()
recipes=json.loads((ROOT/'tools/data/normal_background_shade_repairs.json').read_text())['repairs']
if a.zones:recipes=[r for r in recipes if r['zone'] in a.zones]
changed_names={f'zone{r["zone"]}_{suffix}'for r in recipes for suffix in ('tiles','attr','pal')}
sprite_shades=None
if a.sprite_shade_baseline:
 from qa_normal_sprite_shades import verify
 sprite_shades=verify(a.sprite_shade_baseline)
 for name in ('sprite_pal','spr_bank','spr_big'):
  prior=(a.sprite_shade_baseline/(name+'.bin')).read_bytes()
  assert old[os[name]:os[name]+len(prior)]==prior,('sprite baseline differs from historical ROM',name)
  changed_names.add(name)
refits=[]
for zone in (6,19,20):
 changed_names.update(f'zone{zone}_{suffix}' for suffix in ('tiles','attr','pal'))
 refit_output=a.output.with_name(a.output.stem+f'-zone{zone}.json')
 subprocess.run([sys.executable,str(ROOT/'tools/qa_normal_zone6_palette_fit.py'),
                '--baseline',str(a.baseline),'--output',str(refit_output),'--zone',str(zone),'--art-only'],check=True)
 refits.append(json.loads(refit_output.read_text()))
verified=0
for path in (ROOT/'res/generated').glob('*.bin'):
 name=path.stem
 if any(name == f'zone{z}_{suffix}' for z in zones.SCENE_ONLY_ZONES
        for suffix in ('tiles','attr','map','pal')):
  assert name not in sy
  continue
 if not name.startswith('zone') and name not in ('vivid_lut','star_tiles','star_map','spr_bank','spr_big','sprite_pal','bc_sprite_pal'):continue
 raw=selective_inputs.get(name,path.read_bytes());assert rom[sy[name]:sy[name]+len(raw)]==raw,name
 if name not in changed_names:assert old[os[name]:os[name]+len(raw)]==raw,name
 verified+=1
s=Source();m=s.region('maincpu');bg=decode_bgtiles(s.region('bgtiles'));code,col,_=bgmap_cells(s.region('bgmap'))
colors=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(m[0x14a37+i],m[0x14e37+i]))))for i in range(1024)])
import zones
reports=[]
local_repairs={r['zone']:r for r in json.loads((ROOT/'tools/data/normal_local_shade_repairs.json').read_text())['repairs']}
vivid=struct.unpack_from('>512H',rom,sy['vivid_lut'])
for recipe in recipes:
 z=recipe['zone'];x,y,w,h=zones.ZONES[z]['rect'];metas=sorted({(int(code[r,c]),int(col[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
 def decode(r,s):
  pal=np.array(struct.unpack_from('>32H',r,s[f'zone{z}_pal']));attrs=np.array(struct.unpack_from('>'+str(len(metas)*16)+'H',r,s[f'zone{z}_attr']));start=s[f'zone{z}_tiles'];raw=np.frombuffer(r[start:start+len(metas)*512],'u1').reshape(-1,8,4);px=np.stack((raw>>4,raw&15),-1).reshape(-1,8,8)
  return pal[((attrs>>13&1)*16)[:,None,None]+px],px,pal,attrs
 before,bp,opal,oa=decode(old,os);after,ap,npal,na=decode(rom,sy)
 assert np.array_equal(bp!=0,ap!=0);assert np.array_equal(oa&~0x2000,na&~0x2000)
 assert np.array_equal(opal[1:4],npal[1:4])and np.array_equal(opal[17:19],npal[17:19])
 restored=checked=0;changed=[];source_words=set()
 for meta,(cd,cl)in enumerate(metas):
  for k in range(16):
   i=meta*16+k;sp=bg[cd,k//4*8:k//4*8+8,k%4*8:k%4*8+8];source=colors[cl*16+sp.astype(int)];live=sp!=15;delta=after[i]!=before[i]
   selected=live if cl in recipe.get('source_palettes',[]) else live & np.isin(source,recipe.get('source_colors',{}).get(str(cl),[]))
   for local in local_repairs.get(z,{}).get('changes',[]):
    if local['meta']==meta and local['subtile']==k:
     selected |= live & np.isin(source,local['source_words'])
   assert np.array_equal(after[i][selected],source[selected]),(z,meta,k,'source shade')
   checked+=int(selected.sum())
   source_words.update(map(int,source[selected]))
   assert not delta[~selected].any(),(z,meta,k,'unrelated material')
   if delta.any():
    assert np.array_equal(after[i][delta],source[delta]);count=int(delta.sum());restored+=count;changed.append([meta,k,count])
  prior=before[meta*16:(meta+1)*16];current=after[meta*16:(meta+1)*16];opaque=bp[meta*16:(meta+1)*16]!=0
  for value in np.unique(current[opaque]):
   assert len(np.unique(prior[opaque & (current==value)]))<=1,(z,meta,'merged existing shades',int(value))
  if recipe.get('source_colors'):
   lut=np.array(vivid);lookup=lambda v:lut[(v>>1&7)|((v>>5&7)<<3)|((v>>9&7)<<6)]
   old_vivid=lookup(prior);new_vivid=lookup(current)
   for value in np.unique(new_vivid[opaque]):
    assert len(np.unique(old_vivid[opaque & (new_vivid==value)]))<=1,(z,meta,'Vivid merged existing shades',int(value))
 assert restored==recipe['restored_pixels']+local_repairs.get(z,{}).get('repaired_pixels',0),(z,restored)
 ordered=0
 for lo in source_words:
  for hi in source_words:
   if lo==hi:continue
   rgb=lambda v:(v>>1&7,v>>5&7,v>>9&7)
   if all(x<=y for x,y in zip(rgb(lo),rgb(hi))):
    assert light(vivid[index(lo)])<light(vivid[index(hi)]),(z,'Vivid shade collapse',lo,hi)
    ordered+=1
 reports.append(dict(zone=z,source_pixels=checked,restored_pixels=restored,ordered_vivid_shade_pairs=ordered,changes=changed))
def bc_cells(r,s,n):
 prefix='bc_bg'+(str(n)if n>1 else '');pal=struct.unpack_from('>32H',r,s[prefix+'_palette']);entries=struct.unpack_from('>256H',r,s[prefix+'_remap']);result={}
 for c,e in enumerate(entries):
  if e==4095:continue
  result[c]=[(bool(v and v[0]),pal[(v[1]>>13&1)*16+v[0]]if v and v[0]else 0,v[1]&0x8000 if v and v[0]else 0)for v in rendered_cell(r,s,prefix,e)]
 return result
bc_count=0
for n in range(1,11):
 baseline=bc_cells(old,os,n);assert baseline==bc_cells(rom,sy,n),('BC rendered art changed',n);bc_count+=len(baseline)
 name=f'bc_round{n}_code';assert old[os[name]:os[name]+65536]==rom[sy[name]:sy[name]+65536]
result=dict(passed=True,exact_repairs_no_existing_shade_merges=True,refit_no_new_source_pair_merges=True,rom_sha256=actual_rom_hash,material_layer_rom_sha256=hashlib.sha256(rom).hexdigest(),selective_shades=selective_shades,zones=reports,source_pair_refits=refits,unchanged_bc_cells=bc_count,linked_blobs_verified=verified,vivid_lut_unchanged=True,stars_unchanged=True,source_collision_unchanged=True)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({**result,'zones':[{k:v for k,v in r.items()if k!='changes'}for r in reports]},indent=2))
