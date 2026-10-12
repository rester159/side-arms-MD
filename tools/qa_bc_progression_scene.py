#!/usr/bin/env python3
"""Exercise native round loading, party state and artwork with forced death/defeat."""
import argparse
import json
import hashlib
import struct
from run_rom import ROOT, Runner
from bc_actor_layout import read_actor_pool

parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--from-round',type=int,choices=(1,2,3,4,5,6,7,8),default=1)
parser.add_argument("--players",type=int,choices=(1,2,3,4),default=1)
parser.add_argument("--clear-fire",choices=("none","center","spread","advance","sweep","sweep-both","combat"),default="none",help="Diagnostic firing route while waiting for the forced boss defeat")
parser.add_argument("--charge",action="store_true",help="Hold each firing side for 80 updates to exercise charged beams")
args=parser.parse_args();start=args.from_round-1;next_round=start+1
geometry=json.loads((ROOT/'res/generated/bc_boss_geometry.json').read_text())
r = Runner(); r.run(2600)
original_limit=r.u16('player_limit')
r.write('dbg_bc_native_players',struct.pack('>H',args.players))
r.write('dbg_bc_native_start_round',struct.pack('>H',start))
r.write('dbg_pad_override', b'\x01')
r.write('dbg_bc_native_protect', b'\0\1')
r.write('dbg_bc_native', b'\0\1')
def lives():
    return list(struct.unpack('>'+str(args.players)+'H',r.read('dbg_bc_native_party_lives',args.players*2)))

def steer(firing=False):
    pads=bytearray(8)
    for i in range(args.players):
        x,y=struct.unpack('>2H',r.read('dbg_bc_native_party_position',4,i*4))
        cx,cy=struct.unpack('>2H',r.read('dbg_bc_native_camera',4))
        if start in (2,5):
            target=(146 if 1150<cy<1500 else 128) if start==2 else (170 if 400<cy<1010 or cy>1550 else 80)
            bits=1 if x<target-2 else 2 if x>target+2 else 0
        else:
            target=72 if (start==6 and cx>1950) or (start==3 and 1750<cx<2220) else (120-16*i if firing and args.clear_fire in ("spread","advance","sweep","sweep-both","combat") else 120)
            bits=8 if y>target+2 else 4 if y<target-2 else 0
        if firing and args.clear_fire in ("advance","sweep","sweep-both","combat") and start not in (2,5):
            phase=(r.u32('dbg_bc_native_ticks')+i*120)%640
            target_x=48+(phase if phase<320 else 640-phase)//2 if args.clear_fire in ("sweep","sweep-both","combat") else 160
            bits|=1 if x<target_x-2 else 2 if x>target_x+2 else 0
        if firing and args.clear_fire=="sweep-both" and start in (2,5):
            phase=(r.u32('dbg_bc_native_ticks')+i*120)%480
            target_y=64+(phase if phase<240 else 480-phase)//2
            bits|=8 if y>target_y+2 else 4 if y<target_y-2 else 0
        if firing and args.clear_fire=="combat" and start not in (2,5) and not (start==3 and 1750<cx<2220):
            phase=(r.u32('dbg_bc_native_ticks')+i*160)%480
            target_y=64+(phase if phase<240 else 480-phase)//2
            bits=(bits&3)|(8 if y>target_y+2 else 4 if y<target_y-2 else 0)
        tick=r.u32('dbg_bc_native_ticks')
        period,held=(100,80) if args.charge else (40,20)
        fire=(0x10 if tick%(period*2)>=period else 0x20) if firing and tick%period<held else 0
        pads[i*2]=bits|fire
        pads[i*2+1]=fire if tick%period==0 else 0
    r.write('pad',bytes(pads))

r.run(180)
assert lives()==[3]*args.players,lives()
if args.players==1:
    r.write('dbg_bc_native_die',b'\0\1')
else:
    r.write('dbg_bc_native_die_mask',struct.pack('>H',1<<(args.players-1)))
expected=[3]*args.players;expected[-1]=2
for _ in range(2000):
    steer();r.run(1)
    if lives()==expected:break
assert lives()==expected,lives()
assert r.u16('dbg_bc_native_resets')==(1 if args.players==1 else 0)
for _ in range(90000):
    steer();r.run(1)
    assert r.u16('dbg_bc_native_status') in (0,4),(r.u16('dbg_bc_native_status'),lives())
    if r.u32('dbg_bc_native_ticks') >= (9000 if start else 6000):break
assert r.u32('dbg_bc_native_ticks') >= (9000 if start else 6000)
r.write('pad',bytes(8))
r.write('dbg_bc_native_boss_defeat', b'\0\1')
clear_start = None
for _ in range(6000 if args.clear_fire=="none" else 30000):
    if args.clear_fire!="none":steer(firing=True)
    r.run(1)
    if r.u16('dbg_bc_native_round_exit') == 2 and clear_start is None:
        clear_start = r.u32('frame_counter')
    if r.u16('dbg_bc_native_status') == 6: break
