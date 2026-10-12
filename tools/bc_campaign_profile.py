"""Read-only complete-scene attribution for a window of the controller pilot."""
import bisect
import ctypes as C
import hashlib
import json
import subprocess
from pathlib import Path
import numpy as np
from run_rom import ROOT, CORE
from bc_scene_boundary import scene_boundary

class CampaignProfile:
    def __init__(self, runner, start_tick, calls, output, rom_path=None):
        assert start_tick >= 0 and calls > 0
        assert hashlib.sha256(CORE.read_bytes()).hexdigest() == '20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
        self.r=runner; self.start=start_tick; self.calls=calls; self.out=output
        self.active=False; self.done=False; self.rows=[]; self.errors=[]; self.pending=None
        rom_path=Path(rom_path) if rom_path is not None else ROOT/'out/release/rom.bin'
        self.rom=rom_path.read_bytes(); self.digest=hashlib.sha256(self.rom).hexdigest()
        self.symbols=sorted((int(v[0],16),v[2]) for line in (rom_path.parent/'symbol.txt').read_text().splitlines()
            if len(v:=line.split())>=3 and v[1] in ('t','T') and int(v[0],16)<0x400000)
        self.entry,self.returns,self.boundary_scope=scene_boundary(self.symbols,runner.symbols,self.rom,rom_path)
        self.cpu=C.addressof(C.c_uint8.in_dll(runner.lib,'m68k'))
        self.budget=C.c_uint32.in_dll(runner.lib,'mcycles_vdp').value
        assert self.budget==896040 and C.c_uint16.in_dll(runner.lib,'lines_per_frame').value==262
        assert C.c_uint32.from_address(self.cpu+0x29c8).value==0x100000
        output.mkdir(parents=True,exist_ok=True)
        library=output/'campaign-hook.dylib'
        subprocess.run(['cc','-O2','-dynamiclib',str(ROOT/'tools/bc_profile_hook.c'),'-o',str(library)],check=True)
        self.h=C.CDLL(str(library));self.h.profile_begin.argtypes=[C.c_void_p]*3
        self.h.profile_phase.argtypes=[C.c_void_p];self.h.profile_only.argtypes=[C.c_int]
        self.Callback=C.CFUNCTYPE(None)
        self.h.profile_watch.argtypes=[C.POINTER(C.c_uint32),C.c_uint,self.Callback]
        self.phase=C.c_uint8(0);self.totals=(C.c_uint64*256).in_dll(self.h,'phase_cycles')
        self.callback=self.Callback(self.watch)
        self.pcs=(C.c_uint32*(1+len(self.returns)))(self.entry,*self.returns)

    def clock(self):
        return self.r.frames*self.budget+C.c_uint32.from_address(self.cpu+0x280c).value

    def watch(self):
        if self.errors or len(self.rows)>=self.calls:return
        try:
            pc=(C.c_uint32.from_address(self.cpu+0x2858).value-2)&0xffffff
            if pc==self.entry:
                assert self.pending is None
                self.pending=(self.clock(),self.totals[1],self.r.u32('dbg_bc_native_ticks'))
                self.phase.value=1
            else:
                assert pc in self.returns
                self.phase.value=0
                if self.pending is None:return
                clock,total,tick=self.pending;now=self.r.u32('dbg_bc_native_ticks')
                assert now-tick in (0,1)
                self.rows.append(dict(start_tick=tick,end_tick=now,scene_ticks=self.clock()-clock,
                    attributed_ticks=self.totals[1]-total))
                self.pending=None
        except BaseException as e:
            self.errors.append(repr(e));self.phase.value=0

    def poll(self):
        if self.done:return
        if not self.active and self.r.u32('dbg_bc_native_ticks')>=self.start:
            base=C.cast(self.r.lib.m68k_get_reg,C.c_void_p).value-0x55aac
            assert self.h.profile_begin(self.cpu,base+0x1fefb0,base+0x1719c0)==0
            self.h.profile_phase(C.byref(self.phase));self.h.profile_only(2)
            assert self.h.profile_watch(self.pcs,len(self.pcs),self.callback)==0
            self.active=True;self.start_frame=self.r.frames
        if self.errors:
            self.h.profile_end();self.active=False
            raise AssertionError(self.errors)
        if len(self.rows)==self.calls:
            self.h.profile_end();self.active=False;self.done=True
            hist=np.ctypeslib.as_array((C.c_uint64*0x200000).in_dll(self.h,'instruction_cycles')).copy()
            addresses=[at for at,name in self.symbols];counts={}
            for i in np.nonzero(hist)[0]:
                name=self.symbols[bisect.bisect_right(addresses,int(i)*2)-1][1]
                counts[name]=counts.get(name,0)+int(hist[i])
            values=[x['scene_ticks'] for x in self.rows]
            result=dict(rom_sha256=self.digest,start_tick=self.start,completed_calls=len(self.rows),
                stop_video_frame=self.r.frames,elapsed_video_frames=self.r.frames-self.start_frame,
                stop_tick=self.r.u32('dbg_bc_native_ticks'),ram_sha256=hashlib.sha256(bytes(self.r.ram)).hexdigest(),
                mean_scene_ticks=float(np.mean(values)),maximum_scene_ticks=max(values),
                over_budget=sum(v>self.budget for v in values),frame_budget_core_ticks=self.budget,
                scope=self.boundary_scope+'; excludes outer input and video/VBlank/DMA work',
                replay_verified=False,full_speed_verified=False,rows=self.rows,
                functions=[dict(name=n,attributed_ticks=v) for n,v in sorted(counts.items(),key=lambda x:-x[1])])
            (self.out/'profile.json').write_text(json.dumps(result,indent=2)+'\n')
            np.save(self.out/'scene-cycles.npy',hist)
