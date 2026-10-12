#!/usr/bin/env python3
"""Compare final-boss shot indexing with the production full-pool scan.

Exercises repeated queries within an update, pool resets between updates,
shot consumption/clearing, piercing and last-hit ownership. Hardware/state
integration is separately covered by the fixed-update native ROM replays.
"""
from pathlib import Path
import ctypes as C
import random
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
prefix='''#include <stdint.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16;
#define MAX_PLAYERS 4
#define MAX_SHOTS 9
typedef struct {s16 x,y; u8 active,half_h,half_w,pierce,life,colour; u16 code;} Shot;
typedef struct {Shot shots[9];} Player;
Player players[4]; s16 boss_shift; volatile u8 boss_dbg_autohit;
static s16 raw_x(s16 x){return x+96+boss_shift;}
static s16 raw_y(s16 y){return y+16;}
static void shot_hit(Player *p,Shot *s){(void)p;if(!s->pierce){s->active=2;s->life=16;s->code=0x1c;s->colour=5;}}
'''
class Shot(C.Structure):
 _fields_=[('x',C.c_int16),('y',C.c_int16)]+[(n,C.c_uint8) for n in ('active','half_h','half_w','pierce','life','colour')]+[('code',C.c_uint16)]
class Player(C.Structure):_fields_=[('shots',Shot*9)]
with tempfile.TemporaryDirectory() as directory:
 out=Path(directory);libs=[]
 source=(ROOT/'src/boss.c').read_text()
 start=source.index('typedef struct { Shot *shot; Player *owner; } BossShotRef;')
 code=prefix+source[start:source.index('\nbool boss_touch(')]
 code+='\nvoid begin_test(unsigned char indexed){boss_shot_scan=indexed;boss_shot_ready=0;}\n'
 for name in ('direct','indexed'):
  p=out/(name+'.c');p.write_text(code);target=p.with_suffix('.dylib')
  subprocess.run(['cc','-O2','-shared','-fPIC',str(p),'-o',str(target)],check=True)
  l=C.CDLL(str(target));l.boss_shots.argtypes=[C.c_int16,C.c_int16,C.c_uint8,C.c_uint8,C.POINTER(C.c_void_p)];l.boss_shots.restype=C.c_uint8
  l.begin_test.argtypes=[C.c_uint8];libs.append(l)
 arrays=[(Player*4).in_dll(l,'players') for l in libs];rng=random.Random(0xb055);queries=hits=0
 for case in range(20000):
  lo,hi=(-32768,32768) if case&1 else (-128,384)
  for p in arrays[0]:
   for s in p.shots:
    s.x=rng.randrange(lo,hi);s.y=rng.randrange(lo,hi);s.active=rng.choice((0,1,1,2));s.half_h=rng.randrange(256);s.half_w=rng.randrange(256);s.pierce=rng.randrange(2);s.life=77;s.colour=99;s.code=0xbeef
  C.memmove(C.addressof(arrays[1]),C.addressof(arrays[0]),C.sizeof(arrays[0]));libs[0].begin_test(0);libs[1].begin_test(1)
  for query in range(6):
   shift=rng.randrange(-32768,32768) if case&1 else rng.randrange(-32,33);auto=rng.randrange(2)
   for l in libs:C.c_int16.in_dll(l,'boss_shift').value=shift;C.c_uint8.in_dll(l,'boss_dbg_autohit').value=auto
   args=(rng.randrange(lo,hi),rng.randrange(lo,hi),rng.randrange(256),rng.randrange(256));initial=rng.choice((None,0,3));results=[]
   for l,a in zip(libs,arrays):
    who=C.c_void_p(None if initial is None else C.addressof(a[initial]));n=l.boss_shots(*args,C.byref(who));owner=None if who.value is None else (who.value-C.addressof(a))//C.sizeof(Player);results.append((n,owner,bytes(a)))
   assert results[0]==results[1],(case,query)
   hits+=results[0][0]-auto;queries+=1
   # Earlier boss parts and player deaths may consume or clear shots.
   if query&1:
    pi,si=rng.randrange(4),rng.randrange(9);state=rng.choice((0,2))
    for a in arrays:a[pi].shots[si].active=state
 print('PASS',queries,'ordered boss queries across 20000 pool resets;',hits,'natural hits; consumed/cleared shots, piercing, ownership and all shot bytes match')
