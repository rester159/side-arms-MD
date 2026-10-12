#!/usr/bin/env python3
"""Exhaust valid pixel coordinates and invalid boundaries through native terrain lookup."""
from pathlib import Path
import argparse
import struct
import subprocess
from run_rom import ROOT, Runner

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, default=ROOT/'.local/normal-terrain-native')
out = parser.parse_args().output
out.mkdir(parents=True, exist_ok=True)
source = (ROOT / 'src/level.c').read_text()
start = source.index('bool terrain_solid(')
transition = 'typedef unsigned int u32;typedef unsigned short u16;typedef short s16;typedef unsigned char bool;\n#define FALSE 0\n#define terrain_cells ((const unsigned char *)0x3a0000)\n' + source[start:source.index('\n}\n', start) + 3]
main = r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checks=0;status[0]=1;
 for(unsigned y=0;y<4096;y++) for(unsigned x=0;x<4096;x++) {
  unsigned int index=(y/16)*256+x/16;
  unsigned char expected=(index*73u)^(index>>8);
  unsigned char got=terrain_solid(x,y);
  if(got!=expected){status[1]=x;status[2]=y;status[3]=got;status[0]=0xdead;return;}
  checks++;
 }
 for(unsigned v=4096;v<65536;v++) {
  if(terrain_solid(v,0)||terrain_solid(4095,v)||terrain_solid(v,v)) {
   status[1]=v;status[0]=0xdead;return;
  }
  checks+=3;
 }
 status[1]=checks;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(transition+main)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc = Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc), '-m68000', '-std=gnu99', '-O3', '-nostdlib', '-ffreestanding', '-fno-builtin', '-Wl,-Ttext=0x3e0000', str(out/'start.s'), str(out/'probe.c'), '-o', str(out/'probe.elf')], check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')), '-O', 'binary', str(out/'probe.elf'), str(out/'probe.bin')], check=True)
rom = bytearray((ROOT/'out/release/rom.bin').read_bytes())
rom.extend(bytes(0x400000-len(rom)))
# Distinct values test address selection, including the signed-index boundary.
rom[0x3a0000:0x3b0000] = bytes(((i*73)^(i>>8))&255 for i in range(65536))
raw = (out/'probe.bin').read_bytes()
assert len(raw) < 0x20000
rom[0x3e0000:0x3e0000+len(raw)] = raw
struct.pack_into('>I', rom, 4, 0x3e0000)
(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r = Runner(rom=out/'probe-rom.bin')
for _ in range(40000):
    r.run(1)
    if r.u32('probe_status') in (0x600d, 0xdead):
        break
assert r.u32('probe_status') == 0x600d, r.read('probe_status',16).hex()
assert r.u32('probe_status',4) == 16777216 + 61440*3
print('PASS native 68000: all 16777216 valid pixels and 184320 invalid-coordinate probes match;', r.frames, 'video frames')
