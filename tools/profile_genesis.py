"""Optional guest-cycle attribution for the pinned Genesis Plus GX QA core."""
from contextlib import contextmanager
import bisect
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import subprocess
import numpy as np
from run_rom import ROOT, CORE


@contextmanager
def instruction_profile(runner, output, enabled=True, watch=None, phase=None):
    if not enabled and watch is None:
        yield
        return
    if watch is not None:
        assert 1 <= len(watch[0]) <= 64 and all(isinstance(pc, int) and 0 <= pc < 0x400000 for pc in watch[0])
    assert hashlib.sha256(CORE.read_bytes()).hexdigest() == '20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0', 'unsupported core layout'
    build = Path(os.environ.get('SIDEARMS_BUILD', ROOT))
    library = output.with_suffix('.dylib')
    subprocess.run(['cc', '-O2', '-dynamiclib', str(ROOT/'tools/bc_profile_hook.c'), '-o', str(library)], check=True)
    hook = C.CDLL(str(library))
    hook.profile_begin.argtypes = [C.c_void_p]*3
    base = C.cast(runner.lib.m68k_get_reg, C.c_void_p).value - 0x55aac
    cpu = C.addressof(C.c_uint8.in_dll(runner.lib, 'm68k'))
    assert hook.profile_begin(cpu, base+0x1fefb0, base+0x1719c0) == 0
    if phase is not None:
        # Host-only gate: no guest memory or cycle changes. Bit 1 counts measurement.
        hook.profile_phase.argtypes = [C.c_void_p]
        hook.profile_phase(C.byref(phase))
        hook.profile_only(2)
    callback = None
    callback_errors = []
    if watch is not None:
        pcs, function = watch
        def invoke():
            if callback_errors:
                return
            try:
                function()
            except BaseException as error:
                callback_errors.append(error)
        callback = C.CFUNCTYPE(None)(invoke)
        addresses = (C.c_uint32 * len(pcs))(*pcs)
        hook.profile_watch.argtypes = [C.POINTER(C.c_uint32), C.c_uint, C.CFUNCTYPE(None)]
        assert hook.profile_watch(addresses, len(pcs), callback) == 0
    try:
        yield
        if callback_errors:
            raise callback_errors[0]
    finally:
        hook.profile_end()
        if enabled:
            hist = np.ctypeslib.as_array((C.c_uint64*0x200000).in_dll(hook, 'instruction_cycles')).copy()
            symbols = sorted((int(v[0], 16), v[2]) for line in (build/'out/release/symbol.txt').read_text().splitlines()
                             if len(v := line.split()) >= 3 and v[1] in ('t', 'T') and int(v[0], 16) < 0x400000)
            addresses = [s[0] for s in symbols]
            counts = {}
            for index in np.nonzero(hist)[0]:
                slot = bisect.bisect_right(addresses, int(index)*2)-1
                name = symbols[slot][1] if slot >= 0 else '?'
                counts[name] = counts.get(name, 0)+int(hist[index])
            total = int(hist.sum())
            result = dict(rom_sha256=hashlib.sha256((build/'out/release/rom.bin').read_bytes()).hexdigest(),
                          total_cycles=total, instrumentation=True,
                          functions=[dict(name=n, cycles=c, percent=100*c/total) for n, c in sorted(counts.items(), key=lambda x: -x[1])])
            np.save(output.with_suffix('.npy'), hist)
            output.with_suffix('.json').write_text(json.dumps(result, indent=2)+'\n')
