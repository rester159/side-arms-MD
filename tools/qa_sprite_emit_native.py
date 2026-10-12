#!/usr/bin/env python3
"""Check actual production SAT emission on 68000 against independent word results."""
from pathlib import Path
import struct,subprocess
from run_rom import ROOT,Runner
out=ROOT/'.local/sprite-emit-native';out.mkdir(parents=True,exist_ok=True)
s=(ROOT/'src/sprites.c').read_text()
start=s.index('static inline u16 sprite_flip_bits(')
end=s.index('\nvoid spr_16(',start)
source=s[start:end]
prefix='''#include <stdint.h>
typedef uint16_t u16;typedef int16_t s16;typedef uint8_t u8;
#define MAX_SPR 80
#define vdpSpriteCache (*(u16 (*)[80][4])0xff2002)
#define count (*(volatile u16 *)0xff1000)
'''
main=r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 volatile u16 *table=(volatile u16 *)0xff2002;
 volatile u16 *guard=(volatile u16 *)0xff2000;
 unsigned int checks=0;status[0]=1;
 for(unsigned i=0;i<322;i++)guard[i]=0xa55a;
 for(unsigned flags=0;flags<256;flags++) for(unsigned n=0;n<80;n++) {
  u16 x=(u16)(flags*317+n*1031),y=(u16)(flags*727+n*2039);
  u16 attr=(u16)(flags*539+n*131),size=(u16)((flags&15)<<8);
  count=n;emit(attr,(s16)x,(s16)y,size,flags);
  u16 expected[4]={(u16)(y+128),(u16)(size|(n+1)),
                  (u16)(attr|((flags&3)<<11)),(u16)(x+128)};
  if(count!=n+1){status[0]=0xdead;status[1]=1;return;}
  for(unsigned i=0;i<4;i++) if(table[n*4+i]!=expected[i]) {
   status[1]=n;status[2]=flags;status[3]=i;status[4]=table[n*4+i];status[5]=expected[i];status[0]=0xdead;return;
  }
  // Every non-target word stays untouched, including word-aligned guards.
  for(unsigned i=0;i<322;i++) if((i<1+n*4||i>=1+n*4+4)&&guard[i]!=0xa55a) {
   status[1]=i;status[0]=0xdead;return;
  }
  for(unsigned i=0;i<4;i++)table[n*4+i]=0xa55a;
  checks++;
 }
 status[1]=checks;status[0]=0x600d;
}
'''
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
assert r.u32('probe_status',4)==20480
print('PASS native 68000: 20480 SAT emissions, all flags/slots, wrapping coordinates, exact count/size/link/attribute/position and full-table sentinels;',r.frames,'frames')
