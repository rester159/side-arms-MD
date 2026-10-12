#!/usr/bin/env python3
"""Compare production multiplayer HUD draw commands against an archived cache."""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
header=(ROOT/'inc/hud.h').read_text();types=header[header.index('enum { HUD_MSG_NONE'):header.index('void hud_panel(const')]
prefix=r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int16_t s16;typedef uint32_t u32;typedef u8 bool;
#define TRUE 1
#define MAX_PLAYERS 4
#define HUD_COLS 40
#define HUD_ROWS_GAME 0xe000007
static struct {u32 score;u8 lives,weapon,speed;} players[4];
typedef __typeof__(players[0]) Player;
static u16 limit=4;static u16 game_player_limit(void){return limit;}
static void hud_clear(u32 r){printf("clear %u\n",r);}
static void hud_blank(s16 c,s16 r,u16 n){printf("blank %d %d %u\n",c,r,n);}
static void hud_text(s16 c,s16 r,u8 col,const char *s){printf("text %d %d %u %s\n",c,r,col,s);}
static void hud_number(s16 c,s16 r,u8 col,u32 n,u16 w){printf("number %d %d %u %u %u\n",c,r,col,n,w);}
static void hud_score(s16 c,s16 r,u8 col,u32 n){printf("score %d %d %u %u\n",c,r,col,n);}
static void hud_codes(s16 c,s16 r,u8 col,const u16 *s,u16 n){printf("codes %d %d %u",c,r,col);for(u16 i=0;i<n;i++)printf(" %u",s[i]);puts("");}
'''
main=r'''
int main(void){
 HudPanel p={0};u32 rng=1234567;
 for(u16 tick=0;tick<4000;tick++){
  if(!(tick%127)){cur.on=0;limit=3+(tick%2);}
  if(!(tick%3)){
   rng=rng*1664525+1013904223;p.boss_bars=(rng>>24)%10;
   for(u16 i=0;i<4;i++){
    rng=rng*1664525+1013904223;
    p.pl[i]=(HudPlayer){rng&1,(rng>>1)&1,(rng>>2)&3,(rng>>4)%11,{(rng>>8)%40,(rng>>12)%40,(rng>>16)%40},(rng>>20)&1,(rng>>21)%9};
    players[i]=(Player){rng%10000000,(rng>>5)%10,(rng>>10)%6,(rng>>15)%4};
   }
  }
  printf("tick %u\n",tick);multiplayer_panel(&p);
 }
}
'''
outputs=[]
with tempfile.TemporaryDirectory() as td:
 for i,path in enumerate((a.baseline,ROOT/'src/hud.c')):
  source=path.read_text();start=source.index('static struct {',source.index('#define COL_P'))
  cur=source[start:source.index('} cur;',start)+6]
  start=source.index('static void multiplayer_panel(');end=source.index('\nvoid hud_panel(',start)
  extra=''
  if '} multi_cur[MAX_PLAYERS];' in source:
   pos=source.index('} multi_cur[MAX_PLAYERS];');begin=source.rfind('static struct {',0,pos);extra=source[begin:pos+len('} multi_cur[MAX_PLAYERS];')]
  c=Path(td)/f'case{i}.c';exe=c.with_suffix('');c.write_text(prefix+types+cur+extra+source[start:end]+main)
  subprocess.run(['cc','-std=gnu99','-O2','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True)
  outputs.append(subprocess.check_output([str(exe)]))
assert outputs[0]==outputs[1], 'HUD command sequence differs'
print('PASS: 4000 HUD frames match every draw command; 3P/4P, resets, unchanged frames, scores, lives, energy, names, continue/game-over, weapons, speed and boss bars')
