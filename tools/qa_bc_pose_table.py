#!/usr/bin/env python3
"""Compare production pose selection against an independent saved selector."""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
a=p.parse_args()
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory)
    s=a.baseline.read_text().replace('bc_actor_pose','reference_pose').replace('bc_actor_sprite','reference_sprite')
    (d/'reference.c').write_text(s)
    (d/'verify.c').write_text(r'''
#include "bc_actor_art.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
unsigned int reference_pose(const BcActor *);
static unsigned long checks;
static void check(BcActor *a) {
    BcActor copy=*a;
    unsigned int got=bc_actor_pose(a),want=reference_pose(a);
    if(got!=want) {
        fprintf(stderr,"ref=%04x base=%04x sprite=%04x attr=%04x flags=%02x state=%02x got=%08x want=%08x\n",
          a->sprite_base_ref,a->body.sprite_base,a->body.sprite,a->body.attributes,a->body.flags,a->body.state,got,want);
        assert(got==want);
    }
    assert(!memcmp(a,&copy,sizeof(copy)));checks++;
}
int main(void) {
    BcActor a={0};a.body.state=128;a.body.sprite_base=0x200;
    // Every bank ID, including odd/unsupported/wrapped identifiers.
    for(unsigned ref=0;ref<65536;ref++) {
        a.sprite_base_ref=ref;
        for(unsigned frame=0;frame<64;frame+=2) {a.body.sprite=0x200+frame;check(&a);}
    }
    // Every 16-bit source frame, including subtraction wrap and hidden sentinels.
    for(unsigned ref=0x367a;ref<=0x36d4;ref++) {
        a.sprite_base_ref=ref;
        for(unsigned frame=0;frame<65536;frame++) {
            a.body.sprite=frame;
            for(unsigned flip=0;flip<4;flip++) {a.body.attributes=15|(flip&1?0x800:0)|(flip&2?0x8000:0);check(&a);}
        }
    }
    // All attribute bits, not only the currently used palette/flip fields.
    for(unsigned ref=0x367a;ref<=0x36d4;ref+=2) {
        a.sprite_base_ref=ref;
        for(unsigned attr=0;attr<65536;attr++) {
            a.body.attributes=attr;
            for(unsigned frame=0;frame<64;frame+=8) {a.body.sprite=0x200+frame;check(&a);}
        }
    }
    for(unsigned state=0;state<256;state++) for(unsigned flags=0;flags<256;flags++) {
        a.body.state=state;a.body.flags=flags;
        for(unsigned i=0;i<4;i++){a.body.sprite=(unsigned short[]){0,255,0x200,0x208}[i];check(&a);}
    }
    printf("PASS: %lu exact packed poses; all source banks, frame words, attributes, states and flags; simulation unchanged\n",checks);
}
''')
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'inc'),str(d/'verify.c'),str(d/'reference.c'),str(ROOT/'src/bc_actor_art.c'),'-o',str(d/'verify')],check=True)
    subprocess.run([str(d/'verify')],check=True)
