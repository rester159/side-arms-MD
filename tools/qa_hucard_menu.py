#!/usr/bin/env python3
"""Real Home menu -> Sound Test -> PC Engine playback -> Arcade -> Back."""
import ctypes as C
import json
from run_rom import ROOT, Runner, PAD
r=Runner();r.run(2600)
zram=(C.c_uint8*8192).in_dll(r.lib,'zram')
out=ROOT/'.local/pce-hucard';out.mkdir(exist_ok=True)
def tap(key):r.run(5,PAD[key]);r.run(20)
def state():return r.u32('flow_state')
assert state()==0
tap('DOWN');tap('A');assert state()==9
for _ in range(3):tap('DOWN')
tap('A');assert state()==1
for _ in range(10):tap('DOWN')
tap('A');assert r.read('snd_source',1)==b'\0'
fs=state()
tap('DOWN');tap('DOWN');tap('RIGHT')
assert r.read('snd_source',1)==b'\1'
tap('UP');tap('UP');tap('RIGHT');tap('A')
assert r.read('hucard_active',1)==b'\1'
r.run(600)
assert zram[0x1b0a]==0
r.capture(out/'sound-test-pce.png')
# Changing source stops the old soundtrack before an Arcade selection.
tap('DOWN');tap('DOWN');tap('LEFT')
assert r.read('snd_source',1)==b'\0' and r.read('hucard_active',1)==b'\0'
tap('UP');tap('UP');tap('RIGHT');tap('A');r.run(120)
assert not zram[0x1f08]
tap('B');assert state()==1 and state()!=fs
print(json.dumps(dict(passed=True,underruns=int(zram[0x1b0a]),rom='out/release/rom.bin'),indent=2))
