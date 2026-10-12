#!/usr/bin/env python3
"""Measure bounded BC opening workloads, not complete rounds or campaigns.

Uses the existing uninstrumented native CPU fixture with debug protection and
periodic fire. Host concurrency affects elapsed test time, not guest cycles.
Exit 1 means at least one workload missed full simulation speed; exit 2 means
the measurement failed or the ROM changed during the run.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--players', type=int, nargs='+', choices=range(1, 5), default=[1, 2, 3, 4])
p.add_argument('--rounds', type=int, nargs='+', choices=range(1, 11), default=list(range(1, 11)))
p.add_argument('--warmup', type=int, default=300)
p.add_argument('--updates', type=int, default=600)
p.add_argument('--jobs', type=int, default=4)
p.add_argument('--output', type=Path, default=ROOT / '.local/bc-opening-timing')
p.add_argument('--rom', type=Path, default=ROOT / 'out/release/rom.bin')
p.add_argument('--hucard', action='store_true', help='Select and verify HuCard playback in every timing sample')
a = p.parse_args()
if a.warmup < 0 or a.updates < 1 or a.jobs < 1:
    p.error('warmup must be nonnegative; updates and jobs must be positive')
a.output.mkdir(parents=True, exist_ok=True)
rom = a.rom.resolve()
digest = hashlib.sha256(rom.read_bytes()).hexdigest()


def measure(round_number, players):
    command = [sys.executable, str(ROOT / 'tools/profile_bc_cpu.py'), '--plain',
               '--round', str(round_number), '--players', str(players),
               '--warmup', str(a.warmup), '--updates', str(a.updates), '--rom', str(rom)]
    if a.hucard:command.append('--hucard')
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    (a.output / f'round-{round_number:02d}-{players}p.log').write_text(process.stdout + process.stderr)
    if process.returncode:
        return dict(round=round_number, players=players, error=f'fixture exit {process.returncode}')
    result = json.loads(process.stdout)
    if result['rom_sha256'] != digest or result['instrumentation'] or not result['protected']:
        return dict(round=round_number, players=players, error='fixture identity mismatch')
    result['full_speed_in_sample'] = result['emulated_frames'] == a.updates
    result['simulation_speed_percent'] = 100 * a.updates / result['emulated_frames']
    return result


results = []
with ThreadPoolExecutor(max_workers=a.jobs) as pool:
    futures = [pool.submit(measure, r, n) for r in sorted(set(a.rounds)) for n in sorted(set(a.players))]
    for future in as_completed(futures):
        result = future.result()
        results.append(result)
        print(json.dumps(result), flush=True)
results.sort(key=lambda r: (r['round'], r['players']))
changed = hashlib.sha256(rom.read_bytes()).hexdigest() != digest
errors = changed or any('error' in r for r in results)
report = dict(scope='bounded protected openings with periodic fire; not full campaigns',
              music_source='hucard' if a.hucard else 'arcade',
              rom_sha256=digest, warmup_updates=a.warmup, measured_updates=a.updates,
              rom_changed=changed, measurement_errors=bool(errors), results=results,
              all_samples_full_speed=not errors and all(r['full_speed_in_sample'] for r in results),
              whole_game_verified=False)
(a.output / 'results.json').write_text(json.dumps(report, indent=2) + '\n')
sys.exit(2 if errors else 0 if report['all_samples_full_speed'] else 1)
