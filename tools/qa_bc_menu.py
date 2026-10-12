#!/usr/bin/env python3
"""Real Home menu -> Before Christ modal -> chosen party -> exit/re-entry."""
import argparse
import hashlib
import json
import os
import struct
import subprocess
from pathlib import Path
from run_rom import Runner, PAD, ROOT
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--players',type=int,choices=(1,2,3,4),required=True)
p.add_argument('--output',type=Path,help='Separate evidence directory; defaults to the per-player menu directory')
a=p.parse_args();build=Path(os.environ.get('SIDEARMS_BUILD',ROOT));r=Runner();r.run(2600)
out=a.output or ROOT/f'.local/bc-menu-{a.players}p';out.mkdir(parents=True,exist_ok=True)
def tap(button):
    r.run(5,PAD[button]);r.run(20)
def state():return r.u32('flow_state')
assert state()==0
tap('DOWN');tap('START');assert state()==9
tap('DOWN');r.capture(out/'home.png');tap('A')
assert state()==9 and r.read('player_dialog',1)==b'\1'
# Cancel preserves settings and stays on Before Christ.
saved=r.read('home_cfg',1,5)
tap('DOWN');tap('B')
assert state()==9 and r.read('home_cfg',1,5)==saved
tap('A')
for _ in range((a.players-saved[0])%4):tap('DOWN')
r.capture(out/'modal.png');tap('A');r.run(80)
assert state()==14 and r.u16('dbg_bc_native_players')==a.players
assert r.u16('player_limit')==a.players
assert r.u16('dbg_bc_native_current_round')==0
assert r.u32('dbg_bc_native_ticks')>30
assert r.u16('dbg_bc_native_status') in (0,4)
assert not r.u16('dbg_bc_native_protect') and not r.u16('dbg_bc_native_audio_manual')
assert not r.u16('dbg_bc_native_unmapped') and not r.u16('dbg_bc_native_actor_unmapped')
assert all(r.u16('dbg_bc_native_party_lives',i*2)==2 for i in range(a.players))
r.capture(out/'play.png')
# Each selected controller can pause the shared simulation. Inspect complete
# native records using the linked binary's sizes, including dynamic peers.
sizes={}
for line in subprocess.check_output([str(Path.home()/'mars/m68k-elf/bin/m68k-elf-nm'),
                                    '-S',str(build/'out/release/rom.out')],text=True).splitlines():
    fields=line.split()
    if len(fields)==4:
        name=fields[3].split('.lto_priv.')[0]
        # Match Runner's resolved address, not the first same-named symbol.
        # In particular the ROM sound routine 'score' is not the BC RAM record.
        if r.symbols.get(name)==int(fields[0],16):sizes[name]=int(fields[1],16)
def frozen_state():
    names=('player','stage','actors','score','peer_scores','seed','cursor','defeat',
           'round_exit','audio_request','scheduler_counter','party_control')
    snapshot={name:r.read(name,sizes[name]) for name in names}
    if a.players>1:
        at=r.u32('peers')&65535
        snapshot['peers']=bytes(r.ram[(at+i)^1] for i in range(sizes['player']*(a.players-1)))
    snapshot['ticks']=r.u32('dbg_bc_native_ticks')
    return snapshot
# Physical Start is edge-triggered: holding it must not repeatedly toggle.
r.run(40,PAD['START'])
assert r.read('scene_paused',1)==b'\1'
r.run(5);tap('START')
assert r.read('scene_paused',1)==b'\0'
r.write('dbg_pad_override',b'\1')
def buttons(slot,bits):
    value=bytearray(8);value[slot*2:slot*2+2]=bytes([bits,bits]);r.write('pad',value)
def toggle_pause(slot,expected):
    buttons(slot,0x80)
    for _ in range(20):
        r.run(1)
        if bool(r.read('scene_paused',1)[0])==expected:break
    else:raise AssertionError(('pause toggle',slot,expected))
    r.write('pad',bytes(8));r.run(2)
for slot in range(a.players):
    toggle_pause(slot,True)
    before=frozen_state()
    # Gameplay buttons are held while paused; neither shots nor movement run.
    r.write('pad',bytes([0x31,0x31]*a.players+[0,0]*(4-a.players)));r.run(60)
    assert frozen_state()==before, ('simulation advanced while paused',slot)
    r.capture(out/'paused.png')
    toggle_pause(slot,False)
    r.run(3)
    assert r.u32('dbg_bc_native_ticks')>before['ticks']
# Unselected controller slots cannot pause; source clear-task inhibit is honored.
if a.players<4:
    buttons(a.players,0x80);r.run(5)
    assert not r.read('scene_paused',1)[0]
r.write('round_exit',b'\1',3);buttons(0,0x80);r.run(5)
assert not r.read('scene_paused',1)[0]
r.write('round_exit',b'\0',3);r.write('pad',bytes(8))
r.write('dbg_pad_override',b'\0');r.run(3)

# Drive the existing terminal boundary, without simulating four complete deaths.
r.write('dbg_bc_native_status',struct.pack('>H',7));r.run(20)
assert r.u16('dbg_bc_native_status')==7
assert r.read('terminal_shown',1)==b'\1'
r.capture(out/'game-over.png');tap('START')
assert state()==9 and not r.u16('dbg_bc_native')
# Start again from the retained BC menu cursor, then use the normal soft reset.
tap('A');tap('A');r.run(100)
assert state()==14 and r.u16('player_limit')==a.players
r.write('dbg_pad_override',b'\1');toggle_pause(0,True)
r.write('dbg_pad_override',b'\1');r.write('pad',bytes([0xf0,0xf0,0,0,0,0,0,0]));
for _ in range(20):
    r.run(1)
    if not r.u16('dbg_bc_native'):break
r.write('pad',bytes(8));r.run(60)
assert state()==0 and not r.u16('dbg_bc_native')
print(f'PASS: {a.players}P BC menu, cancel, launch, real audio, every-controller pause/freeze/resume, inhibit, terminal return, re-entry, paused soft reset')

(out/'result.json').write_text(json.dumps(dict(passed=True,players=a.players,rom_sha256=hashlib.sha256((build/'out/release/rom.bin').read_bytes()).hexdigest(),frozen_record_sizes={n:sizes[n]for n in ('player','stage','actors','score','peer_scores','seed','cursor','defeat','round_exit','audio_request','scheduler_counter','party_control')}),indent=2)+'\n')
