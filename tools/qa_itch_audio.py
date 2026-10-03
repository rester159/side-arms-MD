#!/usr/bin/env python3
"""Capture isolated BGM and SFX through the complete game's actual Z80 driver."""
import argparse
import ctypes as C
import json
from pathlib import Path
import wave
import numpy as np
from run_rom import Runner

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--rom', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
r = Runner(a.rom)
class Geometry(C.Structure):
    _fields_ = [('base_width', C.c_uint), ('base_height', C.c_uint),
                ('max_width', C.c_uint), ('max_height', C.c_uint), ('aspect_ratio', C.c_float)]
class Timing(C.Structure):
    _fields_ = [('fps', C.c_double), ('sample_rate', C.c_double)]
class AVInfo(C.Structure):
    _fields_ = [('geometry', Geometry), ('timing', Timing)]
av = AVInfo()
r.lib.retro_get_system_av_info.argtypes = [C.POINTER(AVInfo)]
r.lib.retro_get_system_av_info(C.byref(av))
r.run(2000)
assert r.u32('flow_state') == 0
z = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
chunks = []
def audio(p, n):
    chunks.append(C.string_at(p, n * 4))
    return n
callback_type = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)
callback = callback_type(audio)
r.lib.retro_set_audio_sample_batch.argtypes = [callback_type]
r.lib.retro_set_audio_sample_batch(callback)
def command(cmd):
    wr = z[0x1F04] & 15
    assert ((wr + 1) & 15) != z[0x1F05]
    z[0x1F10 + wr] = cmd
    z[0x1F04] = (wr + 1) & 15
result = {}
for name, cmd in [('music', 0x21), ('sfx', 0x0C), ('mixed', 0x21)]:
    command(0)
    r.run(120)
    chunks.clear()
    command(cmd)
    ticks = 0
    last = z[0x1400]
    for frame in range(600):
        if name == 'mixed' and frame % 30 == 0:
            command(0x0C)
        r.run(1)
        ticks += (z[0x1400] - last) & 255
        last = z[0x1400]
    raw = b''.join(chunks)
    with wave.open(str(a.output / f'{name}.wav'), 'wb') as w:
        w.setnchannels(2); w.setsampwidth(2); w.setframerate(round(av.timing.sample_rate)); w.writeframes(raw)
    x = np.frombuffer(raw, dtype=np.int16).astype(float).reshape(-1, 2)
    x -= x.mean(axis=0)
    result[name] = dict(rms_dbfs=float(20*np.log10(np.sqrt(np.mean(x*x))/32768)),
                        ticks=ticks, samples=len(x), sample_rate=av.timing.sample_rate,
                        tick_hz=ticks / (600 / av.timing.fps))
print(json.dumps(result, indent=2))
(a.output / 'metrics.json').write_text(json.dumps(result, indent=2) + '\n')
