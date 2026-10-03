#!/usr/bin/env python3
"""Compile res/generated/sound.json into the native Genesis sound data (build step).

The arcade byte code is NOT reused. Every music channel and every SFX is compiled from the decoded,
tick-accurate events of sound.json into the Genesis driver's own format (docs/sound_port.md):

  music  per-channel event streams: {note index | rest, triplet flag, duration-table index}, patch
         changes, end, loop jump. All arcade per-note arithmetic is resolved here: octave/transpose,
         tempo x length (dotted), gate -> key-off tick, slur -> "no key-off" (arcade rules cited below).
  notes  F-number tables per region (YM2612 rate), indexed by note number.
  patch  YM2612 register blocks: 24 operator values for $30..$8C (+ch), $B0 FB/ALG, key-on slot mask.
  SFX    linear frame lists (loops unrolled): {mask, ticks lo, ticks hi, fields}; mask bit 2i = tone of
         voice i {period lo, hi (0 = off, $FFFF = keep), slide}, bit 2i+1 = volume {v or $FF keep, slide},
         bit 6 = noise {period or $FF keep, mixer noise bits, slide}, bit 7 = end.

Outputs (ignored by VCS):
  res/generated/sound_z80.bin   two 32 KB banks: bank 0 = tables + music, bank 1 = SFX frames
  src/gen/sound_data.s          .incbin wrapper, 32 KB aligned, symbol `sound_z80_data`

A Python model of the driver's channel timing (`simulate`) replays every compiled stream and must
reproduce the tick of every note/rest of sound.json; the build fails otherwise.
"""
import json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / 'res/generated'
JSON = GEN / 'sound.json'
OUT_BIN = GEN / 'sound_z80.bin'
OUT_S = ROOT / 'src/gen/sound_data.s'

WIN = 0x8000                      # Z80 bank window
CMDTAB, NTAB_NTSC, NTAB_PAL, DURTAB, PATCHES, MUSIC = 0x000, 0x100, 0x200, 0x300, 0x700, 0xB00
LEN_NORMAL = [0, 0, 2, 4, 8, 16, 32, 64]        # arcade $046A
LEN_DOTTED = [0, 0, 3, 6, 12, 24, 48, 96]       # arcade $0472
OP_PATCH, OP_JUMP, OP_END = 0x7D, 0x7E, 0x7F    # stream opcodes; 0 = rest, 1..96 = note, bit 7 = triplet
KIND = {'stop_all': 0, 'stop_sfx': 1, 'stop_music': 2, 'sfx': 3, 'music': 4}

# 16 total-level steps = 12 dB. Only output carriers are attenuated; changing
# modulators would change the instrument. Register order is S1, S3, S2, S4.
MUSIC_TL = 16
CARRIER_MASKS = (0x8, 0x8, 0x8, 0x8, 0xC, 0xE, 0xE, 0xF)


def mix_patch(raw):
    patch = bytearray(raw)
    mask = CARRIER_MASKS[patch[24] & 7]
    for slot in range(4):
        if mask & (1 << slot):
            patch[4 + slot] = min(127, (patch[4 + slot] & 127) + MUSIC_TL)
    return bytes(patch)


def psg_period_table(multiplier):
    """Exact former Z80 arithmetic, precomputed for every 12-bit SSG period."""
    table = bytearray()
    for period in range(4096):
        period = period or 1
        value = period - ((period * multiplier + 128) >> 8)
        while value > 1023:
            value = (value + 1) >> 1
        table += max(1, value).to_bytes(2, 'little')
    return table


class DurTable:
    """(ticks to next event, key-off tick or 0) pairs shared by all streams."""
    def __init__(self):
        self.rows, self.index = [], {}

    def get(self, d, g):
        k = (d, g)
        if k not in self.index:
            self.index[k] = len(self.rows); self.rows.append(k)
            if len(self.rows) > 256:
                raise SystemExit('build_sound: more than 256 duration/gate pairs')
        return self.index[k]


