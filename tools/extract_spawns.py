#!/usr/bin/env python3
"""Extract the Side Arms object/enemy data from the original ROM (development-only).

Writes
  res/generated/spawns.json      every stage-script event that creates objects, with the camera
                                 position/tick at which it fires and the object records it creates
                                 (obtained by executing the spawn routine in tools/z80lite.py)
  res/generated/metasprites.json sprite composition rules + per-template animation frames

Ground truth / addresses: docs/re/objects.md.  ROM is read through tools/arcade_source.py.
usage: extract_spawns.py [--difficulty 0..7 (default 3 = MAME default 'Normal')] [--out DIR]
"""
import argparse, json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT
from z80lite import Z80, Unsupported, Stop

M = None  # maincpu region


def rd(bank, a):
    """Byte at CPU address a with bank `bank` mapped at $8000-$BFFF."""
    if a < 0x8000:
        return M[a]
    return M[0x8000 + bank * 0x4000 + (a - 0x8000)]


def rw(bank, a):
    return rd(bank, a) | (rd(bank, a + 1) << 8)


def s8(v):
    return v - 256 if v > 127 else v


def h4(a):
    return None if a is None else '%04X' % a


# ---------------------------------------------------------------- constants (see objects.md)
ALLOCATORS = {  # address: (base, slot size, slots, sprites per object)
    0x0528: (0xFF00, 0x20, 8, 1), 0x0531: (0xF000, 0x20, 16, 1), 0x054B: (0xF000, 0x40, 8, 2),
    0x0561: (0xF000, 0x40, 7, 3), 0x057A: (0xF000, 0x80, 4, 4), 0x0583: (0xF600, 0x80, 9, 4)}
ITEM_LETTER_TEMPLATES = {  # $2A23-$2A7E: carrier +$18 letter -> pickup template (fixed ROM)
    0x50: 0x4DCF, 0x74: 0x513D, 0x62: 0x5174, 0x6D: 0x51AB, 0x33: 0x51E2, 0x79: 0x5219,
    0x73: 0x5246, 0x41: 0x5273, 0x43: 0x546F, 0x54: 0x549C, 0x49: 0x54C9, 0x4D: 0x54F6}
ITEM_CODES = {  # +$0A of a pickup -> effect when touched ($2657 dispatcher)
    0x00: 'enemy (not a pickup)', 0x80: 'speed up (player+$18 += 1, max 3)',
    0x81: 'speed down (player+$18 -= 1, min 1)', 0x01: 'weapon slot +$11 (+1, max 3; also pod at player+$80 via $1F26)',
    0x02: 'weapon slot +$12 (+1, max 3)', 0x03: 'weapon slot +$13 (+1, max 2)', 0x04: 'weapon slot +$14 (+1, max 2)',
    0x10: 'set player+$15 = $10', 0x11: 'set player+$15 = $11', 0x06: 'special: $2E4E (clears player sub-objects, $3078)',
    0x07: 'bonus: score from +$15 only', 0x08: 'extra life (player+$0B += 1)'}
