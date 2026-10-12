#!/usr/bin/env python3
"""Native scratch benchmark: source 8.8 velocities versus pre-scaled long velocities.

Includes writes at three cadences. Does not change the game ABI or playable ROM.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import numpy as np
from run_rom import ROOT, Runner
from profile_genesis import instruction_profile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--baseline-source',type=Path,required=True,help='Archived bc_rules.c with signed16 source velocities')
a=p.parse_args();out=a.output;out.mkdir(parents=True,exist_ok=True)
rules=(a.baseline_source/'bc_rules.c').read_text()
start=rules.index('static __attribute__((always_inline)) inline void enemy_move_axis(')
move=rules[start:rules.index('\n}\n',start)+3]
assert 'signed short velocity' in move, 'baseline must use signed16 velocities'
source=r'''
typedef unsigned int u32;typedef signed int s32;typedef unsigned short u16;typedef signed short s16;
typedef struct {u32 x,y;s16 vx,vy;} Base;
typedef struct {u32 x,y;s32 vx,vy;} Wide;
'''+move+r'''
#define ATTR __attribute__((noinline,noclone,no_icf))
#define BASE(N) ATTR void base_##N(Base *p,unsigned changed,s16 vx,s16 vy) { \
 if(changed){p->vx=vx;p->vy=vy;} \
 if(p->vx)enemy_move_axis(&p->x,p->vx); \
 if(p->vy)enemy_move_axis(&p->y,p->vy); }
#define WIDE(N) ATTR void wide_##N(Wide *p,unsigned changed,s16 vx,s16 vy) { \
 if(changed){p->vx=(s32)vx*256;p->vy=(s32)vy*256;} \
 if(p->vx)p->x+=(u32)p->vx; \
 if(p->vy)p->y+=(u32)p->vy; }
BASE(1) BASE(5) BASE(20)
WIDE(1) WIDE(5) WIDE(20)
ATTR void encode_velocity(volatile s32 *destination,s32 value) {
 *destination=(s32)(s16)value*256;
}
void probe_main(void) {
 volatile u32 *status=(volatile u32 *)0xff8000;
 Base *base=(Base *)0xff2002;Wide *wide=(Wide *)0xff3002;
 volatile u16 *guard1=(volatile u16 *)0xff2000,*guard2=(volatile u16 *)0xff3000;
 void (*left[3])(Base*,unsigned,s16,s16)={base_1,base_5,base_20};
 void (*right[3])(Wide*,unsigned,s16,s16)={wide_1,wide_5,wide_20};
 static const unsigned periods[3]={1,5,20};u32 checks=0;
 status[0]=1;
 for(unsigned mode=0;mode<3;mode++){
  guard1[0]=guard2[0]=0xa55a;guard1[193]=guard2[257]=0x5aa5;
  for(unsigned i=0;i<32;i++){
   base[i].x=wide[i].x=(i&1)?0xffffff00u:0;
   base[i].y=wide[i].y=(i&2)?0xffffff00u:0;
   base[i].vx=base[i].vy=wide[i].vx=wide[i].vy=0;
  }
  for(unsigned tick=0,phase=0;tick<1000;tick++){
   unsigned changed=phase==0;if(++phase==periods[mode])phase=0;
   for(unsigned i=0;i<32;i++){
   s16 vx=(i&7)?(s16)(tick*257+i*1031):0;
   s16 vy=(i&3)?(s16)(tick*1031+i*257):0;
   left[mode](&base[i],changed,vx,vy);right[mode](&wide[i],changed,vx,vy);
   if(base[i].x!=wide[i].x||base[i].y!=wide[i].y||
      (s32)base[i].vx!=wide[i].vx/256||(s32)base[i].vy!=wide[i].vy/256||
      ((wide[i].x|wide[i].y|(u32)wide[i].vx|(u32)wide[i].vy)&255)){
    status[1]=mode;status[2]=tick;status[3]=i;status[0]=0xdead;return;
   }
   checks++;
  }}
  if(guard1[0]!=0xa55a||guard2[0]!=0xa55a||guard1[193]!=0x5aa5||guard2[257]!=0x5aa5){status[0]=0xdead;return;}
 }
 /* Setter wrapping must match assigning an arbitrary integer to signed16. */
 u32 exhaustive=0;
 for(unsigned i=0;i<65536;i++){
  volatile s32 *slot=(volatile s32 *)0xff8010;
  encode_velocity(slot,(s32)(i|0x7cde0000u));
  s32 expected=(i>=32768?(s32)i-65536:(s32)i)*256;
  if(*slot!=expected||((u32)*slot&255)){status[0]=0xdead;return;}
  exhaustive++;
 }
 status[1]=checks;status[2]=exhaustive;status[0]=0x600d;
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
assert r.u32('probe_status',4)==96000
assert r.u32('probe_status',8)==65536
hist=np.load(out/'cpu.npy');syms=[]
for line in symbols.splitlines():
 f=line.split()
 if len(f)>=3 and f[1] in ('t','T'):syms.append((int(f[0],16),f[2]))
syms.sort();costs={}
for i,(at,name) in enumerate(syms):
 end=syms[i+1][0] if i+1<len(syms) else 0x400000
 if name.startswith(('base_','wide_')):costs[name]=int(hist[at//2:end//2].sum())
assert len(costs)==6 and all(costs.values()),costs
report=dict(production_rom_sha256=digest,checks=96000,setter_velocity_values=65536,costs_core_ticks=costs,
 comparison=[dict(velocity_update_period=n,saved_percent=100*(1-costs[f'wide_{n}']/costs[f'base_{n}'])) for n in (1,5,20)],
 extra_bytes_per_enemy=4,scope='Native kernels only; no game-wide layout, AI getter cost, or gameplay speed claim',production_changed=False)
assert hashlib.sha256(production.read_bytes()).hexdigest()==digest
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
