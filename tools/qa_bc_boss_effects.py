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


class Sequence(C.Structure):
    _fields_=[('center_y',C.c_uint16),('remaining',C.c_uint8),('wait',C.c_uint8)]

def verify(capture,code):
    raw=(capture/'boss-effect-birth.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    template=0x8f02
    record=program[template-0x4000:template-0x4000+19];ref=int.from_bytes(record[11:13],'little')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_runtime','bc_stage','bc_score','bc_player','bc_palette','bc_audio')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));spawn=lib.bc_actor_spawn_boss_effect
        spawn.argtypes=[C.POINTER(Actor),C.c_uint16,C.POINTER(Data),C.c_int16,C.c_uint16,C.POINTER(C.c_uint16)]
        spawn.restype=C.c_int16
        births=failures=fractional=0;positions=set();birth_frames=[]
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,slot,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end in (1,2) and f2>=f
            birth_frames.append(f)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            pool=(Actor*32)(*(actor(before,i,program) for i in range(32)))
            base=int.from_bytes(before[ref-0x2000:ref-0x2000+2],'big')
            seed=C.c_uint16(int.from_bytes(before[0x6c:0x6e],'little'))
            result=spawn(pool,int.from_bytes(before[0x60:0x62],'big'),C.byref(data),0,base,C.byref(seed))
            assert result==(-1 if end==2 else slot),(f,'allocation',result,slot)
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
        for off in range(0,len(play),stride*2):
            r=play[off+6:off+stride]
            if r[0xe08]==64 and r[0x1268]*256+r[0x1288]==0xb497:
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
        return dict(module='boss-defeat explosion birth',births=births,failures=failures,
                    distinct_positions=len(positions),timed_explosions=len(due),fractional_slot_reuse=fractional,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
