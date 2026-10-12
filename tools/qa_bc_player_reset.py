#!/usr/bin/env python3
"""Compare the native player reset with original stage initialization.
Enemy, camera and stage reconstruction are outside this player-only comparison.
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
from qa_bc_player_flow import Control,state


def verify(capture,code):
    raw=(capture/'player-reset.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'reset.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_player')),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_player_reset.argtypes=[C.POINTER(Control),C.c_uint8,C.POINTER(Data),C.c_uint16]
        rounds=set();count=0
        for off in range(0,len(raw),stride*2):
            f,_,phase=struct.unpack_from('<IBB',raw,off);f2,_,end=struct.unpack_from('<IBB',raw,off+stride)
            assert phase==0 and end==1 and f2>=f
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            p=state(before);expected=state(after)
            lib.bc_player_reset(C.byref(p),before[0x4b],C.byref(data),0x9ba7+shift)
            for field,_ in Control._fields_[1:]:
                assert getattr(p,field)==getattr(expected,field),(f,field,getattr(p,field),getattr(expected,field))
            for field in ('x','y','state','invulnerability'):
                assert getattr(p.world,field)==getattr(expected.world,field),(f,field)
            assert bytes(p.world.inventory)==bytes(expected.world.inventory),(f,'inventory')
            assert bytes(p.world.weapons)==bytes(expected.world.weapons),(f,'weapons')
            rounds.add(before[0x4b]);count+=1
        return dict(module='player stage reset',resets=count,rounds=sorted(rounds),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
