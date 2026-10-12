#!/usr/bin/env python3
"""Check native stage events from source handler entry through script advance.
This is per-event integration evidence; unported events remain explicit.
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
from qa_bc_player_flow import state as player_state
from qa_bc_stage import Stage,state as stage_state
from qa_bc_score import Score,decode as score_state


class Palette(C.Structure):
    _fields_=[('colors',C.c_uint16*256),('effect',C.c_uint8)]


def palette_state(r):
    return Palette((C.c_uint16*256)(*struct.unpack_from('<256H',r,0x848)),r[0x5f])


class Audio(C.Structure):
    _fields_=[('handler',C.c_uint16),('parameters',C.c_uint8*8),('state',C.c_uint8)]


class Resources(C.Structure):
    _fields_=[('data',Data)]+[(n,C.c_uint16) for n in ('hover','curve','hopper','launcher')]+[
        ('relocation',C.c_int16),('round',C.c_uint8),('jumper_base',C.c_uint16),('item_base',C.c_uint16),('score',C.POINTER(Score)),('playing',C.c_uint8),('fast_curve_base',C.c_uint16),('boss_base',C.c_uint16),('palette',C.POINTER(Palette)),('audio',C.POINTER(Audio)),('birth_sink',C.c_void_p),('birth_context',C.c_void_p),('ceiling_base',C.c_uint16),('segment_bases',C.c_uint16*6),('random_state',C.POINTER(C.c_uint16)),('fixed_turret_base',C.c_uint16),('walker_base',C.c_uint16),('orbiter_base',C.c_uint16),('terrain_jumper_base',C.c_uint16),('terrain_hopper_base',C.c_uint16),('turret_bases',C.c_uint16*3),('prepare_event',C.c_void_p)]


class Event(C.Structure):
    _fields_=[('actor_event',CommonEvent),('handler',C.c_uint16),('slot',C.c_int16),('status',C.c_uint8),('second_actor_event',CommonEvent),('wave_size',C.c_uint8)]


def verify(capture,code):
    raw=(capture/'stage-events.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    def shot_body(r,j):
        b=decode(r,j);b.accelerating=r[0xcdc+j]*256+r[0xcfa+j] in custom;b.facing=r[0xdae+j]==0x52
        return b
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'runtime.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{name}.c') for name in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_runtime_stage_event.argtypes=[C.POINTER(Stage),C.POINTER(Actor),C.POINTER(Player),
            C.POINTER(Resources),C.POINTER(C.c_uint8)];lib.bc_runtime_stage_event.restype=Event
        lib.bc_audio_acknowledge.argtypes=[C.POINTER(Audio)]
        audio_requests=0
        completed={};unsupported={};births=failures=score_commands=0;wave_sizes={}
        for off in range(0,len(raw),stride*2):
            f,_=struct.unpack_from('<IH',raw,off);f2,_=struct.unpack_from('<IH',raw,off+stride);assert f2>=f
            r=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            assert not r[0x49],'Use ordinary protection, not reference debug invulnerability'
            stage=stage_state(r);pool=(Actor*32)(*(actor(r,j,program) for j in range(32)))
            player=player_state(r).world;count=C.c_uint8(r[0x59])
            for j,shot in enumerate(player.weapons.shots):
                shot.body=shot_body(r,j);shot.kind=4 if j>=28 else 2 if r[0xd90+j] else 0
                shot.tier=r[0xdea+j];shot.launch_wait=r[0xc28+j]
            def base(template):
                if not template:return 0
                ref=int.from_bytes(program[template-0x4000+11:template-0x4000+13],'little')
                return int.from_bytes(r[ref-0x2000:ref-0x2000+2],'big')
            score=score_state(r);palette=palette_state(r);audio=Audio()
            templates=(0xc9dd,0,0,0) if r[0x4b]==8 else (0xb753,0,0xc28b,0) if r[0x4b]==7 else (0xb099,0,0xbdf0,0xbc1c) if r[0x4b]==6 else (0xb42a,0xb7fd,0xbd96,0) if r[0x4b]==5 else (0xb4a7,0,0xbc2e,0xba5a) if r[0x4b]==4 else (0xafd7,0,0xbc40,0xb2ae) if r[0x4b]==3 else (0xb0cf,0xbccc,0xb578,0xb3cc) if r[0x4b]==2 else (0xb58e,0xb91f,0xb2df,0xba33) if r[0x4b]==1 else (0xaca6,0xae54,0xb213,0xb31d)
            resources=Resources(Data(rom,0x4000),*(base(t) for t in templates),shift,r[0x4b],base(0xb915) if r[0x4b]==7 else base(0xb25b) if r[0x4b]==6 else base(0xb5ec) if r[0x4b]==5 else base(0xb669) if r[0x4b]==4 else base(0xb199) if r[0x4b]==3 else base(0xb291) if r[0x4b]==2 else base(0xb750) if r[0x4b]==1 else base(0xb0a5) if not r[0x4b] else 0,base(0x8908+shift),C.pointer(score),r[0x51],base(0xb65e) if r[0x4b]==7 else base(0xafa4) if r[0x4b]==6 else base(0xb335) if r[0x4b]==5 else base(0xb3b2) if r[0x4b]==4 else base(0xaee2) if r[0x4b]==3 else base(0xafda) if r[0x4b]==2 else base(0xb499) if r[0x4b]==1 else base(0xabb1) if not r[0x4b] else 0,base({0xb384:0xb656,0xaff2:0xb1ee,0xac32:0xaeaa,0xc18b:0xc394,0xa8c6:0xaae2,0xb8d4:0xbb9e,0xbcf0:0xbf23,0xc539:0xc742}.get(struct.unpack_from("<H",raw,off+4)[0]+shift,0xa6d9)) if r[0x4b]==8 else base(0xb279) if r[0x4b]==7 else base(0xacd5) if r[0x4b]==6 else base(0xb068) if r[0x4b]==5 else base(0xae59) if r[0x4b]==4 else base(0xa9e6) if r[0x4b]==3 else base(0xacc7) if r[0x4b]==2 else base(0xae67) if r[0x4b]==1 else base(0xb4b0) if not r[0x4b] else 0,C.pointer(palette),C.pointer(audio),None,None,base(0xbb1a) if r[0x4b]==7 else base(0xbb1c) if r[0x4b]==6 else base(0xb59a) if r[0x4b]==3 else base(0xb9a5) if r[0x4b]==2 else base(0xbe93) if r[0x4b]==1 else 0)
            for j in range(6):
                resources.segment_bases[j]=int.from_bytes(r[0x169e+j*2:0x16a0+j*2],'big')
            if r[0x4b]==9:
                for j in range(3):resources.segment_bases[j]=int.from_bytes(r[0x16d0+j*2:0x16d2+j*2],'big')
            seed=C.c_uint16(int.from_bytes(r[0x6c:0x6e],'little'))
            resources.random_state=C.pointer(seed)
            resources.fixed_turret_base=base(0xbd5f) if r[0x4b]==7 else base(0xba8a) if r[0x4b]==3 else base(0xba9a) if r[0x4b]==2 else 0
            resources.walker_base=base(0xb1f8) if r[0x4b]==4 else base(0xad28) if r[0x4b]==3 else 0
            resources.orbiter_base=base(0xafb6) if r[0x4b]==7 else base(0xadbc) if r[0x4b]==5 else 0
            resources.terrain_jumper_base=base(0xba57) if r[0x4b]==5 else 0
            resources.terrain_hopper_base=base(0xbbc5) if r[0x4b]==5 else 0
            if r[0x4b]==6:
                resources.turret_bases[:]=[base(t) for t in (0xb6bc,0xb58d,0xb370)]
            birth_events=[]
            callback_type=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(CommonEvent),C.c_void_p)
            callback=callback_type(lambda slot,event,context: birth_events.append((slot,event.contents.sound,event.contents.score_pending)))
            resources.birth_sink=C.cast(callback,C.c_void_p)
            original=(bytes(stage),bytes(pool),bytes(player),count.value,bytes(score),bytes(palette),seed.value)
            event=lib.bc_runtime_stage_event(C.byref(stage),pool,C.byref(player),C.byref(resources),C.byref(count))
            if event.status==3:
                assert original==(bytes(stage),bytes(pool),bytes(player),count.value,bytes(score),bytes(palette),seed.value)
                assert audio.handler==event.handler and audio.state==1
                assert bytes(audio.parameters)==after[0xf8:0x100],(f,'source BIOS audio parameters')
                waiting=lib.bc_runtime_stage_event(C.byref(stage),pool,C.byref(player),C.byref(resources),C.byref(count))
                assert waiting.status==3 and original==(bytes(stage),bytes(pool),bytes(player),count.value,bytes(score),bytes(palette),seed.value)
                lib.bc_audio_acknowledge(C.byref(audio))
                event=lib.bc_runtime_stage_event(C.byref(stage),pool,C.byref(player),C.byref(resources),C.byref(count))
                assert audio.state==0
                audio_requests+=1
            assert event.status in (1,2),(f,'expected due event')
            name=hex(event.handler)
            if event.status==2:
                assert original==(bytes(stage),bytes(pool),bytes(player),count.value,bytes(score),bytes(palette),seed.value)
                unsupported[name]=unsupported.get(name,0)+1;continue
            assert bytes(palette)==bytes(palette_state(after)),(f,name,'palette')
            want_stage=stage_state(after)
            for field,_ in Stage._fields_:
                assert getattr(stage,field)==getattr(want_stage,field),(f,name,'stage',field)
            for j in range(32):
                want=actor(after,j,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[j].body,field)==getattr(want.body,field),(f,name,j,field)
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[j],field)==getattr(want,field),(f,name,j,field)
            want_player=player_state(after).world
            for field in ('x','y','state','invulnerability'):
                assert getattr(player,field)==getattr(want_player,field),(f,name,'player',field)
            assert bytes(player.inventory)==bytes(want_player.inventory)
            for j,shot in enumerate(player.weapons.shots):
                want=shot_body(after,j)
                for field,_ in Beam._fields_:
                    assert getattr(shot.body,field)==getattr(want,field),(f,name,j,'shot',field)
            assert seed.value==int.from_bytes(after[0x6c:0x6e],'little'),(f,name,'RNG')
            assert count.value==after[0x59]
            assert bytes(score)==bytes(score_state(after)),(f,name,'score state')
            assert player.weapons.returning==after[0x5a] and bytes(player.weapons.option_shots)==after[0x5b:0x5d]
            # Handler addresses can refer to different families in different
            # rounds (round 2's $B5C5 is a single jumper, not round 3's chain).
            groups={(1,0xbd3c):4,(1,0xba7c):8,(1,0xba80):8,(1,0xab95):5,
                    (2,0xb881):2,(2,0xb5c1):8,(2,0xb5c5):8,(2,0xaacb):3,
                    (3,0xb6f6):8,(3,0xb6fa):8,(3,0xb3e7):5,(3,0xb3eb):5,
                    (3,0xb3f1):5,(3,0xa76e):3,(4,0xac50):3,(4,0xb6bb):8,(4,0xb6bf):8}
            group_size=groups.get((resources.round,event.handler))
            if group_size and event.slot>=0:
                assert [e[0] for e in birth_events]==list(range(event.slot,event.slot+group_size)),(f,resources.round,name,'group birth order',group_size,birth_events)
            assert event.wave_size in (0,1,2,4,5,8)
            if event.wave_size and event.slot>=0:
                assert event.slot>=0 and not pool[event.slot].pickup
                assert not pool[event.slot].body.flags&8
                assert len(birth_events)==event.wave_size,(f,name,'wave size',event.wave_size,birth_events)
                assert [e[0] for e in birth_events]==list(range(event.slot,event.slot+event.wave_size))
                assert all(r[0xe08+j]==0 for j,_,_ in birth_events),(f,name,'formation overwrote actors')
                wave_sizes[event.wave_size]=wave_sizes.get(event.wave_size,0)+1
            elif event.slot>=0 and not pool[event.slot].pickup:
                assert pool[event.slot].body.flags&8 or pool[event.slot].sprite_base_ref==0x36d0,(f,name,'unclassified enemy wave')
            completed[name]=completed.get(name,0)+1;births+=len(birth_events);score_commands+=sum(e[2] for e in birth_events)
            failures+=event.slot<0 and (event.handler>=0xabe7 or 0x87a6<=event.handler-shift<=0x87c4)
        assert completed
        return dict(module='native stage event execution',events=sum(completed.values()),audio_requests=audio_requests,handlers=completed,
            wave_sizes=wave_sizes,immediate_birth_updates=births,failed_births=failures,score_commands=score_commands,unsupported_events=unsupported,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
