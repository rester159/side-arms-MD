"""Read-only post-upload SAT demand, not a count of visibly lost pixels.

Mode-5 traversal/size rules follow Genesis Plus GX core/vdp_render.c:
https://github.com/ekeeke/Genesis-Plus-GX/blob/master/core/vdp_render.c
The model uses the core's internal Y/size/link cache and VRAM X/attributes.
It excludes raster changes, transparent pixels, masking and layer occlusion.
"""
import ctypes as C
import numpy as np


class SpriteScanlineAudit:
    def __init__(self, runner, output=None, plane_trace=False, crop_inventory=False):
        self.r = runner
        self.output = output
        self.plane_trace = [] if plane_trace else None
        self.crop_inventory = {} if crop_inventory else None
        self.software_before = {name: runner.u32(name) for name in ('spr_dbg_dropped','spr_dbg_remap')}
        if output is not None:
            output.mkdir(parents=True, exist_ok=True)
        self.sat = (C.c_uint16*512).in_dll(runner.lib, 'sat')
        self.vram = C.cast(runner.vram, C.POINTER(C.c_uint16))
        self.reg = (C.c_uint8*32).in_dll(runner.lib, 'reg')
        self.last_tick = None
        self.samples = self.entry_over_samples = self.width_over_samples = 0
        self.entry_over_lines = self.width_over_lines = 0
        self.max_entries = self.max_width = 0
        self.worst = None

    def observe(self):
        r = self.r
        tick = r.u32('dbg_bc_native_ticks')
        if tick == self.last_tick:
            return
        self.last_tick = tick
        assert self.reg[12] & 1 and not self.reg[12] & 6, 'Expected H40 noninterlaced display'
        assert C.c_uint16.in_dll(r.lib, 'max_sprite_pixels').value == 320
        base = C.c_uint16.in_dll(r.lib, 'satb').value//2
        counts = np.zeros(224, dtype=np.int16)
        widths = np.zeros(224, dtype=np.int16)
        slots, link = [], 0
        for _ in range(80):
            q = link*4
            y = (self.sat[q] & 511)-128
            size = self.sat[q+1] >> 8
            height, width = 8+(size & 3)*8, 8+((size >> 2) & 3)*8
            x = (self.vram[base+q+3] & 511)-128
            slots.append(dict(slot=link,x=x,y=y,width=width,height=height,attr=self.vram[base+q+2]))
            lo, hi = max(0,y), min(224,y+height)
            if lo < hi:
                # The parser selects the first 20 Y-overlapping entries.
                # Offscreen X and transparent patterns still consume width.
                widths[lo:hi] += (counts[lo:hi] < 20)*width
                counts[lo:hi] += 1
            link = self.sat[q+1] & 127
            if link == 0 or link >= 80:
                break
        entry_lines, width_lines = int((counts>20).sum()), int((widths>320).sum())
        if self.plane_trace is not None or self.crop_inventory is not None:
            import hashlib
            raw = np.ctypeslib.as_array(r.vram).reshape(-1,2)[:,::-1].copy().ravel()
            plane = np.zeros((224,320), np.uint8)
            patterns = {}
            for s in slots:
                x, y, w, h, attr = (s[k] for k in ('x','y','width','height','attr'))
                x0,x1,y0,y1=max(0,x),min(320,x+w),max(0,y),min(224,y+h)
                if x0>=x1 or y0>=y1: continue
                key=(attr,w,h)
                if key not in patterns:
                    pixels=np.zeros((h,w),np.uint8)
                    for cx in range(w//8):
                        for cy in range(h//8):
                            at=(((attr&2047)+cx*(h//8)+cy)&2047)*32
                            tile=raw[at:at+32].reshape(8,4)
                            pixels[cy*8:cy*8+8,cx*8:cx*8+8]=np.stack((tile>>4,tile&15),-1).reshape(8,8)
                    if attr&0x800: pixels=pixels[:,::-1]
                    if attr&0x1000: pixels=pixels[::-1]
                    patterns[key]=np.where(pixels,pixels+((attr>>9)&0x70),0).astype(np.uint8)
                patch=patterns[key][y0-y:y1-y,x0-x:x1-x]
                if self.crop_inventory is not None:
                    # Normalize flips/palette to identify the source geometry.
                    # Count occurrences, not distinct ticks, and retain the
                    # first observed pattern for independent ROM matching.
                    pens=patterns[key]&15
                    if attr&0x1000: pens=pens[::-1]
                    if attr&0x800: pens=pens[:,::-1]
                    ys,xs=np.nonzero(pens)
                    if len(xs):
                        left,top=int(xs.min())//8*8,int(ys.min())//8*8
                        right,bottom=(int(xs.max())//8+1)*8,(int(ys.max())//8+1)*8
                        if (left,top,right,bottom)!=(0,0,w,h):
                            signature=f'{w}x{h}:'+hashlib.sha256(pens.tobytes()).hexdigest()
                            item=self.crop_inventory.setdefault(signature,dict(width=w,height=h,
                                crop=[left,top,right-left,bottom-top],pens_hex=pens.tobytes().hex(),
                                first_tick=tick,occurrences=0,pressured_occurrences=0))
                            item['occurrences']+=1
                            pressured=bool(((counts[y0:y1]>20)|(widths[y0:y1]>320)).any())
                            item['pressured_occurrences']+=int(pressured)
                            if pressured and self.output is not None and 'pressure_snapshot' not in item:
                                # One exact example per crop candidate, rather than
                                # assuming it appears in the global worst snapshot.
                                name='crop-'+signature.split(':')[1]+'-vram.bin'
                                (self.output/name).write_bytes(bytes(r.vram))
                                item['pressure_snapshot']=dict(tick=tick,
                                    camera=[r.u16('show_x'),r.u16('show_y')],
                                    sprites=slots,vram_file=name)
                target=plane[y0:y1,x0:x1]; selected=(patch!=0)&(target==0)
                target[selected]=patch[selected]
            if self.plane_trace is not None:
                self.plane_trace.append(dict(tick=tick,sha256=hashlib.sha256(plane.tobytes()).hexdigest()))
        entries, pixels = int(counts.max()), int(widths.max())
        if self.worst is None or (entries,pixels) > (self.worst['peak_entries'],self.worst['peak_selected_width']):
            self.worst = dict(tick=tick,camera=[r.u16('show_x'),r.u16('show_y')],
                              entry_over_lines=np.flatnonzero(counts>20).tolist(),
                              width_over_lines=np.flatnonzero(widths>320).tolist(),
                              peak_entries=entries,peak_selected_width=pixels,sprites=slots)
            if self.output is not None:
                # Native core byte order, paired with the exact SAT snapshot.
                (self.output/'worst-vram.bin').write_bytes(bytes(r.vram))
        self.max_entries = max(self.max_entries,entries)
        self.max_width = max(self.max_width,pixels)
        self.samples += 1
        self.entry_over_samples += bool(entry_lines)
        self.width_over_samples += bool(width_lines)
        self.entry_over_lines += entry_lines
        self.width_over_lines += width_lines

    def result(self):
        assert self.samples
        result = dict(samples=self.samples,max_entries_per_line=self.max_entries,
                    max_selected_width_per_line=self.max_width,
                    entry_over_limit_samples=self.entry_over_samples,
                    width_over_limit_samples=self.width_over_samples,
                    entry_over_limit_lines=self.entry_over_lines,
                    width_over_limit_lines=self.width_over_lines,worst=self.worst,
                    scope='Post-upload SAT bounding-box demand in H40 noninterlaced mode: 20 entries and 320 sprite pixels per line. Width covers first20 Y-overlapping entries, including offscreen X and transparent pixels. Over-limit demand is not a count of visibly lost pixels; excludes masking, layer occlusion and raster-time changes.')
        result['software_counter_deltas'] = {name:self.r.u32(name)-value for name,value in self.software_before.items()}
        if self.plane_trace is not None:
            result['unlimited_plane_trace'] = self.plane_trace
            result['plane_scope'] = 'Ideal sprite plane includes pens, palette and priority in original submission order, before background/window composition and without hardware limits/masking.'
        if self.crop_inventory is not None:
            result['crop_inventory'] = self.crop_inventory
            result['crop_scope'] = 'Visible sprite occurrences with wholly transparent outer tile rows/columns. Pressure is bounding-box overlap, not measured pixel recovery or a runtime performance claim.'
        return result
