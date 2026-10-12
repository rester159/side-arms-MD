#!/usr/bin/env python3
"""Verify optional fire forecasts against actual shadow-core pad writes.
Synthetic fixture only: never evidence of natural campaign completion.
"""
import hashlib
import json
from run_rom import ROOT, Runner
from workload_metrics import WorkloadMetrics
from bc_pilot_lookahead import choose_move, machine_checkpoint

out = ROOT / '.local/bc-pilot-fire'
out.mkdir(exist_ok=True)
r = Runner()
r.run(2600)
for name, value in [('dbg_bc_native_players', 4), ('dbg_bc_native_start_round', 7),
                    ('dbg_bc_native_protect', 0), ('dbg_bc_native', 1)]:
    r.write(name, value.to_bytes(2, 'big'))
r.write('dbg_pad_override', b'\1')
r.run(300)
layout = WorkloadMetrics(r, 4)
sides = (0x20, 0x10, 0x20, 0x10)
directions = (1, 2, 4, 8)

def fingerprint():
    return dict(ram=hashlib.sha256(bytes(r.ram)).hexdigest(), **machine_checkpoint(r))

def active():
    for i in range(4):
        base = r.symbols['player'] if i == 0 else r.u32('peers') + (i-1)*layout.o['bc_player_size']
        for offset, value in ((layout.o['bc_state'], 0x80), (layout.o['bc_invulnerability'], 200)):
            r.ram[((base+offset)&65535)^1] = value

# Initialize the separate shadow core using the unchanged default forecast.
active()
pads = bytes([0x21, 0x21, 0x12, 0x12, 0x24, 0x24, 0x18, 0x18])
before = fingerprint()
choose_move(r, layout, 0x21, 0, (128, 112), party_pads=pads)
assert fingerprint() == before
shadow = r._pilot_shadow
original_write = shadow.write
writes = []
def record(name, data, *args, **kwargs):
    if name == 'pad':
        writes.append((shadow.u32('dbg_bc_native_ticks'), bytes(data)))
    return original_write(name, data, *args, **kwargs)
shadow.write = record
checks = []
for phase in range(6):
    while r.u32('dbg_bc_native_ticks') % 6 != phase:
        r.run(1)
    active()
    tick = r.u32('dbg_bc_native_ticks')
    held = [directions[i] | (sides[i] if phase < 3 else 0) for i in range(4)]
    pads = bytes(v for h in held for v in (h, h))
    for player in range(4):
        writes.clear()
        before = fingerprint()
        chosen = choose_move(r, layout, held[player], 0, (128, 112), horizon=12,
                             player_index=player, party_pads=pads, rapid_fire_sides=sides)
        assert chosen & 0x30 == held[player] & 0x30, 'Selected input changed first-action fire'
        assert fingerprint() == before, 'Authoritative machine changed'
        assert writes and writes[0][0] == tick
        prior = None
        phases = set()
        for at, data in writes:
            if at == tick:
                prior = None
            phases.add(at % 6)
            for peer in range(4):
                expected_fire = (held[peer] & 0x30) if prior is None else (sides[peer] if at % 6 < 3 else 0)
                assert data[peer*2] & 0x30 == expected_fire, (phase, player, at, peer, 'fire')
                if peer != player:
                    assert data[peer*2] & 15 == directions[peer], 'Peer movement changed'
                expected_edge = data[peer*2] if prior is None else data[peer*2] & ~prior[peer*2]
                assert data[peer*2+1] == expected_edge, (phase, player, at, peer, 'edge')
            prior = data
        assert phases == set(range(6)), (phase, player, phases)
        checks.append(dict(phase=phase, player=player+1, chosen=chosen, pad_writes=len(writes)))
result = dict(rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),
              checks=checks, live_ram_cpu_vram_pixels_unchanged=True,
              first_update_edges_preserved=True, future_fire_and_edges_match=True,
              scope='Synthetic shadow-core input forecast; no gameplay, survival or speed claim')
(out/'verified.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result, indent=2))
