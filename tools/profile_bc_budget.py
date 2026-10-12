#!/usr/bin/env python3
"""Measure complete BC scene calls against the pinned core's video-frame budget.

Host-only instruction hooks leave the cartridge and emulated CPU speed intact.
Scene timing excludes input handling and the outer VBlank/DMA processing, so
fitting this budget alone is not proof of full-speed gameplay.
"""
import argparse
import bisect
import ctypes as C
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
import numpy as np
from run_rom import ROOT, CORE, Runner, PAD
from bc_scene_boundary import scene_boundary
from scheduler_policy import entry_policy, process_policy
from bc_weapon_layout import normalize_player, beam_rotation, beam_velocity_shift, player_layout

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--rom',type=Path,default=ROOT/'out/release/rom.bin')
p.add_argument('--enemy-velocity-shift',type=int,choices=(0,8),default=None,help='Normalize scaled long enemy velocities and 54-byte actor records')
p.add_argument('--enemy-coordinate-shift',type=int,choices=(0,8),default=None,help='Normalize enemy storage to source 16.8 for cross-layout state comparisons')
p.add_argument('--state-bytes',action='store_true',help='Save normalized traced state records to simulation.bin for mismatch diagnosis')
p.add_argument('--state-trace',action='store_true',help='Hash actors, stage and party state at every completed scene; exclude transient pointers')
p.add_argument('--workload-trace',action='store_true',help='Read live object, weapon record and SAT counts after each scene')
p.add_argument('--video-trace',action='store_true',help='Hash VDP memories after each completed VBlank process')
p.add_argument('--players',type=int,choices=range(1,5),default=4)
p.add_argument('--round',type=int,choices=range(1,11),default=10)
p.add_argument('--warmup',type=int,default=1000)
p.add_argument('--updates',type=int,default=1000,help='Completed scene/frame calls to measure; catch-up frames can contain multiple simulation updates')
p.add_argument('--charge',action='store_true')
p.add_argument('--vulnerable',action='store_true',help='Use normal damage and respawns instead of debug protection')
p.add_argument('--hucard',action='store_true',help='Select HuCard through Home Options before the native fixture')
p.add_argument('--scheduler-detail-tick',type=int,help='Record native instructions/registers inside the scheduler call at this completed tick')
p.add_argument('--output',type=Path,required=True)
p.add_argument('--capture-frame',action='store_true',help='Save the final native video frame for visual inspection')
p.add_argument('--actor-cache-audit',action='store_true',help='Observe art-cache key changes and attribute-only changes ignored by the pose mapper')
p.add_argument('--actor-handler-audit',action='store_true',help='Read-only end-of-update handler/state/timer inventory; not per-handler CPU attribution')
p.add_argument('--background-audit',action='store_true',help='Verify visible BC background tiles after VBlank processing, every 32 updates')
p.add_argument('--background-audit-every',type=int,default=32,help='Simulation-update interval for the optional background audit')
p.add_argument('--background-palette-audit',action='store_true',help='Also verify all background CRAM colors during unfaded gameplay; requires --background-audit')
p.add_argument('--color-mode',choices=('standard','vivid'),help='Set the native debug fixture color mode before round initialization')
p.add_argument('--r7-steering',action='store_true',help='Round7 scenery fixture: steer upward past the later floor obstruction')
p.add_argument('--contact-grid-audit',action='store_true',help='Measure extra conservative spatial rejection opportunities without changing collision handling')
p.add_argument('--sprite-scanline-audit',action='store_true',help='Read post-upload SAT scanline demand without changing sprite rendering')
p.add_argument('--sprite-plane-trace',action='store_true',help='Hash the unlimited sprite plane at each scanline-audit sample')
p.add_argument('--sprite-crop-inventory',action='store_true',help='Inventory transparent outer sprite tile rows/columns during the scanline audit')
p.add_argument('--focus-tick',type=int,help='Attribute instructions only for the scene starting at this simulation tick')
p.add_argument('--verify-replay',action='store_true',help='Compare final RAM with a separate uninstrumented replay')
p.add_argument('--replay-frames',type=int,help=argparse.SUPPRESS)
p.add_argument('--beam-storage-rotate',type=int,choices=(0,8),help='Native projectile layout override for archived ROMs without a matching header')
p.add_argument('--beam-velocity-shift',type=int,choices=(0,8),help='Native projectile velocity layout override')
a=p.parse_args();assert a.warmup>=0 and a.updates>0 and a.background_audit_every>0
assert not a.r7_steering or a.round==7
assert not a.background_palette_audit or a.background_audit
assert not a.sprite_plane_trace or a.sprite_scanline_audit
assert not a.sprite_crop_inventory or a.sprite_scanline_audit
layout_header=a.rom.resolve().parent/'bc_rules.h'
if not layout_header.exists() and a.rom.resolve()==(ROOT/'out/release/rom.bin').resolve():
    layout_header=ROOT/'inc/bc_rules.h'
