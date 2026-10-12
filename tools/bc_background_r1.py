"""Author R1 ledge quadrants from existing Genesis stone and rock materials.

The contour is new Genesis artwork based on the reviewed source composition;
it is not an identity match to a Normal metatile or imported PCE pixel data.
The stone texture uses its original Normal source pens before palette fitting;
rock materials and checked-in contours retain their existing geometry.
"""
import json
from pathlib import Path


def _decode_meta(tiles, meta):
    result = [[0] * 32 for _ in range(32)]
    for y in range(32):
        for x in range(32):
            tile = (y // 8) * 4 + x // 8
            byte = tiles[meta * 512 + tile * 32 + (y % 8) * 4 + x % 8 // 2]
            result[y][x] = (byte >> 4) if x % 2 == 0 else (byte & 15)
    return result


def _inside(x, y, points):
    """Even/odd polygon fill at pixel centers, using integer arithmetic."""
    x, y = x * 2 + 1, y * 2 + 1
    inside = False
    ax, ay = points[-1]
    ax, ay = ax * 2, ay * 2
    for bx, by in points:
        bx, by = bx * 2, by * 2
        if (ay > y) != (by > y):
            dy = by - ay
            left = (x - ax) * dy
            right = (bx - ax) * (y - ay)
            crosses = (left < right) if dy > 0 else (left > right)
            if crosses:
                inside = not inside
        ax, ay = bx, by
    return inside


def author_ledge_family(tiles, attrs):
    data = json.loads((Path(__file__).parent / 'data/bc_background_r1_contours.json').read_text())
    assert data['strip_size'] == [96, 32]
    from arcade_source import Source, decode_bgtiles
    source = data['stone_source']
    stone = decode_bgtiles(Source().region('bgtiles'))[source['code']]
    levels = {pen: level for level, pen in enumerate(source['pens'])}
    assert set(map(int, stone.ravel())) == set(levels)
    rock = _decode_meta(tiles, 79)
    # Both source materials and every destination tile use unchanged PAL1 and
    # priority. Never silently reinterpret another material's palette bank.
    for meta in (34, 79):
        assert all((word & 0xe000) == 0xa000 for word in attrs[meta * 16:(meta + 1) * 16])

    # The 96x32 authoring strip represents 20,21,and22.
    # It is never emitted as a new layout: crops preserve the proven half-cell
    # identity of 3A and3B, including the asymmetric right end of3B.
    base_ramp = data['stone_base_ramp']
    strip = [[base_ramp[levels[int(stone[y][x % 32])]]
              for x in range(96)] for y in range(32)]
    for layer in data['stone_relief']:
        ramp = layer['ramp']
        for y in range(32):
            for x in range(96):
                if _inside(x, y, layer['points']):
                    # Preserve all four original texture levels in each
                    # relief ramp instead of merging the lightest pair.
                    strip[y][x] = ramp[levels[int(stone[y][x % 32])]]

    outline = data['warm_outline']
    for y in range(32):
        for x in range(96):
            if not _inside(x, y, outline):
                continue
            pen = 2  # Existing deep rock crevice, also the nodule separation.
            for nodule in data['nodules']:
                if _inside(x, y, nodule['points']):
                    # Existing lower-half rock texture with an authored raised
                    # contour. No source-console pixels or pen tables enter.
                    material = rock[16 + (y + nodule['texture_shift'][1]) % 16][(x + nodule['texture_shift'][0]) % 32]
                    pen = {2: 1, 12: 12, 13: 13}.get(material, 12)
                    if _inside(x, y, nodule['highlight']):
                        pen = 14 if material == 13 else 13
                    break
            strip[y][x] = pen

    # The source22 right quadrants are identical to20 left quadrants.
    for y in range(32):
        strip[y][80:96] = strip[y][0:16]

    result = {}
    for cell, left in data['cell_crops'].items():
        cell = int(cell, 16)
        raw = bytearray()
        for ty in range(4):
            for tx in range(4):
                for y in range(8):
                    for x in range(0, 8, 2):
                        row = strip[ty * 8 + y]
                        sx = left + tx * 8 + x
                        raw.append((row[sx] << 4) | row[sx + 1])
        result[cell] = bytes(raw)
    return result


def replace_r1_ledge_family(tiles, attrs, packed, templates):
    for cell, pixels in author_ledge_family(tiles, attrs).items():
        start = cell * 16
        assert all((word & 0xe000) == 0xa000 for word in templates[start:start + 16])
        packed[cell * 512:(cell + 1) * 512] = pixels
        # Existing tile attributes are deliberately untouched, including PAL1,
        # priority, local tile order, and the source cell/remap contract.
