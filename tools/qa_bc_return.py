#!/usr/bin/env python3
"""Compare the native returning weapon with the original full work-RAM trace."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam, decode, ROOT
from qa_bc_shots import Shot


Returning = Shot


def verify(capture):
    raw = (capture/'state.bin').read_bytes()
    assert raw and len(raw) % 8196 == 0
    records = [(struct.unpack_from('<I',raw,i)[0],raw[i+4:i+8196]) for i in range(0,len(raw),8196)]
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'rules.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                        '-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path))
        lib.bc_return_fire.argtypes=[C.POINTER(Returning),C.c_uint8,C.c_uint8,C.c_uint16,C.c_uint16,C.POINTER(C.c_uint8)]
        lib.bc_return_fire.restype=C.c_uint8
        lib.bc_return_step.argtypes=[C.POINTER(Returning),C.c_uint16,C.c_uint16,C.POINTER(C.c_uint8)]
        slots=(Returning*28)()
        for i in range(28): slots[i].body=decode(records[0][1],i)
        active=C.c_uint8(records[0][1][0x5a])
        launches=0; denied=0; updates=0; caught=0; peaks={}; angles=set(); cases=set()
        for (old_frame,old),(frame,ram) in zip(records,records[1:]):
            assert frame==old_frame+1
            px=ram[0x95]*256+ram[0x96];py=ram[0x98]*256+ram[0x99]
            if ram[0x94]==0x80 and not ram[0xad] and ram[0x228]&3 in (1,2) and ram[0x22d]&3:
                assert ram[0xa5]==2
                right=ram[0xaa]==0x52;power=ram[0xae];cases.add((power,right))
                n=lib.bc_return_fire(slots,power,right,px,py,C.byref(active))
                launches+=n;denied+=not n
                peaks[power]=max(peaks.get(power,0),active.value)
            for i,shot in enumerate(slots):
                was_active=bool(shot.body.state)
                lib.bc_return_step(C.byref(shot),px,py,C.byref(active))
                expected=decode(ram,i)
                expected.facing=ram[0xdae+i]==0x52
                expected.accelerating=1
                assert shot.body.state==expected.state,(frame,i,'state',shot.body.state,expected.state)
                if was_active:
                    updates+=1;caught+=not shot.body.state
                    for field,_ in Beam._fields_:
                        actual,want=getattr(shot.body,field),getattr(expected,field)
                        assert actual==want,(frame,i,field,actual,want)
                    assert shot.launch_wait==ram[0xc28+i],(frame,i,'launch wait')
                    if not shot.launch_wait:angles.add(shot.body.delay)
            assert active.value==ram[0x5a],(frame,'active counter',active.value,ram[0x5a])
        assert cases=={(p,d) for p in (1,3,7,15) for d in (False,True)}
        assert launches==caught and not active.value
        assert denied>0 and peaks[1]==2
        return dict(module='returning weapon launch, homing, animation and catch',launches=launches,
                    blocked_launches=denied,active_slot_updates=updates,catches=caught,
                    peak_active_by_power=peaks,observed_directions=sorted(angles),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True)
    a=p.parse_args();print(json.dumps(verify(a.capture),indent=2))
