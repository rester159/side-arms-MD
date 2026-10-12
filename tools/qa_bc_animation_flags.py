#!/usr/bin/env python3
"""Exercise the production enemy animation attribute updates in a native 68000 probe ROM.

The scratch cartridge replaces the reset entry and runs independent C reference
checks. It never modifies the playable release ROM.
"""
from pathlib import Path
import subprocess,struct
from run_rom import Runner,ROOT
out=ROOT/'.local/bc-animation-flags';out.mkdir(parents=True,exist_ok=True);cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
code='#include "bc_rules.h"\n'+r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0; status[0]=1;
 for(unsigned int f=0;f<4;f++) for(unsigned int a=0;a<65536;a++) {
  volatile unsigned short *record=(volatile unsigned short *)0xff8100;
  record[0]=0xa55a;record[1]=a;record[2]=0x5aa5;
  unsigned char frame=(f<<6)|(a&63);
  unsigned short expected=(a&0x77ff)|((frame&128)<<8)|((frame&64)<<5);
  BcEnemy enemy = {0};
  unsigned char bytes[2] = {1,frame}, count=7;
  BcEnemyData data = {bytes,0};
  enemy.state=0x40; enemy.timer=1; enemy.sprite_base=0x200;
  enemy.attributes=record[1];
  unsigned char result=bc_enemy_motion(&enemy,&data,&count);
  record[1]=enemy.attributes;
  if(result!=2 || count!=7 || enemy.animation!=2 || enemy.timer!=1 ||
     enemy.sprite!=(frame==255 ? 255 : 0x200+(frame&63))) {
   status[1]=a;status[2]=frame;status[0]=0xdead;return;
  }
  __asm__ volatile ("" : : : "memory");
  if(record[1]!=expected || record[0]!=0xa55a || record[2]!=0x5aa5) {
   status[1]=a;status[2]=frame;status[3]=record[1];status[4]=expected;status[0]=0xdead;return;
  }
  checked++;
 }
 status[1]=checked;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-I'+str(ROOT/'inc'),'-ffunction-sections','-fdata-sections','-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000,--gc-sections',str(out/'start.s'),str(out/'probe.c'),str(ROOT/'src/bc_rules.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(objcopy),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(20000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==262144
print('PASS native 68000: 262144 animation flip writes; all attribute words and four flip combinations; low byte and other flags preserved; sprite, timer, animation pointer and return/count outputs match;',r.frames,'video frames')
