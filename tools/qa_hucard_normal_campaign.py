#!/usr/bin/env python3
"""Continuous Normal campaign music check, with protected players and assisted boss hits.

No stage warps, music commands, or completion counters are injected. This is an
assisted progression check, not evidence of unassisted combat or full frame rate.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
import re
from pathlib import Path

import numpy as np
from run_rom import ROOT, Runner, PAD
from qa_soak import O

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--players', type=int, choices=(3, 4), default=4)
p.add_argument('--output', type=Path, help='Keep results separate from earlier cartridge evidence')
p.add_argument('--background-zones', type=int, nargs='+', help='Read-only settled palette/cache checks and captures for these Normal zones')
a = p.parse_args()
build = Path(os.environ.get('SIDEARMS_BUILD', ROOT))
rom = build / 'out/release/rom.bin'
digest = hashlib.sha256(rom.read_bytes()).hexdigest()
out = a.output or ROOT / f'.local/pce-hucard/normal-campaign-{a.players}p'
out.mkdir(parents=True, exist_ok=True)
r = Runner(rom=rom)
background_audit = None
if a.background_zones:
    from normal_live_background_audit import NormalBackgroundAudit
    background_audit = NormalBackgroundAudit(r, rom.read_bytes(), a.background_zones, out)
r.run(2600)

def tap(key):
    r.run(5, PAD[key]); r.run(20)

tap('DOWN'); tap('A')
for _ in range(3): tap('DOWN')
tap('A')
for _ in range(8): tap('DOWN')
tap('RIGHT')
assert r.read('home_cfg', 1, 7) == b'\1'
tap('B')
for _ in range(3): tap('UP')
tap('A')
for _ in range((a.players - 2) % 4): tap('DOWN')
tap('A')
assert r.u32('flow_state') == 6 and r.u16('player_limit') == a.players
r.write('dbg_pad_override', b'\1')
r.write('pad', bytes(8))
r.write('boss_dbg_autohit', b'\1')
zram = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
chunks = []

def audio(data, count):
    chunks.append(np.ctypeslib.as_array(data, (count * 2,)).copy())
    return count

cb = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)(audio)
r.callbacks.append(cb)
r.lib.retro_set_audio_sample_batch(cb)
events, sections, audible = [], set(), set()
previous = None
window = 0
for frame in range(300000):
    for player in range(a.players):
        base = player * O['s_Player']
        r.write('players', b'\xc8', base + O['o_Player_invuln'])
        r.write('players', b'\x05', base + O['o_Player_lives'])
    r.run(1)
    assert not zram[0x1b0a], ('queue underrun', frame)
    state = r.u32('flow_state')
    section = int.from_bytes(r.read('level', 2, O['o_Level_section']), 'big')
    if state == 7: sections.add(section)
    if state == 7 and background_audit:
        background_audit.observe(frame)
    track = r.u16('dbg_hucard_track')
    starts = r.u16('dbg_hucard_starts')
    current = (state, section, track, starts)
    if current != previous:
        row = dict(frame=frame, state=state, section=section, track=track,
                   starts=starts, boss_kills=r.u16('boss_kills'))
        events.append(row)
        print(json.dumps(row), flush=True)
        previous = current
        window = 0
        chunks.clear()
    window += 1
    if window == 120 and r.read('hucard_active', 1) == b'\1':
        rms = float(np.sqrt(np.mean(np.concatenate(chunks).astype(float) ** 2)))
        assert rms > 5, ('silent track', track, frame, rms)
        audible.add(track)
        events[-1]['rms'] = rms
        chunks.clear()
    elif window > 120:
        chunks.clear()
    if state == 9:
        break
    assert state in (6, 7), ('unexpected exit', state, frame)
else:
    r.capture(out / 'timeout.png')
    raise AssertionError(('campaign timed out', events[-1]))
section_count = len(re.findall(r'static const LevelEvent sec\d+\[\]',
                              (ROOT / 'src/gen/level_data.c').read_text()))
assert sections == set(range(section_count)), sections
expected = {0x11, 5, 4, 2, 3, 1, 6, 7, 8, 0x0e, 0x10,
            0x12, 0x0c, 0x0d, 0x0a, 0x0f}
assert expected <= audible, ('missing audible music', sorted(expected - audible))
assert any(e['boss_kills'] == 12 for e in events), events[-1]
assert sum(e['track'] == 0x0a and e.get('rms', 0) > 5 for e in events) == 11
assert hashlib.sha256(rom.read_bytes()).hexdigest() == digest
report = dict(passed=True, players=a.players, video_frames=frame + 1,
              sections=sorted(sections), audible_tracks=sorted(audible),
              events=events, underruns=0, rom_sha256=digest,
              protected_players=True, assisted_hit_tests=True,
              injected_stage_warps=False, injected_completion_events=False,
              full_combat_verified=False)
if background_audit:
    report['background_audit'] = background_audit.result()
(out / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({k: v for k, v in report.items() if k != 'events'}), flush=True)
