#!/usr/bin/env python3
"""R9 $A7EB: restore live state then execute the common task, as source bytes specify."""
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_actor_step import Actor,Player,StepData,Event,Data,CommonEvent
from run_rom import ROOT
code=(ROOT/'.local/pce-reference/round9-opening/code-002160.bin').read_bytes()
assert code[0xa7eb-0x4000:0xa7f3-0x4000]==bytes.fromhex('a9809d082e4cb19e')
with tempfile.TemporaryDirectory() as td:
 path=Path(td)/'probe.dylib'
 subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
 lib=C.CDLL(str(path))
 lib.bc_actor_step_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8]
 lib.bc_actor_scroll.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16,C.c_uint8]
 lib.bc_actor_common_into.argtypes=[C.POINTER(CommonEvent),C.POINTER(Actor),C.POINTER(Player),C.POINTER(Data),C.POINTER(C.c_uint8)]
 rng=random.Random(0xa7eb);rom=(C.c_uint8*65536)();data=StepData();data.data=Data(rom,0);data.round=8;data.relocation=-535
 for case in range(1024):
  pool=(Actor*32)();a=pool[4];a.body.state=64;a.routine=0x9eb1;a.death_routine=0xa7eb
  a.body.x=rng.choice((0,100,200,300,65535))<<8;a.body.y=rng.choice((0,100,200,300,65535))<<8
  a.body.vx=rng.choice((-512,0,512));a.body.vy=rng.choice((-384,0,512));a.body.timer=rng.choice((1,2,8));a.body.flags=rng.choice((1,3,5,33))
  a.body.cooldown=rng.choice((0,1,2,255));a.body.damage_lock=rng.choice((0,1,2));a.half_x=a.half_y=6
  p=Player();p.state=rng.choice((0,64,128));p.x=p.y=100<<8;p.invulnerability=rng.choice((0,20));p.inventory.lives=3
  expected=Actor.from_buffer_copy(bytes(a));ep=Player.from_buffer_copy(bytes(p));count=C.c_uint8(8);ec=C.c_uint8(8)
  event=Event();common=CommonEvent();dx,dy=rng.choice((-256,0,256)),rng.choice((-256,0,256));stopped=case%2
  lib.bc_actor_scroll(C.byref(expected),dx,dy,stopped);expected.body.state=128
  lib.bc_actor_common_into(C.byref(common),C.byref(expected),C.byref(ep),C.byref(data.data),C.byref(ec))
  lib.bc_actor_step_into(C.byref(event),pool,4,C.byref(p),C.byref(data),C.byref(count),8,dx,dy,stopped)
  assert event.handled, ('unhandled R9 radial-shot revival',case)
  assert bytes(a)==bytes(expected) and bytes(p)==bytes(ep) and count.value==ec.value,case
  assert bytes(event.actor_event)==bytes(common),case
  assert event.child_slot==-1 and not event.extra_count and not event.boss_defeat and not event.setup_sound,case
 print('PASS: 1024 R9 radial-shot revivals match source state restoration, scrolling, common motion, contacts and events')
