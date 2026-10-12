#!/usr/bin/env python3
"""Exercise the production fixed-point integer-coordinate pair reader in a native 68000 probe ROM.

The scratch cartridge replaces the reset entry and runs independent C reference
checks. It never modifies the playable release ROM.
"""
import argparse
from pathlib import Path
import subprocess,struct
from run_rom import Runner,ROOT
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--segment',action='store_true',help='Check the segment simulation coordinate helper')
args=parser.parse_args()
out=ROOT/('.local/bc-segment-coordinate-probe' if args.segment else '.local/bc-coordinate-pair');out.mkdir(parents=True,exist_ok=True);cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
s=(ROOT/('src/bc_world.c' if args.segment else 'src/bc_actor_draw.c')).read_text()
name='segment_coordinates' if args.segment else 'screen_coordinates'
start=s.index('static inline __attribute__((always_inline)) void '+name+'(')
helper=s[start:s.index('\n}\n',start)+3].replace(name,'screen_coordinates')
code='#include "bc_world.h"\n'+helper+r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0; status[0]=1;
 for(unsigned int p=0;p<4;p++) for(unsigned int v=0;v<65536;v++) {
  BcEnemy *b=(BcEnemy *)(0xff8100+(p&1)*66);
  volatile unsigned short *before=(volatile unsigned short *)((unsigned char *)b-2);
  volatile unsigned short *after=(volatile unsigned short *)((unsigned char *)b+sizeof(*b));
  *before=0xa55a; *after=0x5aa5;
  unsigned int original_x=(v<<8)|((v*13+p)&255)|((v+p)<<24);
  unsigned int original_y=((65535-v)<<8)|((v*7+p)&255)|((v*3+p)<<24);
  b->x=original_x; b->y=original_y;
  __asm__ volatile ("" : : : "memory");
  signed short x,y;screen_coordinates(b,&x,&y);
  __asm__ volatile ("" : : : "memory");
  if(x!=(signed short)v || y!=(signed short)(65535-v) || b->x!=original_x || b->y!=original_y || *before!=0xa55a || *after!=0x5aa5) {
   status[1]=p;status[2]=v;status[3]=(unsigned short)x;status[4]=(unsigned short)y;status[0]=0xdead;return;
  }
  checked++;
 }
 status[1]=checked;status[0]=0x600d;
}
'''
if args.segment:
 code=code.replace('signed short x,y;', 'unsigned short x,y;').replace('(signed short)v', '(unsigned short)v').replace('(signed short)(65535-v)', '(unsigned short)(65535-v)')
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-I'+str(ROOT/'inc'),'-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(objcopy),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(3000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==262144
print('PASS native 68000: 262144 coordinate pair reads, both word-aligned offsets, dirty top bytes and sentinels preserved;',r.frames,'video frames')
