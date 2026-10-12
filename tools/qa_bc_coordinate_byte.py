#!/usr/bin/env python3
"""Exercise the production fixed-point integer-high byte reader in a native 68000 probe ROM.

The scratch cartridge replaces the reset entry and runs independent C reference
checks. It never modifies the playable release ROM.
"""
from pathlib import Path
import subprocess,struct
from run_rom import Runner,ROOT
out=ROOT/'.local/bc-coordinate-byte';out.mkdir(parents=True,exist_ok=True);cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
s=(ROOT/'src/bc_rules.c').read_text();helper=s[s.index('static __attribute__((always_inline)) inline unsigned char enemy_integer_high('):s.index('unsigned char bc_enemy_motion(')]
code=helper+r'''
void probe_main(void) {
 static const unsigned int positions[] = {0,1,0xffff,0xff0000,0xffffff,0x800000,0x7fffff,0xffff00,0xaa123456,0xff000000};
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0;
 status[0]=1;
 for(unsigned int p=0;p<10;p++) for(unsigned int v=0;v<65536;v++) {
  unsigned int *position=(unsigned int *)(0xff8100+(p&1)*10);
  volatile unsigned short *before=(volatile unsigned short *)((unsigned char *)position-2);
  volatile unsigned short *after=(volatile unsigned short *)((unsigned char *)position+4);
  *before=0xa55a; *after=0x5aa5;
  *position=positions[p];
  signed short velocity=(signed short)v;
  unsigned int expected=(positions[p]+velocity)&0xffffff;
  *position=expected | (v << 24);
  __asm__ volatile ("" : : : "memory");
  unsigned char high=enemy_integer_high(position);
  __asm__ volatile ("" : : : "memory");
  if(high != ((expected >> 16) & 255) || *position != (expected | (v << 24)) || *before!=0xa55a || *after!=0x5aa5) {
   status[1]=p;status[2]=v;status[3]=*position;status[4]=expected;status[0]=0xdead;return;
  }
  checked++;
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
assert r.u32('probe_status',4)==655360
print('PASS native 68000: 655360 coordinate byte reads, both word-aligned offsets, dirty top bytes and sentinels preserved;',r.frames,'video frames')
