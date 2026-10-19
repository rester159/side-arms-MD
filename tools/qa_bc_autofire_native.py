#!/usr/bin/env python3
"""Hold real controller buttons in BC: configured turbo pulses; ordinary hold charges."""
import argparse,json,hashlib
from pathlib import Path
from run_rom import Runner,PAD
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--players',type=int,choices=(1,4),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
r=Runner();r.run(2600)
for k,v in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',0),('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(k,v.to_bytes(2,'big'))
r.run(200)
assert r.u16('players_bc_count')==a.players
assert not r.read('dbg_pad_override',1)[0]
rows=[]
for button in ('A','B'):
 for enabled in (0,1):
  r.run(8);r.write('pad_cfg',bytes([enabled,enabled]),6)
  samples=[];last=-1
  for tick in range(96):
   r.run(1,PAD[button])
   samples.append(r.read('pad',2).hex())
  bit=16 if button=='A' else 32
  held=[bytes.fromhex(s)[0]&bit for s in samples]
  rising=sum(bool(v) and (i==0 or not held[i-1]) for i,v in enumerate(held))
  assert rising>=12 if enabled else rising==1,(button,enabled,rising)
  # A four-player frame can reuse the previous picture before polling again.
  assert all(held[next(i for i,v in enumerate(held) if v):]) if not enabled else any(not v for v in held)
  rows.append(dict(button=button,turbo=bool(enabled),rising_edges=rising,held_frames=sum(bool(v)for v in held)))
  r.capture(a.output/f'{button}-{enabled}.png')
report=dict(passed=True,players=a.players,real_controller_input=True,settings_injected=True,protected_debug_launch=True,
 rom_sha256=hashlib.sha256(Path('out/release/rom.bin').read_bytes()).hexdigest(),cases=rows)
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
