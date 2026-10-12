#!/usr/bin/env python3
"""Verify reviewed BC launcher poses in native SAT/VRAM, including all flips.

The expected correspondence comes from the source-art review manifest. This
tests real palette selection, uploaded pattern bytes, sprite placement and
cache behavior; it is not a campaign or frame-rate measurement.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct

from run_rom import ROOT, Runner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rom', type=Path)
    args = parser.parse_args()
    build = Path(os.environ.get('SIDEARMS_BUILD', ROOT))
    rom_path = args.rom or build / 'out/release/rom.bin'
    rom = rom_path.read_bytes()
    manifest = json.loads((build / 'tools/bc_sprite_matches.json').read_text())
    poses = manifest['poses']
    assert len(poses) == 7
    source_ref = int(manifest['source_base_ref'], 0)
    source_base = int(manifest['source_pattern_base'], 0)
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    runner = Runner(rom=rom_path)
    runner.run(2600)
    runner.write('dbg_bc_robot_preview', b'\0\1')
    runner.run(24)
    counters = {name: runner.u32(name) for name in
                ('spr_dbg_remap', 'spr_dbg_dropped', 'spr_dbg_slow')}
    checked = []
    for source_flip in range(4):
        runner.write('dbg_bc_actor_pose', bytes(16 * 14))
        attrs = 0x1185 | ((source_flip & 1) << 11) | ((source_flip & 2) << 14)
        for i, pose in enumerate(poses):
            x, y = 32 + (i % 3) * 80, 40 + (i // 3) * 56
            runner.write('dbg_bc_actor_pose', struct.pack(
                '>7H', source_ref, source_base, source_base + pose['source_offset'],
                attrs, x, y, 128), i * 14)
        runner.run(24)
        assert runner.u16('dbg_bc_actor_unmapped') == 0
        sat = struct.unpack('>28H', runner.read('vdpSpriteCache', 56))
        for i, pose in enumerate(poses):
            y, size_link, attr, x = sat[i * 4:i * 4 + 4]
            assert size_link >> 8 == 15, (pose['id'], 'sprite size')
            assert size_link & 127 == (i + 1 if i < 6 else 0), (pose['id'], 'SAT order')
            assert (x - 128, y - 128) == (48 + (i % 3) * 80, 24 + (i // 3) * 56)
            expected_flip = source_flip ^ pose['source_flips_xor']
            assert (attr >> 11) & 3 == expected_flip, (pose['id'], source_flip, 'flip')
            key = pose['normal_code'] | (pose['normal_colour'] << 11)
            entry = struct.unpack_from('>H', rom, runner.symbols['spr_big_index'] + key * 2)[0]
            assert entry & 0x7fff, (pose['id'], 'missing preconverted composite')
            assert (attr >> 13) & 3 == 2 + (entry >> 15), (pose['id'], 'palette')
            start = runner.symbols['spr_big'] + ((entry & 0x7fff) - 1) * 512
            expected = rom[start:start + 512]
            vram_address = (attr & 0x7ff) * 32
            uploaded = bytes(runner.vram[(vram_address + j) ^ 1] for j in range(512))
            assert uploaded == expected, (pose['id'], 'uploaded pixels')
            checked.append({'pose': pose['id'], 'source_flip': source_flip,
                            'normal_code': pose['normal_code'], 'native_flip': expected_flip})
        runner.capture(out / f'launcher-flip-{source_flip}.png')
    for name, initial in counters.items():
        assert runner.u32(name) == initial, (name, runner.u32(name) - initial)
    runner.write('dbg_bc_robot_preview', b'\0\0')
    runner.run(120)
    assert runner.u32('flow_state') == 0
    result = {'rom_sha256': hashlib.sha256(rom).hexdigest(), 'checked': checked,
              'runtime_remaps': 0, 'sprite_drops': 0, 'composite_fallbacks': 0,
              'returned_to_menu': True, 'campaign_verified': False}
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(f'PASS: {len(checked)} native launcher poses/flips; exact SAT/VRAM; no cache fallback')


if __name__ == '__main__':
    main()
