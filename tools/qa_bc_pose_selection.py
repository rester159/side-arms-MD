#!/usr/bin/env python3
"""Compare pose-only selection and positioned API with an archived art mapper."""
import argparse
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile
from qa_bc_factory import Actor
from qa_bc_beam import ROOT

class Sprite(C.Structure):
    _fields_ = [('code', C.c_uint16), ('x', C.c_int16), ('y', C.c_int16)] + [
        (n, C.c_uint8) for n in ('colour', 'flips', 'size', 'visible', 'handled')]

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
a = p.parse_args()
with tempfile.TemporaryDirectory() as directory:
    libs = []
    for i, source in enumerate((a.baseline, ROOT/'src/bc_actor_art.c')):
        output = Path(directory)/f'art{i}.dylib'
        subprocess.run(['cc', '-std=c99', '-O2', '-Wall', '-Wextra', '-Werror',
            '-shared', '-fPIC', '-I'+str(ROOT/'inc'), str(source), '-o', str(output)], check=True)
        lib = C.CDLL(str(output))
        lib.bc_actor_sprite.argtypes = [C.POINTER(Actor), C.c_int16, C.c_int16]
        lib.bc_actor_sprite.restype = Sprite
        libs.append(lib)
    libs[1].bc_actor_pose.argtypes = [C.POINTER(Actor)]
    libs[1].bc_actor_pose.restype = C.c_uint32
    rng = random.Random(0xbc504f53)
    checks = visible = 0
    for ref in list(range(0x3670, 0x36e0)) + [0, 65535]:
        for frame in range(66):
            for variant in range(8):
                actor = Actor(); b = actor.body
                b.state = (0, 0x40, 0x80, 0xc0)[variant & 3]
                b.flags = 8 if variant == 7 else 0
                b.sprite_base = rng.randrange(65536)
                b.sprite = (b.sprite_base + frame) & 65535
                b.attributes = rng.randrange(65536)
                b.x = rng.randrange(1 << 32); b.y = rng.randrange(1 << 32)
                actor.sprite_base_ref = ref
                before = bytes(actor)
                x, y = rng.randrange(-32768,32768), rng.randrange(-32768,32768)
                old = libs[0].bc_actor_sprite(C.byref(actor),x,y)
                new = libs[1].bc_actor_sprite(C.byref(actor),x,y)
                packed = libs[1].bc_actor_pose(C.byref(actor))
                pose = Sprite(packed & 0x7ff, 0, 0, (packed >> 11) & 15,
                    (packed >> 16) & 3, 32 if packed & 0x40000 else 16,
                    bool(packed & 0x80000), bool(packed & 0x100000))
                for name,_ in Sprite._fields_:
                    assert getattr(old,name) == getattr(new,name), (ref,frame,variant,name)
                    if name not in ('x','y'):
                        assert getattr(pose,name) == getattr(old,name), (ref,frame,variant,name)
                assert pose.x == pose.y == 0 and bytes(actor) == before
                checks += 1; visible += bool(old.visible)
    print(f'PASS: {checks} positioned/pose comparisons; {visible} visible; wrapping, flags, unknown families and read-only simulation')
