#!/usr/bin/env python3
"""Exhaustively check private party targeting, including scheduler wrap."""
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    source = Path(directory)/'target.c'
    binary = Path(directory)/'target'
    source.write_text(r'''
#include "bc_party.c"
#include <assert.h>
#include <stdio.h>
int main(void) {
    BcPlayerControl players[4] = {0};
    BcPartyControl party = {0};
    unsigned long cases = 0;
    for (unsigned n = 2; n <= 4; n++) {
        party.contacts.count = n;
        for (unsigned i = 0; i < n; i++) party.players[i] = &players[i];
        for (unsigned clock = 0; clock < 256; clock++)
            for (unsigned alive = 0; alive < (1u << n); alive++)
                for (unsigned waiting = 0; waiting < (1u << n); waiting++) {
                    party.waiting = waiting;
                    for (unsigned i = 0; i < n; i++)
                        players[i].world.state = alive & (1u << i) ? 0x80 : 0x40;
                    unsigned expected = 0;
                    for (unsigned j = 0; j < n; j++) {
                        unsigned i = ((clock / 8) + j) % n;
                        if ((alive & (1u << i)) && !(waiting & (1u << i))) {
                            expected = i; break;
                        }
                    }
                    assert(target(&party, clock) == &players[expected].world);
                    cases++;
                }
    }
    printf("PASS: %lu target selections, all clocks/living/waiting combinations\n", cases);
}
''')
    names = ('bc_rules','bc_world','bc_stage','bc_runtime','bc_frame','bc_wave',
             'bc_wave_queue','bc_score','bc_player','bc_palette','bc_audio')
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror',
                    '-I'+str(ROOT/'inc'),'-I'+str(ROOT/'src'),str(source),
                    *(str(ROOT/'src'/f'{name}.c') for name in names),
                    '-o',str(binary)],check=True)
    subprocess.run([str(binary)],check=True)
