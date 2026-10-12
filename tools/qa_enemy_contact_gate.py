#!/usr/bin/env python3
"""Compare the actual Normal body-contact gate against a saved prior source.

This isolates dispatch and owner order; pickup/death implementations are stubbed
at their call boundary. Native replay separately covers integrated game state.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline', type=Path, required=True)
a = p.parse_args()

def body(path):
    text = path.read_text().split('contact:\n', 1)[1]
    return text.split('\n}\n', 1)[0]

prefix = r'''
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int16_t s16;
typedef int bool;
typedef struct { u8 state, invuln; } Player;
typedef struct { u8 flags,item,box[4],r[10]; s16 y; } Enemy;
#define PL_ALIVE 2
#define EF_NOCONTACT 2
#define AY(e) ((u8)((e)->y + 16))
#define X2(e) ((e)->r[7])
static Player players[4];
static u8 pl_alive[4],pl_y[4],pl_x2[4],limit;
static unsigned log_events;
static u16 game_player_limit(void) { return limit; }
static u16 absdiff(s16 a,s16 b) { return a>b?a-b:b-a; }
static void en_pickup(Enemy *e,Player *p) { (void)e; log_events=0x100+(p-players); }
static void player_kill(Player *p) { log_events=0x200+(p-players); }
static void en_kill_by(Enemy *e,Player *p) { (void)e; log_events=log_events*16+(p-players); }
'''
main = r'''
static uint32_t seed=0x4c017ac;
static uint32_t rnd(void) { seed^=seed<<13;seed^=seed>>17;seed^=seed<<5;return seed; }
int main(void) {
    unsigned pickups=0,protected_pickups=0,kills=0;
    for(unsigned n=0;n<1000000;n++) {
        Enemy e={0};limit=1+n%4;bool big=(n/4)%2;
        e.flags=(rnd()%8==0)?2:0;e.item=rnd()%3;
        e.y=(s16)rnd();e.r[7]=rnd();e.box[2]=rnd();e.box[3]=rnd();
        for(unsigned i=0;i<4;i++) {
            pl_alive[i]=rnd()%2;players[i].state=(rnd()%4)?2:0;
            players[i].invuln=(rnd()%2)?(1+rnd()%255):0;
            pl_y[i]=rnd();pl_x2[i]=rnd();
            if(n%3==0) { pl_y[i]=(u8)(AY(&e)-(big?0:8));pl_x2[i]=(u8)(X2(&e)-(big?0:4)); }
        }
        log_events=0;reference(&e,big);unsigned expected=log_events;
        log_events=0;candidate(&e,big);
        if(expected!=log_events) { fprintf(stderr,"case %u: %x != %x\n",n,expected,log_events);return 1; }
        if(expected>=0x100 && expected<0x104) {
            pickups++;protected_pickups+=!!players[expected-0x100].invuln;
        } else if(expected) kills++;
    }
    assert(pickups && protected_pickups && kills);
    printf("PASS: 1000000 contact gates, %u pickups (%u protected), %u kills; 1-4P, small/big, stale alive flags, wrapped coordinates\n",pickups,protected_pickups,kills);
}
'''
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory)
    source=prefix+'\nstatic void reference(Enemy *e,bool big) {\n'+body(a.baseline)+'\n}\n'
    source+='static void candidate(Enemy *e,bool big) {\n'+body(ROOT/'src/enemies.c')+'\n}\n'+main
    (d/'gate.c').write_text(source)
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror',str(d/'gate.c'),'-o',str(d/'gate')],check=True)
    subprocess.run([str(d/'gate')],check=True)
