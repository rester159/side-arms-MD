#!/usr/bin/env python3
"""Verify the production wheel metatile collector preserves first-use order."""
from pathlib import Path
import subprocess
import tempfile
root = Path(__file__).resolve().parents[1]
source = (root / 'src/bg.c').read_text()
start = source.index('void bg_frames_begin(')
function = source[start:source.index('\n}\n', start) + 3]
prefix = r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef struct {u16 zone,w,h,nframes; const u16 *maps;} BgFrames;
static const BgFrames *fr;
static u16 fr_state,fr_next,fr_nmeta,fr_meta[64];
static int fr_shown,zone=1,zone_id;
static void bg_frames_end(void){}
static void bg_set_zone(u16 n){zone_id=n;}
'''
main = r'''
int main(void) {
 u16 maps[512],expected[64];unsigned cases=0;
 for(unsigned base=0;base<4096;base++) for(unsigned kind=0;kind<5;kind++) {
  unsigned count=0;
  for(unsigned i=0;i<512;i++) {
   unsigned offset=kind==0?0:kind==1?i%63:kind==2?i%64:kind==3?i%65:i*37;
   maps[i]=((base+offset)&4095)|((i&3)<<14);
   unsigned m=maps[i]&4095,k=0;
   while(k<count&&expected[k]!=m)k++;
   if(k==count&&count<64)expected[count++]=m;
  }
  BgFrames f={1,16,8,4,maps};bg_frames_begin(&f);
  assert(fr==&f&&fr_state==1&&fr_next==0&&fr_shown==-1);
  assert(fr_nmeta==count&&!memcmp(fr_meta,expected,count*sizeof(u16)));cases++;
 }
 printf("PASS: %u preload lists; all 4096 IDs, flips, repeats, and 63/64/65-entry boundaries\n",cases);
}
'''
with tempfile.TemporaryDirectory() as td:
    c=Path(td)/'probe.c';exe=Path(td)/'probe'
    c.write_text(prefix+function+main)
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
