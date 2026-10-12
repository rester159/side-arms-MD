#!/usr/bin/env python3
"""Observe successful DMA scratch allocations across an existing native QA route.

The driver must not enable its own instruction profiler or scheduler trace.
Observations happen at flushQueue entry, before SGDK resets the scratch pointer.
Optional allocation-attempt watches also observe the current compiler's pointer
advance stores before rollback. Unvisited routes remain outside the evidence.
"""
import argparse
import contextlib
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import runpy
import struct
import sys
from run_rom import ROOT, Runner
from profile_genesis import instruction_profile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--output', type=Path, required=True)
p.add_argument('--allocation-attempts', action='store_true', help='Also check pointer advances before capacity checks, including rejected requests')
p.add_argument('driver', type=Path)
p.add_argument('arguments', nargs=argparse.REMAINDER)
a = p.parse_args()
assert not any(x in ('--profile', '--scheduler-trace') for x in a.arguments), 'nested profiler hooks unsupported'
a.output.mkdir(parents=True, exist_ok=True)
original_init = Runner.__init__
observations = []
attempts = []
attempt_sites = []
instances = []
rom = Path(os.environ.get('SIDEARMS_BUILD', ROOT)) / 'out/release/rom.bin'
digest = hashlib.sha256(rom.read_bytes()).hexdigest()
with contextlib.ExitStack() as stack:
    def initialize(self, *args, **kwargs):
        assert not instances, 'one emulator per DMA audit'
        original_init(self, *args, **kwargs)
        instances.append(self)
        flush = self.symbols['flushQueue']
        pcs = [flush]
        if a.allocation_attempts:
            # Linked 68000 code stores each inlined DMA_allocateTemp advance
            # with MOVE.L Dn/An,absolute.l. Observe immediately after the store,
            # before SGDK can roll an overflowing request back. Absolute-source
            # queue resets do not allocate and remain covered at flush time.
            raw = rom.read_bytes()
            target = struct.pack('>I', self.symbols['nextDataBuffer'])
            sites = [at+6 for at in range(0, len(raw)-6, 2)
                     if raw[at+2:at+6] == target and
                     int.from_bytes(raw[at:at+2], 'big') & 0xfff0 == 0x23c0]
            assert sites and len(sites)+1 <= 64, ('unrecognized DMA pointer stores', sites)
            attempt_sites.extend(sites)
            pcs += sites
        cpu = C.addressof(C.c_uint8.in_dll(self.lib, 'm68k'))
        def observe():
            pc = (C.c_uint32.from_address(cpu+0x2858).value-2)&0xffffff
            used = self.u32('nextDataBuffer') - self.u32('dmaDataBuffer')
            capacity = 2 * self.u16('dataBufferSize')
            assert 0 <= used <= capacity, ('invalid DMA scratch pointers', used, capacity)
            (observations if pc == flush else attempts).append(dict(video_frame=self.frames,
                flow_state=self.u32('flow_state'), players=self.u16('player_limit'),
                used_bytes=used, capacity_bytes=capacity,
                transfer_bytes=self.u16('queueTransferSize')))
        stack.enter_context(instruction_profile(self, a.output/'dma-hook', enabled=False,
                                                watch=(pcs, observe)))
    Runner.__init__ = initialize
    previous_argv = sys.argv
    code = 0
    try:
        sys.argv = [str(a.driver)] + a.arguments
        runpy.run_path(str(a.driver), run_name='__main__')
    except SystemExit as error:
        code = error.code
    finally:
        Runner.__init__ = original_init
        sys.argv = previous_argv
assert observations, 'no DMA flushes observed'
assert hashlib.sha256(rom.read_bytes()).hexdigest() == digest
by_state = []
for state in sorted({row['flow_state'] for row in observations}):
    rows = [row for row in observations if row['flow_state'] == state]
    peak = max(row['used_bytes'] for row in rows)
    by_state.append(dict(flow_state=state, flushes=len(rows), peak_bytes=peak,
                         peak_rows=[row for row in rows if row['used_bytes'] == peak][:4]))
report = dict(rom_sha256=digest, driver=str(a.driver), arguments=a.arguments,
              allocation_attempt_observations=len(attempts),
              allocation_attempt_watch_sites=attempt_sites,
              attempted_peak_bytes=max((row['used_bytes'] for row in attempts), default=None),
              driver_exit_code=code, flushes=len(observations),
              peak_bytes=max(row['used_bytes'] for row in observations), by_state=by_state,
              scope=('Pointer advances at matched register-store instructions and every flush during this driver; unvisited routes excluded'
                     if a.allocation_attempts else 'Successful allocations at every flush during this driver; no failed-allocation or unvisited-route proof'))
(a.output/'result.json').write_text(json.dumps(report, indent=2)+'\n')
(a.output/'flushes.json').write_text(json.dumps(observations, indent=2)+'\n')
print(json.dumps(report, indent=2))
raise SystemExit(code)
