#!/usr/bin/env python3
"""Exact co-op ratios while retaining each source formation's linked topology."""
import ctypes as C
from pathlib import Path
import subprocess
import tempfile
from qa_bc_beam import ROOT
class Scale(C.Structure):
    _fields_=[('remainder',C.c_uint8*9)]
with tempfile.TemporaryDirectory() as directory:
    library=Path(directory)/'wave.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
        '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_wave.c'),'-o',str(library)],check=True)
    lib=C.CDLL(str(library));lib.bc_wave_copies.argtypes=[C.POINTER(Scale),C.c_uint8,C.c_uint8]
    lib.bc_wave_copies.restype=C.c_uint8
    for players in (1,2,3,4):
        scale=Scale();totals={size:0 for size in (1,2,4,5,8)}
        # Interleave different sizes: a chain's fractional copy must never be
        # spent on unrelated single enemies or on another formation family.
        for wave in range(100):
            for size in (8,1,5,2,4):
                copies=lib.bc_wave_copies(C.byref(scale),players,size)
                assert 1<=copies<=3
                totals[size]+=copies*size
                multiplier={1:4,2:4,3:6,4:9}[players]
                expected_copies=((wave+1)*multiplier)//4
                assert totals[size]==expected_copies*size
        assert all(value==size*{1:100,2:100,3:150,4:225}[players] for size,value in totals.items())
    for players in (0,1,2,3,4,5,255):
        for size in range(10):
            if players in (1,2,3,4) and size in (1,2,4,5,8):continue
            scale=Scale((C.c_uint8*9)(*range(9)));before=bytes(scale)
            assert lib.bc_wave_copies(C.byref(scale),players,size)==0 and bytes(scale)==before
    scale=Scale()
    assert [lib.bc_wave_copies(C.byref(scale),4,8) for _ in range(4)]==[2,2,2,3]
    assert not any(scale.remainder)
print('PASS: exact 1/1/1.5/2.25 ratios, intact 1/2/4/5/8-actor formations, interleaved accounting, non-wave rejection')
