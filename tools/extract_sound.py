#!/usr/bin/env python3
"""Decode the Side Arms sound driver data (audiocpu ROM a_04k) into res/generated/sound.json.

Development-only: reads the original ROM through tools/arcade_source.py; output is ignored by VCS.
Format reference: docs/re/sound.md (all addresses below are audiocpu ROM addresses).

usage: extract_sound.py [--print]
"""
import argparse, json, math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT

CMD_TABLE = 0x00BB          # 64 x word, dispatched by (latch & $3F) via rst $30 ($00B8)
PATCH_BASE = 0x0C49         # 32-byte FM patches, index = patch number ($02D3)
NOTE_TABLE = 0x0513         # big-endian words: (block<<3 | fnum>>8), fnum&$FF; entry 0 = rest
LEN_NORMAL = [0, 0, 2, 4, 8, 16, 32, 64]     # $046A, indexed by byte>>5
LEN_DOTTED = [0, 0, 3, 6, 12, 24, 48, 96]    # $0472 (command $DF prefix)
SET_CLEAR = {0x01C3: 0xC100, 0x01CC: 0xC200, 0x01D5: 0xC300, 0x01DE: 0xC400}
SFX_SLOTS = {0xC500 + 0x20 * i: (1, i) for i in range(5)} | {0xC600 + 0x20 * i: (2, i) for i in range(5)}
STOP_SFX, STOP_ALL, STOP_MUSIC = 0x0141, 0x013B, 0x015C
YM_CLOCK, YM2612_NTSC, YM2612_PAL = 4_000_000, 7_670_453, 7_600_489
TICK_HZ = YM_CLOCK / 72 / (1024 - 801)  # Timer A, NA = $C8<<2 | $01 ($007C-$008A) -> 249.13 Hz


def w(d, a): return d[a] | d[a + 1] << 8
def s8(v): return v - 256 if v & 0x80 else v


def note_freq(d, index):
    """index = absolute table entry (1 = C#0). Returns (block, fnum, hz)."""
    hi, lo = d[NOTE_TABLE + 2 * index], d[NOTE_TABLE + 2 * index + 1]
    block, fnum = hi >> 3, (hi & 7) << 8 | lo
    hz = fnum * (YM_CLOCK / 72) * 2 ** block / 2 ** 21
    return block, fnum, hz


def patch(d, n):
    a = PATCH_BASE + 32 * n
    raw = d[a:a + 32]
    ops = []
    for op in range(4):  # register order $30+4*op... -> OPN slot order S1,S3,S2,S4
        r = lambda grp: raw[grp * 4 + op]
        ops.append({'dt': r(0) >> 4 & 7, 'mul': r(0) & 15, 'tl': r(1) & 127, 'ks': r(2) >> 6,
                    'ar': r(2) & 31, 'dr': r(3) & 31, 'sr': r(4) & 31, 'sl': r(5) >> 4, 'rr': r(5) & 15})
    return {'raw': raw[:26].hex(), 'fb': raw[24] >> 3 & 7, 'alg': raw[24] & 7,
            'keyon_slots': raw[25] >> 4, 'ops_reg_order': ops}


