#!/usr/bin/env python3
"""Differential check: production streamed contacts vs the record-array task."""
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_common import Player,Event
from qa_bc_factory import Actor
from qa_bc_enemies import Data
from qa_bc_beam import ROOT
Sink=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
class Party(C.Structure):
    _fields_=[('players',C.POINTER(Player)*4),('count',C.c_uint8),('contact_policy',C.c_uint8),('contact',Sink),('context',C.c_void_p)]+[(n,C.c_uint8) for n in ('shot_bounds_valid','shot_min_x','shot_max_x','shot_min_y','shot_max_y','shot_half_x','shot_half_y','body_bounds_valid')]+[(n,C.c_uint16) for n in ('body_min_x','body_max_x','body_min_y','body_max_y')]
class ShotIndex(C.Structure):
    _fields_=[('slots',C.c_uint8*28),('count',C.c_uint8),('x',C.c_uint8*28),('y',C.c_uint8*28)]+[
        (name,C.c_uint8) for name in ('min_x','max_x','min_y','max_y','half_x','half_y')]
with tempfile.TemporaryDirectory() as directory:
    library=Path(directory)/'contacts.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(library)],check=True)
    lib=C.CDLL(str(library))
    lib.bc_actor_common_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),C.POINTER(Player),C.POINTER(Data),C.POINTER(C.c_uint8)]
    lib.bc_actor_party_common_into.argtypes=[C.POINTER(Event),C.POINTER(Actor),C.POINTER(C.POINTER(Player)),C.c_uint8,C.POINTER(Data),C.POINTER(C.c_uint8)]
    rom=(C.c_uint8*65536)();data=Data(rom,0);rng=random.Random(0xbc4)
    seen=empty_policy=bounds_cases=vulnerable_bounds_cases=empty_vulnerable_cases=0
    for case in range(32000):
        n=rng.choice((1,2,3,4));actor=Actor();b=actor.body
        b.x=rng.choice((0,100,101,300,400,65535))<<8;b.y=100<<8
        b.vx=rng.choice((-256,0,256));b.state=rng.choice((128,128,128,64));b.timer=rng.choice((1,2,20))
        b.flags=rng.choice((0,1,2,3,4,8,9,10,32,34));b.hp=rng.choice((1,2,10,20));b.bars=2;b.score_id=12
        b.cooldown=rng.choice((0,0,1,2,255));b.damage_lock=rng.choice((0,0,1,2))
        actor.half_x=actor.half_y=8;actor.pickup=rng.randrange(10) if b.flags&1 else 0
        actor.sprite_base_ref=rng.choice((0,0x36d0));actor.health_fraction=rng.randrange(3 if n==3 else 9)
        if case >= 16000:
            actor.half_x = rng.choice((0,4,8,127,247,250,251,255))
            actor.half_y = rng.choice((0,4,8,127,247,248,250,255))
            b.y = rng.choice((0,32,100,128,255,65535)) << 8
        players=(Player*4)()
        for p in players:
            p.x=rng.choice((20,100,101,180))<<8;p.y=100<<8
            p.state=rng.choice((0,64,128,128,128));p.invulnerability=rng.choice((0,0,1,200))
            p.inventory.lives=3
            for shot in p.weapons.shots[:6]:
                shot.body.state=rng.choice((0,64,128));shot.body.x=rng.choice((20,100,101,180))<<8
                shot.body.y=100<<8;shot.body.half_x=shot.body.half_y=4
                shot.body.damage=rng.choice((0,1,2,10,255));shot.kind=rng.choice((0,2))
            players_options=rng.randrange(3)
            if players_options:p.weapons.shots[27+players_options].body.state=128
        if case >= 12000 and case % 8 == 3:
            players[0].state = 128
            for p in players:
                p.invulnerability = 200
                for shot in p.weapons.shots: shot.body.state = 0
        indices=(ShotIndex*4)()
        if case >= 12000 and case % 8 == 7:
            players[0].state=128;players[0].invulnerability=0
            for p in players:
                for shot in p.weapons.shots:shot.body.state=0
        if case&2:
            for i,p in enumerate(players):
                lib.bc_shot_index(C.byref(indices[i]),C.byref(p.weapons))
                p.shot_index=C.addressof(indices[i])
        if case >= 20000:
            # Shot-immune, nonretiring actors expose wrapped body radii and
            # extreme 16-bit positions instead of retiring before contact.
            b.flags |= 33; b.vx=b.vy=0; b.timer=20
            b.x=rng.choice((0,1,255,256,65534,65535))<<8
            b.y=rng.choice((0,1,255,256,65534,65535))<<8
            actor.half_x=rng.choice((0,4,127,250,251,252,255))
            actor.half_y=rng.choice((0,4,127,247,248,249,255))
            for i,p in enumerate(players):
                p.x=b.x if case%3==0 else rng.choice((0,1,255,256,65534,65535))<<8
                p.y=b.y if case%3==0 else rng.choice((0,1,255,256,65534,65535))<<8
                if i==0:p.state=128;p.invulnerability=0
        reference=Actor.from_buffer_copy(actor);peers=(Player*4).from_buffer_copy(players)
        ptrs=(C.POINTER(Player)*4)(*(C.pointer(p) for p in players))
        expected_ptrs=(C.POINTER(Player)*4)(*(C.pointer(p) for p in peers))
        # Absent slots remain absent in both entry points.
        for i in range(1,n):
            if rng.randrange(5)==0:ptrs[i]=C.POINTER(Player)();expected_ptrs[i]=C.POINTER(Player)()
        received=[]
        @Sink
        def sink(slot,event,context):received.append((slot,bytes(event.contents)))
        living=[p.contents for p in ptrs[:n] if p and p.contents.state==128]
        policy=0 if not case&1 else 1 if not living else 3 if any(not p.invulnerability for p in living) else 2
        if policy == 2 and case & 2 and all(
            not C.cast(p.shot_index,C.POINTER(ShotIndex)).contents.count for p in living):
            policy = 4
            if n > 1: empty_policy += 1
        party=Party(ptrs,n,policy,sink,None)
        if policy in (2,3) and case & 2:
            active=[C.cast(p.shot_index,C.POINTER(ShotIndex)).contents for p in living]
            active=[i for i in active if i.count]
            if active:
                party.shot_bounds_valid=1
                bounds_cases += n > 1
                vulnerable_bounds_cases += n > 1 and policy == 3 and not b.flags & 1
                party.shot_min_x=min(i.min_x for i in active);party.shot_min_y=min(i.min_y for i in active)
                party.shot_max_x=max(i.max_x for i in active);party.shot_max_y=max(i.max_y for i in active)
                party.shot_half_x=max(i.half_x for i in active);party.shot_half_y=max(i.half_y for i in active)
            else:
                party.shot_bounds_valid=2
                empty_vulnerable_cases += n > 1 and policy == 3
        vulnerable=[p for p in living if not p.invulnerability]
        if vulnerable and case & 1:
            party.body_bounds_valid=1
            party.body_min_x=min((p.x>>8)&65535 for p in vulnerable)
            party.body_max_x=max((p.x>>8)&65535 for p in vulnerable)
            party.body_min_y=min((p.y>>8)&65535 for p in vulnerable)
            party.body_max_y=max((p.y>>8)&65535 for p in vulnerable)
        # Production uses NULL for 1P; a party context is valid only for 2–4P.
        for p in players:p.party=C.addressof(party) if n > 1 else None
        expected=(Event*4)();actual=Event();count=C.c_uint8(12);ref_count=C.c_uint8(12)
        lib.bc_actor_party_common_into(expected,C.byref(reference),expected_ptrs,n,C.byref(data),C.byref(ref_count))
        lib.bc_actor_common_into(C.byref(actual),C.byref(actor),C.byref(players[0]),C.byref(data),C.byref(count))
        assert bytes(actor)==bytes(reference) and count.value==ref_count.value,(case,'actor/clocks')
        expected_events=[(i,bytes(e)) for i,e in enumerate(expected[:n]) if any(bytes(e))]
        if n > 1 and any(e.player_died for e in expected):assert party.contact_policy==0
        if n==1:
            assert not received and bytes(actual)==bytes(expected[0]),(case,'solo event')
        else:
            assert received==expected_events,(case,'event order',received,expected_events)
            assert actual.retired==int(any(e.retired for e in expected)) and not any(bytes(actual)[1:])
        for p in players:p.party=0
        assert bytes(players)==bytes(peers),(case,'players/weapons/inventory')
        seen+=len(expected_events)
assert empty_policy > 300, empty_policy
assert bounds_cases > 100, bounds_cases
assert vulnerable_bounds_cases > 100, vulnerable_bounds_cases
assert empty_vulnerable_cases > 100, empty_vulnerable_cases
print(f'Covered {empty_vulnerable_cases} empty vulnerable-party shot unions')
print(f'Covered {vulnerable_bounds_cases} ordinary-actor vulnerable-party shot unions')
print(f'PASS: 32000 1P/2P/3P/4P cached/uncached event comparisons with indexed/unindexed shots, {seen} ordered events, {empty_policy} empty/protected party cases, {bounds_cases} aggregate shot bounds, actors/clocks, fractional boss health, player damage, pickups, options, null/dead/protected slots')
