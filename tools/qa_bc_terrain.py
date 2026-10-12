#!/usr/bin/env python3
"""Check the optimized terrain lookup over world cells and 16-bit wrapping."""
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = r'''
#include "bc_rules.h"
#include <stdio.h>
static unsigned char cells[16384], attributes[2048];
static unsigned char reference(unsigned short x, unsigned short y)
{
    x &= 4095; y &= 4095;
    unsigned short cell = ((x >> 5) & 7) | (((y >> 5) & 7) << 3) |
        (((x >> 8) & 15) << 6) | (((y >> 8) & 15) << 10);
    unsigned short quadrant = ((x & 16) >> 3) | ((y & 16) >> 2);
    return attributes[cells[cell] * 8 + quadrant + 1] & 15;
}
int main(void)
{
    unsigned int seed = 1, checked = 0;
    for (unsigned int i = 0; i < sizeof(cells); i++) {
        seed = seed * 1664525u + 1013904223u; cells[i] = seed >> 24;
    }
    for (unsigned int i = 0; i < sizeof(attributes); i++) {
        seed = seed * 1664525u + 1013904223u; attributes[i] = seed >> 24;
    }
    BcTerrain terrain = {cells, attributes};
    /* Every 16-bit value on each axis against all 256 subcell rows/columns.
     * Includes negative-coordinate wrapping, all world blocks and quadrants,
     * and every within-subcell offset. */
    for (unsigned int axis = 0; axis < 2; axis++)
        for (unsigned int a = 0; a < 65536; a++)
            for (unsigned int b = 0; b < 4096; b += 16) {
                unsigned short x = axis ? b : a, y = axis ? a : b;
                if (bc_terrain_solid(&terrain, x, y) != reference(x, y)) {
                    fprintf(stderr, "Terrain mismatch at %u,%u\n", x, y); return 1;
                }
                checked++;
            }
    printf("{\"terrain_probes\":%u,\"status\":\"PASS\"}\n", checked);
    return 0;
}
'''

with tempfile.TemporaryDirectory() as directory:
    source = Path(directory) / 'terrain.c'
    binary = Path(directory) / 'terrain'
    source.write_text(SOURCE)
    subprocess.run(['cc', '-O2', '-std=c99', '-Wall', '-Wextra', '-Werror',
                    '-I'+str(ROOT/'inc'), str(source), str(ROOT/'src/bc_rules.c'),
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
