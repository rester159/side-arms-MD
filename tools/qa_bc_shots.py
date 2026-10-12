#!/usr/bin/env python3
"""Compare native spread-weapon launch/flight with full Before Christ RAM traces.
The fixture selects five power tiers and both firing directions for weapons 0/1.
"""
import argparse
import csv
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile
from qa_bc_beam import Beam, decode, ROOT
from qa_bc_rules import Terrain


class Shot(C.Structure):
    _fields_ = [('body', Beam)] + [(n, C.c_uint8) for n in ('kind', 'tier', 'phase', 'animation', 'launch_wait')]


def verify(capture, code):
    raw = (capture / 'state.bin').read_bytes()
    assert raw and len(raw) % 8196 == 0
    records = [(struct.unpack_from('<I', raw, i)[0], raw[i+4:i+8196]) for i in range(0, len(raw), 8196)]
    hits = {}
    # Enemy simulation is not ported yet. Replay only the source's explicitly
    # traced enemy-contact notifications after native projectile updates.
    for row in csv.DictReader((capture / 'writes.csv').open()):
        if row['pc'] == 'a0ba' and row['value'] == '40':
            slot = int(row['address'], 16) - 0x1f0a48
            hits.setdefault(int(row['frame']), []).append(slot)
    program = code.read_bytes()
    # The CD links player code at different addresses in some rounds.
    signature = bytes.fromhex('bdcc2df0273a9dcc2dd02c')
    assert program.count(signature) == 1, 'Cannot locate the spread update routine'
    relocation = program.index(signature) + 0x4000 - 0x9204
    custom_routines = tuple(a + relocation for a in (0x9204, 0x9399, 0x923e, 0x9413))
    data = (C.c_uint8 * len(program)).from_buffer_copy(program)
    cells = (C.c_uint8 * 16384).from_buffer_copy(program[0xc000:])
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'rules.dylib'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                        '-I'+str(ROOT/'inc'), str(ROOT/'src/bc_rules.c'), '-o', str(path)], check=True)
        lib = C.CDLL(str(path))
        lib.bc_shot_fire.argtypes = [C.POINTER(Shot)] + [C.c_uint8]*3 + [C.c_uint16]*2
        lib.bc_shot_fire.restype = C.c_uint8
        lib.bc_shot_hit.argtypes = [C.POINTER(Shot)]
        lib.bc_shot_step.argtypes = [C.POINTER(Shot), C.c_uint16, C.c_uint16, C.POINTER(Terrain)]
        slots = (Shot * 28)()
        for i in range(28): slots[i].body = decode(records[0][1], i)
        launches = []; updates = 0; retirements = 0; terrain_impacts = 0; expansions = 0
        for (previous, old), (frame, ram) in zip(records, records[1:]):
            assert frame == previous + 1 and ram[0x4b] == records[0][1][0x4b]
            if ram[0x94] == 0x80 and not ram[0xad] and ram[0x228] & 3 in (1, 2) and ram[0x22d] & 3:
                n = lib.bc_shot_fire(slots, ram[0xa5], ram[0xae], ram[0xaa] == 0x52,
                                     ram[0x95]*256+ram[0x96], ram[0x98]*256+ram[0x99])
                launches.append(dict(frame=frame, kind=ram[0xa5], power=ram[0xae], right=ram[0xaa] == 0x52, shots=n))
            attrs = old[0x44] + old[0x45]*256 - 0xa000 + 0x6000
            terrain = Terrain(cells, C.cast(C.byref(data, attrs), C.POINTER(C.c_uint8)))
            cx, cy = ram[0x2e]*256+ram[0x2f], ram[0x31]*256+ram[0x32]
            for i, shot in enumerate(slots):
                active = bool(shot.body.state)
                old_phase = shot.phase
                lib.bc_shot_step(C.byref(shot), cx, cy, C.byref(terrain))
                terrain_impacts += old_phase == 0 and shot.phase == 1
                expansions += old_phase == 0 and shot.phase == 2
                if i in hits.get(frame, []):
                    assert shot.body.state == 0x80, (frame, i, 'contact needs a flying shot')
                    lib.bc_shot_hit(C.byref(shot))
                expected = decode(ram, i)
                expected.facing = ram[0xdae+i] == 0x52
                routine = ram[0xcdc+i]*256 + ram[0xcfa+i]
                expected.accelerating = routine in custom_routines
                assert shot.body.state == expected.state, (frame, i, 'state', shot.body.state, expected.state)
                if active:
                    updates += 1; retirements += not shot.body.state
                    for field, _ in Beam._fields_:
                        actual, want = getattr(shot.body, field), getattr(expected, field)
                        assert actual == want, (frame, i, field, actual, want)
        assert {(x['kind'], x['power'], x['right']) for x in launches} == {
            (k, p, d) for k in (0,1) for p in (0,1,3,7,15) for d in (False, True)}
        assert retirements == sum(x['shots'] for x in launches)
        return dict(module='weapons 0/1 launch, flight and terrain only', launches=launches,
                    active_slot_updates=updates, retirements=retirements,
                    replayed_enemy_contacts=sum(len(v) for v in hits.values()),
                    terrain_impacts=terrain_impacts, expansions=expansions,
                    limited_volleys=sum(x['shots'] < 5 for x in launches if x['power'] == 15),
                    whole_game_verified=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    p.add_argument('--code', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(verify(a.capture, a.code), indent=2))
