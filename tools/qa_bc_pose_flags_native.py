#!/usr/bin/env python3
"""Exhaust all source attribute words through the production 68000 pose selector."""
from pathlib import Path
import struct
import subprocess
from run_rom import ROOT, Runner
out = ROOT/'.local/bc-pose-flags-native'
out.mkdir(parents=True, exist_ok=True)
cc = Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
(out/'probe.c').write_text(r'''
#include "bc_actor_art.h"
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 BcActor *a=(BcActor *)0xff8100;
 a->body.state=0x80; a->body.flags=0;
 a->body.sprite=a->body.sprite_base=0x400;
 a->sprite_base_ref=0x3698;
 a->body.x=0xabc12345; a->body.y=0x98765432;
 status[0]=1;
 for(unsigned int v=0;v<65536;v++) {
  a->body.attributes=v;
  unsigned int got=bc_actor_pose(a);
  unsigned int expected=0x184127;
  if(v&0x800)expected|=0x10000;
  if(v&0x8000)expected|=0x20000;
  if(got!=expected || a->body.attributes!=v || a->body.x!=0xabc12345 || a->body.y!=0x98765432) {
   status[1]=v;status[2]=got;status[3]=expected;status[0]=0xdead;return;
  }
 }
 status[1]=65536;status[0]=0x600d;
}
''')
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-I'+str(ROOT/'inc'),'-O2','-nostdlib',
 '-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),
 str(out/'probe.c'),str(ROOT/'src/bc_actor_art.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes())
rom.extend(bytes(0x400000-len(rom)))
raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw
struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(3000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==65536
print('PASS: 65536 native attribute words; packed flips/key/visibility/handling and unchanged actor fields')
