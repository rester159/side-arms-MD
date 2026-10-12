"""Read-only visible BC tile-cache audit at the completed VBlank boundary."""
import struct
import numpy as np
from bc_background_equivalence import block_address


class LiveBackgroundAudit:
    def __init__(self, runner, rom, round_number, every=32, palette=False):
        self.r, self.rom, self.number, self.every = runner, rom, round_number, every
        assert every > 0
        prefix = 'bc_bg' + (str(round_number) if round_number > 1 else '')
        sy = runner.symbols
        at = sy[f'bc_round{round_number}_code']
        self.cells = rom[at+0xc000:at+0x10000]
        self.remap = struct.unpack_from('>256H', rom, sy[prefix+'_remap'])
        count = struct.unpack_from('>H', rom, sy[prefix+'_draft']+8)[0]
        self.attrs = struct.unpack_from('>'+str(count*16)+'H', rom, sy[prefix+'_templates'])
        self.blocks = [rom[(at := block_address(rom, sy, prefix, meta)):at+512] for meta in range(count)]
        self.samples = self.tiles = self.pattern_slots = 0
        self.last_tick = None
        self.cameras = set()
        self.palette = None
        if palette:
            import ctypes as C
            self.palette = struct.unpack_from('>32H', rom, sy[prefix+'_palette'])
            self.vivid = struct.unpack_from('>512H', rom, sy['vivid_lut'])
            self.cram = (C.c_uint16*64).in_dll(runner.lib, 'cram')
            self.palette_checks = 0
            self.color_modes = set()

    def observe(self):
        r = self.r
        tick = r.u32('dbg_bc_native_ticks')
        if tick == self.last_tick or tick % self.every:
            return
        self.last_tick = tick
        assert r.u16('dbg_bc_native_current_round') == self.number-1, ('audit round changed', tick)
        if self.palette is not None:
            mode = r.read('color_mode', 1)[0]
            assert mode in (0, 1), ('unknown color mode', mode)
            def packed(word):
                return (word >> 1 & 7) | (word >> 5 & 7) << 3 | (word >> 9 & 7) << 6
            for i, source in enumerate(self.palette):
                expected = packed(self.vivid[packed(source)] if mode else source)
                assert self.cram[i] == expected, ('live background palette mismatch',
                                                 tick, mode, i, expected, self.cram[i])
                self.palette_checks += 1
            self.color_modes.add(mode)
        x, y = r.u16('show_x'), r.u16('show_y')
        x = x-65536 if x & 32768 else x
        y = y-65536 if y & 32768 else y
        vram = np.ctypeslib.as_array(r.vram).reshape(-1, 2)[:, ::-1].copy().tobytes()
        slots = r.read('cell_slot', 128)
        metas = struct.unpack('>56H', r.read('slot_meta', 112))
        shadow = struct.unpack('>2048H', r.read('shadow', 4096))
        resident = set()
        for cy in range(y//32, (y+223)//32+1):
            for cx in range(x//32, (x+319)//32+1):
                mx = max(16, cx) if self.number in (2, 4, 5, 7) else max(16, min(78, cx & 127)) if self.number == 1 else cx
                mx &= 127
                edge_flip = 0x4000 if self.number == 2 and cx == 15 else 0
                if self.number == 3 and mx in (127, 8):
                    mx = 0 if mx == 127 else 7
                    edge_flip = 0x4000 if self.number == 2 and cx == 15 else 0x4000
                my = cy & 127
                cell = self.cells[(mx&7)|((my&7)<<3)|((mx>>3)<<6)|((my>>3)<<10)]
                entry = self.remap[cell] ^ edge_flip
                meta = entry & 4095
                slot = slots[(cy%8)*16+cx%16]
                context = (tick, x, y, cx, cy, cell, slot, r.u16('queueIndex'))
                assert meta < len(self.blocks) and slot < 56, ('unmapped visible cell', context)
                assert metas[slot] == meta, ('wrong resident cell', context, meta, metas[slot])
                if slot not in resident:
                    address = (160+slot*16)*32
                    assert vram[address:address+512] == self.blocks[meta], ('pattern corruption', context)
                    resident.add(slot)
                for ty in range(4):
                    for tx in range(4):
                        sx = 3-tx if entry & 0x4000 else tx
                        sy = 3-ty if entry & 0x8000 else ty
                        template = self.attrs[meta*16+sy*4+sx]
                        expected = (template+160+slot*16)^((entry&0xc000)>>3) if template else 0
                        pos = ((cy*4+ty)%32)*64+(cx%16)*4+tx
                        actual = struct.unpack_from('>H', vram, 0xe000+pos*2)[0]
                        assert shadow[pos] == expected, ('shadow mismatch', context, tx, ty)
                        assert actual == expected, ('nametable corruption', context, tx, ty, expected, actual)
                        self.tiles += 1
        self.pattern_slots += len(resident)
        self.samples += 1
        self.cameras.add((x, y))

    def result(self):
        assert self.samples, 'No live background samples observed'
        result = dict(passed=True, samples=self.samples, visible_tile_checks=self.tiles,
                    resident_pattern_checks=self.pattern_slots, cameras=[list(p) for p in sorted(self.cameras)],
                    sample_interval_updates=self.every,
                    scope='Live visible BC cell mapping, RAM shadow, post-DMA plane-B nametable and resident pattern bytes. Excludes palette fades, raster timing and unsampled updates.')
        if self.palette is not None:
            result['palette'] = dict(checked_cram_words=self.palette_checks,
                                     color_modes=sorted(self.color_modes),
                                     scope='All 32 background CRAM entries after upload versus linked source palette and selected Standard/Vivid mapping. Requires unfaded gameplay; excludes sprite palettes and raster effects.')
        return result


class CampaignBackgroundAudit:
    """Watch JOY_update after video uploads on one real campaign round."""
    def __init__(self, runner, rom, round_number, output):
        import ctypes as C
        import hashlib
        import subprocess
        from run_rom import ROOT, CORE
        assert hashlib.sha256(CORE.read_bytes()).hexdigest() == '20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
        self.r, self.round, self.output = runner, round_number, output
        self.audit = LiveBackgroundAudit(runner, rom, round_number, every=1)
        self.active = self.done = False
        self.errors = []
        self.captures = []
        self.capture_band = None
        self.capture_pending = False
        self.digest = hashlib.sha256(rom).hexdigest()
        output.mkdir(parents=True, exist_ok=True)
        library = output/'background-hook.dylib'
        subprocess.run(['cc','-O2','-dynamiclib',str(ROOT/'tools/bc_profile_hook.c'),'-o',str(library)],check=True)
        self.h = C.CDLL(str(library))
        self.h.profile_begin.argtypes = [C.c_void_p]*3
        self.h.profile_only.argtypes = [C.c_int]
        self.cpu = C.addressof(C.c_uint8.in_dll(runner.lib,'m68k'))
        assert C.c_uint32.from_address(self.cpu+0x29c8).value == 0x100000
        callback_type = C.CFUNCTYPE(None)
        self.h.profile_watch.argtypes = [C.POINTER(C.c_uint32),C.c_uint,callback_type]
        self.pcs = (C.c_uint32*1)(runner.symbols['JOY_update'])
        self.callback = callback_type(self.watch)
        self.base = C.cast(runner.lib.m68k_get_reg,C.c_void_p).value-0x55aac
        previous_run = runner.run
        def run(frames, mask=0):
            for _ in range(frames):
                previous_run(1, mask)
                self.poll()
        runner.run = run

    def watch(self):
        if self.errors or self.r.u16('dbg_bc_native_current_round') != self.round-1:
            return
        try:
            old = self.audit.samples
            self.audit.observe()
            if self.audit.samples != old:
                x = self.r.u16('show_x')
                band = x//256
                if band != self.capture_band:
                    self.capture_band = band
                    self.capture_pending = True
        except BaseException as error:
            self.errors.append(repr(error))

    def poll(self):
        if self.errors:
            self.close()
            raise AssertionError(self.errors)
        number = self.r.u16('dbg_bc_native_current_round')+1
        if not self.active and not self.done and number == self.round and self.r.u16('dbg_bc_native_background_active'):
            assert self.h.profile_begin(self.cpu,self.base+0x1fefb0,self.base+0x1719c0) == 0
            # Watch-only operation: no instruction attribution is required.
            self.h.profile_only(0)
            assert self.h.profile_watch(self.pcs,len(self.pcs),self.callback) == 0
            self.active = True
        if self.active and number != self.round:
            self.close()
        if self.capture_pending:
            self.capture_pending = False
            path = self.output/f'gameplay-{len(self.captures):02d}.png'
            self.r.capture(path)
            self.captures.append(str(path))

    def close(self):
        if self.active:
            self.h.profile_end()
            self.active = False
            self.done = True

    def finish(self):
        import json
        self.close()
        assert not self.errors, self.errors
        report = dict(rom_sha256=self.digest, round=self.round, **self.audit.result(),
                      captures=self.captures, input_scope='Existing campaign controller; observer writes no game state')
        (self.output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        return report