def compile_events(events, st, durs, ops, first=None, states=None):
    """Append the ops of `events` (sound.json walk order) to `ops`, updating compile state `st`."""
    for idx, ev in enumerate(events):
        a, op = ev['a'], ev['op']
        if first is not None:
            first.setdefault(a, (len(ops), idx))
        if states is not None:
            states.append((st['oct'], st['tempo'], st['gate'], st['tie'], st['trip']))
        if op == 'octave':
            st['oct'] = ev['v']
        elif op == 'tempo':
            st['tempo'] = ev['v']
        elif op in ('set15_unused', 'loop_mark', 'jump'):
            pass                                          # jumps: the compiled stream is linear
        elif op == 'loop_until':
            raise SystemExit('build_sound: music loop counters are not used by the data (sound.md)')
        elif op == 'triplet_next':                       # $30 prefix: next note/rest steps twice on odd ticks ($030A)
            st['trip'] = True
        elif op == 'slur':                               # $21-$3E: no key-off while the slur count is > 0 ($0330)
            st['tie'] = ev['v']
        elif op == 'patch':                              # $01-$1E: patch + gate, loaded at once ($03A1)
            st['gate'] = ev['gate']; ops.append(('patch', ev['v']))
        elif op in ('note', 'rest'):
            dotted = ev.get('dotted', False)
            if op == 'note' and not dotted and st['tie']:
                st['tie'] -= 1                            # slur count drops at each plain note ($037E)
            # the walk resolved pitch and length with the state of its pass; later loop passes
            # re-resolve them from their own octave / tempo (both persist across the loop jump)
            if 'lo' not in ev:
                ev['lo'] = ev['k'] - st['oct'] if op == 'note' else 0
                assert ev['dur'] % st['tempo'] == 0 if st['tempo'] else True
                ev['len'] = ev['dur'] // st['tempo'] if st['tempo'] else 0
            d = st['tempo'] * ev['len']
            # key-off countdown dur*(g+1)>>4, g = max(gate,1) ($0439-$0469); it only runs while the
            # duration has not expired and the slur count is 0 ($0330-$0347) -> key-off iff 1 <= G < D
            g = max(st['gate'] & 15, 1)
            G = (d * (g + 1)) >> 4
            D = max(d, 1)                                 # a zero duration is read again on the next tick
            if st['tie'] or not 1 <= G < D:
                G = 0
            k = st['oct'] + ev['lo'] if op == 'note' else 0
            assert 1 <= k <= 96 or op == 'rest', k
            ops.append(('ev', k, st['trip'], durs.get(D, G)))
            st['trip'] = False
        elif op == 'end':
            ops.append(('end',))
        else:
            raise SystemExit(f'build_sound: unknown music op {op}')


def compile_channel(ch, tempo, durs):
    """sound.json channel walk -> ops [(kind, ...)]; a looping walk ends with ('jump', op index)."""
    st = {'oct': 0, 'tempo': tempo, 'gate': ch['gate'], 'tie': 0, 'trip': False}
    ops, first = [], {}
    evs = ch['events']
    first_state = []
    compile_events(evs, st, durs, ops, first, first_state)
    if ch['info']['end'] == 'loop':
        pos, idx = first[ch['info']['loop_addr']]
        # Later passes of the loop start from the state left by the previous pass (octave, tempo, gate,
        # slur persist across the jump). A pass compiled from the current state that yields the same
        # ops and the same end state as an existing pass can reuse it (its future is identical);
        # otherwise it is appended.
        snap = lambda d: (d['oct'], d['tempo'], d['gate'], d['tie'], d['trip'])
        passes = [(pos, ops[pos:], snap(st))]
        for _ in range(16):
            s2 = dict(st); body = []
            compile_events(evs[idx:], s2, durs, body)
            hit = [p for p, o, e in passes if o == body and e == snap(s2)]
            if hit:
                pos = hit[0]; break
            passes.append((len(ops), body, snap(s2)))
            ops += body; st = s2
        else:
            raise SystemExit(f'build_sound: loop at {ch["info"]["loop_addr"]:04x} does not settle')
        ops.append(('jump', pos))
    return ops


