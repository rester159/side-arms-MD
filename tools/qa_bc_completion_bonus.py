#!/usr/bin/env python3
"""Validate completion-bonus decimal columns and the captured source award."""
import ctypes as C
import hashlib
import json
import random
import struct
import subprocess
import tempfile
from pathlib import Path
from qa_bc_score import Score
from qa_bc_beam import ROOT
rng=random.Random(0xbce0)
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'bonus.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
        '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_score.c'),str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_score_completion_bonus.argtypes=[C.POINTER(Score),C.c_uint8,C.c_uint8]
    lib.bc_score_completion_bonus.restype=C.c_uint16
    code=(ROOT/'.local/pce-reference/round10-ending-presentation/code-007080.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest()=='bbd7f05a8d836aa565e75cabf93a415fa30fc1f47eade5968ed82dfa7ea8788b'
    rates=[int(''.join(map(str,code[0x2293+4*i:0x2297+4*i]))) for i in range(6)]
    cases=0
    for continues in range(6):
        for reserves in range(128):
            for upper in (0,1,999,rng.randrange(1000)):
                s=Score();s.digits[:]=list(map(int,f'{rng.randrange(10)}{upper:03d}{rng.randrange(10000):04d}'))
                s.high[:]=[rng.randrange(10) for _ in range(8)];s.queue[:]=[rng.randrange(256) for _ in range(16)]
                s.read=3;s.write=9;s.next_life=5;before=bytes(s);digits=list(s.digits)
                units=((reserves+1)*rates[continues])%1000
                assert lib.bc_score_completion_bonus(C.byref(s),reserves,continues)==units
                assert list(s.digits[1:4])==list(map(int,f'{(upper+units)%1000:03d}'))
                assert s.digits[0]==digits[0] and list(s.digits[4:])==digits[4:]
                assert bytes(s)[8:]==before[8:],'unrelated score task state changed'
                cases+=1
    for reserves,continues in ((255,5),(128,0),(0,6),(0,255)):
        s=Score();before=bytes(s)
        assert lib.bc_score_completion_bonus(C.byref(s),reserves,continues)==0 and bytes(s)==before
    raw=(ROOT/'.local/pce-reference/round10-ending-complete/state.bin').read_bytes()
    snapshots={}
    for off in range(0,len(raw),8196):
        f=struct.unpack_from('<I',raw,off)[0]
        if f in (6972,6973):snapshots[f]=raw[off+4:off+8196]
    before,after=snapshots[6972],snapshots[6973]
    s=Score();s.digits[:]=before[0xc4:0xcc]
    units=lib.bc_score_completion_bonus(C.byref(s),before[0x4d],before[0x4a])
    assert bytes(s.digits)==after[0xc4:0xcc] and units==96
    print(json.dumps(dict(decimal_cases=cases,source_bonus=units*10000,
        source_score_match=True,queue_high_rng_life_tasks_untouched=True,
        presentation_integrated=False),indent=2))
