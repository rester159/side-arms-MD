#!/usr/bin/env python3
"""Deterministic headless Genesis Plus GX (libretro) runner for the built cartridge.

Pad bits (libretro ids): B=0 A(Genesis A)=1 START=3 UP=4 DOWN=5 LEFT=6 RIGHT=7 C=8."""
import ctypes as C, os, sys
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
CORE = Path(os.environ.get('SIDEARMS_CORE', ROOT / '.local/test-core/genesis_plus_gx_libretro.dylib'))
PAD = dict(B=1 << 0, A=1 << 1, START=1 << 3, UP=1 << 4, DOWN=1 << 5, LEFT=1 << 6, RIGHT=1 << 7, C=1 << 8)


class Info(C.Structure):
    _fields_ = [('path', C.c_char_p), ('data', C.c_void_p), ('size', C.c_size_t), ('meta', C.c_char_p)]


class Runner:
    def __init__(self, rom=None, core=CORE):
        build = Path(os.environ.get('SIDEARMS_BUILD', ROOT))
        rom = Path(rom) if rom else build / 'out/release/rom.bin'
        self.lib = l = C.CDLL(str(core)); self.frame = None; self.mask = 0; self.pixel = 2; self.frames = 0

        def env(cmd, p):
            if cmd == 10:
                self.pixel = C.cast(p, C.POINTER(C.c_int))[0]; return self.pixel in (0, 1, 2)
            if cmd == 17:
                C.cast(p, C.POINTER(C.c_bool))[0] = False; return True
            return cmd in (8, 11, 16, 18, 35, 37)

        def video(p, w, h, pitch):
            if not p:
                return
            raw = C.string_at(p, pitch * h)
            if self.pixel == 1:
                a = np.frombuffer(raw, np.uint8).reshape(h, pitch)[:, :w * 4].reshape(h, w, 4); self.frame = a[:, :, [2, 1, 0]].copy()
            else:
                a = np.frombuffer(raw, np.uint16).reshape(h, pitch // 2)[:, :w].astype(np.uint32)
                r = (a >> 11) * 255 // 31; g = ((a >> 5) & 63) * 255 // 63
                self.frame = np.stack([r, g, (a & 31) * 255 // 31], axis=2).astype(np.uint8)
        funcs = [('environment', C.CFUNCTYPE(C.c_bool, C.c_uint, C.c_void_p), env),
                 ('video_refresh', C.CFUNCTYPE(None, C.c_void_p, C.c_uint, C.c_uint, C.c_size_t), video),
                 ('audio_sample', C.CFUNCTYPE(None, C.c_int16, C.c_int16), lambda a, b: None),
                 ('audio_sample_batch', C.CFUNCTYPE(C.c_size_t, C.POINTER(C.c_int16), C.c_size_t), lambda p, n: n),
                 ('input_poll', C.CFUNCTYPE(None), lambda: None),
                 ('input_state', C.CFUNCTYPE(C.c_int16, C.c_uint, C.c_uint, C.c_uint, C.c_uint),
                  lambda port, d, i, b: int(port == 0 and bool(self.mask & (1 << b))))]
        self.callbacks = []
        for name, typ, fn in funcs:
            cb = typ(fn); self.callbacks.append(cb); f = getattr(l, 'retro_set_' + name); f.argtypes = [typ]; f(cb)
        l.retro_init(); raw = Path(rom).read_bytes(); self.buffer = C.create_string_buffer(raw)
        info = Info(str(rom).encode(), C.cast(self.buffer, C.c_void_p), len(raw), None)
        l.retro_load_game.argtypes = [C.POINTER(Info)]; l.retro_load_game.restype = C.c_bool
        assert l.retro_load_game(C.byref(info))
        l.retro_set_controller_port_device(0, 513)
        self.ram = (C.c_uint8 * 65536).in_dll(l, 'work_ram')
        self.vram = (C.c_uint8 * 65536).in_dll(l, 'vram')
        self.symbols = {}
        for line in (Path(rom).parent / 'symbol.txt').read_text().splitlines():
            v = line.split()
            if len(v) >= 3:
                try:
                    self.symbols.setdefault(v[2].split('.lto_priv.')[0], int(v[0], 16))
                except ValueError:
                    pass

    def run(self, n, mask=0):
        self.mask = mask
        for _ in range(n):
            self.lib.retro_run(); self.frames += 1

    def read(self, name, n=2, offset=0):
        a = (self.symbols[name] + offset) & 0xffff
        return bytes(self.ram[(a + i) ^ 1] for i in range(n))

    def u16(self, name, offset=0):
        return int.from_bytes(self.read(name, 2, offset), 'big')

    def u32(self, name, offset=0):
        return int.from_bytes(self.read(name, 4, offset), 'big')

    def write(self, name, data, offset=0):
        a = (self.symbols[name] + offset) & 0xffff
        for i, v in enumerate(data):
            self.ram[(a + i) ^ 1] = v

    def capture(self, path):
        Image.fromarray(self.frame).save(path)


if __name__ == '__main__':
    r = Runner(); out = ROOT / 'reports/port'; out.mkdir(parents=True, exist_ok=True)
    for i in range(int(sys.argv[1]) if len(sys.argv) > 1 else 6):
        r.run(120); r.capture(out / f'shot{i}.png')
    print('frames', r.frames, 'frame_counter', r.u32('frame_counter'))
