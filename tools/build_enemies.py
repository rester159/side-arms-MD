#!/usr/bin/env python3
"""Native enemy tables, generated from the arcade ROM at build time.

Inputs
  ROM (maincpu, via tools/arcade_source.py)    motion scripts, templates, tables
  res/generated/spawns.json / levels.json      per-section event order (must match build_levels.py)
  src/*.c, src/*.h                              which scripts / tables / natives the C code uses

Outputs (ignored by git)
  src/gen/enemy_data.c, inc/gen/enemy_data.h

Design (docs/enemies.md):
* Motion scripts become one flat ROM array `mot[]` of 6-byte steps. A step either shows a frame
  for `dur` frames while moving (dy, dx) per frame, or is a control step (dur 0): goto, kill or
  "native" (call a C behaviour function). Arcade step addresses are only used as names
  (MOT_ADA8 = index of the step that was at $ADA8), never at runtime.
* The C code says what it needs, and only that is generated:
    MOT_xxxx            index of the step at $xxxx (a script entry used by C code)
    MOTTAB_xxxx_n       n step indices read from a ROM word table at $xxxx (entries are steps)
    MOTPTR_xxxx_n       same, entries are motion pointers (+$1E style, step = word + 5)
    ROMB_xxxx_n         n raw bytes of a ROM data table (directions, positions ...)
    TPL_xxxx            EnemyInit index of the object template at $xxxx
    AI_xxxx             behaviour id of the native routine at $xxxx
  A C function preceded by the comment  @native xxxx [yyyy ...]  implements those natives.
* Every object a spawn event creates becomes an EnemyInit (deduplicated); every EV_SPAWN event of
  levels.c becomes a SpawnEvent in the same order as tools/build_levels.py numbers them.
"""
import json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from arcade_source import Source  # noqa: E402
import extract_spawns as es       # noqa: E402

GEN = ROOT / 'res/generated'
DIFFICULTY = 3                     # MAME default; spawns.json was extracted with the same value

M = Source().region('maincpu')
es.M = M


def rd(a):
    return es.rd(0, a)


def rw(a):
    return es.rw(0, a)


def s8(v):
    return v - 256 if v > 127 else v


# ------------------------------------------------------------------ what the C code asks for
srcs = sorted(list((ROOT / 'src').glob('*.c')) + list((ROOT / 'src').glob('*.h')))
srcs = [p for p in srcs if 'gen' not in p.parts]
ctext = '\n'.join(p.read_text() for p in srcs)
want_mot = sorted({int(a, 16) for a in re.findall(r'\bMOT_([0-9A-F]{4})\b', ctext)})
want_mottab = sorted({(int(a, 16), int(n)) for a, n in re.findall(r'\bMOTTAB_([0-9A-F]{4})_(\d+)\b', ctext)})
want_motptr = sorted({(int(a, 16), int(n)) for a, n in re.findall(r'\bMOTPTR_([0-9A-F]{4})_(\d+)\b', ctext)})
want_romb = sorted({(int(a, 16), int(n)) for a, n in re.findall(r'\bROMB_([0-9A-F]{4})_(\d+)\b', ctext)})
want_tpl = sorted({int(a, 16) for a in re.findall(r'\bTPL_([0-9A-F]{4})\b', ctext)})
want_ai = sorted({int(a, 16) for a in re.findall(r'\bAI_([0-9A-F]{4})\b', ctext)})
impl = {}                                   # native address -> C function name
for m in re.finditer(r'@native((?:\s+[0-9A-F]{4})+)\s*\*/\s*(?:static\s+)?void\s+(\w+)\s*\(', ctext):
    for a in m.group(1).split():
        impl[int(a, 16)] = m.group(2)

# ------------------------------------------------------------------ re-run the spawn simulation
# (same code path as tools/extract_spawns.py, keeping each created object's full 32-byte record)
_orig_summary = es.obj_summary


