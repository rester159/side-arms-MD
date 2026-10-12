#!/usr/bin/env python3
"""Compare the native RNG transition with original routine inputs and outputs."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT


def verify(capture):
    raw=(capture/'random.bin').read_bytes();assert raw and len(raw)%8==0
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_random_next.argtypes=[C.c_uint16];lib.bc_random_next.restype=C.c_uint16
        seeds=set()
        for frame,before,after in struct.iter_unpack('<IHH',raw):
            result=lib.bc_random_next(before)
            assert result==after,(frame,before,result,after)
            seeds.add(before)
        return dict(module='RNG transition',updates=len(raw)//8,distinct_inputs=len(seeds),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture),indent=2))