def encode_channel(ops, base):
    """ops -> bytes at Z80 address base (jump targets resolved)."""
    pos, n = [], 0
    for o in ops:
        pos.append(n); n += {'ev': 2, 'patch': 2, 'jump': 3, 'end': 1}[o[0]]
    out = bytearray()
    for o in ops:
        if o[0] == 'ev':
            out += bytes([o[1] | (0x80 if o[2] else 0), o[3]])
        elif o[0] == 'patch':
            out += bytes([OP_PATCH, o[1]])
        elif o[0] == 'jump':
            t = base + pos[o[1]]; out += bytes([OP_JUMP, t & 0xFF, t >> 8])
        else:
            out += bytes([OP_END])
    return bytes(out)


def simulate(ops, durs, ticks, c000=0):
    """Model of the driver's channel step (sa_sound_drv.s80 `chan_tick`); returns [(tick, k)] of the
    note/rest events read. c000 = tick counter before the first tick (extract_sound convention)."""
    out, i, count, trip = [], 0, 1, False
    for t in range(ticks):
        c000 = (c000 + 1) & 0xFF
        for _ in range(2 if trip and c000 & 1 else 1):
            count -= 1
            if count:
                continue
            while True:
                o = ops[i]; i += 1
                if o[0] == 'patch':
                    continue
                if o[0] == 'jump':
                    i = o[1]; continue
                if o[0] == 'end':
                    return out
                out.append((t, o[1])); count = durs.rows[o[3]][0]; trip = o[2]
                break
    return out


def sfx_frames(events):
    """sound.json SFX walk (loops already unrolled by the decoder) -> frame bytes."""
    out = bytearray()
    for ev in events:
        if ev['op'] == 'frame':
            n = ev['ticks']
            assert 1 <= n <= 0xFFFF, ev
            mask, body = 0, bytearray()
            fields = {}
            for s in ev['set']:
                if s['op'] == 'tone':
                    i = 'ABC'.index(s['ch']); mask |= 1 << (2 * i)
                    p = s['period']
                    code = 0 if p == 0 else 0xFFFF if p == 0xFFF else p      # 0 = tone off, $FFFF = keep
                    fields[2 * i] = code.to_bytes(2, 'little') + bytes([s['slide16'] & 0xFF])
                elif s['op'] == 'vol':
                    i = 'ABC'.index(s['ch']); mask |= 2 << (2 * i)
                    fields[2 * i + 1] = bytes([0xFF if s['v'] is None else s['v'], s['slide16_per4'] & 0xFF])
                elif s['op'] == 'noise':
                    mask |= 0x40
                    fields[6] = bytes([0xFF if s['period'] is None else s['period'], s['noise_off_mask'] << 3,
                                       s['slide8_per4'] & 0xFF])
            for k in sorted(fields):
                body += fields[k]
            out += bytes([mask, n & 0xFF, n >> 8]) + body
        elif ev['op'] == 'end':
            out.append(0x80); return bytes(out)
        elif ev['op'] in ('loop_mark', 'loop_count'):
            pass                                          # unrolled by the walk
        else:
            raise SystemExit(f'build_sound: SFX op {ev["op"]} not supported (repeat-forever unused)')
    raise SystemExit('build_sound: SFX without end')


