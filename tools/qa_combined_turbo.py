#!/usr/bin/env python3
"""Check Home autofire mapping for the combined leader and the ring's held input.

Uses real controller input rather than dbg_pad_override, which bypasses mapping.
Run against the built cartridge with the same core as qa_itch_boot.py.
"""
from qa_soak import O
from run_rom import Runner, PAD
from enemy_trace import start_game

r = Runner()
start_game(r)
r.write('en_dbg_mute', [1])
r.write('pad_cfg', bytes([0, 1, 2, 1, 2, 8, 1, 1]))


def player(field, data):
    r.write('players', data, offset=O['o_Player_' + field])


player('in_play', [1])
player('state', (1).to_bytes(4, 'big'))
player('invuln', [255])
player('weapon', [0])


def sample(combined, weapon, button):
    r.write('combined', [combined])
    r.write('combined_hp', [2])
    player('weapon', [weapon])
    r.run(4)
    held = []
    for _ in range(24):
        player('invuln', [255])
        r.run(1, PAD[button])
        if 'pad_fire_held' in r.symbols:
            assert r.read('pad_fire_held', 1)[0] == (16 if button == 'A' else 32), 'ring lost held fire input'
        held.append(r.read('pad', 1)[0] & 48)
    return held


for button in ('A', 'B'):
    for combined in (0, 1):
        values = sample(combined, 0, button)
        assert 0 in values and any(values), 'normal weapon did not receive turbo pulses'
        assert sum(bool(b) and not bool(a) for a, b in zip(values, values[1:])) >= 3, 'turbo did not repeat'
    values = sample(1, 5, button)
    assert all(values), 'AUTO was interrupted by turbo'
    values = sample(2, 0, button)
    assert all(values), 'combined partner ring input was interrupted'

r.run(4)
assert r.read('pad_fire_held', 1)[0] == 0, 'released fire button remained held'
print('Combined turbo: leader repeats, AUTO and partner stay held, ring input preserved')