# spawn routine (script CALL target / SPAWN template) -> family id used in docs/re/objects.md section 6
FAMILIES = {}
for _f, _rs in {
    'trooper_tan': (0x8314, 0x8318, 0x831C, 0x8320), 'trooper_green_drop': (0x8A57, 0x8A5B),
    'surfacing_robot': (0x8C9E, 0x8CA3, 0x8CA8, 0x8CAD), 'trooper_hover': (0x8DB6, 0x8DBA, 0x8DBE, 0x8DC2),
    'trooper_yellow': (0x90CA, 0x90CE), 'trooper_red': (0x9547, 0x954B), 'bomb_column': (0x9815,),
    'turret_crab': (0x9B27, 0x9B2B, 0x9B2F), 'turret_missile': (0x9CB7, 0x9CBB, 0x9CBF, 0x9CC3, 0x9CC7, 0x9CCB, 0x9CCF),
    'turret_spike': (0x9EAD, 0x9EB1, 0x9EB5, 0x9EB9, 0x9EBD, 0x9EC1, 0x9EC5, 0x9EC9), 'turret_dome_laser': (0xA008, 0xA014),
    'jet_homing': (0xA4DA, 0xA4DE, 0xA4E2, 0xA4E6, 0xA4EA), 'pod_column_pow': (0xA905,),
    'pod_vertical': (0xAAB3, 0xAAB7, 0xAABB, 0xAABF, 0xAAC3, 0xAAC7), 'drum_homing': (0xAD32, 0xAD36, 0xAD3A, 0xAD3E, 0xAD42),
    'orb_burst': (0xB15D,), 'eye_turret': (0xB65D, 0xB662, 0xB667), 'mine_homing': tuple(range(0xBAF6, 0xBB13, 4)),
    'barrier_pair': (0xBD66,), 'coin_easter_egg': (0x5523,), 'snake_chain_a': (0x5575,), 'snake_chain_b': (0x5A9C,),
    'boss_battleship_a': (0x69D0,), 'boss_dragon_b': (0x6C12,), 'boss_battleship_c': (0x6DB4,),
    'boss_wheel': (0x7192, 0x719C, 0x71A6), 'boss_final': (0x5FC3,),
    'hidden_alpha_capsule': (0x52FF,), 'hidden_bonus_cow': (0x5337,), 'hidden_bonus_3000': (0x5385, 0x53D3),
    'hidden_1up': (0x5421,)}.items():
    for _r in _rs:
        FAMILIES[_r] = _f
SCORE_TABLE = 0x2337  # 8 BCD digits ending at $2337+index; displayed value = digits * 10
BULLET_DIR_TABLES = {3: 0x4022, 4: 0x4066, 5: 0x40AA, 6: 0x40EE}  # $818C


def score_points(idx):
    if idx < 7:
        return 0
    d = M[SCORE_TABLE + idx - 7:SCORE_TABLE + idx + 1]
    return int(''.join(str(x) for x in d)) * 10


# ---------------------------------------------------------------- templates & motion scripts
def decode_template(bank, a, raw=None):
    t = raw if raw is not None else bytes(rd(bank, a + i) for i in range(32))
    attr = t[1]
    return {
        'addr': h4(a), 'bank': bank if (a is not None and a >= 0x8000) else None,
        'code': t[0] | ((attr << 3) & 0x700), 'color': attr & 15, 'x_hi': (attr >> 4) & 1,
        'y': t[2], 'x': t[3] | ((attr & 0x10) << 4), 'timer': t[4], 'dy': s8(t[5]), 'dx': s8(t[6]),
        'category': t[7], 'state': t[8], 'flags': t[9], 'flags_meaning': flag_names(t[9]),
        'item': t[10], 'item_meaning': ITEM_CODES.get(t[10], 'unknown'), 'hp': t[11],
        'shot_box': [t[12], t[13]], 'body_box': [t[14], t[15]], 'b10': t[16], 'score_index': t[0x15],
        'score_points': score_points(t[0x15]), 'carrier_letter': t[0x18] or None,
        'wall_handler': h4(t[0x1A] | t[0x1B] << 8) if (t[0x1A] | t[0x1B]) else None,
        'death': h4(t[0x1C] | t[0x1D] << 8) if (t[0x1C] | t[0x1D]) else None,
        'motion': h4(t[0x1E] | t[0x1F] << 8), 'raw': t.hex()}


def flag_names(f):
    n = []
    if f & 0x01: n.append('immune to shots')
    if f & 0x02: n.append('no player contact')
    if f & 0x04: n.append('ignores terrain')
    if f & 0x20: n.append('scrolls with BG')
    if f & 0x40: n.append('dying')
    if f & 0x80: n.append('native death handler')
    return n


