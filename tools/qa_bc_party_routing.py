#!/usr/bin/env python3
"""Exercise co-op through the production actor loop and a real boss child-birth path."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_common import Player, Event as Contact
from qa_bc_factory import Actor
from qa_bc_actor_step import StepData, Event
from qa_bc_enemies import Data
from qa_bc_beam import ROOT

ContactSink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Contact),C.c_void_p)
ActorSink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
class Party(C.Structure):
    _fields_=[('players',C.POINTER(Player)*4),('count',C.c_uint8),('contact_policy',C.c_uint8),
              ('contact',ContactSink),('context',C.c_void_p)]+[(n,C.c_uint8) for n in ('shot_bounds_valid','shot_min_x','shot_max_x','shot_min_y','shot_max_y','shot_half_x','shot_half_y','body_bounds_valid')]+[(n,C.c_uint16) for n in ('body_min_x','body_max_x','body_min_y','body_max_y')]

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'party.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio')),
        '-o',str(path)],check=True)
    lib=C.CDLL(str(path))
    lib.bc_runtime_actor_loop.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),
        C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8,ActorSink,C.c_void_p]
    lib.bc_runtime_actor_loop.restype=C.c_uint8
    lib.bc_actor_step_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),C.c_uint8,
        C.POINTER(Player),C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8]
    received=[];ordinary=[]
    @ContactSink
    def contact(slot,event,context):
        received.append((slot,bytes(event.contents)))
    @ActorSink
    def sink(slot,event,context):
        ordinary.append((slot,event.contents.actor_event.score_pending,event.contents.actor_event.sound))
    def party():
        players=(Player*4)()
        group=Party((C.POINTER(Player)*4)(*(C.pointer(p) for p in players)),4,0,contact,None)
        for p in players:p.party=C.addressof(group);p.state=0x80;p.x=p.y=20<<8
        return players,group
    rom=(C.c_uint8*65536)();data=StepData();data.data=Data(rom,0)
    for scenario in range(32):
        unsupported=bool(scenario&1)
        received.clear();ordinary.clear();ps,group=party();pool=(Actor*32)()
        dead_weapons={}
        for bit,member_id in enumerate((0,1,3)):
            if (scenario>>1)&(1<<bit):
                member=ps[member_id]
                member.state=0x40 if scenario&16 else 0
                for shot in member.weapons.shots:
                    shot.body.state=0x80;shot.body.x=shot.body.y=100<<8
                    shot.body.damage=255;shot.body.half_x=shot.body.half_y=8
                dead_weapons[member_id]=bytes(member.weapons)
        for i in range(2):
            b=pool[i].body;b.state=0x80;b.timer=10;b.x=b.y=100<<8;b.vx=256
            b.flags=2;b.hp=1;b.score_id=12;pool[i].half_x=pool[i].half_y=8;pool[i].routine=0x9eb1
        pool[1].body.x=200<<8
        if unsupported:pool[1].routine=0xffff
        for i,p in enumerate(ps):p.shot_index=0x1000+i*256
        shot=ps[2].weapons.shots[0].body
        shot.state=0x80;shot.x=shot.y=100<<8;shot.damage=1;shot.half_x=shot.half_y=4
        count=C.c_uint8()
        result=lib.bc_runtime_actor_loop(pool,0,C.byref(ps[0]),C.byref(data),C.byref(count),16,0,0,1,sink,None)
        assert result==(1 if unsupported else 32)
        assert all(bytes(ps[i].weapons)==before for i,before in dead_weapons.items())
        assert [p.shot_index for p in ps]==[0x1000+i*256 for i in range(4)]
        assert pool[0].body.state==0x40 and pool[0].body.timer==9 and pool[0].body.x==101<<8
        assert len(received)==1 and received[0][0]==2
        event=Contact.from_buffer_copy(received[0][1]);assert event.score_pending and event.score_id==12
        assert ordinary[0]==(0,0,0), 'duplicate score/audio via legacy sink'
        assert group.contact_policy==0 and not group.shot_bounds_valid and not group.body_bounds_valid, 'cache escaped its actor pass'
    # Losing the last living player must invalidate the fast-path cache before
    # the next immune actor: its cooldown no longer has a living-player tick.
    received.clear();ordinary.clear();ps,group=party();pool=(Actor*32)()
    ps[0].x=ps[0].y=100<<8
    for p in ps[1:]:p.state=0
    for i in range(2):
        b=pool[i].body;b.state=128;b.timer=10;b.x=b.y=100<<8
        b.flags=1 if i==0 else 3;b.cooldown=2
        pool[i].routine=0x9eb1;pool[i].half_x=pool[i].half_y=8
    count=C.c_uint8()
    assert lib.bc_runtime_actor_loop(pool,0,C.byref(ps[0]),C.byref(data),C.byref(count),16,0,0,1,sink,None)==32
    assert ps[0].state==64 and pool[0].body.cooldown==1 and pool[1].body.cooldown==2
    assert group.contact_policy==0 and not group.shot_bounds_valid and not group.body_bounds_valid
    # A real final-boss eight-shot birth must hit P2 in the immediate common
    # update, before any of those child slots receive their later loop turn.
    received.clear();ordinary.clear();ps,group=party();pool=(Actor*32)()
    ps[1].x=ps[1].y=100<<8
    program=(ROOT/'.local/pce-reference/round10-protected/code-002160.bin').read_bytes()
    source=(C.c_uint8*len(program)).from_buffer_copy(program)
    data=StepData();data.data=Data(source,0x4000);data.round=9;data.relocation=-535;data.bullet_base=0x23a
    seed=C.c_uint16(0);data.random_state=C.pointer(seed)
    head=pool[0];head.body.state=0x80;head.body.timer=10;head.body.flags=3
    head.body.x=head.body.y=100<<8;head.routine=0xa446;head.dash_started=0x48;head.wait=10;head.phase=1
    event=Event();count=C.c_uint8()
    lib.bc_actor_step_into(C.byref(event),pool,0,C.byref(ps[0]),C.byref(data),C.byref(count),16,0,0,1)
    assert event.handled and event.extra_count==8 and count.value==8
    assert ps[1].state==0x40 and all(ps[i].state==0x80 for i in (0,2,3))
    deaths=[i for i,raw in received if Contact.from_buffer_copy(raw).player_died]
    assert deaths==[1] and all(not e.sound for e in event.extra_events[:8])
    assert all(p.shot_index is None for p in ps)
    # Contact callbacks can change effects_only during an actor update. The
    # aggregate observer must use the new value for that very same actor.
    from qa_bc_actor_loop import RuntimeEvents
    direct=ActorSink(C.cast(lib.bc_runtime_actor_events,C.c_void_p).value)
    for initial in (0,1):
        ps,group=party();pool=(Actor*32)();program=(C.c_uint8*65536)()
        program[0]=255;data=StepData();data.data=Data(program,0)
        context=RuntimeEvents();context.playing=1;context.effects_only=initial
        observed=[];retirement_contacts=[]
        @ActorSink
        def observe_retirement(slot,event,unused):
            e=event.contents
            observed.append((slot,bytes(e.actor_event),bytes(e.child_event),e.child_slot,
                e.extra_count,e.setup_sound,e.boss_defeat))
        @ContactSink
        def toggle_filter(player,event,unused):
            retirement_contacts.append((player,bytes(event.contents)))
            context.effects_only^=1
        context.next=C.cast(observe_retirement,C.c_void_p)
        group.contact=toggle_filter
        for i in range(2):
            pool[i].routine=0x9eb1;pool[i].body.state=128
            pool[i].body.timer=1;pool[i].body.flags=4
        count=C.c_uint8(2)
        assert lib.bc_runtime_actor_loop(pool,0,C.byref(ps[0]),C.byref(data),C.byref(count),16,
            0,0,1,direct,C.addressof(context))==32
        retired=bytes([1]+[0]*7)
        assert retirement_contacts==[(0,retired),(0,retired)] and count.value==0
        assert observed==[(0 if initial else 1,retired,bytes(8),-1,0,0,0)],(initial,observed)
print('PASS: 32 live/dead/dying player and early-exit combinations with occupied dead weapon pools; P3 kill ownership, no duplicate events, four index restores on normal/early exit, P2 immediate boss-bullet contact; same-actor filtering changes from retirement callbacks with complete zeroed records')
