#!/usr/bin/env python3
"""Compare actor-pointer firing paths with an archived world implementation."""
import argparse
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_actor_step import Actor, Player, StepData, Event, Data, ROOT

def fields(value):
    if isinstance(value,Event):
        # The production contract defines only extra_count child entries.
        # Unused array capacity is intentionally not initialized or consumed.
        return tuple((name, tuple(fields(x) for x in getattr(value,name)[:value.extra_count])
            if name in ('extra_slots','extra_events') else fields(getattr(value,name)))
            for name,*_ in value._fields_)
    if isinstance(value,C.Structure):
        return tuple((name,fields(getattr(value,name))) for name,*_ in value._fields_)
    if isinstance(value,C.Array):return tuple(fields(x) for x in value)
    return value

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--curve',action='store_true',help='Exercise escape-shot birth and the latch after allocation failure')
a=p.parse_args()
program=(ROOT/'.local/pce-reference/round08-reference/code-002160.bin').read_bytes()
signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c')
assert program.count(signature)==1
shift=program.index(signature)+0x4000-0x9204
rom=(C.c_uint8*len(program)).from_buffer_copy(program)
with tempfile.TemporaryDirectory() as directory:
    libs=[]
    for i,source in enumerate((a.baseline,ROOT/'src/bc_world.c')):
        path=Path(directory)/f'world{i}.dylib'
        subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),str(source),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_actor_step.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),
            C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8]
        lib.bc_actor_step.restype=Event
        lib.bc_aim16.argtypes=[C.c_uint16]*4;lib.bc_aim16.restype=C.c_uint8
        libs.append(lib)
    cases=children=failures=0
    for slot in range(0 if a.curve else 1,32):
        for full in (False,True):
            for px,py in (((32,48),(64,48),(32,208),(64,208)) if a.curve else ((48,48),(208,48),(48,208),(208,208))):
                results=[]
                for lib in libs:
                    pool=(Actor*32)();player=Player();player.state=0x80;player.invulnerability=200
                    player.x=px<<8;player.y=py<<8
                    if full:
                        for actor in pool:actor.body.state=0x80
                    actor=pool[slot];actor.body.state=0x80;actor.body.flags=3
                    actor.body.x=actor.body.y=128<<8;actor.body.timer=2
                    actor.wait=2;actor.dash_started=0x54;actor.routine=0xb635 if a.curve else 0xbf27
                    actor.direction=lib.bc_aim16(px,py,128,128)^8
                    data=StepData();data.data=Data(rom,0x4000);data.round=7
                    data.relocation=shift;data.bullet_base=0x500
                    count=C.c_uint8(0)
                    event=lib.bc_actor_step(pool,slot,C.byref(player),C.byref(data),C.byref(count),8,0,0,1)
                    assert event.handled and event.fire_requested
                    assert (event.child_slot<0)==full
                    result=(fields(pool),fields(event),count.value,bytes(player))
                    if a.curve:
                        # Source latches the attempt even when allocation fails.
                        assert actor.fired == 1
                        second=lib.bc_actor_step(pool,slot,C.byref(player),C.byref(data),C.byref(count),8,0,0,1)
                        assert not second.fire_requested and actor.fired == 1
                        result+=(fields(pool),fields(second),count.value,bytes(player))
                    results.append(result)
                assert results[0]==results[1],(slot,full,px,py)
                cases+=1;failures+=full;children+=not full
    print(f'PASS: {cases} {"curve" if a.curve else "tail"}-firing comparisons, {children} immediate child updates, {failures} full-pool failures; parent slots {0 if a.curve else 1}–31' + ('; all repeated fire attempts inhibited' if a.curve else '; four aim quadrants'))
