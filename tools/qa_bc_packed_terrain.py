#!/usr/bin/env python3
"""Benchmark an optional packed terrain representation in a scratch 68000 ROM.
This does not change the game's terrain ABI, resources, or release cartridge.
"""
import hashlib,json,os,struct,subprocess
from pathlib import Path
from run_rom import ROOT,Runner
from profile_genesis import instruction_profile
out=ROOT/'.local/bc-packed-terrain-probe';build=out/'out/release';build.mkdir(parents=True,exist_ok=True)
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
def array(name,data,typ='unsigned char'):
    return f'static const {typ} {name}[]={{'+','.join(str(v) for v in data)+'};\n'
source=['typedef unsigned char u8; typedef unsigned short u16;\n',
        'typedef struct {const u8 *cells,*attributes; const u16 *offsets; const u8 *packed,*packed_cells,*packed_attributes,*direct;} Terrain;\n']
rows=[];sizes=[]
for n in range(1,11):
    folder=ROOT/'.local/pce-reference'/('play-task-round1' if n==1 else f'round{n:02d}-reference')
    code=(folder/'code-002160.bin').read_bytes();cells=code[0xc000:0x10000]
    offset=int.from_bytes(code[0x621c:0x621e],'little')-0x4000;attrs=code[offset:offset+2048]
    assert len(cells)==16384 and len(attrs)==2048
    pages=[];offsets=[];known={};direct=bytearray(65536)
    for by in range(16):
        for bx in range(16):
            values=[]
            for y in range(16):
                for x in range(16):
                    tile=cells[(by*16+bx)*64+(y//2)*8+x//2]
                    value=attrs[tile*8+(x&1)*2+(y&1)*4+1]&15
                    values.append(value);direct[(by*16+y)*256+bx*16+x]=value
            page=bytes((values[i]<<4)|values[i+1] for i in range(0,256,2))
            if page not in known:known[page]=len(pages)*128;pages.append(page)
            offsets.append(known[page])
    packed=b''.join(pages);assert len(packed)<=32768
    for label,data,typ in [('cells',cells,'unsigned char'),('attrs',attrs,'unsigned char'),('offsets',offsets,'unsigned short'),('packed',packed,'unsigned char'),('direct',direct,'unsigned char')]:source.append(array(f'r{n}_{label}',data,typ))
    rows.append('{'+f'r{n}_cells,r{n}_attrs,r{n}_offsets,r{n}_packed,r{n}_cells,r{n}_attrs,r{n}_direct'+'}')
    sizes.append(dict(round=n,pages=len(pages),packed_bytes=len(packed)+512))
source.append('static const Terrain terrains[10]={'+','.join(rows)+'};\n')
s=(ROOT/'src/bc_rules.c').read_text();ref=s[s.index('unsigned char bc_terrain_solid('):s.index('/* PCE $8F39-$902E')]
ref=ref.replace('unsigned char bc_terrain_solid(', 'unsigned char __attribute__((noinline,noclone)) reference_lookup(').replace('BcTerrain','Terrain')
source.append(ref)
source.append(r'''
unsigned char __attribute__((noinline,noclone)) packed_lookup(const Terrain *t, u16 x, u16 y) {
 if(t->packed && t->cells==t->packed_cells && t->attributes==t->packed_attributes) {
  u16 page=((x>>8)&15)|((y>>4)&240);
  u16 at=t->offsets[page]+((y&240)>>1)+((x>>5)&7);
  u8 value=t->packed[at];
  return ((x&16)?value:value>>4)&15;
 }
 return reference_lookup(t,x,y);
}
unsigned char __attribute__((noinline,noclone)) direct_lookup(const Terrain *t, u16 x, u16 y) {
 if(t->direct && t->cells==t->packed_cells && t->attributes==t->packed_attributes)
  return t->direct[((x>>4)&255)|((y&4080)<<4)];
 return reference_lookup(t,x,y);
}
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned int checked=0;status[0]=1;
 for(unsigned int round=0;round<10;round++) for(unsigned int i=0;i<65536;i++) {
  u16 x=((i&255)<<4)|((i>>8)&15)|((i&15)<<12);
  u16 y=((i&0xff00)>>4)|(i&15)|(((i>>4)&15)<<12);
  u8 expected=reference_lookup(&terrains[round],x,y);
  u8 actual=packed_lookup(&terrains[round],x,y);
  if(actual!=expected || direct_lookup(&terrains[round],x,y)!=expected) {status[1]=round;status[2]=x;status[3]=y;status[4]=expected;status[5]=actual;status[0]=0xdead;return;}
  checked++;
 }
 status[1]=checked;status[0]=2;while(status[0]==2) {}
 /* Mismatched source pointers and disabled packing must use the source table. */
 unsigned int changed_results=0;
 Terrain changed=terrains[0];changed.cells=terrains[1].cells;
 for(unsigned int i=0;i<4096;i++) {
  changed_results += reference_lookup(&changed,i,i*17)!=reference_lookup(&terrains[0],i,i*17);
  if(packed_lookup(&changed,i,i*17)!=reference_lookup(&changed,i,i*17) || direct_lookup(&changed,i,i*17)!=reference_lookup(&changed,i,i*17)) {status[0]=0xdead;return;}
 }
 changed=terrains[0];changed.attributes=terrains[1].attributes;
 for(unsigned int i=0;i<4096;i++) {
  changed_results += reference_lookup(&changed,i,i*17)!=reference_lookup(&terrains[0],i,i*17);
  if(packed_lookup(&changed,i,i*17)!=reference_lookup(&changed,i,i*17) || direct_lookup(&changed,i,i*17)!=reference_lookup(&changed,i,i*17)) {status[0]=0xdead;return;}
 }
 if(!changed_results) {status[0]=0xdead;return;}
 changed=terrains[0];changed.packed=0;changed.direct=0;
 for(unsigned int i=0;i<4096;i++) {
  changed_results += reference_lookup(&changed,i,i*17)!=reference_lookup(&terrains[0],i,i*17);
  if(packed_lookup(&changed,i,i*17)!=reference_lookup(&changed,i,i*17) || direct_lookup(&changed,i,i*17)!=reference_lookup(&changed,i,i*17)) {status[0]=0xdead;return;}
 }
 status[1]=checked;status[0]=0x600d;
}
''')
(out/'probe.c').write_text(''.join(source));(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x300000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
raw=(out/'probe.bin').read_bytes();assert len(raw)<0x100000
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));rom[0x300000:0x300000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x300000);(build/'rom.bin').write_bytes(rom)
symbols=subprocess.check_output([str(cc.with_name('m68k-elf-nm')),'-n',str(out/'probe.elf')],text=True)
(build/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n'+symbols+'\n00ff8000 B probe_status\n')
r=Runner(rom=build/'rom.bin');old=os.environ.get('SIDEARMS_BUILD');os.environ['SIDEARMS_BUILD']=str(out)
try:
    with instruction_profile(r,out/'profile'):
        for _ in range(12000):
            r.run(1)
            if r.u32('probe_status') in (2,0xdead):break
finally:
    if old is None:os.environ.pop('SIDEARMS_BUILD',None)
    else:os.environ['SIDEARMS_BUILD']=old
assert r.u32('probe_status')==2,r.read('probe_status',24).hex()
r.write('probe_status',(3).to_bytes(4,'big'))
for _ in range(1000):
    r.run(1)
    if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',24).hex()
assert r.u32('probe_status',4)==655360
profile=json.loads((out/'profile.json').read_text());functions={v['name']:v['cycles'] for v in profile['functions']}
result=dict(checked=655360,fallback_checks=12288,rounds=sizes,total_packed_bytes=sum(v['packed_bytes'] for v in sizes),reference_attributed_ticks=functions['reference_lookup'],packed_attributed_ticks=functions['packed_lookup'],direct_attributed_ticks=functions['direct_lookup'],direct_bytes_per_round=65536,profile_scope='655360 valid queries per function; fallback checks run without profiling',source_rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),production_changed=False,full_game_performance_verified=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
