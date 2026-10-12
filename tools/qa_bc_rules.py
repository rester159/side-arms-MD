#!/usr/bin/env python3
"""Compare native Before Christ rules against captured PC Engine observations.

Inputs remain local: a pce_oracle capture with logic.bin, and its runtime code
dump. This checks the small ported rule module, not whole-game equivalence.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import struct
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


class Charge(C.Structure):
    _fields_ = [(name, C.c_uint8) for name in ('charge', 'held', 'latch', 'facing')]


class Event(C.Structure):
    _fields_ = [('beam', C.c_uint8), ('sound', C.c_uint8)]


class Motion(C.Structure):
    _fields_ = [('x', C.c_uint16), ('y', C.c_uint16), ('dx', C.c_int8), ('dy', C.c_int8)]


class Terrain(C.Structure):
    _fields_ = [('cells', C.POINTER(C.c_uint8)), ('attributes', C.POINTER(C.c_uint8))]


def verify(capture, code, motion_capture=None):
    raw = (capture / 'logic.bin').read_bytes()
    stride = 4 + 256 + 8 + 5
    if not raw or len(raw) % stride:
        raise ValueError('Incomplete or empty logic capture')
    records = [raw[i:i+stride] for i in range(0, len(raw), stride)]
    program = code.read_bytes()
    with tempfile.TemporaryDirectory() as directory:
        library = Path(directory) / 'bc_rules.dylib'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', '-I' + str(ROOT / 'inc'), str(ROOT / 'src/bc_rules.c'),
                        '-o', str(library)], check=True)
        lib = C.CDLL(str(library))
        lib.bc_charge_step.argtypes = [C.POINTER(Charge)] + [C.c_uint8] * 4
        lib.bc_charge_step.restype = Event
        lib.bc_direction.argtypes = [C.c_uint8, C.c_uint8, C.POINTER(C.c_int8), C.POINTER(C.c_int8)]
        # Runtime bank $80 begins at CPU $4000 in these code captures.
        for speed in range(256):
            address = 0x9BE7 if speed else 0x9BC7
            for direction in range(256):
                dx, dy = C.c_int8(), C.c_int8()
                lib.bc_direction(direction, speed, C.byref(dx), C.byref(dy))
                expected = struct.unpack_from('bb', program, address - 0x4000 + (direction & 15) * 2)
                assert (dx.value, dy.value) == expected, (speed, direction, expected)
        first = records[0][4:260]
        state = Charge(first[0x56], first[0x55], first[0x57], first[0xAA] == 0x52)
        beams = []
        for old, new in zip(records, records[1:]):
            frame = struct.unpack_from('<I', new)[0]
            assert frame == struct.unpack_from('<I', old)[0] + 1, 'Trace has a missing frame'
            ram = new[4:260]
            event = lib.bc_charge_step(C.byref(state), new[260], ram[0x94] == 0x80,
                                       ram[0xAD], bool(any(old[268:273])))
            expected = (ram[0x56], ram[0x55], ram[0x57], int(ram[0xAA] == 0x52))
            actual = (state.charge, state.held, state.latch, state.facing)
            assert actual == expected, (frame, actual, expected)
            if event.beam:
                slots = new[268:273]
                assert sum(value == 0x80 for value in slots) == event.beam, (frame, event.beam, list(slots))
                beams.append(dict(frame=frame, segments=event.beam))
        assert {b['segments'] for b in beams} == {3, 4, 5}, 'Capture must exercise all three beam strengths'
        motion_frames = 0
        if motion_capture:
            lib.bc_move_step.argtypes = [C.POINTER(Motion), C.c_uint8, C.c_uint8] + [C.c_uint16] * 4 + [C.POINTER(Terrain)]
            lib.bc_move_step.restype = C.c_uint8
            cells = (C.c_uint8 * 16384).from_buffer_copy(program[0xC000:])
            program_buffer = (C.c_uint8 * 65536).from_buffer_copy(program)
            raw_motion = (motion_capture / 'logic.bin').read_bytes()
            assert len(raw_motion) % stride == 0, 'Incomplete motion capture'
            motion_records = [raw_motion[i:i+stride] for i in range(0, len(raw_motion), stride)]
            for previous, current in zip(motion_records, motion_records[1:]):
                frame = struct.unpack_from('<I', current)[0]
                assert frame == struct.unpack_from('<I', previous)[0] + 1
                old, new = previous[4:260], current[4:260]
                # Entry/death flow is a separate, not-yet-ported component.
                if old[0x94] != 0x80 or new[0x94] != 0x80 or old[0xAD] or new[0xAD]:
                    continue
                assert old[0x4B] == new[0x4B] == 0, 'Use the round-one motion fixture with this code dump'
                attribute_offset = 0x6000 + (old[0x44] | old[0x45] << 8) - 0xA000
                assert 0 <= attribute_offset <= len(program) - 2048
                terrain = Terrain(cells, C.cast(C.byref(program_buffer, attribute_offset), C.POINTER(C.c_uint8)))
                player = Motion(old[0x96] * 256 + old[0x97], old[0x99] * 256 + old[0x9A], 0, 0)
                crush = lib.bc_move_step(C.byref(player), current[260] >> 4, new[0xA9],
                                         new[0x2E] * 256 + new[0x2F], new[0x31] * 256 + new[0x32],
                                         new[0x40] * 256 + new[0x41], new[0x42] * 256 + new[0x43],
                                         C.byref(terrain))
                expected = (new[0x96] * 256 + new[0x97], new[0x99] * 256 + new[0x9A],
                            C.c_int8(new[0x9F]).value, C.c_int8(new[0xA1]).value)
                actual = (player.x, player.y, player.dx, player.dy)
                assert not crush and actual == expected, (frame, actual, expected, crush)
                motion_frames += 1
            assert motion_frames, 'No controllable player frames in the motion fixture'
    result = dict(status='PASS', module='movement, terrain and charge rules only',
                  direction_cases=65536, charge_frames=len(records)-1, beam_launches=beams,
                  movement_frames=motion_frames,
                  whole_game_verified=False)
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--motion-capture', type=Path)
    args = parser.parse_args()
    verify(args.capture, args.code, args.motion_capture)