if not layout_header.exists() and (a.enemy_coordinate_shift is None or a.enemy_velocity_shift is None or a.beam_storage_rotate is None or a.beam_velocity_shift is None):
    p.error('Archived ROM requires its matching bc_rules.h, or all explicit enemy-coordinate, enemy-velocity, beam-storage and beam-velocity layout values')
layout=layout_header.read_text() if layout_header.exists() else ''
if a.beam_velocity_shift is None:
    try:a.beam_velocity_shift=beam_velocity_shift(a.rom)
    except ValueError as error:p.error(str(error))
player_abi=player_layout(a.beam_velocity_shift)
for attribute,macro in [('enemy_coordinate_shift','BC_ENEMY_STORAGE_SHIFT'),('enemy_velocity_shift','BC_ENEMY_VELOCITY_SHIFT'),('beam_storage_rotate','BC_BEAM_STORAGE_ROTATE')]:
    if getattr(a,attribute) is None:
        if attribute=='beam_storage_rotate':
            try:a.beam_storage_rotate=beam_rotation(a.rom)
            except ValueError as error:p.error(str(error))
            continue
        match=re.search(r'^#define '+macro+r' (0|8)$',layout,re.M)
        setattr(a,attribute,int(match[1]) if match else 0)
a.output.mkdir(parents=True,exist_ok=True)
if a.state_bytes:
    assert a.state_trace, '--state-bytes requires --state-trace'
    (a.output/'simulation.bin').write_bytes(b'')
