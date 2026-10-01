#!/usr/bin/env python3
"""Run tools/re_levels.lua for one stage (debug stage select + invincibility).

usage: re_levels_run.py STAGE FRAMES [--snap N] [--unstick N] [--nopower]
Output: reports/oracle/stage<NN>/events.txt + snap/*.png (development-only).
"""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT


def run(stage, frames, snap=60, unstick=0, power=1, name=None, timeout=1800):
    src = Source()
    out = ROOT / 'reports/oracle' / (name or f'stage{stage:02d}')
    if out.exists():
        shutil.rmtree(out)
    romdir = out / 'roms/sidearms'
    romdir.mkdir(parents=True)
    for f in src.files:
        (romdir / f).symlink_to(src.root / f)
    for d in ('cfg', 'nvram', 'sta', 'snap', 'diff', 'home'):
        (out / d).mkdir()
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', SA_STAGE=str(stage),
               SA_FRAMES=str(frames), SA_SNAP=str(snap), SA_UNSTICK=str(unstick), SA_POWER=str(power))
    cmd = [os.environ.get('MAME') or shutil.which('mame'), 'sidearms', '-rompath', str(romdir.parent),
           '-autoboot_delay', '0', '-autoboot_script', str(ROOT / 'tools/re_levels.lua'),
           '-video', 'none', '-sound', 'none', '-nothrottle', '-skip_gameinfo', '-noconfirm_quit',
           '-noplugins', '-nohttp', '-nowriteconfig', '-cfg_directory', 'cfg', '-nvram_directory', 'nvram',
           '-state_directory', 'sta', '-snapshot_directory', 'snap', '-diff_directory', 'diff',
           '-homepath', 'home', '-inipath', 'home']
    r = subprocess.run(cmd, cwd=out, env=env, capture_output=True, timeout=timeout)
    (out / 'stdout.txt').write_bytes(r.stdout); (out / 'stderr.txt').write_bytes(r.stderr)
    if r.returncode != 0:
        raise SystemExit(r.stderr.decode(errors='replace')[-2000:])
    lines = (out / 'events.txt').read_text().splitlines()
    assert lines[-1] == 'COMPLETE', lines[-3:]
    return out


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('stage', type=int); a.add_argument('frames', type=int)
    a.add_argument('--snap', type=int, default=60); a.add_argument('--unstick', type=int, default=0)
    a.add_argument('--nopower', action='store_true'); a.add_argument('--name')
    o = a.parse_args()
    print(run(o.stage, o.frames, o.snap, o.unstick, 0 if o.nopower else 1, o.name))
