#!/usr/bin/env python3
"""Compare bound pose lookup with direct reads, including rebinding and fallback."""
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_player_flow import Control
from qa_bc_enemies import Data

rng=random.Random(0xbc905)
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'poses.dylib'
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{name}.c') for name in ('bc_rules','bc_world','bc_player')),'-o',str(path)],check=True)
    lib=C.CDLL(str(path))
    lib.bc_player_bind_poses.argtypes=[C.POINTER(Data),C.c_uint16]
    lib.bc_player_finish.argtypes=[C.POINTER(Control),C.POINTER(Data),C.c_uint16]
    lib.bc_player_finish.restype=C.c_uint8
    checks=0
    for board in range(24):
        # One extra byte allows the original unaligned word read at offset
        # 65535; the first-byte address alone uses unsigned-word wrapping.
        buffers=[(C.c_uint8*65537).from_buffer_copy(rng.randbytes(65537)) for _ in range(2)]
        origin=rng.randrange(65536);table=rng.choice((0,1,65535,rng.randrange(65536)))
        data=Data(buffers[0],origin)
        mode=board%6
        bound=Data(buffers[mode==2],(origin+256)&65535 if mode==3 else origin)
        bound_table=(table+2)&65535 if mode==4 else table
        for case in range(1280):
            state=Control()
            state.world.state=(128,128,0,64,255)[case%5]
            state.world.inventory.weapon=case%3 if case%2 else case%256
            state.world.weapons.charge.facing=rng.choice((0,1,255))
            state.world.invulnerability=rng.randrange(256)
            state.entry=rng.choice((0,0,0,1,16,17,255))
            state.recoil=rng.choice((0,0,1,2,10,255))
            state.attributes=rng.randrange(65536)
            state.body_frame=rng.randrange(65536);state.weapon_frame=rng.randrange(65536)
            if mode==5:
                at=(table-origin+rng.randrange(26))&65535
                buffers[0][at]=rng.randrange(256)
            direct=Control.from_buffer_copy(state);cached=Control.from_buffer_copy(state)
            lib.bc_player_bind_poses(None,0)
            expected=lib.bc_player_finish(C.byref(direct),C.byref(data),table)
            if mode!=1:lib.bc_player_bind_poses(C.byref(bound),bound_table)
            actual=lib.bc_player_finish(C.byref(cached),C.byref(data),table)
            assert actual==expected and bytes(cached)==bytes(direct),(board,case,mode)
            checks+=1
    print(f'PASS: {checks} complete pose/countdown states; cached, disabled, wrong source/origin/table, mutable-source rebinding, all weapon IDs and wrapped/odd addresses')
