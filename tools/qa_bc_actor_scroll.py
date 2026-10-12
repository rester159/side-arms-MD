#!/usr/bin/env python3
"""Compare camera-relative enemy movement before family dispatch."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_factory import Actor,actor
from qa_bc_enemies import Enemy


def verify(capture,code):
    raw=(capture/'actor-scroll.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_actor_scroll.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16,C.c_uint8]
        updates=relative=stopped=wraps=0;velocities=set()
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end==1 and i==i2 and f2>=f
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            a=actor(before,i,program);want=actor(after,i,program)
            dx=int.from_bytes(before[0x40:0x42],'big',signed=True);dy=int.from_bytes(before[0x42:0x44],'big',signed=True)
            if a.body.flags&16:
                if before[0x48]:stopped+=1
                else:
                    relative+=1;velocities.add((dx,dy))
                    wraps+=not (0<=a.body.x-dx*256<=0xffffffff and 0<=a.body.y-dy*256<=0xffffffff)
            lib.bc_actor_scroll(C.byref(a),dx,dy,before[0x48])
            for field,_ in Enemy._fields_:
                assert getattr(a.body,field)==getattr(want.body,field),(f,i,field)
            for field,_ in Actor._fields_[1:]:
                assert getattr(a,field)==getattr(want,field),(f,i,field)
            updates+=1
        assert relative
        return dict(module='camera-relative actors',updates=updates,relative_updates=relative,
                    stopped_relative_updates=stopped,wrap_updates=wraps,velocities=sorted(velocities),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
