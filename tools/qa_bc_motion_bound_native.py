#!/usr/bin/env python3
"""Compare production 68000 motion bounds with the original arithmetic at wrapped edges."""
from pathlib import Path
import argparse,struct,subprocess
from run_rom import ROOT,Runner
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=ROOT/'.local/bc-motion-bound-native')
out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
s=(ROOT/'src/bc_rules.c').read_text()
start=s.index('static unsigned char beam_axis(');end=s.index('/* $998A-',start)
source=s[start:end]
has_move="beam_move(" in source
prefix='#include "bc_rules.h"\n'+f"#define BC_PROBE_HAS_MOVE {int(has_move)}\n"
main=r"""
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 static const unsigned int origins[20]={0,1,255,256,0x10fff,0x11000,0xffefff,0xfff000,0xffffff,0xffff00,0x1000000,0xabffff00,0xff000000,0xffffffff,0x12345678,0x98765432,0x7fffffff,0x80000000,0xffff8000,0xff000100};
 unsigned int checks=0;status[0]=1;
 for(unsigned n=0;n<20;n++) for(unsigned v=0;v<65536;v++) {
  unsigned int p=origins[n],sum=p+((unsigned int)(signed short)v&0xffffff);
  unsigned int expected=sum&0xffffff;
  unsigned short bound=(unsigned short)((expected>>8)+16+(sum>>24));
#if BC_BEAM_STORAGE_ROTATE == 8
  p=(p<<8)|(p>>24);
#endif
#if BC_PROBE_HAS_MOVE
  unsigned int moved=p; beam_move(&moved,bc_beam_velocity((signed short)v));
#endif
  unsigned char actual=beam_axis(&p,bc_beam_velocity((signed short)v));
#if BC_PROBE_HAS_MOVE
  if(moved!=p){status[1]=n;status[2]=v;status[3]=moved;status[0]=0xdead;return;}
#endif
#if BC_BEAM_STORAGE_ROTATE == 8
  p=(p>>8)|(p<<24);
#endif
  if(p!=expected || actual!=(bound>=0x120)){status[1]=n;status[2]=v;status[3]=p;status[0]=0xdead;return;}
  checks++;
 }
 status[1]=checks;status[0]=0x600d;
}
"""
(out/'probe.c').write_text(prefix+source+main)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-I'+str(ROOT/'inc'),'-O3','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(20000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
assert r.u32('probe_status',4)==1310720
print('PASS native: 1310720 beam-axis cases, every signed velocity at 20 fractional/boundary/padded positions;',r.frames,'frames')

if has_move:print("PASS native: 1310720 position-only motion results also match original arithmetic")
