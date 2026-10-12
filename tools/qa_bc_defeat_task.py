#!/usr/bin/env python3
"""Compare boss-defeat explosion allocation, initialization and RNG."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_factory import Actor,actor
from qa_bc_enemies import Data,Enemy
from qa_bc_common import Player,Event as CommonEvent
from qa_bc_player_flow import state
from qa_bc_stage import Stage,state as stage_state
from qa_bc_score import decode as score_state
from qa_bc_actor_loop import RuntimeEvents


class Sequence(C.Structure):
    _fields_=[('center_y',C.c_uint16),('remaining',C.c_uint8),('wait',C.c_uint8)]

class Result(C.Structure):
    _fields_=[('actor_event',CommonEvent),('slot',C.c_int16),('completion',C.c_uint8)]

def verify(capture,code):
    raw=(capture/'boss-effect-task.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)-0x5204
    template=0x8f02+shift
    record=program[template-0x4000:template-0x4000+19];ref=int.from_bytes(record[11:13],'little')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_runtime','bc_stage','bc_score','bc_player','bc_palette','bc_audio')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));step=lib.bc_runtime_defeat_step
        step.argtypes=[C.POINTER(Sequence),C.POINTER(Stage),C.POINTER(Actor),C.POINTER(Player),
            C.POINTER(Data),C.c_int16,C.c_uint16,C.POINTER(C.c_uint16),C.POINTER(C.c_uint8),C.c_uint8,C.POINTER(RuntimeEvents)]
        step.restype=Result
        sequence=None;previous_frame=None
        births=failures=fractional=0;positions=set();birth_frames=[]
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,slot,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end in (1,2) and f2>=f
            birth_frames.append(f)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            pool=(Actor*32)(*(actor(before,i,program) for i in range(32)))
            base=int.from_bytes(before[ref-0x2000:ref-0x2000+2],'big')
            seed=C.c_uint16(int.from_bytes(before[0x6c:0x6e],'little'))
            if sequence is None:
                sequence=Sequence(int.from_bytes(before[0x60:0x62],'big'),50,3)
                previous_frame=f-3
            player=state(before).world;stage=stage_state(before);count=C.c_uint8(before[0x59])
            score=score_state(before);events=RuntimeEvents(C.pointer(score),before[0x51],0,None,None,None)
            for tick in range(previous_frame+1,f+1):
                result=step(C.byref(sequence),C.byref(stage),pool,C.byref(player),C.byref(data),shift,base,
                            C.byref(seed),C.byref(count),0,C.byref(events))
                if tick<f:assert result.slot==-1 and result.completion==0
            previous_frame=f
            assert result.slot==slot,(f,'allocation',result.slot,slot)
            assert bytes(score)==bytes(score_state(after)),(f,'score')
            assert bytes(player)==bytes(state(after).world),(f,'player')
            assert count.value==after[0x59],(f,'limited count')
            assert result.completion==(1 if before[0x48] else 2) if sequence.remaining==0 else result.completion==0
            result=result.slot
            assert seed.value==int.from_bytes(after[0x6c:0x6e],'little'),(f,'RNG')
            for i in range(32):
                want=actor(after,i,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[i].body,field)==getattr(want.body,field),(f,i,field)
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[i],field)==getattr(want,field),(f,i,field)
            if result<0:failures+=1
            else:
                births+=1;positions.add((pool[result].body.x>>8,pool[result].body.y>>8));fractional+=bool(pool[result].body.x&255 or pool[result].body.y&255)
        play=(capture/'play-task.bin').read_bytes();defeats=[]
        defeat_handlers={0:{0xb497},1:{0xae45},2:{0xacab},3:{0xa9ca},4:{0xae3d},
                         5:{0xb04c},6:{0xacb9},7:{0xb25d},8:{0xa6c0,0xb634,0xb1d2,0xae8e,0xc378,0xaac6,0xbb82,0xbf07,0xc726}}
        # Round-two play-task hooks are not yet generalized; actor-entry records
        # identify the same defeat tick without relying on a round-one task PC.
        actor_trace=not play
        if actor_trace:play=(capture/'actor-step.bin').read_bytes()
        for off in range(0,len(play),stride*2):
            r=play[off+6:off+stride]
            if actor_trace and play[off+4]!=0:continue
            if r[0xe08]==64 and r[0x1268]*256+r[0x1288] in defeat_handlers.get(r[0x4b],set()):
                defeats.append((struct.unpack_from('<I',play,off)[0],int.from_bytes(r[0xe88:0xe89]+r[0xea8:0xea9],'big')))
            assert not r[0x4f], 'This timing fixture expects unpaused scheduler ticks'
        assert len(defeats)==1
        lib.bc_runtime_defeat_begin.argtypes=[C.POINTER(Sequence),C.c_uint16]
        lib.bc_runtime_defeat_tick.argtypes=[C.POINTER(Sequence),C.c_uint8]
        lib.bc_runtime_defeat_tick.restype=C.c_uint8
        seq=Sequence();lib.bc_runtime_defeat_begin(C.byref(seq),defeats[0][1]);due=[];last=0
        for frame in range(defeats[0][0]+1,birth_frames[-1]+1):
            last=lib.bc_runtime_defeat_tick(C.byref(seq),0)
            if last:due.append(frame)
        assert due==birth_frames and last==2 and seq.remaining==0
        assert lib.bc_runtime_defeat_tick(C.byref(seq),0)==0
        return dict(module='native boss explosion task, per-attempt source state',births=births,failures=failures,
                    distinct_positions=len(positions),timed_explosions=len(due),fractional_slot_reuse=fractional,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
