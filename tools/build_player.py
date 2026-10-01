#!/usr/bin/env python3
"""Native player / weapon tables from the extracted arcade data (docs/re/flow_player.md, docs/player.md).

Inputs: res/generated/player.json (tools/extract_player.py) for the shot spawn records, BIT orbit,
death animation and bonus-life tables; the ROM set (hash-checked, tools/arcade_source.py) for the few
tables the extractor does not export (full 16-entry movement tables, the P2-led combined-robot ring
B2:$92FF/$933F, the partner explosion list $34F0).
Outputs (ignored by VCS): src/gen/player_data.c, inc/gen/player_data.h.

Shot records become `ShotRec` structs: sprite code (attr code bits 8-10 folded in), colour, spawn
offset relative to the 32x32 body, velocity in px/frame, and hit box half sizes in PIXELS (the arcade
stores the half width in x/2 units, B2:$938F + collision $2500, so it is doubled here).
"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT

GEN = ROOT / 'res/generated'
SRC = ROOT / 'src/gen'; INC = ROOT / 'inc/gen'
for d in (SRC, INC):
    d.mkdir(parents=True, exist_ok=True)
pj = json.loads((GEN / 'player.json').read_text())
M = Source().region('maincpu')


def bk(bank, a, n):
    o = 0x8000 + bank * 0x4000 + (a - 0x8000)
    return M[o:o + n]


def s8(v):
    return v - 256 if v > 127 else v


def rom_rec(a):
    r = bk(2, a, 8)
    return dict(rom=f'B2:${a:04X}', code=r[0], attr=r[1], color=r[1] & 15, code_hi=(r[1] >> 5) & 7,
                dy=s8(r[2]), dx=s8(r[3]), vy=s8(r[4]), vx=s8(r[5]), hit_half_h=r[6], hit_half_w=r[7])


def check(rec):
    """Cross-check a JSON record against the ROM bytes it cites."""
    a = int(rec['rom'].split('$')[1], 16)
    r = rom_rec(a)
    for k in ('code', 'attr', 'dy', 'dx', 'vy', 'vx', 'hit_half_h', 'hit_half_w'):
        assert r[k] == rec[k], (rec['rom'], k, r[k], rec[k])
    return rec


def c_rec(r):
    code = r['code'] | (r.get('code_hi', 0) << 8)
    return (f"{{0x{code:03X}, {r['color']}, {r['dy']}, {r['dx']}, {r['vy']}, {r['vx']}, "
            f"{r['hit_half_w'] * 2}, {r['hit_half_h']}}}")


S = pj['shots']
tables = []   # (c name, dims, rows (list or list of lists), comment)


def table1(name, recs, comment):
    tables.append((name, f'[{len(recs)}]', [c_rec(check(r)) for r in recs], comment))


def table2(name, left, right, comment):
    assert len(left) == len(right)
    tables.append((name, f'[2][{len(left)}]',
                   ['{' + ', '.join(c_rec(check(r)) for r in side) + '}' for side in (left, right)], comment))


# index 0 = facing left (arcade $6C, button 1), 1 = facing right ($72, button 2)
table1('SR_NORMAL', S['normal_left_right'], 'B2:$90DF/$90E7 normal shot')
table1('SR_BIT', S['bit_shot_left_right'], 'B2:$90EF/$90F7 shot fired from each BIT orbiter')
table1('SR_BIT_NORMAL', S['bit_mode_normal_left_right'], 'B2:$90FF/$9107 normal shot while BIT is selected')
table2('SR_SG1', S['sg_l1_left'], S['sg_l1_right'], 'B2:$910F-$913F S.G. level 1 (3 pellets)')
table2('SR_SG2', S['sg_l2_left'], S['sg_l2_right'], 'B2:$913F-$918F S.G. level 2 (5 pellets)')
table2('SR_SG3', S['sg_l3_left'], S['sg_l3_right'], 'B2:$918F-$91FF S.G. level 3 (7 pellets)')
table1('SR_MBL', S['mbl_left_right'], 'B2:$91FF/$9207 M.B.L. head record (body = code+1, tail = code+2)')
table2('SR_3WAY', S['3way_left'], S['3way_right'], 'B2:$920F/$9227 3WAY volley')
table1('SR_AUTO10', S['auto10_left_right'], 'B2:$923F/$9247 AUTO $10 rapid shot')
table2('SR_AUTO11', S['auto11_left'], S['auto11_right'], 'B2:$924F/$9267 AUTO $11 up/forward/down')
# combined robot rings: P1-led linear ring (JSON), P2-led boomerang ring (ROM only)
table2('SR_RING_P1', S['combined_a'], S['combined_b'], 'B2:$927F/$92BF P1-led robot ring, patterns A/B')
ring_p2 = [[rom_rec(0x92FF + 8 * i) for i in range(8)], [rom_rec(0x933F + 8 * i) for i in range(8)]]
table2('SR_RING_P2', ring_p2[0], ring_p2[1], 'B2:$92FF/$933F P2-led robot boomerang ring, patterns A/B')

# movement: 16 entries (joystick nibble b0 R, b1 L, b2 D, b3 U) x (dy, dx); cross-check with JSON
mv = []
for key, a in (('speed1', 0x864C), ('speed2', 0x866C), ('speed3', 0x868C), ('combined_robot', 0x86AC)):
    raw = bk(2, a, 32)
    rows = [(s8(raw[2 * i]), s8(raw[2 * i + 1])) for i in range(16)]
    for name, idx in (('R', 1), ('L', 2), ('D', 4), ('DR', 5), ('DL', 6), ('U', 8), ('UR', 9), ('UL', 10)):
        assert list(rows[idx]) == pj['movement'][key][name], (key, name)
    mv.append((key, a, rows))

orbit = pj['bit_orbit']
assert len(orbit['steps']) == 32
assert M[0x1F56 + 96] == 0x80                            # path terminator ($85F6 wraps on $80)
st = orbit['start_index']
death = pj['death_anim']['frames']
assert len(death) == 8 and all(f['frames'] == 5 for f in death)
# $34F0: partner-without-lives explosion when the robot splits (list after a skipped byte, $FF end)
pexp = []
a = 0x34F1
while M[a] != 0xFF:
    pexp.append(M[a]); a += 1
ext = pj['extend_tables']
EXT = [ext[f'dsw_index{i}']['scores'] for i in range(4)]

c = ['/* Generated by tools/build_player.py from the extracted arcade data. Do not edit. */',
     '#include "gen/player_data.h"', '']
for name, dims, rows, comment in tables:
    c.append(f'/* {comment} */')
    c.append(f'const ShotRec {name}{dims} = {{')
    c += [f'    {r},' for r in rows]
    c.append('};')
c.append('/* B2:$864C/$866C/$868C speed 1-3, B2:$86AC combined robot: (dy, dx) by joystick nibble */')
c.append('const s8 MOVE_TABLE[4][16][2] = {')
for key, a, rows in mv:
    c.append('    {' + ', '.join(f'{{{dy}, {dx}}}' for dy, dx in rows) + f'}},   /* {key} B2:${a:04X} */')
c.append('};')
c.append('/* $1F56: BIT orbit, 32 steps (dy, dx from the body (y, x+16), sprite code), 1 step per frame */')
c.append('const BitStep BIT_PATH[32] = {')
c.append('    ' + ', '.join(f'{{{dy}, {dx}, 0x{code:02X}}}' for dy, dx, code in orbit['steps']))
c.append('};')
c.append(f"const u8 BIT_START_L2 = {st['bit2_level2']}, BIT_START_L3[2] = {{{st['bit2_level3']}, {st['bit3_level3']}}};  /* $1F26 */")
c.append('/* $23AD: death animation, 32x32 composites, colour 8, 5 frames each */')
c.append('const u16 DEATH_CODES[8] = {' + ', '.join(f"0x{f['code'] | ((f['attr'] >> 5) << 8):03X}" for f in death) + '};')
c.append('/* $34F0: robot partner without lives explodes on split, 32x32 colour 8, 6 frames each */')
c.append(f'const u16 PARTNER_EXPLODE[{len(pexp)}] = {{' + ', '.join(f'0x{0x100 | v:03X}' for v in pexp) + '};')
c.append('/* $09F7/$0A07/$0A37/$0A5F bonus-life scores by DSW0 bits 4-5 (index 0 = MAME default); 0xFFFFFFFF ends */')
c.append('const u32 *const EXTEND_TABLES[4] = {')
for i, t in enumerate(EXT):
    c.append(f"    (const u32[]){{{', '.join(str(v) for v in t)}, 0xFFFFFFFF}},")
c.append('};')
(SRC / 'player_data.c').write_text('\n'.join(c) + '\n')

h = ['/* Generated by tools/build_player.py. Do not edit. */', '#pragma once', '#include <genesis.h>', '',
     '/* Shot spawn record (arcade B2:$938F): sprite code, colour, spawn offset from the body top-left,',
     ' * velocity px/frame, hit box half sizes in pixels (half_w = arcade x/2 units * 2). */',
     'typedef struct { u16 code; u8 colour; s8 dy, dx, vy, vx; u8 half_w, half_h; } ShotRec;',
     'typedef struct { s8 dy, dx; u8 code; } BitStep;', '']
for name, dims, rows, comment in tables:
    h.append(f'extern const ShotRec {name}{dims};')
h += ['extern const s8 MOVE_TABLE[4][16][2];', 'extern const BitStep BIT_PATH[32];',
      'extern const u8 BIT_START_L2, BIT_START_L3[2];', 'extern const u16 DEATH_CODES[8];',
      f'#define PARTNER_EXPLODE_N {len(pexp)}', f'extern const u16 PARTNER_EXPLODE[{len(pexp)}];',
      'extern const u32 *const EXTEND_TABLES[4];']
(INC / 'player_data.h').write_text('\n'.join(h) + '\n')
# Every (code, colour) the native player module can draw, for the sprite pattern bank
# (tools/build_assets.py expands each entry to the 2x2 cells c, c+1, c+8, c+9).
uses = set()
def big(code, col):
    uses.add((code & 0x7FF, col))
for off, col in ((0, 0), (0x80, 4)):                       # P1 / P2 bodies
    for c in (0x20, 0x22):
        for pose in (0, 0x10, 0x20, 0x30):
            big(c + pose + off, col); big(c + pose + 4 + off, col)
    for c in (0x62, 0x66, 0x72, 0x76):                     # entry glide, -2/-4 facing left
        for d in (0, 2, 4):
            big(c - d + off, col)
    for c in range(4, 8):                                  # M.B.L. launcher
        uses.add((c + off, col))
for c in range(0x0C, 0x10):                                # BIT orbiters
    uses.add((c, 3))
for key in ('normal_left_right', 'bit_shot_left_right', 'bit_mode_normal_left_right', 'sg_l1_left', 'sg_l1_right',
            'sg_l2_left', 'sg_l2_right', 'sg_l3_left', 'sg_l3_right', '3way_left', '3way_right', 'auto10_left_right',
            'auto11_left', 'auto11_right', 'combined_a', 'combined_b'):
    for r in S[key]:
        uses.add((r['code'] | r['code_hi'] << 8, r['color']))
for r in S['mbl_left_right']:
    for d in (0, 1, 2):
        uses.add((r['code'] + d, 8))
for c in list(range(0x18, 0x1C)) + [0x80, 0x81, 0x82]:     # 3WAY lv2 cycle, S.G. burst
    uses.add((c, 8))
for c in range(0x18, 0x1F):                                # explosions (+ 3WAY lv2 quirk)
    uses.add((c, 5))
for c in list(range(0x198, 0x1A0)) + [0x80, 0x81, 0x82]:   # P2-led boomerang ring + burst
    uses.add((c, 7))
for base in (0x140, 0x180):                                # robot merge, body, flash; partner row
    for d in (0, 2, 4, 6, 0x20, 0x22):
        big(base + d, 0); big(base + d + 16, 0)
for f in death:
    big(f['code'] | ((f['attr'] >> 5) << 8), 8)
(GEN / 'player_sprites.json').write_text(json.dumps(
    {'_doc': 'Generated by tools/build_player.py: (code, colour) pairs drawn by the player module',
     'uses': [{'code': c, 'color': col} for c, col in sorted(uses)]}, indent=0))
print('player:', len(tables), 'shot tables,', len(uses), 'sprite uses')
