#!/usr/bin/env python3
"""Run the original game in MAME headlessly and record observations.

usage: oracle.py NAME FRAMES [--snap N] [--dump N] [--input FILE]
Outputs land in reports/oracle/NAME/ (ignored; development-only).
"""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT


def run(name, frames, snap=0, dump=1, inputs=None, timeout=900):
    src = Source()
    out = ROOT / 'reports/oracle' / name
    if out.exists():
        shutil.rmtree(out)
    romdir = out / 'roms/sidearms'
    romdir.mkdir(parents=True)
    for f in src.files:
        (romdir / f).symlink_to(src.root / f)
    for d in ('cfg', 'nvram', 'sta', 'snap', 'diff', 'home'):
        (out / d).mkdir()
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
               SA_FRAMES=str(frames), SA_SNAP=str(snap), SA_DUMP=str(dump))
    if inputs:
        p = out / 'input.txt'; p.write_text(inputs); env['SA_INPUT'] = str(p)
    cmd = [os.environ.get('MAME') or shutil.which('mame'), 'sidearms', '-rompath', str(romdir.parent),
           '-autoboot_delay', '0', '-autoboot_script', str(ROOT / 'tools/capture.lua'),
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
    a.add_argument('name'); a.add_argument('frames', type=int)
    a.add_argument('--snap', type=int, default=0); a.add_argument('--dump', type=int, default=1)
    a.add_argument('--input')
    o = a.parse_args()
    print(run(o.name, o.frames, o.snap, o.dump, Path(o.input).read_text() if o.input else None))
