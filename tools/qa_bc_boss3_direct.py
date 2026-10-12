#!/usr/bin/env python3
"""Compare mixed homing-shot actor passes with the prior full dispatcher."""
import argparse,ctypes as C,random,subprocess,tempfile
from pathlib import Path
from qa_bc_actor_step import Actor,Player,StepData,Event,Data
from run_rom import ROOT
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
Sink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
def fields(v):
 if isinstance(v,Event):return tuple((n,tuple(fields(x)for x in getattr(v,n)[:v.extra_count])if n in ('extra_slots','extra_events')else fields(getattr(v,n)))for n,*_ in v._fields_)
 if isinstance(v,C.Structure):return tuple((n,fields(getattr(v,n)))for n,*_ in v._fields_)
 if isinstance(v,C.Array):return tuple(fields(x)for x in v)
 return v
with tempfile.TemporaryDirectory() as td:
 libs=[]
 for i,folder in enumerate((a.baseline.resolve(),ROOT/'src')):
  path=Path(td)/f'lib{i}.dylib'
  sources=[folder/(n+'.c')if n in ('bc_world','bc_runtime')else ROOT/'src'/(n+'.c')for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio')]
  subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(ROOT/'inc'),*map(str,sources),'-o',str(path)],check=True)
  lib=C.CDLL(str(path));lib.bc_runtime_actor_loop.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8,Sink,C.c_void_p];lib.bc_runtime_actor_loop.restype=C.c_uint8
  lib.bc_actor_template.argtypes=[C.POINTER(Actor),C.POINTER(C.c_uint8),C.c_uint16];libs.append(lib)
 cases=events=0
 for round_ in (3,9):
  code=(ROOT/f'.local/pce-reference/round{round_:02d}-reference/code-002160.bin').read_bytes()
  rom=(C.c_uint8*len(code)).from_buffer_copy(code);shift=0x527 if round_==9 else 0
  sig=bytes.fromhex('bdcc2df0273a9dcc2d');assert code.count(sig)==1
  relocation=code.index(sig)+0x4000-0x9204
  template=C.cast(C.byref(rom,0xae4a+shift-0x4000),C.POINTER(C.c_uint8))
  for case in range(400):
   results=[]
   for lib in libs:
    rng=random.Random(round_*10000+case);pool=(Actor*32)();player=Player();player.state=rng.choice((128,128,64));player.invulnerability=rng.choice((0,0,50))
    player.x=rng.choice((16,64,120,208,240))<<8;player.y=rng.choice((32,100,180,200))<<8;player.inventory.lives=3
    for option in (28,29):player.weapons.shots[option].body.state=rng.choice((0,128))
    for slot in range(32):
     actor=pool[slot];lib.bc_actor_template(C.byref(actor),template,0x200)
     actor.body.state=0 if rng.randrange(5)==0 else 128
     actor.body.x=(rng.choice((-32,0,16,64,120,208,255,280,300))&65535)<<8
     actor.body.y=(rng.choice((-32,40,100,180,240,270))&65535)<<8
     actor.direction=rng.randrange(16);actor.speed=rng.choice((0,2,4,6,8));actor.phase=rng.choice((0,1,2,10,255));actor.wait=rng.choice((0,1,2,40,255))
     actor.body.flags=rng.choice((0,1,1,5));actor.body.damage_lock=rng.choice((0,1,2,255));actor.body.cooldown=rng.choice((0,1,255))
     actor.body.animation=int.from_bytes(code[0x8962+actor.direction*2-0x4000:0x8964+actor.direction*2-0x4000],'little')
     actor.body.timer=rng.choice((0,1,2,8));actor.routine=0xadcf+shift
     # Ordinary common-only records interleaved with the specialized family.
     if slot%7==0:actor.routine=0x9eb1
    data=StepData();data.data=Data(rom,0x4000);data.round=round_-1;data.relocation=relocation
    count=C.c_uint8(32);observations=[]
    @Sink
    def sink(slot,event,context):observations.append((slot,fields(event.contents)))
    first=case%4;dx,dy=rng.choice((-256,0,256)),rng.choice((-256,0,256));stopped=case%2
    snapshots=[]
    for tick in range(3):
     result=lib.bc_runtime_actor_loop(pool,first,C.byref(player),C.byref(data),C.byref(count),8,dx,dy,stopped,sink,None)
     assert result==32,(round_,case,tick,result)
     snapshots.append((fields(pool),bytes(player),count.value,tuple(observations)))
    results.append(snapshots)
   assert results[0]==results[1],(round_,case)
   cases+=1;events+=len(observations)
 print(f'PASS: {cases} three-pass mixed R3/R9 pools; {events} ordered events; actor/player/count state, scrolling, retirement, damage and options match baseline')
