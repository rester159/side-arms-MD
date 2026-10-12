#!/usr/bin/env python3
"""Verify that the linked surfacer strip retains every source pen and flip."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from arcade_source import ROOT
from bc_background_equivalence import symbols


def decode(data, height):
    columns = np.frombuffer(data, np.uint8).reshape(4, height // 8, 8, 4)
    pixels = np.stack((columns >> 4, columns & 15), -1)
    return pixels.reshape(4, height, 8).transpose(1, 0, 2).reshape(height, 32)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    rom = (ROOT / 'out/release/rom.bin').read_bytes()
    sy = symbols(ROOT / 'out/release/symbol.txt')
    block = struct.unpack_from('>H', rom, sy['spr_big_index'] + 0x250 * 2)[0] & 32767
    assert block, 'Missing original surfacer pose'
    start = sy['spr_big'] + (block - 1) * 512
    original = decode(rom[start:start + 512], 32)
    start = sy['bc_surfacer_strip']
    strip = decode(rom[start:start + 256], 16)
    for flip in range(4):
        expected = original[::-1] if flip & 2 else original
        actual = strip[::-1] if flip & 2 else strip
        if flip & 1:
            expected, actual = expected[:, ::-1], actual[:, ::-1]
        placed = np.zeros((32, 32), np.uint8)
        placed[8:24] = actual
        assert np.array_equal(expected, placed), f'Changed source pens for flip {flip}'
    result = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
                  four_flip_variants_exact=True, original_bytes=512, packed_bytes=256,
                  scope='Linked pattern pens and centered placement; runtime cache and timing checked separately.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
