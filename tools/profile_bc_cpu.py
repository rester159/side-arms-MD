#!/usr/bin/env python3
"""Instruction-cycle attribution using the hash-pinned Genesis Plus GX test core.
Instrumentation modifies only this process's opcode dispatch and is restored
in finally; the ROM/core files remain unchanged. Measures guest cycles, not
host wall time. Final performance claims still require uninstrumented tests.
"""
import argparse
import bisect
import ctypes as C
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np
from run_rom import ROOT,CORE,Runner,PAD
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--players',type=int,choices=(1,2,3,4),default=4)
p.add_argument('--round',type=int,choices=range(1,11),default=10)
p.add_argument('--warmup',type=int,default=1000)
p.add_argument('--updates',type=int,default=1000)
p.add_argument('--rom',type=Path,default=ROOT/'out/release/rom.bin')
p.add_argument('--vulnerable',action='store_true',help='Keep normal player vulnerability; the fixture may terminate if all players die')
p.add_argument('--plain',action='store_true',help='Run the identical timing fixture without instruction instrumentation')
p.add_argument('--charge',action='store_true',help='Hold fire for 80 updates, then release for 20 to exercise charged launches')
p.add_argument('--hucard',action='store_true',help='Select HuCard through Home Options before the native timing fixture')
a=p.parse_args()
assert hashlib.sha256(CORE.read_bytes()).hexdigest()=='20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0','unsupported core layout'
out=ROOT/(f'.local/bc-cpu-r{a.round}-{a.players}p'+('-vulnerable' if a.vulnerable else '')+('-charged' if a.charge else '')+('-hucard' if a.hucard else ''));out.mkdir(exist_ok=True)
library=out/'hook.dylib'
if not a.plain:
    subprocess.run(['cc','-O2','-dynamiclib',str(ROOT/'tools/bc_profile_hook.c'),'-o',str(library)],check=True)
    h=C.CDLL(str(library));h.profile_begin.argtypes=[C.c_void_p]*3
symbols=sorted((int(v[0],16),v[2]) for line in (a.rom.parent/'symbol.txt').read_text().splitlines()
               if len(v:=line.split())>=3 and v[1] in ('t','T') and int(v[0],16)<0x400000)
addresses=[s[0] for s in symbols]
r=Runner(rom=a.rom);r.run(2600)
if a.hucard:
    def tap(button):r.run(5,PAD[button]);r.run(20)
    assert r.u32('flow_state')==0
    tap('DOWN');tap('A');assert r.u32('flow_state')==9
    for _ in range(3):tap('DOWN')
    tap('A');assert r.u32('flow_state')==1
    for _ in range(8):tap('DOWN')
    tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
    tap('B');assert r.u32('flow_state')==9
    assert r.read('music_source',1)==b'\1'
zram=(C.c_uint8*8192).in_dll(r.lib,'zram')
audio_underruns=[]
for key,val in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',a.round-1),
                ('dbg_bc_native_protect',int(not a.vulnerable)),('dbg_bc_native',1)]:r.write(key,val.to_bytes(2,'big'))
r.write('dbg_pad_override',b'\1')
def advance(updates):
    target=r.u32('dbg_bc_native_ticks')+updates
    for _ in range(updates*8+500):
        tick=r.u32('dbg_bc_native_ticks');period,held=(100,80) if a.charge else (40,20)
        bits=0x20 if tick%period<held else 0
        r.write('pad',bytes([bits,bits if tick%period==0 else 0]*a.players+[0,0]*(4-a.players)))
        r.run(1)
        if a.hucard and zram[0x1b0a]:audio_underruns.append((tick,int(zram[0x1b0a])))
        assert r.u16('dbg_bc_native_status') in (0,4)
        if r.u32('dbg_bc_native_ticks')>=target:return
    raise AssertionError('native update timeout')
advance(a.warmup)
base=C.cast(r.lib.m68k_get_reg,C.c_void_p).value-0x55aac
cpu=C.addressof(C.c_uint8.in_dll(r.lib,'m68k'))
start=r.frames
if not a.plain:assert h.profile_begin(cpu,base+0x1fefb0,base+0x1719c0)==0
try:advance(a.updates)
finally:
    if not a.plain:h.profile_end()
audio=dict(source='hucard' if a.hucard else 'arcade',active=bool(r.read('hucard_active',1)[0]),
           track=r.u16('dbg_hucard_track'),underrun_observations=audio_underruns)
if a.hucard:
    assert audio['active'] and zram[0x1f08]==1, audio
    assert not audio_underruns,audio
if a.plain:
    result=dict(round=a.round,players=a.players,protected=not a.vulnerable,charged_fire=a.charge,updates=a.updates,emulated_frames=r.frames-start,
        instrumentation=False,audio=audio,rom_sha256=hashlib.sha256(a.rom.read_bytes()).hexdigest())
    (out/'plain.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))
    raise SystemExit(0)
hist=np.ctypeslib.as_array((C.c_uint64*0x200000).in_dll(h,'instruction_cycles')).copy()
counts={}
for index in np.nonzero(hist)[0]:
    slot=bisect.bisect_right(addresses,int(index)*2)-1
    name=symbols[slot][1] if slot>=0 else '?'
    counts[name]=counts.get(name,0)+int(hist[index])
total=int(hist.sum());ordered=sorted(counts.items(),key=lambda x:-x[1])
result=dict(round=a.round,players=a.players,protected=not a.vulnerable,charged_fire=a.charge,updates=a.updates,emulated_frames=r.frames-start,
    total_cycles=total,audio=audio,rom_sha256=hashlib.sha256(a.rom.read_bytes()).hexdigest(),
    functions=[dict(name=n,cycles=c,percent=100*c/total) for n,c in ordered])
np.save(out/'cycles.npy',hist)
(out/'profile.json').write_text(json.dumps(result,indent=2)+'\n')
print('Native updates',a.updates,'emulated frames',result['emulated_frames'])
for n,c in ordered[:20]:print(f'{100*c/total:6.2f}% {n}')
