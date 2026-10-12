#!/usr/bin/env python3
"""Compare idle dome/hover shortcuts with an archived dispatcher, including events."""
import argparse,ctypes as C,subprocess,tempfile
from pathlib import Path
from qa_bc_actor_step import Actor,Player,StepData,Event,Data
from qa_bc_beam import ROOT
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);args=p.parse_args()
Sink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
def fields(v):
 if isinstance(v,Event):return tuple((n,tuple(fields(x)for x in getattr(v,n)[:v.extra_count])if n in ('extra_slots','extra_events')else fields(getattr(v,n)))for n,*_ in v._fields_)
 if isinstance(v,C.Structure):return tuple((n,fields(getattr(v,n)))for n,*_ in v._fields_)
 if isinstance(v,C.Array):return tuple(fields(x)for x in v)
 return v
code=(ROOT/'.local/pce-reference/round4-defeat/code-002160.bin').read_bytes();rom=(C.c_uint8*len(code)).from_buffer_copy(code)
roms={3:rom}
for number,name in ((4,'round5-ending'),(5,'round6-defeat'),(6,'round7-defeat')):
 raw=(ROOT/'.local/pce-reference'/name/'code-002160.bin').read_bytes();roms[number]=(C.c_uint8*len(raw)).from_buffer_copy(raw)
with tempfile.TemporaryDirectory() as td:
 libs=[]
 for i,folder in enumerate((args.baseline,ROOT/'src')):
  sources=[folder/(n+'.c')if n in ('bc_world','bc_runtime')else ROOT/'src'/(n+'.c')for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio')]
  path=Path(td)/f'{i}.dylib';subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(ROOT/'inc'),*map(str,sources),'-o',str(path)],check=True)
  lib=C.CDLL(str(path));lib.bc_runtime_actor_loop.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8,Sink,C.c_void_p];lib.bc_runtime_actor_loop.restype=C.c_uint8;libs.append(lib)
 cases=events=0
 scenarios=[(3,0xba46,phase,0)for phase in range(256)]+[(round,handler,phase,wait)for round,handler in ((3,0xaf7c),(4,0xb44c),(5,0xb3cf),(6,0xb03e))for phase in (0,1,2,10,255)for wait in (0,1,2,10,255)]
 for round,handler,phase,wait in scenarios:
  for full in (False,True):
   for relocation in (-535,-536):
    for random_present in (False,True):
     results=[]
     for lib in libs:
      pool=(Actor*32)();player=Player();player.state=128;player.invulnerability=255;player.x=player.y=128<<8
      if full:
       for a in pool:a.body.state=128;a.body.timer=40;a.body.flags=0x23;a.routine=0x9eb1;a.body.x=a.body.y=128<<8
      a=pool[5];a.body.state=128;a.body.timer=40;a.body.flags=0x23;a.body.x=a.body.y=128<<8;a.routine=handler;a.phase=phase;a.wait=wait
      data=StepData();data.data=Data(roms[round],0x4000);data.round=round;data.relocation=relocation;data.homing_base=0x280
      cells=(C.c_uint8*16384)();attributes=(C.c_uint8*2048)();data.terrain.cells=cells;data.terrain.attributes=attributes
      seed=C.c_uint16(0x2345);data.random_state=C.pointer(seed)if random_present else None
      count=C.c_uint8(0);observations=[]
      @Sink
      def sink(slot,event,context):observations.append((slot,fields(event.contents)))
      snapshots=[]
      for tick in range(3):
       status=lib.bc_runtime_actor_loop(pool,0,C.byref(player),C.byref(data),C.byref(count),8,1,-1,0,sink,None)
       snapshots.append((status,fields(pool),bytes(player),count.value,seed.value,tuple(observations)))
      results.append(snapshots)
     assert results[0]==results[1],(round,handler,phase,wait,full,relocation,random_present)
     cases+=1;events+=len(observations)
 print(f'PASS: {cases} three-update cases, {events} ordered events; all dome timer bytes and hover boundary timers, occupied/free pools, missing RNG and alternate relocation; actors/player/count/RNG/events match')
