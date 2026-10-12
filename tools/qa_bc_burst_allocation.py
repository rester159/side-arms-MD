#!/usr/bin/env python3
"""Differential-check boss bursts against a supplied pre-optimization world.c.
Vary pool occupancy and immediate-retirement positions, comparing all actor,
player, counter, and valid event state. Reference source is retained locally.
"""
import argparse
import ctypes as C
import hashlib
import json
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_actor_step import Actor,Player,StepData,Event,Data,Terrain,ROOT

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--reference',type=Path,required=True)
a=p.parse_args()
code=(ROOT/'.local/pce-reference/play-task-round1/code-002160.bin').read_bytes()
rom=(C.c_uint8*len(code)).from_buffer_copy(code)
cells=(C.c_uint8*16384).from_buffer_copy(code[0xc000:])
terrain=Terrain(cells,C.cast(C.byref(rom,0x6220),C.POINTER(C.c_uint8)))
rng=random.Random(4128)
checks=children=reused=exhausted=0
with tempfile.TemporaryDirectory() as directory:
    libs=[]
    for i,source in enumerate((a.reference,ROOT/'src/bc_world.c')):
        output=Path(directory)/f'world-{i}.dylib'
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),str(source),'-o',str(output)],check=True)
        lib=C.CDLL(str(output));lib.bc_actor_step_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),C.c_uint8,
            C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8]
        libs.append(lib)
    for case in range(6000):
        actors=(Actor*32)()
        for i in range(32):
            actors[i].body.state=128 if i<2 or rng.randrange(4) else 0
            actors[i].body.x=rng.randrange(256)
            actors[i].body.y=rng.randrange(256)
        if case%7==0:
            for i in range(2,32):actors[i].body.state=0
        if case%7==1:
            for i in range(2,32):actors[i].body.state=128
        boss=actors[0]
        boss.routine=0xb3e3;boss.phase=1;boss.turn=1 if case%3==0 else 20
        boss.body.flags=0x28;boss.body.hp=10;boss.body.bars=20
        boss.body.timer=2;boss.body.animation=0xb4d6;boss.body.sprite_base=0x340
        boss.body.x=rng.choice([0,16,204,255,320,65500])*256
        boss.body.y=rng.choice([0,16,112,223,272,65500])*256
        player=Player();player.state=128;player.invulnerability=255;player.x=80*256;player.y=112*256
        outputs=[]
        for lib in libs:
            pool=(Actor*32).from_buffer_copy(actors);who=Player.from_buffer_copy(player)
            seed=C.c_uint16(1);count=C.c_uint8(0)
            data=StepData(Data(rom,0x4000),0x250,0x1e0,0x1e8,0,0,terrain,2304,0,0x1a8,
                          C.pointer(seed),0x230,case%2,0x358,0x220,0)
            event=Event()
            lib.bc_actor_step_into(C.byref(event),pool,0,C.byref(who),C.byref(data),C.byref(count),8,0,0,1)
            # Compare fields, not ABI padding; unused extra entries are excluded.
            def common(e):return tuple(getattr(e,n) for n,_ in e._fields_)
            info=(common(event.actor_event),common(event.child_event),event.child_slot,event.setup_sound,
                  event.fire_requested,event.handled,event.extra_count,
                  tuple(event.extra_slots[:event.extra_count]),tuple(common(e) for e in event.extra_events[:event.extra_count]),
                  event.boss_defeat,event.boss_center_y)
            outputs.append((bytes(pool),bytes(who),count.value,seed.value,info))
        assert outputs[0]==outputs[1],('burst mismatch',case)
        slots=outputs[1][-1][7]
        children+=len(slots);reused+=len(slots)!=len(set(slots));exhausted+=not slots
        checks+=1
print(json.dumps(dict(cases=checks,child_events=children,immediate_reuse_cases=reused,
                     exhausted_pool_cases=exhausted,all_state_equal=True,
                     reference_sha256=hashlib.sha256(a.reference.read_bytes()).hexdigest()),indent=2))
