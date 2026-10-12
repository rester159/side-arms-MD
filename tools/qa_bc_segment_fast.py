#!/usr/bin/env python3
import shutil
import ctypes as C
import sys,subprocess,tempfile,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
p=argparse.ArgumentParser(description='Compare repeated segment actor loops with an archived dispatcher.')
p.add_argument('--baseline',type=Path,required=True,help='Directory containing baseline bc_world.c and bc_runtime.c')
p.add_argument('--aligned',action='store_true',help='Compare aligned candidate enemy positions with archived 16.8 sources and bc_rules.h')
p.add_argument('--scaled-velocity',action='store_true',help='Compare current long velocities with archived signed16 enemy records')
p.add_argument('--bind-segments',action='store_true',help='Bind candidate immutable tables and exercise both cached speeds')
p.add_argument('--curve',action='store_true',help='Exercise mixed approach/escape curve formations')
p.add_argument('--round',type=int,choices=(2,3,4,5,7,8),default=8)
args=p.parse_args()
cross_layout=args.aligned or args.scaled_velocity
if args.curve and args.round != 8:p.error('--curve currently requires --round 8')
from qa_bc_actor_step import Actor,Player,StepData,Event,Data,Enemy
import qa_bc_enemies
coordinate_shift=0
class NarrowEnemy(C.Structure):
 _fields_=[(n,C.c_int16 if n in ('vx','vy') else t) for n,t in Enemy._fields_]
 def __getattribute__(self,name):
  value=C.Structure.__getattribute__(self,name)
  if name in ('x','y'):
   assert value & ((1<<qa_bc_enemies.enemy_storage_shift)-1)==0
   return value >> qa_bc_enemies.enemy_storage_shift
  return value
 def __setattr__(self,name,value):
  if name in ('x','y'):value <<= qa_bc_enemies.enemy_storage_shift
  C.Structure.__setattr__(self,name,value)
class NarrowActor(C.Structure):
 _fields_=[(n,NarrowEnemy if n=='body' else t) for n,t in Actor._fields_]
def actor_type(index):return NarrowActor if args.scaled_velocity and index==0 else Actor
Sink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
def fields(v):
 if isinstance(v,Event):return tuple((n,tuple(fields(x) for x in getattr(v,n)[:v.extra_count]) if n in ('extra_slots','extra_events') else fields(getattr(v,n))) for n,*_ in v._fields_)
 if isinstance(v,C.Structure):return tuple((n,fields(getattr(v,n))) for n,*_ in v._fields_)
 if isinstance(v,C.Array):return tuple(fields(x) for x in v)
 return v
code=(ROOT/f'.local/pce-reference/round{args.round:02d}-reference/code-002160.bin').read_bytes();rom=(C.c_uint8*len(code)).from_buffer_copy(code)
sig=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert code.count(sig)==1;shift=code.index(sig)+0x4000-0x9204
with tempfile.TemporaryDirectory() as td:
 libs=[]
 for i,folder in enumerate((args.baseline.resolve(),ROOT/'src')):
  path=Path(td)/f'lib{i}.dylib'
  includes=ROOT/'inc'
  if cross_layout and i==0:
   includes=Path(td)/'baseline-inc';shutil.copytree(ROOT/'inc',includes)
   for header in folder.glob('*.h'):shutil.copyfile(header,includes/header.name)
  sources=[folder/(n+'.c') if cross_layout or n in ('bc_world','bc_runtime') else ROOT/'src'/(n+'.c') for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio')]
  if cross_layout and i==0:
   source_dir=Path(td)/'baseline-src';source_dir.mkdir()
   for source in sources:shutil.copyfile(source,source_dir/source.name)
   sources=[source_dir/source.name for source in sources]
  subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(includes),*map(str,sources),'-o',str(path)],check=True)
  lib=C.CDLL(str(path));lib.bc_runtime_actor_loop.argtypes=[C.POINTER(actor_type(i)),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8,Sink,C.c_void_p];lib.bc_runtime_actor_loop.restype=C.c_uint8
  lib.bc_aim16.argtypes=[C.c_uint16]*4;lib.bc_aim16.restype=C.c_uint8;libs.append(lib)
 cells=(C.c_uint8*16384)();attributes=(C.c_uint8*2048)()
 cases=events=children=failures=0
 for first in range(25):
  for full in (False,True):
   for px,py in ((48,48),(208,48),(48,208),(208,208)):
    for wait in (0,1,2,7,255):
     results=[]
     for library_index,lib in enumerate(libs):
      coordinate_shift=8 if args.aligned and library_index else 0
      if args.aligned:qa_bc_enemies.enemy_storage_shift=coordinate_shift
      pool=(actor_type(library_index)*32)();player=Player();player.state=128;player.invulnerability=200;player.x=px<<8;player.y=py<<8
      if full:
       for actor in pool:actor.body.state=128;actor.body.timer=20;actor.body.flags=0x23;actor.routine=0x9eb1
      for i in range(8):
       actor=pool[first+i];actor.body.state=128;actor.body.flags=0x23;actor.body.timer=20;actor.body.x=actor.body.y=128<<8
       actor.routine={2:0xbb7e,3:0xb6c3,4:0xb7f8,5:0xb7bd,7:0xb807,8:0xbf27}[args.round];actor.wait=wait;actor.dash_started=0x48 if i==0 else 0x54 if i==7 else 0x42
       actor.direction=actor.turn=lib.bc_aim16(px,py,128,128)^8
       if args.curve:
        actor.routine=0xb53b if i%2 else 0xb635
        actor.phase=(i//2)&3;actor.turn=0;actor.fired=1 if i==6 else 0

      data=StepData();data.data=Data(rom,0x4000);data.round=args.round-1;data.relocation=shift;data.bullet_base=0x500;data.terrain.cells=cells;data.terrain.attributes=attributes
      if args.bind_segments:
       template={2:0xbcb9,3:0xb7fe,4:0xb933,5:0xb8f8,7:0xb942,8:0xc062}[args.round]
       for j in range(8):pool[first+j].speed=6 if j&1 else code[template-0x4000+8]
       if library_index:
        lib.bc_actor_bind_segments.argtypes=[C.POINTER(StepData)]
        lib.bc_actor_bind_segments(C.byref(data))
      count=C.c_uint8(0);observations=[]
      @Sink
      def sink(slot,event,context):observations.append((slot,fields(event.contents)))
      snapshots=[]
      for tick in range(3):
       result=lib.bc_runtime_actor_loop(pool,0,C.byref(player),C.byref(data),C.byref(count),8,0,0,1,sink,None)
       assert result==32,(first,full,wait,tick,result)
       snapshots.append((fields(pool),bytes(player),count.value,tuple(observations)))
      results.append(snapshots)
     assert results[0]==results[1],(first,full,px,py,wait)
     cases+=1;events+=len(observations)
     for _,event in observations:
      event=dict(event)
      if event['fire_requested']:
       if event['child_slot']>=0:children+=1
       else:failures+=1
 assert children and failures,(children,failures)
 print('PASS',cases,'three-pass '+('curve' if args.curve else 'segment')+' pool cases;',events,'ordered events;',children,'child births;',failures,'allocation failures; complete actor/player/count results match archived dispatcher')
