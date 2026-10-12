#!/usr/bin/env python3
"""Check multiplayer controller prediction in a synthetic fixture, not a campaign."""
import hashlib
import json
from run_rom import Runner, ROOT
from workload_metrics import WorkloadMetrics
from bc_pilot_lookahead import choose_move, machine_checkpoint

out = ROOT / '.local/bc-pilot-party'
out.mkdir(parents=True, exist_ok=True)
r = Runner()
r.run(2600)
for name, value in [('dbg_bc_native_players', 4), ('dbg_bc_native_start_round', 7),
                    ('dbg_bc_native_protect', 0), ('dbg_bc_native', 1)]:
    r.write(name, value.to_bytes(2, 'big'))
r.write('dbg_pad_override', b'\1')
r.run(300)
layout = WorkloadMetrics(r, 4)

def checkpoint():
    return dict(ram=hashlib.sha256(bytes(r.ram)).hexdigest(), **machine_checkpoint(r))

def state_address(i):
    base = r.symbols['player'] if i == 0 else r.u32('peers') + (i-1)*layout.o['bc_player_size']
    return base + layout.o['bc_state']

def set_state(i, value):
    r.ram[(state_address(i) & 65535) ^ 1] = value

# Synthetic active states allow every controller path to be exercised even if
# the warmup naturally loses a player. They are not campaign evidence.
for i in range(4):
    set_state(i, 0x80)
pads = bytes([0x21, 0x21, 0x22, 0x22, 0x24, 0x24, 0x28, 0x28])
before = checkpoint()
choose_move(r, layout, 0x21, 0, (128, 112), player_index=0, party_pads=pads)
assert checkpoint() == before
shadow = r._pilot_shadow
original_write = shadow.write
writes = []

def record_write(name, data, *args, **kwargs):
    if name == 'pad':
        writes.append(bytes(data))
    return original_write(name, data, *args, **kwargs)

shadow.write = record_write
checks = []
for horizon in (4, 12):
    for i in range(4):
        writes.clear()
        before = checkpoint()
        chosen = choose_move(r, layout, pads[2*i], 0, (128, 112), player_index=i, party_pads=pads, horizon=horizon)
        assert checkpoint() == before, ('live machine changed', i)
        assert writes, ('no active prediction', i)
        for written in writes:
            for j in range(4):
                if j != i:
                    assert written[2*j] == pads[2*j], (i, j, 'peer held input')
                    assert written[2*j+1] in (pads[2*j+1], 0), (i, j, 'peer edges')
        active_writes = len(writes)
        set_state(i, 0x40)
        writes.clear()
        before = checkpoint()
        assert choose_move(r, layout, pads[2*i], 0, (128, 112), player_index=i, party_pads=pads, horizon=horizon) == pads[2*i]
        assert not writes and checkpoint() == before, ('inactive peer was simulated', i)
        set_state(i, 0x80)
        checks.append(dict(player=i+1, horizon=horizon, chosen=chosen, active_pad_writes=active_writes))

result = dict(rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),
              checks=checks, live_ram_cpu_vram_pixels_unchanged=True,
              peer_inputs_preserved=True, selected_peer_state_checked=True,
              scope='Synthetic four-player predictor fixture; no campaign or speed claim')
(out/'verified.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
