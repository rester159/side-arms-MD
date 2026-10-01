#!/usr/bin/env python3
"""Run tools/re_sound.lua once per sound command and summarise the YM2203 logs.

usage: re_sound.py [CMD ...] [--secs-music S] [--secs-sfx S] [--no-wav] [--jobs N]
       re_sound.py --summary          (re-summarise existing logs only)
       re_sound.py --verify [CMD ...] (check tools/extract_sound.py output against the logs)
Outputs (development-only, ignored): reports/sound/cmd_XX.log, cmd_XX.wav, summary.txt
"""
import argparse, os, re, shutil, subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT

OUT = ROOT / 'reports/sound'
SFX = [c for c in range(0x01, 0x20) if c not in (0x10, 0x16, 0x19, 0x1F)]
MUSIC = list(range(0x20, 0x39))


def run(cmd, secs, wav=True):
    src = Source()
    work = OUT / f'work_{cmd:02x}'
    if work.exists():
        shutil.rmtree(work)
    romdir = work / 'roms/sidearms'
    romdir.mkdir(parents=True)
    for f in src.files:
        (romdir / f).symlink_to(src.root / f)
    for d in ('cfg', 'nvram', 'sta', 'snap', 'diff', 'home'):
        (work / d).mkdir()
    log = OUT / f'cmd_{cmd:02x}.log'
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy',
               SA_CMD=f'{cmd:02x}', SA_SECS=str(secs), SA_OUT=str(log))
    cmdline = [os.environ.get('MAME') or shutil.which('mame'), 'sidearms', '-rompath', str(romdir.parent),
               '-autoboot_delay', '0', '-autoboot_script', str(ROOT / 'tools/re_sound.lua'),
               '-video', 'none', '-sound', 'none', '-nothrottle', '-skip_gameinfo', '-noconfirm_quit',
               '-noplugins', '-nohttp', '-nowriteconfig', '-cfg_directory', 'cfg', '-nvram_directory', 'nvram',
               '-state_directory', 'sta', '-snapshot_directory', 'snap', '-diff_directory', 'diff',
               '-homepath', 'home', '-inipath', 'home']
    if wav:
        cmdline += ['-wavwrite', str(OUT / f'cmd_{cmd:02x}.wav')]
    r = subprocess.run(cmdline, cwd=work, env=env, capture_output=True, timeout=1800)
    if r.returncode != 0:
        raise SystemExit(f'cmd {cmd:02x}: ' + r.stderr.decode(errors='replace')[-2000:])
    shutil.rmtree(work)
    return log


def summarise(log):
    """Return dict: irq_hz, first/last key-on time, key-ons, active FM channels, SSG use, loop info."""
    irq, keyon, ssg_vol, writes = [], [], {}, 0
    reads = []
    for line in log.read_text().splitlines():
        p = line.split('|')
        if p[0] == 'I':
            irq.append(float(p[1]))
        elif p[0] == 'W':
            writes += 1
            t, chip, reg, val = float(p[1]), int(p[2]), int(p[3], 16), int(p[4], 16)
            if reg == 0x28 and val & 0xF0:
                keyon.append((t, chip, val & 3))
            if 8 <= reg <= 10 and val & 0x0F:
                ssg_vol.setdefault((chip, reg - 8), t)
        elif p[0] == 'R':
            reads.append((float(p[1]), int(p[2], 16)))
    s = {'writes': writes}
    if len(irq) > 10:
        s['irq_hz'] = (len(irq) - 1) / (irq[-1] - irq[0])
    if keyon:
        s['fm_first'] = keyon[0][0]; s['fm_last'] = keyon[-1][0]
        s['fm_channels'] = sorted({(c, ch) for _, c, ch in keyon})
        s['keyons'] = len(keyon)
    s['ssg_channels'] = sorted(ssg_vol)
    # loop: first stream address read twice (after a backwards jump) -> time of first revisit
    seen, loop = {}, None
    for t, a in reads:
        if a in seen and loop is None and t - seen[a] > 0.5:
            loop = (a, seen[a], t)
        seen.setdefault(a, t)
    if reads:
        s['last_read'] = reads[-1][0]
    if loop:
        s['loop'] = loop
    return s


