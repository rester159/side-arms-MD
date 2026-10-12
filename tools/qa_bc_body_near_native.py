#!/usr/bin/env python3
"""Compare native player-body proximity against independent unsigned distances."""
from pathlib import Path
import sys, subprocess, struct, argparse
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from run_rom import Runner
out=root/'.local/bc-body-near-native';out.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--helper',choices=['body_near_inline','body_near_solo'],default='body_near_inline')
args=parser.parse_args()
s=(root/'src/bc_world.c').read_text()
helper=s[s.index('static inline unsigned char __attribute__((always_inline)) body_near_inline('):s.index('/* Ordered subtraction avoids widened sums')]
code='#include "bc_world.h"\n'+helper+r'''
static unsigned char __attribute__((noinline)) reference(unsigned short x,unsigned short y,unsigned short px,unsigned short py,unsigned char hx,unsigned char hy) {
 unsigned short dx=x>=px?x-px:px-x,dy=y>=py?y-py:py-y;
 return dx<(unsigned char)(hx+5) && dy<(unsigned char)(hy+8);
}
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 BcActor *a=(BcActor *)0xff9000; BcWorldPlayer *p=(BcWorldPlayer *)0xffa000;
 status[0]=1;
 for(unsigned int x=0;x<65536;x++) for(unsigned int j=0;j<16;j++) {
  unsigned char hx=(x>>8)+j*37,hy=(x>>4)+j*13;
  unsigned short y=x*197u,rx=(unsigned char)(hx+5),ry=(unsigned char)(hy+8);
  unsigned short px=j&4?(j&1?0:65535):x+(j&1?rx:-rx)+(j&2?1:-1);
  unsigned short py=j&8?y:y+(j&1?ry:-ry)+(j&2?1:-1);
  a->body.x=(x<<16)|(x^0xa5a5);a->body.y=((unsigned int)y<<16)|(x^0x5a5a);
  a->half_x=hx;a->half_y=hy;
  p->x=((unsigned int)px<<8)|((x&255)<<24)|(j*17);
  p->y=((unsigned int)py<<8)|((x&255)<<24)|(j*13);
  unsigned char want=reference(x,y,px,py,hx,hy),got=body_near_inline(a,p);
  if(want!=got){status[1]=x;status[2]=j;status[3]=want;status[4]=got;status[0]=0xdead;return;}
 }
 status[1]=1048576;status[0]=0x600d;
}
'''
code=code.replace('got=body_near_inline(a,p)', 'got='+args.helper+'(a,p)')
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nhalt:\n bra.s halt\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-I'+str(root/'inc'),'-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((root/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((root/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'rom.bin')
for _ in range(50000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
print('PASS native 68000: 1048576 body proximity comparisons; wrapped radii, unsigned endpoints, source fractions and padding;',r.frames,'frames')
