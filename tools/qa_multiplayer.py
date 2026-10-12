#!/usr/bin/env python3
"""Home multiplayer regression, using the built ROM and Genesis Plus GX.
Run once per configuration: .venv/bin/python tools/qa_multiplayer.py --players 1|2|3|4
Exercises real menus and per-player flow; logical pad hook supplies extra pads.
"""
import argparse
import ctypes as C
from run_rom import Runner, PAD, ROOT
from qa_soak import O

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--players', type=int, choices=(1, 2, 3, 4), required=True)
a = ap.parse_args()
r = Runner()
out = ROOT / '.local/multiplayer-qa'
out.mkdir(parents=True, exist_ok=True)

def tap(b):
    r.run(5, PAD[b]); r.run(15)

def state():
    return r.u32('flow_state')

def logical(bits):
    for i in range(a.players):
        r.write("players", b"\xC8", i*O["s_Player"]+O["o_Player_invuln"])
    r.write('pad', bytes([bits, bits] * a.players + [0, 0] * (4-a.players)))
    r.run(1)

for i in range(4000):
    r.run(1)
    if state() == 0 and i > 2000:
        break
else:
    raise AssertionError('Boot did not reach mode select')
tap('DOWN'); tap('START')
assert state() == 9, ('Home screen', state())
# Opening/cancelling the dialog must preserve the saved count and mode screen.
tap('A')
assert state() == 9 and r.read('player_dialog', 1) == b'\x01'
tap('DOWN'); tap('B')
assert state() == 9 and r.read('home_cfg', 1, 5) == b'\x02'
tap('A')
for _ in range((a.players - 2) % 4): tap('DOWN')
r.capture(out / f'{a.players}p-options.png')
tap('A')
assert r.read('home_cfg', 1, 5) == bytes([a.players])
assert r.u16('player_limit') == a.players
r.write('dbg_pad_override', b'\x01')
for f in range(1100):
    logical(0x10 if f % 40 == 20 else 0)
assert state() == 7
# Every selected player starts together; input on unselected slots cannot join.
for i in range(a.players):
    assert r.read('players', 1, i*O['s_Player'] + O['o_Player_in_play']) == b'\x01', ('join', i)
for i in range(a.players, 4):
    assert r.read('players', 1, i*O['s_Player'] + O['o_Player_in_play']) == b'\x00'
assert r.u16('level', O['o_Level_tick']) > 0
assert r.u16('enemy_spawned') > 0, 'Normal must execute its wave timeline'
r.capture(out / f'{a.players}p-play.png')
# Four identical single-enemy records must produce exactly 4 / 6 / 9 enemies.
# Debug wave injection bypasses timeline mute, but exercises production scaling.
r.write('en_dbg_mute', b'\x01')
start = r.u16('enemy_spawned')
for _ in range(4):
    r.write('en_dbg_spawn', b'\x00\x01')
    for _ in range(10):
        logical(0)
        if not r.u16('en_dbg_spawn'): break
    assert not r.u16('en_dbg_spawn'), 'Spawn hook was not consumed'
expected = {1: 4, 2: 4, 3: 6, 4: 9}[a.players]
assert (r.u16('enemy_spawned') - start) & 65535 == expected, ('wave count', r.u16('enemy_spawned') - start)
# Exercise merge for the new robot pair and verify the other pair remains separate.
if a.players > 2:
    r.write('dbg_player_cmd', b'\x06', 2)
    for _ in range(360): logical(0)
    assert r.read('combined', 1) == b'\x03', ('merge', r.read('combined',1))
    assert r.read('players', 4, O['o_Player_state']) == b'\x00\x00\x00\x01'
    r.capture(out / f'{a.players}p-merged.png')
# Soft reset, then start Boss Rush through the Home menu.
logical(0xF0)
for _ in range(30): logical(0)
r.write('dbg_pad_override', b'\x00')
r.run(3)
assert state() == 0
# Selection remembers Home, as does its cursor (START GAME).
tap('START'); tap('DOWN'); tap('DOWN'); tap('A')
assert state() == 9 and r.read('player_dialog', 1) == b'\x01', 'Boss Rush must open player selection'
tap('B')
assert state() == 9 and r.read('player_dialog', 1) == b'\x00'
assert r.read('home_cfg', 1, 5) == bytes([a.players]), 'Cancel changed player count'
tap('A')
assert state() == 9 and r.read('player_dialog', 1) == b'\x01'
tap('A')
assert state() == 12, ('Boss Rush', state())
r.write('dbg_pad_override', b'\x01')
for f in range(500):
    logical(0)
    if r.read('boss_hud', 1) != b'\x00':
        break
else:
    raise AssertionError('Boss did not start')
# BossHud begins with bool active, u8 bars, u8 hits (inc/boss.h).
assert r.read('boss_hud', 1, 2) == bytes([{1:20,2:20,3:30,4:45}[a.players]]), r.read('boss_hud', 4)
assert all(r.read('players',1,i*O['s_Player']+O['o_Player_in_play']) == b'\x01' for i in range(a.players))
# Verify persistence, then migrate a valid version-3 settings block in place.
l = r.lib
l.retro_get_memory_data.argtypes = [C.c_uint]
l.retro_get_memory_data.restype = C.c_void_p
l.retro_get_memory_size.argtypes = [C.c_uint]
l.retro_get_memory_size.restype = C.c_size_t
n = l.retro_get_memory_size(0)
assert n >= 138
save = (C.c_ubyte * n).from_address(l.retro_get_memory_data(0))
logical_save = bytes(save)[1::2]  # Genesis SRAM is on odd addresses.
assert logical_save[:4] == b'SAR2'
assert logical_save[40] == 5 and logical_save[67] == a.players
l.retro_reset(); r.run(2600)
assert r.read('home_cfg', 1, 5) == bytes([a.players]), 'Saved player setting failed to reload'
old = bytearray(logical_save)
old[40] = 3
checksum = 0x5A
for b in old[40:67]:
    checksum = (((checksum << 1) | (checksum >> 7)) & 255) ^ b
old[67] = checksum
for i, b in enumerate(old): save[2*i+1] = b
l.retro_reset(); r.run(2600)
assert r.read('home_cfg', 1, 5) == b'\x02', 'Legacy save must default to two players'
assert r.read('home_cfg', 5) == bytes([3,3,0,1,3]), 'Legacy Home settings were not preserved'
print(f'PASS {a.players}P: joins, wave count {expected}, Boss Rush health, save/reload, v3 migration' + (', merge' if a.players > 2 else ''))
