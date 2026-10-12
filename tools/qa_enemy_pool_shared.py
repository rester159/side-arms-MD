#!/usr/bin/env python3
"""Check shared allocation against independent typed scans, with sanitizers."""
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CODE = r'''
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "enemy_storage.h"
#include "enemy_pool.h"

static unsigned rng = 0x369ab127u;
static unsigned next(void) { rng ^= rng << 13; rng ^= rng >> 17; rng ^= rng << 5; return rng; }
static unsigned checked;

static void normal(Enemy *records, unsigned capacity)
{
    Enemy saved[N_SMALL];
    memcpy(saved, records, capacity * sizeof(*records));
    for (unsigned reverse = 0; reverse < 2; ++reverse) {
        int want = -1;
        for (unsigned i = 0; i < capacity; ++i) {
            unsigned slot = reverse ? capacity - i - 1 : i;
            if (!saved[slot].live) { want = slot; break; }
        }
        int got = enemy_pool_free(records, sizeof(*records), offsetof(Enemy, live), capacity, reverse);
        if (got != want || memcmp(saved, records, capacity * sizeof(*records))) abort();
        ++checked;
    }
}

static void bc(BcActor *records)
{
    BcActor saved[BC_ACTOR_CAPACITY];
    memcpy(saved, records, sizeof(saved));
    for (unsigned reverse = 0; reverse < 2; ++reverse) {
        int want = -1;
        for (unsigned i = 0; i < BC_ACTOR_CAPACITY; ++i) {
            unsigned slot = reverse ? BC_ACTOR_CAPACITY - i - 1 : i;
            if (!saved[slot].body.state) { want = slot; break; }
        }
        int got = enemy_pool_free(records, sizeof(*records), offsetof(BcActor, body.state), BC_ACTOR_CAPACITY, reverse);
        if (got != want || memcmp(saved, records, sizeof(saved))) abort();
        ++checked;
    }
}

int main(void)
{
    struct { unsigned guard[8]; EnemyArena arena; unsigned tail[8]; } storage;
    memset(&storage, 0xa5, sizeof(storage));
    static const unsigned capacities[] = {0,1,8,9,16,24,32,40};
    for (unsigned trial = 0; trial < 20000; ++trial) {
        /* Both mode views are exercised successively in the same arena.
         * Empty/full, every individual free slot, and randomized occupancy. */
        memset(&storage.arena, 0x5a, sizeof(storage.arena));
        for (unsigned i = 0; i < N_SMALL; ++i)
            storage.arena.normal.small[i].live = trial == 0 ? 0 :
                trial == 1 ? 255 : trial < 42 ? i != trial - 2 : (next() & 7 ? next() | 1 : 0);
        for (unsigned i = 0; i < sizeof(capacities)/sizeof(capacities[0]); ++i)
            normal(storage.arena.normal.small, capacities[i]);
        memset(&storage.arena, 0x5a, sizeof(storage.arena));
        for (unsigned i = 0; i < BC_ACTOR_CAPACITY; ++i)
            storage.arena.bc[i].body.state = trial == 0 ? 0 :
                trial == 1 ? 255 : trial < 34 ? i != trial - 2 : (next() & 7 ? next() | 1 : 0);
        bc(storage.arena.bc);
        for (unsigned i = 0; i < 8; ++i)
            if (storage.guard[i] != 0xa5a5a5a5u || storage.tail[i] != 0xa5a5a5a5u) abort();
    }
    printf("PASS %u typed allocation checks; arena transitions, empty/full pools, all free slots, arbitrary nonzero states, no writes; sanitizers enabled\n", checked);
}
'''

with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    (tmp / 'genesis.h').write_text('typedef unsigned char u8; typedef signed char s8; typedef unsigned short u16; typedef signed short s16;\n')
    (tmp / 'probe.c').write_text(CODE)
    subprocess.run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                    '-I' + str(tmp), '-I' + str(ROOT / 'inc'),
                    str(tmp / 'probe.c'), '-o', str(tmp / 'probe')], check=True)
    subprocess.run([str(tmp / 'probe')], check=True)
