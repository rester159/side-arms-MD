#!/usr/bin/env python3
"""Measure stock-speed Boss Rush reached through Home's player modal.

This bounded assisted route supplies protection and steering. It does not prove
natural play, every boss, physical multiplayer adapters, or full-game speed.
Run serially with other Normal/qa_soak fixtures (shared offset build).
"""
import argparse
import ctypes as C
import hashlib
import json
import math
import os
import struct
from pathlib import Path
from run_rom import ROOT, Runner, PAD
from qa_soak import O
from profile_genesis import instruction_profile

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--players',type=int,choices=(1,2,3,4),required=True)
p.add_argument('--frames',type=int,default=3000)
p.add_argument('--profile',action='store_true')
p.add_argument('--scheduler-trace',action='store_true',help='Read-only DMA queue and scanline observations at scheduler entry')
p.add_argument('--video-trace',action='store_true',help='Hash every completed video frame for comparisons of identical routes')
p.add_argument('--verify-exit',action='store_true',help='Soft-reset after measurement and check wheel allocations were released')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();assert a.frames>0
a.output.mkdir(parents=True,exist_ok=True)
build=Path(os.environ.get('SIDEARMS_BUILD',ROOT))
digest=hashlib.sha256((build/'out/release/rom.bin').read_bytes()).hexdigest()
r=Runner()
def tap(button):r.run(5,PAD[button]);r.run(15)
r.run(2600);tap('DOWN');tap('START')
assert r.u32('flow_state')==9
tap('DOWN');tap('DOWN');tap('A')
assert r.read('player_dialog',1)==b'\1'
tap('DOWN');tap('B')
assert r.u32('flow_state')==9 and r.read('home_cfg',1,5)==b'\2'
tap('A')
for _ in range((a.players-2)%4):tap('DOWN')
tap('A')
assert r.u32('flow_state')==12 and r.u16('player_limit')==a.players
r.write('dbg_pad_override',b'\1')

