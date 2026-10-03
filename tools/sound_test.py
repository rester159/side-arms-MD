#!/usr/bin/env python3
"""Verify the Genesis sound driver against the arcade, under MAME (development-only).

For every test case the arcade ('sidearms', tools/re_sound_seq.lua) and the sound test cartridge
(tests/sound_rom under 'genesis', tools/sound_test.lua) are run with the same command schedule:
the arcade gets its latch forced per frame, its per-tick latch reads give the tick of every command,
and the cartridge gets the same commands pushed into the driver FIFO at the same driver ticks, with
the tick counter ($C000 copy) planted to the arcade's value so triplet / slide parity agree.
Checks per tick:
  FM   musical equivalence: per tick the same key-on/off writes (order, channel, slots) and pitch
       writes as the arcade's YM2203 FM writes mapped to the port (chip 2 -> part II, key-on codes 4-6,
       F-numbers through the region table), and operator / FB-ALG state after the explicit
       carrier-only music attenuation. Also counted: raw write-identical ticks (before mix adjustment).
  PSG  the PSG state must equal tools/sound_model.py applied to the arcade's SSG register images.
  CMD  the driver takes each command on the scheduled tick.
Audio (MAME -wavwrite of both machines, informative): RMS envelope correlation and sounding length.
An --api case sends commands through the 68000 sound_command() and checks they arrive in order.

usage: sound_test.py [CASE ...] [--jobs N] [--rerun-arcade] [--no-build] [--music-secs S]
  CASE = cmd_XX (one command in isolation) or a scenario name (see SCENARIOS); default: all.
Outputs: reports/sound_port/{arcade,md}/CASE.{log,wav}, reports/sound_port/report.txt
"""
import argparse, json, os, shutil, subprocess, sys, wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT
import sound_model as sm
from build_sound import CARRIER_MASKS, MUSIC_TL