def decode_motion(bank, ptr, max_steps=64):
    """+$1E points 5 bytes before the first step. Steps: [dur, code, attr, dy, dx];
    dur 0 = native code at (code|attr<<8); $FF = goto; $FE = kill."""
    steps, seen, p = [], set(), (ptr + 5) & 0xFFFF
    for _ in range(max_steps):
        if p in seen:
            steps.append({'op': 'loop', 'to': h4(p)}); break
        seen.add(p)
        d = rd(bank, p)
        if d == 0:
            steps.append({'op': 'native', 'addr': h4(rw(bank, p + 1))}); break
        if d == 0xFF:
            q = rw(bank, p + 1)
            steps.append({'op': 'goto', 'to': h4(q)}); p = q; continue
        if d == 0xFE:
            steps.append({'op': 'kill'}); break
        c, at = rd(bank, p + 1), rd(bank, p + 2)
        steps.append({'op': 'show', 'frames': d, 'code': c | ((at << 3) & 0x700), 'color': at & 15,
                      'dy': s8(rd(bank, p + 3)), 'dx': s8(rd(bank, p + 4))})
        p += 5
    return steps


# ---------------------------------------------------------------- routine execution
class Effects:
    def __init__(self):
        self.tasks, self.sounds = [], []


def run_routine(addr, state, difficulty):
    """Execute a bank-0 library routine as the script interpreter would ($20C6: bank 0, call via $E0F8)."""
    fx = Effects()

    def task_hook(cpu):
        fx.tasks.append({'slot': cpu.a, 'entry': h4(cpu.bc)}); cpu.ret()

    def snd_hook(cpu):
        fx.sounds.append(cpu.a); cpu.ret()

    def stop_hook(cpu):
        raise Stop('kernel call at %04X' % cpu.pc)

    cpu = Z80(lambda a: rd(0, a), hooks={0x00EF: task_hook, 0x02F3: snd_hook, 0x0302: snd_hook,
                                          0x010F: stop_hook, 0x012E: stop_hook, 0x0102: task_hook})
    for k, v in state.items():
        cpu.ram[k] = v
    # DSW0: MAME default $FC; difficulty field = ~bits0-2
    cpu.ram[0xC803] = (0xF8 | ((~difficulty) & 7)) & 0xFF
    cpu.ram[0xC804] = 0xFF
    err = None
    try:
        cpu.call(addr)
    except (Unsupported, Stop) as e:
        err = str(e)
    # created objects: record heads with +8 != 0 in $F000-$FFFF
    objs = []
    for base in range(0xF000, 0x10000, 0x20):
        if cpu.ram.get(base + 8, 0) and any((base + i) in cpu.ram for i in range(32)):
            raw = bytes(cpu.ram.get(base + i, 0) for i in range(32))
            if base >= 0xFB00 and base < 0xFF00 and base != 0xFB00:
                continue  # boss sub-records
            src = [c[0] for c in cpu.copies if c[1] == base and c[2] == 0x20]
            objs.append((base, raw, src[-1] if src else None))
    return cpu, fx, objs, err


# ---------------------------------------------------------------- script simulation
STAGE_STARTS = None  # filled from table $15B4


