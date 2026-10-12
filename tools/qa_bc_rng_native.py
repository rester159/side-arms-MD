#!/usr/bin/env python3
"""Exhaust every source RNG seed through the production 68000 implementation."""
from pathlib import Path
import struct
import subprocess
from run_rom import ROOT, Runner

out = ROOT / '.local/bc-rng-transition/native'
out.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'src/bc_rules.c').read_text()
start = source.index('unsigned short bc_random_next(')
transition = source[start:source.index('\n}\n', start) + 3]
main = r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 volatile unsigned short *input=(volatile unsigned short *)0xff8010;
 const unsigned short *expected=(const unsigned short *)0x3a0000;
 status[0]=1;
 for(unsigned int seed=0;seed<65536;seed++) {
  *input=seed;
  unsigned short got=bc_random_next(*input);
  if(got!=expected[seed]) {
   status[1]=seed;status[2]=got;status[3]=expected[seed];status[0]=0xdead;return;
  }
 }
 status[1]=65536;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(transition+main)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc = Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc), '-m68000', '-O3', '-nostdlib', '-ffreestanding', '-fno-builtin', '-Wl,-Ttext=0x3e0000', str(out/'start.s'), str(out/'probe.c'), '-o', str(out/'probe.elf')], check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')), '-O', 'binary', str(out/'probe.elf'), str(out/'probe.bin')], check=True)
rom = bytearray((ROOT/'out/release/rom.bin').read_bytes())
rom.extend(bytes(0x400000-len(rom)))
# Independent source algorithm: 16-bit triple, then an 8-bit high-byte addition.
expected = []
for seed in range(65536):
    triple = (seed*3) & 65535
    high = ((triple >> 8) + (seed & 255)) & 255
    expected.append((triple & 255) | (high << 8))
rom[0x3a0000:0x3c0000] = struct.pack('>65536H', *expected)
raw = (out/'probe.bin').read_bytes()
assert len(raw) < 0x20000
rom[0x3e0000:0x3e0000+len(raw)] = raw
struct.pack_into('>I', rom, 4, 0x3e0000)
(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r = Runner(rom=out/'probe-rom.bin')
for _ in range(1000):
    r.run(1)
    if r.u32('probe_status') in (0x600d, 0xdead):
        break
assert r.u32('probe_status') == 0x600d, r.read('probe_status',16).hex()
assert r.u32('probe_status',4) == 65536
print('PASS native 68000: all 65536 RNG transitions match the source byte algorithm;', r.frames, 'video frames')
