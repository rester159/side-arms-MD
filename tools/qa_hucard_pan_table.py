#!/usr/bin/env python3
"""Check linked HuCard pan data against the original two-side calculation."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rom = (ROOT / 'out/release/rom.bin').read_bytes()
    symbols = [(int(parts[0], 16), parts[2])
               for line in (ROOT / 'out/release/symbol.txt').read_text().splitlines()
               if len(parts := line.split()) >= 3]
    addresses = [address for address, name in symbols
                 if name == 'pan_info' or name.startswith('pan_info.')]
    assert len(addresses) == 1, 'Expected one linked pan table'
    table = struct.unpack_from('>256H', rom, addresses[0])
    source_levels = (0, 3, 5, 7, 9, 11, 13, 15, 16, 19, 21, 23, 25, 27, 29, 31)
    cases = 0
    for pan, packed in enumerate(table):
        left, right = source_levels[pan >> 4], source_levels[pan & 15]
        assert packed >> 8 == (128 if left else 0) | (64 if right else 0), pan
        assert packed & 255 == max(left, right), pan
        for volume in range(32):
            expected = 2 * ((31 - volume) + (31 - max(left, right)))
            actual = 2 * (62 - volume - (packed & 31))
            assert actual == expected, (pan, volume)
            cases += 1
    result = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
                  pan_entries=256, volume_pan_cases=cases,
                  scope='Linked stereo bits and attenuation for every valid volume/pan pair; packet and native audio checks are separate.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
