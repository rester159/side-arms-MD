#!/usr/bin/env python3
"""Verify autonomous BC stage-to-boss HuCard music after a real Home launch."""
import argparse
import ctypes as C
import hashlib
import json
import os
import numpy as np
from pathlib import Path
from run_rom import ROOT, Runner, PAD

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--players',type=int,choices=(1,2,3,4),default=4)
p.add_argument('--output',type=Path,help='Separate evidence directory for this cartridge')
a=p.parse_args()
build=Path(os.environ.get("SIDEARMS_BUILD",ROOT))
r=Runner();r.run(2600)
def tap(key):
    r.run(5,PAD[key]);r.run(20)
assert r.u32('flow_state')==0
tap('DOWN');tap('A');assert r.u32('flow_state')==9
for _ in range(3):tap('DOWN')
tap('A');assert r.u32('flow_state')==1
for _ in range(8):tap('DOWN')
tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
tap('B')
for _ in range(2):tap('UP')
tap('A')
for _ in range((a.players-2)%4):tap('DOWN')
tap('A')
assert r.u32('flow_state')==14 and r.u16('player_limit')==a.players
# Keep the party alive so elapsed stage time reaches the boss naturally.
# No requests, acknowledgements, boss events or music commands are injected.
r.write('dbg_bc_native_protect',b'\0\1')
zram=(C.c_uint8*8192).in_dll(r.lib,'zram')
chunks=[]
def audio(data,count):
    chunks.append(np.ctypeslib.as_array(data,(count*2,)).copy())
    return count
callback=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)(audio)
r.callbacks.append(callback);r.lib.retro_set_audio_sample_batch(callback)
seen=0;remaining=0;rows=[];wait=max_wait=0
for frame in range(15000):
    r.run(1)
    status=r.u16('dbg_bc_native_status')
    assert status in (0,4),('scene stopped',frame,status)
    assert not r.u16('dbg_bc_native_audio_ack') and not r.u16('dbg_bc_native_audio_manual')
    assert not zram[0x1b0a],('queue underrun',frame)
    wait=wait+1 if status==4 else 0;max_wait=max(wait,max_wait)
    count=r.u16('dbg_bc_native_music_requests')
    if count!=seen:
        assert count==seen+1
        seen=count;remaining=300;chunks.clear()
        expected=(0x21,0x05) if seen==1 else (0x32,0x12)
        assert r.u16('dbg_bc_native_music_command')==expected[0]
        assert r.u16('dbg_hucard_track')==expected[1]
        assert r.read('hucard_active',1)==b'\1'
    elif remaining:
        remaining-=1
        if not remaining:
            samples=np.concatenate(chunks).astype(float)
            rms=float(np.sqrt(np.mean(samples**2)))
            assert rms>5,('silent music',seen,rms)
            rows.append(dict(request=seen,frame=frame,command=expected[0],track=expected[1],rms=rms))
            if seen==2:break
    else:chunks.clear()
assert len(rows)==2 and max_wait<10
out=a.output or ROOT/f'.local/pce-hucard/bc-transition-{a.players}p';out.mkdir(parents=True,exist_ok=True)
r.capture(out/'boss.png')
report=dict(passed=True,players=a.players,requests=rows,max_wait_frames=max_wait,
            underruns=0,protected_players=True,injected_music_requests=False,
            rom_sha256=hashlib.sha256((build/'out/release/rom.bin').read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
