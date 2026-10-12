#!/usr/bin/env python3
"""Decode gallery text and verify its cell layout against private PCE captures.

No reference pixel data is exported into cartridge assets. The output is
Unicode text and source-code cell positions for a separately authored font.
"""
import argparse
import json
import struct
import unicodedata
from pathlib import Path
from build_bc_ending import extract

KANA = {}
for base, text in ((0x80, 'アイウエケコサシ'), (0x88, 'スセソタチツテト'),
                   (0x90, 'オカキクノハヒフ'), (0x98, 'ヘホマミムメモヤ'),
                   (0xa0, 'ナニヌネルレロワ'), (0xa8, 'ヲンァィゥェ'),
                   (0xb0, 'ユヨラリォャュョッ。')):
    KANA.update({base+i: c for i, c in enumerate(text)})
KANA.update({0xba: '\u309a', 0xbb: '\u3099', 0xbc: 'ー', 0x71: 'm', 0x75: ' '})


def decode(caption):
    text = []
    for code in caption:
        if code == 0x2f:
            text.append('\n')
        elif code in KANA:
            text.append(KANA[code])
        elif 0x20 <= code <= 0x7e:
            text.append(chr(code))
        else:
            raise ValueError(f'unmapped gallery code {code:02x}')
    return unicodedata.normalize('NFC', ''.join(text))


def layout(caption):
    """$9B45: slash advances one row; marks go above the previous cell."""
    cells = []
    x = y = 0
    for code in caption:
        if code == 0x2f:
            x = 0
            y += 1
        elif code in (0xba, 0xbb):
            assert x, 'mark without preceding character'
            cells.append((x-1, y-1, code))
        else:
            cells.append((x, y, code))
            x += 1
    return cells


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--code', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    program = args.code.read_bytes()
    _, _, captions, _ = extract(program)
    frame_cells = layout(program[0x9d25-0x4000:0x9d4f-0x4000-1])
    assert len(frame_cells) == 36
    entries = [dict(index=i, text=decode(c), cells=layout(c), verified_frames=[])
               for i, c in enumerate(captions)]
    checked = 0
    for path in sorted(args.capture.glob('f*-ram.bin')):
        ram = path.read_bytes()
        entry = ram[0x73]
        # The completed horizontal entrance ends on a 256-pixel boundary.
        # Other phases can reuse these bytes, so require the exact caption
        # signature before accepting a full cell-for-cell match.
        if entry >= 20 or ram[0x2f] or ram[0x30]:
            continue
        vram_path = path.with_name(path.name.replace('-ram.bin', '-vram.bin'))
        if not vram_path.exists():
            continue
        vram = struct.unpack('<32768H', vram_path.read_bytes())
        col = ((entry+1)*32+11) & 63
        cells = entries[entry]['cells']
        if all(vram[((y+4)&31)*64+((x+col)&63)] == 0x140+code
               for x, y, code in cells) and all(
                vram[((y+6)&31)*64+((x+col-7)&63)] == 0x140+code
                for x, y, code in frame_cells):
            entries[entry]['verified_frames'].append(int(path.name[1:7]))
            checked += len(cells)+len(frame_cells)
    missing = [e['index'] for e in entries if not e['verified_frames']]
    assert not missing, f'No complete matching captured layout for entries {missing}'
    result = dict(entries=entries, frame_cells=frame_cells, verified_cells=checked,
                  source_pixels_packaged=False, native_rendering_verified=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(f'PASS: {len(entries)} captions decoded; {checked} source VRAM cells verified')
    for entry in entries:
        print(entry['index'], entry['text'].split('\n')[0].strip())


if __name__ == '__main__':
    main()
