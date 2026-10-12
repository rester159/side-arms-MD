#!/usr/bin/env python3
"""Sample actor families after completed updates without modifying the cartridge.

This is a workload inventory, not an instruction profile: actors born and retired
within one update need not appear in the post-update snapshot.
"""
import argparse,collections,hashlib,json,struct
from pathlib import Path
from run_rom import ROOT,Runner
from bc_actor_layout import read_actor_pool
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--round',type=int,choices=range(1,11),required=True)
p.add_argument('--players',type=int,choices=range(1,5),default=4)
p.add_argument('--warmup',type=int,default=300)
p.add_argument('--updates',type=int,default=600)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert a.updates>0 and a.warmup>=0
rom=(ROOT/'out/release/rom.bin').read_bytes();r=Runner();r.run(2600)
for key,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',a.round-1),('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(key,struct.pack('>H',value))
r.write('dbg_pad_override',b'\1');last=-1;hist=collections.Counter();samples=0
for _ in range((a.warmup+a.updates)*8+500):
 tick=r.u32('dbg_bc_native_ticks');bits=0x20 if tick%40<20 else 0
 r.write('pad',bytes([bits,bits if tick%40==0 else 0]*a.players+[0,0]*(4-a.players)));r.run(1)
 tick=r.u32('dbg_bc_native_ticks');assert r.u16('dbg_bc_native_status') in (0,4)
 if tick!=last and tick>a.warmup:
  raw=read_actor_pool(r);samples+=1
  for i in range(32):
   actor=raw[i*50:(i+1)*50];state=actor[20]
   if state:hist[(state,struct.unpack_from('>H',actor,30 if state==128 else 32)[0],struct.unpack_from('>H',actor,34)[0])]+=1
 last=tick
 if tick>=a.warmup+a.updates:break
assert samples==a.updates
assert (ROOT/'out/release/rom.bin').read_bytes()==rom
result=dict(rom_sha256=hashlib.sha256(rom).hexdigest(),round=a.round,players=a.players,protected=True,post_update_samples=samples,actors=[dict(state=s,handler=f'{h:04x}',family=f'{f:04x}',uses=n)for (s,h,f),n in hist.most_common()])
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
