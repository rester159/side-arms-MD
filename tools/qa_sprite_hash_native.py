#!/usr/bin/env python3
"""Check the production sprite-cache bucket address for every key on 68000."""
from pathlib import Path
import struct,subprocess
from run_rom import ROOT,Runner
out=ROOT/'.local/sprite-hash-native';out.mkdir(parents=True,exist_ok=True)
s=(ROOT/'src/sprites.c').read_text()
source=s[s.index('typedef struct { u16 key, attr;'):s.index('static Cache small, big;')]
prefix='#include <stdint.h>\ntypedef uint16_t u16;typedef int16_t s16;typedef uint8_t u8;\n#define SMALL_SLOTS 64\n'
main=r"""
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int origins[3]={0x1000,0xff2002,0xffe000};
 unsigned int checks=0;status[0]=1;
 for(unsigned n=0;n<3;n++) for(unsigned key=0;key<65536;key++) {
  unsigned int expected=origins[n]+(((key^(key>>8))&127)*8);
  unsigned int actual=(unsigned int)fast_entry((Cache *)origins[n],(u16)key);
  if(actual!=expected){status[1]=key;status[2]=actual;status[3]=expected;status[0]=0xdead;return;}
  checks++;
 }
 status[1]=checks;status[0]=0x600d;
}
"""
(out/'probe.c').write_text(prefix+source+main)
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
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
assert r.u32('probe_status',4)==196608
print('PASS native 68000: 196608 exact cache addresses, all 65536 keys at three origins;',r.frames,'frames')
