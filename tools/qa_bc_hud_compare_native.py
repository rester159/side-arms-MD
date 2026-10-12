#!/usr/bin/env python3
"""Exercise the production HUD score comparison in a native 68000 probe ROM.

The scratch cartridge replaces the reset entry and runs independent C reference
checks. It never modifies the playable release ROM.
"""
from pathlib import Path
import subprocess,struct
from run_rom import Runner,ROOT
out=ROOT/'.local/bc-hud-movep/probe';out.mkdir(parents=True,exist_ok=True);cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
s=(ROOT/'src/bc_hud.c').read_text()
helper=s[s.index('static inline u8 digits_equal('):s.index('static void score_digits(')]
code='typedef unsigned char u8;\n'+helper+r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0; status[0]=1;
 for(unsigned int alignment=0;alignment<4;alignment++) {
  unsigned char *a=(unsigned char *)(0xff8100+(alignment&1));
  unsigned char *b=(unsigned char *)(0xff8120+(alignment>>1));
  for(unsigned int digit=0;digit<8;digit++) for(unsigned int value=0;value<256;value++) {
   for(unsigned int i=0;i<8;i++) a[i]=b[i]=(unsigned char)(i*31+alignment);
   a[-1]=b[-1]=0xa5; a[8]=b[8]=0x5a;
   b[digit]=value;
   unsigned char expected=(unsigned char)(digit*31+alignment)==value;
   __asm__ volatile("":::"memory");
   unsigned char actual=digits_equal(a,b)!=0;
   __asm__ volatile("":::"memory");
   if(actual!=expected || a[-1]!=0xa5 || b[-1]!=0xa5 || a[8]!=0x5a || b[8]!=0x5a) {
    status[1]=alignment;status[2]=digit;status[3]=value;status[4]=actual;status[0]=0xdead;return;
   }
   for(unsigned int i=0;i<8;i++) if(a[i]!=(unsigned char)(i*31+alignment) || b[i]!=(i==digit?value:(unsigned char)(i*31+alignment))) {
    status[0]=0xdead;return;
   }
   checked++;
  }
 }
 status[1]=checked;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(objcopy),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(3000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==8192
print('PASS native 68000: 8192 eight-digit comparisons, all alignment pairs and differing byte/value positions; input and sentinels preserved')
