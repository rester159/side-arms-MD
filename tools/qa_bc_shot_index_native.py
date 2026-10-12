#!/usr/bin/env python3
"""Compare native 68000 shot-index byte loads with the preceding masked-word implementation.

Builds a scratch probe cartridge; leaves the playable ROM unchanged.
"""
from pathlib import Path
import argparse,sys,subprocess,struct
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'tools'))
from run_rom import Runner
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,default=root/'.local/bc-shot-index-native')
out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
def extract(p):
 s=p.read_text()
 shared=s.find('#define ESI_NAME bc_shot_index')
 if shared >= 0:
  start=s.rfind('/* The shared builder emits',0,shared)
  end=s.index('#include "enemy_shot_index_impl.h"',shared)+len('#include "enemy_shot_index_impl.h"')
  if start < 0:raise ValueError('shared shot-index policy boundary missing')
  return s[start:end]+'\n'
 # Stop after the collector, excluding the independently templated query.
 start=s.rfind('static void',0,s.index(' shot_index_live('))
 public=s.index('\nvoid bc_shot_index(')
 end=s.index('\n}\n',public)+3
 return s[start:end]

# Independent pre-optimization reference, retaining masked 32-bit reads.
base=r'''
static void __attribute__((noinline)) reference_live(BcShotIndex *index,
    const BcBeam *b, unsigned char i)
{
    if ((b->flags & 1) || ((b->x | b->y) & 0xff0000)) return;
    unsigned char n = index->count++;
    index->slots[n] = i;
    index->x[n] = b->x >> 8; index->y[n] = b->y >> 8;
    unsigned char x = index->x[n], y = index->y[n];
    if (x < index->min_x) index->min_x = x;
    if (x > index->max_x) index->max_x = x;
    if (y < index->min_y) index->min_y = y;
    if (y > index->max_y) index->max_y = y;
    if (b->half_x > index->half_x) index->half_x = b->half_x;
    if (b->half_y > index->half_y) index->half_y = b->half_y;
}

void reference_index(BcShotIndex *index, const BcWeapons *weapons)
{
    index->count = 0;
    index->min_x = index->min_y = 255;
    index->max_x = index->max_y = index->half_x = index->half_y = 0;
    const BcShot *shot = weapons->shots;
    /* Preserve slot order while keeping the empty-slot scan compact. */
    for (unsigned char i = 0; i < 28; i += 2, shot += 2) {
        if (shot[0].body.state == 0x80) reference_live(index, &shot[0].body, i);
        if (shot[1].body.state == 0x80) reference_live(index, &shot[1].body, i + 1);
    }
}

'''
current=extract(root/'src/bc_rules.c')
code='#include "bc_rules.h"\n'+base+current+r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 BcWeapons *weapons=(BcWeapons *)0xff9000,*native=(BcWeapons *)0xffc000;
 BcShotIndex *want=(BcShotIndex *)0xffa000,*got=(BcShotIndex *)0xffa100;
 unsigned char *raw=(unsigned char *)weapons;
 for(unsigned short i=0;i<sizeof(*weapons);i++)raw[i]=0;
 status[0]=1;
 for(unsigned int board=0;board<4096;board++) {
  for(unsigned short i=0;i<30;i++) {
   BcBeam *b=&weapons->shots[i].body;
   unsigned int v=(board*131+i*1709);
   b->state=((v>>9)&3)==0?0:((v>>9)&3)==1?64:128;
   b->flags=(v>>3)&3;
   b->x=((v&255)<<24)|(((v&7)==0?(v>>8)&255:0)<<16)|((v&255)<<8)|((v>>4)&255);
   b->y=(((v>>3)&255)<<24)|(((v&15)==3?(v>>5)&255:0)<<16)|(((v>>4)&255)<<8)|(v&255);
   b->half_x=v>>2;b->half_y=v>>5;
  }
  for(unsigned short i=0;i<sizeof(*want);i++)((unsigned char *)want)[i]=((unsigned char *)got)[i]=0xa5;
  __asm__ volatile("" : : : "memory");
  unsigned char *saved=(unsigned char *)0xffb000,*native_raw=(unsigned char *)native;
  for(unsigned short i=0;i<sizeof(*weapons);i++)native_raw[i]=raw[i];
#if BC_BEAM_STORAGE_ROTATE == 8
  for(unsigned short i=0;i<30;i++) {
   BcBeam *b=&native->shots[i].body;
   b->x=(b->x<<8)|(b->x>>24);b->y=(b->y<<8)|(b->y>>24);
  }
#endif
  for(unsigned short i=0;i<sizeof(*weapons);i++)saved[i]=native_raw[i];
  ((unsigned char *)got)[-1]=0x5a;((unsigned char *)got)[sizeof(*got)]=0xa5;
  reference_index(want,weapons);bc_shot_index(got,native);
  for(unsigned short i=0;i<sizeof(*weapons);i++)if(saved[i]!=native_raw[i]) {
   status[1]=board;status[2]=i;status[0]=0xdead;return;
  }
  if(((unsigned char *)got)[-1]!=0x5a || ((unsigned char *)got)[sizeof(*got)]!=0xa5) {
   status[1]=board;status[2]=0xffff;status[0]=0xdead;return;
  }
  for(unsigned short i=0;i<sizeof(*want);i++)if(((unsigned char *)want)[i]!=((unsigned char *)got)[i]) {
   status[1]=board;status[2]=i;status[3]=((unsigned char *)want)[i];status[4]=((unsigned char *)got)[i];status[0]=0xdead;return;
  }
 }
 status[1]=4096;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nhalt:\n bra.s halt\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc';objcopy=cc.with_name('m68k-elf-objcopy')
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-I'+str(root/'inc'),'-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(objcopy),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((root/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((root/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'rom.bin')
for _ in range(15000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
print('PASS native 68000: 4096 complete shot-index comparisons, dirty top bytes, fractions, high-byte rejection, state/flag/half-size variation, weapon bytes and index sentinels unchanged;',r.frames,'video frames')
