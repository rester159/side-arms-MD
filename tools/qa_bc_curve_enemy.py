#!/usr/bin/env python3
"""Compare round-1 $AD31 approach/tracking/turn AI with source task snapshots.
Also checks native actor fields and child birth/common updates. Parent birth,
parent common update and death remain outside this comparison.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_enemies import Enemy,Data,decode
from qa_bc_factory import Actor,actor
from qa_bc_common import Player,Event as CommonEvent
from qa_bc_player_flow import state


class Curve(C.Structure):
    _fields_=[('body',Enemy)]+[(n,C.c_uint8) for n in ('direction','speed','wait','phase','turn','escaping','fired')]


class Fire(C.Structure):
    _fields_=[('fire',C.c_uint8),('direction',C.c_uint8)]


class ActorEvent(C.Structure):
    _fields_=[('child_event',CommonEvent),('child_slot',C.c_int16),('fire_requested',C.c_uint8)]


def verify(capture,code):
    raw=(capture/'ai.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program)
    data=Data(rom,0x4000)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_enemy_curve_prepare.argtypes=[C.POINTER(Curve),C.c_uint16,C.c_uint16,C.POINTER(Data)]+[C.c_uint16]*3
        lib.bc_enemy_curve_escape.argtypes=[C.POINTER(Curve),C.c_uint16,C.c_uint16,C.c_uint8,C.c_uint8]
        lib.bc_enemy_curve_escape.restype=Fire
        lib.bc_actor_curve_prepare.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Player),C.POINTER(Data),C.POINTER(C.c_uint8),C.c_uint8,C.c_uint16]
        lib.bc_actor_curve_prepare.restype=ActorEvent
        actor_updates=child_updates=0
        updates=transitions=escapes=0;phases=set();directions=set();turns=set()
        escape_updates=shots=failed_allocations=0
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            routine=before[0x1228+i]*256+before[0x1248+i]
            if before[0xe08+i]!=0x80 or routine not in (0xad31,0xae2b):continue
            assert i==i2 and phase==0 and end==1 and f2>=f
            assert before[0x4b]==0,'This verifier describes round 1 only'
            b=Curve(decode(before,i,program),*(before[a+i] for a in (0x11a8,0x11c8,0x1308,0x1328,0x1348)),routine==0xae2b,before[0x1368+i])
            px=before[0x95]*256+before[0x96];py=before[0x98]*256+before[0x99]
            pool=(Actor*32)(*(actor(before,j,program) for j in range(32)))
            player=state(before).world;count=C.c_uint8(before[0x59])
            ref=int.from_bytes(program[0x4aaf:0x4ab1],'little')
            base=int.from_bytes(before[ref-0x2000:ref-0x2000+2],'big')
            combined=lib.bc_actor_curve_prepare(pool,i,C.byref(player),C.byref(data),C.byref(count),before[0x58],base)
            for j in range(32):
                want=actor(after,j,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[j].body,field)==getattr(want.body,field),(f,j,'actor body',field)
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[j],field)==getattr(want,field),(f,j,'actor',field)
            assert count.value==after[0x59],(f,'limited count')
            expected_player=state(after).world
            for field in ('x','y','state','invulnerability'):
                assert getattr(player,field)==getattr(expected_player,field),(f,'player',field)
            assert bytes(player.inventory)==bytes(expected_player.inventory),(f,'inventory')
            assert bytes(player.weapons)==bytes(expected_player.weapons),(f,'weapons')
            actor_updates+=1;child_updates+=combined.child_slot>=0
            if routine==0xad31:
                phases.add(b.phase)
                lib.bc_enemy_curve_prepare(C.byref(b),px,py,C.byref(data),0x8479,0xae6c,0xae77)
                updates+=1;escapes+=b.escaping;transitions+=b.phase!=before[0x1328+i]
            else:
                event=lib.bc_enemy_curve_escape(C.byref(b),px,py,before[0x59],before[0x58]);escape_updates+=1
                if event.fire:
                    free=next((j for j in range(32) if not before[0xe08+j]),None)
                    if free is None:failed_allocations+=1
                    else:
                        assert after[0x11a8+free]==event.direction,(f,i,'fired direction')
                        assert after[0x59]==(before[0x59]+1)&255,(f,i,'shot count')
                    shots+=1
            expected=decode(after,i,program)
            for field,_ in Enemy._fields_:
                assert getattr(b.body,field)==getattr(expected,field),(f,i,field,getattr(b.body,field),getattr(expected,field))
            for field,address in [('direction',0x11a8),('speed',0x11c8),('wait',0x1308),('phase',0x1328),('turn',0x1348),('fired',0x1368)]:
                assert getattr(b,field)==after[address+i],(f,i,field,getattr(b,field),after[address+i])
            assert after[0x1228+i]*256+after[0x1248+i]==(0xae2b if b.escaping else 0xad31)
            directions.add(b.direction)
            if b.phase==3:turns.add(b.turn)
        assert updates and phases=={0,1,2,3}
        return dict(module='round-1 turning attacker AI and native actor/child integration',actor_updates=actor_updates,child_updates=child_updates,updates=updates,escape_updates=escape_updates,
                    fire_requests=shots,failed_allocations=failed_allocations,
                    phase_transitions=transitions,escape_transitions=escapes,phases=sorted(phases),
                    directions=sorted(directions),turn_markers=sorted(turns),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
