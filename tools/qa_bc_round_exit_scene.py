#!/usr/bin/env python3
"""Native clear sequence with an explicitly forced boss defeat and optional co-op."""
import argparse
import hashlib
import json
import struct
from run_rom import ROOT,Runner,PAD
from bc_actor_layout import read_actor_pool
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--round',type=int,choices=(1,2,3,4,5,6,7,8),default=1)
p.add_argument('--players',type=int,choices=(1,2,3,4),default=1)
p.add_argument('--hucard',action='store_true')
a=p.parse_args()
r=Runner();r.run(2600)
monitor=None
if a.hucard:
    def tap(button):r.run(5,PAD[button]);r.run(20)
    tap('DOWN');tap('A');assert r.u32('flow_state')==9
    for _ in range(3):tap('DOWN')
    tap('A');assert r.u32('flow_state')==1
    for _ in range(8):tap('DOWN')
    tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
    tap('B');assert r.u32('flow_state')==9 and r.read('music_source',1)==b'\1'
    from hucard_campaign_monitor import CampaignMusicMonitor
    monitor=CampaignMusicMonitor(r)
r.write('dbg_bc_native_players',struct.pack('>H',a.players))
r.write('dbg_pad_override',b'\x01')
r.write('dbg_bc_native_hold_exit',b'\0\1')
r.write('dbg_bc_native_start_round',struct.pack('>H',a.round-1))
r.write('dbg_bc_native_protect',b'\0\1');r.write('dbg_bc_native',b'\0\1')
budget=11000 if a.round==5 else 7500 if a.round>=3 else 5500
boss_family=json.loads((ROOT/'res/generated/bc_boss_geometry.json').read_text())['banks'][a.round-1]['family']
boss_seen=None
for _ in range(60000):
    tick=r.u32('dbg_bc_native_ticks')
    actor=read_actor_pool(r,1)
    ready=actor[20]==0x80 and int.from_bytes(actor[34:36],'big')==boss_family
    if ready and boss_seen is None:boss_seen=tick
    bits=0
    if a.round==3:
        y=r.u16('dbg_bc_native_camera',2);x=r.u16('dbg_bc_native_position')
        target=146 if 1150<y<1500 else 128
        bits=1 if x<target-2 else 2 if x>target+2 else 0
    if a.round==4:
        x=r.u16('dbg_bc_native_camera');y=r.u16('dbg_bc_native_position',2)
        target=72 if 1750<x<2220 else 120
        bits=8 if y>target+2 else 4 if y<target-2 else 0
    if a.round==7:
        x=r.u16('dbg_bc_native_camera');y=r.u16('dbg_bc_native_position',2)
        target=72 if x>1950 else 120
        bits |= 8 if y>target+2 else 4 if y<target-2 else 0
    if a.round==6:
        y=r.u16('dbg_bc_native_camera',2);x=r.u16('dbg_bc_native_position')
        target=170 if 400<y<1010 or y>1550 else 80
        bits=1 if x<target-2 else 2 if x>target+2 else 0
    # Co-op routes have expanded waves; use real controller fire until the
    # boss appears, instead of assuming the one-player fixed arrival tick.
    if a.players>1 and boss_seen is None and tick%40<20:bits|=0x20
    r.write('pad',bytes([bits,bits if tick%40==0 else 0]*a.players+[0,0]*(4-a.players)))
    r.run(1)
    assert r.u16('dbg_bc_native_status') in (0,4)
    now=r.u32('dbg_bc_native_ticks')
    if ready and boss_seen is not None and now>=boss_seen+120 and (a.players>1 or now>=budget):break
else:raise AssertionError(('boss not ready',a.round,a.players,r.u32('dbg_bc_native_ticks'),r.read('dbg_bc_native_camera',4).hex(),hex(r.u16('dbg_bc_native_handler')),actor.hex()))
assert boss_seen is not None
assert not r.u16('dbg_bc_native_resets'), 'Route restarted'
r.write('pad',bytes(8))
r.write('dbg_bc_native_boss_defeat',b'\0\1')
start=None;end=None;phases=[]
for elapsed in range(1400):
    r.run(1)
    phase=r.u16('dbg_bc_native_round_exit')
    if not phases or phases[-1]!=phase:phases.append(phase)
    if phase==2 and start is None:start=r.u32('frame_counter')
    if r.u16('dbg_bc_native_status')==6:
        end=r.u32('frame_counter');break
assert phases==[0,1,2,3],phases
assert start is not None and end-start==421,(start,end)
assert r.u16('dbg_bc_native_music_command')==0x2a
assert r.u16('dbg_bc_native_music_requests')==3
assert not r.u16('dbg_bc_native_boss_defeat')
assert not r.u16('dbg_bc_native_actor_unmapped')
assert r.u16('player_limit')==a.players
assert not r.u32('spr_dbg_dropped') and not r.u32('spr_dbg_remap')
out=ROOT/(('.local/bc-round-exit' if a.round==1 else f'.local/bc-round-exit-round{a.round}')+(f'-{a.players}p' if a.players>1 else '')+('-hucard' if a.hucard else ''));out.mkdir(exist_ok=True,parents=True)
r.capture(out/'clear-handoff.png')
r.write('dbg_bc_native',b'\0\0');r.write('dbg_pad_override',b'\0');r.run(120);assert r.u32('flow_state')==0
result=dict(round=a.round,players=a.players,rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),forced_boss_defeat=True,boss_first_seen_tick=boss_seen,route_updates=now,phases=phases,clear_wait_updates=end-start,music_command='0x2a',
            returned_to_menu=True,loader_handoff_reached=True,next_round_loaded=False)
if monitor:
    result['hucard_audio']=monitor.finish(out,False)
    assert not any(result['hucard_audio']['renderer_diagnostics']['counter_deltas'].values())
    assert not result['hucard_audio']['renderer_diagnostics']['maximum_unmapped']
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
