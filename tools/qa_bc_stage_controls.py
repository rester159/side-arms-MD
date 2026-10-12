#!/usr/bin/env python3
"""Compare native common stage handlers against captured source entry/exit RAM."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_stage import Stage,state


def verify(capture):
    raw=(capture/'stage-controls.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'stage.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_stage.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_stage_control.argtypes=[C.POINTER(Stage),C.c_uint16]
        lib.bc_stage_control.restype=C.c_uint8
        counts={}
        for off in range(0,len(raw),stride*2):
            f,handler=struct.unpack_from('<IH',raw,off);f2,_=struct.unpack_from('<IH',raw,off+stride)
            assert f2>=f
            p=state(raw[off+6:off+stride]);expected=state(raw[off+stride+6:off+stride*2])
            assert lib.bc_stage_control(C.byref(p),handler),(f,hex(handler),'unhandled')
            for field,_ in Stage._fields_:
                assert getattr(p,field)==getattr(expected,field),(f,hex(handler),field,getattr(p,field),getattr(expected,field))
            counts[hex(handler)]=counts.get(hex(handler),0)+1
        return dict(module='common stage controls',calls=sum(counts.values()),handlers=counts,whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture),indent=2))
