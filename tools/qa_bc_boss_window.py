#!/usr/bin/env python3
"""Replay a natural input record and report read-only boss core alignment snapshots.

Samples are video-boundary observations once per new simulation tick, not a
trace of the instant collision executes. The complete endpoint must reproduce.
"""
import argparse,hashlib,json,struct
from pathlib import Path
from run_rom import Runner,ROOT
from bc_actor_layout import read_actor_pool
from bc_pilot_lookahead import machine_checkpoint
from workload_metrics import WorkloadMetrics
p=argparse.ArgumentParser(description=__doc__);p.add_argument('recording',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--round',type=int,choices=range(1,11),default=4);a=p.parse_args()
expected=json.loads((a.recording/'result.json').read_text());assert expected['home_modal_launch'] and not expected['debug_protection']
sha=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest();assert sha==expected['rom_sha256']
inputs=(a.recording/'controller-inputs.bin').read_bytes();assert len(inputs)==11*expected['gameplay_end_video_frame']
r=Runner();layout=WorkloadMetrics(r,1);last=-1;rows=[]
for offset in range(0,len(inputs),11):
 mask,override=struct.unpack('>HB',inputs[offset:offset+3]);r.write('dbg_pad_override',bytes([override]));r.write('pad',inputs[offset+3:offset+11]);r.run(1,mask)
 if r.frames<2800 or r.u16('dbg_bc_native_current_round')!=a.round-1:continue
 tick=r.u32('dbg_bc_native_ticks')
 if tick==last:continue
 last=tick;b=read_actor_pool(r)[:50]
 if b[20]!=128 or not b[22]&8:continue
 x=int.from_bytes(b[:4],'big')>>8;y=int.from_bytes(b[4:8],'big')>>8
 if a.round==4 and x!=232:continue
 py=int.from_bytes(r.read('player',4,4),'big')>>8
 candidates=0
 for i in range(28):
  shot=r.read('player',layout.o['bc_shot_size'],layout.o['bc_shots']+i*layout.o['bc_shot_size'])
  assert layout.o['bc_shot_size']==32 and layout.o['bc_shot_state']==16
  if shot[16]!=128 or shot[18]&1:continue
  sx=int.from_bytes(shot[:4],'big')>>8;sy=int.from_bytes(shot[4:8],'big')>>8
  if sx>255 or sy>255:continue
  if abs(x-sx)<((b[36]+shot[20])&255) and abs(y-sy)<((b[37]+shot[21])&255):candidates+=1
 rows.append(dict(tick=tick,core_y=y,player_y=py,vertical_gap=abs(y-py),open=not bool(b[22]&1),cooldown=b[26],damage_lock=b[27],hp=b[24],bars=b[25],overlapping_shots=candidates))
assert hashlib.sha256(bytes(r.ram)).hexdigest()==expected['gameplay_end_ram_sha256']
assert machine_checkpoint(r)==json.loads((a.recording/'machine-checkpoint.json').read_text())
opened=[v for v in rows if v['open'] and not v['cooldown'] and not v['damage_lock']]
report=dict(rom_sha256=sha,round=a.round,boss_slot=0,exact_endpoint_replay=True,scope='video-boundary snapshots once per observed tick; not collision execution trace',samples=len(rows),open_samples=len(opened),open_aligned_within8=sum(v['vertical_gap']<=8 for v in opened),minimum_open_vertical_gap=min((v['vertical_gap']for v in opened),default=None),open_shot_overlap_samples=sum(bool(v['overlapping_shots'])for v in opened),health_states=sorted(set((v['hp'],v['bars'])for v in rows)),rows=rows)
a.output.mkdir(parents=True,exist_ok=True);(a.output/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='rows'},indent=2))
