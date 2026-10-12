#!/usr/bin/env python3
"""Compare entire native enemy loops, including children and shared player state.
Inputs are seeded once per loop; stage/player/score tasks are not simulated here.
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
from qa_bc_common import Player
from qa_bc_player_flow import state
from qa_bc_rules import Terrain
from qa_bc_actor_step import StepData,Event
from qa_bc_score import Score,decode as score_state


class Defeat(C.Structure):
    _fields_=[('center_y',C.c_uint16),('remaining',C.c_uint8),('wait',C.c_uint8)]


class RuntimeEvents(C.Structure):
    _fields_=[("score",C.POINTER(Score)),("playing",C.c_uint8),("effects_only",C.c_uint8),("next",C.c_void_p),("context",C.c_void_p),("defeat",C.c_void_p)]


def verify(capture,code,frame_from=0,frame_to=None,source_round=None):
    raw=(capture/'actor-loop.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    custom={a+shift for a in (0x9204,0x9399,0x923e,0x9413,0x953a,0x998a,0x9ca8,0x9d22)}
    def shot_body(r,j):
        b=decode(r,j);b.accelerating=r[0xcdc+j]*256+r[0xcfa+j] in custom;b.facing=r[0xdae+j]==0x52
        return b
    rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    cells=(C.c_uint8*16384).from_buffer_copy(program[0xc000:])
    sink_type=C.CFUNCTYPE(None,C.c_uint8,C.POINTER(Event),C.c_void_p)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'runtime.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{name}.c') for name in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_runtime_actor_loop.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),
            C.POINTER(StepData),C.POINTER(C.c_uint8),C.c_uint8,C.c_int16,C.c_int16,C.c_uint8,sink_type,C.c_void_p]
        lib.bc_runtime_actor_loop.restype=C.c_uint8
        lib.bc_runtime_actor_events.argtypes=[C.c_uint8,C.POINTER(Event),C.c_void_p]
        loops=updates=children=deaths=retired=later_child_updates=score_commands=final_requests=0
        skipped_other_rounds=0
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,end_slot,end=struct.unpack_from('<IBB',raw,off+stride)
            if f < frame_from or (frame_to is not None and f2 > frame_to):
                continue
            assert phase==0 and end==1 and end_slot==32 and f2>=f
            r=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            if source_round is not None and (r[0x4b]!=source_round-1 or after[0x4b]!=source_round-1):
                skipped_other_rounds+=1
                continue
            assert not r[0x49],'Global debug invulnerability is outside native rules'
            pool=(Actor*32)(*(actor(r,j,program) for j in range(32)))
            player=state(r).world;count=C.c_uint8(r[0x59])
            for j,shot in enumerate(player.weapons.shots):
                shot.body=shot_body(r,j);shot.kind=4 if j>=28 else 2 if r[0xd90+j] else 0
                shot.tier=r[0xdea+j];shot.launch_wait=r[0xc28+j]
            def base(address):return int.from_bytes(r[address-0x2000:address-0x2000+2],'big')
            bullet_ref=int.from_bytes(program[0x4aaf+shift:0x4ab1+shift],'little')
            attrs=int.from_bytes(r[0x44:0x46],'little')-0x4000
            terrain=Terrain(cells,C.cast(C.byref(rom,attrs),C.POINTER(C.c_uint8)))
            seed=C.c_uint16(int.from_bytes(r[0x6c:0x6e],'little'))
            data=StepData(Data(rom,0x4000),base(bullet_ref),base(0x367c),base(0x367e),shift,r[0x4b],
                          terrain,int.from_bytes(r[0x2e:0x30],'big'),int.from_bytes(r[0x31:0x33],'big'),
                          base(0x367a),C.pointer(seed),base(0x3684),r[0x5e],base(0x36b4 if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36c6 else 0x36ce if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36ba else 0x36cc if r[0x4b]==8 and int.from_bytes(r[0x11e8:0x11e9]+r[0x1208:0x1209],"big")in (0x36c4,0x36c0) else 0x36ce if r[0x4b]==5 else 0x36b4 if r[0x4b] in (3,6) else 0x36cc if r[0x4b] in (1,7) else 0x36c8),base(0x3682),r[0x12],base(0x3698 if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36c6 else 0x36ca if r[0x4b]==8 and r[0x11e8]*256+r[0x1208]==0x36b8 else 0x3698 if r[0x4b]==6 else 0x36ca if r[0x4b]==4 else 0x36c8))
            events=[];score=score_state(r);defeat=Defeat()
            event_context=RuntimeEvents(C.pointer(score),r[0x51],0,None,None,C.cast(C.pointer(defeat),C.c_void_p))
            @sink_type
            def sink(slot,event,context):
                lib.bc_runtime_actor_events(slot,event,C.byref(event_context))
                events.append((slot,Event.from_buffer_copy(event.contents)))
            next_slot=lib.bc_runtime_actor_loop(pool,0,C.byref(player),C.byref(data),C.byref(count),r[0x58],
                int.from_bytes(r[0x40:0x42],'big',signed=True),int.from_bytes(r[0x42:0x44],'big',signed=True),r[0x48],sink,None)
            assert next_slot==32,(f,'unsupported slot',next_slot,hex(pool[next_slot].routine))
            assert not player.shot_index,'Temporary shot index escaped its scope'
            if r[0x4b]==9:
                final_events=sum(event.boss_defeat==2 for _,event in events)
                assert final_events==int(not r[0x50] and bool(after[0x50])),(f,'final-ending event')
                if final_events:assert defeat.remaining==0, "Final ending must not start ordinary boss explosions"
                final_requests+=final_events
            slots=[slot for slot,_ in events];assert slots==sorted(set(slots))
            for j in range(32):
                want=actor(after,j,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[j].body,field)==getattr(want.body,field),(f,j,'body',field,getattr(pool[j].body,field),getattr(want.body,field))
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[j],field)==getattr(want,field),(f,j,field)
            expected=state(after).world
            for field in ('x','y','state','invulnerability'):
                assert getattr(player,field)==getattr(expected,field),(f,'player',field)
            assert bytes(player.inventory)==bytes(expected.inventory),(f,'inventory')
            for j,shot in enumerate(player.weapons.shots):
                want=shot_body(after,j)
                for field,_ in Beam._fields_:
                    assert getattr(shot.body,field)==getattr(want,field),(f,j,'shot',field)
            assert count.value==after[0x59],(f,'count')
            assert seed.value==int.from_bytes(after[0x6c:0x6e],'little'),(f,'random seed')
            assert bytes(score)==bytes(score_state(after)),(f,'score queue/state')
            assert player.weapons.returning==after[0x5a] and bytes(player.weapons.option_shots)==after[0x5b:0x5d]
            loops+=1;updates+=len(events)
            for slot,event in events:
                score_commands+=event.child_event.score_pending+event.actor_event.score_pending+sum(e.score_pending for e in event.extra_events[:event.extra_count])
                children+=(event.child_slot>=0)+event.extra_count;deaths+=event.actor_event.player_died;retired+=event.actor_event.retired
                later_child_updates+=event.child_slot>slot and event.child_slot in slots
                later_child_updates+=sum(child>slot and child in slots for child in event.extra_slots[:event.extra_count])
        assert loops, 'No complete actor loops in the requested frame/round range'
        # Unknown-handler exit must also restore the caller's cache pointer.
        pool=(Actor*32)();pool[0].body.state=128;pool[0].routine=0xffff
        player.shot_index=0x1234
        stop=lib.bc_runtime_actor_loop(pool,0,C.byref(player),C.byref(data),C.byref(count),0,0,0,0,sink,None)
        assert stop==0 and player.shot_index==0x1234
        return dict(module='complete native enemy loop',source_round=source_round,skipped_other_round_loops=skipped_other_rounds,frame_from=frame_from,frame_to=frame_to,loops=loops,actor_updates=updates,child_updates=children,
                    later_slot_child_updates=later_child_updates,player_deaths=deaths,retirements=retired,
                    score_commands=score_commands,final_ending_requests=final_requests,unsupported_loops=0,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True)
    p.add_argument('--frame-from',type=int,default=0);p.add_argument('--frame-to',type=int)
    p.add_argument('--source-round',type=int,choices=range(1,11),help='Restrict to the round matching the supplied code bank; report excluded transition records')
    a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code,a.frame_from,a.frame_to,a.source_round),indent=2))
