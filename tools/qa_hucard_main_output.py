#!/usr/bin/env python3
"""Measure all HuCard tracks through the actual cartridge's Sound Test UI."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import wave
from collections import Counter

import numpy as np
from run_rom import ROOT, Runner, PAD

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--pal', action='store_true')
p.add_argument('--audio', action='store_true', help='Save the measured stereo clips for audition')
p.add_argument('--track', type=lambda value: int(value, 0), choices=range(21), help='Check one Sound Test entry instead of all 21')
p.add_argument('--frames', type=int, default=600, help='Video frames per track; positive multiple of 30')
p.add_argument('--output', type=Path, help='Keep this run separate from earlier reports')
a = p.parse_args()
assert a.frames > 0 and a.frames % 30 == 0
out = a.output or ROOT / '.local/pce-hucard' / ('main-output-pal' if a.pal else 'main-output-ntsc')
out.mkdir(parents=True, exist_ok=True)
rom = ROOT / 'out/release/rom.bin'
source_hash = hashlib.sha256(rom.read_bytes()).hexdigest()
if a.pal:
    data = bytearray(rom.read_bytes())
    data[0x1f0:0x200] = b'E' + b' ' * 15
    shutil.copy(rom.parent / 'symbol.txt', out / 'symbol.txt')
    rom = out / 'rom.bin'
    rom.write_bytes(data)
r = Runner(rom=rom)

class Timing(C.Structure):
    _fields_ = [('geo', C.c_uint * 4), ('aspect', C.c_float),
                ('fps', C.c_double), ('rate', C.c_double)]

av = Timing()
r.lib.retro_get_system_av_info(C.byref(av))
assert (av.fps < 55) == a.pal
zram = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
buf = []
cb = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)(
    lambda ptr, n: buf.append(np.ctypeslib.as_array(ptr, (n * 2,)).copy()) or n)
r.callbacks.append(cb)
r.lib.retro_set_audio_sample_batch(cb)

def tap(key):
    r.run(5, PAD[key])
    r.run(20)
    buf.clear()

def counter():
    return zram[0x1b0c] + 256 * zram[0x1b0d]

r.run(2600)
assert r.u32('flow_state') == 0
tap('DOWN'); tap('A')
assert r.u32('flow_state') == 9
for _ in range(3): tap('DOWN')
tap('A')
assert r.u32('flow_state') == 1
for _ in range(10): tap('DOWN')
tap('A')
tap('DOWN'); tap('DOWN'); tap('RIGHT')
assert r.read('snd_source', 1) == b'\1'
tap('UP'); tap('UP')
tracks = []
packet_checks = 0
packet_slots = set()
instrument_samples = Counter()
for _ in range(a.track or 0): tap('RIGHT')
for song in (range(21) if a.track is None else [a.track]):
    assert r.read('snd_music', 1) == bytes([song])
    r.run(5, PAD['A']); r.run(1)
    assert r.u16('dbg_hucard_track') == song
    assert r.read('hucard_active', 1) == b'\1'
    buf.clear()
    before = counter()
    power = 0.; count = peak = 0
    clip = []
    track_instruments = Counter()
    for _ in range(a.frames // 30):
        r.run(30)
        assert zram[0x1b0a] == 0, ('underrun', song)
        # The last published slot must contain the complete producer packet,
        # including after ring wrap. Z80 only consumes these bytes.
        slot = (int(zram[0x1f09]) - 1) & 3
        address = 0x1800 + slot * 72
        packet = r.read('hucard_packet',72)
        assert bytes(zram[address:address+72]) == packet, ('packet copy',song,slot)
        for channel in range(6):
            voice = packet[channel*12:(channel+1)*12]
            instrument = voice[0]
            assert instrument <= 32, ('instrument', song, instrument)
            # Algorithms 5/6 use the first operator as a modulator.
            carriers = voice[9:12] if voice[3] & 7 in (5, 6) else voice[8:12]
            if instrument and any(level < 127 for level in carriers):
                track_instruments[instrument] += 1
                instrument_samples[instrument] += 1
        packet_slots.add(slot)
        packet_checks += 1
        samples = np.concatenate(buf).astype(np.int32)
        if a.audio: clip.append(samples.astype('<i2'))
        buf.clear()
        power += float(np.sum(samples.astype(float) ** 2))
        count += samples.size
        peak = max(peak, int(np.max(np.abs(samples))))
    ticks = (counter() - before) & 65535
    expected = a.frames / av.fps * 7159090.909090909 / (113 * 1024)
    assert abs(ticks - expected) < 2, (song, ticks, expected)
    rms = float(np.sqrt(power / count))
    assert rms > 5 and peak < 32767, (song, rms, peak)
    track = dict(song=song, frames=a.frames, ticks=ticks, rms=round(rms, 2), peak=peak,
                 sampled_active_instruments=dict(sorted(track_instruments.items())))
    if a.audio:
        filename=f'track-{song:02x}.wav'
        with wave.open(str(out/filename),'wb') as wav:
            wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(round(av.rate))
            wav.writeframes(np.concatenate(clip).tobytes())
        track['audio_file']=filename
    tracks.append(track)
    print(f'Track {song:02x}: audible, clock correct, no underruns', flush=True)
    if a.track is None and song < 20: tap('RIGHT')

# STOP and source changes use the same controls exposed to the player.
for _ in range(3): tap('DOWN')
tap('A'); r.run(120); buf.clear(); r.run(30)
assert r.read('hucard_active', 1) == b'\0'
assert np.max(np.abs(np.concatenate(buf).astype(np.int32))) < 4
tap('UP'); tap('LEFT')
assert r.read('snd_source', 1) == b'\0'
tap('UP'); tap('UP'); tap('RIGHT'); tap('A')
r.run(120); buf.clear(); r.run(30)
assert not zram[0x1f08]
assert np.sqrt(np.mean(np.concatenate(buf).astype(float) ** 2)) > 20
tap('B')
assert r.u32('flow_state') == 1
report = dict(passed=True, source_rom_sha256=source_hash,
              sampled_active_instruments=dict(sorted(instrument_samples.items())),
              instrument_scope='Non-muted carriers in producer packets sampled every 30 video frames; not exhaustive instrument coverage',
              published_packet_checks=packet_checks, published_packet_slots=sorted(packet_slots),
              tested_rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
              core_sha256=hashlib.sha256(Path(r.lib._name).read_bytes()).hexdigest(),
              pal=a.pal, fps=av.fps, sample_rate=av.rate, tracks=tracks, underruns=0,
              stop_silent=True, arcade_resumed=True, back_to_options=True,
              scope='Actual Sound Test UI and audio output; no subjective timbre claim')
(out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