def _summary(base, raw, tmpl=None):
    o = _orig_summary(base, raw, tmpl)
    o['raw'] = bytes(raw).hex()
    return o


es.obj_summary = _summary
for t in es.find_templates():
    raw = bytes(rd(t + i) for i in range(32))
    es.TEMPLATE_INDEX[raw[7:12] + raw[12:16] + raw[0x1A:0x1E]] = t
starts = []
for s in [rw(0x15B4 + 2 * i) for i in range(16)]:
    if s not in starts:
        starts.append(s)
sim = [e for e in es.simulate(starts[0], DIFFICULTY) if e.get('kind') != 'page']

sp = json.loads((GEN / 'spawns.json').read_text())
lv = json.loads((GEN / 'levels.json').read_text())

# ------------------------------------------------------------------ motion steps
# addresses known to be native code (terrain handlers, native deaths, C-implemented natives):
# a script that runs on into them is cut there
CODE = set(impl) | set(es.FAMILIES) | set(range(0x8000, 0x8310))   # + spawn and script routines
for e in sim:
    for o in e.get('objects', []):
        raw = bytes.fromhex(o['raw'])
        if raw[0x1A] | raw[0x1B]:
            CODE.add(raw[0x1A] | raw[0x1B] << 8)
        if raw[9] & 0x80:
            CODE.add(raw[0x1C] | raw[0x1D] << 8)

CTL_GOTO, CTL_KILL, CTL_NATIVE = 0, 1, 2
steps = []          # (dur, colour_or_ctl, dy, dx, code_or_arg, comment)
step_at = {}        # arcade address -> index
natives = {}        # address -> ai id (1..)
pending = []


def native_id(a):
    if a not in natives:
        natives[a] = len(natives) + 1
    return natives[a]


def visit(a):
    """Index of the step at arcade address a (decoding the script from there if new)."""
    if a in step_at:
        return step_at[a]
    first = len(steps)
    cur = a
    for _ in range(400):
        if cur in step_at:
            steps.append([0, CTL_GOTO, 0, 0, step_at[cur], 'goto $%04X' % cur])
            break
        if cur in CODE and cur != a:     # ran into native code: the arcade never gets this far
            steps.append([0, CTL_KILL, 0, 0, 0, 'end (code at $%04X)' % cur])
            break
        step_at[cur] = len(steps)
        b = rd(cur)
        if b == 0:
            n = rw(cur + 1)
            steps.append([0, CTL_NATIVE, 0, 0, native_id(n), 'native $%04X' % n])
            break
        if b == 0xFF:
            t = rw(cur + 1)
            steps.append([0, CTL_GOTO, 0, 0, None, 'goto $%04X' % t])
            pending.append((len(steps) - 1, t))
            break
        if b == 0xFE:
            steps.append([0, CTL_KILL, 0, 0, 0, 'kill'])
            break
        at = rd(cur + 2)
        code = rd(cur + 1) | ((at << 3) & 0x700)
        dy, dx = s8(rd(cur + 3)), s8(rd(cur + 4))
        steps.append([b, at & 15, dy, dx, code, '$%04X' % cur])
        cur += 5
        if abs(dx) * b >= 0x200 or abs(dy) * b >= 0x100:
            # the object has left the 9-bit / 8-bit screen before this step ends: whatever follows
            # in the ROM (often code) is never reached
            steps.append([0, CTL_KILL, 0, 0, 0, 'off screen'])
            break
    else:
        raise SystemExit('script at $%04X too long' % a)
    return step_at[a]


def resolve():
    while pending:
        i, t = pending.pop()
        steps[i][4] = visit(t)


# ------------------------------------------------------------------ templates / inits
POOL_SMALL, POOL_BIG, POOL_ITEM = 0, 1, 2
inits, init_key = [], {}


def pool_of(slot):
    a = int(slot, 16)
    if a >= 0xFF00:
        return POOL_ITEM
    if a >= 0xF600:
        return POOL_BIG
    return POOL_SMALL


