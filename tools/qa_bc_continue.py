#!/usr/bin/env python3
"""Compare continue countdown/score reset with original source captures."""
import ctypes as C
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from qa_bc_score import Score, decode, ROOT

class Prompt(C.Structure):
    _fields_=[(name,C.c_uint8) for name in ('digit','remaining','state')]

def frames(name):
    raw=(ROOT/'.local/pce-reference'/name/'state.bin').read_bytes()
    assert len(raw)%8196==0
    return {struct.unpack_from('<I',raw,o)[0]:raw[o+4:o+8196] for o in range(0,len(raw),8196)}

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'continue.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{name}.c') for name in ('bc_continue','bc_score','bc_rules')),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_continue_begin.argtypes=[C.POINTER(Prompt),C.c_uint8]
    lib.bc_continue_tick.argtypes=[C.POINTER(Prompt),C.c_uint8];lib.bc_continue_tick.restype=C.c_uint8
    lib.bc_score_continue.argtypes=[C.POINTER(Score)]
    checked=0
    for capture,accepted in (('continue-accept',True),('continue-timeout',False)):
        source=frames(capture)
        first=next(f for f,r in source.items() if f>2500 and r[0x29]==9 and r[0x28]==90)
        p=Prompt();lib.bc_continue_begin(C.byref(p),1)
        last=3000 if accepted else first+900
        for f in range(first+1,last+1):
            result=lib.bc_continue_tick(C.byref(p),int(accepted and f==3000))
            # Timeout jumps to title initialization, which has already cleared
            # the countdown and remaining-credit RAM in this frame snapshot.
            if result==3:
                assert source[f-1][0x28:0x2a]==b'\1\0'
                assert source[f][0x28:0x2a]==b'\0\0' and source[f][0x4a]==0
            else:assert (p.digit,p.remaining)==(source[f][0x29],source[f][0x28]),(capture,f,bytes(p).hex())
            checked+=1
        assert result==(2 if accepted else 3)
        before=bytes(p)
        for _ in range(60):lib.bc_continue_tick(C.byref(p),1)
        assert bytes(p)==before
        if accepted:
            assert source[2999][0x4a]==5 and source[3000][0x4a]==4
            score=decode(source[3029]);lib.bc_score_continue(C.byref(score))
            assert bytes(score)==bytes(decode(source[3030]))
            assert source[3030][0x4d]==2 and source[3051][0x94]==128
    p=Prompt();lib.bc_continue_begin(C.byref(p),0)
    assert lib.bc_continue_tick(C.byref(p),1)==3
    lib.bc_continue_begin(C.byref(p),1)
    for _ in range(899):assert lib.bc_continue_tick(C.byref(p),0)==1
    assert p.digit==0 and p.remaining==1
    assert lib.bc_continue_tick(C.byref(p),1)==2
    print(json.dumps(dict(source_countdown_updates=checked,timeout_updates=900,
        score_reset_matches=True,last_update_start_wins=True,terminal_stable=True,
        public_continue_integrated=False),indent=2))
