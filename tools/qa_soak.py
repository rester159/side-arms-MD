#!/usr/bin/env python3
"""QA soak / frame-rate bot for the built cartridge (development only, docs/qa.md).

  qa_soak.py [--players 1|2] [--sections 0-9] [--frames N] [--sheet] [--out reports/qa]

For each section: start a game through the real front end (2P: pad 2 Start, NAMING timeout),
warp to the section start (`dbg_warp`), then play it with an invincible autofire bot (AUTO $11,
lives topped up, steering in a slow vertical sweep) until the next section starts or the frame
limit. Measures, per section: frames the 68000 dropped (`frame_counter` vs runner frames), the
worst `prof_line`, sprites the display list had to drop (`spr_dbg_dropped`), crushes, hangs
(frame_counter frozen for 60 frames = 68000 exception), and saves a contact sheet of screenshots.
Run with SIDEARMS_BUILD=dir to test a snapshot build."""
import argparse, os, re, struct, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.path.insert(0, str(Path(__file__).parent))
from run_rom import Runner, ROOT
from enemy_trace import start_game

BUILD = Path(os.environ.get('SIDEARMS_BUILD', ROOT))
IN = dict(R=1, L=2, D=4, U=8, A=0x10, B=0x20, C=0x40, S=0x80)
GDK = Path(os.environ.get('GDK', Path.home() / 'mars/m68k-elf'))


def offsets():
    """Struct offsets from the compiler, so the bot follows inc/*.h changes."""
    src = '''#include "game.h"
#include "boss.h"
#define O(t, f) int o_##t##_##f = __builtin_offsetof(t, f);
O(Player, state) O(Player, x) O(Player, y) O(Player, lives) O(Player, invuln) O(Player, score)
O(Player, in_play) O(Player, weapon)
O(Level, section) O(Level, scroll_x) O(Level, scroll_y) O(Level, mode) O(Level, tick)
O(BossHud, active) O(BossHud, bars)
int s_Player = sizeof(Player);
'''
    tmp = ROOT / '.local/qa'; tmp.mkdir(parents=True, exist_ok=True)
    (tmp / 'off.c').write_text(src)
    subprocess.run([str(GDK / 'bin/m68k-elf-gcc'), '-m68000', '-w', '-I', str(BUILD / 'inc'), '-I', str(GDK / 'inc'),
                    '-I', str(GDK / 'res'), '-S', '-o', str(tmp / 'off.s'), str(tmp / 'off.c')], check=True)
    o, name = {}, None
    for line in (tmp / 'off.s').read_text().splitlines():
        m = re.match(r'^(\w+):', line)
        if m:
            name = m.group(1); continue
        m = re.match(r'\s+\.(long|zero)\s+(\d+)', line)
        if m and name:
            o[name] = 0 if m.group(1) == 'zero' else int(m.group(2)); name = None
    return o


O = offsets()
REMAPPED = set()        # sprite (code | colour << 11) the bank lacked (runtime remap): --collect


