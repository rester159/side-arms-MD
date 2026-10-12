#!/usr/bin/env python3
"""Audit native queued DMA command atomicity during a bounded boot/attract run.

Read-only opcode hooks verify interrupt masking, descriptor register values,
command order, and restored interrupt priority. This does not prove all gameplay
DMA workloads or hardware behavior. Requires the pinned profiling core.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
from run_rom import ROOT, Runner
from profile_genesis import instruction_profile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--frames', type=int, default=750)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
assert a.frames > 0
a.output.mkdir(parents=True, exist_ok=True)
build = Path(os.environ.get('SIDEARMS_BUILD', ROOT))
rom = (build/'out/release/rom.bin').read_bytes()
r = Runner()
entry = r.symbols['flushQueue']
# Require the actual native sequence; never assume an address from an older ROM.
pattern = bytes.fromhex('40c1007c07003298329846c151c8')
start = rom.find(pattern, entry, entry + 80)
assert start >= 0, 'atomic flushQueue sequence not found'
pcs = [start, start+6, start+8, start+10, start+12]
getreg = r.lib.m68k_get_reg
getreg.argtypes = [C.c_uint]
getreg.restype = C.c_uint
cpu = C.addressof(C.c_uint8.in_dll(r.lib, 'm68k'))
regs = (C.c_uint8*32).in_dll(r.lib, 'reg')
phase = 0
saved_priority = 0
transfers = 0
max_words = 0
priorities = set()

def observe():
    global phase, saved_priority, transfers, max_words
    pc = (C.c_uint32.from_address(cpu+0x2858).value-2) & 0xffffff
    sr = getreg(17)
    if pc == start:
        assert phase == 0, ('nested transfer', phase)
        saved_priority = sr & 0x700
        priorities.add(saved_priority >> 8)
        phase = 1
    elif pc == start+6:
        assert phase == 1 and sr & 0x700 == 0x700
        at = (getreg(8)-12) & 65535
        raw = bytes(r.ram[((at+i)&65535)^1] for i in range(16))
        words = raw[1] | raw[3] << 8
        assert words > 0, 'unintended zero-length queued DMA'
        for register, offset in ((19,1),(20,3),(22,5),(15,7),(23,9),(21,11)):
            assert regs[register] == raw[offset], (r.frames, register, regs[register], raw[offset])
        max_words = max(max_words, words)
        phase = 2
    elif pc == start+8:
        assert phase == 2 and sr & 0x700 == 0x700
        phase = 3
    elif pc == start+10:
        assert phase == 3 and sr & 0x700 == 0x700
        phase = 4
    else:
        assert phase == 4 and sr & 0x700 == saved_priority
        transfers += 1
        phase = 0

with instruction_profile(r, a.output/'audit', enabled=False, watch=(pcs, observe)):
    r.run(a.frames)
assert transfers > 0 and phase == 0, ('incomplete audit', transfers, phase)
assert hashlib.sha256((build/'out/release/rom.bin').read_bytes()).digest() == hashlib.sha256(rom).digest()
result = dict(rom_sha256=hashlib.sha256(rom).hexdigest(), frames=a.frames,
              transfers=transfers, max_queued_words=max_words,
              restored_priorities=sorted(priorities),
              scope='Boot/attract only; native paired word commands and descriptor registers; no whole-game or hardware claim')
(a.output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
