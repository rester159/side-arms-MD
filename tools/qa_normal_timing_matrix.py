#!/usr/bin/env python3
"""Run fixed-update Normal samples serially and optionally compare a baseline.

Serial execution avoids the existing shared qa_soak offset-build scratch files.
Exit 0: all speed targets met; 1: bounded samples still below full speed;
2: measurement error, changed ROM, or mismatched compared state hashes.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--players', type=int, nargs='+', choices=(1, 2, 3, 4), default=[1, 2, 3, 4])
p.add_argument('--sections', type=int, nargs='+', choices=range(10), default=list(range(10)))
p.add_argument('--updates', type=int, default=1000)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--baseline', type=Path, help='Directory containing <players>p-<section>/result.json')
p.add_argument('--scheduler-trace',action='store_true')
p.add_argument('--render-trace', action='store_true', help='Also compare ordered sprite pixels when a baseline is given')
a = p.parse_args()
assert a.updates > 0
out = a.output.resolve(); out.mkdir(parents=True, exist_ok=True)
rom = Path(os.environ.get('SIDEARMS_BUILD', ROOT)) / 'out/release/rom.bin'
rom_hash = hashlib.sha256(rom.read_bytes()).hexdigest()
rows = []; errors = []
for players in dict.fromkeys(a.players):
    for section in dict.fromkeys(a.sections):
        name = f'{players}p-{section}'
        case = out / name; case.mkdir(exist_ok=True)
        result_file = case / 'result.json'
        if result_file.exists():
            result_file.unlink()  # A failed run must not reuse an earlier result.
        command = [sys.executable, str(ROOT / 'tools/qa_normal_fixed_updates.py'),
                   '--players', str(players), '--section', str(section),
                   '--updates', str(a.updates), '--output', str(case)]
        if a.scheduler_trace:
            command.append('--scheduler-trace')
        if a.render_trace:
            command.append('--render-trace')
        with (case / 'run.log').open('w') as log:
            completed = subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            assert completed.returncode in (0, 1) and result_file.exists(), 'measurement failed; see run.log'
            result = json.loads(result_file.read_text())
            assert result['rom_sha256'] == rom_hash, 'ROM changed'
            assert result['updates'] == a.updates and len(result['state_hashes']) == a.updates + 1
            row = dict(players=players, section=section, frames=result['emulated_frames'],
                       updates=a.updates, worst_lines=result['worst_lines'],
                       sprite_drops=result['sprite_drops'], runtime_remaps=result['runtime_remaps'])
            if a.baseline:
                base = json.loads((a.baseline / name / 'result.json').read_text())
                for key in ('players', 'section', 'updates', 'protected', 'parallax'):
                    assert base[key] == result[key], f'baseline {key} differs'
                assert base['state_hashes'] == result['state_hashes'], 'compared state hashes differ'
                if a.render_trace:
                    assert base['render_hashes'] == result['render_hashes'], 'compared sprite pixels/order differ'
                row.update(baseline_rom_sha256=base['rom_sha256'], baseline_frames=base['emulated_frames'],
                           saved_frames=base['emulated_frames']-result['emulated_frames'], hashes_match=True)
            rows.append(row)
            print(json.dumps(row), flush=True)
        except (AssertionError, OSError, ValueError, KeyError) as error:
            errors.append(dict(case=name, error=str(error)))
            print(json.dumps(errors[-1]), flush=True)
if hashlib.sha256(rom.read_bytes()).hexdigest() != rom_hash:
    errors.append(dict(error='ROM changed during matrix'))
result = dict(rom_sha256=rom_hash, rows=rows, errors=errors,
              full_speed_verified=not errors and all(r['frames'] == r['updates'] for r in rows),
              full_game_verified=False)
(out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
raise SystemExit(2 if errors else 0 if result['full_speed_verified'] else 1)