def make_init(raw, pool, comment):
    raw = bytes(raw)
    attr = raw[1]
    flags = raw[9]
    death_a = raw[0x1C] | raw[0x1D] << 8
    wall_a = raw[0x1A] | raw[0x1B] << 8
    mot_a = raw[0x1E] | raw[0x1F] << 8
    nxt = visit((mot_a + 5) & 0xFFFF) if mot_a else 0xFFFF
    if flags & 0x80:
        death = native_id(death_a)
    else:
        death = visit(death_a) if death_a else 0xFFFF
    # +$1A is only a terrain handler for objects that test terrain (flag bit 2 clear); others may
    # keep unrelated data there (e.g. the orb fragments' continuation pointer)
    wall = native_id(wall_a) if wall_a and not (flags & 0x04) else 0
    x = raw[3] | ((attr & 0x10) << 4)
    y = raw[2]
    rec = dict(code=raw[0] | ((attr << 3) & 0x700), colour=attr & 15, timer=raw[4] or 1,
               x=x - 96, y=(y - 256 if y >= 0xF8 else y) - 16, dy=s8(raw[5]), dx=s8(raw[6]),
               cat=raw[7], flags=flags, item=raw[10], hp=raw[11],
               box=list(raw[12:16]), r=list(raw[0x10:0x1A]), wall=wall, death=death, next=nxt, pool=pool)
    key = json.dumps(rec, sort_keys=True)
    if key not in init_key:
        init_key[key] = len(inits)
        rec['comment'] = comment
        inits.append(rec)
    return init_key[key]


def template_init(t, pool):
    return make_init(bytes(rd(t + i) for i in range(32)), pool, 'template $%04X' % t)


# templates the C code spawns itself (bullets, missiles, pickups ...)
TPL_POOL = {}
ITEM_LETTERS = [ord(c) for c in 'Ptbm3ysACTIM']          # +$18 values in $2A23 order
for t in want_tpl:
    TPL_POOL[t] = template_init(t, POOL_SMALL)
# templates a script SPAWN record may name outside the stage tables (the attract demo's item
# capsules; the script only ever spawns pickups and hidden bonuses): address -> EnemyInit
all_tpl = {}
HIDDEN_TEMPLATES = (0x52FF, 0x5337, 0x5385, 0x53D3, 0x5421)     # objects.md 4.3
for t in sorted(set(es.ITEM_LETTER_TEMPLATES.values()) | set(HIDDEN_TEMPLATES)):
    all_tpl[t] = template_init(t, POOL_ITEM)
letter_init = []
for c in ITEM_LETTERS:
    letter_init.append(template_init(es.ITEM_LETTER_TEMPLATES[c], POOL_ITEM))

# ------------------------------------------------------------------ spawn events per section
SPK_NONE, SPK_SEQ, SPK_LETTER, SPK_GROUP, SPK_EYE, SPK_ORB, SPK_BARRIER = range(7)
LETTER_ROUTINES = {}
for a in range(0x82CC, 0x8310):
    if rd(a) == 0x3E and rd(a + 2) == 0x32 and rw(a + 3) == 0xE048:
        LETTER_ROUTINES[a] = rd(a + 1)

# spawn routines that hand the pending carried letter to the object they create (call $08D2)
CALLS_08D2 = set()
for r, f in es.FAMILIES.items():
    if b'\xcd\xd2\x08' in bytes(rd(a) for a in range(r, r + 0x80)):
        CALLS_08D2.add(f)
sim_by_ptr = {}
for e in sim:
    sim_by_ptr.setdefault((e['script'], e['tick']), e)

