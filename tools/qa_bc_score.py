#!/usr/bin/env python3
"""Compare native score queue/arithmetic/awards with original task snapshots."""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT


class Score(C.Structure):
    _fields_=[('digits',C.c_uint8*8),('high',C.c_uint8*8),('queue',C.c_uint8*16)]+[
        (n,C.c_uint8) for n in ('read','write','next_life')]


class Event(C.Structure):
    _fields_=[(n,C.c_uint8) for n in ('consumed','refresh_score','refresh_high','life_awarded','sound')]


def decode(r):
    s=Score();s.digits[:]=r[0xc4:0xcc];s.high[:]=r[0xd4:0xdc];s.queue[:]=r[0x82:0x92]
    s.read=r[0x92];s.write=r[0x93];s.next_life=r[0x54]
    return s


def verify(capture):
    raw=(capture/'score.bin').read_bytes();stride=8198
    assert raw and len(raw)%(stride*2)==0
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'score.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                        str(ROOT/'src/bc_rules.c'),str(ROOT/'src/bc_score.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_score_enqueue.argtypes=[C.POINTER(Score),C.c_uint8,C.c_uint8]
        lib.bc_score_step.argtypes=[C.POINTER(Score),C.POINTER(C.c_uint16),C.POINTER(C.c_uint8)]
        lib.bc_score_step.restype=Event
        enqueues=ignored=steps=consumed=awards=highs=wraps=0;commands=set();indices=set()
        for off in range(0,len(raw),stride*2):
            f,command,phase=struct.unpack_from('<IBB',raw,off);f2,_,end=struct.unpack_from('<IBB',raw,off+stride)
            assert f2>=f and (phase,end) in ((0,1),(2,3))
            before=raw[off+6:off+stride];after=raw[off+stride+6:off+stride*2]
            s=decode(before);expected=decode(after)
            if phase==2:
                lib.bc_score_enqueue(C.byref(s),command,before[0x51]);enqueues+=1;ignored+=not before[0x51]
            else:
                seed=C.c_uint16(before[0x6c]+before[0x6d]*256);lives=C.c_uint8(before[0x4d])
                event=lib.bc_score_step(C.byref(s),C.byref(seed),C.byref(lives));steps+=1
                assert seed.value==after[0x6c]+after[0x6d]*256,(f,'RNG')
                assert lives.value==after[0x4d],(f,'lives',lives.value,after[0x4d])
                assert event.consumed==(before[0x82+before[0x92]]!=255)
                assert event.refresh_score==event.consumed
                assert event.life_awarded==(before[0x54]!=after[0x54])
                assert event.refresh_high==(before[0xd4:0xdc]!=after[0xd4:0xdc])
                assert event.sound==(22 if event.life_awarded else 0)
                consumed+=event.consumed;awards+=event.life_awarded;highs+=event.refresh_high
                indices.add(before[0x54])
                if event.consumed:
                    commands.add(before[0x82+before[0x92]])
                    wraps+=after[0xc4:0xcc]<before[0xc4:0xcc]
            for field,_ in Score._fields_:
                actual,want=getattr(s,field),getattr(expected,field)
                if isinstance(actual,C.Array):actual,want=bytes(actual),bytes(want)
                assert actual==want,(f,phase,field,actual,want)
        assert steps
        return dict(module='score queue and task',enqueue_calls=enqueues,ignored_enqueue_calls=ignored,
                    task_updates=steps,consumed_commands=consumed,life_awards=awards,high_score_updates=highs,
                    score_wraps=wraps,commands=sorted(commands),threshold_indices=sorted(indices),whole_game_verified=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture),indent=2))
