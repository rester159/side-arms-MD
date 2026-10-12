#!/usr/bin/env python3
"""Compare wheel display during incremental preparation against direct rendering."""
import argparse
import ast
from pathlib import Path
import re
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True,help='Uncached frame_cells implementation')
p.add_argument('--source',type=Path,default=ROOT/'src/bg.c')
a=p.parse_args()
source=a.source.read_text()
def function(text,name):
    m=re.search(r'^(?:static )?(?:inline )?(?:void|bool|u16) '+name+r'\(',text,re.M)
    assert m,name
    return text[m.start():text.index('\n}\n',m.start())+3]
# Reuse the existing plane-comparison fixture declarations without executing it.
tree=ast.parse((ROOT/'tools/qa_wheel_delta.py').read_text())
prefix=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='PREFIX' for t in n.targets))
prefix=prefix.replace('const u16 *extra_tmpl;} BgFrames;','const u16 *extra_tmpl;u16 nframes;} BgFrames;').replace('f={0,0,11,8,maps,extra}','f={0,0,11,8,maps,extra,3}')
prefix=prefix.replace(',cache[56*4*17]', '').replace(',slots[128]', '')
prefix+='''
#include <stdlib.h>
typedef uint32_t u32;
#define BG_SLOTS 56
static u16 *fr_img,fr_render;static u8 fr_state;
static s16 fr_shown,fr_pending;static bool dirty_all,fail_allocation;
static void *MEM_alloc(unsigned n){return fail_allocation?NULL:malloc(n);}
'''
main=r'''
int main(void){
 unsigned checks=0;
 for(unsigned i=0;i<1024;i++){ordinary[i]=(i%5)?0xe000|(i&15):0;extra[i]=(i%3)?0x6000|(i&15):0;}
 for(unsigned failed=0;failed<2;failed++) for(unsigned h=1;h<=8;h++) for(unsigned wrap=0;wrap<16;wrap++) {
  f.h=h;f.w=11;f.cx=wrap;f.cy=wrap;fail_allocation=failed;
  for(unsigned i=0;i<128;i++)meta_slot[i]=(i%13)?i%56:255;
  for(unsigned i=0;i<3*h*11;i++)maps[i]=(i*17%128)|((i%4)<<14);
  memset(shadow,0x59,sizeof(shadow));u16 visible[2048],expected[2048];
  memcpy(visible,shadow,sizeof(shadow));memcpy(expected,shadow,sizeof(shadow));
  fr_img=0;fr_cells=0;fr_slots=0;fr_render=0;fr_state=3;
  fr_shown=fr_pending=fr_shadow_frame=-1;dirty_all=0;
  for(unsigned tick=0;tick<32;tick++) {
   /* Multiple requests exercise replacing a prepared image with a direct draw. */
   for(unsigned request=0;request<2;request++) {
    unsigned n=(tick*2+request)%4;
    bool ready=fr_state==2||(fr_state==3&&fr_img);
    bg_frames_show(n);
    if(ready&&n<3)reference_cells(n,expected,0,h);
    if(fr_pending>=0)assert(fr_state==2||fr_render>=(unsigned)(fr_pending+1)*(1+(h+1)/2));
   }
   if(fr_state==3&&frames_render())fr_state=2;
   if(fr_pending>=0){memcpy(visible,fr_img+fr_pending*2048,sizeof(visible));fr_pending=-1;dirty_all=0;}
   else if(dirty_all){memcpy(visible,shadow,sizeof(visible));dirty_all=0;}
   assert(!memcmp(visible,expected,sizeof(visible)));checks++;
  }
  assert(fr_state==2);free(fr_img);free(fr_cells);free(fr_slots);
 }
 printf("PASS: %u startup plane comparisons, all heights/flips/ring positions, partial images, repeated requests, and allocation failure\n",checks);
}
'''
plain=source[source.index('#define CW('):source.index('#undef CW')+len('#undef CW')]
reference=function(a.baseline.read_text(),'frame_cells').replace('frame_cells(','reference_cells(',1)
with tempfile.TemporaryDirectory() as td:
    root=Path(td);c=root/'probe.c'
    c.write_text('\n'.join([prefix,plain,function(source,'frame_orientation'),function(source,'cached_frame_cell'),reference,function(source,'frame_cells'),function(source,'frames_render'),function(source,'bg_frames_show'),main]))
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(c),'-o',str(root/'probe')],check=True)
    subprocess.run([str(root/'probe')],check=True)
