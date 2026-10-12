#!/usr/bin/env python3
"""Validate native little-endian word decoding with exact 16-bit offset wrap."""
from pathlib import Path
import struct,subprocess
from run_rom import ROOT,Runner
out=ROOT/'.local/bc-wrapped-word-native';out.mkdir(parents=True,exist_ok=True)
s=(ROOT/'src/bc_rules.c').read_text();start=s.index('static inline unsigned short enemy_word(')
decoder='typedef struct {const unsigned char *bytes;unsigned short origin;} BcEnemyData;\n'+s[start:s.index('\n}\n',start)+3]
main=r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 static const unsigned short origins[5]={0,1,0x4000,0x8001,0xffff};
 BcEnemyData data={(const unsigned char *)0x3c0000,0};
 unsigned int checks=0;status[0]=1;
 for(unsigned mode=0;mode<5;mode++){
  data.origin=origins[mode];
  for(unsigned int offset=0;offset<65536;offset++){
   unsigned short expected=((const unsigned short *)0x3a0000)[offset];
   unsigned short address=offset+data.origin;
   unsigned int actual=enemy_word(&data,address);
   if(actual!=expected){status[1]=mode;status[2]=offset;status[3]=actual;status[0]=0xdead;return;}
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
# A cyclic order-two De Bruijn sequence covers every possible source word.
sequence=[];digits=[0]*513
def db(t,period):
 if t>2:
  if 2%period==0:sequence.extend(digits[1:period+1])
 else:
  digits[t]=digits[t-period];db(t+1,period)
  for value in range(digits[t-period]+1,256):digits[t]=value;db(t+1,t)
db(1,1);assert len(sequence)==65536
words=[sequence[i]|(sequence[(i+1)&65535]<<8) for i in range(65536)]
assert len(set(words))==65536
rom[0x3a0000:0x3c0000]=b''.join(value.to_bytes(2,'big') for value in words)
rom[0x3c0000:0x3d0000]=bytes(sequence)
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(20000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==327680
print('PASS native 68000: 327680 wrapped source-word reads, all 65536 values/offsets and five origins;',r.frames,'video frames')
