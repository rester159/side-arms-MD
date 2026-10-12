import sys,json,struct,collections
from pathlib import Path
from qa_bc_factory import actor
root=Path(__file__).resolve().parents[1];gen=json.loads((root/'res/generated/bc_boss_shots.json').read_text());beam=json.loads((root/'tools/data/bc_beam_shapes.json').read_text())['shapes'];unique=json.loads((root/'tools/data/bc_unique_shapes.json').read_text())['shapes'];lookup={(r['family'],r['frame'],r['source_palette']):r for r in beam+unique+gen}
counts=collections.Counter();bad={};unknown={}
for name in ['actor-step-hopper','round2-ending','round3-defeat','round4-defeat','round5-ending','round6-defeat','round7-defeat','round8-defeat','round9-final','round10-protected']:
 folder=root/'.local/pce-reference'/name;code=(folder/'code-002160.bin').read_bytes()
 for f in sorted(folder.glob('*-ram.bin')):
  ram=f.read_bytes();a=actor(ram,0,code)
  boss=bool(a.body.state and a.body.flags&8 and a.sprite_base_ref in range(0x36b6,0x36c7,2))
  final=any(actor(ram,j,code).body.state and actor(ram,j,code).sprite_base_ref in (0x36d0,0x36d2,0x36d4) for j in range(8))
  vram=struct.unpack('<32768H',f.with_name(f.name.replace('-ram','-vram')).read_bytes())
  for slot in range(1,32):
   a=actor(ram,slot,code);b=a.body
   if b.state!=128 or b.flags&8 or b.sprite in (0,255) or a.sprite_base_ref not in (0x3682,0x3698,0x36cc,0x36b4,0x36c8,0x36ce):continue
   if not (boss or final or a.sprite_base_ref==0x36b4):continue
   key=(a.sprite_base_ref,b.sprite-b.sprite_base,b.attributes&15);rec=lookup.get(key)
   if rec is None:unknown.setdefault(str(key),(name,f.name,slot));continue
   pattern=b.sprite>>1
   rows=[''.join(format(sum(((vram[pattern*64+y+c*16]>>(15-x))&1)<<c for c in range(4)),'x')for x in range(16))for y in range(16)]
   if key[0]==0x36cc:rows=[''.join('5' if x=='7' else x for x in row)for row in rows]
   if rows!=rec['rows']:bad.setdefault(str(key),(name,f.name,slot,rows,rec['rows']))
   else:counts[hex(key[0])]+=1
result=dict(verified=dict(counts),unknown=unknown,mismatch=bad)
(root/'.local/bc-shared-attack-audit.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
assert not unknown and not bad
