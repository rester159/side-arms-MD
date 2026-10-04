#!/usr/bin/env python3
"""Exercise MiSTer's small-ROM /TIME SRAM latch decode in Genesis Plus GX.

This is a cartridge-bus model, not an FPGA simulation. MiSTer RTL reference:
https://github.com/MiSTer-devel/MegaDrive_MiSTer/blob/master/rtl/cartridge.sv
For ROM <= 4 MiB, every low-byte /TIME write sets md_bank_sram from bit 0;
while enabled, SRAM shadows $200000-$3FFFFF. GPGX normally decodes $A130F1
more narrowly, hiding SGDK's accidental SRAM enable through SSF2 registers.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
from run_rom import Runner, PAD

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--rom', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--expect-failure', action='store_true')
args = ap.parse_args()
r = Runner(args.rom)

class Map(C.Structure):
    _fields_ = [(n, C.c_void_p) for n in ('base', 'read8', 'read16', 'write8', 'write16')]

maps = (Map * 256).in_dll(r.lib, 'm68k')
original = [bytes(maps[i]) for i in range(0x20, 0x40)]
write = C.CFUNCTYPE(None, C.c_uint, C.c_uint)
read = C.CFUNCTYPE(C.c_uint, C.c_uint)
io8, io16 = write(maps[0xA1].write8), write(maps[0xA1].write16)
save = (C.c_uint8 * 65536)(*([255] * 65536))
# Base is used for direct DMA access; callbacks supply the replicated SRAM byte
# on CPU reads, matching the RTL. Fresh blank SRAM suffices for this boot test.
dma_blank = (C.c_uint8 * 65536)(*([255] * 65536))
rd8 = read(lambda a: save[(a >> 1) & 65535])
rd16 = read(lambda a: save[(a >> 1) & 65535] * 257)
def store(a, d):
    if a & 1:
        save[(a >> 1) & 65535] = d & 255
wr8 = write(store)
wr16 = write(lambda a, d: store(a | 1, d))
events = []
def latch(a, d):
    events.append({'address': hex(a), 'value': d, 'frame': r.frames})
    for i in range(0x20, 0x40):
        if d & 1:
            maps[i] = Map(C.addressof(dma_blank), C.cast(rd8, C.c_void_p),
                          C.cast(rd16, C.c_void_p), C.cast(wr8, C.c_void_p),
                          C.cast(wr16, C.c_void_p))
        else:
            C.memmove(C.addressof(maps[i]), original[i - 0x20], C.sizeof(Map))
def byte_write(a, d):
    io8(a, d)
    if (a & 0xFFFF00) == 0xA13000 and a & 1:
        latch(a, d)
def word_write(a, d):
    io16(a, d)
    if (a & 0xFFFF00) == 0xA13000:
        latch(a | 1, d & 255)
cb8, cb16 = write(byte_write), write(word_write)
maps[0xA1].write8 = C.cast(cb8, C.c_void_p)
maps[0xA1].write16 = C.cast(cb16, C.c_void_p)
r.run(2000)
before = r.u32('frame_counter')
r.run(120)
updates = r.u32('frame_counter') - before
zram = (C.c_uint8 * 8192).in_dll(r.lib, 'zram')
result = dict(state=r.u32('flow_state'), updates=updates, sound_ready=zram[0x1F07], writes=events)
passed = result['state'] == 0 and 115 <= updates <= 120 and result['sound_ready'] == 128
args.output.mkdir(parents=True, exist_ok=True)
r.capture(args.output / 'boot.png')
(args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result), flush=True)
assert passed != args.expect_failure, 'unexpected boot result with MiSTer SRAM decode'
if not args.expect_failure:
    assert not any(int(e['address'], 16) != 0xA130F1 for e in events), 'unexpected mapper write'

if not args.expect_failure:
    def tap(button):
        r.run(5, PAD[button])
        r.run(15)
    tap('DOWN'); tap('START')
    assert r.u32('flow_state') == 9
    r.capture(args.output / 'home.png')
    tap('DOWN'); tap('DOWN'); tap('A')
    old_lives = r.read('home_cfg', 1, 1)[0]
    tap('DOWN'); tap('RIGHT'); tap('B')
    new_lives = r.read('home_cfg', 1, 1)[0]
    assert new_lives == old_lives % 7 + 1
    assert bytes(save[:4]) == b'SAR2', 'settings did not reach SRAM'
    r.lib.retro_reset()
    maps[0xA1].write8 = C.cast(cb8, C.c_void_p)
    maps[0xA1].write16 = C.cast(cb16, C.c_void_p)
    r.run(2000)
    assert r.u32('flow_state') == 0
    assert r.read('home_cfg', 1, 1)[0] == new_lives, 'SRAM settings did not survive reset'
    # Older settings blocks keep their checksum at an earlier byte.
    for version, length in [(1, 21), (2, 26)]:
        save[40] = version
        checksum = 0x5A
        for value in save[40:40 + length]:
            checksum = (((checksum << 1) | (checksum >> 7)) & 255) ^ value
        save[40 + length] = checksum
        r.lib.retro_reset()
        maps[0xA1].write8 = C.cast(cb8, C.c_void_p)
        maps[0xA1].write16 = C.cast(cb16, C.c_void_p)
        r.run(2000)
        assert r.read('home_cfg', 1, 1)[0] == new_lives, ('legacy save', version)
    tap('START'); tap('START')
    r.run(1100)
    assert r.u32('flow_state') == 7, 'Home game did not start'
    before = r.u32('frame_counter')
    r.run(120, PAD['B'])
    assert r.u32('frame_counter') - before >= 115
    r.capture(args.output / 'play.png')
    assert not any(int(e['address'], 16) != 0xA130F1 for e in events)
    result.update(save_reload=True, gameplay=True, writes=events)
    (args.output / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('PASS: Home options saved/reloaded across reset; Home gameplay advances')
