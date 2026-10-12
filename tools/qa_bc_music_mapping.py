#!/usr/bin/env python3
"""Verify replacement music selection from captured source BIOS requests."""
import ctypes as C
import json
from pathlib import Path
import subprocess
import tempfile
from qa_bc_enemies import Data
from qa_bc_stage_runtime import Audio
from run_rom import ROOT

cases = [
    ('play-task-round1', 0x8c50, 0, 0x21),
    ('play-task-round1', 0x8d22, 0, 0x32),
    ('play-task-round1', 0x8db2, 0, 0x2a),
    ('round02-reference', 0x8a4e, -535, 0x22),
    ('round2-ending', 0x8b4a, -535, 0x32),
    ('round3-route', 0x8a63, -535, 0x23),
    ('round3-route', 0x8b20, -535, 0x32),
    ('round4-opening', 0x8a78, -535, 0x24),
    ('round5-opening', 0x8a8d, -535, 0x25),
    ('round6-opening', 0x8aa2, -535, 0x26),
    ('round6-route3', 0x8b35, -535, 0x32),
    ('round7-opening', 0x8ab7, -535, 0x27),
    ('round8-opening', 0x8acc, -535, 0x28),
    ('round9-opening', 0x66f6, -535, 0x29),
    ('round10-protected', 0x8af6, -535, 0x36),
    ('round10-protected', 0xa5ff, -535, 0x2c),
    ('round10-ending-presentation', 0x9850, 0, 0x21),
    ('round10-ending-presentation', 0x9989, 0, 0xfe),
]
with tempfile.TemporaryDirectory() as directory:
    path = Path(directory) / 'music.dylib'
    subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC',
                    '-I'+str(ROOT/'inc'), str(ROOT/'src/bc_audio.c'), '-o', str(path)], check=True)
    lib = C.CDLL(str(path))
    lib.bc_audio_round_start.argtypes = [C.POINTER(Audio), C.POINTER(Data), C.c_uint8]
    lib.bc_audio_round_start.restype = C.c_uint8
    lib.bc_audio_request.argtypes = [C.POINTER(Audio), C.POINTER(Data), C.c_uint16]
    lib.bc_audio_music_command.argtypes = [C.POINTER(Audio), C.c_int16]
    lib.bc_audio_music_command.restype = C.c_uint8
    commands = json.loads((ROOT/'res/generated/sound.json').read_text())['commands']
    for capture, handler, relocation, command in cases:
        code = (ROOT/'.local/pce-reference'/capture/('code-007080.bin' if handler in (0x9850,0x9989) else 'code-002160.bin')).read_bytes()
        rom = (C.c_uint8*len(code)).from_buffer_copy(code)
        data = Data(rom, 0x4000)
        request = Audio()
        if handler == 0x66f6:
            assert code[0x26f0:0x26fb] == bytes.fromhex('a54bc908d01720323b12e0')
            for round_index in range(10):
                request = Audio()
                assert lib.bc_audio_round_start(C.byref(request), C.byref(data), round_index) == (round_index == 8)
                if round_index != 8: assert bytes(request) == bytes(Audio())
            assert lib.bc_audio_round_start(C.byref(request), C.byref(data), 8)
        else:lib.bc_audio_request(C.byref(request), C.byref(data), handler)
        if handler in (0x9850,0x9989):
            generated = Audio()
            lib.bc_audio_ending_request(C.byref(generated), int(handler == 0x9989))
            assert bytes(generated) == bytes(request)
        before = bytes(request)
        assert lib.bc_audio_music_command(C.byref(request), relocation) == command
        assert bytes(request) == before and request.state == 1
        if command == 0xfe:
            assert handler == 0x9989  # Native finite credits extension.
        else:
            assert commands[f'{command:02x}']['kind'] == 'music'
        for i in range(8):
            request.parameters[i] ^= 1
            assert lib.bc_audio_music_command(C.byref(request), relocation) == 255
            request.parameters[i] ^= 1
        request.handler = 0
        assert lib.bc_audio_music_command(C.byref(request), relocation) == 255
print(json.dumps(dict(mapped_source_requests=len(cases), rejected_parameter_changes=8*len(cases),
                     original_cd_audio=False, native_scene_verified_by_this_test=False), indent=2))
