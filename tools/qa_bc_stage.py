#!/usr/bin/env python3
"""Verify native checkpoint camera state and fixed-point scroll against source RAM.
Stage event handlers and tile uploads are outside this comparison.
Use captures from relocation-aware stage hooks for rounds after round 1.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_enemies import Data


class Stage(C.Structure):
    _fields_=[('x',C.c_uint32),('y',C.c_uint32),('dx',C.c_int16),('dy',C.c_int16),
              ('script',C.c_uint16),('terrain_attributes',C.c_uint16),('checkpoint_script',C.c_uint16),
              ('checkpoint_x',C.c_uint8),('checkpoint_y',C.c_uint8),('shot_limit',C.c_uint8),('stopped',C.c_uint8),('boss_active',C.c_uint8)]


def state(r):
    return Stage(int.from_bytes(r[0x2e:0x31],'big'),int.from_bytes(r[0x31:0x34],'big'),
                 int.from_bytes(r[0x40:0x42],'big',signed=True),int.from_bytes(r[0x42:0x44],'big',signed=True),
                 int.from_bytes(r[0x46:0x48],'little'),int.from_bytes(r[0x44:0x46],'little'),
                 int.from_bytes(r[0x69:0x6b],'little'),r[0x67],r[0x68],r[0x58],r[0x48],r[0x5e])


def verify(capture,code):
    raw=(capture/'stage-state.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();header=(C.c_uint8*8).from_buffer_copy(program[0x6218:0x6220])
    rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'stage.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_stage.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));functions=[lib.bc_stage_checkpoint_initial,lib.bc_stage_checkpoint_restore,lib.bc_stage_scroll]
        for fn in functions[:2]:fn.argtypes=[C.POINTER(Stage),C.POINTER(C.c_uint8)]
        functions[2].argtypes=[C.POINTER(Stage)]
        lib.bc_stage_event_next.argtypes=[C.POINTER(Stage),C.POINTER(Data)];lib.bc_stage_event_next.restype=C.c_uint16
        counts=[0,0,0,0];velocities=set();wraps=0;handlers=set();events=0
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,_,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase in (0,2,4,6) and (end==phase+1 or (phase==6 and end==9)) and f2>=f
            before=state(raw[off+6:off+stride]);after=state(raw[off+stride+6:off+stride*2]);index=phase//2
            p=Stage.from_buffer_copy(before)
            if index==3:
                handler=lib.bc_stage_event_next(C.byref(p),C.byref(data))
                assert bool(handler)==(end==7),(f,'event dispatch',handler,end)
                if handler:
                    address=before.script-0x4000
                    assert handler==int.from_bytes(program[address+1:address+3],'little')
                    handlers.add(handler);events+=1
            elif index==2:
                functions[index](C.byref(p));velocities.add((before.dx,before.dy))
                wraps+=any(not 0<=v<=0xfffff for v in (before.x+before.dx,before.y+before.dy))
            else:functions[index](C.byref(p),header)
            for field,_ in Stage._fields_:
                assert getattr(p,field)==getattr(after,field),(f,phase,field,getattr(p,field),getattr(after,field))
            counts[index]+=1
        return dict(module='checkpoint camera and scroll',initializations=counts[0],restores=counts[1],
                    scroll_updates=counts[2],event_checks=counts[3],dispatched_events=events,
                    handlers=[hex(h) for h in sorted(handlers)],velocities=sorted(velocities),wrap_updates=wraps,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
