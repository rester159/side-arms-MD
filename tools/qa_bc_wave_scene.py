#!/usr/bin/env python3
"""Actual Genesis 3P/4P source-wave replay, pending drain and exact spawn counts."""
import argparse
import json
import hashlib
import re
import struct
import subprocess
from pathlib import Path
from run_rom import ROOT,Runner
from bc_actor_layout import read_actor_pool
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--players',type=int,choices=(3,4),required=True)
p.add_argument('--round',type=int,choices=range(1,11),default=1)
p.add_argument('--updates',type=int,default=800)
p.add_argument('--bidirectional',action='store_true',help='Alternate fire sides to clear enemies approaching from behind')
p.add_argument('--rom',type=Path,default=ROOT/'out/release/rom.bin',help='ROM with sibling symbols and matching native structure definitions')
p.add_argument('--output',type=Path,help='Preserve an independent comparison run')
a=p.parse_args()
out=a.output or ROOT/(f'.local/bc-wave-{a.players}p' if a.round==1 else f'.local/bc-wave-{a.players}p-round{a.round}');out.mkdir(exist_ok=True)
source=out/'offsets.c';assembly=out/'offsets.s'
source.write_text('''#include "bc_party.h"
#define W(f) int w_##f = __builtin_offsetof(BcPartyControl,waves)+__builtin_offsetof(BcWaveQueue,f);
W(originals) W(extras) W(count) W(blocked) W(scale) W(head) W(pending)
int s_stopped=__builtin_offsetof(BcStage,stopped);
int c_scrolling=__builtin_offsetof(BcFrameCursor,scrolling);
int p_shots=__builtin_offsetof(BcPlayerControl,world.weapons.shots);
int shot_size=sizeof(BcShot);
int shot_state=__builtin_offsetof(BcShot,body.state);
''')
subprocess.run([str(Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'),'-m68000','-I'+str(ROOT/'inc'),'-S',str(source),'-o',str(assembly)],check=True)
o={};name=None
for line in assembly.read_text().splitlines():
    m=re.match(r'^(\w+):',line)
    if m:name=m[1]
    m=re.match(r'\s+\.(long|zero)\s+(\d+)',line)
    if m and name:o[name]=0 if m[1]=='zero' else int(m[2]);name=None
r=Runner(rom=a.rom);r.run(2600)
for key,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',a.round-1),
                  ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(key,struct.pack('>H',value))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8))
def counter(field):return r.u16('party_control',o['w_'+field])
def pending():return r.read('party_control',1,o['w_count'])[0]
worst=0;shot_seen=False
def step():
    global worst,shot_seen
    tick=r.u32('dbg_bc_native_ticks')
    fire=0x10 if a.bidirectional and tick%80>=40 else 0x20
    bits=fire if tick%40<20 else 0
    pressed=bits if tick%40==0 else 0
    r.write('pad',bytes([bits,pressed]*a.players+[0,0]*(4-a.players)));r.run(1)
    if any(r.read('player',1,o['p_shots']+i*o['shot_size']+o['shot_state'])[0]==128 for i in range(28)):shot_seen=True
    worst=max(worst,r.u16('prof_seg',6))
    assert r.u16('dbg_bc_native_status') in (0,4),(r.u16('dbg_bc_native_status'),hex(r.u16('dbg_bc_native_handler')))
    assert not r.u16('dbg_bc_native_unmapped') and not r.u16('dbg_bc_native_actor_unmapped')
for _ in range(a.updates*8+500):
    step()
    if r.u32('dbg_bc_native_ticks')>=a.updates:break
else:raise AssertionError(('native update timeout',a.updates,r.u32('dbg_bc_native_ticks')))
originals=counter('originals');assert originals>=4 or a.round==10
assert shot_seen,'test inputs never produced a live shot'
r.capture(out/'scaled.png')
# Stop further source events at this test boundary; pending copies must still
# drain through the production scheduler while players/actors keep running.
r.write('stage',b'\1',o['s_stopped'])
r.write('cursor',b'\0',o['c_scrolling'])
for _ in range(3000):
    step()
    if not pending():break
else:
    r.capture(out/'drain-stalled.png')
    (out/'actors.bin').write_bytes(read_actor_pool(r,rom=a.rom))
    (out/'stall.json').write_text(json.dumps(dict(camera=list(struct.unpack('>2I',r.read('stage',8))),
        head=r.read('party_control',1,o['w_head'])[0],pending=pending(),
        records=r.read('party_control',32,o['w_pending']).hex(),originals=counter('originals'),
        extras=counter('extras'),blocked=counter('blocked'),ticks=r.u32('dbg_bc_native_ticks')),indent=2))
    raise AssertionError(('pending waves did not drain',counter('blocked')))
assert counter('originals')==originals
remainders=list(r.read('party_control',9,o['w_scale']))
expected=(originals*(2 if a.players==3 else 5)-sum(i*v for i,v in enumerate(remainders)))//4
assert counter('extras')==expected,(originals,counter('extras'),expected)
result=dict(rom_sha256=hashlib.sha256(a.rom.read_bytes()).hexdigest(),round=a.round,players=a.players,bidirectional=a.bidirectional,live_shots_verified=shot_seen,originals=originals,extras=counter('extras'),remainders=remainders,
    updates=r.u32('dbg_bc_native_ticks'),frames=r.frames-2600,blocked=counter('blocked'),worst_lines=worst,
    sprite_drops=r.u32('spr_dbg_dropped'),runtime_remaps=r.u32('spr_dbg_remap'),full_speed_verified=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
assert not result['sprite_drops'] and not result['runtime_remaps'],result
r.capture(out/'drained.png')
print(f'PASS round {a.round}, {a.players}P: {originals} original + {counter("extras")} extra ordinary enemies; queue empty, no missing art/drops/remaps; full speed not verified')
