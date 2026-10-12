#!/usr/bin/env python3
"""Exercise production strip splicing with stubbed cache outcomes; native pixels are checked separately."""
from pathlib import Path
import subprocess
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'.local/qa-bc-spike-strips'
p.mkdir(parents=True,exist_ok=True)
s=(ROOT/'src/sprites.c').read_text(); start=s.index('static __attribute__((noinline,optimize("O2"))) void spike_strips');end=s.index('/* Bounded composition',start)
prefix=r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
#include <stdio.h>
typedef uint16_t u16; typedef uint8_t u8;
typedef struct {u16 y;u8 size,link;u16 attribut,x;} VDPSprite;
#define MAX_SPR 80
#define NONE 255
#define DMA_VRAM 0
#define SPRITE_SIZE(w,h) ((((w)-1)<<2)|((h)-1))
static VDPSprite vdpSpriteCache[81],before[80];
static u16 count,spike_count,budget,uploads,variant;
static u8 spike_entries[80],bc_spike_strips[384];
static u16 spr_big_index[32768];
static struct {u16 attr[80];} big;
static u16 lookup(void *c,u16 k){return variant==0?0xc300:0;}
static u16 victim(void *c){return variant==2?NONE:0;}
static void claim(void *c,u16 slot,u16 code,u16 key,u8 pal){big.attr[slot]=0xc300;}
static u16 slot_tile(void *c,u16 slot){return 0x300;}
static void DMA_queueDmaFast(int a,void*b,int c,int d,int e){}
'''
main=r'''
int main(void){unsigned checks=0;
for(unsigned n=1;n<=80;n++)for(unsigned targets=0;targets<=n;targets++)
for(unsigned pattern=0;pattern<3;pattern++)
for(unsigned flip=0;flip<4;flip++)for(variant=0;variant<4;variant++){
 memset(vdpSpriteCache,0xa5,sizeof(vdpSpriteCache));
 count=n;spike_count=targets;budget=variant==1?0:384;uploads=0;
 for(unsigned i=0;i<n;i++){
  vdpSpriteCache[i]=(VDPSprite){128+i,15,i+1<n?i+1:0,0xe100|(flip<<11),128+i*2};
  before[i]=vdpSpriteCache[i];
 }
 // Head, tail and interleaved targets include arbitrary unmodified links.
 int selected[80]={0},rank[80]; unsigned r=0;
 for(unsigned k=0;k<targets;k++){
  unsigned i=pattern==0?n-targets+k:pattern==1?k:
      k<(n+1)/2?k*2:(k-(n+1)/2)*2+1;
  selected[i]=1;
 }
 for(unsigned i=0;i<n;i++){
  rank[i]=-1;
  if(selected[i]){rank[i]=r;spike_entries[r++]=i;}
 }
 assert(r==targets);
 spike_strips();
 unsigned extras=(variant==0||variant==3)?(targets<80-n?targets:80-n):0;
 assert(count==n+extras && count<=80);
 assert(vdpSpriteCache[80].y==0xa5a5);
 unsigned cursor=0,seen=0;
 for(unsigned i=0;i<n;i++){
  assert(cursor==i);VDPSprite *cap=&vdpSpriteCache[cursor];seen++;
  if(rank[i]>=0 && (unsigned)rank[i]<extras){
   unsigned j=rank[i];assert(cap->link==n+j);
   assert(cap->x==before[i].x+8 && cap->y==before[i].y+((flip&2)?16:0));
   assert(cap->size==SPRITE_SIZE(2,2));assert(cap->attribut==((before[i].attribut&0xf800)|0x300));
   VDPSprite *base=&vdpSpriteCache[cap->link];seen++;
   assert(base->x==before[i].x && base->y==before[i].y+((flip&2)?0:16));
   assert(base->size==SPRITE_SIZE(4,2));assert(base->attribut==((before[i].attribut&0xf800)|0x304));
   cursor=base->link;
  }else{assert(!memcmp(cap,&before[i],sizeof(*cap)));cursor=cap->link;}
 }
 assert(cursor==0 && seen==count);checks++;
}
printf("PASS %u SAT capacity, flip, link and fallback cases\n",checks);
}
'''
(p/'probe.c').write_text(prefix+s[start:end]+main)
subprocess.run(['cc','-O2','-Wno-unknown-attributes',str(p/'probe.c'),'-o',str(p/'probe')],check=True)
subprocess.run([str(p/'probe')],check=True)
