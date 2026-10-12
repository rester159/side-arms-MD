#!/usr/bin/env python3
"""Measure native stack/peer allocation separation without changing guest code.

Only detects stack-pointer overlap with live peer allocations in this fixture;
it does not prove whole-game stack safety or detect every out-of-bounds write.
"""
import argparse
import ctypes as C
import hashlib
import json
import re
import subprocess
from pathlib import Path
from run_rom import ROOT,CORE,Runner
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--rom',type=Path,default=ROOT/'out/release/rom.bin')
p.add_argument('--players',type=int,choices=(2,3,4),default=4)
p.add_argument('--round',type=int,choices=range(1,11),default=10)
p.add_argument('--updates',type=int,default=2000)
p.add_argument('--ending',action='store_true')
p.add_argument('--plain',action='store_true',help='Uninstrumented replay for state comparison')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
assert a.updates>0
assert hashlib.sha256(CORE.read_bytes()).hexdigest()=='20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
digest=hashlib.sha256(a.rom.read_bytes()).hexdigest()
r=Runner(rom=a.rom);r.run(2600)
getreg=r.lib.m68k_get_reg;getreg.argtypes=[C.c_uint];getreg.restype=C.c_uint32
cpu=C.addressof(C.c_uint8.in_dll(r.lib,'m68k'))
assert getreg(16)==C.c_uint32.from_address(cpu+0x2858).value
assert 0xff0000 <= (getreg(15)&0xffffff) < 0x1000000
# Compile the target ABI size without sharing other tests' temporary files.
probe=a.output/'size.c';probe.write_text('#include "bc_player.h"\nint size=sizeof(BcPlayerControl);\n')
subprocess.run([str(Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'),'-m68000','-I'+str(ROOT/'inc'),'-S',str(probe),'-o',str(probe.with_suffix('.s'))],check=True)
player_size=int(re.search(r'size:\s*\.long\s+(\d+)',probe.with_suffix('.s').read_text())[1])
hook=a.output/'stack-hook.dylib'
subprocess.run(['cc','-O2','-dynamiclib',str(ROOT/'tools/bc_stack_hook.c'),'-o',str(hook)],check=True)
h=C.CDLL(str(hook));h.stack_begin.argtypes=[C.c_void_p]*4+[C.c_uint]*4
base=C.cast(getreg,C.c_void_p).value-0x55aac
if not a.plain:assert h.stack_begin(cpu,base+0x1fefb0,C.cast(getreg,C.c_void_p),C.addressof(r.ram),r.symbols['peers']&65535,r.symbols['dbg_bc_native_ticks']&65535,a.players,player_size)==0
try:
 r.write('home_session',b'\1' if a.ending else b'\0')
 for name,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',a.round-1),('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(name,value.to_bytes(2,'big'))
 r.write('dbg_pad_override',b'\1')
 for _ in range(a.updates*5+1000):
  tick=r.u32('dbg_bc_native_ticks');bits=0x20 if tick%100<80 else 0
  r.write('pad',bytes([bits,bits if tick%100==0 else 0]*a.players+[0,0]*(4-a.players)))
  r.run(1)
  assert r.u16('dbg_bc_native_status') in (0,4,6)
  if r.u32('dbg_bc_native_ticks')>=a.updates:break
 else:raise AssertionError('update timeout')
 if a.ending:
  r.write('pad',bytes(8));r.write('dbg_bc_native_status',b'\0\6')
  for _ in range(15000):
   r.run(1)
   if r.read('ending_bonus_phase',1)==b'\7':break
  else:raise AssertionError('ending timeout')
finally:
 if not a.plain:h.stack_end()
assert hashlib.sha256(a.rom.read_bytes()).hexdigest()==digest
names=('lowest_sp','lowest_pc','lowest_tick','minimum_gap','gap_sp','gap_end','gap_pc','gap_tick','overlap_samples')
measure={n:C.c_uint32.in_dll(h,n).value for n in names} if not a.plain else {}
if measure:
 assert C.c_uint64.in_dll(h,'samples').value>0 and measure['gap_end']>=0xff0000, 'No live peer allocation observed'
 assert 0xff0000<=measure['lowest_sp']<0x1000000, 'Stack pointer outside work RAM'
 measure['sampled_boundaries']=C.c_uint64.in_dll(h,'samples').value
if measure and measure['minimum_gap']&0x80000000:measure['minimum_gap']-=1<<32
result=dict(rom_sha256=digest,players=a.players,round=a.round,ending=a.ending,
 instrumented=not a.plain,frames=r.frames,ticks=r.u32('dbg_bc_native_ticks'),
 ram_sha256=hashlib.sha256(bytes(r.ram)).hexdigest(),stack=measure,
 scope='This input route only; peer-allocation overlap check, not whole-game stack safety')
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if measure:assert not measure['overlap_samples'], 'Native stack overlaps peer allocation'