sections = []
routine_first = {}  # (routine, True) -> (section, index) of its first spawn event (for the attract demo)
spawn_objs = []     # EnemyInit index per spawned object; a SpawnEvent covers [first, first+count)
for sec, st in zip(lv['sections'], sp['stages']):
    ctrl = {c['ptr'] for c in sec['control']}
    evs = []
    for e in st['events']:
        if e['kind'] == 'resume_after_boss':
            continue
        r = int(e['routine'], 16) if 'routine' in e else None
        if e['script'] in ctrl:
            continue
        s = sim_by_ptr[(e['script'], e['tick'])]
        objs = s.get('objects', [])
        fam = e.get('family') or ''
        kind, first, count, arg = SPK_NONE, 0, 0, 0
        cmt = '%s $%s' % (fam or e['kind'], e.get('routine') or e.get('cmd'))
        if r in LETTER_ROUTINES:
            kind, arg = SPK_LETTER, LETTER_ROUTINES[r]
            cmt = 'carried item letter %r' % chr(arg)
        elif fam.startswith('boss_') or fam == 'coin_easter_egg' or not objs:
            kind = SPK_NONE
        else:
            first, count = len(spawn_objs), len(objs)
            for k, o in enumerate(objs):
                raw = bytearray.fromhex(o['raw'])
                raw[0x18] = 0          # carried letters are handed out at run time ($08D2 / $E048)
                ref = make_init(raw, pool_of(o['slot']), '%s %s' % (fam, o['template']))
                if fam in CALLS_08D2 and (fam != 'eye_turret' or k == 0):
                    ref |= 0x8000      # this spawn takes the pending item letter ($08D2)
                if fam == 'pod_column_pow':
                    ref |= 0x4000      # $A91B: the routine itself sets letter 'P' first
                spawn_objs.append(ref)
            if fam in ('snake_chain_a', 'snake_chain_b'):
                kind, arg = SPK_GROUP, 8
            elif fam == 'bomb_column':
                kind, arg = SPK_GROUP, 4
            elif fam == 'eye_turret':
                kind, arg = SPK_EYE, [0xB65D, 0xB662, 0xB667].index(r)
            elif fam == 'orb_burst':
                kind = SPK_ORB
            elif fam == 'barrier_pair':
                kind = SPK_BARRIER
            else:
                kind = SPK_SEQ
        if r is not None and (r, kind != SPK_NONE) not in routine_first and kind != SPK_NONE:
            routine_first[(r, True)] = (len(sections), len(evs))
        evs.append((kind, first, count, arg, cmt))
    sections.append(evs)

# check against the level timeline numbering (tools/build_levels.py: LevelSection.nspawns)
lvl_c = (ROOT / 'src/gen/level_data.c')
if lvl_c.exists():
    m = re.findall(r'\{\s*-?\d+,\s*-?\d+,\s*(\d+),\s*(\d+),\s*sec\d+\s*\}', lvl_c.read_text())
    n_spawn = [int(b) for a, b in m]
    if n_spawn and n_spawn != [len(s) for s in sections]:
        raise SystemExit('spawn table size mismatch with level_data.c: %s vs %s' % (n_spawn, [len(s) for s in sections]))

# ------------------------------------------------------------------ fixed tables
bullet_dirs = {}
for spd, tab in es.BULLET_DIR_TABLES.items():
    bullet_dirs[spd] = [visit((rw(tab + 2 * k) + 5) & 0xFFFF) for k in range(32)]
aim_table = [rd(0x0780 + i) for i in range(64)]
score_points = [es.score_points(i) for i in range(0, 0x78, 8)]   # index >> 3

# POW capsule chain (death handlers from $4E01, docs/re/objects.md 4.2). Each handler makes the
# capsule intangible and plays a transition; the native at the end of the transition settles the
# new form (item, HP, idle animation). The last form picks AUTO $10/$11 at random ($50FD).
def find_set(a, n=48):
    for b in range(a, a + n):
        if rd(b) == 0x21 and rd(b + 3) == 0xC3 and rw(b + 4) == 0x2435:
            return rw(b + 1)
    return None


