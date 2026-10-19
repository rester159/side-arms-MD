#!/usr/bin/env python3
"""Verify Standard/Vivid background colors reach native CRAM in all BC rounds."""
import ctypes as C
import argparse
import hashlib
import json
import struct
from pathlib import Path
from run_rom import ROOT, Runner

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, default=ROOT/'.local/vivid-shade-guard')
a = p.parse_args()
out = a.output
out.mkdir(parents=True, exist_ok=True)
rom = (ROOT/'out/release/rom.bin').read_bytes()
r = Runner()
r.run(2600)
lut = struct.unpack_from('>512H', rom, r.symbols['vivid_lut'])
cram = (C.c_uint16*64).in_dll(r.lib, 'cram')
rows = []
for mode in (1, 0):
    for number in range(1, 11):
        prefix = 'bc_bg'+(str(number) if number > 1 else '')
        palette = struct.unpack_from('>32H', rom, r.symbols[prefix+'_palette'])
        r.write('color_mode', bytes([mode]))
        r.write('dbg_bc_cells', struct.pack('>I', r.symbols[f'bc_round{number}_code']+0xc000))
        r.write('dbg_bc_background', struct.pack('>H', number+1))
        r.write('dbg_bc_camera', struct.pack('>2H', 535 if number == 5 else 512,
                                            1024 if number == 5 else 0))
        r.write('dbg_bc_robot_preview', b'\0\1')
        r.run(12)
        for i, source in enumerate(palette):
            packed = (source >> 1 & 7) | (source >> 5 & 7) << 3 | (source >> 9 & 7) << 6
            displayed = lut[packed] if mode else source
            if mode and number == 1:
                displayed = struct.unpack_from('>H', rom, r.symbols['bc_bg_vivid_palette']+i*2)[0]
            # GX stores CRAM as contiguous BBBGGGRRR, unlike the cart's word.
            expected = ((displayed >> 1 & 7) | (displayed >> 5 & 7) << 3 |
                        (displayed >> 9 & 7) << 6)
            assert cram[i] == expected, (mode, number, i, cram[i], expected)
        if number == 5:
            r.capture(out/('native-r5-vivid.png' if mode else 'native-r5-standard.png'))
        rows.append(dict(round=number, mode='Vivid' if mode else 'Standard', cram_words=32))
        r.write('dbg_bc_robot_preview', b'\0\0')
        r.write('dbg_bc_background', b'\0\0')
        r.run(120)
        assert r.u32('flow_state') == 0
report = dict(passed=True, rom_sha256=hashlib.sha256(rom).hexdigest(),
              views=rows, checked_cram_words=640,
              scope='Native palette upload and return to menu, not gameplay or full camera coverage.')
(out/'native.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
