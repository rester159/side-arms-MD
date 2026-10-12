#!/usr/bin/env python3
"""Exercise the production cap compositor with deterministic cache/queue failures."""
from pathlib import Path
import subprocess,json
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'.local/qa-bc-cap-merges';p.mkdir(parents=True,exist_ok=True)
src=(ROOT/'src/sprites.c').read_text();frag=src[src.index('/* Bounded composition'):src.index('\nvoid spr_end')]
prefix=r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef uintptr_t u32;
#define TRUE true
#define FALSE false
#define NONE 255
#define DMA_VRAM 0
#define SPRITE_SIZE(w,h) ((((w)-1)<<2)|((h)-1))
typedef struct {u16 y;u8 size,link;u16 attribut,x;} VDPSprite;
static VDPSprite vdpSpriteCache[80],before[80];
static struct {u16 attr[32];} big;
static u16 spike_count,count,budget,uploads;static u8 spike_entries[80];
static unsigned mode,claims,queues;
static u16 game_player_limit(void){return mode==7?2:4;}
static u16 lookup(void*c,u16 key){return mode==1?0xe300:0;}
static u16 victim(void*c){return mode==2?NONE:0;}
static u16 slot_tile(void*c,u16 slot){return 0x300;}
static void claim(void*c,u16 slot,u16 code,u16 key,u8 pal){claims++;big.attr[slot]=0xe300;}
static bool DMA_queueDmaFast(int a,void*b,int c,int d,int e){queues++;return mode!=4;}
'''
main=r'''
int main(void){unsigned checks=0;
for(mode=0;mode<8;mode++)for(int dx=-15;dx<=15;dx++)for(unsigned flip=0;flip<4;flip++){
 memset(vdpSpriteCache,0,sizeof(vdpSpriteCache));unsigned first=mode==6?10:0,second=mode==5?2:first+1;
 count=second+1;spike_count=2;spike_entries[0]=first;spike_entries[1]=second;
 for(unsigned i=0;i<count;i++)vdpSpriteCache[i]=(VDPSprite){180,15,i+1<count?i+1:0,0xe100,128};
 vdpSpriteCache[first]=(VDPSprite){180,5,first+1,0xe100|(flip<<11),220};
 vdpSpriteCache[second]=(VDPSprite){180,5,0,0xe100|(flip<<11),220+dx};
 memcpy(before,vdpSpriteCache,sizeof(before));claims=queues=uploads=dbg_cap_merges=0;budget=mode==3?0:6144;
 cap_merge();
 if(mode<=1){
  assert(dbg_cap_merges==1);assert(vdpSpriteCache[first].link==0);
  assert(vdpSpriteCache[first].x==(dx<0?220+dx:220));
  assert((vdpSpriteCache[first].attribut&0xf800)==(before[first].attribut&0xf000));
  assert(claims==(mode==0)&&queues==(mode==0)&&uploads==(mode==0));
 }else{
  assert(!memcmp(before,vdpSpriteCache,sizeof(before)));assert(!claims&&!uploads&&!dbg_cap_merges);
  assert(budget==(mode==3?0:6144));assert(queues==(mode==4));
 }
 checks++;
}
printf("PASS %u fallback/offset/flip cases\n",checks);return 0;}
'''
# Align the test table to a 128 KiB boundary so host ASLR cannot trigger the
# deliberate source-bank guard while testing unrelated fallback cases.
header=(ROOT/'inc/gen/bc_cap_merge_patterns.inc').read_text().replace('aligned(256)','aligned(131072)');(p/'fallback-patterns.inc').write_text(header);frag=frag.replace('"gen/bc_cap_merge_patterns.inc"','"fallback-patterns.inc"')
(p/'fallback-test.c').write_text(prefix+frag+main);subprocess.run(['cc','-O2','-Wno-pointer-to-int-cast',str(p/'fallback-test.c'),'-o',str(p/'fallback-test')],check=True);r=subprocess.run([str(p/'fallback-test')],check=True,capture_output=True,text=True);print(r.stdout)
(p/'fallback-result.json').write_text(json.dumps(dict(passed=True,cases=992,scope='Host-compiled isolated candidate function with cache/queue stubs: all 31 overlapping offsets, four flips, success/cache hit/no victim/no budget/queue rejection/intervening row overlap/fetch exhaustion/two-player bypass. No native timing or live queue exhaustion proof.'),indent=2)+'\n')