def main():
    if not JSON.exists():
        subprocess.run([sys.executable, str(ROOT / 'tools/extract_sound.py')], check=True)
    j = json.loads(JSON.read_text())
    durs = DurTable()
    bank0 = bytearray(b'\xff' * 0x8000)
    bank1 = bytearray(b'\xff' * 0x8000)
    music_at, sfx_at = MUSIC, 0
    cmd = {}
    checked = 0
    for c, e in j['commands'].items():
        n = int(c, 16)
        if e['kind'] == 'music':
            hdr_addr = music_at; music_at += 18
            hdr = bytearray()
            for ch in e['channels']:
                ops = compile_channel(ch, e['tempo'], durs)
                code = encode_channel(ops, WIN + music_at)
                bank0[music_at:music_at + len(code)] = code
                hdr += (WIN + music_at).to_bytes(2, 'little') + bytes([ch['patch']])
                music_at += len(code)
                # replay the compiled stream: every note/rest must start on the arcade's tick
                want = [(x['t'], x.get('k', 0)) for x in ch['events'] if x['op'] in ('note', 'rest')]
                last = ch['info']['total_ticks'] + 1
                if ch['info']['end'] == 'loop':
                    last += 2 * ch['info']['loop_ticks']
                got = simulate(ops, durs, last)
                if got[:len(want)] != want:
                    bad = next(i for i, (x, y) in enumerate(zip(got, want)) if x != y)
                    raise SystemExit(f'build_sound: timing mismatch cmd {c} ch {ch["fm_channel"]} event {bad}')
                # (later loop passes may differ from the first: octave/tempo/gate/slur carry over the
                #  jump, e.g. $22 ch3 plays its loop a semitone higher from the 2nd pass on)
                checked += len(want)
            bank0[hdr_addr:hdr_addr + 18] = hdr
            cmd[n] = (4, e['priority'], WIN + hdr_addr)
        elif e['kind'] == 'sfx':
            fr = sfx_frames(e['events'])
            bank1[sfx_at:sfx_at + len(fr)] = fr
            slot = ((e['chip'] - 1) * 5 + e['priority'])
            cmd[n] = (3, slot, WIN + sfx_at); sfx_at += len(fr)
        else:
            cmd[n] = (KIND.get(e['kind'], 5), 0, 0)
    if music_at > 0x8000 or sfx_at > 0x4000:
        raise SystemExit(f'build_sound: bank overflow (music {music_at}, sfx {sfx_at})')
    for n, (k, arg, ptr) in cmd.items():
        bank0[CMDTAB + 4 * n:CMDTAB + 4 * n + 4] = bytes([k, arg, ptr & 0xFF, ptr >> 8])
    for table, region in ((NTAB_NTSC, 'ntsc'), (NTAB_PAL, 'pal')):
        scale = j['fnum_scale_ym2612'][region]
        bank0[table:table + 2] = b'\0\0'
        for nt in j['note_table']:
            f = round(nt['fnum'] * scale)
            assert f < 2048
            bank0[table + 2 * nt['k']:table + 2 * nt['k'] + 2] = bytes([nt['block'] << 3 | f >> 8, f & 0xFF])
    for i, (d, g) in enumerate(durs.rows):
        bank0[DURTAB + 4 * i:DURTAB + 4 * i + 4] = d.to_bytes(2, 'little') + g.to_bytes(2, 'little')
    for key, p in j['patches'].items():
        raw = bytes.fromhex(p['raw'])     # registers $30,$34,..,$8C (operator order S1 S3 S2 S4), $B0, key-on mask
        o = PATCHES + 32 * int(key, 16)
        bank0[o:o + 26] = mix_patch(raw)
    # Spare space in SFX bank: NTSC at Z80 $C000, PAL at $E000. No ROM growth.
    bank1[0x4000:0x6000] = psg_period_table(27)
    bank1[0x6000:0x8000] = psg_period_table(29)
    blob = bytes(bank0) + bytes(bank1)
    OUT_BIN.write_bytes(blob)
    import hashlib
    digest = hashlib.sha1(blob).hexdigest()[:16]
    OUT_S.parent.mkdir(parents=True, exist_ok=True)
    OUT_S.write_text(
        '/* Generated by tools/build_sound.py. Do not edit. Native sound data: two 32 KB Z80 banks\n'
        f'   (tables + music, SFX); must be 32 KB aligned. Data hash {digest} (forces a rebuild). */\n'
        '.section .rodata.sound_z80_data,"a"\n'
        '.balign 32768\n'
        '.global sound_z80_data\n'
        'sound_z80_data:\n'
        f'.incbin "{OUT_BIN}"\n')
    print(f'{OUT_BIN.relative_to(ROOT)}: music {music_at - MUSIC} B, SFX {sfx_at} B, '
          f'{len(durs.rows)} duration pairs, {checked} music events replayed tick-exact')


if __name__ == '__main__':
    main()
