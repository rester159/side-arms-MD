#!/usr/bin/env python3
"""Check the actual MOVEP event clear at both byte alignments under O2 and O3."""
import argparse
import json
import struct
import subprocess
from pathlib import Path
from run_rom import ROOT, Runner

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--rom', type=Path, required=True)
p.add_argument('--source', type=Path, default=ROOT/'src/bc_world.c')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
source = a.source.read_text()
start = source.index('static __attribute__((always_inline)) inline void event_clear(')
helper = source[start:source.index('\n}\n', start)+3]
main = r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 unsigned char *storage=(unsigned char *)0xff2000;
 unsigned int checks=0;status[0]=1;
 for(unsigned int alignment=0;alignment<2;alignment++) {
  for(unsigned int value=0;value<256;value++) {
   for(unsigned int i=0;i<20;i++)storage[i]=(unsigned char)(value+i);
   BcActorEvent *event=(BcActorEvent *)(storage+4+alignment);
   unsigned char prior=event->retired;
   event_clear(event);
   if(prior!=(unsigned char)(value+4+alignment) || event->retired || event->player_died) {
    status[1]=value;status[2]=alignment;status[0]=0xdead;return;
   }
   for(unsigned int i=0;i<20;i++) {
    unsigned char expected=(i>=4+alignment && i<12+alignment)?0:(unsigned char)(value+i);
    if(storage[i]!=expected){status[1]=value;status[2]=i;status[3]=storage[i];status[0]=0xdead;return;}
   }
   checks++;
  }
 }
 status[1]=checks;status[0]=0x600d;
}
'''
cc = Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
reports = []
for optimization in ('O2', 'O3'):
 out = a.output/optimization
 out.mkdir(parents=True, exist_ok=True)
 (out/'probe.c').write_text('#include "bc_world.h"\n'+helper+main)
 (out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
 subprocess.run([str(cc),'-m68000','-'+optimization,'-I'+str(ROOT/'inc'),'-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
 subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
 rom=bytearray(a.rom.read_bytes());raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
 rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000);(out/'probe-rom.bin').write_bytes(rom)
 (out/'symbol.txt').write_text((a.rom.parent/'symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
 r=Runner(rom=out/'probe-rom.bin')
 for _ in range(1000):
  r.run(1)
  if r.u32('probe_status')in(0x600d,0xdead):break
 assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
 assert r.u32('probe_status',4)==512
 reports.append(dict(optimization=optimization,cases=512,passed=True))
 r.lib.retro_unload_game();r.lib.retro_deinit()
result=dict(passed=True,tests=reports,scope='Eight cleared bytes, prior read and surrounding sentinels; even/odd event addresses, all byte values.')
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
