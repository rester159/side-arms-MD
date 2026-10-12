#!/usr/bin/env python3
"""Control-flow regression checks for duplicated hoisted frame-call setup."""
from bc_scene_boundary import _verified_hoisted_paths

rom = bytearray(64)
rom[24:26] = b'\x4e\x93'
# Both arms initialize A3 before the shared call, then the frame loop repeats.
code = [(0,'beqs','0xc'), (2,'lea','0x100,%a3'), (8,'bras','0x18'),
        (12,'lea','0x100,%a3'), (18,'bras','0x18'),
        (24,'jsr','%a3@'), (26,'bras','0x18')]
loads = [(2,'a3'), (12,'a3')]
assert _verified_hoisted_paths(code, loads, rom) == [26]

def rejects(candidate, message):
    try:
        _verified_hoisted_paths(candidate, loads, rom)
    except AssertionError:
        return
    raise AssertionError(message)

rejects([(0,'beqs','0x18')] + code[1:], 'accepted branch bypassing both loads')
rejects(code[:4] + [(18,'moveal','%d0,%a3')] + code[5:], 'accepted register overwrite')
rejects(code[:4] + [(18,'moveml','%sp@+,%d2-%a6')] + code[5:], 'accepted implicit register restore')
rejects(code[:2] + [(8,'jmp','%a0@')] + code[3:], 'accepted unverified indirect branch')
print('PASS: shared initialized loop; reject bypass, overwrite, MOVEM restore and indirect branch')
