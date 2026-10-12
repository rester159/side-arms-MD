#!/usr/bin/env python3
"""Run final serpent with explicit protection/forced head deaths through ending handoff."""
import argparse
import hashlib
import json
import struct
from run_rom import ROOT, Runner
from bc_actor_layout import read_actor_pool

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--players',type=int,choices=(1,2,3,4),default=1)
a=parser.parse_args()
r=Runner();r.run(2600)
for key,val in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',9),('dbg_bc_native_protect',1),
                ('dbg_bc_native_hold_exit',1),('dbg_bc_native',1)]:
    r.write(key,struct.pack('>H',val))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8))
out=ROOT/f'.local/bc-round10-scene-{a.players}p';out.mkdir(exist_ok=True)
heads=[];born=0;forced=False;clear_start=None;clear_end=None;worst=0
for f in range(60000):
    r.run(1)
    status=r.u16('dbg_bc_native_status');tick=r.u32('dbg_bc_native_ticks')
    assert status in (0,4,6),(f,status,hex(r.u16('dbg_bc_native_handler')))
    assert not r.u16('dbg_bc_native_actor_unmapped')
    assert not r.u16('dbg_bc_native_unmapped') and not r.u16('dbg_bc_native_resets')
    if tick>10:worst=max(worst,r.u16('prof_seg',6))
    # Canonical QA actor: 50 bytes; body.state +20, role +48.
    pool=read_actor_pool(r,8)
    head=next((i for i in range(8) if pool[i*50+20]==0x80 and pool[i*50+48]==0x48 and struct.unpack_from('>H',pool,i*50+34)[0]==0x36d0),None)
    if head is not None and (not heads or head!=heads[-1]['slot']):
        assert head==len(heads),(head,heads,tick,[(pool[i*50+20],pool[i*50+48]) for i in range(8)])
        heads.append(dict(slot=head,tick=tick));born=tick;forced=False
        assert struct.unpack_from('>H',pool,head*50+34)[0]==0x36d0
    if head is not None and not forced and tick>=born+700:
        r.capture(out/f'head-{head}.png')
        r.write('dbg_bc_native_boss_defeat',b'\0\1');forced=True
    phase=r.u16('dbg_bc_native_round_exit')
    if phase==2 and clear_start is None:clear_start=r.u32('frame_counter')
    if status==6:
        clear_end=r.u32('frame_counter');break
assert len(heads)==6 and clear_end is not None,heads
assert clear_end-clear_start==421
assert r.u16('dbg_bc_native_music_command')==0x2c
assert list(struct.unpack('>'+str(a.players)+'H',r.read('dbg_bc_native_party_lives',a.players*2)))==[3]*a.players
assert r.u16('player_limit')==a.players
assert r.u32('spr_dbg_dropped')==0 and r.u32('spr_dbg_remap')==0
assert r.u16('dbg_bc_native_background_active')
assert 255 not in r.read('slot_refs',56)
assert struct.unpack('>2H',r.read('dbg_bc_native_camera',4))==(3840,2304)
r.capture(out/'ending-handoff.png')
result=dict(players=a.players,rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),heads=heads,frames=f+1,native_updates=r.u32('dbg_bc_native_ticks'),
            worst_lines=worst,forced_defeats=True,ending_wait_updates=421,
            sprite_drops=0,runtime_remaps=0,full_speed_verified=False,ending_presentation=False)
r.write('dbg_bc_native',b'\0\0');r.run(120)
assert r.u32('flow_state')==0
result['returned_to_menu']=True
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
