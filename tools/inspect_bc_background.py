#!/usr/bin/env python3
"""Build reference sheets for authoring BC scenery with our Genesis artwork.

PCE pixels are inspection material only: this tool generates no linked assets.
Verify the decoded round-one layout against captured PCE background nametables
before producing the reference sheets. Do not automatically choose replacements:
matching texture alone can substitute the wrong silhouette or collision edge.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CODE_SHA = 'c5623ff8faab5175a48afeda4c7ab032d018295107fe74c71d30c7c8e2fe0c0a'


def cell_index(x, y):
    x &= 4095
    y &= 4095
    return ((x >> 5) & 7) | (((y >> 5) & 7) << 3) | ((x >> 8) << 6) | ((y >> 8) << 10)


def source_word(code, x, y):
    cell = code[0xc000 + cell_index(x, y)]
    offset = 0x6220 + cell * 8 + ((x & 16) >> 3) + ((y & 16) >> 2)
    pattern, attributes = code[offset:offset + 2]
    # $70CD-$7118: four 8x8 characters per 16x16 quadrant, 16 tiles/row.
    tile = 0x1c0 + (pattern & 248) * 4 + (pattern & 7) * 2
    tile += ((x >> 3) & 1) + (((y >> 3) & 1) * 16)
    return ((attributes & 0xf0) << 8) | tile


def source_cell(code, vram, palette, cell):
    pixels = np.zeros((32, 32, 3), dtype=np.uint8)
    for q in range(4):
        pattern, attributes = code[0x6220 + cell * 8 + q * 2:0x6222 + cell * 8 + q * 2]
        base = 0x1c0 + (pattern & 248) * 4 + (pattern & 7) * 2
        for sy in range(2):
            for sx in range(2):
                start = (base + sy * 16 + sx) * 16
                for y in range(8):
                    low, high = int(vram[start + y]), int(vram[start + y + 8])
                    for x in range(8):
                        pen = ((low >> (7-x)) & 1) | (((low >> (15-x)) & 1) << 1)
                        pen |= (((high >> (7-x)) & 1) << 2) | (((high >> (15-x)) & 1) << 3)
                        pixels[q // 2 * 16 + sy * 8 + y, q % 2 * 16 + sx * 8 + x] = palette[(attributes >> 4) * 16 + pen]
    return pixels


def atlas(images, labels, title, path, columns=8):
    rows = (len(images) + columns - 1) // columns
    out = Image.new('RGB', (columns * 100, rows * 90 + 30), '#181824')
    draw = ImageDraw.Draw(out)
    draw.text((8, 8), title, fill='white')
    for i, (pixels, label) in enumerate(zip(images, labels)):
        x, y = i % columns * 100 + 4, i // columns * 90 + 30
        out.paste(Image.fromarray(pixels).resize((64, 64), Image.Resampling.NEAREST), (x, y))
        draw.text((x, y + 65), label, fill='white')
    out.save(path)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture', type=Path, default=ROOT / '.local/pce-reference/play-task-round1')
    p.add_argument('--output', type=Path, default=ROOT / '.local/bc-background-authoring')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    code = (a.capture / 'code-002160.bin').read_bytes()
    assert hashlib.sha256(code).hexdigest() == CODE_SHA, 'This inspector describes round-one tables only'
    verified = 0
    captures = []
    for frame in (2160, 2400, 2880, 3360, 3960, 4560):
        prefix = a.capture / f'f{frame:06}'
        ram = Path(str(prefix) + '-ram.bin').read_bytes()
        vram = np.frombuffer(Path(str(prefix) + '-vram.bin').read_bytes(), '<u2')
        x, y = ram[0x2e] * 256 + ram[0x2f], ram[0x31] * 256 + ram[0x32]
        count = 0
        # Exclude HUD and the freshly streamed edge; compare actual VDC BAT words.
        for ty in range(y // 8 + 3, (y + 223) // 8):
            for tx in range(x // 8 + 1, (x + 255) // 8):
                expected = source_word(code, tx * 8, ty * 8)
                actual = int(vram[(ty % 64) * 64 + tx % 64])
                assert actual == expected, (frame, tx, ty, hex(actual), hex(expected))
                count += 1
        captures.append(dict(frame=frame, camera=[x, y], tiles=count))
        verified += count

    vram = np.frombuffer((a.capture / 'f002880-vram.bin').read_bytes(), '<u2')
    words = np.frombuffer((a.capture / 'f002880-palette.bin').read_bytes(), '<u2')
    palette = np.array([((int(w) >> 3 & 7) * 36, (int(w) >> 6 & 7) * 36, (int(w) & 7) * 36) for w in words], np.uint8)
    cells = [source_cell(code, vram, palette, i) for i in range(63)]
    labels = []
    metadata = []
    for i in range(63):
        values = list(code[0x6220 + i * 8:0x6228 + i * 8])
        solids = [values[q * 2 + 1] & 15 for q in range(4)]
        labels.append(f'{i:02X} ' + ''.join('X' if value else '.' for value in solids))
        metadata.append(dict(cell=i, quadrants=[dict(pattern=values[q*2], palette=values[q*2+1] >> 4,
                            collision=solids[q]) for q in range(4)]))
    atlas(cells, labels, 'PCE reference only / TL TR BL BR collision: X=solid', a.output / 'source-cells.png')
    # Round-one playfield, including the stage's final right-side margin.
    strip = np.zeros((256, 3584, 3), np.uint8)
    for cy in range(8):
        for cx in range(16, 128):
            cell = code[0xc000 + cell_index(cx * 32, cy * 32)]
            assert cell < len(cells), (cx, cy, cell)
            strip[cy*32:cy*32+32, (cx-16)*32:(cx-15)*32] = cells[cell]
    Image.fromarray(strip).save(a.output / 'source-round-one.png')

    generated = ROOT / 'res/generated'
    patterns = np.frombuffer((generated / 'zone0_tiles.bin').read_bytes(), np.uint8)
    attrs = np.frombuffer((generated / 'zone0_attr.bin').read_bytes(), '>u2')
    words = np.frombuffer((generated / 'zone0_pal.bin').read_bytes(), '>u2')
    vivid = np.frombuffer((generated / 'vivid_lut.bin').read_bytes(), '>u2')
    for name, use_vivid in [('converted', False), ('vivid', True)]:
        colours = []
        for raw in words:
            w = int(raw)
            if use_vivid:
                index = ((w >> 1) & 7) | (((w >> 5) & 7) << 3) | (((w >> 9) & 7) << 6)
                w = int(vivid[index])
            colours.append(((w >> 1 & 7) * 36, (w >> 5 & 7) * 36, (w >> 9 & 7) * 36))
        palette = np.array(colours, np.uint8)
        images = []
        for meta in range(len(patterns) // 512):
            pixels = np.zeros((32, 32, 3), np.uint8)
            for subtile in range(16):
                offset = meta * 512 + subtile * 32
                packed = patterns[offset:offset+32].reshape(8, 4)
                pens = np.stack((packed >> 4, packed & 15), axis=-1).reshape(8, 8)
                rgb = palette[((int(attrs[meta*16+subtile]) >> 13) & 1) * 16 + pens].copy()
                rgb[pens == 0] = 0
                x, y = subtile % 4 * 8, subtile // 4 * 8
                pixels[y:y+8, x:x+8] = rgb
            images.append(pixels)
        atlas(images, [str(i) for i in range(len(images))], f'Our Genesis zone 0 artwork / {name} palette',
              a.output / f'genesis-cells-{name}.png')
    report = dict(verified_source_tiles=verified, captures=captures, source_cells=metadata,
                  genesis_metatiles=len(images), source_images_reference_only=True,
                  replacement_mapping_authored=False, linked_assets_changed=False)
    (a.output / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(dict(verified_source_tiles=verified, source_cells=len(cells),
                         genesis_metatiles=len(images), output=str(a.output)), indent=2))


if __name__ == '__main__':
    main()
