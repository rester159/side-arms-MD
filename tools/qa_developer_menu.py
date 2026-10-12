#!/usr/bin/env python3
"""Verify the secret Home developer menu through physical controller input."""
import argparse, hashlib, json
from pathlib import Path
from run_rom import ROOT, Runner, PAD
from qa_soak import O
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['normal','bc'],required=True);a=p.parse_args()
r=Runner();out=ROOT/'.local/developer-v2'/a.mode;out.mkdir(parents=True,exist_ok=True)
def tap(key):r.run(5,PAD[key]);r.run(20)
def byte(name):return r.read(name,1)[0]
r.run(2600);assert r.u32('flow_state')==0
tap('DOWN');tap('A');assert r.u32('flow_state')==9
assert not byte('developer_unlocked')
# Seven directions alone do not unlock; the final Right is required.
for key in ['UP','DOWN','UP','DOWN','LEFT','RIGHT','LEFT']:tap(key)
assert not byte('developer_unlocked')
tap('RIGHT');assert byte('developer_unlocked') and not byte('developer_menu')
assert r.u32('flow_state')==9
while byte('home_cursor')!=4:tap('DOWN')
tap('A');assert byte('developer_menu')
r.capture(out/'developer.png')
# Developer Sound Test uses the normal sound menu and returns via Options/Home.
for _ in range(6):tap('DOWN')
tap('A');assert r.u32('flow_state')==11
tap('B');tap('B');assert r.u32('flow_state')==9
while byte('home_cursor')!=4:tap('DOWN')
tap('A');assert byte('developer_menu')
# Return Home and restore its Normal cursor for the subsequent re-entry check.
tap('B')
while byte('home_cursor')!=0:tap('UP')
for key in ['UP','DOWN','UP','DOWN','LEFT','RIGHT','LEFT','RIGHT']:tap(key)
assert not byte('developer_menu')
while byte('home_cursor')!=4:tap('DOWN')
tap('A');assert byte('developer_menu')
# Both toggles must be operable, and finish ON for a protected practice launch.
for _ in range(2):tap('DOWN')
for name in ['developer_invincible','developer_lives']:
 assert byte(name)==1
 tap('LEFT');assert byte(name)==0
 tap('RIGHT');assert byte(name)==1
 tap('DOWN')
# Back returns to Home, where the unlocked menu remains selectable.
tap('B');assert not byte('developer_menu')
while byte('home_cursor')!=4:tap('DOWN')
tap('A');assert byte('developer_menu')
if a.mode=='bc':tap('RIGHT')
for key in ('A','C','START'):
 tap(key);assert byte('developer_mode')==int(a.mode=='bc')
tap('DOWN');tap('RIGHT');tap('RIGHT') # round 3
for key in ('A','C','START'):
 tap(key);assert byte('developer_round')==2
for _ in range(4):tap('DOWN')
tap('A');assert byte('developer_active')
r.run(2000)
if a.mode=='normal':
 assert r.u32('flow_state')==7
 assert r.u16('level',O['o_Level_section'])==2
 assert r.read('players',1,O['o_Player_invuln'])[0]>150
 # Inject the last death-animation step; validate actual life spending both ways.
 lives=r.read('players',1,O['o_Player_lives'])[0]
 def death():
  r.write('players',(2).to_bytes(4,'big'),O['o_Player_state'])
  r.write('players',bytes([1,7]),O['o_Player_invuln']+3)
  r.run(10)
 death();assert r.read('players',1,O['o_Player_lives'])[0]==lives
 r.write('developer_lives',b'\0');death()
 assert r.read('players',1,O['o_Player_lives'])[0]==lives-1
 r.write('developer_lives',b'\1')
else:
 assert r.u16('dbg_bc_native_current_round')==2
 assert r.u32('dbg_bc_native_ticks')>100
 # Force the native death path, checking infinite lives across its checkpoint.
 r.write('dbg_bc_native_die',b'\0\1');r.run(500)
 assert r.u16('dbg_bc_native_status')!=7
r.capture(out/'practice.png')
# Reset clears practice effects; ordinary launch stays ordinary.
r.run(5,PAD['A']|PAD['B']|PAD['C']|PAD['START']);r.run(30)
assert r.u32('flow_state')==0 and not byte('developer_active')
tap('A');assert r.u32('flow_state')==9
while byte('home_cursor')!=0:tap('UP')
tap('A');tap('A');r.run(1800)
assert not byte('developer_active')
report={'passed':True,'mode':a.mode,'exact_code':True,'practice_round':3,'toggles':True,'reset_clears_practice':True,'sha256':hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()}
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
