"""Arcade starfield generator (MAME sidearms draw_starfield) -> periodic 512x256 image.

The hardware's screen-x band mask (rejection 1) is applied in star space so the
image stays a pure scroll; colors are palette 0x378 | (latch >> 5)."""
import numpy as np

def star_image(sfrom, flop=1):
    img = np.zeros((256, 512), np.int16) - 1
    for y in range(256):
        latch = 0
        for X in range(512):
            h = X  # hcount + x, 9 bits with carry
            prev = (X - 1) & 0x1ff
            if (prev & 0x1f) == 0x1f:
                i = (y << 4) & 0xff0
                i |= ((flop ^ (h >> 8)) & 1) << 3
                i |= (h >> 5) & 7
                latch = sfrom[i + 0x3000]
            if not ((y ^ (X >> 3)) & 4):
                continue
            if (y | ((h & 0xff) >> 1)) & 2:
                continue
            if (~((latch ^ h) ^ 1)) & 0x1f:
                continue
            img[y, X] = latch >> 5
    return img

if __name__ == '__main__':
    import sys; sys.path.insert(0, 'tools')
    from arcade_source import Source
    img = star_image(Source().region('starfield'))
    n = (img >= 0).sum()
    cells = set()
    for cy in range(32):
        for cx in range(64):
            cells.add(img[cy*8:cy*8+8, cx*8:cx*8+8].tobytes())
    print('stars', n, 'unique cells', len(cells))
