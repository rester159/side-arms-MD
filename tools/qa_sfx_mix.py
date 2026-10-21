#!/usr/bin/env python3
"""Execute the shipping Z80 attenuation routine for every input and both mixes."""
import hashlib
import json
from pathlib import Path
from z80lite import Z80

rom=Path('out/release/rom.bin').read_bytes()
symbols={line.split()[2]:int(line.split()[0],16) for line in Path('out/release/symbol.txt').read_text().splitlines() if len(line.split())==3}
driver=rom[symbols['sa_sound_drv']:symbols['sa_sound_drv']+8192]
table=bytes([15,14,14,14,14,14,14,12,11,9,8,6,5,3,2,0])
table_at=driver.index(table)
entry=driver.rfind(bytes.fromhex('e60f21'),0,table_at)
assert entry>=0 and table_at-entry<40
cases=0
for mix in (0,3):
 for volume in range(256):
  memory=bytearray(driver)
  memory[0x1f0b]=mix
  cpu=Z80(lambda address:memory[address])
  cpu.a=volume;cpu.bc=0x1234;cpu.de=0x5678
  cpu.call(entry)
  assert cpu.a==min(15,table[volume&15]+mix),(mix,volume,cpu.a)
  assert cpu.bc==0x1234 and cpu.de==0x5678
  cases+=1
print(json.dumps(dict(passed=True,cases=cases,rom_sha256=hashlib.sha256(rom).hexdigest())))
