#!/usr/bin/env python3
"""Compare serpent volleys against a saved pre-optimization world implementation."""
import argparse
import ctypes as C
import json
from pathlib import Path
import random
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_factory import Actor
from qa_bc_common import Player
from qa_bc_actor_step import StepData, Event
from qa_bc_enemies import Data

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline-world',type=Path,required=True)
p.add_argument('--code',type=Path,required=True)
a=p.parse_args()
program=a.code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program)
rng=random.Random(20261004)
with tempfile.TemporaryDirectory() as tmp:
    funcs=[];libs=[]
    for i,source in enumerate((a.baseline_world,ROOT/'src/bc_world.c')):
        path=Path(tmp)/f'world{i}.dylib'
        subprocess.run(['cc','-O2','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),str(source),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));libs.append(lib)
        fn=lib.bc_actor_final_serpent_prepare
        fn.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.POINTER(Event)]
        funcs.append(fn)
    reused=full=retired=children=0
    for case in range(8192):
        pool=(Actor*32)();parent=case%32
        for j,actor in enumerate(pool):
            actor.body.state=0x80 if rng.randrange(32)<case%33 else 0
            actor.body.x=rng.randrange(1<<24);actor.body.y=rng.randrange(1<<24)
            actor.body.damage_lock=rng.randrange(256)
            actor.body.bars=rng.randrange(256)
        actor=pool[parent];actor.body.state=0x80;actor.wait=2;actor.phase=1;actor.dash_started=0x48
        actor.body.x=(rng.choice((0,1,128,255,256,288,320,32768,65535))<<8)|rng.randrange(256)
        actor.body.y=(rng.choice((0,1,120,223,224,256,272,32768,65535))<<8)|rng.randrange(256)
        player=Player();player.state=0x80;player.invulnerability=case%2
        player.x=actor.body.x;player.y=actor.body.y
        count=rng.randrange(256);seed=C.c_uint16(rng.randrange(65536))
        data=StepData();data.data=Data(rom,0x4000);data.random_state=C.pointer(seed);data.bullet_base=0x1234
        results=[]
        for fn in funcs:
            work=(Actor*32).from_buffer_copy(pool);pilot=Player.from_buffer_copy(player)
            limited=C.c_uint8(count);event=Event();saved_seed=seed.value
            fn(work,parent,C.byref(pilot),C.byref(data),C.byref(limited),C.byref(event))
            assert seed.value==saved_seed
            results.append((bytes(work),bytes(pilot),limited.value,bytes(event)))
        assert results[0]==results[1],('volley differential',case)
        slots=list(event.extra_slots[:event.extra_count]);children+=len(slots)
        reused+=len(set(slots))<len(slots);full+=not slots
        retired+=sum(not work[i].body.state for i in set(slots))
    assert reused and full and retired and children
    print(json.dumps(dict(cases=8192,children=children,reused_slot_cases=reused,
        full_pool_cases=full,retired_slots=retired,exact_actor_player_count_events=True),indent=2))
