"""Render isolated patches through the same Genesis Plus GX YM core as cartridge QA.

YM2612 entry points follow core/sound/ym2612.h in Genesis Plus GX. Runner
initialization is required to establish the core's global channel-enable state.
This probe uses enhanced precision to measure synthesis separately from DAC noise.
"""
import ctypes as C
import numpy as np
from run_rom import Runner


class PatchProbe:
    def __init__(self):
        self.runner = Runner()
        self.runner.run(120)
        self.lib = self.runner.lib
        self.lib.YM2612Init()
        self.lib.YM2612Config(2)
        self.lib.YM2612Update.argtypes = [C.POINTER(C.c_int), C.c_int]

    def write(self, register, value):
        self.lib.YM2612Write(0, register)
        self.lib.YM2612Write(1, value)

    def render(self, multipliers, levels, algorithm=7, attenuation=0):
        self.lib.YM2612ResetChip()
        self.write(0x22, 0)
        self.write(0xb0, algorithm)
        self.write(0xb4, 0xc0)
        for slot, (multiplier, level) in enumerate(zip(multipliers, levels)):
            if algorithm == 7 or slot != 0:
                level += attenuation
            for register, value in ((0x30, multiplier), (0x40, min(127, level)),
                                    (0x50, 31), (0x60, 0), (0x70, 0),
                                    (0x80, 15), (0x90, 0)):
                self.write(register + slot * 4, value)
        # Exact 256-native-sample period makes FFT harmonics unambiguous.
        self.write(0xa4, 0x22)
        self.write(0xa0, 0)
        self.write(0x28, 0xf0)
        samples = np.zeros(8192 * 2, np.int32)
        self.lib.YM2612Update(samples.ctypes.data_as(C.POINTER(C.c_int)), 8192)
        return samples.reshape(-1, 2)[2048:, 0].astype(float)
