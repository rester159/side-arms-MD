#!/usr/bin/env python3
"""Measure NTSC game loops per emulated frame with 3P/4P and scaled waves.
No CPU overclock or emulator speed override. Exits nonzero on any missed gameplay frame.
"""
import argparse, json, math, struct
from run_rom import Runner, PAD, ROOT
from qa_soak import O
from profile_genesis import instruction_profile
ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--players',type=int,choices=(1,2,3,4),required=True)
ap.add_argument('--sections',default='0-9')
ap.add_argument('--frames',type=int,default=6000)
ap.add_argument('--no-parallax',action='store_true')
ap.add_argument('--profile',action='store_true',help='Attribute guest instruction cycles during measured gameplay')
ap.add_argument('--boss',type=int,default=0,help='warp to this boss ordinal instead of section start')
a=ap.parse_args()
out = ROOT / ".local/multiplayer-qa"
out.mkdir(parents=True, exist_ok=True)
variant = "plain" if a.no_parallax else "parallax"
r=Runner()
def tap(b): r.run(5,PAD[b]);r.run(15)
r.run(2600)
tap('DOWN');tap('START')
for _ in range(3):tap('DOWN')
tap('A');assert r.u32('flow_state')==1, 'Home Options did not open'
for _ in range(6):tap('DOWN')
if a.no_parallax:tap('LEFT')
tap('DOWN')
tap('B')
assert r.read('home_cfg',1,6)==bytes([not a.no_parallax]), 'PARALLAX setting was not applied'
for _ in range(3):tap('UP')
assert r.read('home_cursor',1)==b'\0', 'Normal mode not selected'
tap('A');assert r.read('player_dialog',1)==b'\1'
for _ in range((a.players-2)%4):tap('DOWN')
tap('A')
r.write('dbg_pad_override',b'\x01')
def keep():
    for i in range(a.players):
        p=i*O['s_Player']
        r.write('players',b'\xC8',p+O['o_Player_invuln'])
        r.write('players',b'\x07',p+O['o_Player_lives'])
def pads(bits):
    r.write('pad',bytes(sum(([b,b] for b in bits),[])+[0,0]*(4-a.players)))
for f in range(1200):
    keep();pads([0x80 if f%40==0 else 0x10 if f%40==20 else 0]*a.players);r.run(1)
assert r.u32('flow_state')==7
lo,_,hi=a.sections.partition('-')
results=[]
for sec in range(int(lo),int(hi or lo)+1):
    r.write('dbg_warp',struct.pack('>H',sec+1+(a.boss<<8)))
    for i in range(a.players):r.write('dbg_player_cmd',b'\x11',i)
    pads([0]*a.players)
    for _ in range(600):
        keep();r.run(1)
        if not r.u16('dbg_warp'):break
    assert not r.u16('dbg_warp')
    # Exclude explicit loading/warp; all later play, spawns and boss transitions count.
    r.run(120)
    fc=r.u32('frame_counter'); lag=0;worst=0;contexts=[];updates=0
    drops=r.u32('spr_dbg_dropped');remaps=r.u32('spr_dbg_remap')
    with instruction_profile(r, out/f'cpu-{a.players}p-{sec}-boss{a.boss}-{variant}', a.profile):
        for f in range(a.frames):
            keep();bits=[]
            for i in range(a.players):
                p=i*O['s_Player'];x=int.from_bytes(r.read('players',2,p+O['o_Player_x']),'big',signed=True);y=int.from_bytes(r.read('players',2,p+O['o_Player_y']),'big',signed=True)
                tx=48+i*24;ty=32+i*40+int(12*math.sin(f/90+i))
                b=0x20|(1 if x<tx-3 else 2 if x>tx+3 else 0)|(4 if y<ty-3 else 8 if y>ty+3 else 0)
                bits.append(b)
                if r.read('players',1,p+O['o_Player_weapon'])!=b'\x05':r.write('dbg_player_cmd',b'\x11',i)
            pads(bits);r.run(1)
            n=r.u32('frame_counter');updates+=(n-fc)&0xffffffff
            if n==fc:
                lag+=1
            elif struct.unpack('>4H',r.read('prof_seg',8))[3]>=240:
                contexts.append(dict(f=f,seg=struct.unpack('>4H',r.read('prof_seg',8)),parts=struct.unpack('>6H',r.read('prof_multi',12)),collect=r.u16('en_prof_collect'),player=struct.unpack('>2H',r.read('prof_player',4)),enemy=(r.u16('en_prof_update'),r.u16('en_prof_draw')),objects=r.u16('en_prof_nobj'),uploads=r.u16('uploads')))
                contexts.sort(key=lambda c:c['seg'][3],reverse=True);contexts=contexts[:24]
            fc=n;worst=max(worst,struct.unpack('>4H',r.read('prof_seg',8))[3])
            if r.u16('level',O['o_Level_section'])!=sec or r.u32('flow_state')!=7:break
    result=dict(players=a.players,section=sec,boss=a.boss,parallax=not a.no_parallax,frames=f+1,updates=updates,missed=lag,worst_lines=worst,sprite_drops=r.u32('spr_dbg_dropped')-drops,remaps=r.u32('spr_dbg_remap')-remaps,slow=contexts)
    results.append(result);print(json.dumps(result),flush=True)
    r.capture(out/f'perf-{a.players}p-{sec}-boss{a.boss}-{variant}.png')
p=out/f'perf-{a.players}p-{a.sections}-boss{a.boss}-{variant}.json';p.write_text(json.dumps(results,indent=2))
raise SystemExit(1 if any(x['missed'] for x in results) else 0)
