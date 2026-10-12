#!/usr/bin/env python3
"""Replay PCE boss collision/phase observations against the current native rules.

Requires local oracle traces. Samples each distinct part/pose/protection state,
retains health/state transitions, and checks complete before/after actor tasks.
This is source parity, not a claim of exhaustive gameplay or physical hardware QA.
"""
import argparse, collections, hashlib, json, mmap, struct
from pathlib import Path
from qa_bc_actor_step import verify
from bc_background_equivalence import symbols

ROOT=Path(__file__).resolve().parents[1]
CAPTURES={
 1:['boss-loop-natural','boss-defeat-task'],
 2:['round2-ending','round2-defeat'],
 3:['round3-cycle','round3-defeat'],
 4:['round4-defeat'],
 5:['round5-ending','round5-defeat'],
 6:['round6-defeat'],
 7:['round7-defeat'],
 8:['round8-boss-opening','round8-defeat'],
 9:['round9-first-defeat','round9-second-defeat','round9-third-defeat',
    'round9-fourth-defeat','round9-fifth-defeat-short','round9-sixth-defeat',
    'round9-seventh','round9-eighth','round9-final'],
 10:['round10-opening','round10-head','round10-ending-clean'],
}
STRIDE=8198

def word(r,hi,lo,i):return r[hi+i]*256+r[lo+i]
def boss_ref(ref):return 0x36b6<=ref<=0x36c6 and not ref&1 or ref in (0x36d0,0x36d2,0x36d4)

def run(output):
 output.mkdir(parents=True,exist_ok=True)
 rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
 report={'rom_sha256':hashlib.sha256(rom).hexdigest(),'rounds':[],
         'scope':'PCE sampled full-task before/after replay, including actual collision results and boss phases. Not exhaustive gameplay.'}
 for number,folders in CAPTURES.items():
  group=output/f'round{number}';group.mkdir(exist_ok=True)
  counts=collections.Counter();parts={};hazards={};sources=[];kept=changes=skipped=0
  code=rom[sy[f'bc_round{number}_code']:sy[f'bc_round{number}_code']+65536]
  (group/'code.bin').write_bytes(code)
  with (group/'actor-step.bin').open('wb')as dest:
   for name in folders:
    capture=ROOT/'.local/pce-reference'/name;path=capture/'actor-step.bin'
    source_code=capture/'code-002160.bin'
    assert source_code.read_bytes()==code,(name,'source bank mismatch')
    scanned=selected=0
    with path.open('rb')as stream:
     data=mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ)
     assert len(data)and len(data)%(STRIDE*2)==0
     for off in range(0,len(data),STRIDE*2):
      _,i,phase=struct.unpack_from('<IBB',data,off)
      r=data[off+6:off+STRIDE];after=data[off+STRIDE+6:off+STRIDE*2]
      ref=word(r,0x11e8,0x1208,i)
      isboss=boss_ref(ref)
      # Include ordinary attack actors while the boss occupies slot zero.
      boss_present=r[0xe08] and boss_ref(word(r,0x11e8,0x1208,0))
      if not isboss and not boss_present:continue
      scanned+=1
      if r[0x49]:skipped+=1;continue
      assert r[0x4b]==number-1,(name,r[0x4b])
      routine=word(r,0x1228,0x1248,i);sprite=word(r,0xf28,0xf48,i)
      # Include edge states separately; no numeric HP/bar value is used to
      # reduce sampling of otherwise identical no-contact waiting frames.
      flags=r[0x1148+i];hx=r[0x1068+i];hy=r[0x1088+i]
      key=(ref,routine,sprite,flags,hx,hy,bool(r[0x10c8+i]),bool(r[0x1108+i]),r[0xe08+i])
      changed=any(r[a+i]!=after[a+i]for a in (0x1028,0x10e8,0xe08))
      if counts[key]>=4 and not changed:continue
      counts[key]+=1;kept+=1;selected+=1;changes+=changed
      dest.write(data[off:off+STRIDE*2])
      p=(parts if isboss else hazards).setdefault((ref,hx,hy),dict(family=hex(ref),half_width=hx,half_height=hy,flags=set(),hp=set(),bars=set(),cooldown=set(),damage_lock=set(),samples=0))
      p['samples']+=1
      for field,at in [('flags',0x1148),('hp',0x1028),('bars',0x10e8),('cooldown',0x10c8),('damage_lock',0x1108)]:p[field].add(r[at+i])
     data.close()
    sources.append(dict(capture=name,encounter_updates_seen=scanned,selected=selected))
  assert kept,(number,'no boss coverage')
  print(f'Round {number}: checking {kept} boss/attack updates / {len(parts)} part hitboxes',flush=True)
  result=verify(group,group/'code.bin')
  assert result['unsupported_updates']==0,(number,result['unsupported_handlers'])
  row=dict(round=number,source_bank_matches_rom=True,health_or_state_changes=changes,debug_skipped=skipped,sources=sources,parts=[{k:sorted(v)if isinstance(v,set)else v for k,v in p.items()}for p in parts.values()],attack_actors=[{k:sorted(v)if isinstance(v,set)else v for k,v in p.items()}for p in hazards.values()],source_code_sha256=hashlib.sha256(code).hexdigest(),replay=result)
  report['rounds'].append(row)
  (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 report['passed']=True;report['boss_encounter_updates']=sum(r['replay']['updates']for r in report['rounds'])
 (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps(dict(passed=True,rounds=len(report['rounds']),boss_encounter_updates=report['boss_encounter_updates'])),flush=True)
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,default=ROOT/'.local/bc-all-boss-collision');args=parser.parse_args();run(args.output)