def decode_music_channel(d, start, tempo, c000=0):
    """Tick-accurate walk of one FM channel as the IRQ does it ($030A/$031B/$0362).
    Event 't' = tick (Timer-A IRQ) at which the byte is consumed, relative to the first processing tick.
    c000 = value of the free-running IRQ counter $C000 before that tick (only its parity matters: the
    $30 'triplet' prefix makes $030A run the channel twice on odd ticks). Stops at end ($FF) or at a jump
    to an already visited address (= the loop). Returns (events, info)."""
    st = {'pc': start, 'oct': 0, 'tie': 0, 'tempo': tempo, 'counter': 0, 'mark': None, 'gate': None}
    events, visited = [], {}

    def batch(t):
        """One $0362 call: consume bytes until a note/rest (returns dur) or end/loop (returns None)."""
        trip = False
        while True:
            a = st['pc']; b = d[a]; st['pc'] += 1
            visited.setdefault(a, t)
            lo, hi = b & 0x1F, b >> 5
            if lo == 0x1F:
                arg = d[st['pc']]
                if hi == 0:
                    st['oct'] = arg; st['pc'] += 1; events.append({'t': t, 'a': a, 'op': 'octave', 'v': arg})
                elif hi == 1:
                    st['tempo'] = arg; st['pc'] += 1; events.append({'t': t, 'a': a, 'op': 'tempo', 'v': arg})
                elif hi == 2:
                    st['pc'] += 1; events.append({'t': t, 'a': a, 'op': 'set15_unused', 'v': arg})
                elif hi == 3:
                    tgt = w(d, st['pc']); st['pc'] += 2
                    events.append({'t': t, 'a': a, 'op': 'jump', 'v': tgt})
                    if tgt in visited:
                        return ('loop', tgt)
                    st['pc'] = tgt
                elif hi == 4:
                    st['mark'], st['counter'] = st['pc'], 0; events.append({'t': t, 'a': a, 'op': 'loop_mark'})
                elif hi == 5:
                    st['pc'] += 1; st['counter'] += 1
                    events.append({'t': t, 'a': a, 'op': 'loop_until', 'v': arg})
                    if arg >= st['counter']:
                        st['pc'] = st['mark']
                elif hi == 6:   # dotted note / rest ($03B6): no slur bookkeeping, x1.5 length table
                    st['pc'] += 1
                    dur = st['tempo'] * LEN_DOTTED[arg >> 5]
                    if arg & 0x1F:
                        k = st['oct'] + (arg & 0x1F)
                        events.append({'t': t, 'a': a, 'op': 'note', 'k': k, 'midi': 12 + k, 'dur': dur,
                                       'dotted': True, 'gate': st['gate']})
                    else:
                        events.append({'t': t, 'a': a, 'op': 'rest', 'dur': dur, 'dotted': True})
                    return ('dur', dur, trip)
                else:
                    events.append({'t': t, 'a': a, 'op': 'end'})
                    return ('end',)
            elif lo == 0:
                dur = st['tempo'] * LEN_NORMAL[hi]
                events.append({'t': t, 'a': a, 'op': 'rest', 'dur': dur, 'triplet': trip})
                return ('dur', dur, trip)
            elif hi == 0:
                st['gate'] = d[st['pc']] & 15; st['pc'] += 1
                events.append({'t': t, 'a': a, 'op': 'patch', 'v': b, 'gate': st['gate']})
            elif hi == 1:
                if b == 0x30:
                    trip = True; events.append({'t': t, 'a': a, 'op': 'triplet_next'})
                else:
                    st['tie'] = (b + 1) & 0x1F; events.append({'t': t, 'a': a, 'op': 'slur', 'v': st['tie']})
            else:
                dur = st['tempo'] * LEN_NORMAL[hi]
                k = st['oct'] + lo
                legato = st['tie'] > 0
                if st['tie']: st['tie'] -= 1
                events.append({'t': t, 'a': a, 'op': 'note', 'k': k, 'midi': 12 + k, 'dur': dur,
                               'legato': legato, 'triplet': trip, 'gate': st['gate']})
                return ('dur', dur, trip)

    dur, flag, t = 0, False, 0
    while t < 2_000_000:
        c000 = (c000 + 1) & 0xFF
        for _ in range(2 if flag and c000 & 1 else 1):
            if dur == 0 or dur == 1:      # $031B: zero -> read; else dec, zero -> read
                r = batch(t)
                if r[0] == 'end':
                    return events, {'end': 'end', 'total_ticks': t}
                if r[0] == 'loop':
                    return events, {'end': 'loop', 'loop_addr': r[1], 'loop_start_ticks': visited[r[1]],
                                    'total_ticks': t, 'loop_ticks': t - visited[r[1]]}
                dur, flag = r[1], r[2]
            else:
                dur -= 1
        t += 1
    return events, {'end': 'runaway', 'total_ticks': t}


