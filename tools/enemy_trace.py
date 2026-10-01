#!/usr/bin/env python3
"""Enemy-module verification (development only, docs/enemies.md).

  enemy_trace.py arcade [--frames N] [--fire]   run tools/enemy_trace.lua in MAME -> reports/oracle/enemy_trace/trace.txt
  enemy_trace.py port [--frames N] [--fire]     run the built cartridge headless   -> reports/port/enemy_trace.txt
  enemy_trace.py compare                        compare the two traces (spawn moments/positions, motion)

Both runs play stage 1 with an idle, invincible player 1. The traces use arcade units (sprite
coordinates, scroll) so they can be compared directly; frames are aligned on the camera (the
arcade's BG scroll x)."""
import argparse, os, shutil, subprocess, sys
from collections import defaultdict
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT

ARC = ROOT / 'reports/oracle/enemy_trace'
PORT = ROOT / 'reports/port/enemy_trace.txt'


def run_arcade(frames, fire, stage=1):
    src = Source()
    if ARC.exists():
        shutil.rmtree(ARC)
    romdir = ARC / 'roms/sidearms'
    romdir.mkdir(parents=True)
    for f in src.files:
        (romdir / f).symlink_to(src.root / f)
    for d in ('cfg', 'nvram', 'sta', 'snap', 'diff', 'home'):
        (ARC / d).mkdir()
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', SA_FRAMES=str(frames),
               SA_FIRE='1' if fire else '0', SA_STAGE=str(stage))
    cmd = [os.environ.get('MAME') or shutil.which('mame'), 'sidearms', '-rompath', str(romdir.parent),
           '-autoboot_delay', '0', '-autoboot_script', str(ROOT / 'tools/enemy_trace.lua'),
           '-video', 'none', '-sound', 'none', '-nothrottle', '-skip_gameinfo', '-noconfirm_quit',
           '-noplugins', '-nohttp', '-nowriteconfig', '-cfg_directory', 'cfg', '-nvram_directory', 'nvram',
           '-state_directory', 'sta', '-snapshot_directory', 'snap', '-diff_directory', 'diff',
           '-homepath', 'home', '-inipath', 'home']
    r = subprocess.run(cmd, cwd=ARC, env=env, capture_output=True, timeout=3600)
    lines = (ARC / 'trace.txt').read_text().splitlines()
    assert r.returncode == 0 and lines[-1] == 'COMPLETE', r.stderr[-2000:]
    print('arcade trace', ARC / 'trace.txt', len(lines))


FS_PLAY = 7          # FlowState (inc/flow.h)
P_SIZE, P_INVULN = 280, 25   # sizeof(Player), offsetof(Player, invuln) (inc/player.h; +1 since Player.vertical)
E_SIZE = 40                  # sizeof(Enemy) (src/enemy_int.h)


def start_game(r):
    """Front end -> stage 1 with player 1 (inc/flow.h states); returns the frame count used."""
    from run_rom import PAD
    for f in range(6000):
        st = int.from_bytes(r.read('flow_state', 4), 'big')
        if st == FS_PLAY:
            return f
        k = f % 40
        if st in (0, 1):                                  # mode select / setup: START
            mask = PAD['START'] if k < 4 else 0
        elif st in (2, 3, 4):                             # warning / title / demo: coin (C) then START
            mask = PAD['C'] if k < 4 else PAD['START'] if 20 <= k < 24 else 0
        else:                                             # credit / NAMING / intro: START, button A
            mask = PAD['START'] if k < 4 else PAD['A'] if 20 <= k < 24 else 0
        r.run(1, mask)
    raise SystemExit('front end did not reach FS_PLAY')


