#!/usr/bin/env python3
"""Compare shared enemy explosion setup before the common animation update."""
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
    raw=(capture/'ai.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c')
    assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'world.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_world.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_actor_explosion.argtypes=[C.POINTER(Actor),C.c_uint8,C.c_uint16,C.c_uint16]
        lib.bc_actor_explosion.restype=C.c_uint8
        lib.bc_actor_scroll.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16,C.c_uint8]
        counts={};relative=0
        for off in range(0,len(raw),stride*2):
            f,i,phase=struct.unpack_from('<IBB',raw,off);f2,i2,end=struct.unpack_from('<IBB',raw,off+stride)
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            handler=before[0x1268+i]*256+before[0x1288+i]-shift
            if before[0xe08+i]==128 or handler not in (0x8e95,0x8eb5,0x8ec1):continue
            assert phase==0 and end==1 and i==i2 and f2>=f
            kind=(0x8e95,0x8eb5,0x8ec1).index(handler)
            a=actor(before,i,program);want=actor(after,i,program)
            relative+=bool(a.body.flags&16 and not before[0x48])
            lib.bc_actor_scroll(C.byref(a),int.from_bytes(before[0x40:0x42],'big',signed=True),
                                int.from_bytes(before[0x42:0x44],'big',signed=True),before[0x48])
            ref=0x367e if kind else 0x367c
            base=int.from_bytes(before[ref-0x2000:ref-0x2000+2],'big')
            assert lib.bc_actor_explosion(C.byref(a),kind,base,(0x8f1e if kind else 0x8f15)+shift)==4
            for field,_ in Enemy._fields_:
                assert getattr(a.body,field)==getattr(want.body,field),(f,i,field)
            for field,_ in Actor._fields_[1:]:
                assert getattr(a,field)==getattr(want,field),(f,i,field)
            counts[hex(handler)]=counts.get(hex(handler),0)+1
        assert counts,'No applicable explosion setup captured'
        return dict(module='shared enemy explosion setup',calls=sum(counts.values()),handlers=counts,
                    world_relative_calls=relative,sound_command_reference_verified=False,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
