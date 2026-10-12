#!/usr/bin/env python3
"""Classify linked BC background art by source collision for layer planning.

A collision-free tile is only a candidate: enemy/platform attachment, map joins,
visibility and two-plane streaming costs still require separate verification.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path
from arcade_source import ROOT
from bc_background_equivalence import symbols, rendered_cell

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
rom = (ROOT/'out/release/rom.bin').read_bytes()
sy = symbols(ROOT/'out/release/symbol.txt')
rows = []
for number in range(1, 11):
    code = rom[sy[f'bc_round{number}_code']:sy[f'bc_round{number}_code']+65536]
    at = int.from_bytes(code[0x621c:0x621e], 'little') - 0x4000
    assert 0 <= at <= len(code)-2048
    prefix = 'bc_bg'+(str(number) if number > 1 else '')
    remap = struct.unpack_from('>256H', rom, sy[prefix+'_remap'])
    cells = []
    for cell, entry in enumerate(remap):
        if entry == 4095:
            continue
        px = rendered_cell(rom, sy, prefix, entry)
        opaque = [bool(v and v[0]) for v in px]
        # Match bc_terrain_solid's source attribute-byte selection exactly.
        solid = [code[at+cell*8+q*2+1] & 15 for q in range(4)]
        quadrant_pixels = [sum(opaque[(q//2*16+y)*32+q%2*16+x]
                               for y in range(16) for x in range(16))
                           for q in range(4)]
        kind = ('empty' if not any(opaque) else
                'collision-bearing' if any(solid) else 'collision-free-art')
        cells.append(dict(cell=cell, classification=kind,
                          opaque_pixels=sum(opaque), solid_quadrants=solid,
                          opaque_pixels_per_quadrant=quadrant_pixels))
    rows.append(dict(round=number, source_attributes_offset=at,
                     collision_free_art=[c['cell'] for c in cells if c['classification']=='collision-free-art'],
                     collision_bearing_art=[c['cell'] for c in cells if c['classification']=='collision-bearing'],
                     empty=[c['cell'] for c in cells if c['classification']=='empty'],
                     cells=cells))
result = dict(schema=1, rom_sha256=hashlib.sha256(rom).hexdigest(),
              scope='All linked BC cells, including defensive margin fills; not a route-visibility or safe-layer certification',
              rounds=rows, remaining_checks=['route visibility', 'enemy/platform attachment',
                 'art joins and phase transitions', 'VRAM and DMA budget', 'stock-clock timing'])
a.output.parent.mkdir(parents=True, exist_ok=True)
a.output.write_text(json.dumps(result, indent=2)+'\n')
for r in rows:
    print(f"R{r['round']}: {len(r['collision_free_art'])} collision-free art cells; "
          f"{len(r['collision_bearing_art'])} collision-bearing; {len(r['empty'])} empty")
