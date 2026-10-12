#!/usr/bin/env python3
"""Capture/replay controller input at native scene entry, preserving simulation order.

Capture first proves equivalence to the original plain controller recording.
Replay compares every completed scene's canonical gameplay state. Neither mode
restores emulator snapshots or writes health, actors, score, weapons or RNG.
"""
import argparse, bisect, ctypes as C, hashlib, json, struct
import numpy as np
from pathlib import Path
from run_rom import Runner, ROOT
from bc_campaign_profile import CampaignProfile
from bc_scene_state import canonical_scene_bytes, state_layout, validate_native_layout

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('mode',choices=['capture','replay'])
p.add_argument('recording',type=Path)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--rom',type=Path,default=ROOT/'out/release/rom.bin',help='Optional archived ROM with matching symbols and unchanged bc_rules.h layout')
p.add_argument('--scene-record',type=Path,help='Capture output required for replay')
p.add_argument('--scene-limit',type=int,help='Replay only this many recorded scenes; reports a partial route, never a completed capture')
p.add_argument('--profile-start',type=int,help='First simulation tick eligible for complete-scene profiling')
p.add_argument('--profile-calls',type=int,default=1000)
p.add_argument('--workload-trace',action='store_true',help='Read scene-entry object and actor-family counts during the profile window')
a=p.parse_args()
if a.workload_trace and a.profile_start is None:p.error('--workload-trace requires --profile-start')
if a.profile_calls<1 or (a.profile_start is not None and a.profile_start<0):p.error('Invalid profile window')
if a.mode=='replay' and a.scene_record is None:p.error('--scene-record is required for replay')
if a.scene_limit is not None and (a.mode!='replay' or a.scene_limit<1):p.error('--scene-limit requires replay and a positive count')
if a.scene_record and a.scene_record.resolve()==a.output.resolve():p.error('Replay output must differ from its scene record')
if a.rom.resolve() != (ROOT/'out/release/rom.bin').resolve():
 header=a.rom.parent/'bc_rules.h'
 assert header.exists() and header.read_bytes()==(ROOT/'inc/bc_rules.h').read_bytes(), 'Archived ROM requires identical bc_rules.h layout'
a.output.mkdir(parents=True,exist_ok=True)
(a.output/'scene-record.json').unlink(missing_ok=True)
(a.output/'profile.json').unlink(missing_ok=True)
rom_sha=hashlib.sha256(a.rom.read_bytes()).hexdigest()
original=json.loads((a.recording/'result.json').read_text())
assert original['players'] in (1,2,3,4) and original['home_modal_launch'] and not original['debug_protection']
players=original['players']
if a.mode=='capture':
 assert hashlib.sha256(a.rom.read_bytes()).hexdigest()==original['rom_sha256'], 'Capture requires the original ROM'
inputs=(a.recording/'controller-inputs.bin').read_bytes();assert len(inputs)%11==0
expected=json.loads((a.scene_record/'scene-record.json').read_text()) if a.mode=='replay' else None
source_scene_count=expected['completed_scenes'] if expected else None
if expected:
 assert expected['mode']=='capture' and len(expected['scenes'])==expected['completed_scenes']
 assert expected['source_recording_sha256']==hashlib.sha256(inputs).hexdigest()
 assert expected.get('players',1)==players, 'Scene-record player count differs'
 if a.scene_limit is not None:
  if a.scene_limit>source_scene_count:p.error('--scene-limit exceeds the recorded route')
  expected['scenes']=expected['scenes'][:a.scene_limit]
validate_native_layout()
r=Runner(rom=a.rom);hook=None
if a.workload_trace:
 from workload_metrics import WorkloadMetrics
 workload=WorkloadMetrics(r,players)

def state():
 return hashlib.sha256(canonical_scene_bytes(r,players)).hexdigest()

class Scenes(CampaignProfile):
 def __init__(self):
  self.records=[];self.pending_scene=None;self.cursor=0;self.finished=False
  self.profile_rows=[];self.profile_pending=None
  super().__init__(r,0,10**9,a.output/'hook',a.rom)
 def watch(self):
  if self.errors or self.finished:return
  try:
   pc=(C.c_uint32.from_address(self.cpu+0x2858).value-2)&0xffffff
   if pc==self.entry:
    assert self.pending_scene is None
    # The function also runs in menus. Keep boot/modal/initialization on the
    # original video-frame inputs until native simulation has begun.
    if not self.cursor and r.u32('dbg_bc_native_ticks')==0:return
    if expected:
     assert self.cursor<len(expected['scenes']), 'More scenes than captured'
     row=expected['scenes'][self.cursor]
     assert r.u32('dbg_bc_native_ticks')==row['start_tick'],('entry tick',self.cursor)
     r.write('dbg_pad_override',b'\1');r.write('pad',bytes.fromhex(row['pad']))
    self.pending_scene=dict(start_tick=r.u32('dbg_bc_native_ticks'),pad=r.read('pad',8).hex(),start_frame=r.frames)
    if a.profile_start is not None and self.pending_scene['start_tick']>=a.profile_start and len(self.profile_rows)<a.profile_calls:
     self.profile_workload=dict(**workload.sample('bc'),actor_families=workload.actor_families(),weapon_families_per_player=workload.weapon_families()) if a.workload_trace else None
     self.profile_pending=(self.clock(),self.totals[1]);self.phase.value=1
   else:
    assert pc in self.returns
    if self.pending_scene is None:return
    self.phase.value=0
    row=self.pending_scene;row.update(end_tick=r.u32('dbg_bc_native_ticks'),state_sha256=state(),end_frame=r.frames)
    if self.profile_pending is not None:
     clock,total=self.profile_pending
     self.profile_rows.append(dict(start_tick=row['start_tick'],end_tick=row['end_tick'],start_frame=row['start_frame'],end_frame=row['end_frame'],scene_ticks=self.clock()-clock,attributed_ticks=self.totals[1]-total))
     if self.profile_workload is not None:self.profile_rows[-1]['entry_workload']=self.profile_workload
     self.profile_pending=None
    if expected:
     want=expected['scenes'][self.cursor]
     assert row['end_tick']==want['end_tick'] and row['state_sha256']==want['state_sha256'],('scene state mismatch',self.cursor,row,want)
    self.records.append(row);self.cursor+=1;self.pending_scene=None
    if expected and self.cursor==len(expected['scenes']):self.finished=True
  except BaseException as e:self.errors.append(repr(e))
 def check(self):
  if self.errors:raise AssertionError(self.errors)

