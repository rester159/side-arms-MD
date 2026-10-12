"""Recover exact Normal source shades in unused pens without changing BC patterns."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def apply(raw, colors, small, small_index, large, large_index, palette_words):
    recipe = json.loads((ROOT/'tools/data/normal_sprite_shade_repairs.json').read_text())
    for bank, (r, g, b) in enumerate(recipe['colors']):
        assert palette_words[bank*16+15] == 0
        palette_words[bank*16+15] = r*2 + g*32 + b*512
    for repair in recipe['repairs']:
        size = repair['size']; stride = size*size//2
        data, lookup = (small, small_index) if size == 16 else (large, large_index)
        entries = {lookup[key] for key in repair['keys']}
        assert len(entries) == 1
        entry = entries.pop(); block = entry & 32767
        assert block and entry >> 15 == repair['bank']
        # A new alias must be reviewed rather than accidentally acquiring this repair.
        assert {k for k, v in enumerate(lookup) if v & 32767 == block} == set(repair['keys'])
        start = (block-1)*stride; before = bytes(data[start:start+stride])
        assert hashlib.sha256(before).hexdigest() == repair['before_sha256']
        proposals = []
        for key in repair['keys']:
            code, color = key & 2047, key >> 11
            cells = [raw[((code+a)&2047)*128:((code+a)&2047)*128+128]
                     for a in ((0,) if size == 16 else (0, 1, 8, 9))]
            if size == 16:
                source = cells[0]
            else:
                tl, tr, bl, br = cells; source = bytearray()
                for x in range(4):
                    top, bottom = (tl, bl) if x < 2 else (tr, br); half = (x & 1)*64
                    source += top[half:half+64] + bottom[half:half+64]
            after = bytearray(before); restored = 0
            for i, byte in enumerate(source):
                for shift in (4, 0):
                    pen = (byte >> shift) & 15
                    if pen != 15 and list(colors[512+color*16+pen]) == repair['rgb3']:
                        assert ((before[i] >> shift) & 15) not in (0, 15)
                        after[i] = (after[i] & ~(15 << shift)) | (15 << shift)
                        restored += 1
            assert restored == repair['restored_pixels']
            assert hashlib.sha256(after).hexdigest() == repair['after_sha256']
            proposals.append(after)
        assert all(proposals[0] == other for other in proposals)
        data[start:start+stride] = proposals[0]
    return recipe
