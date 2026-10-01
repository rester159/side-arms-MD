#!/usr/bin/env python3
"""Home-mode parallax checks (development only, docs/parallax.md).

  parallax_check.py soak  [--players 1|2] [--sections 0-9] [--frames N] [--arcade] [--off]
      tools/qa_soak.py's bot and frame-drop measurement, but the game is started through the
      HOME screen (PARALLAX ON by default; --off turns it off in OPTIONS first; --arcade = the
      Arcade path, as qa_soak.py).
  parallax_check.py shots [--sections 0-9] [--at f1,f2,..] [--seq N] [--out reports/parallax]
      warp to each section and save screenshots (a short sequence of every 4th frame with --seq).
Run with SIDEARMS_BUILD=dir to test a snapshot build."""
import argparse, os, struct, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
import qa_soak
from run_rom import PAD, ROOT

FS_PLAY, FS_HOME = 7, 9


def start_home(r, parallax=True):
    """boot -> HOME (cursor down, START) -> START GAME -> stage 1. parallax=False pokes the Home
    PARALLAX setting to OFF on the boot screen (flow_apply_config picks it up with HOME)."""
    for f in range(12000):
        st = r.u32('flow_state'); fc = r.u32('frame_counter')
        if st == FS_PLAY:
            return f
        k = f % 40
        mask = 0
        if fc == 0:
            pass
        elif st == 0:                                   # boot screen: cursor to HOME, START
            if not parallax:
                r.write('home_cfg', [0], offset=5)      # HomeSettings.parallax
            home = r.read('cursor', 1)[0] == 1
            mask = (PAD['START'] if home else PAD['DOWN']) if k < 4 else 0
        elif st == FS_HOME:
            mask = PAD['START'] if k < 4 else 0
        else:                                           # NAMING / intro: START, A
            mask = PAD['START'] if k < 4 else PAD['A'] if 20 <= k < 24 else 0
        r.run(1, mask)
    raise SystemExit('front end did not reach FS_PLAY (home)')


def use_home(parallax=True):
    qa_soak.start_game = lambda r: start_home(r, parallax)


def shots(o):
    from run_rom import Runner
    out = Path(o.out); out.mkdir(parents=True, exist_ok=True)
    lo, _, hi = o.sections.partition('-')
    for sec in range(int(lo), int(hi or lo) + 1):
        b = qa_soak.Bot(1)
        r = b.r
        r.write('dbg_warp', struct.pack('>H', sec + 1))
        b.pad(0, 0); r.run(2)
        for _ in range(600):
            if b.lvl('section') == sec and not r.u16('dbg_warp'):
                break
            b.keep_alive(); r.run(1)
        at = [int(v) for v in o.at.split(',')]
        f = 0
        frames = []
        for t in at:
            while f < t:
                b.keep_alive(); b.pad(b.steer(0, f), 0); r.run(1); f += 1
            if o.seq:
                seq = []
                for i in range(o.seq):
                    seq.append(np.array(r.frame))
                    for _ in range(4):
                        b.keep_alive(); b.pad(b.steer(0, f), 0); r.run(1); f += 1
                Image.fromarray(np.concatenate(seq, 0)).save(out / f'{o.tag}s{sec + 1}_f{t}_seq.png')
            frames.append(np.array(r.frame))
            mode = r.read('par_dbg_mode', 1)[0] if 'par_dbg_mode' in r.symbols else -1
            print(f'section {sec + 1} frame {t}: cam {b.lvl("scroll_x")},{b.lvl("scroll_y")} mode {mode} '
                  f'band {r.read("par_dbg_band", 1)[0] if "par_dbg_band" in r.symbols else -1}')
        Image.fromarray(np.concatenate(frames, 1) if len(frames) < 4 else
                        np.concatenate([np.concatenate(frames[i:i + 3], 1) for i in range(0, len(frames) // 3 * 3, 3)], 0)
                        ).save(out / f'{o.tag}s{sec + 1}.png')


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('cmd', choices=['soak', 'shots'])
    a.add_argument('--players', type=int, default=1)
    a.add_argument('--sections', default='0-9')
    a.add_argument('--frames', type=int, default=6000)
    a.add_argument('--arcade', action='store_true')
    a.add_argument('--off', action='store_true')
    a.add_argument('--at', default='100,600,1200')
    a.add_argument('--seq', type=int, default=0)
    a.add_argument('--tag', default='')
    a.add_argument('--out', default=str(ROOT / 'reports/parallax'))
    o = a.parse_args()
    if not o.arcade:
        use_home(not o.off)
    if o.cmd == 'shots':
        shots(o)
        sys.exit()
    lo, _, hi = o.sections.partition('-')
    tot_f = tot_l = 0
    for s in range(int(lo), int(hi or lo) + 1):
        res = qa_soak.run_section(s, o.players, o.frames, None)
        ctx = res.pop('lagctx')
        tot_f += res['frames']; tot_l += res['lag']
        print('section %2d %dP: %6d frames, dropped %4d (%.2f%%), worst loop %3d lines, end: %s' % (
            s + 1, res['players'], res['frames'], res['lag'], 100.0 * res['lag'] / res['frames'], res['worst_line'],
            res['end']))
        for c in ctx[:12]:
            print('     ', c)
        sys.stdout.flush()
    print('total %d frames, dropped %d (%.2f%%)' % (tot_f, tot_l, 100.0 * tot_l / max(tot_f, 1)))
