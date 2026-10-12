#!/usr/bin/env python3
"""Protected crushes stay at the screen edge; ordinary crushes still kill."""
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path
from qa_bc_player_flow import Control, Event, Data, Terrain, ROOT

with tempfile.TemporaryDirectory() as directory:
    library = Path(directory) / 'player.dylib'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    '-I' + str(ROOT / 'inc'),
                    *(str(ROOT / f'src/{name}.c') for name in ('bc_rules', 'bc_world', 'bc_player')),
                    '-o', str(library)], check=True)
    lib = C.CDLL(str(library))
    lib.bc_player_control.argtypes = [C.POINTER(Control), C.c_uint8] + [C.c_uint16]*4 + [C.POINTER(Terrain), C.POINTER(Data), C.c_uint16]
    lib.bc_player_control.restype = Event
    protection = C.c_uint8.in_dll(lib, 'bc_damage_disabled')
    cells = (C.c_uint8 * 16384)()
    attributes = (C.c_uint8 * 2048)(*([1]*2048))
    terrain = Terrain(cells, attributes)
    data = Data(cells, 0)
    checked = 0
    for protected in (0, 1):
        protection.value = protected
        for axis in (0, 1):
            for scroll in (1, 128, 256, 768):
                p = Control(); p.world.state = 0x80
                p.world.x, p.world.y = 16 << 8, 32 << 8
                for tick in range(512 if protected else 1):
                    event = lib.bc_player_control(C.byref(p), 0, 0, 0,
                        scroll if axis == 0 else 0, scroll if axis == 1 else 0,
                        C.byref(terrain), C.byref(data), 0)
                    if protected:
                        assert (p.world.x, p.world.y, p.world.state, event.sound) == (4096, 8192, 0x80, 0)
                    else:
                        assert p.world.state == 0x40 and event.sound == 3
                    checked += 1
    print(json.dumps(dict(passed=True, control_updates=checked, axes=2,
                         protected_stays_in_bounds=True, ordinary_crush_still_kills=True)))