if r.u16('dbg_bc_native_status')!=6:
    out=ROOT/f'.local/bc-progression-{start+1}-{next_round+1}-{args.players}p'
    out.mkdir(parents=True,exist_ok=True)
    r.capture(out/'stalled.png')
    (out/'actors.bin').write_bytes(read_actor_pool(r))
    (out/'party-control.bin').write_bytes(r.read('party_control',256))
    (out/'stall.json').write_text(json.dumps(dict(players=args.players,round=start+1,clear_fire=args.clear_fire,charged_fire=args.charge,
        ticks=r.u32('dbg_bc_native_ticks'),status=r.u16('dbg_bc_native_status'),lives=lives(),
        camera=list(struct.unpack('>2H',r.read('dbg_bc_native_camera',4))),
        rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest()),indent=2)+'\n')
assert r.u16('dbg_bc_native_status') == 6,(r.u16('dbg_bc_native_status'),r.u32('dbg_bc_native_ticks'),r.read('dbg_bc_native_camera',4).hex(),lives())
assert r.u32('frame_counter') - clear_start == 421
assert r.u16('dbg_bc_native_current_round') == start

# End the old round's controller script before loading a different layout.
r.write('pad',bytes(8))

# Distinct nonzero score/high-score bytes make accidental new-game reset visible.
score_refs=[('score',0)]+[('peer_scores',35*i) for i in range(args.players-1)]
for i,(name,offset) in enumerate(score_refs):
    r.write(name,bytes([0,0,0,0,i+1,2,3,0, 0,0,0,0,9,i+1,9,0]),offset)
scores=[r.read(name,16,offset) for name,offset in score_refs]
before_lives=lives()
assert all(value<128 for value in before_lives),before_lives
ticks = r.u32('dbg_bc_native_ticks')
frame = r.u32('frame_counter')
for _ in range(120):
    r.run(1)
    if r.u32('frame_counter') != frame: break
assert r.u32('frame_counter') != frame, 'Round loading did not complete'
assert r.u16('dbg_bc_native_current_round') == next_round
assert r.u16('dbg_bc_native_status') in (0, 4)
assert lives()==before_lives,(before_lives,lives())
assert [r.read(name,16,offset) for name,offset in score_refs]==scores
assert r.u16('player_limit')==args.players
assert r.u32('dbg_bc_native_ticks') >= ticks
assert r.u16('dbg_bc_native_resets')==(1 if args.players==1 else 0)
assert r.u16('dbg_bc_native_round_exit') == 0
assert r.u16('dbg_bc_native_actors') == 0
assert struct.unpack('>2H', r.read('dbg_bc_native_camera', 4)) == ((512,2048) if start==7 else (512,1792) if start==6 else (512,1536) if start==5 else (256,0) if start==4 else (512,1024) if start==3 else (512,768) if start==2 else (0,0) if start else (512,256))
assert r.u16('dbg_bc_native_background_active')
slots = [i for i,v in enumerate(r.read('slot_refs',56)) if v == 255]
next_blocks=geometry['banks'][4 if start==7 else next_round]['block_count']
assert len(slots)==(geometry['capacity'] if start==7 else next_blocks)
rom = (ROOT/'out/release/rom.bin').read_bytes()
address = r.symbols['bc_boss5_patterns' if start==7 else f'bc_boss{next_round+1}_patterns']
for i,slot in enumerate(list(reversed(slots))[:next_blocks]):
    at = (160+slot*16)*32
    assert bytes(r.vram[(at+j)^1] for j in range(512)) == rom[address+i*512:address+(i+1)*512]
for _ in range(10000):
    r.run(1)
    assert r.u16('dbg_bc_native_status') in (0,4)
    assert not r.u16('dbg_bc_native_actor_unmapped')
    assert not r.u16('dbg_bc_native_unmapped')
    if r.u32('dbg_bc_native_ticks')>=ticks+1000:break
assert r.u32('dbg_bc_native_ticks') >= ticks+1000
assert r.u16('dbg_bc_native_music_command') == (0x29 if start==7 else 0x28 if start==6 else 0x27 if start==5 else 0x26 if start==4 else 0x25 if start==3 else 0x24 if start==2 else 0x23 if start else 0x22)
assert lives()==before_lives,(before_lives,lives())
out = ROOT/f'.local/bc-progression-{start+1}-{next_round+1}-{args.players}p'; out.mkdir(parents=True,exist_ok=True)
r.capture(out/f'round-{next_round+1}.png')
r.write('dbg_bc_native', b'\0\0'); r.write('dbg_pad_override', b'\0'); r.run(120)
assert r.u32('flow_state') == 0
assert r.u16('player_limit')==original_limit
assert 255 not in r.read('slot_refs',56)
result = dict(rounds=[start+1,next_round+1], forced_player_death=True, forced_boss_defeat=True,
              seeded_score_preserved=True, clear_fire=args.clear_fire,charged_fire=args.charge, full_speed_verified=False, remaining_lives=before_lives, players=args.players, rom_sha256=hashlib.sha256(rom).hexdigest(), clear_wait_updates=421,
              next_round_boss_patterns_verified=True, next_round_gameplay_resumed=True,
              returned_to_menu=True, full_campaign_verified=False, music_command=hex(r.u16('dbg_bc_native_music_command')),
              next_round_music_verified=True)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
