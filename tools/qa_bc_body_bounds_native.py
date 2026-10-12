#!/usr/bin/env python3
"""Compare the production party-body axis predicate against widened-sum math.

Runs a scratch native 68000 cartridge; does not change the playable ROM.
The deterministic 524,288-case sweep spans every 16-bit position and byte
radius, including zero radii, extreme endpoints and reversed intervals.
This is not the complete Cartesian product of the four input fields.
"""
from pathlib import Path
import sys, subprocess, struct
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from run_rom import Runner
out=root/'.local/bc-body-bounds-native';out.mkdir(exist_ok=True)
s=(root/'src/bc_world.c').read_text();helper=s[s.index('static inline unsigned char __attribute__((always_inline)) body_axis_far('):s.index('/* A conservative union rejects only actors outside every vulnerable body.')]
code=helper+r'''
static unsigned char __attribute__((noinline)) reference(unsigned short p,unsigned short lo,unsigned short hi,unsigned char r) {
 return (unsigned int)p+r <= lo || p >= (unsigned int)hi+r;
}
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 status[0]=1;
 for(unsigned int x=0;x<65536;x++) for(unsigned int j=0;j<8;j++) {
  unsigned char r=(x>>8)+j*37;
  unsigned short endpoints[8]={0,65535,x,x+r,x-r,x+r-1,x-r+1,(x*197u)^0xa5a5u};
  unsigned short lo=endpoints[j],hi=endpoints[7-j];
  unsigned char want=reference(x,lo,hi,r),got=body_axis_far(x,lo,hi,r);
  if(want!=got){status[1]=x;status[2]=j;status[3]=r;status[4]=lo;status[5]=hi;status[0]=0xdead;return;}
 }
 status[1]=524288;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nhalt:\n bra.s halt\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((root/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((root/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'rom.bin')
for _ in range(50000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
print('PASS native 68000: 524288 ordered-subtraction vs widened-sum comparisons; every coordinate, every radius, extreme and inverted endpoints;',r.frames,'frames')
