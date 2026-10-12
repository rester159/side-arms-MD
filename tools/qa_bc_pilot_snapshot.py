#!/usr/bin/env python3
"""Check controller-search snapshot determinism on the pinned Genesis test core.

This is a test-harness gate, not natural-campaign or gameplay-speed evidence.
"""
import hashlib, json
from pathlib import Path
from run_rom import Runner, ROOT, CORE
from bc_pilot_lookahead import PilotSnapshot

assert hashlib.sha256(CORE.read_bytes()).hexdigest() == '20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
out = ROOT/'.local/bc-pilot-snapshot'; out.mkdir(exist_ok=True)
r = Runner(); r.run(2600)
for name, value in [('dbg_bc_native_players',4),('dbg_bc_native_start_round',7),('dbg_bc_native_protect',0),('dbg_bc_native',1)]:
    r.write(name, value.to_bytes(2,'big'))
r.write('dbg_pad_override', b'\1')
r.run(500)
assert r.u16('dbg_bc_native_status') in (0,4)
def fingerprint():
    return dict(ram=hashlib.sha256(bytes(r.ram)).hexdigest(),
                vram=hashlib.sha256(bytes(r.vram)).hexdigest(),
                pixels=hashlib.sha256(r.frame.tobytes()).hexdigest(),
                frame=r.frames,tick=r.u32('dbg_bc_native_ticks'))
def advance(direction):
    previous = 0
    for n in range(120):
        bits = direction | (0x20 if n % 6 < 3 else 0)
        r.write('pad',bytes([bits,bits&~previous])*4)
        r.run(1); previous=bits
    return fingerprint()
snapshot=PilotSnapshot(r); initial=fingerprint()
reference=advance(0)
snapshot.restore(); assert fingerprint()==initial
branches=[]
for direction in range(11):
    if direction in (3,7):continue
    first=advance(direction)
    snapshot.restore(); assert fingerprint()==initial
    second=advance(direction)
    assert first==second, (direction,'branch replay mismatch')
    snapshot.restore(); assert fingerprint()==initial
    assert advance(0)==reference, (direction,'branch contaminated baseline replay')
    snapshot.restore(); assert fingerprint()==initial
    branches.append(direction)
result=dict(rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),
    snapshot_bytes=snapshot.size,branches=branches,video_frames_per_branch=120,
    exact_checks=['work RAM','VRAM','rendered pixels','Runner frame','simulation tick'],
    reference=reference,full_campaign_verified=False,full_speed_verified=False)
(out/'verified.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
