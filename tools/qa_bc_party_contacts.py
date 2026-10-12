#!/usr/bin/env python3
"""Co-op contact semantics: single actor clock, ordered shots and pickup ownership."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_common import Player,Event
from qa_bc_factory import Actor
from qa_bc_enemies import Data
from qa_bc_beam import ROOT

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'party.dylib'
    layout=Path(directory)/'layout.c'
    layout.write_text('#include <stddef.h>\n#include "bc_world.h"\n'
                      'unsigned actor_size(void) { return sizeof(BcActor); }\n'
                      'unsigned fraction_offset(void) { return offsetof(BcActor, health_fraction); }\n')
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                    '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),str(layout),
                    '-o',str(path)],check=True)
    lib=C.CDLL(str(path))
    lib.bc_actor_party_common_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),
        C.POINTER(C.POINTER(Player)),C.c_uint8,C.POINTER(Data),C.POINTER(C.c_uint8)]
    rom=(C.c_uint8*65536)();data=Data(rom,0)
    def fixture(hp=20):
        a=Actor();b=a.body
        b.x=b.y=100<<8;b.vx=256;b.state=0x80;b.timer=10;b.hp=hp;b.flags=2;b.score_id=12
        a.half_x=a.half_y=8
        players=(Player*4)()
        for p in players:
            p.x=p.y=20<<8;p.state=0x80
            s=p.weapons.shots[0];s.body.state=0x80;s.body.x=s.body.y=100<<8
            s.body.half_x=s.body.half_y=4;s.body.damage=1
        return a,players
    def step(a,players,n=4):
        pointers=(C.POINTER(Player)*4)(*(C.pointer(p) for p in players))
        events=(Event*4)();count=C.c_uint8(7)
        lib.bc_actor_party_common_into(events,C.byref(a),pointers,n,C.byref(data),C.byref(count))
        return events,count.value
    for n in (1,2,3,4):
        a,ps=fixture();ev,count=step(a,ps,n)
        assert (a.body.x,a.body.timer,a.body.hp)==(101<<8,9,20-n)
        assert [p.weapons.shots[0].body.state for p in ps]==[0x40]*n+[0x80]*(4-n)
        assert count==7 and not any(e.score_pending for e in ev)
    # A lethal hit belongs to P3; P4's shot survives the retired target.
    a,ps=fixture(3);ev,_=step(a,ps)
    assert a.body.state==0x40 and [e.score_pending for e in ev]==[0,0,1,0]
    assert ev[2].score_id==12 and ps[3].weapons.shots[0].body.state==0x80
    # Countdown once, after/before the same phases as the original 1P task.
    for field,start,end in [('cooldown',2,1),('cooldown',255,255),('damage_lock',1,0)]:
        a,ps=fixture();setattr(a.body,field,start);ev,_=step(a,ps)
        assert getattr(a.body,field)==end and a.body.hp==20
        assert all(p.weapons.shots[0].body.state==0x40 for p in ps)
    # A boss bar cannot be exhausted repeatedly in one update.
    a,ps=fixture(1);a.body.flags=10;a.body.bars=2;ev,_=step(a,ps,2)
    assert (a.body.bars,a.body.hp,a.body.cooldown,a.body.damage_lock)==(1,10,30,29)
    assert ev[0].sound==4 and all(p.weapons.shots[0].body.state==0x80 for p in ps[1:])
    # Exact effective boss health, including fractional carry between bars.
    # Only P1 fires; other participants remain present and alive. Protection
    # between bars is skipped here so this measures damage, not elapsed time.
    lib.actor_size.restype=lib.fraction_offset.restype=C.c_uint
    assert C.sizeof(Actor)==lib.actor_size(), 'Python/C actor size mismatch'
    assert Actor.health_fraction.offset==lib.fraction_offset(), 'Python/C health remainder offset mismatch'
    for n in (1,2,3,4):
        for boss,bars,hp in [('ordinary',0,20),('serpent',0,20),
                             ('composite',2,10),('composite',3,10)]:
            a,ps=fixture(hp);a.body.vx=0
            if boss=='serpent':a.sprite_base_ref=0x36d0
            if boss=='composite':a.body.flags=10;a.body.bars=bars
            baseline=bars*10 if bars else hp
            numerator,denominator=((3,2) if n==3 else (9,4) if n==4 else (1,1))
            expected=((baseline*numerator+denominator-1)//denominator
                      if boss!='ordinary' else baseline)
            for hit in range(1,expected+1):
                a.body.timer=255;a.body.cooldown=a.body.damage_lock=0
                for p in ps:p.weapons.shots[0].body.state=0
                ps[0].weapons.shots[0].body.state=0x80
                ev,_=step(a,ps,n)
                assert (a.body.state==0x40)==(hit==expected),(n,boss,bars,hit,expected,a.body.hp)
            assert ev[0].score_pending and not any(e.score_pending for e in ev[1:])
    # Multi-damage hits retain their remainder; invulnerable hits do not bank
    # damage that could be applied when protection expires.
    for n,first_hp,remainder in [(3,19,1),(4,20,8)]:
        a,ps=fixture();a.body.vx=0;a.sprite_base_ref=0x36d0
        for p in ps[1:]:p.weapons.shots[0].body.state=0
        ps[0].weapons.shots[0].body.damage=2
        step(a,ps,n)
        assert (a.body.hp,a.health_fraction)==(first_hp,remainder)
        for field in ('cooldown','damage_lock'):
            setattr(a.body,field,10);ps[0].weapons.shots[0].body.state=0x80
            step(a,ps,n)
            assert (a.body.hp,a.health_fraction)==(first_hp,remainder)
            setattr(a.body,field,0)
        ps[0].weapons.shots[0].body.state=0x80;step(a,ps,n)
        assert a.body.hp==(18 if n==3 else 19)
    # Slot reuse cannot inherit a former boss's fractional damage.
    lib.bc_actor_template.argtypes=[C.POINTER(Actor),C.POINTER(C.c_uint8),C.c_uint16]
    record=(C.c_uint8*19)();record[0]=0x80;record[4]=20
    a.health_fraction=8;lib.bc_actor_template(C.byref(a),record,0)
    assert a.health_fraction==0 and a.body.hp==20
    # Dead players do not consume shots, pickups or the first live slot's turn.
    a,ps=fixture(1);ps[0].state=0;ev,_=step(a,ps)
    assert ev[1].score_pending and ps[0].weapons.shots[0].body.state==0x80
    # A pickup is awarded once to P2, with its lives/options remaining private.
    a,ps=fixture();a.body.flags=1;a.pickup=9
    for p in ps:p.inventory.lives=3
    for p in ps[1:]:p.x=p.y=100<<8
    ev,_=step(a,ps)
    assert a.body.state==0 and [p.inventory.lives for p in ps]==[3,4,3,3]
    assert [e.pickup for e in ev]==[0,9,0,0]
    # A persistent boss may contact all four; only P3's option absorbs its hit.
    a,ps=fixture();a.body.flags=9
    for p in ps:p.x=p.y=100<<8
    ps[2].weapons.shots[28].body.state=0x80
    ev,_=step(a,ps)
    assert [p.state for p in ps]==[0x40,0x40,0x80,0x40]
    assert ps[2].invulnerability==16 and ps[2].weapons.shots[28].body.state==0x40
    assert ev[2].option_absorbed==1 and sum(e.player_died for e in ev)==3
    # Offscreen limited shots retire once, independent of player count.
    a,ps=fixture();a.body.x=400<<8;a.body.flags=4;ev,count=step(a,ps)
    assert a.body.state==0 and count==6 and ev[0].retired
    # Death animation and no-live-player updates still advance a single clock.
    for state in (0x40,0x80):
        a,ps=fixture();a.body.state=state;a.body.cooldown=2;a.body.damage_lock=3
        for p in ps:p.state=0
        ev,_=step(a,ps)
        assert a.body.timer==9 and a.body.cooldown==2 and a.body.damage_lock==2
        assert a.body.x==(100 if state==0x40 else 101)<<8
print('PASS: exact 1/1/1.5/2.25 boss health, fractional bars, invulnerability, reuse; 1/2/3/4P ordered damage, single clocks, death ownership, boss bars, pickups, options and retirement')
