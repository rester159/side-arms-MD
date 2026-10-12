#!/usr/bin/env python3
"""Capture the local PC Engine CD reference with MAME, including VRAM/palette/RAM.

Requires a user-supplied System Card BIOS and extracted CUE/image. Captures are
local reference material, never linked into the cartridge or committed.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    out = ROOT / '.local/pce-reference' / args.name
    if out.exists():
        raise SystemExit(f'Refusing to overwrite an existing capture: {out}')
    out.mkdir(parents=True)
    for name in ('cfg', 'nvram', 'snap', 'sta', 'home'):
        (out / name).mkdir()
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
               PCE_FRAMES=str(args.frames), PCE_STAGE=str(args.stage),
               PCE_INTERVAL=str(args.interval), PCE_SNAPSHOT_FROM=str(args.snapshot_from), PCE_LATE_CODE_FROM=str(args.late_code_from), PCE_FIRE=args.fire,
               PCE_INVULNERABLE=str(int(args.invulnerable)),
               PCE_BOSS_FAST=str(int(args.boss_fast)), PCE_TRACE_FROM=str(args.trace_from),
               PCE_GALLERY_TRACE=str(int(args.gallery_trace)), PCE_FULL_STATE=str(int(args.full_state)), PCE_CONTACT_TRACE=str(int(args.contact_trace)),
               PCE_ENEMY_TRACE=str(int(args.enemy_trace)), PCE_AI_TRACE=str(int(args.ai_trace)),
               PCE_PLAYER_TRACE=str(int(args.player_trace)), PCE_PLAYER_CASES=str(int(args.player_cases)),
               PCE_PICKUP_CASES=str(int(args.pickup_cases)), PCE_RANDOM_TRACE=str(int(args.random_trace)),
               PCE_FACTORY_TRACE=str(int(args.factory_trace)), PCE_COMMON_TRACE=str(int(args.common_trace)),
               PCE_COMMON_CASES=str(int(args.common_cases)), PCE_SCORE_TRACE=str(int(args.score_trace)),
               PCE_SCORE_CASES=str(int(args.score_cases)), PCE_PLAYER_FLOW_TRACE=str(int(args.player_flow_trace)))
    if args.input: env['PCE_INPUT'] = str(args.input.resolve())
    cmd = [shutil.which('mame'), 'pce', '-cart', str(args.bios.resolve()),
           '-cdrom', str(args.cue.resolve()), '-autoboot_delay', '0',
           '-autoboot_script', str(ROOT / 'tools/pce_capture.lua'),
           '-video', 'none', '-sound', 'none', '-nothrottle', '-skip_gameinfo',
           '-noconfirm_quit', '-noplugins', '-nohttp', '-nowriteconfig',
           '-cfg_directory', 'cfg', '-nvram_directory', 'nvram',
           '-state_directory', 'sta', '-snapshot_directory', 'snap',
           '-homepath', 'home', '-inipath', 'home']
    with (out / 'mame.log').open('w') as log:
        result = subprocess.run(cmd, cwd=out, env=env, stdout=log,
                                stderr=subprocess.STDOUT, timeout=max(120, args.frames / 30))
    if result.returncode or not (out / 'complete.txt').exists():
        raise SystemExit(f'Capture failed; inspect {out / "mame.log"}')
    print(out)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('name')
    p.add_argument('--cue', type=Path, required=True)
    p.add_argument('--bios', type=Path, required=True)
    p.add_argument('--gallery-trace', action='store_true', help='Trace actor updates in the final ending gallery (stage 9 fixture)')
    p.add_argument('--late-code-from', type=int, default=0, help='Also dump CD RAM and bank maps at snapshot intervals from this frame')
    p.add_argument('--frames', type=int, default=6000)
    p.add_argument('--snapshot-from', type=int, default=0,
                   help='Begin VRAM/palette/SAT screenshots at this frame; inputs still run from boot')
    p.add_argument('--stage', type=int, choices=range(10), default=0)
    p.add_argument('--interval', type=int, default=120)
    p.add_argument('--fire', choices=('none','pulse','hold','charge'), default='pulse')
    p.add_argument('--input', type=Path, help='Timeline: frame field value, or frame poke hex-address hex-byte')
    p.add_argument('--trace-from', type=int, default=0, help='Record compact per-frame logic snapshots from this frame')
    p.add_argument('--ai-trace', action='store_true', help='Capture enemy-specific work before the common update')
    p.add_argument('--random-trace', action='store_true', help='Capture original RNG inputs and outputs')
    p.add_argument('--factory-trace', action='store_true', help='Capture enemy allocation and template initialization')
    p.add_argument('--common-trace', action='store_true', help='Capture complete common enemy updates')
    p.add_argument('--common-cases', action='store_true', help='With --common-trace, inject and restore ordering-sensitive enemy update cases')
    p.add_argument('--score-trace', action='store_true', help='Capture score enqueue and complete score-task iterations')
    p.add_argument('--score-cases', action='store_true', help='With --score-trace, inject and restore score arithmetic/queue boundary cases')
    p.add_argument('--player-flow-trace', action='store_true', help='Capture player control and pose/countdown tasks')
    p.add_argument('--player-trace', action='store_true', help='Capture enemy/player contact before the damage-lock countdown')
    p.add_argument('--player-cases', action='store_true', help='With --player-trace, inject and restore isolated contact boundary/option cases')
    p.add_argument('--pickup-cases', action='store_true', help='With --player-trace, inject and restore isolated pickup/option-replenishment cases')
    p.add_argument('--enemy-trace', action='store_true', help='Capture common enemy animation/motion and depleted-HP transitions')
    p.add_argument('--contact-trace', action='store_true', help='Capture original enemy/shot collision entry and exit state')
    p.add_argument('--full-state', action='store_true', help='Record full work RAM each frame from trace-from')
    p.add_argument('--invulnerable', action='store_true')
    p.add_argument('--boss-fast', action='store_true')
    a = p.parse_args()
    if a.interval < 1 or a.frames < 1 or not 0 <= a.snapshot_from <= a.frames or Path(a.name).name != a.name:
        p.error('Use a directory name and positive frame/interval counts')
    if (a.player_cases or a.pickup_cases) and not a.player_trace:
        p.error('Contact cases require --player-trace')
    if a.player_cases and a.pickup_cases:
        p.error('Choose one contact fixture family per capture')
    if a.common_cases and (not a.common_trace or a.player_cases or a.pickup_cases):
        p.error('--common-cases requires --common-trace and cannot be combined with contact fixtures')
    if a.score_cases and not a.score_trace:
        p.error('--score-cases requires --score-trace')
    run(a)
