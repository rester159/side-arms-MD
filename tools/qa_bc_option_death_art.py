#!/usr/bin/env python3
"""Check final-option damage selects four mapped destruction poses, then retires.

This is a native branch fixture, not a naturally observed PCE death sequence.
Source-bank pixels and Genesis uploads are checked by the projectile shape QA.
"""
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_shots import Shot
from qa_bc_projectile_art import Sprite

records = {r['source_pose']: r for r in json.loads(
    (ROOT/'res/generated/bc_player_projectile_shapes.json').read_text())}
with tempfile.TemporaryDirectory() as directory:
    library = Path(directory)/'option.dylib'
    subprocess.run(['cc','-shared','-fPIC','-I'+str(ROOT/'inc'),
                    str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_projectile_art.c'),
                    '-o',str(library)],check=True)
    lib = C.CDLL(str(library))
    lib.bc_option_step.argtypes = [C.POINTER(Shot)]+[C.c_uint8]*3+[C.c_uint16]
    lib.bc_projectile_sprite.argtypes = [C.c_void_p,C.c_int16,C.c_int16]
    lib.bc_projectile_sprite.restype = Sprite
    for facing in (0,1):
        for flips in (0,0x800,0x8000,0x8800):
            shot = Shot(); shot.kind=4; shot.tier=1; shot.phase=3
            shot.body.state=128; shot.body.attributes=0x81|flips
            shot.body.flags=3; shot.body.x=128<<8; shot.body.y=112<<8
            seen=[]
            for tick in range(17):
                lib.bc_option_step(C.byref(shot),facing,128,112,112)
                if not shot.body.state:
                    assert tick==16
                    break
                sprite=lib.bc_projectile_sprite(C.byref(shot.body),32,0)
                seen.append(shot.body.sprite)
                assert sprite.handled and sprite.visible and not sprite.flips
                assert (sprite.x,sprite.y)==(152,104)
                assert sprite.code | sprite.colour<<11 == records[shot.body.sprite]['key']
            assert seen==[pose for pose in (0x1e0,0x1e2,0x1e4,0x1e6) for _ in range(4)]
print('PASS: eight final-option damage cases; four mapped poses, four ticks each, then retirement')
