#!/usr/bin/env python3
"""Preserve captured BC composite geometry for replacing mismatched boss drafts.

This exports source evidence, not Genesis-ready artwork. Palette conversion and
resident-block budgeting must be completed before using it in the game.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from qa_bc_factory import actor

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    (1, 0x36b6, 'actor-step-hopper', 9240),
    (2, 0x36c4, 'round2-ending', 7440),
    (3, 0x36bc, 'round3-defeat', 7920),
    (4, 0x36be, 'round4-defeat', 7440),
    (5, 0x36b8, 'round5-ending', 12720),
    (6, 0x36ba, 'round6-defeat', 7680),
    (7, 0x36c6, 'round7-defeat', 9360),
    (8, 0x36c0, 'round8-defeat', 10080),
    (9, 0x36c2, 'round9-final', 27360),
)
DEST = ROOT / 'tools/data/bc_composite_source_shapes.json'


def export():
    bosses = []
    for number, family, capture, frame in SOURCES:
        folder = ROOT / '.local/pce-reference' / capture
        stem = f'f{frame:06d}'
        paths = {kind: folder / f'{stem}-{kind}.bin'
                 for kind in ('ram', 'vram', 'palette')}
        paths['code'] = folder / 'code-002160.bin'
        paths['screenshot'] = folder / 'snap' / f'{stem}.png'
        raw = {kind: path.read_bytes() for kind, path in paths.items()}
        ram, code = raw['ram'], raw['code']
        vram = struct.unpack('<32768H', raw['vram'])
        palette = struct.unpack('<512H', raw['palette'])
        poses = {}
        for slot in range(32):
            a = actor(ram, slot, code)
            b = a.body
            if (not b.state or a.sprite_base_ref != family or not b.flags & 8
                    or b.sprite < 0x4000):
                continue
            record = code[b.sprite - 0x4000:]
            assert record[0] == 0xfa, (number, hex(b.sprite))
            pieces = []
            for index in range(record[1]):
                y, x, offset, flags = struct.unpack_from('bbBB', record, 2 + index * 4)
                assert not flags & ~0x88, (number, flags)
                pattern = (b.sprite_base + offset) >> 1
                rows = []
                for py in range(16):
                    sy = 15 - py if flags & 0x80 else py
                    row = []
                    for px in range(16):
                        sx = 15 - px if flags & 8 else px
                        row.append(sum(((vram[pattern * 64 + sy + plane * 16]
                                         >> (15 - sx)) & 1) << plane
                                       for plane in range(4)))
                    rows.append(''.join(format(p, 'x') for p in row))
                pieces.append(dict(x=x, y=y, pattern=pattern, flags=flags, rows=rows))
            source_palette = b.attributes & 15
            words = palette[256 + source_palette * 16:272 + source_palette * 16]
            colors = [[w >> 3 & 7, w >> 6 & 7, w & 7] for w in words]
            if pieces:
                x0 = min(p['x'] for p in pieces)
                y0 = min(p['y'] for p in pieces)
                width = max(p['x'] + 16 for p in pieces) - x0
                height = max(p['y'] + 16 for p in pieces) - y0
            else:
                x0 = y0 = width = height = 0
            pose = dict(frame=b.sprite, source_palette=source_palette, colors=colors,
                        bounds=[x0, y0, width, height], pieces=pieces,
                        rectangular_32px_blocks=((width + 31) // 32) * ((height + 31) // 32))
            if b.sprite in poses:
                assert poses[b.sprite] == pose
            poses[b.sprite] = pose
        assert poses and any(p['pieces'] for p in poses.values()), number
        bosses.append(dict(round=number, family=family, capture=capture, capture_frame=frame,
                           source_hashes={k: hashlib.sha256(v).hexdigest() for k, v in raw.items()},
                           poses=list(poses.values()),
                           rectangular_32px_blocks=sum(p['rectangular_32px_blocks'] for p in poses.values())))
    return dict(schema=1, purpose='Source geometry evidence; not production Genesis assets',
                transparent_pen=0, rgb_channel_max=7,
                block_estimate='Independent rectangular packing per pose; before deduplication and blank-block removal',
                bosses=bosses)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = export()
    rendered = json.dumps(result, indent=2) + '\n'
    if args.check:
        assert DEST.read_text() == rendered, 'Source geometry or capture hashes changed'
    else:
        DEST.write_text(rendered)
    print(json.dumps(dict(bosses=len(result['bosses']),
                          poses=sum(len(b['poses']) for b in result['bosses']),
                          pieces=sum(len(p['pieces']) for b in result['bosses'] for p in b['poses']),
                          production_art_changed=False, checked=args.check)))


if __name__ == '__main__':
    main()