def decode_sfx(d, start):
    """Walk an SSG effect stream exactly as $0702/$0785 do."""
    pc, t, events, mark, counter = start, 0, [], None, 0
    def sub(pc):
        b = d[pc]; a = pc; pc += 1; k = b >> 5
        if k in (1, 2, 3):
            per = (b & 0x0F) << 8 | d[pc]; slide = s8(d[pc + 1]); pc += 2
            return pc, {'a': a, 'op': 'tone', 'ch': 'ABC'[k - 1], 'period': per, 'slide16': slide}
        if k in (4, 5, 6):
            v = b & 0x1F; slide = s8(d[pc]); pc += 1
            return pc, {'a': a, 'op': 'vol', 'ch': 'ABC'[k - 4], 'v': None if v == 0x1F else v & 15, 'slide16_per4': slide}
        if k == 7:
            v = b & 0x1F; mix = d[pc] & 0x38; slide = s8(d[pc + 1]); pc += 2
            return pc, {'a': a, 'op': 'noise', 'period': None if v == 0x1F else v,
                        'noise_off_mask': mix >> 3, 'slide8_per4': slide}
        return pc, {'a': a, 'op': 'sub0_unhandled', 'v': b}
    for _ in range(5000):
        a = pc; b = d[pc]; pc += 1
        k = (b >> 2) & 7
        if k == 0:
            n = b << 8 | d[pc]; pc += 1
            subs = []
            while d[pc] & 0xE0:
                pc, e = sub(pc); subs.append(e)
            events.append({'t': t, 'a': a, 'op': 'frame', 'ticks': n or 65536, 'set': subs})
            t += n or 65536
        elif k == 1:
            mark, counter = pc, 0; events.append({'t': t, 'a': a, 'op': 'loop_mark'})
        elif k == 2:
            n = d[pc]; pc += 1; counter += 1
            events.append({'t': t, 'a': a, 'op': 'loop_count', 'v': n})
            if n != counter: pc = mark
        elif k == 3:
            events.append({'t': t, 'a': a, 'op': 'repeat_forever'})
            return events, {'end': 'loop', 'loop_ticks': t, 'total_ticks': t}
        else:
            events.append({'t': t, 'a': a, 'op': 'end'})
            return events, {'end': 'end', 'total_ticks': t}
    return events, {'end': 'runaway', 'total_ticks': t}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--print', action='store_true'); o = ap.parse_args()
    d = Source().region('audiocpu')
    out = {'tick_hz': TICK_HZ, 'ym2203_clock': YM_CLOCK,
           'fnum_scale_ym2612': {'ntsc': (YM_CLOCK / 72) / (YM2612_NTSC / 144),
                                 'pal': (YM_CLOCK / 72) / (YM2612_PAL / 144)},
           'note_table': [], 'patches': {}, 'commands': {}}
    for i in range(1, 97):
        blk, fn, hz = note_freq(d, i)
        out['note_table'].append({'k': i, 'midi': 12 + i, 'block': blk, 'fnum': fn, 'hz': round(hz, 3)})
    used_patches = set()
    for c in range(64):
        h = w(d, CMD_TABLE + 2 * c)
        e = {'handler': h}
        if h == STOP_ALL: e['kind'] = 'stop_all'
        elif h == STOP_SFX: e['kind'] = 'stop_sfx'
        elif h == STOP_MUSIC: e['kind'] = 'stop_music'
        elif d[h:h + 2] == b'\xdd\x21':        # ld ix,slot ; ld hl,data ; jp $09EC
            slot, data = w(d, h + 2), w(d, h + 5)
            chip, pri = SFX_SLOTS[slot]
            ev, info = decode_sfx(d, data)
            e |= {'kind': 'sfx', 'slot': slot, 'chip': chip, 'priority': pri, 'data': data, 'info': info,
                  'seconds': info['total_ticks'] / TICK_HZ, 'events': ev}
        elif d[h] == 0xCD and w(d, h + 1) in SET_CLEAR:   # call clear_set ; ld hl,hdr ; jp $01F2
            sset, hdr = SET_CLEAR[w(d, h + 1)], w(d, h + 4)
            tempo = d[hdr]
            chans = []
            for i in range(6):
                p = hdr + 1 + 4 * i
                ptr, pno, gate = w(d, p), d[p + 2], d[p + 3]
                used_patches.add(pno)
                ev, info = decode_music_channel(d, ptr, tempo)
                for x in ev:
                    if x['op'] == 'patch': used_patches.add(x['v'])
                silent = not any(x['op'] == 'note' for x in ev)
                chans.append({'fm_channel': i, 'chip': 1 + i // 3, 'chip_ch': i % 3, 'ptr': ptr, 'patch': pno,
                              'gate': gate & 15, 'silent': silent, 'info': info, 'events': ev})
            # The whole set is alive only while its channel 0 is ($0236 tests (ix+0) of the first record),
            # so a non-looping track ends when channel 0 ends (other channels are frozen, not keyed off).
            c0 = chans[0]['info']
            e |= {'kind': 'music', 'set': sset, 'priority': (sset - 0xC100) >> 8, 'header': hdr, 'tempo': tempo,
                  'voices': sum(not c['silent'] for c in chans), 'channels': chans,
                  'loops': c0['end'] == 'loop'}
            if c0['end'] == 'loop':
                lp = [c['info'] for c in chans if c['info']['end'] == 'loop']
                period = 1
                for x in lp: period = math.lcm(period, x['loop_ticks'])
                start = max(x['loop_start_ticks'] for x in lp)
                e |= {'loop_start_ticks': start, 'loop_ticks': period,
                      'intro_seconds': start / TICK_HZ, 'loop_seconds': period / TICK_HZ,
                      'seconds': (start + period) / TICK_HZ}
            else:
                e['seconds'] = c0['total_ticks'] / TICK_HZ
        else:
            e['kind'] = 'unknown'
        out['commands'][f'{c:02x}'] = e
    for n in sorted(used_patches):
        out['patches'][f'{n:02x}'] = patch(d, n)
    dst = ROOT / 'res/generated/sound.json'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(out, indent=1))
    if o.print:
        for c, e in out['commands'].items():
            if e['kind'] == 'music':
                ends = ','.join(f"{x['info']['end'][0]}{x['info']['total_ticks']}" for x in e['channels'])
                lp = f" intro={e.get('intro_seconds', 0):.2f}s loop={e['loop_seconds']:.2f}s" if e['loops'] else ''
                print(f"{c} music set={e['set']:04X} tempo={e['tempo']} voices={e['voices']} len={e['seconds']:.2f}s{lp} [{ends}]")
            elif e['kind'] == 'sfx':
                print(f"{c} sfx chip{e['chip']} pri{e['priority']} data={e['data']:04X} {e['info']['end']} {e['seconds']:.3f}s")
            else:
                print(c, e['kind'])
        print('patches used:', ' '.join(out['patches']))
    print(dst)


if __name__ == '__main__':
    main()
