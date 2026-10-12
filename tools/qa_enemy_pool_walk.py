#!/usr/bin/env python3
"""Audit enemy pool bounds while running the existing Normal timing stress bot.

Accepts qa_multiplayer_perf.py arguments. Checks native RAM after each video
frame; adds no guest instructions. Timing failures retain the bot's exit code.
The current native Enemy record is 40 bytes, with the live flag at offset zero.
"""
import runpy
import struct
import sys
from run_rom import ROOT, Runner

original_run = Runner.run
checks = 0

def audited_run(runner, frames, mask=0):
    global checks
    for _ in range(frames):
        original_run(runner, 1, mask)
        if runner.frames < 2600:
            continue
        ends = struct.unpack('>3I', runner.read('pool_end', 12))
        counts = runner.read('n_live', 3)
        for pool, (name, size) in enumerate((('en_small', 40), ('en_big', 24), ('en_item', 8))):
            raw = runner.read(name, size * 40)
            live = [slot for slot in range(size) if raw[slot * 40]]
            expected = runner.symbols[name] + (max(live) + 1 if live else 0) * 40
            assert ends[pool] == expected, (runner.frames, name, ends[pool], expected, live)
            assert counts[pool] == len(live), (runner.frames, name, counts[pool], len(live))
        checks += 1

Runner.run = audited_run
try:
    runpy.run_path(str(ROOT / 'tools/qa_multiplayer_perf.py'), run_name='__main__')
finally:
    Runner.run = original_run
    print('POOL_AUDIT_FRAMES', checks, file=sys.stderr)
