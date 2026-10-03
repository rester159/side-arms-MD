#!/usr/bin/env python3
"""Boot regression with flash-cart-like dirty RAM/I/O, region and reset controls.

Run each case in a separate process (the emulator core owns global state).
This models one launch condition; it is not EverDrive or MiSTer certification.
"""
import argparse
import ctypes as C
from pathlib import Path
import shutil
import tempfile
from run_rom import Runner

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--rom', type=Path, default=Path('out/release/rom.bin'))
ap.add_argument('--region', choices=('U', 'E'), default='U')
ap.add_argument('--dirty', action='store_true')
ap.add_argument('--reset', action='store_true')
ap.add_argument('--output', type=Path, default=Path('reports/itch-bugs'))
args = ap.parse_args()
args.output.mkdir(parents=True, exist_ok=True)
label = f'{args.region}-{"dirty" if args.dirty else "cold"}-{"reset" if args.reset else "boot"}'
with tempfile.TemporaryDirectory() as temp:
    rom = Path(temp) / 'rom.bin'
    data = bytearray(args.rom.read_bytes())
    data[0x1F0:0x200] = args.region.encode().ljust(16, b' ')
    rom.write_bytes(data)
    shutil.copy(args.rom.parent / 'symbol.txt', rom.parent / 'symbol.txt')
    r = Runner(rom)
    r.lib.retro_get_region.restype = C.c_uint
    assert r.lib.retro_get_region() == (1 if args.region == 'E' else 0), 'core did not select the requested region'
    if args.dirty:
        for i in range(65536):
            r.ram[i] = 0xA5
        io = (C.c_uint8 * 16).in_dll(r.lib, 'io_reg')
        io[4] = io[6] = 0x40
    r.run(2000)
    if args.reset:
        assert r.u32('flow_state') == 0, 'initial launch failed before reset'
        r.lib.retro_reset()
        r.run(2000)
    before = r.u32('frame_counter')
    r.run(120)
    progress = r.u32('frame_counter') - before
    r.capture(args.output / f'{label}.png')
    zram = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
    result = dict(case=label, state=r.u32('flow_state'), updates=progress, sound_ready=zram[0x1F07])
    print(result, flush=True)
    assert result['state'] == 0, 'did not reach mode select'
    assert 115 <= progress <= 120, 'game loop stopped or failed to initialize'
    assert result['sound_ready'] == 0x80, 'sound driver not ready'
