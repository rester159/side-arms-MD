#!/usr/bin/env python3
"""Preserve the five PCE player-death poses from position-verified live SAT entries."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from qa_bc_player_flow import state

ROOT = Path(__file__).resolve().parents[1]
capture = ROOT / '.local/pce-reference/player-death-art-sequence'
poses = (0xb500, 0xb680, 0xb800, 0xb980, 0xbb00)
found = {}
for path in sorted(capture.glob('*-ram.bin')):
    ram = path.read_bytes()
    player = state(ram)
    if player.body_frame not in poses:
        continue
    raw = {kind: path.with_name(path.name.replace('-ram', '-' + kind)).read_bytes()
           for kind in ('sat', 'vram', 'palette')}
    sat = struct.unpack('<256H', raw['sat'])
    for slot in range(64):
        y, x, pattern, attributes = sat[slot * 4:slot * 4 + 4]
        if (attributes != player.attributes or
            (x - 16, y - 48) != (player.world.x >> 8, player.world.y >> 8)):
            continue
        assert attributes == 0x1181, 'Expected unflipped 32x32 player death sprite'
        vram = struct.unpack('<32768H', raw['vram'])
        palette = struct.unpack('<512H', raw['palette'])
        base = pattern >> 1
        rows = [''.join(format(sum(((vram[(base + (y // 16) * 2 + x // 16) * 64
                       + y % 16 + plane * 16] >> (15 - x % 16)) & 1) << plane
                       for plane in range(4)), 'x') for x in range(32)) for y in range(32)]
        raw['ram'] = ram
        # Prefer the last visible sample of each pose, after its DMA settled.
        found[player.body_frame] = dict(
            id=f'player-death-{player.body_frame:04x}', source_pose=player.body_frame,
            size=32, source_palette=1, rows=rows,
            colors=[[word >> 3 & 7, word >> 6 & 7, word & 7]
                    for word in palette[272:288]],
            source_capture=capture.name, source_frame=int(path.name[1:7]),
            sat_slot=slot, sat_pattern=pattern, sat_attributes=attributes,
            player_position_verified=True,
            source_hashes={kind: hashlib.sha256(data).hexdigest() for kind, data in raw.items()})
        break
assert set(found) == set(poses), ('Missing live death poses', set(poses) - set(found))
document = json.dumps(dict(schema=1, shapes=[found[pose] for pose in poses]), indent=2) + '\n'
destination = ROOT / 'tools/data/bc_player_death_shapes.json'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--check', action='store_true')
args = parser.parse_args()
if args.check:
    assert destination.read_text() == document
else:
    destination.write_text(document)
print('Five live PCE player-death poses, matched to player position and SAT attributes')
