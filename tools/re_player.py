#!/usr/bin/env python3
"""Run tools/re_player.lua under MAME (development-only RE probe for docs/re/flow_player.md).

usage: re_player.py NAME FRAMES --input FILE [--snap N] [--snapat 100,200]
Output: reports/oracle/NAME/events.txt (+ snap/). Parse with load_events().
"""
import argparse, os, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT


def run(name, frames, inputs, snap=0, snapat=''):
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
    p = out / 'input.txt'; p.write_text(inputs)
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', SA_FRAMES=str(frames),
               SA_SNAP=str(snap), SA_SNAPAT=snapat, SA_INPUT=str(p))
    cmd = [os.environ.get('MAME') or shutil.which('mame'), 'sidearms', '-rompath', str(romdir.parent),
           '-autoboot_delay', '0', '-autoboot_script', str(ROOT / 'tools/re_player.lua'),
           '-video', 'none', '-sound', 'none', '-nothrottle', '-skip_gameinfo', '-noconfirm_quit',
           '-noplugins', '-nohttp', '-nowriteconfig', '-cfg_directory', 'cfg', '-nvram_directory', 'nvram',
           '-state_directory', 'sta', '-snapshot_directory', 'snap', '-diff_directory', 'diff',
           '-homepath', 'home', '-inipath', 'home']
    r = subprocess.run(cmd, cwd=out, env=env, capture_output=True, timeout=900)
    (out / 'stderr.txt').write_bytes(r.stderr)
    if r.returncode != 0:
        raise SystemExit(r.stderr.decode(errors='replace')[-2000:])
    return out


def load_events(name):
    """-> (ram {frame: bytes $E000-$E2FF}, obj {frame: bytes $F000-$FFFF}, text {frame: (codes, attrs)}, writes list)"""
    ram, obj, text, w = {}, {}, {}, []
    for line in open(ROOT / 'reports/oracle' / name / 'events.txt'):
        k = line[:2]
        if k == 'F|':
            _, f, r, s = line.strip().split('|'); ram[int(f)] = bytes.fromhex(r); obj[int(f)] = bytes.fromhex(s)
        elif k == 'T|':
            _, f, c, a = line.strip().split('|'); text[int(f)] = (bytes.fromhex(c), bytes.fromhex(a))
        elif k == 'W|':
            _, f, pc, ad, d = line.strip().split('|'); w.append((int(f), int(pc, 16), int(ad, 16), int(d, 16)))
    return ram, obj, text, w


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('name'); a.add_argument('frames', type=int); a.add_argument('--input', required=True)
    a.add_argument('--snap', type=int, default=0); a.add_argument('--snapat', default='')
    o = a.parse_args()
    print(run(o.name, o.frames, Path(o.input).read_text(), o.snap, o.snapat))
