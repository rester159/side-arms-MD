#!/usr/bin/env python3
"""Compare native option-body flight and hit response with original full RAM.

The source fixture initializes real option templates and schedules six hits via
input RAM pokes. It does not validate pickup acquisition or option projectile fire.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam, decode, ROOT
from qa_bc_shots import Shot


def verify(capture,input_path,code):
    raw=(capture/'state.bin').read_bytes();assert raw and len(raw)%8196==0
    records=[(struct.unpack_from('<I',raw,i)[0],raw[i+4:i+8196]) for i in range(0,len(raw),8196)]
    program=code.read_bytes();signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c')
    assert program.count(signature)==1
    shift=program.index(signature)+0x4000-0x9204
    hits={}
    for line in input_path.read_text().splitlines():
        parts=line.split()
        if len(parts)==4 and parts[1]=='poke' and int(parts[2],16) in (0x1f0a64,0x1f0a65) and int(parts[3],16)==0x40:
            hits.setdefault(int(parts[0]),[]).append(int(parts[2],16)-0x1f0a64)
    def body(r,i):
        b=decode(r,i);b.accelerating=(r[0xcdc+i]*256+r[0xcfa+i]) in (0x9ca8+shift,0x9d22+shift)
        b.facing=r[0xdae+i]==0x52
        return b
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_option_step.argtypes=[C.POINTER(Shot),C.c_uint8,C.c_uint8,C.c_uint8,C.c_uint16]
        lib.bc_shot_hit.argtypes=[C.POINTER(Shot)]
        r=records[0][1];options=[]
        for i in (28,29):
            assert r[0xa48+i]==0x80
            options.append(Shot(body(r,i),4,r[0xdea+i],0,0,r[0xc28+i]))
        updates=retired=applied_hits=0;hp=set();facings=set()
        for (_,old),(frame,r) in zip(records,records[1:]):
            for side in hits.get(frame,[]):
                lib.bc_shot_hit(C.byref(options[side]));applied_hits+=1
            for side,s in enumerate(options):
                active=bool(s.body.state);i=side+28
                lib.bc_option_step(C.byref(s),r[0xaa]==0x52,old[0xc2],old[0xc3],r[0x98]*256+r[0x99])
                expected=body(r,i)
                assert s.body.state==expected.state,(frame,i,'state',s.body.state,expected.state)
                if not active:continue
                updates+=1;retired+=not s.body.state;hp.add(s.tier);facings.add(r[0xaa]==0x52)
                for field,_ in Beam._fields_:
                    assert getattr(s.body,field)==getattr(expected,field),(frame,i,field,getattr(s.body,field),getattr(expected,field))
                assert s.tier==r[0xdea+i],(frame,i,'HP',s.tier,r[0xdea+i])
                assert s.launch_wait==r[0xc28+i]
        return dict(module='option bodies only',active_updates=updates,retirements=retired,
                    injected_hits=applied_hits,hp_values=sorted(hp),facings=len(facings),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True);p.add_argument('--input',type=Path,required=True)
    p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.input,a.code),indent=2))
