#!/usr/bin/env python3
"""Check supported enemy creature/projectile/effect art against captured actor states.
Other families are counted as unmapped, not claimed as rendered.
"""
import argparse
import collections
import ctypes as C
import json
from pathlib import Path
import subprocess
import tempfile
from qa_bc_factory import Actor,actor
from qa_bc_beam import ROOT

class Sprite(C.Structure):
    _fields_=[('code',C.c_uint16),('x',C.c_int16),('y',C.c_int16)]+[
        (n,C.c_uint8) for n in ('colour','flips','size','visible','handled')]

p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,action='append',required=True);a=p.parse_args()
counts=collections.Counter();frames=collections.defaultdict(set);missing=collections.Counter()
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'art.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                    str(ROOT/'src/bc_actor_art.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_actor_sprite.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16];lib.bc_actor_sprite.restype=Sprite
    for capture in a.capture:
        program=(capture/'code-002160.bin').read_bytes();raw=(capture/'actor-step.bin').read_bytes();stride=8198
        assert raw and len(raw)%(stride*2)==0
        for off in range(stride,len(raw),stride*2):
            slot=raw[off+4];b=actor(raw[off+6:off+stride],slot,program)
            if not b.body.state:continue
            before=bytes(b);s=lib.bc_actor_sprite(C.byref(b),32,0)
            assert bytes(b)==before
            ref=hex(b.sprite_base_ref)
            if b.sprite_base_ref in (0x36d0,0x36d2,0x36d4,0x3696,0x36ce,0x367c,0x367e,0x3682,0x3684,0x3686,0x3688,0x368c,0x368e,0x3692,0x3698,0x36c8,0x36cc,0x3694,0x36aa,0x369c,0x36ae,0x36b0,0x36b2,0x369a,0x36ac,0x36b4,0x368a,0x3690,0x369e,0x36a0,0x36a2,0x36a4,0x36a6,0x36a8) and not b.body.flags&8:
                assert s.handled,(str(capture),slot,ref,hex(b.body.sprite),hex(b.body.sprite_base))
            if not s.handled:missing[ref]+=1;continue
            if not s.visible:continue
            assert s.x==C.c_int16(b.body.x>>8).value-s.size//2+32
            assert s.y==C.c_int16(b.body.y>>8).value-s.size//2
            counts[ref]+=1;frames[ref].add((b.body.sprite-b.body.sprite_base,s.code,s.flips,s.size))
result=dict(mapped_states=sum(counts.values()),families=dict(counts),
            frames={k:[list(v) for v in sorted(values)] for k,values in frames.items()},
            unmapped_families=dict(missing),simulation_unchanged=True,complete_enemy_art=False)
print(json.dumps(result,indent=2))