def simulate(start, difficulty, end=None, max_ticks=200000):
    """Run the event script from `start` ($E090) like $1FE5-$211F (one tick = 2 frames)."""
    # game start ($0D6E-$0D7F): camera 0,0, horizontal scroll ($80A7/$80B3), mode $80
    st = {0xE080: 0x80, 0xE088: 0, 0xE089: 0, 0xE08A: 0, 0xE08B: 1, 0xE048: 0, 0xE017: 0,
          0xE092: 0, 0xE093: 0, 0xE094: 0, 0xE095: 0, 0xE050: 0x22, 0xE051: 0x40}
    ptr, tick, events = start, 0, []
    stage_tick = 0
    while tick < max_ticks:
        if end is not None and ptr >= end:
            break
        tick += 1
        stage_tick += 1
        mode = st[0xE080]
        if mode == 0x80:
            st[0xE088], st[0xE089] = st[0xE08A], st[0xE08B]
        else:
            st[0xE088] = st[0xE089] = 0
        if mode == 0x20:
            cnt = (st.get(0xE084, 0) | st.get(0xE085, 0) << 8) - 1
            st[0xE084], st[0xE085] = cnt & 0xFF, (cnt >> 8) & 0xFF
            if cnt != 0:
                continue
            st[0xE080] = 0x80
            st[0xE088], st[0xE089] = st[0xE08A], st[0xE08B]
            mode = 0x80
        if mode == 0x40:
            # halted for a boss: the game resumes via $8051 from the boss-death task ($3976/$3A66).
            # Positions do not change while halted, so resume immediately.
            st[0xE080] = 0x80
            events.append({'tick': tick, 'kind': 'resume_after_boss', 'script': h4(ptr)})
            continue
        for ax, dr in ((0xE094, 0xE088), (0xE092, 0xE089)):
            if st[dr]:
                v = (st[ax] | st[ax + 1] << 8) + (1 if st[dr] == 1 else -1)
                v &= 0xFFF
                st[ax], st[ax + 1] = v & 0xFF, v >> 8
        if not (st[0xE089] or st[0xE088]):
            continue
        while True:
            # $2049-$2065: the axis low byte is re-read for every entry (a CALL may move the camera)
            key = st[0xE092] if st[0xE089] else st[0xE094]
            cmd, trig = rd(1, ptr), rd(1, ptr + 1)
            if trig != key:
                break
            cam = {'x': st[0xE092] | st[0xE093] << 8, 'y': st[0xE094] | st[0xE095] << 8}
            ev = {'tick': tick, 'frame': tick * 2, 'script': h4(ptr), 'cmd': '%02X' % cmd,
                  'trigger': trig, 'camera': cam, 'scroll': {'dy': s8(st[0xE088]), 'dx': s8(st[0xE089])}}
            if cmd == 0xFF:
                ev['kind'] = 'page'
                ptr += 2
                events.append(ev)
                break
            target = rw(1, ptr + 2)
            ptr += 4
            if cmd == 0xFE:
                ev['kind'] = 'call'; ev['routine'] = h4(target)
                if target in FAMILIES: ev['family'] = FAMILIES[target]
                cpu, fx, objs, err = run_routine(target, st, difficulty)
                for k in (0xE080, 0xE084, 0xE085, 0xE08A, 0xE08B, 0xE092, 0xE093, 0xE094, 0xE095,
                          0xE048, 0xE017, 0xE050, 0xE051):
                    if k in cpu.ram:
                        st[k] = cpu.ram[k]
                if fx.tasks: ev['tasks'] = fx.tasks
                if fx.sounds: ev['sounds'] = ['%02X' % s for s in fx.sounds]
                if objs: ev['objects'] = [obj_summary(b, r, t) for b, r, t in objs]
                if err: ev['note'] = err
                if cpu.ram.get(0xE048, 0) != st.get('_letter', 0):
                    pass
            elif cmd in (0xFB, 0xFC, 0xFD):
                ev['kind'] = 'task'; ev['slot'] = cmd - 0xF8; ev['entry'] = h4(target)
            else:
                ev['kind'] = 'spawn_template'
                ev['family'] = FAMILIES.get(target)
                raw = bytearray(rd(0, target + i) for i in range(32))
                if st[0xE089]:
                    raw[2] = cmd
                else:
                    raw[2] = 0xF0
                    raw[3] = ((cmd & 0xFE) << 1 | (cmd & 0xFE) >> 7) & 0xFF
                    if not (cmd & 0x80):
                        raw[1] &= ~0x10
                ev['objects'] = [obj_summary(0xFF00, bytes(raw), tmpl=target)]
            events.append(ev)
        if rd(1, ptr) == 0xFF and rd(1, ptr + 1) == 0xFF and rd(1, ptr + 2) == 0xFF and rd(1, ptr + 3) == 0xFF \
                and rd(1, ptr + 4) == 0xFF:
            break  # end of script ($A406.. filler)
    return events


