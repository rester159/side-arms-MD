#!/usr/bin/env python3
"""Exercise every Boss Rush arena and result music with assisted completion events.
Boss-kill counters are injected after each music window; this is not a combat playthrough.
"""
import argparse,ctypes as C,hashlib,json,re
from pathlib import Path
import numpy as np
from run_rom import ROOT,Runner,PAD
from qa_soak import O
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--players',type=int,choices=(3,4),default=4);p.add_argument('--autohit',action='store_true',help='Use the existing hit-test fixture instead of injecting boss-kill counters');p.add_argument('--output',type=Path,help='Keep results separate from earlier cartridge evidence');a=p.parse_args()
digest=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()
# Derive encounters from the built arcade timeline, not from current music debug state.
encounters=[]
for section in re.findall(r'static const LevelEvent sec\d+\[\] = \{(.*?)\};',(ROOT/'src/gen/level_data.c').read_text(),re.S):
 music=0
 for op,arg,routine in re.findall(r'\{\d+,\s*\d+,\s*(EV_MUSIC|EV_BOSS),\s*(\d+),\s*(\d+),',section):
  if op=='EV_MUSIC':music=int(arg);continue
  kind=int(arg);routine=int(routine)
  command=({0x69d0:0x32,0x6c12:0x33,0x6db4:0x34}[routine] if kind==0 else 0x35 if kind==1 else music)
  track={0x32:0x12,0x33:0x0e,0x34:0x0c,0x35:0x0d,0x36:0x10}[command]
  encounters.append(dict(kind=kind,routine=routine,command=command,track=track))
r=Runner();r.run(2600)
def tap(k):r.run(5,PAD[k]);r.run(20)
tap('DOWN');tap('A')
for _ in range(3):tap('DOWN')
tap('A')
for _ in range(8):tap('DOWN')
tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
tap('B');tap('UP');tap('A')
for _ in range((a.players-2)%4):tap('DOWN')
tap('A');assert r.u32('flow_state')==12 and r.u16('player_limit')==a.players
assert r.read('rush_n',1)[0]==len(encounters)
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8))
zram=(C.c_uint8*8192).in_dll(r.lib,'zram');chunks=[]
def audio(data,count):chunks.append(np.ctypeslib.as_array(data,(count*2,)).copy());return count
cb=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)(audio);r.callbacks.append(cb);r.lib.retro_set_audio_sample_batch(cb)
def step():
 for i in range(a.players):r.write('players',b'\xc8',i*O['s_Player']+O['o_Player_invuln'])
 r.run(1);assert not zram[0x1b0a],('underrun',r.frames)
for i,row in enumerate(encounters):
 for _ in range(1800):
  step();chunks.clear()
  if r.read('rush_idx',1)[0]==i and r.read('rush_rs',1)==b'\1' and r.u16('dbg_hucard_track')==row['track']:break
 else:raise AssertionError(('missing encounter music',i,row,r.u16('dbg_hucard_track')))
 assert r.read('hucard_active',1)==b'\1'
 for _ in range(120):step()
 rms=float(np.sqrt(np.mean(np.concatenate(chunks).astype(float)**2)))
 assert rms>5,(i,'silent music');row['rms']=rms
 print('encounter',i+1,'track',hex(row['track']),'audible',flush=True)
 if a.autohit:
  kills=r.u16('boss_kills');r.write('boss_dbg_autohit',b'\1');chunks.clear()
  for damage_frame in range(12000):
   step();chunks.clear()
   if r.read('rush_rs',1)==b'\2':break
  else:raise AssertionError(('boss never defeated through hit path',i))
  r.write('boss_dbg_autohit',b'\0')
  assert r.u16('boss_kills')==((kills+1)&65535)
  row['defeat_video_frames']=damage_frame+1
  if row['kind']!=2:
   assert r.u16('dbg_hucard_track')==0x0a and r.read('hucard_active',1)==b'\1',('missing clear jingle',i)
   for _ in range(60):step()
   clear_rms=float(np.sqrt(np.mean(np.concatenate(chunks).astype(float)**2)))
   assert clear_rms>5,(i,'silent clear jingle')
   row['clear_track']=10;row['clear_rms']=clear_rms
 else:
  r.write('boss_kills',((r.u16('boss_kills')+1)&65535).to_bytes(2,'big'))
  step();assert r.read('rush_rs',1)==b'\2'
for _ in range(300):
 step();chunks.clear()
 if r.u32('flow_state')==13:break
assert r.u32('flow_state')==13
assert r.read('rush_defeated',1)[0]==len(encounters)
for _ in range(120):step()
assert r.u16('dbg_hucard_track')==0x0f and r.read('hucard_active',1)==b'\1'
assert float(np.sqrt(np.mean(np.concatenate(chunks).astype(float)**2)))>5
# Every selected player should be able to leave the result screen.
if a.players<4:
 bits=bytearray(8);bits[6:8]=b'\x80\x80';r.write('pad',bits)
 r.run(3);assert r.u32('flow_state')==13, 'unselected P4 dismissed results'
 r.write('pad',bytes(8));r.run(3)
bits=bytearray(8);bits[(a.players-1)*2:(a.players-1)*2+2]=b'\x80\x80';r.write('pad',bits)
for _ in range(30):
 r.run(1)
 if r.u32('flow_state')==9:break
assert r.u32('flow_state')==9,('last selected player cannot leave results',a.players)
assert not r.read('hucard_active',1)[0]
assert hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()==digest
out=a.output or ROOT/(f'.local/pce-hucard/rush-progression-{a.players}p'+('-autohit' if a.autohit else ''));out.mkdir(parents=True,exist_ok=True)
report=dict(passed=True,players=a.players,encounters=encounters,result_track=15,last_player_exit=True,underruns=0,rom_sha256=digest,assisted_completion_events=not a.autohit,assisted_hit_tests=a.autohit,full_combat_verified=False)
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
