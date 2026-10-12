#!/usr/bin/env python3
"""Native feasibility benchmark for word-aligned BC integer coordinates.

Scratch cartridge only. A 16.16 storage word holds the same 16.8 value
shifted left eight bits; its low byte stays zero. No precision is added/lost.
Repeated reads model separate consumers, not a claim about whole-game speed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from run_rom import ROOT, Runner
from profile_genesis import instruction_profile
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--baseline-source',type=Path,required=True,help='Archived original-layout bc_rules.c and bc_actor_draw.c; current game uses aligned coordinates')
a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True)
rules=(a.baseline_source/'bc_rules.c').read_text()
assert 'clr.b %0' in rules, 'baseline must use original 24-bit movement'
start=rules.index('static __attribute__((always_inline)) inline void enemy_move_axis(')
move=rules[start:rules.index('\n}\n',start)+3]
draw=(a.baseline_source/'bc_actor_draw.c').read_text()
assert 'movep.w 1(%2)' in draw, 'baseline must use original coordinate reader'
start=draw.index('static inline __attribute__((always_inline)) void screen_coordinates(')
read=draw[start:draw.index('\n}\n',start)+3]
source=r'''
typedef unsigned int u32;typedef unsigned short u16;typedef signed short s16;
typedef struct {u32 x,y;s16 vx,vy;} Point;
typedef Point BcEnemy;
'''+move+'\n'+read+r'''
typedef u16 __attribute__((may_alias)) Word;
static inline void aligned_move(u32 *position,s16 velocity) {
 __asm__("add.l %1,%0" : "+m"(*position) : "d"((int)velocity*256) : "cc");
}
static inline void aligned_read(const Point *p,s16 *x,s16 *y) {
 *x=*(const Word *)&p->x;*y=*(const Word *)&p->y;
}
#define KERNEL(NAME,N,MOVE,READ) \
__attribute__((noinline)) u32 NAME(Point *p) { \
 if(p->vx)MOVE(&p->x,p->vx);if(p->vy)MOVE(&p->y,p->vy); \
 u32 result=0;for(unsigned i=0;i<N;i++){s16 x,y; \
 __asm__ volatile("" ::: "memory");READ(p,&x,&y); \
 result+=(u16)x+((u32)(u16)y<<1); }return result; }
KERNEL(base0,0,enemy_move_axis,screen_coordinates)
KERNEL(base1,1,enemy_move_axis,screen_coordinates)
KERNEL(base2,2,enemy_move_axis,screen_coordinates)
KERNEL(base4,4,enemy_move_axis,screen_coordinates)
KERNEL(aligned0,0,aligned_move,aligned_read)
KERNEL(aligned1,1,aligned_move,aligned_read)
KERNEL(aligned2,2,aligned_move,aligned_read)
KERNEL(aligned4,4,aligned_move,aligned_read)
static u32 random_word(u32 *seed){u32 v=*seed;v^=v<<13;v^=v>>17;v^=v<<5;*seed=v;return v;}
void probe_main(void) {
 volatile u32 *status=(volatile u32*)0xff8000;
 Point *base=(Point*)0xff2002,*aligned=(Point*)0xff3002;
 volatile u16 *guard1=(volatile u16*)0xff2000,*guard2=(volatile u16*)0xff3000;
 u32 checks=0,seed=0x571b,random_changes=0,previous=0;status[0]=1;
 u32 (*left[4])(Point*)={base0,base1,base2,base4};
 u32 (*right[4])(Point*)={aligned0,aligned1,aligned2,aligned4};
 static const s16 velocities[8]={0,1,-1,256,-256,32767,-32768,511};
 for(unsigned mode=0;mode<4;mode++){
  guard1[0]=guard2[0]=0xa55a;guard1[193]=guard2[193]=0x5aa5;
  for(unsigned i=0;i<32;i++){
   base[i].x=i<8?(i&1?0xffffff:0):random_word(&seed)&0xffffff;
   base[i].y=i<8?(i&2?0xffffff:0):random_word(&seed)&0xffffff;
   if(i>=8){if(base[i].x!=previous)random_changes++;previous=base[i].x;}
   base[i].vx=velocities[i&7];base[i].vy=velocities[(i+3)&7];
   aligned[i]=base[i];aligned[i].x<<=8;aligned[i].y<<=8;
  }
  for(unsigned tick=0;tick<1000;tick++)for(unsigned i=0;i<32;i++){
   u32 a=left[mode](&base[i]),b=right[mode](&aligned[i]);
   if(a!=b||base[i].x!=(aligned[i].x>>8)||base[i].y!=(aligned[i].y>>8)||
      ((aligned[i].x|aligned[i].y)&255)){
    status[1]=mode;status[2]=tick;status[3]=i;status[4]=a;status[5]=b;status[0]=0xdead;return;
   }
   checks++;
  }
  if(guard1[0]!=0xa55a||guard2[0]!=0xa55a||guard1[193]!=0x5aa5||guard2[193]!=0x5aa5){status[0]=0xdead;return;}
 }
 /* Exhaust all signed 16-bit velocities at four wrapping boundaries. */
 u32 exhaustive=0;
 for(u32 bits=0;bits<65536;bits++)for(unsigned edge=0;edge<4;edge++){
  static const u32 edges[4]={0,255,0xffff00,0xffffff};
  u32 original=edges[edge],shifted=original<<8;
  enemy_move_axis(&original,(s16)bits);aligned_move(&shifted,(s16)bits);
  if(original!=(shifted>>8)||(shifted&255)){status[0]=0xdead;return;}
  exhaustive++;
 }
 status[1]=checks;status[2]=random_changes;status[3]=seed;status[4]=exhaustive;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(source)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O3','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
production=ROOT/'out/release/rom.bin';digest=hashlib.sha256(production.read_bytes()).hexdigest()
rom=bytearray(production.read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom)
symbols=subprocess.check_output([str(cc.with_name('m68k-elf-nm')),'-n',str(out/'probe.elf')],text=True)
(out/'symbol.txt').write_text(symbols+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
with instruction_profile(r,out/'cpu'):
 for _ in range(20000):
  r.run(1)
  if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
assert r.u32('probe_status',4)==128000
assert r.u32('probe_status',8)==96, "PRNG must advance in writable RAM"
assert r.u32('probe_status',16)==262144
# Histogram addresses belong to the scratch ELF, not the release symbol map.
import numpy as np
hist=np.load(out/'cpu.npy');syms=[]
for line in symbols.splitlines():
 f=line.split()
 if len(f)>=3 and f[1] in ('t','T'):syms.append((int(f[0],16),f[2]))
syms.sort();costs={}
for i,(at,name) in enumerate(syms):
 end=syms[i+1][0] if i+1<len(syms) else 0x400000
 if name.startswith(('base','aligned')):costs[name]=int(hist[at//2:end//2].sum())
assert all(name in costs for name in ('base0','base1','base2','base4','aligned0','aligned1','aligned2','aligned4')),costs
report=dict(production_rom_sha256=digest,checks=128000,exhaustive_velocity_checks=r.u32('probe_status',16),random_coordinate_changes=r.u32('probe_status',8),costs_core_ticks=costs,
 comparison=[dict(read_pairs=n,base=costs[f'base{n}'],aligned=costs[f'aligned{n}'],
 saved_percent=100*(1-costs[f'aligned{n}']/costs[f'base{n}'])) for n in (0,1,2,4)],
 scope='Native microbenchmark only; no game-wide layout conversion, AI validation or gameplay speed claim',production_changed=False)
assert hashlib.sha256(production.read_bytes()).hexdigest()==digest
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
