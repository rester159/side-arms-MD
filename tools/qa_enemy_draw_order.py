#!/usr/bin/env python3
"""Compile the actual small/large-enemy draw loops and compare full-pool sprite order.

Exercises nonempty pool/rotation combinations, including empty tails,
holes and dense pools. Uses a recording sprite stub; does not claim gameplay
or performance verification.
"""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'src/enemies.c').read_text();a=s.index('static __attribute__((noinline)) void draw_small(');b=s.index('\nstatic void draw_big',a)
source='''#include <stdint.h>
#include <assert.h>
#include <stdio.h>
typedef uint16_t u16;
typedef struct { unsigned live,code,colour; int x,y; } Enemy;
static unsigned got[40],count;
static void spr_16(unsigned code,unsigned colour,int x,int y,unsigned flags) { got[count++]=code; }
#define spr_32 spr_16
'''+s[a:b]+'''
int main(void) {
 uint32_t rng=159; unsigned checks=0;
 for(unsigned n=8;n<=40;n+=16) for(unsigned mask=0;mask<10000;mask++) {
  Enemy pool[40]={0};unsigned last=0;
  for(unsigned i=0;i<n;i++) {
   rng=rng*1664525+1013904223;pool[i].live=(rng>>24)<(mask%256);
   pool[i].code=i+1;if(pool[i].live)last=i+1;
  }
  if(!last)continue;
  for(unsigned rot=0;rot<(n==8?8:n==24?24:16);rot++) {
   count=0;
   if(n==24)draw_large(pool,pool+last,rot);else draw_small(pool,pool+last,rot);
   unsigned expected=0;
   for(unsigned k=0;k<n;k++) {
    unsigned i=(rot+k)%n;
    if(pool[i].live) { assert(expected<count);assert(got[expected++]==i+1); }
   }
   assert(count==expected);checks++;
  }
 }
 printf("%u ordered pool draws matched full traversal\\n",checks);
}
'''
p=ROOT/'.local/qa-enemy-draw-order/order.c';p.parent.mkdir(parents=True,exist_ok=True);p.write_text(source)
subprocess.run(['cc','-O2',str(p),'-o',str(p.with_suffix(''))],check=True)
subprocess.run([str(p.with_suffix(''))],check=True)
