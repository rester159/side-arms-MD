#!/usr/bin/env python3
"""Measure BC simulation and presentation separately at stock emulator timing.

Protected, periodic-fire fixture; not a campaign or unassisted playthrough.
Input is supplied per video frame. Use per-scene replay tests for equivalence.
PAL testing changes only the ROM region header in the evidence directory.
"""
import argparse
import ctypes as C
import hashlib
import json
import shutil
from pathlib import Path

from run_rom import Runner, PAD


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', type=Path, required=True)
    parser.add_argument('--round', type=int, choices=range(1, 11), required=True)
    parser.add_argument('--players', type=int, choices=(1, 2, 3, 4), default=4)
    parser.add_argument('--pal', action='store_true')
    parser.add_argument('--music', choices=('arcade', 'hucard'), default='hucard')
    parser.add_argument('--frames', type=int, default=6000)
    parser.add_argument('--stop-on-game-over', action='store_true',
                        help='Report a shortened sample when the stationary fixture exhausts its lives; terrain deaths are still possible')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert args.frames >= 600, 'Need at least ten seconds of samples'
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.rom.read_bytes()
    tested_rom = args.rom
    if args.pal:
        image = bytearray(source)
        image[0x1f0:0x200] = b'E' + b' ' * 15
        tested_rom = args.output / 'rom.bin'
        assert tested_rom.resolve() != args.rom.resolve()
        tested_rom.write_bytes(image)
        shutil.copy2(args.rom.parent / 'symbol.txt', args.output / 'symbol.txt')

    runner = Runner(rom=tested_rom)

    class AVInfo(C.Structure):
        _fields_ = [('geometry', C.c_uint * 4), ('aspect', C.c_float),
                    ('fps', C.c_double), ('sample_rate', C.c_double)]

    av = AVInfo()
    runner.lib.retro_get_system_av_info(C.byref(av))
    assert (av.fps < 55) == args.pal
    runner.run(2600)

    def tap(button):
        runner.run(5, PAD[button])
        runner.run(20)

    tap('DOWN')
    tap('A')
    for _ in range(3):
        tap('DOWN')
    tap('A')
    for _ in range(8):
        tap('DOWN')
    if args.music == 'hucard':
        tap('RIGHT')
    else:
        runner.run(25)  # Keep the option-screen duration identical.
    tap('B')
    assert runner.read('music_source', 1) == bytes([args.music == 'hucard'])
    for name, value in [('dbg_bc_native_players', args.players),
                        ('dbg_bc_native_start_round', args.round - 1),
                        ('dbg_bc_native_protect', 1), ('dbg_bc_native', 1)]:
        runner.write(name, value.to_bytes(2, 'big'))
    runner.write('dbg_pad_override', b'\1')
    zram = (C.c_uint8 * 8192).in_dll(runner.lib, 'zram')
    underruns = []
    termination = 'frame_limit'

    def step():
        nonlocal termination
        tick = runner.u32('dbg_bc_native_ticks')
        held = 0x20 if tick % 40 < 20 else 0
        pressed = held if tick % 40 == 0 else 0
        runner.write('pad', bytes([held, pressed] * args.players +
                                  [0, 0] * (4 - args.players)))
        runner.run(1)
        if zram[0x1b0a]:
            underruns.append(runner.frames)
        if args.stop_on_game_over and runner.u16('dbg_bc_native_status') == 7:
            termination = 'game_over'
            return False
        assert runner.u16('dbg_bc_native_status') in (0, 4, 6), dict(
            status=runner.u16('dbg_bc_native_status'),
            tick=runner.u32('dbg_bc_native_ticks'),
            handler=hex(runner.u16('dbg_bc_native_handler')),
            round=runner.u16('dbg_bc_native_current_round') + 1)
        return True

    for _ in range(600):
        assert step(), 'Fixture ended during warmup'
    assert runner.read('party_count', 1) == bytes([args.players]), 'Wrong active party size'
    ticks = [runner.u32('dbg_bc_native_ticks')]
    skipped_start = runner.u32('dbg_bc_render_skips')
    presented_start = runner.u32('frame_counter')
    for _ in range(args.frames):
        active = step()
        ticks.append(runner.u32('dbg_bc_native_ticks'))
        if not active:
            break
    measured_frames = len(ticks) - 1
    window = round(av.fps * 5)
    assert measured_frames >= window, 'Sample too short for a five-second timing window'
    rolling = [(ticks[i + window] - ticks[i]) * av.fps / window
               for i in range(measured_frames - window + 1)]
    updates = ticks[-1] - ticks[0]
    presentations = runner.u32('frame_counter') - presented_start
    report = dict(
        source_rom_sha256=hashlib.sha256(source).hexdigest(),
        tested_rom_sha256=hashlib.sha256(tested_rom.read_bytes()).hexdigest(),
        round=args.round, players=args.players, pal=args.pal, music=args.music,
        refresh_hz=av.fps, video_frames=measured_frames,
        requested_video_frames=args.frames, termination=termination,
        simulation_updates=updates, updates_per_second=updates * av.fps / measured_frames,
        minimum_rolling_five_second_rate=min(rolling),
        presentation_batches=presentations,
        presentation_batches_per_second=presentations * av.fps / measured_frames,
        render_skips=runner.u32('dbg_bc_render_skips') - skipped_start,
        underruns=len(underruns), final_round=runner.u16('dbg_bc_native_current_round') + 1,
        ntsc_50_update_gate=None if args.pal else min(rolling) >= 50,
        scope=__doc__.strip(),
    )
    (args.output / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
    assert args.rom.read_bytes() == source, 'Input ROM changed during measurement'
    print(json.dumps(report, indent=2))
    assert not underruns, 'HuCard packet underrun'
    if not args.pal:
        assert report['ntsc_50_update_gate'], 'Below 50 simulation updates/sec'


if __name__ == '__main__':
    main()
