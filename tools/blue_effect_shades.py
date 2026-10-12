"""Shade mapping for Normal's blue explosions using existing PAL2/PAL3 pens.

The runtime emits disjoint layers only when SAT, cache and DMA space permit.
Source pen 15 stays transparent. No shared palette entries are changed.
"""

# Source palette 7 -> index in the concatenated Normal sprite palettes.
PENS = (7, 23, 23, 8, 21, 21, 8, 4, 14, 14, 9, 9, 20, 20, 14, 7)
EXPECTED = {7: (0, 0, 0), 23: (0, 0, 1), 8: (0, 2, 4),
            21: (0, 0, 7), 4: (0, 3, 5), 14: (7, 7, 7),
            9: (0, 4, 6), 20: (0, 6, 7)}


def header(palette):
    for pen, rgb in EXPECTED.items():
        word = palette[pen]
        assert ((word >> 1) & 7, (word >> 5) & 7, (word >> 9) & 7) == rgb, \
            f'Blue effect palette changed at pen {pen}; refit its shades'
    tables = []
    for bank in (1, 0):
        pens = [0 if n == 15 or value // 16 != bank else value % 16
                for n, value in enumerate(PENS)]
        tables.append([pens[b >> 4] * 16 + pens[b & 15] for b in range(256)])
    return ('static const u8 blue_pair_lut[2][256] = {\n'
            + ',\n'.join('{' + ','.join(hex(b) for b in row) + '}' for row in tables)
            + '\n};\n')
