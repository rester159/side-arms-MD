#!/usr/bin/env python3
"""Launch all twelve Home mode/player selections using real controller input.

Verifies dialog/cancel/selection and entry; does not claim full-game or speed coverage.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from run_rom import ROOT,Runner,PAD
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--mode',choices=('normal','bc','rush'))
p.add_argument('--players',type=int,choices=range(1,5))
a=p.parse_args();assert (a.mode is None)==(a.players is None)
a.output.mkdir(parents=True,exist_ok=True)
rom=ROOT/'out/release/rom.bin';sha=hashlib.sha256(rom.read_bytes()).hexdigest()
if a.mode is None:
 rows=[]
 for mode in ('normal','bc','rush'):
  for players in range(1,5):
   folder=a.output/f'{mode}-{players}p'
   subprocess.run([sys.executable,__file__,'--mode',mode,'--players',str(players),'--output',str(folder)],check=True)
   rows.append(json.loads((folder/'result.json').read_text()))
 assert len(rows)==12 and all(r['rom_sha256']==sha for r in rows)
 assert hashlib.sha256(rom.read_bytes()).hexdigest()==sha
 (a.output/'results.json').write_text(json.dumps(dict(rom_sha256=sha,cases=rows,full_speed_verified=False),indent=2)+'\n')
 print('PASS: all 12 Home mode/player dialog, cancel and launch combinations')
else:
 r=Runner();r.run(2600)
 def tap(b):r.run(5,PAD[b]);r.run(20)
 assert r.u32('flow_state')==0
 tap('DOWN');tap('START');assert r.u32('flow_state')==9
 mode=('normal','bc','rush').index(a.mode)
 for _ in range(mode):tap('DOWN')
 assert r.read('home_cursor',1)==bytes([mode])
 saved=r.read('home_cfg',1,5)
 tap('A');assert r.read('player_dialog',1)==b'\1' and r.u32('flow_state')==9
 tap('DOWN');tap('B')
 assert r.read('player_dialog',1)==b'\0' and r.read('home_cfg',1,5)==saved and r.u32('flow_state')==9
 tap('A')
 for _ in range((a.players-saved[0])%4):tap('DOWN')
 assert r.read('player_choice',1)==bytes([a.players-1])
 r.capture(a.output/'modal.png');tap('A')
 assert r.read('home_cfg',1,5)==bytes([a.players]) and r.u16('player_limit')==a.players
 state=r.u32('flow_state');assert state=={'normal':6,'bc':14,'rush':12}[a.mode],(a.mode,state)
 if a.mode=='bc':assert r.u16('dbg_bc_native_players')==a.players and r.u16('dbg_bc_native_status') in (0,4)
 if a.mode=='rush':assert r.read('rush_joined',4)==bytes([1]*a.players+[0]*(4-a.players))
 r.capture(a.output/'launched.png')
 assert hashlib.sha256(rom.read_bytes()).hexdigest()==sha
 result=dict(rom_sha256=sha,mode=a.mode,players=a.players,dialog=True,cancel_preserves_count=True,flow_state=state,launch=True,scope='Home dialog and entry, no gameplay performance claim')
 (a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(f'PASS {a.mode} {a.players}P')
