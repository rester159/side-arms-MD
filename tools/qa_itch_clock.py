#!/usr/bin/env python3
"""Sample sound-clock continuity during real Arcade waves and continuous firing.

Uses the existing invincible gameplay bot; timings are emulated frames, not host
wall time. SIDEARMS_BUILD selects the tested build. This cannot prove that an
unspecified hardware/emulator stutter report has been resolved.
"""
import argparse
import ctypes as C
import json
import struct
from qa_soak import Bot

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--players', type=int, choices=(1, 2), required=True)
ap.add_argument('--section', type=int, choices=range(10), required=True)
ap.add_argument('--frames', type=int, default=3000)
a = ap.parse_args()
b = Bot(a.players)
r = b.r
r.write('dbg_warp', struct.pack('>H', a.section + 1))
b.pad(0, 0)
for _ in range(600):
    b.keep_alive(); r.run(1)
    if not r.u16('dbg_warp'):
        break
assert b.lvl('section') == a.section and not r.u16('dbg_warp')
r.run(120)
z = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
last = z[0x1400]
deltas, backlog, frozen, max_frozen = [], [], 0, 0
start = r.u32('frame_counter')
for frame in range(a.frames):
    b.keep_alive()
    b.pad(b.steer(0, frame), b.steer(1, frame) if a.players == 2 else 0)
    r.run(1)
    delta = (z[0x1400] - last) & 255
    deltas.append(delta)
    last = z[0x1400]
    backlog.append(z[0x1404])
    frozen = frozen + 1 if delta == 0 else 0
    max_frozen = max(max_frozen, frozen)
windows = [sum(deltas[i:i + 60]) for i in range(0, len(deltas) - 59, 60)]
print(json.dumps(dict(players=a.players, section=a.section + 1, frames=a.frames,
    game_updates=r.u32('frame_counter') - start, sound_ticks=sum(deltas),
    ticks_per_frame=[min(deltas), max(deltas)], ticks_per_60_frames=[min(windows), max(windows)],
    max_pending_half_ticks=max(backlog), max_sound_frozen_frames=max_frozen,
    final_flow=r.u32('flow_state'))), flush=True)
assert max_frozen < 3, 'sound clock stalled for three emulated frames'
assert r.u32('frame_counter') > start, 'game stopped'
assert max(backlog) <= 16, 'sound driver accumulated more than 32 ms of unprocessed ticks'
assert all(240 <= n <= 260 for n in windows), 'sound clock drift/burst outside 60-frame window bounds'