TEMPLATE_INDEX = {}


def obj_summary(base, raw, tmpl=None):
    d = decode_template(None, None, raw)
    if tmpl is None:
        tmpl = TEMPLATE_INDEX.get(bytes(raw[7:12]) + bytes(raw[12:16]) + bytes(raw[0x1A:0x1E]))
    o = {'slot': h4(base), 'template': h4(tmpl) if tmpl else None,
         'screen': {'x': d['x'], 'y': d['y']}, 'code': d['code'], 'color': d['color'], 'hp': d['hp'],
         'score': d['score_points'], 'item': d['item'], 'flags': d['flags'], 'motion': d['motion'],
         'wall_handler': d['wall_handler'], 'death': d['death']}
    if raw[0x18]:
        o['carries'] = chr(raw[0x18])
    if raw[0x10]:
        o['b10'] = raw[0x10]
    return o


# ---------------------------------------------------------------- template discovery
def find_templates():
    """All `ld hl,T / ld bc,$0020 / ldir` sites = object templates copied into sprite RAM."""
    out = {}
    for mt in re.finditer(rb'\x21(..)\x01\x20\x00\xed\xb0', M, re.S):
        off = mt.start()
        t = mt.group(1)[0] | mt.group(1)[1] << 8
        bank = 0 if off < 0x8000 else (off - 0x8000) // 0x4000
        site = off if off < 0x8000 else 0x8000 + (off - 0x8000) % 0x4000
        if t >= 0x8000 and bank != 0:
            continue
        out.setdefault(t, []).append({'site': h4(site), 'bank': bank})
    for t in list(ITEM_LETTER_TEMPLATES.values()) + [0x52FF, 0x5337, 0x5385, 0x53D3, 0x5421, 0x69F7, 0x6C39, 0x6DDB]:
        out.setdefault(t, [])
    return out


def pow_chain(start=0x4E01):
    """Follow the POW capsule death-handler chain ($4E01...): each hit changes the capsule."""
    def find(a, pat, n=96):
        for k in range(a, a + n):
            if all(rd(0, k + i) == x for i, x in enumerate(pat)):
                return k
    h, seen, out = start, set(), []
    while h and h not in seen:
        seen.add(h)
        k = find(h, [0xC3, 0x35, 0x24])
        trans = decode_motion(0, rw(0, k - 2) - 5, 8)
        nat = [s for s in trans if s['op'] == 'native']
        if not nat:
            break
        n = int(nat[0]['addr'], 16)
        entry = {'handler': h4(h), 'transition': [s for s in trans if s['op'] == 'show']}
        k1 = find(n, [0xDD, 0x36, 0x0A]); k2 = find(n, [0xDD, 0x36, 0x0B])
        if k1 is not None and k1 < n + 4:
            entry['item'] = rd(0, k1 + 3); entry['hp'] = rd(0, k2 + 3)
            k3 = find(n, [0xDD, 0x75, 0x1C]); k4 = find(k3, [0xC3, 0x35, 0x24])
            entry['idle'] = decode_motion(0, rw(0, k4 - 2) - 5, 8)
            entry['next_handler'] = h4(rw(0, k3 - 2))
            out.append(entry)
            h = rw(0, k3 - 2)
        else:
            entry['note'] = 'random: item $10 or $11 (RNG $E008 bit7), immune to shots afterwards ($50FD)'
            out.append(entry)
            break
    return out


# ---------------------------------------------------------------- reachable animation frames
MOTION_ENTRIES = (0x27EE, 0x2435, 0x2B1B)   # big / small / boss "set motion pointer = HL" entries


