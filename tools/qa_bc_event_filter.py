#!/usr/bin/env python3
"""Compare opt-in effect filtering with the full actor event consumer chain."""
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_actor_step import Event
from qa_bc_actor_loop import RuntimeEvents, Defeat
from qa_bc_score import Score
class Queue(C.Structure):
    _fields_=[('sources',C.c_uint8*128),('count',C.c_uint16),('dropped',C.c_uint16)]
Sink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'events.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{name}.c') for name in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio','bc_actor_audio')),
        '-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_runtime_actor_events.argtypes=[C.c_uint8,C.POINTER(Event),C.POINTER(RuntimeEvents)]
    lib.bc_audio_actor_append.argtypes=[C.POINTER(Queue),C.POINTER(Event)]
    scores=[Score(),Score()];defeats=[Defeat(),Defeat()];audio=[Queue(),Queue()]
    final=[[],[]];calls=[0,0]
    def callback(index):
        @Sink
        def sink(slot,event,context):
            calls[index]+=1
            lib.bc_audio_actor_append(C.byref(audio[index]),event)
            if event.contents.boss_defeat==2:final[index].append((slot,event.contents.boss_center_y))
        return sink
    callbacks=[callback(0),callback(1)]
    contexts=[RuntimeEvents(C.pointer(scores[i]),1,i,C.cast(callbacks[i],C.c_void_p),None,C.addressof(defeats[i])) for i in range(2)]
    rng=random.Random(0xbce);silent=0
    for case in range(5000):
        e=Event();e.handled=1;e.child_slot=-1
        # Include unused-record garbage: it must not create score/audio effects.
        for child in e.extra_events:child.sound=255;child.score_pending=1;child.score_id=99
        mode=case%10
        if mode==0:e.setup_sound=rng.choice((3,4,8,12,13,22))
        elif mode in (1,2):
            target=e.actor_event if mode==1 else e.child_event
            target.sound=rng.choice((0,3,4,8));target.score_pending=rng.randrange(2);target.score_id=rng.randrange(1,40)
        elif mode==3:
            e.extra_count=rng.randrange(1,11)
            for child in e.extra_events[:e.extra_count]:child.sound=rng.choice((0,3,4,8));child.score_pending=rng.randrange(2);child.score_id=rng.randrange(1,40)
        elif mode==4:e.boss_defeat=rng.choice((1,2));e.boss_center_y=rng.randrange(256)
        else:
            # Non-effect actor observations remain available in default mode.
            e.actor_event.retired=1;e.actor_event.pickup=2;e.fire_requested=1;silent+=1
        before=bytes(e);slot=case%32
        for c in contexts:lib.bc_runtime_actor_events(slot,C.byref(e),C.byref(c))
        assert bytes(e)==before
        assert bytes(scores[0])==bytes(scores[1]),(case,'score/order')
        assert bytes(defeats[0])==bytes(defeats[1]),(case,'defeat')
        assert bytes(audio[0])==bytes(audio[1]),(case,'audio/order/overflow')
        assert final[0]==final[1],(case,'ending')
        if case%40==39:
            for q in audio:q.count=q.dropped=0
    assert calls[0]==5000 and calls[1]<=5000-silent
    assert final[0]
    print(f'PASS: 5000 events; {calls[0]-calls[1]} empty deliveries skipped; identical scores, sound order/overflow, boss defeats and ending requests; default observers preserved')

    # Compare the caller-side simple-event guard with a wrapper that always
    # reaches the public dispatcher. Both consume the same complete actor loop.
    from qa_bc_actor_loop import Actor, Player, StepData, Data
    lib.bc_runtime_actor_loop.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8,Sink,C.c_void_p]
    lib.bc_runtime_actor_loop.restype=C.c_uint8
    direct=Sink(C.cast(lib.bc_runtime_actor_events,C.c_void_p).value)
    @Sink
    def indirect(slot,event,context):
        lib.bc_runtime_actor_events(slot,event,C.cast(context,C.POINTER(RuntimeEvents)))
    program=(C.c_uint8*65536)();data=StepData();data.data=Data(program,0)
    final_code=(ROOT/'.local/pce-reference/round10-protected/code-002160.bin').read_bytes()
    final_program=(C.c_uint8*len(final_code)).from_buffer_copy(final_code)
    seed=C.c_uint16();data.random_state=C.pointer(seed)
    cells=(C.c_uint8*16384)();attributes=(C.c_uint8*2048)()
    data.terrain.cells=cells;data.terrain.attributes=attributes
    deliveries=[[],[]]
    def observe(index):
        @Sink
        def callback(slot,event,context):
            e=event.contents
            deliveries[index].append((slot,bytes(e.actor_event),e.extra_count,
                tuple(e.extra_slots[:e.extra_count]),tuple(bytes(v) for v in e.extra_events[:e.extra_count])))
            lib.bc_audio_actor_append(C.byref(audio[index]),event)
        return callback
    observers=[observe(0),observe(1)]
    for case in range(256):
        data.round=9 if case&16 else 0
        data.data=Data(final_program,0x4000) if data.round==9 else Data(program,0)
        data.relocation=-535 if data.round==9 else 0;data.bullet_base=0x23a
        pool=(Actor*32)();player=Player();player.state=128;player.x=player.y=100<<8
        player.inventory.lives=3;player.invulnerability=case&1
        for slot in range(8):
            a=pool[slot];a.routine=0x9eb1;a.body.state=128;a.body.timer=20
            a.body.x=(100 if slot==0 else 140+slot*8)<<8;a.body.y=100<<8
            a.body.flags=(case>>1)&3;a.body.hp=1;a.body.score_id=12
            a.half_x=a.half_y=8
        # Homing tasks share the simple-event envelope in the optimized
        # general loop. Include both turn expiry and terrain-hit early return.
        for quadrant in (1,3,5,7):attributes[quadrant]=1 if case&128 else 0
        if not (case&16):
            for slot in (4,5):
                pool[slot].routine=0x8b17+data.relocation
                pool[slot].wait=1 if case&64 else 5
                pool[slot].direction=slot;pool[slot].speed=0
        serpent=bool(case&16 and case&32)
        if serpent:
            a=pool[0];a.routine=0xa446;a.dash_started=0x48;a.wait=10;a.phase=1
            a.body.flags=3
        shot=player.weapons.shots[0].body
        shot.state=128;shot.x=shot.y=100<<8;shot.half_x=shot.half_y=4;shot.damage=2
        pools=[(Actor*32).from_buffer_copy(pool) for _ in range(2)]
        players=[Player.from_buffer_copy(player) for _ in range(2)]
        scores=[Score(),Score()];audio=[Queue(),Queue()];deliveries=[[],[]]
        contexts=[RuntimeEvents(C.pointer(scores[i]),1,(case>>3)&1,C.cast(observers[i],C.c_void_p),None,None) for i in range(2)]
        counts=[C.c_uint8(),C.c_uint8()]
        for i,sink in enumerate((indirect,direct)):
            seed.value=0
            assert lib.bc_runtime_actor_loop(pools[i],0,C.byref(players[i]),C.byref(data),C.byref(counts[i]),16,0,0,1,sink,C.addressof(contexts[i]))==32
        assert bytes(pools[0])==bytes(pools[1]) and bytes(players[0])==bytes(players[1])
        assert counts[0].value==counts[1].value and bytes(scores[0])==bytes(scores[1])
        assert bytes(audio[0])==bytes(audio[1]) and deliveries[0]==deliveries[1]
        if serpent:assert any(e[2]==8 for e in deliveries[1]), 'serpent burst was filtered'
        if not contexts[0].effects_only:assert len(deliveries[0])>=8 if serpent else len(deliveries[0])==8
    print('PASS: 256 complete general/final actor loops through direct/wrapped sinks, including homing turns/terrain hits and serpent child bursts; matching gameplay, scores, audio and opt-out observer deliveries')
