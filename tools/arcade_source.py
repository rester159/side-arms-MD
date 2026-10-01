"""Development-only, hash-checked access to the original Side Arms ROM set.

Nothing read here is linked verbatim into the repository; build tools convert it
into local generated assets under res/generated/ (ignored by version control).
"""
from pathlib import Path
import hashlib, json, os, sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT = ROOT / 'rom'


class Source:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('SIDEARMS_SOURCE', DEFAULT)).expanduser().resolve()
        self.lock = json.loads((ROOT / 'tools/rom_manifest.json').read_text())
        self.files = {}
        for row in self.lock['files']:
            path = self.root / row['path']
            if not path.is_file():
                raise ValueError(f"Original Side Arms ROM set (MAME 'sidearms') required in {self.root} (missing {row['path']})")
            raw = path.read_bytes()
            if len(raw) != row['size'] or hashlib.sha256(raw).hexdigest() != row['sha256']:
                raise ValueError('Wrong ROM revision or damaged file: ' + row['path'])
            self.files[row['path']] = raw

    def region(self, name):
        """Concatenate files in MAME ROM_LOAD order for a region."""
        order = {
            'maincpu': ['sa03.bin', 'a_14e.rom', 'a_12e.rom'],
            'audiocpu': ['a_04k.rom'],
            'starfield': ['b_11j.rom'],
            'fgtiles': ['a_10j.rom'],
            'bgtiles': ['b_13d.rom', 'b_13e.rom', 'b_13f.rom', 'b_13g.rom',
                        'b_14d.rom', 'b_14e.rom', 'b_14f.rom', 'b_14g.rom'],
            'sprites': ['b_11b.rom', 'b_13b.rom', 'b_11a.rom', 'b_13a.rom',
                        'b_12b.rom', 'b_14b.rom', 'b_12a.rom', 'b_14a.rom'],
            'bgmap': ['b_03d.rom'],
            'proms': ['63s141.16h', '63s141.11h', '63s141.15h', '63s081.3j'],
        }[name]
        return b''.join(self.files[f] for f in order)


# --- graphics decoders (layouts from MAME capcom/sidearms.cpp) -------------

def _bits(data, bitoff):
    return (data[bitoff >> 3] >> (7 - (bitoff & 7))) & 1


def decode_chars(rom):
    """8x8 2bpp, planes {4,0}, 16 bytes/char -> (n,8,8) uint8."""
    a = np.frombuffer(rom, np.uint8).reshape(-1, 8, 2)  # n, row, byte
    out = np.zeros((a.shape[0], 8, 8), np.uint8)
    for x in range(8):
        byte = a[:, :, x >> 2]
        bit = 3 - (x & 3)  # MAME bit offset 0 = MSB
        p1 = (byte >> (bit + 4)) & 1   # plane at offset 0 -> MSB of pen
        p0 = (byte >> bit) & 1         # plane at offset 4 -> LSB
        out[:, :, x] = (p1 << 1) | p0
    return out


def _decode4(rom, size, xoffs, yoffs, stride):
    """Generic Capcom 4bpp: planes {half+4, half+0, 4, 0}."""
    half = len(rom) // 2
    lo = np.frombuffer(rom[:half], np.uint8)
    hi = np.frombuffer(rom[half:], np.uint8)
    n = half // stride
    out = np.zeros((n, size, size), np.uint8)
    base = np.arange(n) * stride * 8
    for y, yo in enumerate(yoffs):
        for x, xo in enumerate(xoffs):
            off = base + yo + xo
            # plane bit offsets (MSB first in pen): hi+4, hi+0, lo+4, lo+0
            def bit(arr, o):
                return (arr[o >> 3] >> (7 - (o & 7))) & 1
            pen = (bit(hi, off + 4) << 3) | (bit(hi, off) << 2) | (bit(lo, off + 4) << 1) | bit(lo, off)
            out[:, y, x] = pen
    return out


def decode_sprites(rom):
    xo = [0, 1, 2, 3, 8, 9, 10, 11, 256, 257, 258, 259, 264, 265, 266, 267]
    yo = [i * 16 for i in range(16)]
    return _decode4(rom, 16, xo, yo, 64)


def decode_bgtiles(rom):
    xo = []
    for col in range(4):
        b = col * 32 * 16
        xo += [b + 0, b + 1, b + 2, b + 3, b + 8, b + 9, b + 10, b + 11]
    yo = [i * 16 for i in range(32)]
    return _decode4(rom, 32, xo, yo, 256)


def bgmap_cells(rom):
    """128x128 logical map -> arrays (code, color, flipx, flipy)."""
    code = np.zeros((128, 128), np.int32)
    color = np.zeros((128, 128), np.int32)
    flags = np.zeros((128, 128), np.int32)
    for row in range(128):
        for col in range(128):
            off = ((row << 7) + col) << 1
            off = ((off & 0xf801) | ((off & 0x0700) >> 7) | ((off & 0x00fe) << 3)) & 0x7fff
            c = rom[off]; a = rom[off + 1]
            code[row, col] = c | ((a << 8) & 0x100)
            color[row, col] = (a >> 3) & 0x1f
            flags[row, col] = (a >> 1) & 3
    return code, color, flags


def palette_rgb(lo, hi):
    """xBRG_444: lo byte = RRRRGGGG? MAME xBRG_444 on 16-bit word (hi<<8|lo):
    bits 11-8 B, 7-4 R, 3-0 G."""
    w = (hi << 8) | lo
    b = (w >> 8) & 15; r = (w >> 4) & 15; g = w & 15
    return r * 17, g * 17, b * 17


if __name__ == '__main__':
    try:
        s = Source()
    except (ValueError, OSError) as e:
        sys.exit(str(e))
    print(f'Verified original Side Arms ROM set ({len(s.files)} files).')
