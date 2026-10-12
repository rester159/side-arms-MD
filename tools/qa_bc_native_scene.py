#!/usr/bin/env python3
"""Run the native BC development scene on the actual Genesis CPU emulator.
This scene uses draft background artwork and incomplete audio. Test acknowledgement
and protection are explicit. A pass is not a finished or source-identical port.
"""
import argparse
import json
import struct
from run_rom import ROOT,Runner
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--frames',type=int,default=27000);p.add_argument('--updates',type=int,default=7000)
p.add_argument('--profile',action='store_true');p.add_argument('--music',action='store_true',help='Use the actual Genesis music backend')
p.add_argument('--round',type=int,choices=(1,2,3,4,5,6,7,8,9,10),default=1,help='Native development round')
a=p.parse_args()
r=Runner();r.run(2600)
r.write('dbg_bc_native_start_round',struct.pack('>H',a.round-1))
r.write('dbg_pad_override',b'\x01');r.write('dbg_bc_native_protect',b'\0\1')
r.write('dbg_bc_native_audio_manual',b'\0\1')
r.write('dbg_bc_native',b'\0\1')
r.write('dbg_bc_native_profile_on',struct.pack('>H',int(a.profile)))
r.run(30) # Exclude scene initialization; it now waits for test audio acknowledgement.
assert r.u16('dbg_bc_native_status')==4
assert r.u16('dbg_bc_native_background_active'), 'Missing scenery resource'
if a.music:r.write('dbg_bc_native_audio_manual',b'\0\0')
initial_drops=r.u32('spr_dbg_dropped');initial_remaps=r.u32('spr_dbg_remap')
profile_totals={};draw_profile_totals={};
max_actors=max_unmapped=acks=missed=worst=0;fc=r.u32('frame_counter');samples=[];slow=[]
out=ROOT/(('.local/bc-native-scene' if a.round==1 else f'.local/bc-native-scene-round{a.round}')+('-profile' if a.profile else ''));out.mkdir(parents=True,exist_ok=True)
milestones={1000,2500,4000,5500};captures=[]
for f in range(a.frames):
    status=r.u16('dbg_bc_native_status')
    if status==4 and not a.music:
        r.write('dbg_bc_native_audio_ack',b'\0\1');acks+=1
    tick=r.u32('dbg_bc_native_ticks')
    bits=0x20 if tick%40<20 else 0
    if a.round==3 and tick>250:
        y=r.u16('dbg_bc_native_camera',2);x=r.u16('dbg_bc_native_position')
        target=146 if 1150<y<1500 else 128
        bits |= 1 if x<target-2 else 2 if x>target+2 else 0
    if a.round==4:
        camera_x=r.u16('dbg_bc_native_camera');y=r.u16('dbg_bc_native_position',2)
        target=72 if 1750<camera_x<2220 else 120
        bits |= 8 if y>target+2 else 4 if y<target-2 else 0
    if a.round==7:
        x=r.u16('dbg_bc_native_camera');y=r.u16('dbg_bc_native_position',2)
        target=72 if x>1950 else 120
        bits |= 8 if y>target+2 else 4 if y<target-2 else 0
    if a.round==6:
        y=r.u16('dbg_bc_native_camera',2);x=r.u16('dbg_bc_native_position')
        target=170 if 400<y<1010 or y>1550 else 80
        bits |= 1 if x<target-2 else 2 if x>target+2 else 0
    pressed=bits if tick%40==0 else 0
    r.write('pad',bytes([bits,pressed,0,0,0,0,0,0]))
    r.run(1)
    now=r.u32('frame_counter');completed=now!=fc;missed+=not completed;fc=now
    current_tick=r.u32('dbg_bc_native_ticks')
    if completed and current_tick in milestones:
        path=out/('tick-%05d.png'%current_tick);r.capture(path)
        captures.append(str(path));milestones.remove(current_tick)
    status=r.u16('dbg_bc_native_status')
    max_actors=max(max_actors,r.u16('dbg_bc_native_actors'))
    max_unmapped=max(max_unmapped,r.u16('dbg_bc_native_actor_unmapped'))
    worst=max(worst,r.u16('prof_seg',6))
    if completed and a.profile:
        draw_parts=list(struct.unpack('>4H',r.read('dbg_bc_native_draw_profile',8)))
        band=str((current_tick//1000)*1000)
        bucket=draw_profile_totals.setdefault(band,dict(samples=0,total=[0]*4,maximum=[0]*4))
        bucket['samples']+=1
        for i,value in enumerate(draw_parts):
            bucket['total'][i]+=value
            bucket['maximum'][i]=max(bucket['maximum'][i],value)
        parts=list(struct.unpack('>3H',r.read('dbg_bc_native_profile',6)))
        # Aggregate every completed frame, not only the retained worst frames.
        band=str((current_tick//1000)*1000)
        bucket=profile_totals.setdefault(band,dict(samples=0,total=[0,0,0],maximum=[0,0,0]))
        bucket['samples']+=1
        for i,value in enumerate(parts):
            bucket['total'][i]+=value
            bucket['maximum'][i]=max(bucket['maximum'][i],value)
        slow.append(dict(tick=r.u32('dbg_bc_native_ticks'),actors=r.u16('dbg_bc_native_actors'),
                         parts=parts,draw_parts=draw_parts))
        slow.sort(key=lambda row:sum(row['parts']),reverse=True);slow=slow[:12]
    assert not r.u16('dbg_bc_native_unmapped'),(f,'unmapped robot/weapon art')
    if f%600==0 or status not in (0,4):
        # Boss artwork must remain reserved while the scrolling background
        # shares its cache. No current visible world cell may lose its slot.
        assert r.read('slot_refs',56).count(255)==(0 if a.round==10 else 10 if a.round in (5,9) else 6)
        x,y=struct.unpack('>2H',r.read('dbg_bc_native_camera',4));x-=32
        slots=r.read('cell_slot',128)
        for cy in range(y//32,(y+223)//32+1):
            for cx in range(x//32,(x+319)//32+1):
                assert slots[(cy%8)*16+cx%16]<56,('missing background cell',f,cx,cy)
        samples.append(dict(frame=f,status=status,handler=hex(r.u16('dbg_bc_native_handler')),
                            camera=list(struct.unpack('>2H',r.read('dbg_bc_native_camera',4))),actors=r.u16('dbg_bc_native_actors')))
    if status not in (0,4) or r.u32('dbg_bc_native_ticks')>=a.updates:break
r.capture(out/'last.png')
result=dict(round=a.round,frames=f+1,native_updates=r.u32('dbg_bc_native_ticks'),stage_events=r.u32('dbg_bc_native_events'),
            max_live_actors=max_actors,test_audio_acknowledgements=acks,
            music_backend=a.music,music_commands=r.u16('dbg_bc_native_music_requests'),
            actor_sfx_commands=r.u16('dbg_bc_native_actor_sfx_commands'),
            actor_sfx_dropped=r.u16('dbg_bc_native_actor_sfx_dropped'),
            actor_sfx_mask=hex(r.u32('dbg_bc_native_actor_sfx_mask')),missed_emulated_frames=missed,worst_lines=worst,
            final_status=status,remaining_lives=r.u16('dbg_bc_native_lives'),checkpoint_resets=r.u16('dbg_bc_native_resets'),samples=samples,captures=captures,slow=slow,profile_totals=profile_totals,draw_profile_totals=draw_profile_totals,draw_profile_labels=["background","player","actors","HUD"],profiling_enabled=a.profile,
            profile_unit='SGDK subticks (1/76800 second)',enemy_art=f'round_{a.round}_creatures_boss_pickups_projectiles_effects',
            max_unmapped_actors=max_unmapped,background_art=bool(r.u16('dbg_bc_native_background_active')),
            background_art_draft=True,source_scheduler_verified=False,
            sprite_drops=r.u32('spr_dbg_dropped')-initial_drops,runtime_remaps=r.u32('spr_dbg_remap')-initial_remaps,
            full_game_performance_verified=False)
r.write('dbg_bc_native',b'\0\0');r.write('dbg_pad_override',b'\0');r.run(120)
assert r.u32('flow_state')==0
assert 255 not in r.read('slot_refs',56), 'BC boss patterns leaked into menu cache'
result['returned_to_menu']=True
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
assert status in (0,4),(status,'native scene stopped before requested duration')
if a.round==6:
    assert result['checkpoint_resets']==0, 'Route restarted at a checkpoint'
    if a.updates>=8000:assert result['samples'][-1]['camera']==[256,1792]
if a.round in (4,5):
    assert result['checkpoint_resets']==0, 'Route restarted at a checkpoint'
    assert result['samples'][-1]['camera'][0]==(2816 if a.round==5 else 2304) if a.updates>=11000 or (a.round==4 and a.updates>=8000) else True
assert max_actors>0 and result['stage_events']>4
assert result['native_updates']==a.updates,'Native update budget not reached'
assert not max_unmapped, 'Missing native actor artwork'

if a.round==7 and a.updates>=8000:
    assert not result['checkpoint_resets']
    assert result['samples'][-1]['camera']==[2816,1536]

if a.round==8 and a.updates>=9000:
    assert not result["checkpoint_resets"]
    assert result["samples"][-1]["camera"]==[2816,1792]
