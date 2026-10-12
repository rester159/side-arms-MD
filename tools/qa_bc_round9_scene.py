#!/usr/bin/env python3
"""Run all nine native encounters with protection and explicit forced defeats."""
import argparse
import hashlib
import json
import struct
from run_rom import ROOT,Runner
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--next-round',action='store_true')
parser.add_argument('--players',type=int,choices=(1,2,3,4),default=1)
a=parser.parse_args()
geometry=json.loads((ROOT/'res/generated/bc_boss_geometry.json').read_text())
r=Runner();r.run(2600)
for key,val in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',8),('dbg_bc_native_protect',1),('dbg_bc_native_hold_exit',1),('dbg_bc_native',1)]:
    r.write(key,struct.pack('>H',val))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8))
rom=(ROOT/'out/release/rom.bin').read_bytes()
out=ROOT/f'.local/bc-round9-scene-{a.players}p';out.mkdir(exist_ok=True)
seen=[];born=0;forced=False;checked=False;clear_start=None;clear_end=None
missing=drops=remaps=worst=0
for f in range(90000):
    r.run(1)
    status=r.u16('dbg_bc_native_status');tick=r.u32('dbg_bc_native_ticks')
    assert status in (0,4,6),(f,status,hex(r.u16('dbg_bc_native_handler')))
    missing=max(missing,r.u16('dbg_bc_native_actor_unmapped'))
    assert not missing,(f,tick,r.u16('dbg_bc_native_encounter'),'missing actor art')
    assert not r.u16('dbg_bc_native_unmapped')
    assert not r.u16('dbg_bc_native_resets')
    worst=max(worst,r.u16('prof_seg',6))
    encounter=r.u16('dbg_bc_native_encounter')
    if encounter and (not seen or encounter!=seen[-1]['encounter']):
        assert encounter==len(seen)+1
        seen.append(dict(encounter=encounter,tick=tick));born=tick;forced=checked=False
    if encounter and not checked and tick>=born+10:
        slots=[i for i,v in enumerate(r.read('slot_refs',56)) if v==255]
        assert len(slots)==geometry['capacity']
        bank='bc_boss_patterns' if encounter==1 else f'bc_boss{encounter}_patterns'
        address=r.symbols[bank]
        body_blocks=geometry['banks'][encounter-1]['block_count']
        checked_blocks=body_blocks
        for i,slot in enumerate(list(reversed(slots))[:checked_blocks]):
            at=(160+slot*16)*32
            source=address+i*512
            assert bytes(r.vram[(at+j)^1] for j in range(512))==rom[source:source+512],(encounter,i)
        checked=True
    if encounter and not forced and tick>=born+700:
        r.capture(out/f'encounter-{encounter}.png')
        r.write('dbg_bc_native_boss_defeat',b'\0\1');forced=True
    phase=r.u16('dbg_bc_native_round_exit')
    if phase==2 and clear_start is None:clear_start=r.u32('frame_counter')
    if status==6:
        clear_end=r.u32('frame_counter');break
assert len(seen)==9 and clear_end is not None,seen
assert clear_end-clear_start==421
assert r.u16('dbg_bc_native_music_command')==0x2a
assert list(struct.unpack('>'+str(a.players)+'H',r.read('dbg_bc_native_party_lives',a.players*2)))==[3]*a.players
assert r.u16('player_limit')==a.players
assert r.u32('spr_dbg_dropped')==0 and r.u32('spr_dbg_remap')==0
result=dict(players=a.players,rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),encounters=seen,frames=f+1,native_updates=r.u32('dbg_bc_native_ticks'),worst_lines=worst,
            forced_defeats=True,clear_wait_updates=421,missing_art=missing,sprite_drops=0,runtime_remaps=0,
            full_speed_verified=False,next_round_loaded=False)
r.capture(out/'clear.png')
if a.next_round:
    score_refs=[('score',0)]+[('peer_scores',35*i) for i in range(a.players-1)]
    for i,(name,offset) in enumerate(score_refs):
        r.write(name,bytes([0,0,0,0,i+1,2,3,0,0,0,0,0,9,i+1,9,0]),offset)
    scores=[r.read(name,16,offset) for name,offset in score_refs]
    r.write('dbg_bc_native_hold_exit',b'\0\0')
    for _ in range(120):
        r.run(1)
        if r.u16('dbg_bc_native_current_round')==9 and r.u16('dbg_bc_native_status') in (0,4):break
    assert r.u16('dbg_bc_native_current_round')==9
    assert [r.read(name,16,offset) for name,offset in score_refs]==scores
    assert list(struct.unpack('>'+str(a.players)+'H',r.read('dbg_bc_native_party_lives',a.players*2)))==[3]*a.players
    assert r.u16('player_limit')==a.players
    target=r.u32('dbg_bc_native_ticks')+1800
    for _ in range(18000):
        r.run(1)
        assert r.u16('dbg_bc_native_status') in (0,4)
        assert not r.u16('dbg_bc_native_actor_unmapped')
        if r.u32('dbg_bc_native_ticks')>=target:break
    assert r.u32('dbg_bc_native_ticks')>=target
    assert r.u16('dbg_bc_native_background_active')
    assert struct.unpack('>2H',r.read('dbg_bc_native_camera',4))==(3840,2304)
    assert r.u16('dbg_bc_native_music_command')==0x36
    assert 255 not in r.read('slot_refs',56)
    assert r.u32('spr_dbg_dropped')==0 and r.u32('spr_dbg_remap')==0
    r.capture(out/'round10.png')
    result.update(next_round_loaded=True,score_preserved=True,lives_preserved=True,next_round_updates=1800)
r.write('dbg_bc_native',b'\0\0');r.run(120)
assert r.u32('flow_state')==0 and 255 not in r.read('slot_refs',56)
result['returned_to_menu']=True
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
