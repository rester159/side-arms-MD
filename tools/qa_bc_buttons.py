#!/usr/bin/env python3
"""Exhaustively compare BC's production input conversion with its bit contract."""
import ctypes
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
scene = (ROOT / 'src/bc_scene.c').read_text()
start = scene.index('static u8 buttons(u8 in)')
end = scene.index('\nstatic void ', start)
game = (ROOT / 'inc/game.h').read_text()
enum_start = game.index('enum {')
enum_end = game.index('};', enum_start) + 2
source = ('typedef unsigned char u8;\n' + game[enum_start:enum_end] + '\n' +
          scene[start:end] + '\nu8 convert(u8 in) { return buttons(in); }\n')
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory)
    (path / 'buttons.c').write_text(source)
    subprocess.run(['cc', '-std=c11', '-O3', '-Wall', '-Wextra', '-Werror',
                    '-shared', '-fPIC', str(path / 'buttons.c'), '-o',
                    str(path / 'buttons.dylib')], check=True)
    lib = ctypes.CDLL(str(path / 'buttons.dylib'))
    lib.convert.argtypes = [ctypes.c_ubyte]
    lib.convert.restype = ctypes.c_ubyte
    # Logical input bits: right, left, down, up, fire-left, fire-right,
    # weapon, start. BC bits: fire-right, fire-left, weapon, start,
    # up, right, down, left. Include opposing and simultaneous inputs.
    destinations = (5, 7, 6, 4, 1, 0, 2, 3)
    for value in range(256):
        expected = sum(1 << target for bit, target in enumerate(destinations)
                       if value & (1 << bit))
        assert lib.convert(value) == expected, (value, expected)
print('PASS: all 256 logical held/pressed input combinations preserve BC bits')
