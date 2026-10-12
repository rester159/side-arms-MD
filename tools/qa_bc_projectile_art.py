#!/usr/bin/env python3
"""Check artwork coverage without changing captured BC projectile state."""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import tempfile
from qa_bc_beam import ROOT,Beam,decode

class Sprite(C.Structure):
    _fields_=[('code',C.c_uint16),('x',C.c_int16),('y',C.c_int16)]+[(n,C.c_uint8) for n in ('colour','flips','visible','handled')]

def verify(captures):
    with tempfile.TemporaryDirectory() as d:
        path=Path(d)/'art.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),str(ROOT/'src/bc_projectile_art.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_projectile_sprite.argtypes=[C.POINTER(Beam),C.c_int16,C.c_int16];lib.bc_projectile_sprite.restype=Sprite
        count=0;frames=set()
        for capture in captures:
            raw=(capture/'state.bin').read_bytes();assert len(raw)%8196==0
            for off in range(0,len(raw),8196):
                ram=raw[off+4:off+8196]
                for slot in range(30):
                    b=decode(ram,slot)
                    if not b.state:continue
                    before=bytes(b);s=lib.bc_projectile_sprite(C.byref(b),32,0)
                    assert s.handled and s.visible,(str(capture),off//8196,slot,hex(b.sprite))
                    assert bytes(b)==before
                    assert s.x==C.c_int16(b.x>>8).value+24 and s.y==C.c_int16(b.y>>8).value-8
                    count+=1;frames.add(b.sprite)
        return dict(active_states=count,source_frames=[hex(f) for f in sorted(frames)],simulation_unchanged=True,rendered=False)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,action='append',required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture),indent=2))
