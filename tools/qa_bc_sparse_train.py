#!/usr/bin/env python3
"""Compare fragmented co-op trains with the original contiguous train lifecycle."""
import argparse,ctypes as C,json,random,subprocess,tempfile
from pathlib import Path
from qa_bc_factory import Actor
from qa_bc_common import Player
from qa_bc_enemies import Data
from qa_bc_stage_runtime import Resources
from qa_bc_actor_step import StepData,Event
from qa_bc_segment_birth_index import Party
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
rng=random.Random(8192);cases=updates=promotions=failures=tail_shots=reused=0
with tempfile.TemporaryDirectory() as folder:
 tmp=Path(folder);libs=[]
 for label,source in [('baseline',a.baseline),('candidate',ROOT/'src')]:
  runtime=tmp/(label+'-runtime.c');runtime.write_text((source/'bc_runtime.c').read_text()+'''
int test_train(BcActor *a,BcWorldPlayer *p,const BcStageEventData *d,unsigned char *c,unsigned char v){return segment_birth(a,p,d,c,v);}
''')
  libpath=tmp/(label+'.dylib')
  subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),str(runtime),str(source/'bc_world.c'),*(str(ROOT/f'src/{n}.c')for n in ('bc_rules','bc_stage','bc_score','bc_player','bc_palette','bc_audio')),'-o',str(libpath)],check=True)
  lib=C.CDLL(str(libpath));lib.test_train.argtypes=[C.POINTER(Actor),C.POINTER(Player),C.POINTER(Resources),C.POINTER(C.c_uint8),C.c_uint8];lib.test_train.restype=C.c_int
  lib.bc_actor_step.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8];lib.bc_actor_step.restype=Event
  libs.append(lib)
 def normalized(actor):
  copy=Actor.from_buffer_copy(actor);copy.auxiliary=copy.probe_x=copy.probe_y=0;return bytes(copy)
 masks=[[5,13,20,28],list(range(0,32,4)),list(range(0,32,2))]
 for _ in range(9):
  while True:
   occupied=sorted(rng.sample(range(32),rng.randrange(8,24)))
   if max(len(x)for x in ''.join('x'if i in occupied else '.'for i in range(32)).split('x'))<8:break
  masks.append(occupied)
 for rnd in (1,2,3,4,6,7):
  code=(ROOT/f'.local/pce-reference/round{rnd+1:02d}-reference/code-002160.bin').read_bytes();rom=(C.c_uint8*len(code)).from_buffer_copy(code)
  shift=code.index(bytes.fromhex('bdcc2df0273a9dcc2dd02c'))+0x4000-0x9204
  sd=Resources();sd.data=Data(rom,0x4000);sd.round=rnd;sd.relocation=shift;sd.segment_bases[:]=range(0x100,0x106)
  step=StepData();step.data=sd.data;step.round=rnd;step.relocation=shift
  for variant in (0,1):
   for n in (3,4):
    for occupied in masks:
     pools=[(Actor*32)(),(Actor*32)()];players=[Player(),Player()];parties=[Party(),Party()];counts=[C.c_uint8(),C.c_uint8()]
     members=[list(range(8)),[i for i in range(32)if i not in occupied][:8]]
     for slot in occupied:pools[1][slot].body.state=128;pools[1][slot].routine=0xffff
     untouched={slot:bytes(pools[1][slot])for slot in occupied}
     for index,lib in enumerate(libs):
      players[index].state=128;players[index].invulnerability=200;players[index].x=128<<8;players[index].y=120<<8
      parties[index].count=n;parties[index].players[0]=C.pointer(players[index]);players[index].party=C.cast(C.pointer(parties[index]),C.c_void_p)
      assert lib.test_train(pools[index],C.byref(players[index]),C.byref(sd),C.byref(counts[index]),variant)==members[index][0]
     assert [pools[1][i].probe_x for i in members[1]]==[members[1][max(0,i-1)]for i in range(8)]
     assert [pools[1][i].probe_y for i in members[1]]==[members[1][min(7,i+1)]for i in range(8)]
     # Tail firing must use the real parent slot, even when its predecessor
     # is elsewhere. Compare the emitted child with the original task.
     saved=[bytes(pool) for pool in pools];shots=[]
     for index,lib in enumerate(libs):
      tail=pools[index][members[index][-1]]
      tail.body.x=128<<8;tail.body.y=120<<8;tail.direction=8;tail.wait=2
      players[index].x=200<<8
      event=lib.bc_actor_step(pools[index],members[index][-1],C.byref(players[index]),C.byref(step),C.byref(counts[index]),16,0,0,0)
      assert event.fire_requested and event.child_slot>=0
      shots.append(normalized(pools[index][event.child_slot]))
     assert shots[0]==shots[1]
     tail_shots+=1
     for index in range(2):
      C.memmove(pools[index],saved[index],C.sizeof(pools[index]));counts[index].value=0;players[index].x=128<<8
     for tick in range(400):
      events=[[],[]]
      for index,lib in enumerate(libs):
       # Exercise every head promotion and the final delayed triple death.
       if tick>=120 and (tick-120)%35==0:
        heads=[s for s in members[index]if pools[index][s].body.state==128 and pools[index][s].dash_started==0x48]
        if heads:pools[index][heads[0]].body.state=64;promotions+=index==1
       for slot in members[index]:
        if pools[index][slot].body.state:
         e=lib.bc_actor_step(pools[index],slot,C.byref(players[index]),C.byref(step),C.byref(counts[index]),0,0,0,0)
         events[index].append((bytes(e.actor_event),bytes(e.child_event),e.child_slot,e.setup_sound,e.fire_requested,e.handled,e.extra_count,e.boss_defeat,e.boss_center_y))
      assert events[0]==events[1],(rnd,variant,n,tick,"events")
      for left,right in zip(members[0],members[1]):
       assert normalized(pools[0][left])==normalized(pools[1][right]),(rnd,variant,n,tick,left,right)
      for slot,state in untouched.items():assert bytes(pools[1][slot])==state
      assert counts[0].value==counts[1].value
      updates+=1
     cases+=1
  # Recycle sparse scratch bytes into a normal contiguous train. The
  # original template contract must disable the links on every new member.
  for n in (1,2,3,4):
   pool=(Actor*32)();player=Player();party=Party();party.count=n;party.players[0]=C.pointer(player);player.party=C.cast(C.pointer(party),C.c_void_p)
   for actor in pool:actor.auxiliary=255;actor.probe_x=31;actor.probe_y=31
   count=C.c_uint8()
   assert libs[1].test_train(pool,C.byref(player),C.byref(sd),C.byref(count),0)==0
   assert all(pool[i].auxiliary==0 for i in range(8))
   reused+=8
  # Original 1/2P fragmented failures and fewer-than-eight co-op failures
  # must leave all actor bytes untouched.
  for n,occupied in [(1,masks[0]),(2,masks[0]),(3,list(range(25))),(4,list(range(25)))]:
   pool=(Actor*32)();player=Player();party=Party();party.count=n;party.players[0]=C.pointer(player);player.party=C.cast(C.pointer(party),C.c_void_p)
   for slot in occupied:pool[slot].body.state=128
   before=bytes(pool);count=C.c_uint8()
   assert libs[1].test_train(pool,C.byref(player),C.byref(sd),C.byref(count),0)==-1
   assert bytes(pool)==before;failures+=1
print(json.dumps(dict(passed=True,formations=cases,compared_update_batches=updates,head_deaths=promotions,unchanged_failed_allocations=failures,tail_shots=tail_shots,reused_members=reused,rounds=6,variants=2,players=[3,4]),indent=2))