def fmt(cmd, s):
    parts = [f'{cmd:02x}', f"writes={s['writes']}"]
    if 'irq_hz' in s: parts.append(f"irq={s['irq_hz']:.2f}Hz")
    if 'keyons' in s:
        parts.append(f"fm_keyon={s['keyons']} first={s['fm_first']:.3f}s last={s['fm_last']:.3f}s")
        parts.append('fm=' + ','.join(f'{c}.{ch}' for c, ch in s['fm_channels']))
    if s['ssg_channels']:
        parts.append('ssg=' + ','.join(f'{c}.{"ABC"[ch]}' for c, ch in s['ssg_channels']))
    if 'last_read' in s: parts.append(f"last_seq_read={s['last_read']:.3f}s")
    if 'loop' in s:
        a, t1, t2 = s['loop']; parts.append(f'loop@{a:04x} first={t1:.3f}s again={t2:.3f}s period={t2 - t1:.3f}s')
    return ' '.join(parts)


def verify(cmds=None):
    """Check the static decode (res/generated/sound.json, tools/extract_sound.py) against the MAME logs:
    every decoded event (tick, address) must appear as a sequence-data read at the same tick (+ the start
    offset measured from the first read), and looped tracks must re-read their loop address one loop later."""
    import bisect, json
    j = json.loads((ROOT / 'res/generated/sound.json').read_text())
    rows = []
    for c, e in j['commands'].items():
        if cmds and int(c, 16) not in cmds: continue
        log = OUT / f'cmd_{c}.log'
        if e['kind'] not in ('music', 'sfx') or not log.exists(): continue
        irq, reads = [], {}
        for line in log.read_text().splitlines():
            p = line.split('|')
            if p[0] == 'I': irq.append(float(p[1]))
            elif p[0] == 'R': reads.setdefault(int(p[2], 16), []).append(float(p[1]))
        tick = lambda t: bisect.bisect_right(irq, t)
        rt = {a: [tick(t) for t in ts] for a, ts in reads.items()}
        streams = [ch['events'] for ch in e['channels']] if e['kind'] == 'music' else [e['events']]
        first = [ev for evs in streams for ev in evs]
        if not first: continue
        off = min(rt.get(first[0]['a'], [10**9]))
        ok = bad = 0; worst = 0
        for ev in first:
            ts = rt.get(ev['a'], [])
            dt = min((abs(x - off - ev['t']) for x in ts), default=None)
            if dt is None: bad += 1; continue
            worst = max(worst, dt); ok += dt <= 1; bad += dt > 1
        row = f"{c} {e['kind']:5s} events={len(first)} match(+-1 tick)={ok} miss={bad} worst={worst} offset={off}"
        if e['kind'] == 'music' and e.get('loops'):
            info = e['channels'][0]['info']
            ts = rt.get(info['loop_addr'], [])
            exp = [off + info['total_ticks'] + k * info['loop_ticks'] for k in range(3)]
            got = [min((abs(x - y) for x in ts), default=None) for y in exp]
            row += f" loop@{info['loop_addr']:04x} expected_ticks={exp} err={got}"
        rows.append(row)
    print('\n'.join(rows))
    return rows


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('cmds', nargs='*')
    ap.add_argument('--secs-music', type=float, default=150)
    ap.add_argument('--secs-sfx', type=float, default=8)
    ap.add_argument('--no-wav', action='store_true')
    ap.add_argument('--jobs', type=int, default=4)
    ap.add_argument('--summary', action='store_true')
    ap.add_argument('--verify', action='store_true', help='compare logs with res/generated/sound.json')
    o = ap.parse_args()
    if o.verify:
        rows = verify([int(c, 16) for c in o.cmds] or None)
        (OUT / 'verify.txt').write_text('\n'.join(rows) + '\n'); sys.exit(0)
    OUT.mkdir(parents=True, exist_ok=True)
    cmds = [int(c, 16) for c in o.cmds] or (SFX + MUSIC)
    if not o.summary:
        with ThreadPoolExecutor(o.jobs) as ex:
            list(ex.map(lambda c: run(c, o.secs_music if c >= 0x20 else o.secs_sfx, not o.no_wav), cmds))
    lines = [fmt(c, summarise(OUT / f'cmd_{c:02x}.log')) for c in cmds if (OUT / f'cmd_{c:02x}.log').exists()]
    (OUT / 'summary.txt').write_text('\n'.join(lines) + '\n')
    print('\n'.join(lines))