class Bot:
    def __init__(self, players=1):
        self.r = r = Runner()
        start_game(r)
        self.prev = [0, 0]
        self.edge = [0, 0]
        self.fc = None
        self.players = players
        if players == 2:                # pad 2 Start: join through the real flow (NAMING timeout)
            for f in range(8):
                self.keep_alive(1)
                self.pad(0, IN['S'] if f < 4 else 0); r.run(1)
            for f in range(900):
                self.keep_alive(1)
                self.pad(0, 0); r.run(1)
                if self.pl(1, 'in_play'):
                    break
            else:
                raise SystemExit('player 2 did not join')

    def pad(self, p0, p1):
        # 'pressed' edges stay set until a game loop that started after the write has run
        # (frame_counter + 2: the loop in progress may already have read the pads; a long frame
        # spans several runner frames, so an edge written over one of them would be lost)
        fc = self.r.u32('frame_counter')
        if self.fc is None or fc - self.fc >= 2:
            self.edge = [0, 0]; self.fc = fc
        for i, v in enumerate((p0, p1)):
            e = v & ~self.prev[i] & 0xFF
            if e and not self.edge[i]:
                self.fc = fc                        # the edge lives from this loop on
            self.edge[i] |= e
            self.r.write('pad', [v, self.edge[i]], offset=2 * i); self.prev[i] = v
        self.r.write('dbg_pad_override', [1])

    def pl(self, i, f, n=1, signed=False):
        b = self.r.read('players', n, offset=i * O['s_Player'] + O['o_Player_' + f])
        return int.from_bytes(b, 'big', signed=signed)

    def wpl(self, i, f, data):
        self.r.write('players', data, offset=i * O['s_Player'] + O['o_Player_' + f])

    def lvl(self, f, n=2, signed=False):
        return int.from_bytes(self.r.read('level', n, offset=O['o_Level_' + f]), 'big', signed=signed)

    def keep_alive(self, n=None):
        for i in range(self.players if n is None else n):
            self.wpl(i, 'invuln', [200])
            if self.pl(i, 'lives') < 3:
                self.wpl(i, 'lives', [5])
            if self.pl(i, 'in_play') and self.pl(i, 'state', 4) == 1 and self.pl(i, 'weapon') != 5:
                self.r.write('dbg_player_cmd', [0x11], offset=i)    # weapon lost at a death: AUTO again

    def steer(self, i, f):
        """slow vertical sweep, x around 1/4 of the screen; fire right (AUTO: hold)"""
        y, x = self.pl(i, 'y', 2, True), self.pl(i, 'x', 2, True)
        ty = 40 + int(60 * (1 + np.sin(f / 90.0 + i * 2)))
        tx = 64 + 40 * i
        m = IN['B']
        if y < ty - 3: m |= IN['D']
        elif y > ty + 3: m |= IN['U']
        if x < tx - 3: m |= IN['R']
        elif x > tx + 3: m |= IN['L']
        return m


def run_section(sec, players, frames, sheet_dir, nshots=12, autohit=True):
    b = Bot(players)
    r = b.r
    r.write('dbg_warp', struct.pack('>H', sec + 1))
    for i in range(players):
        r.write('dbg_player_cmd', [0x11], offset=i)       # AUTO $11 (star)
    b.pad(0, 0); r.run(2)
    for _ in range(600):                                  # the warp applies on the next level update
        if b.lvl('section') == sec and not r.u16('dbg_warp'):
            break
        b.keep_alive(); r.run(1)
    fc = r.u32('frame_counter')
    lag, lagctx, frozen, worst_line, deaths, shots = 0, [], 0, 0, 0, []
    boss_frames, boss_run, bosses = 0, 0, 0
    drop0 = r.u32('spr_dbg_dropped') if 'spr_dbg_dropped' in r.symbols else 0
    alive = [b.pl(i, 'state', 4) for i in range(2)]
    start_sec = sec
    end_reason = 'frame limit'
    pending = 0
    remap_n = r.u32('spr_dbg_remap') if 'spr_dbg_remap' in r.symbols else 0
    up0 = r.u16('uploads') if 'uploads' in r.symbols else 0
    ms0 = r.u16('misses') if 'misses' in r.symbols else 0
    for f in range(frames):
        b.keep_alive()
        b.pad(b.steer(0, f), b.steer(1, f) if players == 2 else 0)
        r.run(1)
        nfc = r.u32('frame_counter')
        up = r.u16('uploads') if 'uploads' in r.symbols else 0
        ms = r.u16('misses') if 'misses' in r.symbols else 0
        if nfc == fc:
            lag += 1; frozen += 1; pending += 1
            if frozen >= 60:
                end_reason = 'HANG (frame_counter frozen 60 frames)'; break
        else:
            frozen = 0
            seg = struct.unpack('>4H', r.read('prof_seg', 8)) if 'prof_seg' in r.symbols else (0, 0, 0, 0)
            worst_line = max(worst_line, seg[3])
            if pending:
                # the loop that just completed overran: where its time went (lines since VBlank)
                lagctx.append((f, b.lvl('tick'), seg, (up - up0) & 0xFFFF, (ms - ms0) & 0xFFFF))
            pending = 0
        up0, ms0 = up, ms
        fc = nfc
        if 'spr_dbg_remap' in r.symbols:
            n = r.u32('spr_dbg_remap')
            if n != remap_n:
                ring = struct.unpack('>64H', r.read('spr_dbg_remap_key', 128))
                for i in range(remap_n, n):
                    REMAPPED.add(ring[i & 63])
                remap_n = n
        for i in range(2):
            st = b.pl(i, 'state', 4)
            if st == 2 and alive[i] != 2: deaths += 1
            alive[i] = st
        if r.read('boss_hud', 1, O['o_BossHud_active'])[0] or r.read('kind', 1)[0]:
            boss_frames += 1; boss_run += 1
            # bosses: after 1500 frames of fighting, every hit test also counts one P1 shot
            # (boss_dbg_autohit) so the real damage / score / death paths finish the fight
            if boss_run == 1500 and autohit and 'boss_dbg_autohit' in r.symbols:
                r.write('boss_dbg_autohit', [1])
        elif boss_run:
            boss_run = 0; bosses += 1
            if 'boss_dbg_autohit' in r.symbols:
                r.write('boss_dbg_autohit', [0])
        if f % 500 == 250:
            shots.append(np.array(r.frame))
        s = b.lvl('section')
        if s != start_sec:
            end_reason = 'next section %d' % s; shots.append(np.array(r.frame)); break
        if r.u32('flow_state') != 7:
            end_reason = 'left play (flow %d)' % r.u32('flow_state'); break
    drop = (r.u32('spr_dbg_dropped') if 'spr_dbg_dropped' in r.symbols else 0) - drop0
    res = dict(section=sec, players=players, frames=f + 1, lag=lag, worst_line=worst_line, deaths=deaths,
               boss_frames=boss_frames, bosses=bosses, spr_dropped=drop, end=end_reason, lagctx=lagctx,
               score=[b.pl(i, 'score', 4) for i in range(players)])
    if sheet_dir:
        cols = 4
        pick = np.linspace(0, len(shots) - 1, min(16, len(shots))).round().astype(int) if shots else []
        ims = [shots[k] for k in pick]
        while len(ims) % cols: ims.append(np.zeros_like(ims[0]))
        grid = np.concatenate([np.concatenate(ims[k:k + cols], 1) for k in range(0, len(ims), cols)], 0)
        Image.fromarray(grid).save(Path(sheet_dir) / ('section%d_%dp.png' % (sec + 1, players)))
    return res