pow_rows = []
for p in sp['pow_chain']:
    h = int(p['handler'], 16)
    ti = visit(find_set(h))
    resolve()
    j = ti
    while steps[j][0] != 0:
        j += 1
    assert steps[j][1] == CTL_NATIVE, (p, steps[j])
    settle = [a for a, i in natives.items() if i == steps[j][4]][0]
    impl.setdefault(h, 'pow_turn')
    impl.setdefault(settle, 'pow_settle')
    idle = find_set(settle) if 'item' in p else None
    pow_rows.append(dict(handler=h, settle=settle, trans=ti, item=p.get('item', 0), hp=p.get('hp', 0),
                         idle=visit(idle) if idle else 0xFFFF))
native_id(0x4E01)

# eye turret formations: $B65D/$B662/$B667 use tables $B70E/$B71E/$B72E of 8 pointers, each to
# 5 (y, x>>1 rotated) pairs; the formation is picked at random ($B6DB)
eye_pos = []
for tab in (0xB70E, 0xB71E, 0xB72E):
    sets = []
    for k in range(8):
        q = rw(tab + 2 * k)
        sets.append([rd(q + i) for i in range(10)])
    eye_pos.append(sets)

mot_named = {a: visit(a) for a in want_mot}
mottab = {(a, n): [visit(rw(a + 2 * k)) for k in range(n)] for a, n in want_mottab}
motptr = {(a, n): [visit((rw(a + 2 * k) + 5) & 0xFFFF) for k in range(n)] for a, n in want_motptr}
for a in want_ai:
    native_id(a)
resolve()
# templates may only be known after all natives (TPL list is fixed above) -> done

# ------------------------------------------------------------------ emit
missing = sorted(a for a in natives if a not in impl)
h = ['/* Generated by tools/build_enemies.py from the arcade ROM. Do not edit. */', '#pragma once',
     '#include <genesis.h>', '',
     '/* motion step: dur > 0 shows (code, colour) for dur frames moving (dy, dx) px per frame;',
     ' * dur == 0 is a control step: ctl = MS_GOTO (arg = step), MS_KILL, MS_NATIVE (arg = AI id) */',
     'typedef struct { u8 dur, colour; s8 dy, dx; u16 code; } MStep;',
     'enum { MS_GOTO, MS_KILL, MS_NATIVE };',
     '#define MS_CTL(s) ((s)->colour)', '#define MS_ARG(s) ((s)->code)',
     'extern const MStep en_mot[];', '',
     '/* object initialiser (one per distinct arcade object record a spawn creates) */',
     'typedef struct {',
     '    u16 code; u8 colour, timer;',
     '    s16 x, y;               /* Genesis screen px (arcade sprite coords - (96, 16)) */',
     '    s8 dy, dx;',
     '    u8 cat, flags, item, hp;',
     '    u8 box[4];              /* arcade +$0C..+$0F: shot half-h, shot half-w/2, body half-h, body half-w/2 */',
     '    u8 r[10];               /* arcade +$10..+$19 */',
     '    u8 pool, wall;          /* pool: 0 small, 1 big (2x2), 2 item; wall = AI id of the terrain handler */',
     '    u16 death, next;        /* death: step (or AI id with flags & 0x80); next = first step */',
     '} EnemyInit;',
     'extern const EnemyInit enemy_inits[];', '',
     '/* spawn events (index = EV_SPAWN b of the level timeline) */',
     'enum { SPK_NONE, SPK_SEQ, SPK_LETTER, SPK_GROUP, SPK_EYE, SPK_ORB, SPK_BARRIER };',
     '/* first/count: range of en_spawn_objs[] (EnemyInit index | SO_TAKES_LETTER | SO_SETS_P);',
     ' * arg: LETTER = letter, GROUP = records per group, EYE = formation table 0-2 */',
     '#define SO_TAKES_LETTER 0x8000', '#define SO_SETS_P 0x4000', '#define SO_INDEX 0x3FFF',
     'typedef struct { u8 kind, count; u16 first, arg; } SpawnEvent;',
     'extern const u16 en_spawn_objs[];',
     'typedef struct { u16 n; const SpawnEvent *ev; } SpawnSection;',
     'extern const SpawnSection en_spawn_sections[%d];' % len(sections), '',
     'struct Enemy;', 'typedef void (*EnemyFn)(struct Enemy *e);',
     'extern const EnemyFn en_ai_table[];', '#define AI_COUNT %d' % (len(natives) + 1),
     'extern const u16 en_bullet_dirs[4][32];   /* speed level 3..6 -> first step per direction */',
     'extern const u8 en_aim_table[64];          /* $0780 */',
     'extern const u32 en_score_points[15];      /* $2337, by score index >> 3 */',
     'extern const u16 en_letter_inits[12];      /* pickup per carried letter, $2A23 order: P t b m 3 y s A C T I M */',
     'typedef struct { u16 trans, idle; u8 item, hp; } PowForm;',
     'extern const u8 en_eye_formations[3][8][10]; /* (y, rotated x/2) x 5, tables $B70E/$B71E/$B72E */',
     'typedef struct { u16 addr, init; } TemplateRef;',
     'typedef struct { u16 addr; u8 section; u8 pad; u16 index; } RoutineRef;',
     'extern const RoutineRef en_routines[];     /* spawn routine -> a stage spawn event using it, sorted */',
     'extern const u16 en_routine_count;',
     'extern const TemplateRef en_templates[];   /* arcade template address -> EnemyInit, sorted */',
     'extern const u16 en_template_count;',
     'extern const PowForm en_pow_chain[%d];' % len(pow_rows),
     '#define POW_FORMS %d' % len(pow_rows), '']
