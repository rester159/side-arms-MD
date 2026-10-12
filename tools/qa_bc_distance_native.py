#!/usr/bin/env python3
"""Exhaust production native unsigned distance over every X and boundary Ys."""
from pathlib import Path
import struct,subprocess
from run_rom import ROOT,Runner
out=ROOT/'.local/bc-body-distance-native';out.mkdir(exist_ok=True)
s=(ROOT/'inc/bc_rules.h').read_text()
helper=s[s.index('static inline __attribute__((always_inline)) unsigned short bc_unsigned_distance('):len(s)]
(out/'probe.c').write_text(helper+'\nvoid probe_main(void) {\n volatile unsigned int *status=(volatile unsigned int *)0xff8000;\n const unsigned short ys[10]={0,1,4,127,255,256,32767,32768,65534,65535};\n unsigned int checked=0;status[0]=1;\n for(unsigned int j=0;j<10;j++)for(unsigned int x=0;x<65536;x++){\n  unsigned short y=ys[j],actual=bc_unsigned_distance(x,y);\n  unsigned short expected=x>=y?x-y:y-x;\n  if(actual!=expected){status[1]=x;status[2]=y;status[3]=actual;status[0]=0xdead;return;}\n  checked++;\n }\n status[1]=checked;status[0]=0x600d;\n}\n')
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O2','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)));raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000)
(out/'probe-rom.bin').write_bytes(rom);(out/'symbol.txt').write_text((ROOT/'out/release/symbol.txt').read_text()+'\n00ff8000 B probe_status\n')
r=Runner(rom=out/'probe-rom.bin')
for _ in range(5000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',16).hex()
assert r.u32('probe_status',4)==655360
print('PASS: 655360 native unsigned distances; all65536 X values against10 Y boundary values, both subtraction directions')
