#!/usr/bin/env python3
"""Exercise emulated controller protocols without the logical pad override.

Run each adapter in a separate process. This verifies SGDK detection and slot
routing through Genesis Plus GX, not electrical compatibility on real hardware.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
from run_rom import Runner, ROOT, CORE

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--adapter', choices=('teamplayer1', 'teamplayer2', 'wayplay'), required=True)
p.add_argument('--buttons', type=int, choices=(3, 6), default=6)
p.add_argument('--hold-at-boot', action='store_true', help='Hold Up on all four pads through startup')
p.add_argument('--other-port-empty', action='store_true', help='Team Player port 1 with no standalone pad on port 2')
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
r = Runner()
masks = [0] * 8
callback_type = C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint)

def input_state(port, device, index, button):
    if device != 1 or port >= len(masks):
        return 0
    return masks[port] if button == 256 else int(bool(masks[port] & (1 << button)))

callback = callback_type(input_state)
r.callbacks.append(callback)
r.lib.retro_set_input_state.argtypes = [callback_type]
r.lib.retro_set_input_state(callback)
pad_device = 257 if a.buttons == 3 else 513
team_device = 1537 if a.buttons == 3 else 1793
way_device = 1025 if a.buttons == 3 else 1281
devices = {'teamplayer1': (team_device, pad_device),
           'teamplayer2': (pad_device, team_device),
           'wayplay': (way_device, None)}[a.adapter]
if a.other_port_empty:
    assert a.adapter == 'teamplayer1'
    devices = (team_device, 0)
if a.adapter == 'teamplayer2':
    # GX configures Team Player pad types at physical indices 4..7, but its
    # input initializer consumes logical pad types 1..4 after a standalone
    # port-1 pad. Prime both groups via the public API before final wiring.
    r.lib.retro_set_controller_port_device(0, team_device)
for port, device in enumerate(devices):
    if device is not None:
        r.lib.retro_set_controller_port_device(port, device)
if a.hold_at_boot:
    masks[:4] = [1 << 4] * 4
r.run(4000)
if a.hold_at_boot:
    assert [r.u16('pad_raw', i * 4) for i in range(4)] == [1] * 4, 'Held startup buttons did not reach game'
    masks[:4] = [0] * 4
    r.run(10)
assert r.read('dbg_pad_override', 1) == b'\0'
assert list(r.read('pad_six', 4)) == [int(a.buttons == 6)] * 4, (a.adapter, list(r.read('pad_six', 4)))
buttons = [('UP', 4, 1), ('DOWN', 5, 2), ('LEFT', 6, 4), ('RIGHT', 7, 8),
           ('A', 1, 0x40), ('B', 0, 0x10), ('C', 8, 0x20), ('START', 3, 0x80)]
if a.buttons == 6:
    buttons += [('X', 10, 0x400), ('Y', 9, 0x200), ('Z', 11, 0x100)]
checked = []
for player in range(4):
    for name, bit, raw in buttons:
        masks[player] = 1 << bit
        r.run(5)
        held = [r.u16('pad_raw', i * 4) for i in range(4)]
        expected = [raw if i == player else 0 for i in range(4)]
        assert held == expected, (a.adapter, player, name, held, expected)
        masks[player] = 0
        r.run(5)
        assert all(r.u16('pad_raw', i * 4) == 0 for i in range(4)), ('release', player, name)
        checked.append(dict(player=player + 1, button=name))
assert r.read('dbg_pad_override', 1) == b'\0'
if a.hold_at_boot:
    masks[:4] = [1 << 4] * 4
    r.lib.retro_reset()
    r.run(4000)
    assert [r.u16('pad_raw', i * 4) for i in range(4)] == [1] * 4, 'Held reset buttons did not reach game'
    masks[:4] = [0] * 4
    r.run(10)
    assert all(r.u16('pad_raw', i * 4) == 0 for i in range(4))
report = dict(passed=True, adapter=a.adapter, buttons=a.buttons,
              hold_at_boot=a.hold_at_boot, other_port_empty=a.other_port_empty,
              held_reset_checked=a.hold_at_boot,
              rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),
              core_sha256=hashlib.sha256(CORE.read_bytes()).hexdigest(),
              checks=checked, logical_input_override=False,
              scope='Emulated protocol detection, per-player raw buttons and releases; not physical hardware.')
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(f'PASS {a.adapter} {a.buttons}-button: {len(checked)} isolated button/release checks')
