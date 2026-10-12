#!/usr/bin/env python3
"""Exercise the production score equality primitive in a native 68000 probe ROM.

The scratch cartridge replaces the reset entry and runs independent C reference
checks. It never modifies the playable release ROM.
"""
from pathlib import Path
import subprocess,struct
from run_rom import Runner,ROOT
out=ROOT/'.local/bc-score-packed-probe';out.mkdir(parents=True,exist_ok=True);cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
s=(ROOT/'src/bc_score.c').read_text();helper=s[s.index('static unsigned char same_score('):s.index('void bc_score_continue(')]
code='#include "bc_score.h"\n'+helper+r'''
void probe_main(void) {
 static const unsigned char bases[16]={0,1,2,8,9,10,15,16,31,63,127,128,191,240,254,255};
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0;
 status[0]=1;
 for(unsigned int alignment=0;alignment<2;alignment++)
 for(unsigned int base=0;base<16;base++)
 for(unsigned int digit=0;digit<8;digit++)
 for(unsigned int value=0;value<256;value++) {
  BcScore *score=(BcScore *)(0xff8100+alignment);
  volatile unsigned char *raw=(volatile unsigned char *)score;
  for(unsigned int i=0;i<35;i++)raw[i]=0xa5;
  raw[-1]=0x5a;raw[35]=0x5a;
  for(unsigned int i=0;i<8;i++)score->digits[i]=score->high[i]=bases[base];
  score->digits[digit]=value;
  __asm__ volatile ("" : : : "memory");
  unsigned char expected=value==bases[base],actual=same_score(score);
  if(actual!=expected || raw[-1]!=0x5a || raw[35]!=0x5a) {
   status[1]=alignment;status[2]=digit;status[3]=value;status[4]=actual;status[0]=0xdead;return;
  }
  for(unsigned int i=0;i<35;i++) {
   unsigned char want=i<16?bases[base]:0xa5;
   if(i==digit)want=value;
   if(raw[i]!=want){status[1]=i;status[0]=0xdead;return;}
  }
  checked++;
 }
 status[1]=checked;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-I'+str(ROOT/'inc'),'-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(objcopy),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(5000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==65536
print('PASS native 68000: 65536 score comparisons, even/odd alignment, all byte values at every digit, read-only records and sentinels preserved;',r.frames,'video frames')
