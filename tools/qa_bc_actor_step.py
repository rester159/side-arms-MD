#!/usr/bin/env python3
"""Compare complete translated actor updates, including immediate child tasks.
Unknown source handlers are counted separately and must leave native state intact.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT,Beam,decode
from qa_bc_factory import Actor,actor
from qa_bc_enemies import Data,Enemy
from qa_bc_common import Player,Event as CommonEvent
from qa_bc_player_flow import state
from qa_bc_rules import Terrain


class StepData(C.Structure):
    _fields_=[('data',Data),('bullet_base',C.c_uint16),('small_base',C.c_uint16),
              ('large_base',C.c_uint16),('relocation',C.c_int16),('round',C.c_uint8),
              ('terrain',Terrain),('camera_x',C.c_uint16),('camera_y',C.c_uint16),('bullet_death_base',C.c_uint16),('random_state',C.POINTER(C.c_uint16)),('homing_inherited_base',C.c_uint16),('boss_active',C.c_uint8),('boss_spread_base',C.c_uint16),('homing_base',C.c_uint16),('scheduler_counter',C.c_uint8),('boss_beam_base',C.c_uint16)]


class Event(C.Structure):
    _fields_=[('actor_event',CommonEvent),('child_event',CommonEvent),('child_slot',C.c_int16),
              ('setup_sound',C.c_uint8),('fire_requested',C.c_uint8),('handled',C.c_uint8),('extra_count',C.c_uint8),('extra_slots',C.c_int16*10),('extra_events',CommonEvent*10),('boss_defeat',C.c_uint8),('boss_center_y',C.c_uint16)]


def verify(capture,code):
    raw=(capture/'actor-step.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    def shot_body(r,j):
        b=decode(r,j);b.accelerating=r[0xcdc+j]*256+r[0xcfa+j] in custom
        b.facing=r[0xdae+j]==0x52
        return b
    rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_actor_step.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),
            C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8]
        lib.bc_actor_step.restype=Event
        counts={};unsupported={};children=deaths=retired=boss_children=defeats=0
        hopper_delay=hopper_landings=hopper_shots=hopper_wall_hits=0
        jumper_phases=set();jumper_turn_updates=jumper_shots=0
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end==1 and i==i2 and f2>=f
            r=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            assert not r[0x49], 'Global debug invulnerability is not a native gameplay rule; use a protection-timer fixture'
            pool=(Actor*32)(*(actor(r,j,program) for j in range(32)))
            player=state(r).world;count=C.c_uint8(r[0x59])
            for j,shot in enumerate(player.weapons.shots):
                shot.body=shot_body(r,j)
                shot.kind=4 if j>=28 else 2 if r[0xd90+j] else 0
                shot.tier=r[0xdea+j];shot.launch_wait=r[0xc28+j]
            def base(address):return int.from_bytes(r[address-0x2000:address-0x2000+2],'big')
            bullet_ref=int.from_bytes(program[0x4aaf+shift:0x4ab1+shift],'little')
            attrs=int.from_bytes(r[0x44:0x46],'little')-0x4000
            terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
            seed=C.c_uint16(int.from_bytes(r[0x6c:0x6e],'little'))
            data=StepData(Data(rom,0x4000),base(bullet_ref),base(0x367c),base(0x367e),shift,r[0x4b],
                          terrain,int.from_bytes(r[0x2e:0x30],'big'),int.from_bytes(r[0x31:0x33],'big'),base(0x367a),C.pointer(seed),base(0x3684),r[0x5e],base(0x36b4 if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36c6 else 0x36ce if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36ba else 0x36cc if r[0x4b]==8 and int.from_bytes(r[0x11e8:0x11e9]+r[0x1208:0x1209],"big")in (0x36c4,0x36c0) else 0x36ce if r[0x4b]==5 else 0x36b4 if r[0x4b] in (3,6) else 0x36cc if r[0x4b] in (1,7) else 0x36c8),base(0x3682),r[0x12],base(0x3698 if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36c6 else 0x36ca if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36b8 else 0x3698 if r[0x4b]==6 else 0x36ca if r[0x4b]==4 else 0x36c8))
            saved_pool=bytes(pool);saved_player=bytes(player)
            handler=pool[i].routine if pool[i].body.state==128 else pool[i].death_routine
            event=lib.bc_actor_step(pool,i,C.byref(player),C.byref(data),C.byref(count),r[0x58],
                int.from_bytes(r[0x40:0x42],'big',signed=True),int.from_bytes(r[0x42:0x44],'big',signed=True),r[0x48])
            if not event.handled:
                assert bytes(pool)==saved_pool and bytes(player)==saved_player and count.value==r[0x59]
                assert seed.value==int.from_bytes(r[0x6c:0x6e],'little')
                unsupported[hex(handler)]=unsupported.get(hex(handler),0)+1
                continue
            for j in range(32):
                want=actor(after,j,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[j].body,field)==getattr(want.body,field),(f,i,j,'body',field,getattr(pool[j].body,field),getattr(want.body,field))
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[j],field)==getattr(want,field),(f,i,j,field)
            expected=state(after).world
            for field in ('x','y','state','invulnerability'):
                assert getattr(player,field)==getattr(expected,field),(f,i,'player',field)
            assert bytes(player.inventory)==bytes(expected.inventory),(f,i,'inventory')
            for j,shot in enumerate(player.weapons.shots):
                want=shot_body(after,j)
                for field,_ in Beam._fields_:
                    assert getattr(shot.body,field)==getattr(want,field),(f,i,j,'shot',field)
            assert count.value==after[0x59],(f,i,'count')
            assert seed.value==int.from_bytes(after[0x6c:0x6e],'little'),(f,i,'random seed')
            assert player.weapons.returning==after[0x5a] and bytes(player.weapons.option_shots)==after[0x5b:0x5d]
            if handler==0xaed3 and r[0x4b]==0:
                jumper_phases.add(r[0x1308+i]);jumper_turn_updates+=bool(r[0x1348+i]);jumper_shots+=event.fire_requested
            if handler==0xb11f and r[0x4b]==0:
                hopper_delay+=bool(r[0x10a8+i])
                hopper_landings+=not r[0x10a8+i] and bool(after[0x10a8+i])
                hopper_shots+=event.fire_requested
                hopper_wall_hits+=not r[0x10a8+i] and r[0x1308+i]!=after[0x1308+i]
            counts[hex(handler)]=counts.get(hex(handler),0)+1
            if event.boss_defeat == 2:
                assert r[0x4b]==9 and handler==0xa579 and after[0x50]==1
                defeats+=1
            elif event.boss_defeat == 1:
                assert event.boss_center_y==int.from_bytes(after[0x60:0x62],'big'),(f,'boss effect center')
                assert event.setup_sound==13
                defeats+=1
            boss_children+=event.extra_count
            children+=event.child_slot>=0;deaths+=event.actor_event.player_died;retired+=event.actor_event.retired
        assert counts
        return dict(module='complete native actor step for translated handlers',updates=sum(counts.values()),
            handlers=counts,jumper_phases=sorted(jumper_phases),jumper_turn_updates=jumper_turn_updates,
            jumper_fire_requests=jumper_shots,hopper_delay_updates=hopper_delay,hopper_landings=hopper_landings,
            hopper_fire_requests=hopper_shots,hopper_wall_hits=hopper_wall_hits,child_updates=children,player_deaths=deaths,retirements=retired,
            boss_defeat_requests=defeats,boss_child_updates=boss_children,unsupported_updates=sum(unsupported.values()),unsupported_handlers=unsupported,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
