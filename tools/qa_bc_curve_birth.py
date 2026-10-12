#!/usr/bin/env python3
"""Compare round-1 turning-attacker births before the immediate common update."""
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


def verify(capture,code,family='curve'):
    raw=(capture/f'{family}-birth.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    template={'curve':0xae54,'hover':0xaca6,'launcher':0xb31d,'hopper':0xb213}[family]
    record=program[template-0x4000:template-0x4000+19];ref=int.from_bytes(record[11:13],'little')
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));spawn=getattr(lib,'bc_actor_spawn_'+family);spawn.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Data),C.c_uint16,C.c_uint16]
        spawn.restype=C.c_int16
        lib.bc_actor_stage_birth.argtypes=[C.POINTER(Actor),C.c_uint16,C.POINTER(Data),C.c_uint16]
        lib.bc_actor_stage_birth.restype=C.c_int16
        events={'curve':dict(zip((56,88,120,152,184),(0xacd7,0xacdd,0xace3,0xace9,0xacef))),
                'hover':{80:0xabe7,160:0xabed},'hopper':{240:0xb0d0,32:0xb0d6},
                'launcher':dict(zip((48,96,144,192,240),(0xb23e,0xb244,0xb24a,0xb250,0xb256)))}
        births=failures=fractional=0;lanes=set()
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,slot,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end in (1,2) and f2>=f
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            pool=(Actor*32)(*(actor(before,i,program) for i in range(32)))
            base=int.from_bytes(before[ref-0x2000:ref-0x2000+2],'big')
            dispatched=(Actor*32).from_buffer_copy(pool)
            result=spawn(pool,before[0x27],C.byref(data),template,base)
            assert result==(-1 if end==2 else slot),(f,'allocation',result,slot)
            dispatched_slot=lib.bc_actor_stage_birth(dispatched,events[family][before[0x27]],C.byref(data),base)
            assert dispatched_slot==result and bytes(dispatched)==bytes(pool),(f,'stage birth dispatch')
            for i in range(32):
                want=actor(after,i,program)
                for field,_ in Enemy._fields_:
                    assert getattr(pool[i].body,field)==getattr(want.body,field),(f,i,field)
                for field,_ in Actor._fields_[1:]:
                    assert getattr(pool[i],field)==getattr(want,field),(f,i,field)
            if result<0:failures+=1
            else:
                births+=1;lanes.add(before[0x27]);fractional+=bool(pool[result].body.x&255 or pool[result].body.y&255)
        return dict(module='round-1 '+family+' birth',births=births,failures=failures,
                    lanes=sorted(lanes),fractional_slot_reuse=fractional,stage_dispatch_verified=True,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);p.add_argument('--family',choices=('curve','hover','launcher','hopper'),default='curve');a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code,a.family),indent=2))
