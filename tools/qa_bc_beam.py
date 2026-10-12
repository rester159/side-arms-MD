#!/usr/bin/env python3
"""Differential test of native BC charged-beam flight against full PCE RAM traces.
This exercises launch, animation, spacing and retirement, not enemy damage.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class Beam(C.Structure):
    _fields_ = [('x', C.c_uint32), ('y', C.c_uint32),
                ('vx', C.c_int16), ('vy', C.c_int16),
                ('sprite', C.c_uint16), ('attributes', C.c_uint16)] + [
                    (n, C.c_uint8) for n in ('state', 'timer', 'flags', 'damage',
                    'half_x', 'half_y', 'delay', 'accelerating', 'facing')]


def decode(ram, slot):
    def word(hi, lo): return ram[hi + slot] * 256 + ram[lo + slot]
    def signed(v): return v if v < 32768 else v - 65536
    return Beam(word(0xa66, 0xa84) * 256 + ram[0xaa2+slot],
                word(0xac0, 0xade) * 256 + ram[0xafc+slot],
                signed(word(0xb92, 0xbb0)), signed(word(0xbce, 0xbec)),
                word(0xb56, 0xb74), word(0xb1a, 0xb38),
                ram[0xa48+slot], ram[0xc64+slot], ram[0xc46+slot],
                ram[0xc82+slot], ram[0xca0+slot], ram[0xcbe+slot],
                ram[0xdcc+slot], word(0xcdc, 0xcfa) == 0x998a,
                ram[0xac] == 0x52)


def verify(capture):
    raw = (capture / 'state.bin').read_bytes()
    stride = 8196
    assert raw and len(raw) % stride == 0, 'Truncated RAM trace'
    records = [(struct.unpack_from('<I', raw, i)[0], raw[i+4:i+stride])
               for i in range(0, len(raw), stride)]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'rules.dylib'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-I'+str(ROOT/'inc'), str(ROOT/'src/bc_rules.c'),
                        '-o', str(path)], check=True)
        lib = C.CDLL(str(path))
        lib.bc_beam_launch.argtypes = [C.POINTER(Beam), C.c_uint8, C.c_uint8,
                                      C.c_uint16, C.c_uint16]
        lib.bc_beam_step.argtypes = [C.POINTER(Beam)]
        slots = (Beam * 5)(*(decode(records[0][1], i+20) for i in range(5)))
        launches = []; active_frames = 0; retirements = 0
        for (old_frame, old), (frame, ram) in zip(records, records[1:]):
            assert frame == old_frame + 1
            if old[0x56] >= 40 and not ram[0x56] and not any(b.state for b in slots):
                segments = 5 if old[0x56] >= 60 else 4 if old[0x56] >= 50 else 3
                right = ram[0xaa] == 0x52
                lib.bc_beam_launch(slots, segments, right,
                                   ram[0x95]*256+ram[0x96], ram[0x98]*256+ram[0x99])
                launches.append(dict(frame=frame, segments=segments, right=right))
            for i, beam in enumerate(slots):
                was_active = bool(beam.state)
                lib.bc_beam_step(C.byref(beam))
                expected = decode(ram, i+20)
                assert beam.state == expected.state, (frame, i, 'state', beam.state, expected.state)
                if was_active:
                    active_frames += 1
                    retirements += not beam.state
                    for field, _ in Beam._fields_:
                        # Facing is shared state; ignored on unused slots only.
                        actual, want = getattr(beam, field), getattr(expected, field)
                        assert actual == want, (frame, i, field, actual, want)
        assert {(x['segments'], x['right']) for x in launches} == {
            (n, d) for n in (3, 4, 5) for d in (False, True)}, 'Missing length/direction cases'
        assert retirements == sum(x['segments'] for x in launches)
        return dict(module='charged beam launch and flight only', launches=launches,
                    active_slot_updates=active_frames, retirements=retirements,
                    whole_game_verified=False)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(verify(a.capture), indent=2))