try:
 limit=len(inputs)//11 if a.mode=='capture' else len(inputs)//11*3
 for frame in range(limit):
  if frame==2600:
   hook=Scenes();hook.poll();hook.h.profile_only(2 if a.profile_start is not None else 0)
  # Menu boot uses the exact original inputs. Once native scenes start,
  # replay supplies controller bytes at scene entry, independent of VBlank.
  if a.mode=='capture' or hook is None or hook.cursor==0:
   mask,override=struct.unpack_from('>HB',inputs,frame*11)
   r.write('dbg_pad_override',bytes([override]));r.write('pad',inputs[frame*11+3:frame*11+11])
  else:mask=0
  r.run(1,mask)
  if hook:
   hook.check()
   if hook.finished:break
 else:assert a.mode=='capture','Replay frame limit exceeded'
 assert hook and hook.records
 if a.mode=='capture':
  from bc_pilot_lookahead import machine_checkpoint
  assert hashlib.sha256(bytes(r.ram)).hexdigest()==original['gameplay_end_ram_sha256']
  assert machine_checkpoint(r)==json.loads((a.recording/'machine-checkpoint.json').read_text())
 else:assert hook.cursor==len(expected['scenes'])
 assert hashlib.sha256(a.rom.read_bytes()).hexdigest()==rom_sha, 'ROM changed during run'
 if a.profile_start is not None:
  assert len(hook.profile_rows)==a.profile_calls, 'Recorded route ended before profile completed'
  hist=np.ctypeslib.as_array((C.c_uint64*0x200000).in_dll(hook.h,'instruction_cycles')).copy()
  addresses=[at for at,name in hook.symbols];counts={}
  for i in np.nonzero(hist)[0]:
   name=hook.symbols[bisect.bisect_right(addresses,int(i)*2)-1][1]
   counts[name]=counts.get(name,0)+int(hist[i])
  values=[row['scene_ticks'] for row in hook.profile_rows]
  profile=dict(rom_sha256=rom_sha,start_tick=a.profile_start,completed_calls=len(values),
      mean_scene_ticks=float(np.mean(values)),maximum_scene_ticks=max(values),
      over_budget=sum(v>hook.budget for v in values),frame_budget_core_ticks=hook.budget,
      video_frame_span=hook.profile_rows[-1]['end_frame']-hook.profile_rows[0]['start_frame'],
      scope=hook.boundary_scope+'; excludes outer input and final video/VBlank/DMA work',
      canonical_scene_states_match=bool(expected),original_checkpoint_matches=a.mode=='capture',
      full_speed_verified=False,rows=hook.profile_rows,
      functions=[dict(name=n,attributed_ticks=v)for n,v in sorted(counts.items(),key=lambda x:-x[1])])
  if a.workload_trace:
   profile['workload_scope']=workload.scope+' Actor families are scene-entry occupancy, not execution counts; births and state changes during the scene are not counted.'
   profile['workload_abi']=workload.o
  (a.output/'profile.json').write_text(json.dumps(profile,indent=2)+'\n')
  np.save(a.output/'scene-cycles.npy',hist)
 result=dict(rom_sha256=rom_sha,players=players,
  source_recording_sha256=hashlib.sha256(inputs).hexdigest(),mode=a.mode,
  completed_scenes=hook.cursor,video_frames=r.frames,scenes=hook.records,
  source_scene_count=source_scene_count,requested_scene_limit=a.scene_limit,
  complete_recorded_route=(hook.cursor==source_scene_count) if expected else None,
  comparison_scope=('Actor pool, stage, and primary player (excluding only transient player pointers), '
                    'plus RNG seed, score, credits, and unused-continue counts. Multiplayer also includes '
                    'every selected peer player and score, all continue prompts, and pending/shown flags. '
                    'Sampled at completed scenes; not a full-RAM or video comparison.'),
  canonical_state_layout=state_layout(players),
  full_campaign_verified=False,full_speed_verified=False)
 (a.output/'scene-record.json').write_text(json.dumps(result)+'\n')
 print(json.dumps({k:v for k,v in result.items()if k!='scenes'},indent=2))
finally:
 if hook and hook.active:hook.h.profile_end()
