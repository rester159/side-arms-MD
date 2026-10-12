#!/usr/bin/env python3
"""Native 68000 comparison of production option-trail copy with byte reference."""
from pathlib import Path
import subprocess,struct
from run_rom import Runner,ROOT
out=ROOT/'.local/bc-trail-native';out.mkdir(parents=True,exist_ok=True)
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
s=(ROOT/'src/bc_rules.c').read_text();lo=s.index('void bc_weapons_record_position(');hi=s.index('/* Only live slots',lo)
code='#include "bc_rules.h"\n'+s[lo:hi]+r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0;status[0]=1;
 for(unsigned int p=0;p<2;p++) for(unsigned int v=0;v<8192;v++) {
  BcWeapons *w=(BcWeapons *)(0xff8100+p*1026);
  volatile unsigned char *area=(volatile unsigned char *)w;
  unsigned short offset=__builtin_offsetof(BcWeapons,trail);
  for(unsigned int i=offset-8;i<offset+24;i++)area[i]=(i*37+v*13+(v>>4))&255;
  unsigned char expected[16],before[8],after[8];
  for(unsigned int i=0;i<16;i++)expected[i]=w->trail[i];
  for(unsigned int i=0;i<8;i++){before[i]=area[offset-8+i];after[i]=area[offset+16+i];}
  for(unsigned int step=0;step<9;step++) {
   unsigned short x=v*17+step*29,y=v*31+step*11;
   for(unsigned int i=15;i>=2;i--)expected[i]=expected[i-2];
   expected[0]=x;expected[1]=y;
   bc_weapons_record_position(w,x,y);
   for(unsigned int i=0;i<16;i++)if(w->trail[i]!=expected[i]){
    status[1]=v;status[2]=step;status[3]=i;status[0]=0xdead;return;
   }
   for(unsigned int i=0;i<8;i++)if(area[offset-8+i]!=before[i] || area[offset+16+i]!=after[i]){
    status[1]=v;status[2]=step;status[3]=0x100+i;status[0]=0xdead;return;
   }
   checked++;
  }
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
for _ in range(12000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==147456
print('PASS native 68000: 147456 option-trail updates, both word alignments, nine-step history, low coordinate bytes, overlapping copy and neighboring bytes preserved;',r.frames,'video frames')
