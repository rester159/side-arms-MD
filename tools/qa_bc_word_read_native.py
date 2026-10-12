#!/usr/bin/env python3
"""Exercise the production source-word decoder on 68000 at both alignments."""
from pathlib import Path
import struct,subprocess
from run_rom import ROOT,Runner
out=ROOT/'.local/bc-word-read-native';out.mkdir(parents=True,exist_ok=True)
s=(ROOT/'src/bc_world.c').read_text();start=s.index('static unsigned short word(');decoder=s[start:s.index('\n}\n',start)+3]
main=r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 volatile unsigned char *storage=(volatile unsigned char *)0xff2000;
 unsigned int checks=0;status[0]=1;
 for(unsigned int alignment=0;alignment<2;alignment++) {
  for(unsigned int value=0;value<65536;value++) {
   for(unsigned i=0;i<6;i++)storage[i]=0xa5;
   storage[1+alignment]=value;storage[2+alignment]=value>>8;
   unsigned int got=word((const unsigned char *)storage+1+alignment);
   if(got!=value){status[1]=alignment;status[2]=value;status[3]=got;status[0]=0xdead;return;}
   for(unsigned i=0;i<6;i++) {
    unsigned char expected=i==1+alignment?value:i==2+alignment?value>>8:0xa5;
    if(storage[i]!=expected){status[1]=i;status[0]=0xdead;return;}
   }
   checks++;
  }
 }
 status[1]=checks;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(decoder+main)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O3','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(20000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==131072
print('PASS native 68000: all 65536 source words at both byte alignments; unsigned extension and source/sentinel bytes preserved;',r.frames,'video frames')
