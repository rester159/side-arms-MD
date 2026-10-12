#!/usr/bin/env python3
"""Exhaust projectile flip attributes through the production 68000 art selector."""
from pathlib import Path
import struct
import subprocess
from run_rom import ROOT, Runner
out = ROOT/'.local/bc-projectile-flips-native'
out.mkdir(parents=True, exist_ok=True)
cc = Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
(out/'probe.c').write_text(r'''
#include "bc_projectile_art.h"
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 BcBeam *b=(BcBeam *)0xff8100;
 b->state=0x80;b->x=0xabc12345;b->y=0x98765432;
 unsigned short frames[4]={0x1b8,0x1bc,0x1e0,0xffff};
 unsigned int checks=0;status[0]=1;
 for(unsigned int k=0;k<4;k++)for(unsigned int v=0;v<65536;v++) {
  b->sprite=frames[k];b->attributes=v;b->facing=(v&4)!=0;
  BcProjectileSprite got=bc_projectile_sprite(b,0,0);
  unsigned int expected=0;
  if(v&0x800)expected|=1;
  if(v&0x8000)expected|=2;
  if(k==1)expected=0;
  if(got.flips!=expected || b->attributes!=v || b->x!=0xabc12345 || b->y!=0x98765432 ||
     got.visible!=(k!=3) || got.handled!=(k!=3)) {
   status[1]=v;status[2]=got.flips;status[3]=expected;status[0]=0xdead;return;
  }
  checks++;
 }
 status[1]=checks;status[0]=0x600d;
}
''')
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-I'+str(ROOT/'inc'),'-O2','-nostdlib',
 '-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),
 str(out/'probe.c'),str(ROOT/'src/bc_projectile_art.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes())
rom.extend(bytes(0x400000-len(rom)))
raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw
struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(20000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==262144
print('PASS: 262144 native projectile attribute/frame cases, flips and handling, facing override, unchanged inputs')