for a in sorted(mot_named):
    h.append('#define MOT_%04X %d' % (a, mot_named[a]))
for (a, n) in sorted(mottab):
    h.append('extern const u16 MOTTAB_%04X_%d[%d];' % (a, n, n))
for (a, n) in sorted(motptr):
    h.append('extern const u16 MOTPTR_%04X_%d[%d];' % (a, n, n))
for (a, n) in sorted(set(want_romb)):
    h.append('extern const u8 ROMB_%04X_%d[%d];' % (a, n, n))
for t in sorted(TPL_POOL):
    h.append('#define TPL_%04X %d' % (t, TPL_POOL[t]))
for a, i in sorted(natives.items()):
    h.append('#define AI_%04X %d%s' % (a, i, '' if a in impl else '   /* not implemented */'))
(ROOT / 'inc/gen').mkdir(parents=True, exist_ok=True)
(ROOT / 'src/gen').mkdir(parents=True, exist_ok=True)
(ROOT / 'inc/gen/enemy_data.h').write_text('\n'.join(h) + '\n')

c = ['/* Generated by tools/build_enemies.py from the arcade ROM. Do not edit. */',
     '#include "gen/enemy_data.h"', '']
c.append('const MStep en_mot[%d] = {' % len(steps))
for i, (d, col, dy, dx, code, cm) in enumerate(steps):
    c.append('    {%d, %d, %d, %d, %d},  /* %d %s */' % (d, col, dy, dx, code, i, cm))
c.append('};')
c.append('const EnemyInit enemy_inits[%d] = {' % len(inits))
for i, r in enumerate(inits):
    c.append('    {%d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, {%s}, {%s}, %d, %d, %d, %d},  /* %d %s */' % (
        r['code'], r['colour'], r['timer'], r['x'], r['y'], r['dy'], r['dx'], r['cat'], r['flags'], r['item'],
        r['hp'], ', '.join(map(str, r['box'])), ', '.join(map(str, r['r'])), r['pool'], r['wall'], r['death'],
        r['next'], i, r['comment']))
