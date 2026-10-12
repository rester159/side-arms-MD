#!/usr/bin/env python3
"""Check hardware flip submissions through the production 68000 projectile renderer."""
from pathlib import Path
import struct
import argparse
import subprocess
from run_rom import ROOT, Runner
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--players', type=int, choices=(1, 2, 3, 4), default=1)
parser.add_argument('--output', type=Path)
args = parser.parse_args()
out = args.output or ROOT/'.local/bc-projectile-bits-native'
out.mkdir(parents=True, exist_ok=True)
cc = Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
(out/'draw.c').write_text((ROOT/'src/bc_projectile_draw.c').read_text())
(out/'sprites.h').write_text("typedef signed short s16;\nvoid spr_bc_bits16(unsigned short,signed short,signed short,unsigned short);\nvoid spr_bc_straight3(signed short,signed short,unsigned char,unsigned char);\n")
(out/'game.h').write_text("unsigned short game_player_limit(void);\n")
(out/'probe.c').write_text(r'''
#include "bc_projectile_art.h"
#define submitted (*(volatile unsigned short *)0xff8040)
#define bits (*(volatile unsigned short *)0xff8042)
#define drawn_x (*(volatile unsigned short *)0xff8044)
#define drawn_key (*(volatile unsigned short *)0xff8048)
#define drawn_y (*(volatile unsigned short *)0xff8046)
#if BC_BEAM_STORAGE_ROTATE == 8
#define RAW_X ((0xabc12345u<<8)|(0xabc12345u>>24))
#define RAW_Y ((0x98765432u<<8)|(0x98765432u>>24))
#else
#define RAW_X 0xabc12345u
#define RAW_Y 0x98765432u
#endif
unsigned short game_player_limit(void) { return 1; }
void spr_bc_bits16(unsigned short key, signed short x, signed short y, unsigned short v) {
 drawn_key=key;drawn_x=x;drawn_y=y;submitted++;bits=v;
}
void spr_bc_straight3(signed short x,signed short y,unsigned char f,unsigned char a) {
 (void)x;(void)y;(void)f;(void)a;submitted=0xdead;
}
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 BcWeapons *w=(BcWeapons *)0xff8100;
 for(unsigned int i=0;i<sizeof(*w);i++)((unsigned char *)w)[i]=0;
 BcBeam *b=&w->shots[0].body;
 b->state=0x80;b->x=RAW_X;b->y=RAW_Y;
 unsigned short frames[10]={0x1b8,0x1bc,0x1be,0x1c0,0x1e0,0x1d4,0x1aa,0x1b4,0x1d6,0xffff};
 unsigned int checks=0;status[0]=1;
 for(unsigned int k=0;k<10;k++)for(unsigned int v=0;v<65536;v++) {
  b->sprite=frames[k];b->attributes=v;b->facing=(v&4)!=0;
  submitted=0;bits=0xffff;
  unsigned char missing=bc_projectiles_draw(w,0,0);
  unsigned int expected=0;
  if(v&0x800)expected|=0x800;
  if(v&0x8000)expected|=0x1000;
  if(k>=1 && k<=3)expected=0;
  unsigned short expected_key[10]={0x4016, (unsigned short)(0x4012+((v&4)?3:0)), (unsigned short)(0x4011+((v&4)?3:0)), (unsigned short)(0x4010+((v&4)?3:0)),0x281c,0x281c,0x3999,0x408f,0x281d,0};
  if((k!=9 && (drawn_key!=expected_key[k] || submitted!=1 || bits!=expected || missing || drawn_x!=(unsigned short)((signed short)(0xabc12345u>>8)-8) || drawn_y!=(unsigned short)((signed short)(0x98765432u>>8)-8))) ||
     (k==9 && (submitted || missing!=1)) ||
     b->attributes!=v || b->x!=RAW_X || b->y!=RAW_Y) {
   status[1]=v;status[2]=bits;status[3]=expected;status[0]=0xdead;return;
  }
  checks++;
 }
 status[1]=checks;status[0]=0x600d;
}
''')
(out/'probe.c').write_text((out/'probe.c').read_text().replace(
    'unsigned short game_player_limit(void) { return 1; }',
    'unsigned short game_player_limit(void) { return %d; }' % args.players))
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-I'+str(out),'-I'+str(ROOT/'inc'),'-O2','-nostdlib',
 '-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),
 str(out/'probe.c'),str(out/'draw.c'),str(ROOT/'src/bc_projectile_art.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes())
rom.extend(bytes(0x400000-len(rom)))
raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw
struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(20000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==655360
print('PASS %dP: 655360 native renderer cases, exact artwork keys, SAT flip bits and pixel coordinates, sampled projectile frames, missing-art handling and unchanged inputs' % args.players)