if a.state_trace:
    validation_inc=a.rom.resolve().parent/'inc'
    if not (validation_inc/'bc_player.h').exists():validation_inc=ROOT/'inc'
    subprocess.run([str(Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'),'-m68000',
        '-I'+str(validation_inc),'-x','c','-fsyntax-only','-'],input=f'''#include "bc_player.h"
#include "bc_stage.h"
_Static_assert(sizeof(BcPlayerControl)=={player_abi["player_bytes"]},"player trace ABI");
_Static_assert(__builtin_offsetof(BcPlayerControl,world.weapons.shots)==8,"projectile pool offset");
_Static_assert(sizeof(BcShot)=={player_abi["shot_bytes"]},"projectile stride");
_Static_assert(__builtin_offsetof(BcShot,body.x)==0 && __builtin_offsetof(BcShot,body.y)==4,"projectile axes");
_Static_assert(__builtin_offsetof(BcWorldPlayer,shot_index)=={player_abi["pointer_start"]},"first transient pointer");
_Static_assert(__builtin_offsetof(BcWorldPlayer,party)=={player_abi["pointer_start"]+4},"second transient pointer");
_Static_assert(sizeof(BcActor)==50 || sizeof(BcActor)==54,"actor trace ABI");
_Static_assert(sizeof(BcStage)==24,"stage trace ABI");
''',text=True,check=True)
assert hashlib.sha256(CORE.read_bytes()).hexdigest()=='20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
rom_path=a.rom.resolve();rom=rom_path.read_bytes();digest=hashlib.sha256(rom).hexdigest()
r=Runner(rom=rom_path);r.run(2600)
if a.hucard:
    def tap(button):r.run(5,PAD[button]);r.run(20)
    assert r.u32('flow_state')==0
    tap('DOWN');tap('A');assert r.u32('flow_state')==9
    for _ in range(3):tap('DOWN')
    tap('A');assert r.u32('flow_state')==1
    for _ in range(8):tap('DOWN')
    tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
    tap('B');assert r.u32('flow_state')==9
    assert r.read('music_source',1)==b'\1'
if a.color_mode is not None:
    r.write('color_mode', bytes([int(a.color_mode == 'vivid')]))
if a.workload_trace:
    from workload_metrics import WorkloadMetrics
    workload=WorkloadMetrics(r,a.players)
for key,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',a.round-1),('dbg_bc_native_protect',0 if a.vulnerable else 1),('dbg_bc_native',1)]:
    r.write(key,value.to_bytes(2,'big'))
r.write('dbg_pad_override',b'\1')
def step():
    tick=r.u32('dbg_bc_native_ticks');period,held=(100,80) if a.charge else (40,20)
    bits=0x20 if tick%period<held else 0
    if a.r7_steering:
        camera_x=r.u16('dbg_bc_native_camera');y=r.u16('dbg_bc_native_position',2)
        target=72 if camera_x>1950 else 120
        bits|=8 if y>target+2 else 4 if y<target-2 else 0
    r.write('pad',bytes([bits,bits if tick%period==0 else 0]*a.players+[0,0]*(4-a.players)))
    r.run(1)
    assert r.u16('dbg_bc_native_status') in (0,4)
for _ in range(a.warmup*8+500):
    if r.u32('dbg_bc_native_ticks')>=a.warmup:break
    step()
else:raise AssertionError('warmup timed out')
if a.replay_frames is not None:
    for _ in range(a.replay_frames):step()
    print(json.dumps(dict(frames=r.frames,tick=r.u32('dbg_bc_native_ticks'),ram_sha256=hashlib.sha256(bytes(r.ram)).hexdigest())))
    raise SystemExit(0)
measurement_start=r.frames
frame_budget=C.c_uint32.in_dll(r.lib,'mcycles_vdp').value
lines=C.c_uint16.in_dll(r.lib,'lines_per_frame').value
assert frame_budget==896040 and lines==262 and C.c_uint8.in_dll(r.lib,'vdp_pal').value==0
cpu=C.addressof(C.c_uint8.in_dll(r.lib,'m68k'))
assert C.c_uint32.from_address(cpu+0x29c8).value==0x100000,'core clock scale changed'
symbols=sorted((int(v[0],16),v[2]) for line in (rom_path.parent/'symbol.txt').read_text().splitlines()
    if len(v:=line.split())>=3 and v[1] in ('t','T') and int(v[0],16)<0x400000)
addresses=[s[0] for s in symbols]
entry,returns,boundary_scope=scene_boundary(symbols,r.symbols,rom,rom_path)
library=a.output/'budget-hook.dylib'
subprocess.run(['cc','-O2','-dynamiclib',str(ROOT/'tools/bc_profile_hook.c'),'-o',str(library)],check=True)
h=C.CDLL(str(library));h.profile_begin.argtypes=[C.c_void_p]*3;h.profile_phase.argtypes=[C.c_void_p]
h.profile_only.argtypes=[C.c_int]
h.profile_trace.argtypes=[C.c_int,C.c_void_p,C.c_void_p]
Callback=C.CFUNCTYPE(None)
h.profile_watch.argtypes=[C.POINTER(C.c_uint32),C.c_uint,Callback]
base=C.cast(r.lib.m68k_get_reg,C.c_void_p).value-0x55aac
rows=[];pending=None;errors=[]
actor_cache_before=None
actor_cache_audit=dict(changed_keys=0,irrelevant_attribute_only_changes=0,slots={})
actor_handler_audit={}
if a.actor_handler_audit:
    from bc_actor_layout import read_actor_pool

def observe_actor_handlers():
    pool=read_actor_pool(r,rom=a.rom)
    for at in range(0,len(pool),50):
        actor=pool[at:at+50];state=actor[20]
        if not state:continue
        handler=int.from_bytes(actor[30:32] if state==128 else actor[32:34],'big')
        key=f'{handler:04x}:{state:02x}'
        row=actor_handler_audit.setdefault(key,dict(handler=handler,state=state,observations=0,
            animation_due_next=0,phase_one=0,wait_one=0,moving_x=0,moving_y=0,move_delayed=0))
        row['observations']+=1;row['animation_due_next']+=actor[21]==1
        row['phase_one']+=actor[43]==1;row['wait_one']+=actor[42]==1
        row['moving_x']+=bool(int.from_bytes(actor[8:10],'big'))
        row['moving_y']+=bool(int.from_bytes(actor[10:12],'big'))
        row['move_delayed']+=bool(actor[23])
background_audit=None
sprite_scanline_audit=None
if a.sprite_scanline_audit:
    from sprite_scanline_audit import SpriteScanlineAudit
    sprite_scanline_audit=SpriteScanlineAudit(r,a.output/'sprite-scanline',plane_trace=a.sprite_plane_trace,crop_inventory=a.sprite_crop_inventory)
contact_grid_audit=None
if a.contact_grid_audit:
    from bc_contact_grid_audit import ContactGridAudit
    contact_grid_audit=ContactGridAudit(r,rom)
contact_grid_pcs=[] if contact_grid_audit is None else [contact_grid_audit.pc]
if a.background_audit:
    from bc_live_background_audit import LiveBackgroundAudit
    background_audit=LiveBackgroundAudit(r,rom,a.round,a.background_audit_every,palette=a.background_palette_audit)
def observe_actor_cache():
    return r.read('art_cache',32*20)
if a.actor_cache_audit:
    assert 'art_cache' in r.symbols
    assert 'sizeof(ActorArtCache) == 20' in (ROOT/'src/bc_actor_draw.c').read_text()
scheduler_rows=[]
scheduler_entries=[at for at,name in symbols if name.startswith('SYS_doVBlankProcessEx')]
assert scheduler_entries
scheduler_policies = {at: entry_policy(rom, at, r.symbols.get('VDP_waitVBlank'))
                      for at in scheduler_entries}
video_complete_entries=[at for at,name in symbols if name=='JOY_update']
assert len(video_complete_entries)==1
scene_start_vtimer=None
scheduler_pending=None
scheduler_return=None
detail_started=False
r.lib.m68k_get_reg.argtypes=[C.c_uint]
r.lib.m68k_get_reg.restype=C.c_uint
phase=C.c_uint8(0);totals=(C.c_uint64*256).in_dll(h,'phase_cycles')
def state_hash():
    # Canonical ABI retains original pointer positions after normalization.
    stride=54 if a.enemy_velocity_shift else 50
    actors=bytearray(r.read('actors',stride*32))
    if a.enemy_coordinate_shift:
        for offset in range(0,len(actors),stride):
            for axis in (0,4):
                pos=offset+axis
                value=int.from_bytes(actors[pos:pos+4],'big')
                assert value & 255 == 0, ('nonzero aligned fraction padding',offset//stride,axis,value)
                actors[pos:pos+4]=(value >> a.enemy_coordinate_shift).to_bytes(4,'big')
    if a.enemy_velocity_shift:
        canonical=bytearray()
        for offset in range(0,len(actors),stride):
            raw=actors[offset:offset+stride]
            canonical.extend(raw[:8])
            for at in (8,12):
                value=int.from_bytes(raw[at:at+4],'big',signed=True)
                assert value%256==0 and -8388608<=value<=8388352, ('scaled velocity',offset//stride,at,value)
                canonical.extend((value//256).to_bytes(2,'big',signed=True))
            canonical.extend(raw[16:])
        actors=canonical
    parts=[bytes(actors),r.read('stage',24)]
    def player_bytes(address):
        raw=bytes(r.ram[((address+i)&65535)^1] for i in range(player_abi["player_bytes"]))
        raw=normalize_player(raw,a.beam_storage_rotate,a.beam_velocity_shift)
        return raw[:1000]+raw[1008:]
    parts.append(player_bytes(r.symbols['player']))
    peers=r.u32('peers')
    for i in range(a.players-1):parts.append(player_bytes(peers+i*player_abi["player_bytes"]))
    raw=b''.join(parts)
    if a.state_bytes:
        with (a.output/'simulation.bin').open('ab') as stream:stream.write(raw)
    return hashlib.sha256(raw).hexdigest()
def clock():return r.frames*frame_budget+C.c_uint32.from_address(cpu+0x280c).value
@Callback
def watch():
    global pending,scene_start_vtimer,scheduler_pending,scheduler_return,detail_started,actor_cache_before
    if errors or len(rows)>=a.updates:return
    try:
        pc=(C.c_uint32.from_address(cpu+0x2858).value-2)&0xffffff
        if pc in contact_grid_pcs:
            contact_grid_audit.observe()
            return
        if pc in video_complete_entries:
            if scheduler_pending is not None:
                # SGDK calls JOY_update only after DMA, scroll, palette,
                # user VBlank callback and optional frame-load VDP writes.
                # A null callback or a verified single RTS cannot draw later.
                # The archived first multitap fix installed a no-op callback.
                if 'joyEventCB' in r.symbols:
                    callback = r.u32('joyEventCB')
                    assert callback == 0 or (0 < callback < len(rom)-1 and
                                             rom[callback:callback+2] == b'\x4e\x75')
                scheduler_pending.update(video_end_scanline=C.c_uint16.in_dll(r.lib,'v_counter').value,
                                         video_end_vtimer=r.u32('vtimer'))
                if background_audit is not None:background_audit.observe()
                if sprite_scanline_audit is not None:sprite_scanline_audit.observe()
            return
        if pc==scheduler_return:
            if scheduler_pending['tick']==a.scheduler_detail_tick:
                h.profile_trace(0,None,None)
            scheduler_pending.update(end_scanline=C.c_uint16.in_dll(r.lib,'v_counter').value,
                end_vtimer=r.u32('vtimer'),elapsed_ticks=clock()-scheduler_pending.pop('start_clock'))
            if a.video_trace:
                memories=b''.join(bytes((C.c_uint8*size).in_dll(r.lib,name))
                    for name,size in (('vram',65536),('cram',128),('vsram',128)))
                scheduler_pending['video_sha256']=hashlib.sha256(memories).hexdigest()
            scheduler_rows.append(scheduler_pending)
            scheduler_pending=None;scheduler_return=None
            assert h.profile_watch(pcs,len(pcs),watch)==0
            return
        if pc in scheduler_entries:
            sp=r.lib.m68k_get_reg(15)&0xffff
            scheduler_return=int.from_bytes(bytes(r.ram[((sp+i)&0xffff)^1] for i in range(4)),'big')
            assert 0<scheduler_return<len(rom)
            scheduler_pending=dict(entry_pc=pc,tick=r.u32('dbg_bc_native_ticks'),
                process_time_stack=int.from_bytes(bytes(r.ram[((sp+4+i)&65535)^1]for i in range(4)),'big'),
                scanline=C.c_uint16.in_dll(r.lib,'v_counter').value,
                dma_queue_bytes=r.u16('queueTransferSize'),dma_queue_operations=r.u16('queueIndex'),vtimer=r.u32('vtimer'),
                scene_start_vtimer=scene_start_vtimer,start_clock=clock())
            scheduler_pending['process_time'] = process_policy(
                scheduler_policies[pc], scheduler_pending['process_time_stack'])
            scheduler_pending['process_time_source'] = scheduler_policies[pc][0]
            if scheduler_pending['tick']==a.scheduler_detail_tick and not detail_started:
                h.profile_trace(1,C.addressof(C.c_uint16.in_dll(r.lib,'v_counter')),
                                C.cast(r.lib.m68k_get_reg,C.c_void_p))
                detail_started=True
            dynamic=(C.c_uint32*(len(pcs)+1))(*pcs,scheduler_return)
            assert h.profile_watch(dynamic,len(dynamic),watch)==0
            return
        if pc==entry:
            if a.actor_cache_audit:actor_cache_before=observe_actor_cache()
            scene_start_vtimer=r.u32('vtimer')
            assert pending is None,'nested scene entry'
            pending=(clock(),totals[1],r.u32('dbg_bc_native_ticks'))
            h.profile_only(2 if a.focus_tick is None or pending[2]==a.focus_tick else 0)
            phase.value=1
        else:
            assert pc in returns
            phase.value=0
            if pending is None:return # profiler began during an incomplete call
            elapsed=clock()-pending[0];attributed=totals[1]-pending[1]
            tick=r.u32('dbg_bc_native_ticks');advanced=tick-pending[2]
            if tick==a.scheduler_detail_tick and not detail_started:
                h.profile_trace(1,C.addressof(C.c_uint16.in_dll(r.lib,'v_counter')),
                                C.cast(r.lib.m68k_get_reg,C.c_void_p))
                detail_started=True
            # The shared frame scheduler can execute up to eight BC updates
            # before returning. Keep legacy scene boundaries limited to one.
            maximum_updates = 8 if 'game_frame' in r.symbols and 'dbg_bc_catchup_batches' in r.symbols else 1
            assert elapsed>0 and attributed>0 and 0 <= advanced <= maximum_updates,(elapsed,attributed,advanced)
            rows.append(dict(start_tick=pending[2],tick=tick,simulation_updates=advanced,scene_ticks=elapsed,attributed_ticks=attributed))
            if a.state_trace:rows[-1]['simulation_sha256']=state_hash()
            if a.actor_handler_audit:observe_actor_handlers()
            if a.workload_trace:rows[-1]['workload']=workload.sample('bc')
            if a.actor_cache_audit:
                after=observe_actor_cache()
                for slot in range(32):
                    start=slot*20
                    prior=actor_cache_before[start:start+8];current=after[start:start+8]
                    if prior==current:continue
                    actor_cache_audit['changed_keys']+=1
                    prior_word=int.from_bytes(prior[:4],'big');current_word=int.from_bytes(current[:4],'big')
                    if prior[4:]==current[4:] and (prior_word^current_word)&0xffff880f==0:
                        actor_cache_audit['irrelevant_attribute_only_changes']+=1
                        actor_cache_audit['slots'][slot]=actor_cache_audit['slots'].get(slot,0)+1
            pending=None
            if len(rows)==a.updates:h.profile_only(0)
    except BaseException as error:
        errors.append(repr(error));phase.value=0
pcs=(C.c_uint32*(1+len(returns)+len(scheduler_entries)+len(video_complete_entries)+len(contact_grid_pcs)))(entry,*returns,*scheduler_entries,*video_complete_entries,*contact_grid_pcs)
assert len(pcs)<64
assert h.profile_begin(cpu,base+0x1fefb0,base+0x1719c0)==0
h.profile_phase(C.byref(phase));h.profile_only(2)
assert h.profile_watch(pcs,len(pcs),watch)==0
try:
    for _ in range(a.updates*8+500):
        step()
        if errors:raise AssertionError(errors)
        if len(rows)>=a.updates:break
    else:raise AssertionError('complete scene-call measurement timed out')
finally:h.profile_end()
assert hashlib.sha256(rom_path.read_bytes()).hexdigest()==digest,'ROM changed'
hist=np.ctypeslib.as_array((C.c_uint64*0x200000).in_dll(h,'instruction_cycles')).copy()
counts={}
for i in np.nonzero(hist)[0]:
    name=symbols[bisect.bisect_right(addresses,int(i)*2)-1][1]
    counts[name]=counts.get(name,0)+int(hist[i])
values=np.array([v['scene_ticks'] for v in rows],dtype=np.int64)
summary=dict(mean=float(values.mean()),median=float(np.median(values)),p90=float(np.percentile(values,90)),
    p99=float(np.percentile(values,99)),maximum=int(values.max()),over_frame_budget=int((values>frame_budget).sum()))
replay=dict(frames=r.frames,tick=r.u32('dbg_bc_native_ticks'),ram_sha256=hashlib.sha256(bytes(r.ram)).hexdigest())
if a.verify_replay:
    command=[sys.executable,str(Path(__file__).resolve()),'--players',str(a.players),'--round',str(a.round),
        '--rom',str(rom_path),'--warmup',str(a.warmup),'--updates',str(a.updates),'--output',str(a.output),
        '--replay-frames',str(r.frames-measurement_start),'--enemy-coordinate-shift',str(a.enemy_coordinate_shift),'--enemy-velocity-shift',str(a.enemy_velocity_shift),'--beam-storage-rotate',str(a.beam_storage_rotate),'--beam-velocity-shift',str(a.beam_velocity_shift)]+(['--charge'] if a.charge else [])+(['--vulnerable'] if a.vulnerable else [])
    if a.hucard:command.append('--hucard')
    if a.r7_steering:command+=['--r7-steering']
    if a.color_mode is not None:command+=['--color-mode',a.color_mode]
    reference=subprocess.run(command,check=True,capture_output=True,text=True)
    assert json.loads(reference.stdout)==replay,('instrumented/native replay mismatch',replay,reference.stdout)
if a.focus_tick is not None:assert sum(v['start_tick']==a.focus_tick for v in rows)==1,'focus tick not measured'
late_blank=[v for v in scheduler_rows if 224<=v['scanline']<262 and
    v['scene_start_vtimer'] is not None and v['vtimer']!=v['scene_start_vtimer']]
result=dict(music_source='hucard' if a.hucard else 'arcade',scheduler=dict(calls=len(scheduler_rows),late_vblank_calls=len(late_blank),
    scope='Read-only scheduler entry observations; no claim that queued DMA fits remaining blank',
    rows=scheduler_rows),rom_sha256=digest,focus_tick=a.focus_tick,elapsed_video_frames=r.frames-measurement_start,
    beam_storage_rotate=a.beam_storage_rotate,beam_velocity_shift=a.beam_velocity_shift,enemy_velocity_shift=a.enemy_velocity_shift,enemy_coordinate_shift=a.enemy_coordinate_shift,replay_verified=a.verify_replay,end_state=replay,round=a.round,players=a.players,protected=not a.vulnerable,charged_fire=a.charge,
    completed_scene_calls=len(rows),simulation_updates=sum(v['simulation_updates'] for v in rows),
    frame_budget_core_ticks=frame_budget,scene_ticks=summary,
    mean_scene_frame_fraction=float(values.mean()/frame_budget),
    scope=boundary_scope+'; excludes outer-loop input and final video/VBlank/DMA work',
    full_speed_verified=False,rows=rows,
    functions=[dict(name=n,attributed_ticks=c) for n,c in sorted(counts.items(),key=lambda x:-x[1])])
if a.actor_cache_audit:
    result['actor_cache_audit']={**actor_cache_audit,
        'scope':'Observed before/after scene cache-key changes, not all cache misses; ignored attribute mask derived from current ordinary/boss pose mappers. No runtime change.'}
if a.actor_handler_audit:
    result['actor_handler_audit']=dict(rows=sorted(actor_handler_audit.values(),key=lambda v:-v['observations']),
        scope='Active actor snapshots after measured scene updates, with next-step animation timers. Actors born/retired within an update can be absent; these are not invocation counts or per-handler CPU costs. Canonical 50-byte actor decoding; no guest writes.')
if background_audit is not None:result['background_audit']=background_audit.result()
if sprite_scanline_audit is not None:result['sprite_scanline_audit']=sprite_scanline_audit.result()
if a.color_mode is not None:result['color_mode_fixture']=a.color_mode
if contact_grid_audit is not None:result['contact_grid_audit']=contact_grid_audit.result()
if a.r7_steering:result['input_fixture']='Round7 later-floor steering; all selected players receive the same primary-player route input'
if a.workload_trace:
    result['workload_scope']=workload.scope
    result['workload_abi']=workload.o
if a.scheduler_detail_tick is not None:
    class TraceRow(C.Structure):
        _fields_=[('pc',C.c_uint32),('clock',C.c_uint32),('scanline',C.c_uint32),('reg',C.c_uint32*16)]
    count=C.c_uint.in_dll(h,'instruction_trace_count').value
    assert count and not C.c_uint.in_dll(h,'instruction_trace_overflow').value, 'Missing or overflowing scheduler trace'
    trace=(TraceRow*8192).in_dll(h,'instruction_trace')
    detail=[]
    for row in trace[:count]:
        index=bisect.bisect_right(addresses,row.pc)-1
        detail.append(dict(pc=row.pc,clock=row.clock,scanline=row.scanline,registers=list(row.reg),
                           function=symbols[index][1]if index>=0 else '?',bytes=rom[row.pc:row.pc+16].hex()))
    (a.output/'scheduler-instructions.json').write_text(json.dumps(dict(rom_sha256=digest,
        tick=a.scheduler_detail_tick,instructions=detail),indent=2)+'\n')
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
np.save(a.output/'scene-cycles.npy',hist)
if a.capture_frame:r.capture(a.output/'frame.png')
print(json.dumps({k:v for k,v in result.items() if k not in ('rows','functions','scheduler')},indent=2))
for n,c in sorted(counts.items(),key=lambda x:-x[1])[:10]:print(f'{c:12d} {n}')
print('Scheduler entries / late VBlank:',len(scheduler_rows),len(late_blank))
