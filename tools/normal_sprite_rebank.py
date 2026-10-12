"""Restore the final red explosion ring using the existing dark-red palette."""
import hashlib
import json
import struct
from pathlib import Path


def apply(raw, small, small_index, large, large_index, palette):
    recipe = json.loads((Path(__file__).parent/'data/normal_sprite_rebank.json').read_text())
    assert hashlib.sha256(struct.pack('>32H', *palette)).hexdigest() == recipe['palette_sha256']
    for row in recipe['records']:
        size, key = row['size'], row['key']
        data, lookup = (small, small_index) if size == 16 else (large, large_index)
        entry = lookup[key]
        assert entry == row['before_entry']
        block = entry & 32767
        assert [k for k, v in enumerate(lookup) if v & 32767 == block] == [key]
        stride = size * size // 2
        start = (block - 1) * stride
        before = bytes(data[start:start + stride])
        assert hashlib.sha256(before).hexdigest() == row['before_sha256']
        code = key & 2047
        cells = [raw[(code + a)*128:(code + a + 1)*128]
                 for a in ((0,) if size == 16 else (0, 1, 8, 9))]
        if size == 16:
            source = cells[0]
        else:
            tl, tr, bl, br = cells
            source = bytearray()
            for x in range(4):
                top, bottom = (tl, bl) if x < 2 else (tr, br)
                half = (x & 1) * 64
                source += top[half:half + 64] + bottom[half:half + 64]
        lut = row['pen_lut']
        after = bytes((lut[b >> 4] << 4) | lut[b & 15] for b in source)
        assert hashlib.sha256(after).hexdigest() == row['after_sha256']
        for old, new in zip(before, after):
            assert (old >> 4 == 0) == (new >> 4 == 0)
            assert (old & 15 == 0) == (new & 15 == 0)
        data[start:start + stride] = after
        lookup[key] = row['after_entry']
    return recipe
