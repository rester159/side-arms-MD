#!/usr/bin/env python3
"""Production wave replay using original round code, pool pressure and FIFO."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_party_frame import WaveQueue
from qa_bc_stage_runtime import Resources,Event
from qa_bc_stage import Stage
from qa_bc_factory import Actor
from qa_bc_common import Player
from qa_bc_enemies import Data
from qa_bc_beam import ROOT
with tempfile.TemporaryDirectory() as directory:
    library=Path(directory)/'queue.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_score','bc_player','bc_palette','bc_audio','bc_wave','bc_wave_queue')),
        '-o',str(library)],check=True)
    lib=C.CDLL(str(library))
    args=[C.POINTER(Stage),C.POINTER(Actor),C.POINTER(Player),C.POINTER(Resources),C.POINTER(C.c_uint8)]
    lib.bc_runtime_stage_event.argtypes=args;lib.bc_runtime_stage_event.restype=Event
    lib.bc_wave_service.argtypes=[C.POINTER(WaveQueue)]+args
    lib.bc_wave_enqueue.argtypes=[C.POINTER(WaveQueue),C.c_uint8,C.c_uint16,C.c_uint8]
    lib.bc_wave_enqueue.restype=C.c_uint8
    lib.bc_wave_barrier.argtypes=[C.c_uint8,C.c_uint16,C.c_int16]
    lib.bc_wave_barrier.restype=C.c_uint8
    cases=[(0,'play-task-round1',0xaa34,1),(2,'round3-middle',0xb881,2),
           (1,'round2-ending',0xbd3c,4),(7,'round8-formation',0xb967,5),
           (7,'round8-formation',0xbe25,8)]
    for round,capture,handler,size in cases:
        program=(ROOT/f'.local/pce-reference/{capture}/code-002160.bin').read_bytes()
        rom=(C.c_uint8*65536)();rom[0x4000:]=program[:0xc000]
        rom[0x1000:0x1003]=[128,handler&255,handler>>8]
        sd=Resources();sd.data=Data(rom,0);sd.round=round
        signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c')
        sd.relocation=program.index(signature)+0x4000-0x9204
        seed=C.c_uint16(1);sd.random_state=C.pointer(seed)
        stage=Stage();stage.x=128<<8;stage.script=0x1000;stage.shot_limit=16
        pool=(Actor*32)();player=Player();count=C.c_uint8()
        def service(q):lib.bc_wave_service(C.byref(q),C.byref(stage),pool,C.byref(player),C.byref(sd),C.byref(count))
        def clear():
            for actor in pool:actor.body.state=0
        for n in (1,2,3,4):
            q=WaveQueue()
            for _ in range(4):
                clear();stage.script=0x1000
                event=lib.bc_runtime_stage_event(C.byref(stage),pool,C.byref(player),C.byref(sd),C.byref(count))
                assert (event.status,event.wave_size)==(1,size) and event.slot>=0,(round,hex(handler),size,event.wave_size,event.slot)
                assert lib.bc_wave_enqueue(C.byref(q),n,0x1000,size)
                for _ in range(40):
                    clear();before=bytes(stage);service(q)
                    assert bytes(stage)==before,'replay modified live stage state'
                    if not q.count:break
                assert q.count==0
            assert q.originals==size*4 and q.extras==size*{1:0,2:0,3:2,4:5}[n]
        if size==1:
            # Distinct lanes prove FIFO order, including a two-copy record.
            rom[0x1003:0x1006]=[128,0x3a,0xaa]
            q=WaveQueue();q.scale.remainder[1]=3
            lib.bc_wave_enqueue(C.byref(q),4,0x1000,1)
            lib.bc_wave_enqueue(C.byref(q),4,0x1003,1)
            lanes=[]
            for _ in range(40):
                clear();before=q.extras;service(q)
                if q.extras!=before:lanes.append(pool[0].body.y>>8)
            assert lanes==[56,56,88],lanes
        # Full/fragmented pools retain the same pending copy; no RNG consumption.
        q=WaveQueue();lib.bc_wave_enqueue(C.byref(q),4,0x1000,size)
        for actor in pool:actor.body.state=0x80
        before=seed.value
        for _ in range(20):service(q)
        assert q.count==1 and q.extras==0 and q.blocked and seed.value==before
        assert (q.pending[q.head].script,q.pending[q.head].size,q.pending[q.head].copies)==(0x1000,size,1)
        if size>1:
            for i,actor in enumerate(pool):actor.body.state=0 if i%2==0 else 0x80
            service(q);assert q.count==1 and not q.extras
        clear();service(q);assert q.count==0 and q.extras==size
        # Wrap a full queue, reject overflow without changing fractional credit.
        q=WaveQueue()
        for _ in range(8):assert lib.bc_wave_enqueue(C.byref(q),4,0x1000,size)
        before=bytes(q);assert not lib.bc_wave_enqueue(C.byref(q),4,0x1000,size) and bytes(q)==before
        for _ in range(100):clear();service(q)
        assert q.count==0 and q.extras==size*10
    bosses=[(0,0xb34b),(1,0xab95),(2,0xaacb),(3,0xa76e),(4,0xac50),
            (5,0xae4c),(6,0xaa0b),(7,0xb046),(9,0xa399)]
    bosses += [(8,h) for h in (0xa574,0xb384,0xaff2,0xac32,0xc18b,0xa8c6,0xb8d4,0xbcf0,0xc539)]
    assert all(lib.bc_wave_barrier(r,h,0) for r,h in bosses)
    for shift in (-1333,0,2000):
        assert lib.bc_wave_barrier(0,(0x8d76+shift)&65535,shift)
        assert lib.bc_wave_barrier(0,(0x8c17+shift)&65535,shift)
    assert all(not lib.bc_wave_barrier(r,h,0) for r,_,h,_ in cases)
print('PASS: original-code 1/2/4/5/8 formations, exact co-op totals, full/fragmented pools, retries, queue wrap/overflow, stage isolation, boss barriers')
