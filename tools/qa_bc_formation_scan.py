#!/usr/bin/env python3
"""Compare the production formation/segment allocation scan with a simple exhaustive search."""
import argparse
from pathlib import Path
import subprocess
import tempfile
ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--size', type=int, choices=(5, 8), default=5)
size = parser.parse_args().size
source = (ROOT/'src/bc_runtime.c').read_text()
start = source.index('    unsigned char slot = 0;', source.index(' formation_birth(' if size == 5 else ' segment_birth('))
end = source.index(f'    for (unsigned char i = 0; i < {size}; i++)', start)
scan = source[start:end]
with tempfile.TemporaryDirectory() as directory:
    tmp = Path(directory)
    code = '#include "bc_world.h"\n#include <assert.h>\n#include <stdint.h>\n#include <stdio.h>\n'
    code += f'#define RUN_SIZE {size}\n'
    code += 'static int actual(const BcActor *actors) {\n' + scan + 'return slot;\n}\n'
    code += r'''
static unsigned long checks;
static void check(uint32_t mask) {
    BcActor actors[32] = {0};
    for (unsigned i = 0; i < 32; i++) actors[i].body.state = (mask >> i & 1) ? (i % 3 == 0 ? 0x40 : i % 3 == 1 ? 0x80 : 0xff) : 0;
    int expected = -1;
    for (unsigned i = 0; i <= 32 - RUN_SIZE; i++) if (!(mask >> i & ((1u << RUN_SIZE) - 1))) { expected = i; break; }
    assert(actual(actors) == expected);
    for (unsigned i = 0; i < 32; i++) assert(!!actors[i].body.state == !!(mask >> i & 1));
    checks++;
}
int main(void) {
    for (unsigned shift = 0; shift <= 16; shift++)
        for (uint32_t mask = 0; mask < 65536; mask++) {
            check(mask << shift);
            check((mask << shift) | ~(UINT32_C(65535) << shift));
        }
    uint32_t seed = 0xbc12345;
    for (unsigned i = 0; i < 1000000; i++) {
        seed ^= seed << 13; seed ^= seed >> 17; seed ^= seed << 5;
        check(seed);
    }
    printf("PASS: %lu occupancy patterns; first free run, mixed live states, boundaries and nonmutation\n", checks);
}
'''
    (tmp/'scan.c').write_text(code)
    subprocess.run(['cc','-std=c99','-O2','-Wall','-Wextra','-Werror','-I'+str(ROOT/'inc'),str(tmp/'scan.c'),'-o',str(tmp/'scan')],check=True)
    subprocess.run([str(tmp/'scan')],check=True)
