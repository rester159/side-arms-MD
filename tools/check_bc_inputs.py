#!/usr/bin/env python3
"""Fail early when local BC reference inputs required by the build are absent."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT / '.local/pce-reference'


def required_inputs():
    yield REFERENCE / 'play-task-round1/code-002160.bin'
    yield REFERENCE / 'play-task-round1/play-task.bin'
    for number in range(2, 11):
        capture = REFERENCE / f'round{number:02d}-reference'
        yield capture / 'code-002160.bin'
        yield capture / 'f002400-ram.bin'
    yield REFERENCE / 'round10-ending-presentation/code-007080.bin'
    yield Path('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc')


if __name__ == '__main__':
    missing = [path for path in required_inputs() if not path.is_file()]
    if missing:
        raise SystemExit('Before Christ build inputs are missing:\n' +
                         '\n'.join(f'  {path}' for path in missing) +
                         '\nSee README.md, Before Christ build inputs. '
                         'Existing generated files are not a substitute for these inputs.')
