#!/usr/bin/env python3
"""Native feasibility probe for shadow-backed wheel cell copies.

Uses actual wheel map identities with deterministic synthetic cell words. This
checks the native copy mechanism and its CPU cost, not game initialization,
slot invalidation, DMA scheduling, allocation or actual rendered game pixels.
The playable ROM is never modified.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import random
import re
import struct
import subprocess
from run_rom import ROOT, Runner
from profile_genesis import instruction_profile

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--movem',action='store_true',help='Use multi-register copies')
args=parser.parse_args()
out=ROOT/('.local/wheel-copy-native-movem' if args.movem else '.local/wheel-copy-native');out.mkdir(parents=True,exist_ok=True)
source=(ROOT/'src/gen/boss_data.c').read_text()

def plan(before,after):
    sources={key:i for i,key in enumerate(before) if key is not None}
    for i,key in enumerate(before):
        if key is not None and key==after[i]:sources[key]=i
    pending={i:sources[k] for i,k in enumerate(after) if k is not None and k!=before[i]}
    moves=[];scratch=len(before)
    while pending:
        used=set(pending.values());safe=next((d for d in pending if d not in used),None)
        if safe is not None:moves.append((pending.pop(safe),safe))
        else:
            assert scratch not in used
            dst=next(iter(pending));moves.append((dst,scratch))
            pending={d:scratch if s==dst else s for d,s in pending.items()}
    return moves

prefix='''typedef unsigned char u8; typedef unsigned short u16; typedef signed short s16;
typedef struct {u16 cx,cy,slots; const u8 *layout; const u16 *pixels; const u16 *plans[9];u16 counts[9];} Wheel;
'''
parts=[prefix];wheels=[];rng=random.Random(0x68000)
for name,body in re.findall(r'static const u16 (wheel\w+)_maps\[\d+\] = \{(.*?)\};',source,re.S):
    words=[int(x,16)&0xcfff for x in re.findall(r'0x[0-9A-Fa-f]+',body)];assert len(words)==264
    header=re.search(r'static const BgFrames '+name+r'_frames = \{ (\d+), (\d+), (\d+),',source)
    cx,cy=map(int,header.groups()[1:]);frames=[words[i*88:(i+1)*88] for i in range(3)]
    keys=sorted(set(words));ids={k:i for i,k in enumerate(keys)};assert len(keys)<255
    missing=[sorted(set(keys)-set(f)) for f in frames];cap=max(map(len,missing))
    states=[f+m+[None]*(cap-len(m)) for f,m in zip(frames,missing)]
    layout=[255 if k is None else ids[k] for state in states for k in state]
    pixels=[0 if rng.randrange(7)==0 else rng.randrange(65536) for _ in range(len(keys)*16)]
    parts.append(f'static const u8 {name}_layout[]={{'+','.join(map(str,layout))+'};')
    parts.append(f'static const u16 {name}_pixels[]={{'+','.join(map(str,pixels))+'};')
    def address(slot):
        if slot>=88:return 0x8000+(slot-88)*32
        x,y=slot%11,slot//11
        return (((cy+y)&7)<<9)|(((cx+x)&15)<<3)
    names=[];counts=[]
    for old in range(3):
        for new in range(3):
            moves=plan(states[old],states[new]);counts.append(len(moves));label=f'{name}_p{old}{new}';names.append(label)
            values=[address(i) for pair in moves for i in pair]
            parts.append(f'static const u16 {label}[]={{'+(','.join(map(str,values)) if values else '0')+'};')
    parts.append(f'static const Wheel {name}={{ {cx},{cy},{88+cap},{name}_layout,{name}_pixels,'+'{'+','.join(names)+'},{'+','.join(map(str,counts))+'}};')
    wheels.append({'name':name,'cache_cells':cap,'copy_counts':counts})
parts.append('static const Wheel * const wheels[]={'+','.join('&'+w['name'] for w in wheels)+'};')
# Four source/destination stride combinations. Buffers are word-aligned.
def block(ss,ds):
    if args.movem:
        instructions=[]
        regs=['%%d0-%%d1','%%d2-%%d3','%%d4-%%d5','%%d6/%%a2']
        if ss==8:instructions.append('movem.l 0(%0),%%d0-%%d6/%%a2')
        else:
            for row in range(4):instructions.append(f'movem.l {row*ss}(%0),{regs[row]}')
        if ds==8:instructions.append('movem.l %%d0-%%d6/%%a2,0(%1)')
        else:
            for row in range(4):instructions.append(f'movem.l {regs[row]},{row*ds}(%1)')
        return '__asm__ volatile ("'+'\\n\\t'.join(instructions)+'" : : "a"(src),"a"(dst) : "d0","d1","d2","d3","d4","d5","d6","a2","memory","cc");'
    instructions=[]
    for row in range(4):
        for x in (0,4):instructions.append(f'move.l {row*ss+x}(%0),{row*ds+x}(%1)')
    return '__asm__ volatile ("'+'\\n\\t'.join(instructions)+'" : : "a"(src),"a"(dst) : "memory","cc");'
parts.append('''void __attribute__((noinline)) copy_plan(const u16 *ops,u16 count,u16 *plane,u16 *cache) {
 for(u16 i=0;i<count;i++) {
  u16 s=*ops++,d=*ops++;const u16 *src;u16 *dst;
  if(s&0x8000) {
   src=(const u16 *)((const u8 *)cache+(s16)(s&0x7fff));
   if(d&0x8000) {dst=(u16 *)((u8 *)cache+(s16)(d&0x7fff));
'''+block(8,8)+'''
   } else {dst=(u16 *)((u8 *)plane+(s16)d);
'''+block(8,128)+'''
   }
  } else {
   src=(const u16 *)((const u8 *)plane+(s16)s);
   if(d&0x8000) {dst=(u16 *)((u8 *)cache+(s16)(d&0x7fff));
'''+block(128,8)+'''
   } else {dst=(u16 *)((u8 *)plane+(s16)d);
'''+block(128,128)+'''
   }
  }
 }
}
void __attribute__((noinline)) plan_done(void) {__asm__ volatile ("nop");}
''')
parts.append(r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff1000;
 u16 *plane=(u16 *)0xff2000,*cache=(u16 *)0xff4000;
 status[0]=1;status[7]=0;while(!status[7]) {__asm__ volatile ("nop");}
 unsigned int checked=0;
 for(u16 alignment=0;alignment<4;alignment++) {
 plane=(u16 *)(0xff2000+((alignment&1)<<1));cache=(u16 *)(0xff4000+(alignment&2));status[6]=alignment;
 for(u16 wi=0;wi<5;wi++) {
  const Wheel *w=wheels[wi];u16 cap=w->slots-88;
  plane[-1]=cache[-1]=0xa55a;plane[2048]=cache[(cap+1)*16]=0x5aa5;
  for(u16 i=0;i<2048;i++)plane[i]=0x5959;
  for(u16 i=0;i<(cap+1)*16;i++)cache[i]=0xdead;
  for(u16 slot=0;slot<w->slots;slot++) {
   u8 key=w->layout[slot];if(key==255)continue;
   u16 *dst;u16 stride;
   if(slot<88) {u16 x=slot%11,y=slot/11;dst=plane+(((w->cy+y)&7)<<8)+(((w->cx+x)&15)<<2);stride=64;}
   else {dst=cache+(slot-88)*16;stride=4;}
   const u16 *src=w->pixels+key*16;
   for(u16 y=0;y<4;y++)for(u16 x=0;x<4;x++)dst[y*stride+x]=src[y*4+x];
  }
  u16 old=0;
  for(u16 tick=0;tick<180;tick++) {
   static const u8 sequence[9]={0,1,0,2,1,1,2,2,0};
   u16 next=sequence[tick%9];
   status[1]=wi;status[2]=old;status[3]=next;status[4]=tick;
   u16 index=old*3+next;
   copy_plan(w->plans[index],w->counts[index],plane,cache);plan_done();
   const u8 *layout=w->layout+next*w->slots;
   for(u16 row=0;row<32;row++)for(u16 col=0;col<64;col++) {
    u16 x=((col>>2)-(w->cx&15))&15,y=((row>>2)-(w->cy&7))&7;
    u16 expected=x>=11?0x5959:w->pixels[layout[y*11+x]*16+(row&3)*4+(col&3)];
    if(plane[row*64+col]!=expected) {status[5]=row*64+col;status[0]=0xdead;return;}
   }
   for(u16 slot=0;slot<cap;slot++) {
    u8 key=layout[88+slot];if(key==255)continue;
    for(u16 word=0;word<16;word++)if(cache[slot*16+word]!=w->pixels[key*16+word]) {
     status[5]=4096+slot*16+word;status[0]=0xdead;return;
    }
   }
   if(plane[-1]!=0xa55a || cache[-1]!=0xa55a || plane[2048]!=0x5aa5 || cache[(cap+1)*16]!=0x5aa5) {status[0]=0xdead;return;}
   old=next;checked++;
  }
 }
 }
 status[1]=checked;status[0]=0x600d;
}
''')
(out/'probe.c').write_text('\n'.join(parts))
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O3','-fno-ipa-icf','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),subprocess.check_output([str(cc),'-m68000','-print-libgcc-file-name'],text=True).strip(),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
symbols=subprocess.check_output([str(cc.with_name('m68k-elf-nm')),'-n',str(out/'probe.elf')],text=True)
(out/'probe-symbols.txt').write_text(symbols)
pcs={w[2]:int(w[0],16) for line in symbols.splitlines() if len(w:=line.split())==3}
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());original_hash=hashlib.sha256(rom).hexdigest();raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text('00ff1000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin');cpu=C.addressof(C.c_uint8.in_dll(r.lib,'m68k'))
r.run(1);assert r.u32('probe_status')==1
budget=C.c_uint32.in_dll(r.lib,'mcycles_vdp').value
assert budget==896040 and C.c_uint32.from_address(cpu+0x29c8).value==0x100000
r.write('probe_status',bytes([0,0,0,1]),28)
samples=[];pending=None
r.lib.m68k_get_reg.argtypes=[C.c_uint];r.lib.m68k_get_reg.restype=C.c_uint

def watch():
    global pending
    pc=(C.c_uint32.from_address(cpu+0x2858).value-2)&0xffffff
    now=r.frames*budget+C.c_uint32.from_address(cpu+0x280c).value
    if pc==pcs['copy_plan']:
        pending=(now,[r.u32('probe_status',i*4) for i in (1,2,3,4,6)])
    else:
        assert pending is not None
        start,(wi,old,new,tick,alignment)=pending
        assert now>=start
        samples.append({'wheel':wi,'old':old,'new':new,'tick':tick,'alignment':alignment,'core_ticks':now-start,'scanlines':(now-start)/3420})
        pending=None
with instruction_profile(r,out/'copy-watch',enabled=False,watch=([pcs['copy_plan'],pcs['plan_done']],watch)):
    for _ in range(20000):
        r.run(1)
        if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
assert r.u32('probe_status',4)==len(samples)==3600
assert hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()==original_hash
summary=[]
for wi,wheel in enumerate(wheels):
    assert {s['alignment'] for s in samples if s['wheel']==wi}==set(range(4))
    assert {(s['old'],s['new']) for s in samples if s['wheel']==wi}=={(a,b) for a in range(3) for b in range(3)}
    rows=[s for s in samples if s['wheel']==wi and s['old']!=s['new']]
    summary.append(dict(wheel=wheel['name'],minimum_scanlines=min(s['scanlines'] for s in rows),mean_scanlines=sum(s['scanlines'] for s in rows)/len(rows),maximum_scanlines=max(s['scanlines'] for s in rows),transitions=len(rows),copy_counts=wheel['copy_counts']))
result={'movem':args.movem,'release_rom_sha256':original_hash,'map_source_sha256':hashlib.sha256(source.encode()).hexdigest(),'native_verified_transitions':3600,'all_modes':False,'native_game_integration_verified':False,'full_speed_verified':False,'scope':__doc__,'summary':summary,'samples':samples}
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='samples'},indent=2))
