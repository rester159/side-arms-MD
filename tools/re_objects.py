#!/usr/bin/env python3
"""Run tools/re_objects.lua (object/enemy probe) under MAME for one or more stages.

usage: re_objects.py [--stages 1,2,..] [--frames N] [--snap N] [--sdump N] [--unstick N] [--jobs N]
Output: reports/oracle/obj_sNN/events.txt (development-only, ignored).
"""
import argparse, os, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT


def run(stage, frames, snap, sdump, unstick, move=1, timeout=3600):
    src = Source()
    out = ROOT / 'reports/oracle' / f'obj_s{stage:02d}'
    if out.exists():
        shutil.rmtree(out)
    romdir = out / 'roms/sidearms'
    romdir.mkdir(parents=True)
    for f in src.files:
        (romdir / f).symlink_to(src.root / f)
    for d in ('cfg', 'nvram', 'sta', 'snap', 'diff', 'home'):
        (out / d).mkdir()
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', SA_STAGE=str(stage),
               SA_FRAMES=str(frames), SA_SNAP=str(snap), SA_SDUMP=str(sdump), SA_UNSTICK=str(unstick),
               SA_MOVE=str(move))
    cmd = [os.environ.get('MAME') or shutil.which('mame'), 'sidearms', '-rompath', str(romdir.parent),
           '-autoboot_delay', '0', '-autoboot_script', str(ROOT / 'tools/re_objects.lua'),
           '-video', 'none', '-sound', 'none', '-nothrottle', '-skip_gameinfo', '-noconfirm_quit',
           '-noplugins', '-nohttp', '-nowriteconfig', '-cfg_directory', 'cfg', '-nvram_directory', 'nvram',
           '-state_directory', 'sta', '-snapshot_directory', 'snap', '-diff_directory', 'diff',
           '-homepath', 'home', '-inipath', 'home']
    r = subprocess.run(cmd, cwd=out, env=env, capture_output=True, timeout=timeout)
    (out / 'stdout.txt').write_bytes(r.stdout); (out / 'stderr.txt').write_bytes(r.stderr)
    lines = (out / 'events.txt').read_text().splitlines()
    ok = r.returncode == 0 and lines and lines[-1] == 'COMPLETE'
    return stage, ok, out


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('--stages', default='1,2,3,4,5,6,7,8,9,10')
    a.add_argument('--frames', type=int, default=9000)
    a.add_argument('--snap', type=int, default=0)
    a.add_argument('--sdump', type=int, default=0)
    a.add_argument('--unstick', type=int, default=2400)
    a.add_argument('--move', type=int, default=1)
    a.add_argument('--jobs', type=int, default=5)
    o = a.parse_args()
    st = [int(s) for s in o.stages.split(',')]
    with ThreadPoolExecutor(o.jobs) as ex:
        for s, ok, out in ex.map(lambda s: run(s, o.frames, o.snap, o.sdump, o.unstick, o.move), st):
            print(s, 'OK' if ok else 'FAILED', out)