OUT = ROOT / 'reports/sound_port'
CART = ROOT / 'tests/sound_rom'
MAME = os.environ.get('MAME') or shutil.which('mame')
SFX = [c for c in range(0x01, 0x20) if c not in (0x10, 0x16, 0x19, 0x1F)]
MUSIC = list(range(0x20, 0x39))
# name: (secs, [(frame, cmd), ...]) ; frames are arcade frames (60 Hz) after the start
SCENARIOS = {
    # Sustained two-player-style shots/explosions: exercise priority replacement,
    # cached slot selection and rapid period slides over a looping music track.
    'scn_combat': (20, [(0, 0x21)] +
                   [(f, (0x07, 0x01, 0x08, 0x02, 0x03, 0x09)[(f // 4) % 6])
                    for f in range(4, 1100, 4)] + [(1120, 0x00)]),
    # game over ($2E, set $C300) over stage BGM ($21, set $C200): freeze, silence, resume
    'scn_priority': (22, [(0, 0x21), (600, 0x2E)]),
    # same set restarted (no set change -> 2-tick start), another song in the same set, $38 in $C100
    # under it (frozen), stop of the higher set via an empty $C200 track ($2B) -> $38 resumes
    'scn_sets': (24, [(0, 0x38), (120, 0x21), (300, 0x21), (500, 0x24), (800, 0x2B), (1000, 0x2D)]),
    # SFX priorities / kills on both chips while music plays, then stop commands
    'scn_sfx': (12, [(0, 0x23), (30, 0x01), (32, 0x09), (34, 0x01), (60, 0x1E), (64, 0x0E), (70, 0x05),
                     (100, 0x11), (102, 0x0C), (104, 0x12), (110, 0x1A), (140, 0x1C), (150, 0x13),
                     (300, 0x16), (310, 0x0D), (320, 0x1D), (400, 0x10), (420, 0x08), (430, 0x3A),
                     (440, 0x22), (520, 0x00), (560, 0x2E), (600, 0x03), (601, 0x02)]),
}


def mame(args, work, env, timeout=1800):
    if work.exists():
        shutil.rmtree(work)
    for d in ('cfg', 'nvram', 'sta', 'snap', 'diff', 'home'):
        (work / d).mkdir(parents=True)
    cmd = [MAME] + args + ['-autoboot_delay', '0', '-video', 'none', '-sound', 'none', '-nothrottle',
                           '-skip_gameinfo', '-noconfirm_quit', '-noplugins', '-nohttp', '-nowriteconfig',
                           '-cfg_directory', 'cfg', '-nvram_directory', 'nvram', '-state_directory', 'sta',
                           '-snapshot_directory', 'snap', '-diff_directory', 'diff', '-homepath', 'home',
                           '-inipath', 'home']
    r = subprocess.run(cmd, cwd=work, env=dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', **env),
                       capture_output=True, timeout=timeout)
    if r.returncode != 0:
        raise SystemExit(f'MAME failed: {" ".join(args[:2])}\n' + r.stderr.decode(errors='replace')[-2000:])
    shutil.rmtree(work)


def run_arcade(name, secs, seq):
    log, wav = OUT / 'arcade' / f'{name}.log', OUT / 'arcade' / f'{name}.wav'
    log.parent.mkdir(parents=True, exist_ok=True)
    src = Source(); work = OUT / f'work_a_{name}'
    romdir = work / 'roms/sidearms'
    if work.exists():
        shutil.rmtree(work)
    romdir.mkdir(parents=True)
    for f in src.files:
        (romdir / f).symlink_to(src.root / f)
    tmp = OUT / f'roms_{name}'
    if tmp.exists():
        shutil.rmtree(tmp)
    shutil.move(str(work / 'roms'), tmp)
    try:
        mame(['sidearms', '-rompath', str(tmp), '-autoboot_script', str(ROOT / 'tools/re_sound_seq.lua'),
              '-wavwrite', str(wav)], work,
             dict(SA_SEQ=','.join(f'{f}:{c:02x}' for f, c in seq), SA_SECS=str(secs), SA_OUT=str(log)))
    finally:
        shutil.rmtree(tmp)
    return log


REGION = 'ntsc'                     # --pal: MAME 'megadriv' (PAL) and the PAL tables


def run_md(name, secs, inject=None, c000=None, api=None):
    sub = 'md' if REGION == 'ntsc' else 'md_pal'
    log, wav = OUT / sub / f'{name}.log', OUT / sub / f'{name}.wav'
    log.parent.mkdir(parents=True, exist_ok=True)
    env = dict(ST_SECS=str(secs), ST_OUT=str(log))
    if inject:
        env['ST_SEQ'] = ','.join(f'{t}:{c:02x}' for t, c in inject)
    if c000 is not None:
        env['ST_C000'] = str(c000)
    if api:
        env['ST_API'] = ','.join(f'{f}:{c:02x}' for f, c in api)
        env['ST_HOST'] = f'{symbol("host_cmd"):x}'
    mame(['genesis' if REGION == 'ntsc' else 'megadriv', '-cart', str(CART / 'out/release/rom.bin'), '-autoboot_script',
          str(ROOT / 'tools/sound_test.lua'), '-wavwrite', str(wav)], OUT / f'work_m_{sub}_{name}', env)
    return log


def symbol(name):
    for line in (CART / 'out/release/symbol.txt').read_text().splitlines():
        v = line.split()
        if len(v) >= 3 and v[2] == name:
            return int(v[0], 16) & 0xFFFFFF
    raise KeyError(name)


def parse(log):
    """-> dict(ticks=[{'t', 'c000', 'latch', 'w': [(chip, reg, data)], 'p': [bytes], 'd': [cmd]}], t0_abs)"""
    ticks, t0, gap = [], None, None
    pre = {'w': [], 'p': [], 'd': []}
    for line in log.read_text().splitlines():
        if line.startswith('#'):
            for tok in line[1:].split():
                if tok.startswith('t0_abs='):
                    t0 = float(tok[7:])
                if tok.startswith('max_status_gap_ms='):
                    gap = float(tok[18:])
            continue
        p = line.split('|')
        cur = ticks[-1] if ticks else pre
        if p[0] == 'I':
            ticks.append({'t': float(p[1]), 'c000': int(p[2]) if len(p) > 2 else None, 'latch': None,
                          'w': [], 'p': [], 'd': []})
        elif p[0] == 'L':
            cur['latch'] = int(p[2], 16)
        elif p[0] == 'W':
            cur['w'].append((int(p[2]), int(p[3], 16), int(p[4], 16)))
        elif p[0] == 'P':
            cur['p'].append(int(p[2], 16))
        elif p[0] == 'D':
            cur['d'].append(int(p[2], 16))
    return {'ticks': ticks, 't0': t0, 'max_gap': gap, 'complete': 'COMPLETE' in log.read_text()[-20:]}


def arcade_commands(a):
    """Ticks where the arcade dispatches a command ($00A9: latch != last and != $FF)."""
    last, out = 0xFF, []
    for i, t in enumerate(a['ticks']):
        v = t['latch']
        if v is None:
            continue
        if v != last:
            last = v
            if v != 0xFF:
                out.append((i, v))
    return out


def map_fm(writes, ntsc_fnum):
    """Arcade (chip, reg, data) FM writes -> expected YM2612 (part, reg, data) writes."""
    out, i = [], 0
    while i < len(writes):
        chip, reg, d = writes[i]
        if reg < 0x10 or reg in (0x27, 0x2D, 0x2E, 0x2F):
            i += 1; continue
        if reg == 0x28:
            out.append((1, 0x28, (d & 0xF0) | (d & 3) | (4 if chip == 2 else 0)))
        elif 0xA4 <= reg <= 0xA6 and i + 1 < len(writes) and writes[i + 1][:2] == (chip, reg - 4):
            block, fnum = d >> 3, (d & 7) << 8 | writes[i + 1][2]
            f2 = ntsc_fnum[(block, fnum)]
            out += [(chip, reg, block << 3 | f2 >> 8), (chip, reg - 4, f2 & 0xFF)]
            i += 2; continue
        else:
            out.append((chip, reg, d))
        i += 1
    return out


def ssg_images(ticks):
    """Per tick the 11 SSG registers of each arcade chip after that tick's writes."""
    regs = {1: [0] * 14, 2: [0] * 14}
    regs[1][7] = regs[2][7] = 0xFF
    out = []
    for t in ticks:
        for chip, reg, d in t['w']:
            if reg < 0x0E:
                regs[chip][reg] = d
        out.append((regs[1][:11], regs[2][:11]))
    return out


def envelope(path, t0, secs, hop=0.02):
    with wave.open(str(path)) as w:
        sr, n, ch = w.getframerate(), w.getnframes(), w.getnchannels()
        x = np.frombuffer(w.readframes(n), np.int16).astype(np.float64).reshape(-1, ch).mean(axis=1)
    x = x[int(t0 * sr):int((t0 + secs) * sr)]
    h = int(hop * sr); m = len(x) // h
    x = x[:m * h].reshape(m, h)
    x = x - x.mean(axis=1, keepdims=True)          # the Genesis mix carries a DC offset
    e = np.sqrt((x ** 2).mean(axis=1) + 1e-9)
    return 20 * np.log10(e / 32768.0)


def sounding(env, hop=0.02):
    on = np.nonzero(env > env.max() - 40)[0]
    return (on[-1] + 1) * hop if len(on) else 0.0


def compare(name, secs, seq, j, rerun_arcade):
    alog = OUT / 'arcade' / f'{name}.log'
    head = alog.read_text().split('\n', 1)[0] if alog.exists() else ''
    have = float(head.split('secs=')[1].split()[0]) if 'secs=' in head else 0
    if rerun_arcade or have < secs or f"seq={','.join(f'{f}:{c:02x}' for f, c in seq)} " not in head:
        run_arcade(name, secs, seq)
    a = parse(alog)
    cmds = arcade_commands(a)
    if not cmds:
        return {'name': name, 'error': 'arcade dispatched no command'}
    c000 = a['ticks'][0]['c000']
    m = parse(run_md(name, secs, inject=cmds, c000=c000))
    ntsc = {(n['block'], n['fnum']): round(n['fnum'] * j['fnum_scale_ym2612'][REGION]) for n in j['note_table']}
    n = min(len(a['ticks']), len(m['ticks'])) - 1          # last tick may be cut off by the end of the run
    fm_ok = fm_bad = fm_writes = fm_same = 0; first_fm = None
    psg_ok = psg_bad = 0; first_psg = None
    imgs = ssg_images(a['ticks'])
    model, md = sm.PSGState(), sm.PSGState()
    latch = (0, 1)
    keyons_a = keyons_m = 0
    sa, sm_ = {}, {}                      # YM2612 register state (part, reg) from both streams
    def voice_state(st, mixed=False):     # operator / FB-ALG registers of the 6 channels
        result = {k: v for k, v in st.items() if (0x30 <= k[1] <= 0x9F and k[1] & 3 != 3) or 0xB0 <= k[1] <= 0xB2}
        if mixed:
            for (part, reg), value in result.items():
                if 0x40 <= reg <= 0x4E:
                    algorithm = st.get((part, 0xB0 + (reg & 3)), 0) & 7
                    if CARRIER_MASKS[algorithm] & (1 << ((reg >> 2) & 3)):
                        result[(part, reg)] = min(127, (value & 127) + MUSIC_TL)
        return result
    for i in range(n):
        exp = map_fm(a['ticks'][i]['w'], ntsc)
        got = [w for w in m['ticks'][i]['w'] if w[1] != 0x27]
        keyons_a += sum(1 for w in exp if w[1] == 0x28 and w[2] & 0xF0)
        keyons_m += sum(1 for w in got if w[1] == 0x28 and w[2] & 0xF0)
        fm_writes += len(exp)
        fm_same += exp == got
        for w in exp:
            sa[(w[0], w[1])] = w[2]
        for w in got:
            sm_[(w[0], w[1])] = w[2]
        # musical equivalence: same key-on/off writes (order, channel, slots) and same pitch writes in
        # this tick, same operator / pitch registers after it
        keys = lambda ws: [w for w in ws if w[1] == 0x28]
        pitch = lambda ws: sorted(w for w in ws if 0xA0 <= w[1] <= 0xA6)
        if keys(exp) == keys(got) and pitch(exp) == pitch(got) and voice_state(sa, mixed=True) == voice_state(sm_):
            fm_ok += 1
        else:
            fm_bad += 1
            if first_fm is None:
                first_fm = (i, exp[:10], got[:10])
        sm.reduce(imgs[i][0], imgs[i][1], model, REGION)
        for b in m['ticks'][i]['p']:
            latch = sm.psg_apply(md, b, latch)
        if model.audible() == md.audible():
            psg_ok += 1
        else:
            psg_bad += 1
            if first_psg is None:
                first_psg = (i, model.audible(), md.audible())
    took = [(i, c) for i, t in enumerate(m['ticks']) for c in t['d']]
    cmd_ok = took == cmds
    # tick lateness vs. an ideal Timer A clock (2 half periods of 107 / 106 units of 144 clocks)
    period = 2 * (107 if REGION == 'ntsc' else 106) * 144 / (7670453 if REGION == 'ntsc' else 7600489)
    T = np.array([t['t'] for t in m['ticks']])
    late = (T - T[0] - np.arange(len(T)) * period) * 1000
    # audio (informative)
    ea = envelope(OUT / 'arcade' / f'{name}.wav', a['t0'], secs)
    em = envelope(OUT / ('md' if REGION == 'ntsc' else 'md_pal') / f'{name}.wav', m['t0'], secs)
    k = min(len(ea), len(em))
    corr = float(np.corrcoef(ea[:k], em[:k])[0, 1]) if k > 10 else float('nan')
    return {'name': name, 'ticks': n, 'commands': [f'{t}:{c:02x}' for t, c in cmds], 'cmd_ok': cmd_ok,
            'fm_ticks_ok': fm_ok, 'fm_ticks_bad': fm_bad, 'fm_writes': fm_writes, 'fm_write_identical_ticks': fm_same,
            'keyons': [keyons_a, keyons_m], 'psg_ticks_ok': psg_ok, 'psg_ticks_bad': psg_bad,
            'first_fm_diff': first_fm, 'first_psg_diff': first_psg,
            'tick_hz_md': (len(m['ticks']) - 1) / (m['ticks'][-1]['t'] - m['ticks'][0]['t']),
            'late_ms_max': round(float(late.max()), 2), 'late_ms_p99': round(float(np.percentile(late, 99)), 2),
            'poll_gap_ms': m.get('max_gap'),
            'env_corr': round(corr, 3), 'sounding_s': [round(float(sounding(ea)), 2), round(float(sounding(em)), 2)],
            'complete': a['complete'] and m['complete']}


def api_case():
    """68000 path: sound_command() via the test cart's host queue; check order and latency."""
    sent = [(0, 0x21), (30, 0x01), (31, 0x0C), (60, 0x10), (61, 0x10), (90, 0x2E), (91, 0x01), (92, 0x02),
            (93, 0x03), (120, 0x39), (150, 0x00)]
    m = parse(run_md('api', 4, api=sent))
    took = [(i, c) for i, t in enumerate(m['ticks']) for c in t['d']]
    order_ok = [c for _, c in took] == [c for _, c in sent]
    # latency: frame f is written at the start of frame f (f / frame rate); taken at tick i
    lat = []
    for (f, _), (i, _) in zip(sent, took):
        lat.append(m['ticks'][i]['t'] - f / (59.922743 if REGION == 'ntsc' else 49.701459))
    return {'name': 'api', 'sent': len(sent), 'taken': len(took), 'order_ok': order_ok,
            'latency_ms': [round(1000 * x, 1) for x in lat]}


def gpgx_case(cmds=(0x21, 0x2E, 0x0C, 0x13), secs=12):
    """Second emulator: Genesis Plus GX (libretro, tools/run_rom.py) plays each command through the
    68000 API; its audio envelope is compared with the MAME cartridge run (onset-aligned)."""
    import ctypes as C
    import run_rom
    run_rom.ROOT = CART
    out = []
    for cmd in cmds:
        r = run_rom.Runner(rom=CART / 'out/release/rom.bin')
        buf = []
        cb = C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t)(
            lambda p, n: buf.append(np.ctypeslib.as_array(p, (n * 2,)).copy()) or n)
        r.lib.retro_set_audio_sample_batch(cb)
        class Timing(C.Structure):
            _fields_ = [('geo', C.c_uint * 4), ('aspect', C.c_float), ('fps', C.c_double), ('rate', C.c_double)]
        av = Timing(); r.lib.retro_get_system_av_info(C.byref(av))
        zram = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
        r.run(30)
        buf.clear()
        tick0 = zram[0x1400]
        r.write('host_cmd', [cmd]); r.write('host_n', [1])
        frames = int(secs * av.fps)
        ticks = 0; prev = tick0
        for _ in range(frames):
            r.run(1); t = zram[0x1400]; ticks += (t - prev) & 0xFF; prev = t
        x = np.concatenate(buf).reshape(-1, 2)
        wav_path = OUT / 'gpgx' / f'cmd_{cmd:02x}.wav'
        wav_path.parent.mkdir(parents=True, exist_ok=True)
        with wave.open(str(wav_path), 'wb') as w:
            w.setnchannels(2); w.setsampwidth(2); w.setframerate(int(round(av.rate))); w.writeframes(x.astype(np.int16).tobytes())
        eg = envelope(wav_path, 0, secs)
        mlog = OUT / 'md' / f'cmd_{cmd:02x}.log'
        em = envelope(OUT / 'md' / f'cmd_{cmd:02x}.wav', parse(mlog)['t0'], secs) if mlog.exists() else None
        corr = None
        if em is not None:
            on = lambda e: int(np.argmax(e > e.max() - 30))
            a, b = eg[on(eg):], em[on(em):]
            k = min(len(a), len(b))
            corr = round(float(np.corrcoef(a[:k], b[:k])[0, 1]), 3)
        out.append({'cmd': f'{cmd:02x}', 'tick_hz': round(ticks / (frames / av.fps), 2), 'taken': zram[0x1F05] == zram[0x1F04],
                    'env_corr_vs_mame': corr, 'sounding_s': round(float(sounding(eg)), 2)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('cases', nargs='*')
    ap.add_argument('--jobs', type=int, default=6)
    ap.add_argument('--rerun-arcade', action='store_true')
    ap.add_argument('--no-build', action='store_true')
    ap.add_argument('--music-secs', type=float, default=125)
    ap.add_argument('--sfx-secs', type=float, default=20)
    ap.add_argument('--gpgx', action='store_true', help='only the Genesis Plus GX cross-check')
    ap.add_argument('--pal', action='store_true', help="run the cartridge as PAL (MAME 'megadriv')")
    o = ap.parse_args()
    global REGION
    REGION = 'pal' if o.pal else 'ntsc'
    if not o.no_build:
        subprocess.run(['make', '-C', str(CART)], check=True, capture_output=True)
    j = json.loads((ROOT / 'res/generated/sound.json').read_text())
    if o.gpgx:
        res = gpgx_case()
        (OUT / 'report_gpgx.txt').write_text('\n'.join(json.dumps(x) for x in res) + '\n')
        print('\n'.join(json.dumps(x) for x in res)); return
    cases = {}
    for c in SFX + MUSIC:
        cases[f'cmd_{c:02x}'] = (o.music_secs if c >= 0x20 else o.sfx_secs, [(0, c)])
    cases.update(SCENARIOS)
    names = o.cases or list(cases) + ['api']
    OUT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(o.jobs) as ex:
        futs = {nm: ex.submit(api_case) if nm == 'api' else ex.submit(compare, nm, *cases[nm], j, o.rerun_arcade)
                for nm in names}
        res = [futs[nm].result() for nm in names]
    lines = []
    failed = False
    for r in res:
        if r['name'] == 'api':
            failed |= not r['order_ok'] or r['sent'] != r['taken']
            lines.append(f"api      sent={r['sent']} taken={r['taken']} order_ok={r['order_ok']} latency_ms={r['latency_ms']}")
            continue
        if 'error' in r:
            failed = True
            lines.append(f"{r['name']:12s} ERROR {r['error']}"); continue
        ok = (r['fm_ticks_bad'] == 0 and r['psg_ticks_bad'] == 0 and r['cmd_ok'] and r['complete']
              and (r['poll_gap_ms'] or 0) < 2.0)
        failed |= not ok
        lines.append(f"{r['name']:12s} {'PASS' if ok else 'FAIL'} ticks={r['ticks']} cmds={','.join(r['commands'])} "
                     f"fm={r['fm_ticks_ok']}/{r['ticks']} (write-identical {r['fm_write_identical_ticks']}; {r['fm_writes']} writes, keyons arcade/md "
                     f"{r['keyons'][0]}/{r['keyons'][1]}) psg={r['psg_ticks_ok']}/{r['ticks']} "
                     f"tick={r['tick_hz_md']:.3f}Hz late_ms(max/p99)={r['late_ms_max']}/{r['late_ms_p99']} "
                     f"poll_gap_ms={r['poll_gap_ms']} env_corr={r['env_corr']} sounding_s(arcade/md)={r['sounding_s']}")
        if r['first_fm_diff']:
            lines.append(f"    first FM diff at tick {r['first_fm_diff'][0]}: arcade {r['first_fm_diff'][1]} md {r['first_fm_diff'][2]}")
        if r['first_psg_diff']:
            lines.append(f"    first PSG diff at tick {r['first_psg_diff'][0]}: model {r['first_psg_diff'][1]} md {r['first_psg_diff'][2]}")
    tag = ('' if REGION == 'ntsc' else '_pal') + ('_partial' if o.cases else '')
    (OUT / f'report{tag}.txt').write_text('\n'.join(lines) + '\n')
    (OUT / f'report{tag}.json').write_text(json.dumps(res, indent=1))
    print('\n'.join(lines))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