def _motion_ok(bank, p):
    d = rd(bank, p)
    if d in (0, 0xFE, 0xFF):
        return d != 0 or rw(bank, p + 1) >= 0x2E00
    return abs(s8(rd(bank, p + 3))) <= 8 and abs(s8(rd(bank, p + 4))) <= 8


def reachable_frames(motion_ptr, bank=0, limit=400, region=None, natives=()):
    """Static byte-pattern crawl: motion steps -> native code -> `ld hl,nn` + jp to a set-motion entry.
    Collects every (code,color) shown. Heuristic (no full disassembly): may include neighbours."""
    frames, seen_m, seen_n = [], set(), set()
    todo = [('m', motion_ptr + 5)] + [('n', n) for n in natives]
    while todo and len(seen_m) + len(seen_n) < limit:
        k, a = todo.pop()
        if k == 'm':
            if a in seen_m or not _motion_ok(bank, a):
                continue
            seen_m.add(a)
            p = a
            for _ in range(64):
                d = rd(bank, p)
                if d == 0:
                    todo.append(('n', rw(bank, p + 1))); break
                if d == 0xFF:
                    todo.append(('m', rw(bank, p + 1))); break
                if d == 0xFE:
                    break
                if abs(s8(rd(bank, p + 3))) > 8 or abs(s8(rd(bank, p + 4))) > 8:
                    break
                fc = (rd(bank, p + 1) | ((rd(bank, p + 2) << 3) & 0x700), rd(bank, p + 2) & 15)
                if fc not in frames:
                    frames.append(fc)
                p += 5
                if d >= 200:
                    break
        else:
            if a in seen_n or a < 0x2E00 or (region and not region[0] <= a < region[1]):
                continue
            seen_n.add(a)
            n = 0xC0 if not region else max(4, min(0xC0, region[1] - a))
            blk = [rd(bank, a + i) for i in range(n)]
            has_set = any(blk[i] == 0xC3 and (blk[i + 1] | blk[i + 2] << 8) in MOTION_ENTRIES for i in range(len(blk) - 2))
            for i in range(len(blk) - 3):
                if blk[i] == 0x21:
                    nn = blk[i + 1] | blk[i + 2] << 8
                    if blk[i + 3] == 0x01 and i + 5 < len(blk) and blk[i + 4] == 0x20:
                        continue  # template copy
                    if has_set and (nn >= 0x8000 or 0x2E00 <= nn < 0x8000):
                        todo.append(('m', nn))
                if blk[i] in (0xC3, 0xCA, 0xC2, 0xDA, 0xD2):
                    nn = blk[i + 1] | blk[i + 2] << 8
                    if abs(nn - a) < 0x300 and nn not in MOTION_ENTRIES and nn >= 0x2E00:
                        todo.append(('n', nn))
    return frames


