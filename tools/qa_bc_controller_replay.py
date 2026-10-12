#!/usr/bin/env python3
"""Replay a recorded Home pilot route without save states or forced game outcomes."""
import argparse, hashlib, json, struct
from run_rom import Runner, ROOT
p=argparse.ArgumentParser();p.add_argument('directory')
p.add_argument('--verify-ending',action='store_true',help='After exact gameplay replay, repeat the recorded final-clear ending and compare phases, credits and final pixels')
p.add_argument('--profile-start',type=int,help='Read-only complete-scene profile starting at this simulation tick')
p.add_argument('--profile-calls',type=int,default=1000)
a=p.parse_args()
from pathlib import Path
d=Path(a.directory);expected=json.loads((d/'result.json').read_text())
assert expected['home_modal_launch'] and not expected['debug_protection']
assert hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()==expected['rom_sha256']
inputs=(d/'controller-inputs.bin').read_bytes();assert len(inputs)%11==0
assert len(inputs)//11==expected['gameplay_end_video_frame']
r=Runner()
profiler=None
if a.profile_start is not None:
 from bc_campaign_profile import CampaignProfile
for offset in range(0,len(inputs),11):
 mask,override=struct.unpack('>HB',inputs[offset:offset+3])
 if a.profile_start is not None and profiler is None and r.frames>=2600 and r.u32('dbg_bc_native_ticks')>=a.profile_start:
  profiler=CampaignProfile(r,a.profile_start,a.profile_calls,d/'replay-profile')
 if profiler:profiler.poll()
 r.write('dbg_pad_override',bytes([override]));r.write('pad',inputs[offset+3:offset+11]);r.run(1,mask)
if a.profile_start is not None:
 assert profiler is not None, 'Input record ended before the profile start tick'
 profiler.poll()
 assert profiler.done, 'Input record ended before the requested profile completed'
(d/'replayed-end-ram.bin').write_bytes(bytes(r.ram))
from bc_pilot_lookahead import machine_checkpoint
(d/'replayed-checkpoint.json').write_text(json.dumps(machine_checkpoint(r),indent=2)+'\n')
got=hashlib.sha256(bytes(r.ram)).hexdigest()
assert got==expected['gameplay_end_ram_sha256'], (got,expected['gameplay_end_ram_sha256'])
if (d/'machine-checkpoint.json').exists():
 assert json.loads((d/'replayed-checkpoint.json').read_text())==json.loads((d/'machine-checkpoint.json').read_text()), 'CPU/video checkpoint mismatch'
gameplay_frames=r.frames
ending={}
if a.verify_ending:
 assert expected['reason']=='final_clear' and expected['ending'].get('home_returned'), 'Recording has no completed ending'
 r.write('pad',bytes(8));frozen_tick=r.u32('dbg_bc_native_ticks');ending_start=r.frames;phases=[]
 for _ in range(30000):
  phase=r.read('ending_bonus_phase',1)[0]
  if not phases or phases[-1]!=phase:phases.append(phase)
  assert r.u32('dbg_bc_native_ticks')==frozen_tick
  if phase==7:break
  r.run(1)
 else:raise AssertionError(('ending timeout',phases))
 assert r.u16('ending_credit_clock')==5760
 r.run(60);assert r.read('ending_bonus_phase',1)==b'\7'
 ending=dict(phases=phases,frames=r.frames-ending_start,credit_updates=5760,gameplay_ticks_frozen=True)
 button=bytearray(8);button[(expected['players']-1)*2:(expected['players']-1)*2+2]=bytes([0x10,0x10]);r.write('pad',button)
 for _ in range(120):
  r.run(1)
  if not r.u16('dbg_bc_native') and r.u32('flow_state')==9:break
 else:raise AssertionError('Home return failed')
 r.write('pad',bytes(8));r.write('dbg_pad_override',b'\0');r.run(30)
 assert r.u32('flow_state')==9 and not r.u16('dbg_bc_native')
 ending['home_returned']=True
 assert ending==expected['ending'],(ending,expected['ending'])
 from PIL import Image
 import numpy as np
 assert np.array_equal(r.frame,np.array(Image.open(d/'final.png').convert('RGB'))), 'Final Home pixels differ'
 r.capture(d/'replayed-final.png')
 ending['final_pixels_match']=True
result=dict(rom_sha256=expected['rom_sha256'],frames=gameplay_frames,ending=ending,
    gameplay_end_ram_sha256=got,save_state_restores=0,profile_start=a.profile_start,profile_calls=a.profile_calls if profiler else 0,
    forced_boss_defeats=False,seeded_health_or_weapons=False,
    full_campaign_verified=False,full_speed_verified=False)
(d/'controller-replay.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
