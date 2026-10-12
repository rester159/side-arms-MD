#!/usr/bin/env python3
"""Differential test of cached collision candidates over sequential enemy scans.
Checks hits that consume ordinary shots, piercing, locks, flags and bounds.
"""
import ctypes as C
import json
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_weapons import Weapons,Target,Hit

class Index(C.Structure):
    _fields_=[('slots',C.c_uint8*28),('count',C.c_uint8),('x',C.c_uint8*28),('y',C.c_uint8*28)]+[
        (name,C.c_uint8) for name in ('min_x','max_x','min_y','max_y','half_x','half_y')]

rng=random.Random(735901)
scans=contacts=damaged=0
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'index.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                    str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path))
    lib.bc_shot_index.argtypes=[C.POINTER(Index),C.POINTER(Weapons)]
    lib.bc_enemy_shots.argtypes=[C.POINTER(Target),C.POINTER(Weapons)];lib.bc_enemy_shots.restype=Hit
    lib.bc_enemy_shots_indexed.argtypes=[C.POINTER(Target),C.POINTER(Weapons),C.POINTER(Index)]
    lib.bc_enemy_shots_indexed.restype=Hit
    for board in range(2000):
        plain=Weapons()
        for shot in plain.shots:
            b=shot.body;b.state=rng.choice((0,0x80,0x80,0x40));b.flags=rng.randrange(4)
            b.x=rng.choice((rng.randrange(256),256,65535))<<8
            b.y=rng.randrange(256)<<8;b.damage=rng.randrange(1,11)
            b.half_x=rng.choice((0,4,8,127,255));b.half_y=rng.choice((0,4,8,127,255))
            shot.kind=rng.randrange(4)
        indexed=Weapons.from_buffer_copy(plain);index=Index()
        lib.bc_shot_index(C.byref(index),C.byref(indexed))
        expected=[i for i,b in enumerate(shot.body for shot in plain.shots[:28])
                  if b.state==128 and not b.flags&1 and not (b.x|b.y)&0xff0000]
        assert list(index.slots)[:index.count]==expected
        assert list(index.x)[:index.count]==[plain.shots[i].body.x>>8 for i in expected]
        assert list(index.y)[:index.count]==[plain.shots[i].body.y>>8 for i in expected]
        assert index.min_x==min((plain.shots[i].body.x>>8 for i in expected),default=255)
        assert index.max_x==max((plain.shots[i].body.x>>8 for i in expected),default=0)
        assert index.min_y==min((plain.shots[i].body.y>>8 for i in expected),default=255)
        assert index.max_y==max((plain.shots[i].body.y>>8 for i in expected),default=0)
        for enemy in range(16):
            b=plain.shots[rng.randrange(28)].body
            target=Target(((b.x>>8)+rng.randrange(-9,10))&65535,
                          ((b.y>>8)+rng.randrange(-9,10))&65535,
                          rng.choice((4,8,127,255)),rng.choice((4,8,127,255)),
                          rng.choice((0,0,1)),rng.randrange(1,16),rng.choice((0,0,255)),rng.choice((0,0,4)))
            other=Target.from_buffer_copy(target)
            want=lib.bc_enemy_shots(C.byref(target),C.byref(plain))
            got=lib.bc_enemy_shots_indexed(C.byref(other),C.byref(indexed),C.byref(index))
            assert bytes(got)==bytes(want),(board,enemy,'event')
            assert bytes(other)==bytes(target),(board,enemy,'target')
            assert bytes(indexed)==bytes(plain),(board,enemy,'weapon state')
            scans+=1;contacts+=got.contacts;damaged+=got.damaged
print(json.dumps(dict(scans=scans,contacts=contacts,damaging_hits=damaged,slot_order_preserved=True),indent=2))
