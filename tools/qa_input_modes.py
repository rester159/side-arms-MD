#!/usr/bin/env python3
"""Exercise the production physical-button mapper with both player-arena modes."""
import subprocess,tempfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'src/input.c').read_text()
s=s[s.index('static const u16 PB_BIT'):s.index('\nvoid input_update')]
prefix=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;typedef uint16_t u16;typedef int bool;
#define MAX_PLAYERS 4
#define BUTTON_A 1
#define BUTTON_B 2
#define BUTTON_C 4
#define BUTTON_X 8
#define BUTTON_Y 16
#define BUTTON_Z 32
#define BUTTON_RIGHT 64
#define BUTTON_LEFT 128
#define BUTTON_UP 256
#define BUTTON_DOWN 512
#define BUTTON_START 1024
enum {IN_RIGHT=1,IN_LEFT=2,IN_DOWN=4,IN_UP=8,IN_FIRE_L=16,IN_FIRE_R=32,IN_WEAPON=64,IN_START=128};
enum {PB_A,PB_B,PB_C,PB_X,PB_Y,PB_Z,PB_COUNT};
enum {ACT_FIRE_L,ACT_FIRE_R,ACT_WEAPON,ACT_COUNT};
enum {XB_NONE,XB_PREV,XB_NEXT,XB_LOCK,XB_COUNT};
enum {PL_ALIVE=1,WPN_AUTO=4};
typedef struct {u8 button[3],extra[3],autofire[2];} PadConfig;
typedef struct {u8 facing_left,in_play,state,weapon,combined;} Player;
typedef struct {struct {struct {struct {u8 facing;} charge;} weapons;u8 state;} world;} BcPlayerControl;
typedef union {Player normal[4];BcPlayerControl bc;} PlayerArena;
static PlayerArena player_arena;
#define normal_players player_arena.normal
static BcPlayerControl extra[3],*peers;
static u16 players_bc_count;
static u8 combined,pad_weapon_req[4],pad_fire_held[4];static bool pad_six[4];static PadConfig pad_cfg;
static bool player_is_combined(const Player*p){return p->combined;}
'''
main=r'''
int main(void){
 unsigned checks=0;
 for(unsigned count=1;count<=4;count++){
  memset(&player_arena,0,sizeof player_arena);memset(extra,0,sizeof extra);
  players_bc_count=count;peers=count>1?extra:0;
  for(unsigned i=0;i<4;i++){
   BcPlayerControl*p=i&&i<count?&peers[i-1]:&player_arena.bc;
   for(unsigned alive=0;alive<2;alive++)for(unsigned enabled=0;enabled<2;enabled++){
    input_defaults(&pad_cfg);pad_cfg.autofire[0]=pad_cfg.autofire[1]=enabled;p->world.state=alive?0x80:0;
    memset(af_t,0,sizeof af_t);
    for(unsigned tick=0;tick<32;tick++){
     u8 actual=map(i,BUTTON_A|BUTTON_B,0);
     u8 expected=(alive&&enabled&&i<count&&(tick&2))?0:IN_FIRE_L|IN_FIRE_R;
     assert(actual==expected);assert(pad_fire_held[i]==(IN_FIRE_L|IN_FIRE_R));checks++;
    }
   }
   input_defaults(&pad_cfg);pad_six[i]=1;
   for(unsigned facing=0;facing<2;facing++){
    p->world.weapons.charge.facing=facing;
    assert(map(i,BUTTON_Z,0)==((i<count&&!facing)?IN_FIRE_L:IN_FIRE_R));checks++;
   }
   pad_six[i]=0;
  }
 }
 players_bc_count=0;peers=0;
 for(unsigned i=0;i<4;i++)for(unsigned combo=0;combo<3;combo++)for(unsigned auto_weapon=0;auto_weapon<2;auto_weapon++){
  Player*p=&normal_players[i];*p=(Player){0,1,PL_ALIVE,auto_weapon?WPN_AUTO:0,combo!=0};
  combined=combo==1?i+1:0;input_defaults(&pad_cfg);pad_cfg.autofire[1]=1;memset(af_t,0,sizeof af_t);
  for(unsigned tick=0;tick<32;tick++){
   assert(map(i,BUTTON_B,0)==((!auto_weapon&&combo!=2&&(tick&2))?0:IN_FIRE_R));checks++;
  }
 }
 printf("PASS: %u mapper checks; BC 1-4P, inactive slots, facing lock, held charge, Normal AUTO and combined leader/ring\n",checks);
}
'''
with tempfile.TemporaryDirectory() as td:
 p=Path(td);(p/'test.c').write_text(prefix+s+main)
 subprocess.run(['cc','-std=c99','-fsanitize=address,undefined','-g',str(p/'test.c'),'-o',str(p/'test')],check=True)
 subprocess.run([str(p/'test')],check=True)
