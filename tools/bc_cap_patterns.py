"""Precompose identical BC turret caps without changing their indexed pixels."""


def generate(cap):
    assert len(cap) == 128, 'Expected one column-major 16x16 cap'

    def pen(x, y):
        at = (x // 8) * 64 + (y // 8) * 32 + (y % 8) * 4 + (x % 8) // 2
        return (cap[at] >> (0 if x & 1 else 4)) & 15

    offsets, patterns = [], bytearray()
    for dx in range(-15, 16):
        for flipped in range(2):
            left = min(0, dx)
            width = (abs(dx) + 23) // 8 * 8
            pixels = [[0] * width for _ in range(16)]
            for origin in (0, dx):
                for y in range(16):
                    for x in range(16):
                        target = origin - left + x
                        if not pixels[y][target]:
                            pixels[y][target] = pen(15 - x if flipped else x, y)
            offsets.append(len(patterns))
            for x in range(0, width, 8):
                for y in (0, 8):
                    for row in range(y, y + 8):
                        for col in range(x, x + 8, 2):
                            patterns.append(pixels[row][col] << 4 | pixels[row][col + 1])
    assert len(offsets) == 62 and len(patterns) == 13568
    return offsets, bytes(patterns)


def header(cap):
    offsets, data = generate(cap)
    return ('static const u16 cap_offsets[] = {' + ','.join(map(str, offsets)) + '};\n'
            'static const u8 cap_patterns[] __attribute__((aligned(256))) = {\n'
            + ',\n'.join(','.join(map(str, data[i:i+32])) for i in range(0, len(data), 32))
            + '\n};\n')
