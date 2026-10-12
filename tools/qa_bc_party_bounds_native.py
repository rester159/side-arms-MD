#!/usr/bin/env python3
"""Check the production paired body bounds predicate on native 68000.

1,048,576 deterministic cases cover both axes, every 16-bit coordinate,
byte-wrapped radii, zero radii, extreme and inverted endpoints. Half of the
cases force X to be near so the Y predicate is exercised independently.
Runs a scratch cartridge and leaves the production ROM unchanged.
"""
from pathlib import Path
import sys, subprocess, struct
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from run_rom import Runner
out=root/'.local/bc-party-bounds-native';out.mkdir(exist_ok=True)
s=(root/'src/bc_world.c').read_text();helper=s[s.index('static inline unsigned char __attribute__((always_inline)) body_axis_far('):s.index('/* Used after body rejection;')]
code='#include \"bc_world.h\"\n'+helper+r'''
static unsigned char __attribute__((noinline)) reference(unsigned short p,unsigned short lo,unsigned short hi,unsigned char r) {
 return (unsigned int)p+r <= lo || p >= (unsigned int)hi+r;
}
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 status[0]=1;
 for(unsigned int x=0;x<65536;x++) for(unsigned int j=0;j<16;j++) {
  unsigned char r=(x>>8)+j*37;
  unsigned short endpoints[8]={0,65535,x,x+r,x-r,x+r-1,x-r+1,(x*197u)^0xa5a5u};
  unsigned short lo=endpoints[j&7],hi=endpoints[(7-j)&7];
  BcActor a={0};BcParty party={0};
  a.body.x=x<<16;a.body.y=((x*197u)&65535)<<16;
  a.half_x=r-5;a.half_y=((x+j*71)&255)-8;
  party.body_min_x=lo;party.body_max_x=hi;
  party.body_min_y=endpoints[(j+2)&7];party.body_max_y=endpoints[(j+5)&7];
  if(j>=8){a.half_x=252;lo=hi=x;party.body_min_x=party.body_max_x=x;}
  unsigned char want=reference(x,lo,hi,(unsigned char)(a.half_x+5)) || reference(a.body.y>>16,party.body_min_y,party.body_max_y,(unsigned char)(a.half_y+8));
  unsigned char got=party_bodies_far(&a,&party);
  if(want!=got){status[1]=x;status[2]=j;status[3]=r;status[4]=lo;status[5]=hi;status[0]=0xdead;return;}
 }
 status[1]=1048576;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nhalt:\n bra.s halt\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-I'+str(root/'inc'),'-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((root/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((root/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'rom.bin')
for _ in range(50000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
print('PASS native 68000: 1048576 paired bounds vs widened-sum comparisons; every coordinate, every radius, extreme and inverted endpoints;',r.frames,'frames')
