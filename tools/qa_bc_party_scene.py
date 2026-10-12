#!/usr/bin/env python3
"""Actual Genesis co-op inputs, artwork, shared simulation and individual respawn."""
import argparse
import json
import struct
from run_rom import ROOT,Runner
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--players',type=int,choices=(2,3,4),default=4);a=p.parse_args()
r=Runner();r.run(2600);original_limit=r.u16('player_limit')
for key,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',9),
                  ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(key,struct.pack('>H',value))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8))
out=ROOT/f'.local/bc-party-scene{a.players}';out.mkdir(exist_ok=True)
worst=0

def advance(updates):
    global worst
    target=r.u32('dbg_bc_native_ticks')+updates
    for _ in range(updates*8+500):
        r.run(1)
        assert r.u16('dbg_bc_native_status') in (0,4),(r.u16('dbg_bc_native_status'),hex(r.u16('dbg_bc_native_handler')))
        assert not r.u16('dbg_bc_native_unmapped') and not r.u16('dbg_bc_native_actor_unmapped')
        worst=max(worst,r.u16('prof_seg',6))
        if r.u32('dbg_bc_native_ticks')>=target:return
    r.capture(out/'stalled.png')
    raise AssertionError(('native update stalled',r.u32('dbg_bc_native_ticks'),r.u16('dbg_bc_native_status'),r.u16('dbg_bc_native_music_command'),r.u16('dbg_bc_native_music_requests'),r.u32('frame_counter')))
def positions():return [struct.unpack('>2H',r.read('dbg_bc_native_party_position',4,i*4)) for i in range(a.players)]
def lives():return list(struct.unpack('>'+str(a.players)+'H',r.read('dbg_bc_native_party_lives',a.players*2)))
advance(100)
assert r.u16('player_limit')==a.players and lives()==[3]*a.players
before=positions();r.write('pad',bytes([1,1,2,2,8,8,4,4]));advance(30);after=positions()
assert after[0][0]>before[0][0] and after[1][0]<before[1][0],(before,after)
if a.players>=3:assert after[2][1]<before[2][1]
if a.players==4:assert after[3][1]>before[3][1]
r.capture(out/'controllers.png')
r.write('pad',bytes([0x20,0x20]*a.players+[0,0]*(4-a.players)));advance(40)
r.capture(out/'firing.png')
# Verify the packed 32x16 strips use the exact ROM shot pixels, including
# transparent overlap priority. Normal 32x32 actors have a different SAT size.
rom=(ROOT/'out/release/rom.bin').read_bytes()
key=next(r['key'] for r in json.loads((ROOT/'res/generated/bc_player_projectile_shapes.json').read_text()) if r['source_pose']==0x1b8)
bank=struct.unpack_from('>H',rom,r.symbols['spr_bank_index']+key*2)[0]
assert bank&0x7fff
address=r.symbols['spr_bank']+((bank&0x7fff)-1)*128
source=rom[address:address+128];left,right=source[:64],source[64:]
expected=[]
for front,back in ((left,right),(right,left)):
    overlap=bytes(((f&240) or (b&240)) | ((f&15) or (b&15)) for f,b in zip(front,back))
    expected.append(left+overlap+overlap+right)
verified_strips=0
sat=struct.unpack('>320H',r.read('vdpSpriteCache',640))
for i in range(80):
    y,size,attr,x=sat[i*4:i*4+4]
    if size>>8==13:
        at=(attr&0x7ff)*32
        assert bytes(r.vram[(at+j)^1] for j in range(256)) in expected
        assert ((attr>>13)&3)==2+(bank>>15)
        verified_strips+=1
    if not size&127:break
assert verified_strips>0
r.write('pad',bytes(8))
slot=a.players-1;r.write('dbg_bc_native_die_mask',struct.pack('>H',1<<slot))
advance(320)
expected=[3]*a.players;expected[slot]=2
assert lives()==expected,lives()
assert r.u16('dbg_bc_native_party_respawns',slot*2)==1
assert not r.u16('dbg_bc_native_resets'), 'peer death reset the shared stage'
assert struct.unpack('>2H',r.read('dbg_bc_native_camera',4))==(3840,2304)
advance(500)
assert lives()==expected and r.u16('dbg_bc_native_party_respawns',slot*2)==1
r.capture(out/'respawn.png')
result=dict(players=a.players,independent_inputs=True,individual_respawn=True,lives=lives(),verified_strips=verified_strips,
            updates=r.u32('dbg_bc_native_ticks'),frames=r.frames-2600,worst_lines=worst,
            sprite_drops=r.u32('spr_dbg_dropped'),runtime_remaps=r.u32('spr_dbg_remap'),
            full_speed_verified=False,spawn_health_scaling=False)
r.write('dbg_bc_native',b'\0\0');r.run(120)
assert r.u32('flow_state')==0 and r.u16('player_limit')==original_limit
result['returned_to_menu']=True
# Re-enter after freeing peer records; both heap lifetime and cached strip art
# must survive returning to the menu and starting a fresh co-op run.
r.write('dbg_bc_native',b'\0\1');r.write('pad',bytes(8));r.run(30)
advance(100)
assert lives()==[3]*a.players and r.u16('player_limit')==a.players
r.write('dbg_bc_native',b'\0\0');r.run(120)
assert r.u32('flow_state')==0 and r.u16('player_limit')==original_limit
result['reentry_verified']=True
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert result['sprite_drops']==0 and result['runtime_remaps']==0