# ---------------------------------------------------------------- metasprites
def metasprites(templates):
    rules = {
        '1x1': {'records': 1, 'parts': [{'dx': 0, 'dy': 0, 'code_add': 0}],
                'used_by': 'objects from allocators $0528 ($FF00 x8), $0531 ($F000 x16); bullets, pickups, chains'},
        '2x2': {'records': 4, 'parts': [{'dx': 0, 'dy': 0, 'code_add': 0}, {'dx': 16, 'dy': 0, 'code_add': 1},
                                        {'dx': 0, 'dy': 16, 'code_add': 8}, {'dx': 16, 'dy': 16, 'code_add': 9}],
                'source': '$281D-$28F7 (record +$00/+$20/+$40/+$60)', 'used_by': '$F600-$FA7F (9 slots) and $057A'},
        '8x4_boss': {'records': 32, 'parts': [{'dx': 16 * (r % 8), 'dy': 16 * (r // 8), 'code_add': r} for r in range(32)],
                     'source': '$2B4A-$2CF2 ($FB00-$FEFF)', 'note': 'codes c..c+31 row-major, sheet 8 codes wide'},
        'chain8': {'records': 8, 'source': '$5575/$5A9C', 'note': '8 independent 1x1 segments in $F000-$F0FF or '
                   '$F100-$F1FF; +$11 role $48 head / $4D body / $54 tail; start timers 5,10..40'},
    }
    frames = {}
    for t, sites in sorted(templates.items()):
        bank = 0
        raw = bytes(rd(bank, t + i) for i in range(32))
        mp = raw[0x1E] | raw[0x1F] << 8
        if not mp:
            continue
        steps = decode_motion(bank, mp, 24)
        shows = [s for s in steps if s['op'] == 'show']
        if not shows:
            continue
        uniq = []
        for s in shows:
            k = (s['code'], s['color'])
            if k not in uniq:
                uniq.append(k)
        frames[h4(t)] = [{'code': c, 'color': col} for c, col in uniq]
    shared = {
        'explosion_2x2_c8': {'script': '4D5E', 'frames': [[c, 8] for c in (0x1C0, 0x1C2, 0x1C4, 0x1C6, 0x1D0, 0x1D2, 0x1D4, 0x1D6)],
                             'frame_len': 4, 'layout': '2x2'},
        'explosion_2x2_c7': {'script': '4D87', 'frames': [[c, 7] for c in (0x1C0, 0x1C2, 0x1C4, 0x1C6, 0x1D0, 0x1D2, 0x1D4)],
                             'frame_len': 4, 'layout': '2x2'},
        'explosion_1x1': {'script': '4DAB', 'frames': [[c, 8] for c in range(0x138, 0x13F)], 'frame_len': 5, 'layout': '1x1'},
        'enemy_bullet': {'frames': [[0x126, 8], [0x127, 7]], 'frame_len': 1, 'layout': '1x1'},
    }
    return {'rules': rules, 'template_frames': frames, 'shared_animations': shared}


def family_frames(events):
    """family -> {'layout', 'frames':[[code,color],...]} from every motion pointer the family's spawns use."""
    starts = sorted(set(FAMILIES))
    def region_of(fam):
        rs = [r for r, f in FAMILIES.items() if f == fam]
        lo = min(rs)
        nxt = [x for x in starts if x > max(rs) and FAMILIES[x] != fam]
        hi = min(nxt) if nxt else 0xC000
        if lo < 0x8000:
            return (lo, min(hi, 0x8000))
        return (lo, hi)
    out = {}
    for st in events:
        for e in st['events']:
            fam = e.get('family')
            if not fam or not e.get('objects'):
                continue
            f = out.setdefault(fam, {'layout': None, 'motions': set(), 'frames': []})
            for o in e['objects']:
                slot = int(o['slot'], 16)
                f['layout'] = ('8x4_boss' if slot == 0xFB00 else '2x2' if 0xF600 <= slot < 0xFB00 and (slot - 0xF600) % 0x80 == 0
                               else '1x1')
                f['motions'].add(int(o['motion'], 16))
                for h in (o.get('wall_handler'), o.get('death')):
                    if h:
                        f.setdefault('handlers', set()).add(int(h, 16))
    for fam, f in out.items():
        reg = region_of(fam)
        hs = sorted(f.pop('handlers', set()))
        for mp in sorted(f['motions']):
            for fc in reachable_frames(mp, region=reg, natives=[h for h in hs if reg[0] <= h < reg[1]]):
                if list(fc) not in f['frames']:
                    f['frames'].append(list(fc))
        f['motions'] = ['%04X' % m for m in sorted(f['motions'])]
        f['code_region'] = ['%04X' % reg[0], '%04X' % reg[1]]
        f['note'] = 'frames found by a static byte-pattern crawl of motion scripts and native code in code_region'
    return out


def main():
    global M
    ap = argparse.ArgumentParser()
    ap.add_argument('--difficulty', type=int, default=3)
    ap.add_argument('--out', default=str(ROOT / 'res/generated'))
    o = ap.parse_args()
    M = Source().region('maincpu')
    templates = find_templates()
    for t in templates:
        raw = bytes(rd(0, t + i) for i in range(32))
        TEMPLATE_INDEX[raw[7:12] + raw[12:16] + raw[0x1A:0x1E]] = t
    starts = [rw(0, 0x15B4 + 2 * i) for i in range(16)]
    stage_starts = []
    for s in starts:
        if s not in stage_starts:
            stage_starts.append(s)
    # one continuous run from the game-start entry; events are attributed to stages by the
    # debug stage-select table $15B4 (entry addresses), as the script itself has no stage markers.
    evs = [e for e in simulate(stage_starts[0], o.difficulty) if e.get('kind') != 'page']
    stages = []
    for i, s in enumerate(stage_starts):
        end = stage_starts[i + 1] if i + 1 < len(stage_starts) else 0x10000
        se = [e for e in evs if 'script' in e and s <= int(e['script'], 16) < end]
        t0 = se[0]['tick'] if se else 0
        for e in se:
            e['stage_tick'] = e['tick'] - t0
        stages.append({'stage': i + 1, 'script_start': h4(s), 'script_end': h4(end if end < 0x10000 else None),
                       'events': se})
    tdec = {}
    for t, sites in sorted(templates.items()):
        d = decode_template(0, t)
        d['copied_at'] = sites
        mp = int(d['motion'], 16)
        if mp:
            d['motion_script'] = decode_motion(0, mp, 24)
        if d['death'] and not (d['flags'] & 0x80):
            d['death_script'] = decode_motion(0, int(d['death'], 16) - 5, 16)
        tdec[h4(t)] = d
    bullet = {}
    for spd, tab in BULLET_DIR_TABLES.items():
        bullet[str(spd)] = {'table': h4(tab), 'dirs': [{'dir': k, 'script': h4(rw(0, tab + 2 * k)),
                                                        'steps': decode_motion(0, rw(0, tab + 2 * k), 8)} for k in range(32)]}
    caps = {}
    for a in range(0x8000, 0x8031, 4):
        c = rd(0, a + 1)
        caps[h4(a)] = [max(0, s8(rd(0, 0x8049 + d)) + c) for d in range(8)]
    speed_by_stage = {h4(0x813C + 8 * k): [rd(0, 0x813C + 8 * k + d) for d in range(8)] for k in range(10)}
    data = {
        'source': 'Side Arms (MAME sidearms) maincpu; see docs/re/objects.md',
        'difficulty': o.difficulty,
        'tick_frames': 2,
        'camera_note': 'camera = BG scroll registers $E092 (x) / $E094 (y) at the tick the event fires; '
                       'object screen coords are raw sprite coords (visible x 64..447, y 16..239)',
        'stages': stages,
        'templates': tdec,
        'families': {h4(k): v for k, v in sorted(FAMILIES.items())},
        'item_letters': {chr(k): h4(v) for k, v in ITEM_LETTER_TEMPLATES.items()},
        'item_codes': {'%02X' % k: v for k, v in ITEM_CODES.items()},
        'pow_chain': pow_chain(),
        'score_table': {'%02X' % i: score_points(i) for i in range(8, 0x78, 8)},
        'enemy_bullet': {'template': '4000', 'direction_tables_by_speed': bullet,
                         'speed_level_by_stage_and_difficulty': speed_by_stage,
                         'max_bullets_routines': caps},
    }
    out = Path(o.out); out.mkdir(parents=True, exist_ok=True)
    (out / 'spawns.json').write_text(json.dumps(data, indent=1))
    ms = metasprites(templates)
    ms['family_frames'] = family_frames(stages)
    (out / 'metasprites.json').write_text(json.dumps(ms, indent=1))
    n = sum(len(s['events']) for s in stages)
    print('stages', len(stages), 'events', n, 'templates', len(tdec), '->', out)


if __name__ == '__main__':
    main()
