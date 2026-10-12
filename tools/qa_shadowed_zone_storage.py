"""Verify omitted Normal zone storage and unchanged retained generated assets."""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from bc_background_equivalence import symbols
from arcade_source import ROOT
import zones

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();new=(ROOT/'out/release/rom.bin').read_bytes()
os=symbols(a.baseline/'symbol.txt');ns=symbols(ROOT/'out/release/symbol.txt')
assert len(old)==len(new)==4194304
omitted={f'zone{z}_{s}'for z in zones.SHADOWED_ZONE_PARENTS for s in ('tiles','attr','map','pal')}
omitted|={f'zone{z}h_{s}'for z in zones.SHADOWED_ZONE_PARENTS for s in ('tiles','attr','map')}
assert zones.SHADOWED_ZONE_PARENTS=={2:1},'Additional omissions require independent reachability review'
checked=[];removed=[]
for file in sorted((ROOT/'res/generated').glob('*.bin')):
 name=file.stem;raw=file.read_bytes()
 if name in omitted:
  assert name in os and name not in ns,name
  assert old[os[name]:os[name]+len(raw)]==raw,('Offline omitted source changed',name)
  removed.append(dict(name=name,bytes=len(raw)))
 elif name in os or name in ns:
  assert name in os and name in ns,('Unexpected linked asset addition/removal',name)
  assert old[os[name]:os[name]+len(raw)]==raw,('Baseline/generated mismatch',name)
  assert new[ns[name]:ns[name]+len(raw)]==raw,('Candidate/generated mismatch',name)
  checked.append(name)
assert {r['name']for r in removed}==omitted
count=int(re.search(r'#define ZONE_COUNT (\d+)',(ROOT/'inc/gen/assets.h').read_text()).group(1))
def geometry(rom,sy):
 return [struct.unpack_from('>5H',rom,sy['zones']+i*26)for i in range(count)]
before=geometry(old,os);after=geometry(new,ns)
for i,(b,c)in enumerate(zip(before,after)):
 if i in zones.SHADOWED_ZONE_PARENTS:
  assert new[ns['zones']+i*26:ns['zones']+(i+1)*26]==bytes(26)
  j=zones.SHADOWED_ZONE_PARENTS[i];x,y,w,h,_=b;px,py,pw,ph,_=before[j]
  assert j<i and px<=x and py<=y and px+pw>=x+w and py+ph>=y+h
 else:assert b==c,('Other zone geometry changed',i)
# Exhaust camera-centre cells covering all zone rectangles plus an outer border.
xs=range(min(r[0]for r in before)-1,max(r[0]+r[2]for r in before)+1)
ys=range(min(r[1]for r in before)-1,max(r[1]+r[3]for r in before)+1)
def select(rects,x,y):
 return next((i for i,(rx,ry,w,h,n)in enumerate(rects)if rx<=x<rx+w and ry<=y<ry+h),None)
points=0
for x in xs:
 for y in ys:
  assert select(before,x,y)==select(after,x,y),(x,y)
  points+=1
# Ordinary selection cannot enter zone 2; explicit wheel selection must not either.
frames=[]
for name in ('wheel0_frames','wheel0h_frames','wheel1_frames','wheel1h_frames','wheel2_frames'):
 bd=struct.unpack_from('>6HIHII',old,os[name]);cd=struct.unpack_from('>6HIHII',new,ns[name])
 b,c=bd[0],cd[0]
 assert b==c and c not in zones.SHADOWED_ZONE_PARENTS
 assert bd[:6]==cd[:6] and bd[7]==cd[7],('Wheel descriptor changed',name)
 for field,size in ((6,bd[3]*bd[4]*bd[5]*2),(8,bd[7]*512),(9,bd[7]*32)):
  assert old[bd[field]:bd[field]+size]==new[cd[field]:cd[field]+size],('Wheel art changed',name,field)
 frames.append(dict(name=name,zone=c))
for i in range(count):
 bp=struct.unpack_from('>I',old,os['zone_home']+i*4)[0]
 cp=struct.unpack_from('>I',new,ns['zone_home']+i*4)[0]
 if i in zones.SHADOWED_ZONE_PARENTS:assert bp and not cp
 else:
  assert bool(bp)==bool(cp)
  if bp:assert old[bp:bp+10]==new[cp:cp+10] and old[bp+26:bp+28]==new[cp+26:cp+28]
result=dict(passed=True,rom_sha256=hashlib.sha256(new).hexdigest(),baseline_rom_sha256=hashlib.sha256(old).hexdigest(),removed=removed,removed_payload_bytes=sum(r['bytes']for r in removed),unchanged_linked_generated_blobs=len(checked),unchanged_blob_names=checked,equal_camera_selector_points=points,wheel_selectors=frames,scope='Zone2 zero descriptor/Home pointer; all other geometry and first-containing camera selections unchanged; no wheel selector enters omitted zone. All retained generated linked blobs and offline omitted sources match baseline byte-for-byte. This does not certify actor-code changes or replace native campaigns.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items()if k!='unchanged_blob_names'},indent=2))