c.append('};')
for si, evs in enumerate(sections):
    c.append('static const SpawnEvent sec%d[%d] = {' % (si + 1, max(1, len(evs))))
    for i, (k, f, n, a, cm) in enumerate(evs):
        c.append('    {%d, %d, %d, %d},  /* %d %s */' % (k, n, f, a, i, cm))
    if not evs:
        c.append('    {0, 0, 0, 0},')
    c.append('};')
c.append('const u16 en_spawn_objs[%d] = {%s};' % (max(1, len(spawn_objs)), ', '.join(map(str, spawn_objs)) or '0'))
c.append('const SpawnSection en_spawn_sections[%d] = {' % len(sections))
c += ['    {%d, sec%d},' % (len(evs), i + 1) for i, evs in enumerate(sections)]
c.append('};')
fn = sorted(set(impl[a] for a in natives if a in impl))
c += ['void %s(struct Enemy *e);' % f for f in fn]
c.append('void en_native_missing(struct Enemy *e);')
c.append('const EnemyFn en_ai_table[AI_COUNT] = {')
c.append('    en_native_missing,')
for a, i in sorted(natives.items(), key=lambda kv: kv[1]):
    c.append('    %s,  /* %d $%04X */' % (impl.get(a, 'en_native_missing'), i, a))
c.append('};')
c.append('const u16 en_bullet_dirs[4][32] = {')
for spd in (3, 4, 5, 6):
    c.append('    {%s},' % ', '.join(map(str, bullet_dirs[spd])))
c.append('};')
c.append('const u8 en_aim_table[64] = {%s};' % ', '.join(map(str, aim_table)))
c.append('const u32 en_score_points[15] = {%s};' % ', '.join(map(str, score_points)))
c.append('const u16 en_letter_inits[12] = {%s};' % ', '.join(map(str, letter_init)))
c.append('const TemplateRef en_templates[%d] = {%s};' % (len(all_tpl), ', '.join('{%d, %d}' % kv for kv in sorted(all_tpl.items()))))
c.append('const u16 en_template_count = %d;' % len(all_tpl))
rf = sorted((r, si, ix) for (r, _), (si, ix) in routine_first.items())
c.append('const RoutineRef en_routines[%d] = {%s};' % (len(rf), ', '.join('{%d, %d, 0, %d}' % v for v in rf)))
c.append('const u16 en_routine_count = %d;' % len(rf))
c.append('const u8 en_eye_formations[3][8][10] = {')
for sets in eye_pos:
    c.append('    {%s},' % ', '.join('{%s}' % ', '.join(map(str, v)) for v in sets))
c.append('};')
c.append('const PowForm en_pow_chain[%d] = {' % len(pow_rows))
for r in pow_rows:
    c.append('    {%d, %d, %d, %d},  /* handler $%04X settle $%04X */' % (r['trans'], r['idle'], r['item'], r['hp'], r['handler'], r['settle']))
c.append('};')
for (a, n), v in sorted(mottab.items()):
    c.append('const u16 MOTTAB_%04X_%d[%d] = {%s};' % (a, n, n, ', '.join(map(str, v))))
for (a, n), v in sorted(motptr.items()):
    c.append('const u16 MOTPTR_%04X_%d[%d] = {%s};' % (a, n, n, ', '.join(map(str, v))))
for (a, n) in sorted(set(want_romb)):
    c.append('const u8 ROMB_%04X_%d[%d] = {%s};' % (a, n, n, ', '.join(str(rd(a + i)) for i in range(n))))
(ROOT / 'src/gen/enemy_data.c').write_text('\n'.join(c) + '\n')
print('enemies: %d steps, %d inits, %d natives (%d without C code), spawns %s' % (
    len(steps), len(inits), len(natives), len(missing), [len(s) for s in sections]))
if '-v' in sys.argv and missing:
    print('missing natives:', ' '.join('%04X' % a for a in missing))
