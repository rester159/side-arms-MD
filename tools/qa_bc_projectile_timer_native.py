#!/usr/bin/env python3
"""Exhaust production native animation-timer decrement and neighboring bytes."""
from pathlib import Path
import struct,subprocess
from run_rom import ROOT,Runner
out=ROOT/'.local/bc-projectile-timer-native';out.mkdir(exist_ok=True)
s=(ROOT/'src/bc_rules.c').read_text()
helper=s[s.index('static inline __attribute__((always_inline)) unsigned char projectile_timer_due('):s.index('/* $998A-$99B9')]
(out/'probe.c').write_text(helper+r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned char *bytes=(unsigned char *)0xff8100;
 unsigned int checked=0;
 status[0]=1;
 for(unsigned int alignment=1;alignment<=2;alignment++)
  for(unsigned int v=0;v<256;v++) {
   for(unsigned int j=0;j<4;j++)bytes[j]=0xa5;
   bytes[alignment]=v;
   unsigned char due=projectile_timer_due(&bytes[alignment]);
   if(due!=(v==1) || bytes[alignment]!=(unsigned char)(v-1)) {
    status[1]=v;status[2]=due;status[3]=bytes[alignment];status[0]=0xdead;return;
   }
   for(unsigned int j=0;j<4;j++)if(j!=alignment && bytes[j]!=0xa5) {
    status[1]=v;status[2]=j;status[0]=0xdead;return;
   }
   checked++;
  }
 status[1]=checked;status[0]=0x600d;
}
''')
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom);(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(100):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==512
print('PASS: 512 native timer cases; all256 values at even/odd addresses, wrap, zero branch and neighboring sentinels')
