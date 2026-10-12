#!/usr/bin/env python3
"""Compare actual wheel delta/cache drawing against a saved uncached bg.c.

Whole-plane comparisons include ring wrap, slot reassignment, missing tiles,
shadow invalidation and separate pre-rendered images. Lifecycle/VRAM transfer
behavior is covered separately by native video traces and exit checks.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
a=p.parse_args()
s=(ROOT/'src/bg.c').read_text();b=a.baseline.read_text()
def function(source,name):
    start=source.index(('static inline u16 ' if name=='frame_orientation' else 'static void ')+name+'(')
    return source[start:source.index('\n}\n',start)+3]
PREFIX=r'''#include <stdint.h>
#include <stdio.h>
#include <assert.h>
#include <string.h>
typedef uint16_t u16;typedef uint8_t u8;typedef int16_t s16;typedef int bool;
#define TRUE 1
#define FALSE 0
#define RING_W 16
#define RING_H 8
#define NO_SLOT 255
#define VRAM_BG_TILE 160
#define TILE_ATTR_HFLIP_MASK 0x800
#define TILE_ATTR_VFLIP_MASK 0x1000
typedef struct {u16 metas;const u16 *tmpl;} Zone;
typedef struct {u16 cx,cy,w,h;const u16 *maps;const u16 *extra_tmpl;} BgFrames;
static u16 ordinary[64*16],extra[64*16],maps[3*88],shadow[32][64],cache[56*4*17];
static u8 meta_slot[128],slots[128];
static Zone z={64,ordinary};static const Zone *zone=&z;
static BgFrames f={0,0,11,8,maps,extra};static const BgFrames *fr=&f;
static const u16 *ext_tmpl=extra;static u16 *fr_cells;static u8 *fr_slots;
static s16 fr_shadow_frame=-1;

'''
MAIN=r'''static uint32_t seed=0x7f31c;static uint32_t rnd(void){seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed;}
int main(void){
 for(unsigned i=0;i<1024;i++){ordinary[i]=i/16%3==0?0xe000|(i&15):(rnd()%3?((rnd()&7)<<13)|(i&15):0);extra[i]=i/16%3==0?0xe000|(i&15):(rnd()%3?((rnd()&7)<<13)|(i&15):0);}
 u16 expected[2048],other[2048];unsigned checks=0;
 for(unsigned route=0;route<40;route++){
  memset(shadow,0x59,sizeof(shadow));memset(expected,0x59,sizeof(expected));memset(cache,0,sizeof(cache));
  fr_shadow_frame=-1;fr_slots=(route&1)?slots:0;fr_cells=(route&2)?cache:0;f.cx=rnd();f.cy=rnd();
  for(unsigned i=0;i<128;i++)meta_slot[i]=rnd()%5?rnd()%56:255;
  for(unsigned i=0;i<88;i++){maps[i]=rnd()%128|((rnd()%4)<<14);maps[88+i]=rnd()%2?maps[i]:rnd()%128|((rnd()%4)<<14);maps[176+i]=rnd()%2?maps[i]:rnd()%128|((rnd()%4)<<14);}
  for(unsigned tick=0;tick<500;tick++){
   if(tick%17==0){unsigned i=rnd()%2048;shadow[i/64][i%64]=expected[i]=rnd();fr_shadow_frame=-1;}
   if(tick%11==0)meta_slot[rnd()%128]=rnd()%4?rnd()%56:255;
   unsigned n=rnd()%3;
   reference_cells(n,expected,0,8);frame_cells(n,&shadow[0][0],0,8);fr_shadow_frame=n;
   assert(!memcmp(expected,shadow,sizeof(shadow)));checks++;
   // Rendering an independent full-frame image must never use shadow skips.
   memset(other,0x59,sizeof(other));u16 ref_other[2048];memcpy(ref_other,other,sizeof(other));
   reference_cells(n,ref_other,2,6);frame_cells(n,other,2,6);assert(!memcmp(ref_other,other,sizeof(other)));checks++;
  }
 }
 printf("PASS: %u whole-plane comparisons; delta invalidation, slot changes, blank cells, flips, ring wrap, cache combinations and independent images\n",checks);
}
'''
plain=s[s.index('#define CW('):s.index('#undef CW')+len('#undef CW')]
reference=function(b,'frame_cells').replace('frame_cells(','reference_cells(',1)
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory)
    (d/'compare.c').write_text('\n'.join((PREFIX,plain,function(s,'frame_orientation'),function(s,'cached_frame_cell'),reference,function(s,'frame_cells'),MAIN)))
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(d/'compare.c'),'-o',str(d/'compare')],check=True)
    subprocess.run([str(d/'compare')],check=True)