def controls(tick):
    bits=[]
    for i in range(a.players):
        off=i*O['s_Player']
        r.write('players',b'\xc8',off+O['o_Player_invuln'])
        x=int.from_bytes(r.read('players',2,off+O['o_Player_x']),'big',signed=True)
        y=int.from_bytes(r.read('players',2,off+O['o_Player_y']),'big',signed=True)
        tx=48+i*24;ty=32+i*40+int(12*math.sin(tick/90+i))
        # Select the already-owned AUTO through ordinary C-button releases.
        # Holding fire with the initial BIT weapon would only launch once.
        b=0x20|(1 if x<tx-3 else 2 if x>tx+3 else 0)|(4 if y<ty-3 else 8 if y>ty+3 else 0)
        if r.read('players',1,off+O['o_Player_weapon'])!=b'\5' and (tick//4)%2==0:b|=0x40
        bits.extend([b,b])
    r.write('pad',bytes(bits+[0,0]*(4-a.players)))

for tick in range(1000):
    controls(tick);r.run(1)
    if r.read('rush_rs',1)==b'\1' and r.read('boss_hud',1)!=b'\0':break
else:raise AssertionError('Boss Rush did not reach first fight')
assert all(r.read('players',1,i*O['s_Player']+O['o_Player_in_play'])==b'\1' for i in range(a.players))
initial=r.u32('frame_counter');previous=initial;missed=0;worst=0
update_counts={}
multiple_update_samples=[]
start_drops=r.u32('spr_dbg_dropped');start_remaps=r.u32('spr_dbg_remap')
boss_indices=set();states=set();windows=[];window_updates=0
wheel_cache_frames=wheel_fallback_frames=0
wheel_heap=None
def heap_blocks():
    address=r.u32('heap')&65535;end=r.u32('heapEnd')&65535;blocks=[]
    while address<end:
        word=(r.ram[address^1]<<8)|r.ram[(address+1)^1]
        size=word&~1
        assert size>=2 and address+size<=end,('invalid heap block',address,word,end)
        blocks.append(dict(address=address,bytes=size-2,used=bool(word&1)))
        address+=size
    assert address==end
    return blocks
scheduler=[]
video_hashes=[]
watch=None
if a.scheduler_trace:
    pcs=[];labels={};symbols=[]
    for line in (build/'out/release/symbol.txt').read_text().splitlines():
        fields=line.split()
        if len(fields)>=3 and fields[1] in ('t','T'):
            address=int(fields[0],16);symbols.append((address,fields[2]))
            if fields[2].startswith('SYS_doVBlankProcessEx'):
                pcs.append(address);labels[address]='scheduler'
            elif fields[2]=='flushQueue':
                pcs.append(address);labels[address]='flush'
    rom=(build/'out/release/rom.bin').read_bytes()
    start=next(at for at,name in symbols if name.startswith('main.'))
    end=min(at for at,name in symbols if at>start)
    operand=struct.pack('>I',r.symbols['dbg_pad_override'])
    for at in range(start,end-5,2):
        if rom[at+2:at+6]==operand and (int.from_bytes(rom[at:at+2],'big')&0xf1ff)==0x1039:
            pcs.append(at);labels[at]='input'
    assert pcs
    cpu=C.addressof(C.c_uint8.in_dll(r.lib,'m68k'))
    def observe_scheduler():
        pc=(C.c_uint32.from_address(cpu+0x2858).value-2)&0xffffff
        scheduler.append(dict(kind=labels[pc],video_frame=r.frames,frame_counter=r.u32('frame_counter'),
            scanline=C.c_uint16.in_dll(r.lib,'v_counter').value,vtimer=r.u32('vtimer'),
            dma_bytes=r.u16('queueTransferSize'),dma_operations=r.u16('queueIndex'),
            dma_buffer_bytes=r.u32('nextDataBuffer')-r.u32('dmaDataBuffer'),
            dma_buffer_capacity=2*r.u16('dataBufferSize'),
            rush_index=r.read('rush_idx',1)[0],rush_state=r.read('rush_rs',1)[0],
            wheel_state=r.read('fr_state',1)[0],wheel_frame=r.u16('fr_shown')))
    watch=(pcs,observe_scheduler)
with instruction_profile(r,a.output/'cpu',enabled=a.profile,watch=watch):
    for tick in range(a.frames):
        controls(tick);r.run(1)
        if a.video_trace:video_hashes.append(hashlib.sha256(r.frame.tobytes()).hexdigest())
        assert r.u32('flow_state')==12,('left Boss Rush',tick,r.u32('flow_state'))
        current=r.u32('frame_counter');delta=(current-previous)&0xffffffff
        # The counter advances before VBlank scheduling, not at the emulator's
        # video boundary. A late completion followed by a short update after
        # VBlank can both fall in one video frame. Keep these visible rather
        # than treating every two-completion sample as memory corruption.
        assert delta<=2,('unexpected frame counter',delta)
        update_counts[delta]=update_counts.get(delta,0)+1
        if delta>1:
            multiple_update_samples.append(dict(video_frame=r.frames,previous=previous,current=current))
        missed+=not delta;window_updates+=delta;previous=current
        worst=max(worst,r.u16('prof_seg',6))
        boss_indices.add(r.read('rush_idx',1)[0]);states.add(r.read('rush_rs',1)[0])
        if r.read('fr_state',1)==b'\2':
            if wheel_heap is None:wheel_heap=heap_blocks()
            if r.u32('fr_img'):wheel_cache_frames+=1
            else:wheel_fallback_frames+=1
        if (tick+1)%600==0:
            windows.append(dict(frames=600,updates=window_updates));window_updates=0
if a.frames%600:windows.append(dict(frames=a.frames%600,updates=window_updates))
assert hashlib.sha256((build/'out/release/rom.bin').read_bytes()).hexdigest()==digest
r.capture(a.output/'end.png')
result=dict(rom_sha256=digest,players=a.players,emulated_frames=a.frames,
    updates=(previous-initial)&0xffffffff,missed_frames=missed,worst_lines=worst,
    update_count_histogram=update_counts,
    multiple_update_samples=multiple_update_samples,
    net_update_shortfall=a.frames-((previous-initial)&0xffffffff),
    boss_indices=sorted(boss_indices),rush_states=sorted(states),windows=windows,
    wheel_cache_frames=wheel_cache_frames,wheel_fallback_frames=wheel_fallback_frames,
    wheel_heap=wheel_heap,
    sprite_drops=r.u32('spr_dbg_dropped')-start_drops,
    runtime_remaps=r.u32('spr_dbg_remap')-start_remaps,
    protected=True,loadout='Boss Rush defaults; owned AUTO selected via C',
    instrumented=a.profile or a.scheduler_trace,instruction_profile=a.profile,
    ram_sha256=hashlib.sha256(bytes(r.ram)).hexdigest(),
    scope='Bounded assisted route through real Boss Rush modal; not all bosses or natural play',
    full_speed_in_sample=not missed,full_game_verified=False)
if a.scheduler_trace:
    (a.output/'scheduler.json').write_text(json.dumps(scheduler,indent=2)+'\n')
    result['scheduler_observations']=len(scheduler)
    flushes=[row for row in scheduler if row['kind']=='flush']
    assert flushes, 'DMA buffer audit requires observations before queue reset'
    assert all(0<=row['dma_buffer_bytes']<=row['dma_buffer_capacity'] for row in scheduler)
    buffer_peak=max(row['dma_buffer_bytes'] for row in flushes)
    result['dma_buffer_audit']=dict(
        scope='Measured fight route only; excludes boot, menus, entry and reset; successful allocations only',
        flushes=len(flushes),
        peak_bytes=buffer_peak,
        capacity_bytes=sorted({row['dma_buffer_capacity'] for row in flushes}),
        peak_rows=[row for row in flushes if row['dma_buffer_bytes']==buffer_peak][:8])
if a.video_trace:
    (a.output/'video-hashes.json').write_text(json.dumps(video_hashes)+'\n')
if a.verify_exit:
    r.write('pad',bytes([0xf0,0xf0]*a.players+[0,0]*(4-a.players)))
    r.run(1);r.write('pad',bytes(8));r.run(30)
    assert r.u32('flow_state')==0,('soft reset failed',r.u32('flow_state'))
    for name in ('fr_img','fr_slots','fr_cells'):
        if name in r.symbols:assert r.u32(name)==0,('wheel allocation retained',name)
    result['soft_reset_released_wheel_allocations']=True
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
raise SystemExit(1 if missed else 0)