def run_port(frames, fire, align=1042, stage=1):
    from run_rom import Runner, PAD
    r = Runner()
    used = start_game(r)
    if stage > 1:
        r.write('dbg_warp', bytes([0, stage]))                  # level.c test hook: section stage-1
    pools = [('en_small', 16, 0xF000, 0x20), ('en_big', 9, 0xF600, 0x80), ('en_item', 8, 0xFF00, 0x20)]
    out = []
    # RNG sync (probe only): when the port's camera makes its first scroll step, load $E008 and its
    # 3-frame phase from the arcade trace at the same moment, so RNG-driven choices can be compared
    arng, acam, atick, aloop = {}, {}, {}, {}
    if ARC.exists() and (ARC / 'trace.txt').exists():
        for ln in (ARC / 'trace.txt').read_text().splitlines():
            v = ln.split('|')
            if v[0] == 'R':
                arng[int(v[1])] = bytes.fromhex(v[5]) if len(v) > 5 else bytes([int(v[2])])
                aloop[int(v[1])] = int(v[3])
                if len(v) > 6:
                    atick[int(v[1])] = int(v[6])
            elif v[0] == 'F':
                acam[int(v[1])] = (int(v[2]), int(v[3]))
    synced = False
    prev_cam = None
    g0 = r.u16('frame')
    last = None
    for f in range(1, frames + 1):
        # time axis = the game's own frame counter, so frames the 68000 drops (lag) don't shift
        # the timeline against the arcade's
        g = (r.u16('frame') - g0) & 0xFFFF
        af = g + 1 + align                                      # the arcade frame this game frame matches
        mask = (PAD['B'] if (af // 4) % 2 else 0) if fire and af >= 1100 else 0
        r.write('players', bytes([200]), offset=P_INVULN)          # invincible P1 (probe only)
        r.run(1, mask)
        g = (r.u16('frame') - g0) & 0xFFFF
        if g == last:
            continue
        last = g
        f = g
        lv = r.read('level', 8)
        sx = int.from_bytes(lv[4:6], 'big', signed=True) & 0xFFF
        sy = int.from_bytes(lv[6:8], 'big', signed=True) & 0xFFF
        if not synced and prev_cam and abs(prev_cam[0] - sx) + abs(prev_cam[1] - sy) == 1:
            fa = next((k for k in sorted(acam) if acam[k] == (sx, sy) and acam.get(k - 1) == prev_cam), None)
            if fa and arng:
                # phase: frames since the arcade's last $E008 step
                ph = 0
                while ph < 3 and arng.get(fa - ph) == arng.get(fa - ph - 1):
                    ph += 1
                r.write('en_rng', arng[fa][:1])
                if len(arng[fa]) == 8:
                    r.write('en_rnd', arng[fa][1:])
                if fa in atick:
                    r.write('en_target_tick', bytes([atick[fa]]))
                r.write('en_rng_div', bytes([ph % 3]))
            if fa:
                # frame phase: the port's `frame` plays the arcade loop counter $E003 (free-running
                # since boot; arcade traces show $E003 = frame - 20). Weapons gate on its low bits
                # (AUTO $10 every 4, AUTO $11 every 8 frames, B2:$8C0D/$8C85): with the 4-on/4-off
                # autofire input an unsynced phase makes AUTO $11 fire either always or never.
                e3 = aloop.get(fa, (fa - 20) & 0xFF)
                cur = r.u16('frame')
                if (cur ^ e3) & 1:
                    print('warning: frame parity differs from the arcade at sync (camera alignment)')
                r.write('frame', ((cur & 0xFF00) | e3).to_bytes(2, 'big'))
                g0 = (g0 + (((cur & 0xFF00) | e3) - cur)) & 0xFFFF
                align = fa - f                                  # inputs follow the matched arcade frame
            synced = True
        prev_cam = (sx, sy)
        pl = r.read('players', 26)
        out.append('F|%d|%d|%d|%d|%d|%d|%s' % (f, sx, sy, (int.from_bytes(pl[8:10], 'big', signed=True) + 16) & 0xFF,
                                              int.from_bytes(pl[6:8], 'big', signed=True) + 96, pl[3],
                                              bytes([pl[17]] + list(pl[19:24]) + [pl[16]]).hex()))   # weapon, levels[1..5], speed
        sh = r.read('players', 36 + 22 * 9)                     # Player.shots at +36, Shot = 22 bytes
        for i in range(9):
            q = sh[36 + 22 * i:36 + 22 * (i + 1)]
            if q[8]:
                out.append('S|%d|%04x|%d|%d|%d|%d|%d' % (f, 0xF2E0 + 0x20 * i, (int.from_bytes(q[2:4], 'big', signed=True) + 16) & 0xFF,
                                                        int.from_bytes(q[0:2], 'big', signed=True) + 96, q[8], q[13], q[12] // 2))
        for name, n, base, stride in pools:
            raw = r.read(name, E_SIZE * n)
            for i in range(n):
                e = raw[i * E_SIZE:(i + 1) * E_SIZE]
                if not e[0]:
                    continue
                x = int.from_bytes(e[4:6], 'big', signed=True) + 96
                y = (int.from_bytes(e[6:8], 'big', signed=True) + 16) & 0xFF
                code = int.from_bytes(e[12:14], 'big')
                out.append('O|%d|%04x|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d' % (f, base + stride * i, y, x, code, e[11], e[2], e[16], e[10],
                                                                    e[22], e[23], e[28], e[29]))   # r[0], r[1], r[6], r[7]
    PORT.parent.mkdir(parents=True, exist_ok=True)
    PORT.write_text('\n'.join(out) + '\nCOMPLETE\n')
    print('port trace', PORT, len(out), 'front end frames', used)


def load(path):
    cam, objs = {}, defaultdict(dict)
    for ln in Path(path).read_text().splitlines():
        v = ln.split('|')
        if v[0] == 'F':
            cam[int(v[1])] = (int(v[2]), int(v[3]), int(v[4]), int(v[5]))
        elif v[0] == 'O':
            objs[int(v[1])][int(v[2], 16)] = tuple(int(t) for t in v[3:])
    return cam, objs


REGIONS = (('big', 0xF600, 0xFA80), ('small', 0xF000, 0xF200), ('item', 0xFF00, 0x10000))


def lives(cam, objs, lo, hi, f0, f1):
    """object lifetimes in [f0, f1): (first frame, slot, [records per frame])"""
    out, cur = [], {}
    for f in range(f0, f1):
        now = {a: o for a, o in objs.get(f, {}).items() if lo <= a < hi}
        for a in list(cur):
            if a not in now:
                out.append(cur.pop(a))
        for a, o in now.items():
            if a not in cur:
                cur[a] = (f, a, [])
            cur[a][2].append(o)
    out += cur.values()
    return sorted(out)


def compare(verbose=False):
    ac, ao = load(ARC / 'trace.txt')
    pc, po = load(PORT)
    # stage start = first frame the camera moves after the stage's own start position (both runs
    # start the section at the same scroll; the arcade first shows the intro / previous screens)
    def start(cam, frm, to):
        fs = sorted(cam)
        for i in range(1, len(fs)):
            if cam[fs[i - 1]][:2] == frm and cam[fs[i]][:2] == to:
                return fs[i]
        raise SystemExit('stage start not found')
    pf = sorted(pc)
    frm = to = None
    for i in range(1, len(pf)):                 # first one-pixel scroll step of the port run
        u, v = pc[pf[i - 1]][:2], pc[pf[i]][:2]
        if abs(u[0] - v[0]) + abs(u[1] - v[1]) == 1:
            frm, to = u, v
            break
    a0, p0 = start(ac, frm, to), start(pc, frm, to)
    off = p0 - a0
    a1 = max(ac)
    p1 = max(pc)
    end = min(a1, p1 - off)
    print('stage start: arcade frame %d, port frame %d (offset %+d); compared %d frames' % (a0, p0, off, end - a0))
    # camera agreement
    bad = sum(1 for f in range(a0, end) if ac[f][:2] != pc[f + off][:2])
    print('camera: %d of %d frames differ' % (bad, end - a0))
    for name, lo, hi in REGIONS:
        la = lives(ac, ao, lo, hi, a0, end)
        lp = lives(pc, po, lo, hi, a0 + off, end + off)
        used, hits, exact, delays, worst = set(), 0, 0, [], []
        for fa, sa, ra in la:
            cand = [k for k, (fp, sp, rp) in enumerate(lp) if k not in used and abs(fp - off - fa) <= 2
                    and abs(rp[0][0] - ra[0][0]) <= 4 and abs(rp[0][1] - ra[0][1]) <= 8]
            if not cand:
                continue
            k = cand[0]
            used.add(k)
            hits += 1
            fp, sp, rp = lp[k]
            delays.append(fp - off - fa)
            n = min(len(ra), len(rp), 240)
            d = max(max(abs(ra[i][0] - rp[i][0]), abs(ra[i][1] - rp[i][1])) for i in range(n))
            worst.append((d, fa, hex(sa), ra[0][2], n))
            if d == 0:
                exact += 1
        worst.sort(reverse=True)
        print('%-5s arcade %4d port %4d matched %4d (spawn frame +-2, pos +-4/8); identical paths (first <=240 f) %d; '
              'spawn delay hist %s' % (name, len(la), len(lp), hits, exact,
                                       {d: delays.count(d) for d in sorted(set(delays))}))
        if verbose:
            for w in worst[:8]:
                print('      worst: max |dpos| %d  arcade frame %d slot %s code %03X over %d frames' % w)
            unmatched = [(fa, hex(sa), ra[0]) for fa, sa, ra in la if not any(
                abs(fp - off - fa) <= 2 and abs(rp[0][0] - ra[0][0]) <= 4 and abs(rp[0][1] - ra[0][1]) <= 8
                for fp, sp, rp in lp)]
            for u in unmatched[:10]:
                print('      arcade-only: frame %d slot %s first %s' % u)


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('what', choices=['arcade', 'port', 'compare'])
    a.add_argument('--frames', type=int, default=6000)
    a.add_argument('--fire', action='store_true')
    a.add_argument('-v', action='store_true')
    a.add_argument('--stage', type=int, default=1)
    a.add_argument('--align', type=int, default=1042, help='arcade frame - port frame (stage start)')
    o = a.parse_args()
    tag = ('_fire' if o.fire else '') + ('_s%02d' % o.stage if o.stage > 1 else '')
    ARC = ROOT / ('reports/oracle/enemy_trace' + tag)
    PORT = ROOT / ('reports/port/enemy_trace' + tag + '.txt')
    if o.what == 'arcade':
        run_arcade(o.frames, o.fire, o.stage)
    elif o.what == 'port':
        run_port(o.frames, o.fire, o.align, o.stage)
    else:
        compare(o.v)
