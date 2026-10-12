#!/usr/bin/env python3
"""Exhaust production native pitch division on emulated 68000 hardware."""
import hashlib,json,struct,subprocess
from pathlib import Path
from run_rom import ROOT,Runner
out=ROOT/'.local/hucard-pitch-native';out.mkdir(exist_ok=True)
source=(ROOT/'src/sound/hucard_fm.c').read_text()
helper=source[source.index('static unsigned short pitch_divide('):source.index('\nvoid hucard_fm_frame(')]
main=r'''
void probe_main(void) {
 volatile unsigned int *status=(volatile unsigned int *)0xff8000;
 const unsigned short *expected=(const unsigned short *)0x380000;
 unsigned int checks=0;status[0]=1;
 for(unsigned region=0;region<2;region++) for(unsigned input=0;input<65536;input++) {
  unsigned long d=input?input:4096;
  unsigned long numerator=region?4444560:4404020;
  unsigned minimum=region?2171:2151,block=0;
  while(d<minimum && block<7){d<<=1;block++;}
  unsigned short actual=pitch_divide(numerator+d/2,(unsigned short)d);
  if(actual!=expected[checks]) {
   status[1]=input;status[2]=region;status[3]=actual;status[4]=expected[checks];
   status[0]=0xdead;return;
  }
  checks++;
 }
 status[1]=checks;status[0]=0x600d;
}
'''
(out/'probe.c').write_text(helper+main)
(out/'start.s').write_text('.text\n.global _start\n_start:\n move.w #0x2700,%sr\n lea 0xffff00,%sp\n jsr probe_main\nstop_here:\n bra.s stop_here\n')
cc=Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'
subprocess.run([str(cc),'-m68000','-O3','-nostdlib','-ffreestanding','-fno-builtin','-Wl,-Ttext=0x3e0000',str(out/'start.s'),str(out/'probe.c'),'-o',str(out/'probe.elf')],check=True)
subprocess.run([str(cc.with_name('m68k-elf-objcopy')),'-O','binary',str(out/'probe.elf'),str(out/'probe.bin')],check=True)
# Independent old conversion: divide at each octave, without threshold constants.
expected=[];bounds=[]
for numerator in (4404020,4444560):
 for period in range(65536):
  divisor=period or 4096;block=0
  quotient=(numerator+divisor//2)//divisor
  while quotient>2047 and block<7:
   block+=1;divisor*=2;quotient=(numerator+divisor//2)//divisor
  assert 128<=divisor<=65535 and quotient<=65535
  expected.append(quotient);bounds.append(divisor)
rom=bytearray((ROOT/'out/release/rom.bin').read_bytes());rom.extend(bytes(0x400000-len(rom)))
rom[0x380000:0x3c0000]=struct.pack('>131072H',*expected)
raw=(out/'probe.bin').read_bytes();assert len(raw)<0x20000
rom[0x3e0000:0x3e0000+len(raw)]=raw;struct.pack_into('>I',rom,4,0x3e0000)
(out/'rom.bin').write_bytes(rom)
(out/'symbol.txt').write_text('00ff8000 B probe_status\n')
r=Runner(rom=out/'rom.bin')
for _ in range(5000):
 r.run(1)
 if r.u32('probe_status') in (0x600d,0xdead):break
assert r.u32('probe_status')==0x600d,r.read('probe_status',20).hex()
assert r.u32('probe_status',4)==131072
report=dict(passed=True,cases=131072,max_quotient=max(expected),min_divisor=min(bounds),max_divisor=max(bounds),frames=r.frames,helper_sha256=hashlib.sha256(helper.encode()).hexdigest())
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
