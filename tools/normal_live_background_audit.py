"""Read-only samples of settled Normal background cache uploads and CRAM."""
import ctypes as C
import struct
from pathlib import Path

import numpy as np


class NormalBackgroundAudit:
    def __init__(self, runner, rom, zones, output):
        self.r, self.rom, self.output = runner, rom, Path(output)
        self.zones = set(zones)
        self.rows = {z: dict(samples=0, pattern_checks=0, palette_words=0,
                             resident_metas=set(), excluded={}) for z in zones}
        self.seen = set()
        self.cram = (C.c_uint16*64).in_dll(runner.lib, 'cram')
        self.lut = struct.unpack_from('>512H', rom, runner.symbols['vivid_lut'])
        self.attempts = self.unsettled = 0
        self.reg = (C.c_uint8*32).in_dll(runner.lib, 'reg')
        self.borrowed_zones = set()
        for zone in self.zones:
            count = struct.unpack_from('>H', rom, runner.symbols['zones']+zone*26+8)[0]
            words = struct.unpack_from('>' + str(count*16) + 'H', rom,
                                       runner.symbols[f'zone{zone}_attr'])
            home = struct.unpack_from('>I', rom, runner.symbols['zone_home']+zone*4)[0]
            if home:
                extra_count = struct.unpack_from('>H', rom, home+26)[0]
                extra_attrs = struct.unpack_from('>I', rom, home+32)[0]
                words += struct.unpack_from('>' + str(extra_count*16) + 'H', rom, extra_attrs)
            if any(word & 0x4000 for word in words):
                self.borrowed_zones.add(zone)
                self.rows[zone]['borrowed_entries_checked'] = 0
                self.rows[zone]['borrowed_metas'] = set()

    def observe(self, frame):
        r = self.r
        zone = r.u16('zone_id')
        self.seen.add(zone)
        if zone not in self.zones or frame % 16:
            return
        self.attempts += 1
        # Sample after DMA, outside palette switches and wheel-frame overrides.
        for reason, active in (('dma_pending', r.u16('queueIndex')),
                               ('zone_switch', r.read('sw_state', 1)[0]),
                               ('wheel_override', r.u32('fr'))):
            if active:
                self.unsettled += 1
                skips = self.rows[zone]['excluded']
                skips[reason] = skips.get(reason, 0)+1
                return
        def packed(word):
            return (word >> 1 & 7) | (word >> 5 & 7) << 3 | (word >> 9 & 7) << 6
        palette = struct.unpack_from('>32H', self.rom, r.symbols[f'zone{zone}_pal'])
        mode = r.read('color_mode', 1)[0]
        assert mode in (0, 1)
        expected = [packed(self.lut[packed(w)] if mode else w) for w in palette]
        if zone == 0 and mode:
            expected = [packed(w) for w in struct.unpack_from(
                '>32H', self.rom, r.symbols['zone0_vivid_pal'])]
        # Fade/transition samples are excluded; require verified samples in each
        # requested zone at completion, rather than treating skips as passes.
        if list(self.cram[:32]) != expected:
            self.unsettled += 1
            skips = self.rows[zone]['excluded']
            skips['palette_transition'] = skips.get('palette_transition', 0)+1
            return
        if zone in self.borrowed_zones:
            sprite = struct.unpack_from('>32H', self.rom, r.symbols['sprite_pal'])
            expected_sprite = [packed(self.lut[packed(w)] if mode else w) for w in sprite]
            assert list(self.cram[32:64]) == expected_sprite, ('Normal borrowed sprite palette', zone, frame)
        pointer = r.u32('zone')
        count = struct.unpack_from('>H', self.rom, pointer+8)[0]
        tiles = struct.unpack_from('>I', self.rom, pointer+10)[0]
        assert tiles == r.symbols[f'zone{zone}_tiles']
        extra = r.u32('ext_tiles')
        if extra:
            assert extra == r.symbols[f'zone{zone}h_tiles']
        refs = r.read('slot_refs', 56)
        metas = struct.unpack('>56H', r.read('slot_meta', 112))
        vram = np.ctypeslib.as_array(r.vram).reshape(-1, 2)[:, ::-1].copy().tobytes()
        checked = 0
        for slot, (ref, meta) in enumerate(zip(refs, metas)):
            if not ref or ref >= 254:
                continue
            assert meta != 65535, (zone, frame, slot)
            source = tiles+meta*512 if meta < count else extra+(meta-count)*512
            assert meta < count or extra, (zone, frame, meta)
            address = (160+slot*16)*32
            assert vram[address:address+512] == self.rom[source:source+512], ('Normal pattern upload', zone, frame, slot, meta)
            checked += 1
            self.rows[zone]['resident_metas'].add(meta)
        assert checked, ('No resident Normal patterns', zone, frame)
        if zone in self.borrowed_zones:
            plane = (self.reg[4] & 7) << 13
            words = struct.unpack_from('>2048H', vram, plane)
            templates = struct.unpack_from('>I', self.rom, pointer+14)[0]
            extra_templates = r.u32('ext_tmpl')
            for word in words:
                tile = word & 2047
                if not word & 0x4000 or not 160 <= tile < 160+56*16:
                    continue
                slot, index = divmod(tile-160, 16)
                meta = metas[slot]
                if meta == 65535:
                    continue
                assert meta < count or extra_templates
                source = templates+meta*32 if meta < count else extra_templates+(meta-count)*32
                expected_word = struct.unpack_from('>H', self.rom, source+index*2)[0]
                assert word & 0xe000 == expected_word & 0xe000, ('Normal borrowed tile attribute', zone, frame, meta, index)
                self.rows[zone]['borrowed_entries_checked'] += 1
                self.rows[zone]['borrowed_metas'].add(meta)
        row = self.rows[zone]
        if not row['samples']:
            r.capture(self.output/f'background-zone-{zone}.png')
            row['first_frame'] = frame
            row['color_mode'] = mode
        row['samples'] += 1
        row['pattern_checks'] += checked
        row['palette_words'] += 64 if zone in self.borrowed_zones else 32

    def result(self):
        assert all(row['samples'] for row in self.rows.values()), ('Missing Normal background coverage', self.rows, self.seen)
        return dict(passed=True, zones={z: {**row, 'resident_metas': sorted(row['resident_metas']), **({'borrowed_metas': sorted(row['borrowed_metas'])} if 'borrowed_metas' in row else {})}
                                       for z, row in self.rows.items()},
                    observed_zones=sorted(self.seen), attempts=self.attempts,
                    excluded_unsettled_samples=self.unsettled,
                    scope='Read-only settled Normal campaign samples: all 32 background CRAM entries (plus32 sprite CRAM entries for borrowed-palette zones), borrowed plane-B bank/priority bits, and active ordinary cache pattern bytes versus linked assets. Excludes fades, zone switches, wheel animation overrides, visible placement and unsampled frames. Borrowed entry checks include offscreen ring entries.')
