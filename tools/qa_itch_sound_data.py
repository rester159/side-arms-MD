#!/usr/bin/env python3
"""Verify the music mix against source patches and unmodified baseline data."""
import argparse
import json
from pathlib import Path
from build_sound import mix_patch, GEN, PATCHES, MUSIC_TL
from sound_model import tpn

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--baseline', type=Path, required=True)
args = ap.parse_args()
# Explicit signal-output topology in operator numbering, independently mapped
# to register order S1,S3,S2,S4. Exercise clamping as well as ordinary levels.
carriers = ({4}, {4}, {4}, {4}, {2, 4}, {2, 3, 4}, {2, 3, 4}, {1, 2, 3, 4})
for alg, outputs in enumerate(carriers):
    for level in (0, 32, 112, 126, 127):
        raw = bytearray([level] * 26)
        raw[24] = alg
        mixed = mix_patch(raw)
        for i in range(26):
            slot = (1, 3, 2, 4)[i - 4] if 4 <= i < 8 else 0
            expected = min(127, level + MUSIC_TL) if slot in outputs else raw[i]
            assert mixed[i] == expected, (alg, level, i)
before = args.baseline.read_bytes()
after = (GEN / 'sound_z80.bin').read_bytes()
expected = bytearray(before)
patches = json.loads((GEN / 'sound.json').read_text())['patches']
for key, patch in patches.items():
    raw = bytes.fromhex(patch['raw'])
    offset = PATCHES + 32 * int(key, 16)
    assert before[offset:offset + 26] == raw
    expected[offset:offset + 26] = mix_patch(raw)
for base, multiplier in ((0xC000, 27), (0xE000, 29)):
    for period in range(4096):
        offset = base + 2 * period
        expected[offset:offset + 2] = tpn(period, multiplier).to_bytes(2, 'little')
assert after == expected, 'unexpected changes outside carrier levels and period tables'
print(f'PASS: {len(patches)} source patches; all 8 algorithms and saturation; 8192 period entries; music events/SFX unchanged')