if __name__ == '__main__':
    a = argparse.ArgumentParser()
    a.add_argument('--players', type=int, default=1)
    a.add_argument('--sections', default='0-9')
    a.add_argument('--frames', type=int, default=30000)
    a.add_argument('--out', default=str(ROOT / 'reports/qa'))
    a.add_argument('--nosheet', action='store_true')
    a.add_argument('--collect', action='store_true', help='add remapped sprite keys to tools/sprite_pairs.json')
    o = a.parse_args()
    lo, _, hi = o.sections.partition('-')
    secs = range(int(lo), int(hi or lo) + 1)
    Path(o.out).mkdir(parents=True, exist_ok=True)
    for s in secs:
        res = run_section(s, o.players, o.frames, None if o.nosheet else o.out)
        ctx = res.pop('lagctx')
        print('section %2d %dP: %6d frames, dropped %4d (%.2f%%), worst loop %3d lines, deaths %d, bosses %d (%d frames), '
              'sprites dropped %d, score %s, end: %s' % (s + 1, res['players'], res['frames'], res['lag'],
                                                         100.0 * res['lag'] / res['frames'], res['worst_line'],
                                                         res['deaths'], res['bosses'], res['boss_frames'], res['spr_dropped'],
                                                         res['score'], res['end']))
        if ctx:
            print('   slow loops (runner frame, section tick, prof_seg start/update/draw/video lines, sprite uploads, bg misses):')
            for c in ctx[:40]:
                print('     ', c)
        sys.stdout.flush()
    if REMAPPED:
        print('sprite patterns missing from the bank (runtime remap):', sorted('%03X/c%d' % (k & 0x7FF, k >> 11) for k in REMAPPED))
        if o.collect:
            import json
            p = ROOT / 'tools/sprite_pairs.json'
            old = set(json.loads(p.read_text())) if p.exists() else set()
            p.write_text(json.dumps(sorted(old | REMAPPED)))
            print('added to', p, len(REMAPPED - old))
