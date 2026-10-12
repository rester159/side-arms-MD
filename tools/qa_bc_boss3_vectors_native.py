#!/usr/bin/env python3
"""Compare production native homing-shot preparation with the source-read baseline."""
import argparse,struct,subprocess
from pathlib import Path
from run_rom import ROOT,Runner
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
out=ROOT/'.local/bc-boss3-vector-probe';out.mkdir(exist_ok=True)
s=(ROOT/'src/bc_world.c').read_text();old=a.baseline.read_text()
def between(text,start,end):return text[text.index(start):text.index(end,text.index(start))]
word=between(s,'static unsigned short word(','/* $8137-')
binding=between(s,'static const BcActorStepData *segment_data;','static void __attribute__((noinline)) segment_prepare_due(')
start='static void __attribute__((noinline)) boss_three_prepare('
end='static void __attribute__((noinline)) terrain_cycle_prepare('
helper_start='static inline __attribute__((always_inline)) void boss_three_homing_prepare('
helper=between(s,helper_start,start) if helper_start in s else ''
actual=helper+between(s,start,end);reference=between(old,start,end).replace('boss_three_prepare','reference_prepare')
syms={v[2].split('.lto_priv.')[0]:int(v[0],16)for line in (ROOT/'out/release/symbol.txt').read_text().splitlines() if len(v:=line.split())>=3}
rom=(ROOT/'out/release/rom.bin').read_bytes();table=syms['bc_boss3_native_vectors'];components=0
for i,round_ in enumerate((3,9)):
 at=table+i*646;source,origin=struct.unpack_from('>IH',rom,at)
 assert source==syms[f'bc_round{round_}_code'] and origin==0x4000
 for speed in range(0,10,2):
  vector=struct.unpack_from('<H',rom,source+0x8262+speed-origin)[0]
  for direction in range(16):
   for axis in range(2):
    expected=struct.unpack_from('<h',rom,source+vector+direction*4+axis*2-origin)[0]*256
    got=struct.unpack_from('>i',rom,at+6+((speed//2)*32+direction*2+axis)*4)[0]
    assert got==expected;components+=1
code='''#include "bc_world.h"
#include "bc_round_data.h"
#include <stddef.h>
static volatile unsigned int *status=(volatile unsigned int *)0xff8000;
void *memcpy(void *d,const void *s,size_t n){unsigned char *a=d;const unsigned char *b=s;while(n--)*a++=*b++;return d;}
void *memset(void *d,int v,size_t n){unsigned char *a=d;while(n--)*a++=v;return d;}
signed short bc_actor_spawn_bullet(BcActor *a,unsigned char p,unsigned char d,const BcEnemyData *b,unsigned short t,unsigned short s,unsigned short v){status[0]=0xdead;return -1;}
void bc_actor_common_into(BcActorEvent *e,BcActor *a,BcWorldPlayer *p,const BcEnemyData *d,unsigned char *c){status[0]=0xdead;}
'''+word+binding+reference+actual+r'''
void probe_main(void){
 _Static_assert(sizeof(BcBoss3NativeVectors)==646,"ROM table layout");
 BcActor actual[32],expected[32];BcWorldPlayer player;BcActorStepData data,copy;
 BcActorStepEvent event;unsigned char count=0;unsigned int checked=0;
 status[0]=1;
 for(unsigned int round=0;round<2;round++){
  memset(&data,0,sizeof(data));data.round=round?8:2;
  data.data=bc_boss3_native_vectors[round].source;copy=data;
  for(unsigned int binding=0;binding<3;binding++){
   bc_actor_bind_segments(binding==1?0:&data);
   const BcActorStepData *source=binding==2?&copy:&data;
   for(unsigned int speed=0;speed<11;speed++)
   for(unsigned int direction=0;direction<18;direction++)
   for(unsigned int phase=0;phase<3;phase++)
   for(unsigned int wait=0;wait<3;wait++)
   for(unsigned int target=0;target<3;target++){
    memset(actual,0,sizeof(BcActor));
    actual[0].routine=0xadcf+(round?0x527:0);actual[0].speed=speed;
    actual[0].direction=direction;actual[0].phase=phase;actual[0].wait=wait;
    bc_enemy_set_x(&actual[0].body,182);bc_enemy_set_y(&actual[0].body,100);
    player.y=(target==0?0:target==1?128:255)<<8;
    expected[0]=actual[0];
    reference_prepare(expected,0,&player,source,&count,&event);
    boss_three_prepare(actual,0,&player,source,&count,&event);
    for(unsigned int j=0;j<sizeof(BcActor);j++)if(((unsigned char*)actual)[j]!=((unsigned char*)expected)[j]){
     status[1]=checked;status[2]=j;status[3]=speed;status[4]=direction;status[0]=0xdead;return;
    }
    if(status[0]==0xdead)return;
    checked++;
   }
  }
 }
 status[1]=checked;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(code)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-ffunction-sections','-fdata-sections','-I'+str(ROOT/'inc'),'-Wl,--gc-sections,-Ttext=0x3e0000,--section-start=.bss=0xff9000',f'-Wl,--defsym=bc_boss3_native_vectors={table}',str(out/'start.s'),str(out/'probe.c'),str(ROOT/'src/bc_rules.c'),'-lgcc','-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
probe=(out/'probe.bin').read_bytes();assert len(probe)<0x20000
rom=bytearray(rom);rom[0x3e0000:0x3e0000+len(probe)]=probe;struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom);(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(5000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==32076,r.u32('probe_status',4)
print(f'PASS: {components} native ROM components; 32076 native preparation comparisons, rounds3/9, bound/unbound/other-object fallback, speed/direction bounds, phase/wait wraps and aiming')
