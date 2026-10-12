#!/usr/bin/env python3
"""Controller-driven campaign diagnostic, with optional explicit protection.

Never forces enemy defeat, round completion, lives, score, health or weapons.
This heuristic pilot is not proof that every natural campaign path works.
"""
import argparse,hashlib,json,os,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from run_rom import Runner,ROOT,PAD
from bc_actor_layout import read_actor_pool
p=argparse.ArgumentParser();p.add_argument('--players',type=int,choices=(1,2,3,4),default=4);p.add_argument('--updates',type=int,default=30000);p.add_argument('--protect',action='store_true');p.add_argument('--scroll-prediction',action='store_true',help='Predict current camera velocity and terrain crushes; requires --dodge');p.add_argument('--dodge',action='store_true',help='Read-only actor prediction chooses controller movement to avoid contact');p.add_argument('--turret-lanes',action='store_true',help='Split round-seven late-section aim between upper and lower turrets');p.add_argument('--home',action='store_true',help='Launch through Home/modal and continue through credits and Home return');p.add_argument('--use-continues',action='store_true',help='Accept real Home continue offers through Start; never seed credits or lives');p.add_argument('--output',type=Path,required=True);p.add_argument('--profile-start',type=int,help='Profile complete scene calls starting at this campaign tick');p.add_argument('--profile-calls',type=int,default=1000);p.add_argument('--stop-frame',type=int,help='Stop at an absolute runner video frame for independent profiler replay');p.add_argument('--rapid-fire',action='store_true',help='Use three held / three released updates for ordinary controller volleys instead of long charges');p.add_argument('--seek-pickups',action='store_true',help='Steer toward nearby live weapons, options and extra lives; ordinary collision rules still collect them');p.add_argument('--death-trace',action='store_true',help='Read-only snapshots of alive-to-dying transitions; does not infer a cause');p.add_argument('--immediate-safety',action='store_true',help='Prefer candidates without a predicted next-update body collision; requires --dodge');p.add_argument('--lookahead',action='store_true',help='Evaluate real-core short movement branches; requires natural Home run and --dodge');p.add_argument('--record-inputs',action='store_true',help='Record per-video-frame controller input for independent replay');p.add_argument('--boss-standoff',type=int,help='Desired horizontal distance from a visible boss; controller-only aiming trial');p.add_argument('--boss-four-direct-aim',action='store_true',help='Track the R4 core directly; retain actual-core collision lookahead');p.add_argument('--home-lives',type=int,choices=range(1,8),help='Choose total starting lives through the real Home Options UI');p.add_argument('--boss-eight-lookahead',type=int,choices=range(4,17),default=4,help='Controller search horizon at the visible R8 boss; default4 preserves existing policy');p.add_argument('--boss-nine-four-direct-aim',action='store_true',help='Use direct aiming at the repeated fourth boss in R9, with actual-core safety lookahead');p.add_argument('--boss-nine-eight-lookahead',type=int,choices=range(4,17),default=4,help='Controller prediction horizon at the repeated eighth boss in R9');p.add_argument('--boss-nine-eight-survival',action='store_true',help='When every predicted direction dies at R9 boss8, prefer the longest survival before aim distance');p.add_argument('--boss-four-lookahead',type=int,choices=range(4,17),default=4,help='Controller search horizon at the visible R4 boss; default4 preserves existing policy');p.add_argument('--predict-rapid-fire',action='store_true',help='Forecast the known rapid-fire rhythm in speculative controller branches; requires --rapid-fire and --lookahead');p.add_argument('--hucard',action='store_true',help='Select HuCard music through Home and monitor campaign audio');p.add_argument('--background-audit-round',type=int,choices=range(1,11),help='Read-only visible background audit after each video upload in one campaign round');p.add_argument('--gallery-palette-baseline',type=Path,help='Verify unfaded native gallery CRAM against an archived Normal sprite palette');p.add_argument('--color-mode',choices=('standard','vivid'),default='vivid');a=p.parse_args();assert a.updates>0;a.output.mkdir(parents=True,exist_ok=True)
assert not a.hucard or (a.home and not a.lookahead), '--hucard requires Home without speculative rewinds'
assert not a.predict_rapid_fire or (a.rapid_fire and a.lookahead), '--predict-rapid-fire requires --rapid-fire and --lookahead'
assert a.boss_four_lookahead==4 or a.lookahead, '--boss-four-lookahead requires real-core lookahead'
assert not a.boss_nine_eight_survival or a.lookahead, '--boss-nine-eight-survival requires real-core lookahead'
assert a.boss_nine_eight_lookahead==4 or a.lookahead, '--boss-nine-eight-lookahead requires real-core lookahead'
assert not a.boss_nine_four_direct_aim or a.lookahead, '--boss-nine-four-direct-aim requires real-core lookahead'
assert a.boss_eight_lookahead==4 or a.lookahead, '--boss-eight-lookahead requires real-core lookahead'
assert a.home_lives is None or a.home, '--home-lives requires Home Options'
assert a.boss_standoff is None or 32<=a.boss_standoff<=192, '--boss-standoff must be32..192'
assert not a.boss_four_direct_aim or a.lookahead, '--boss-four-direct-aim requires real-core lookahead'
assert not a.immediate_safety or a.dodge, '--immediate-safety requires --dodge'
assert not a.scroll_prediction or a.dodge, '--scroll-prediction requires --dodge'
assert not a.use_continues or a.home, '--use-continues requires the real Home session'
assert not (a.use_continues and (a.profile_start is not None or a.stop_frame is not None)), 'Continue input waits cannot be combined with an exact-frame profiler replay'
assert not a.lookahead or (a.home and a.dodge and not a.protect), '--lookahead requires natural Home with --dodge'
assert a.background_audit_round is None or (a.profile_start is None and not a.lookahead), 'Background audit cannot share instruction hooks with profiling or speculative replay'
rom=Path(os.environ.get('SIDEARMS_BUILD',ROOT))/'out/release/rom.bin';digest=hashlib.sha256(rom.read_bytes()).hexdigest()
r=Runner(rom=rom)
controller_record = bytearray()
survival_statistics = {}
if a.lookahead or a.record_inputs:
 from bc_pilot_lookahead import choose_move
 original_run = r.run
 def recorded_run(n, mask=0):
  for _ in range(n):
   if not getattr(r,'_pilot_search',False):
    controller_record.extend(struct.pack('>HB',mask,r.read('dbg_pad_override',1)[0])+r.read('pad',8))
   original_run(1,mask)
 r.run = recorded_run
r.run(2600)
selected_color=bytes([int(a.color_mode=='vivid')])
r.write('game_cfg',selected_color,7);r.write('color_mode',selected_color)
if a.home:
 def tap(button):r.run(5,PAD[button]);r.run(20)
 assert r.u32('flow_state')==0
 tap('DOWN');tap('START');assert r.u32('flow_state')==9
 if a.hucard:
  for _ in range(3):tap('DOWN')
  tap('A')
  for _ in range(8):tap('DOWN')
  tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
  tap('B')
  for _ in range(3):tap('UP')
 if a.home_lives is not None:
  while r.read('home_cursor',1)!=b'\3':tap('DOWN')
  tap('A');assert r.u32('flow_state')==1
  tap('DOWN')
  selected_lives=r.read('home_cfg',1,1)[0]
  for _ in range((a.home_lives-selected_lives)%7):tap('RIGHT')
  r.capture(a.output/'home-lives-options.png')
  tap('B');assert r.u32('flow_state')==9
  assert r.read('home_cfg',1,1)==bytes([a.home_lives])
  while r.read('home_cursor',1)!=b'\1':tap('UP')
 else:tap('DOWN')
 assert r.read('home_cursor',1)==b'\1'
 tap('A');assert r.read('player_dialog',1)==b'\1'
 selected=r.read('home_cfg',1,5)[0]
 for _ in range((a.players-selected)%4):tap('DOWN')
 r.capture(a.output/'player-modal.png');tap('A')
 assert r.u32('flow_state')==14 and r.u16('player_limit')==a.players
 assert r.u16('dbg_bc_native_players')==a.players and r.u16('dbg_bc_native_current_round')==0
 assert not r.u16('dbg_bc_native_protect')
 if a.protect:r.write('dbg_bc_native_protect',b'\0\1')
else:
 for k,v in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',0),('dbg_bc_native_protect',int(a.protect)),('dbg_bc_native',1)]:r.write(k,v.to_bytes(2,'big'))
music_monitor = None
if a.hucard:
 from hucard_campaign_monitor import CampaignMusicMonitor
 music_monitor = CampaignMusicMonitor(r)
r.write('dbg_pad_override',b'\1')
if a.dodge or a.death_trace:
 from bc_pilot_terrain import solid, stationary_step, scrolling_step
 from workload_metrics import WorkloadMetrics
 pilot_layout=WorkloadMetrics(r,a.players)
 terrain_rom=rom.read_bytes();terrain_cache={}
 def player_terrain():
  cells=r.u32('actor_data',pilot_layout.o['bc_terrain_cells']) & 0xffffff
  attrs=r.u32('actor_data',pilot_layout.o['bc_terrain_attributes']) & 0xffffff
  key=(cells,attrs)
  if key not in terrain_cache:
   assert cells+16384<=len(terrain_rom) and attrs+2048<=len(terrain_rom), ('terrain outside ROM',key)
   terrain_cache[key]=(terrain_rom[cells:cells+16384],terrain_rom[attrs:attrs+2048])
  cell_data,attribute_data=terrain_cache[key]
  return lambda x,y:solid(cell_data,attribute_data,x,y)

 def player_speed(i):
  address=r.symbols['player'] if i==0 else r.u32('peers')+(i-1)*pilot_layout.o['bc_player_size']
  return bool(pilot_layout.byte(address+pilot_layout.o['bc_speed']))

for _ in range(1000):
 r.run(1)
 if r.u32('dbg_bc_native_ticks'):break
assert r.u32('dbg_bc_native_ticks'), 'Native launch did not complete'
profiler=None
if a.profile_start is not None:
 from bc_campaign_profile import CampaignProfile
 profiler=CampaignProfile(r,a.profile_start,a.profile_calls,a.output/'profile',rom_path=rom)
background_monitor=None
if a.background_audit_round is not None:
 from bc_live_background_audit import CampaignBackgroundAudit
 background_monitor=CampaignBackgroundAudit(r,rom.read_bytes(),a.background_audit_round,a.output/'background-audit')
pickup_target_updates = 0
def pickup_target(raw, x, y):
 candidates = []
 for slot in range(32):
  b = raw[slot*50:(slot+1)*50]
  if b[20] != 0x80 or b[38] not in (2,3,4,5,9):continue
  px = (int.from_bytes(b[:4], 'big') >> 8) & 65535
  py = (int.from_bytes(b[4:8], 'big') >> 8) & 65535
  if not (16 <= px <= 240 and 32 <= py <= 200):continue
  distance = (px-x)**2 + (py-y)**2
  if distance <= 112**2:candidates.append((distance, slot, px, py))
 return min(candidates)[2:] if candidates else None

death_records = []
previous_players = {}
def trace_player_deaths(tick, round_, raw, camera):
 for i in range(a.players):
  address = r.symbols['player'] if i == 0 else r.u32('peers')+(i-1)*pilot_layout.o['bc_player_size']
  read = lambda offset, n: bytes(pilot_layout.byte(address+offset+k) for k in range(n))
  x, y = (int.from_bytes(read(offset,4),'big') >> 8 for offset in (0,4))
  state = read(pilot_layout.o['bc_state'],1)[0]
  nearby = []
  for slot in range(32):
   b = raw[slot*50:(slot+1)*50]
   if not b[20]:continue
   ex,ey = ((int.from_bytes(b[offset:offset+4],'big') >> 8)&65535 for offset in (0,4))
   if ex >= 32768:ex -= 65536
   if ey >= 32768:ey -= 65536
   nearby.append(dict(slot=slot,x=ex,y=ey,state=b[20],flags=b[22],pickup=b[38],half_x=b[36],half_y=b[37],distance2=(ex-x)**2+(ey-y)**2))
  snapshot = dict(tick=tick,round=round_+1,player=i+1,state=state,position=[x,y],camera=list(camera),
      invulnerability=read(pilot_layout.o['bc_invulnerability'],1)[0],previous_buttons=old[i],
      nearby=sorted(nearby,key=lambda item:item['distance2'])[:5])
  previous = previous_players.get(i)
  if previous and previous['state'] == 0x80 and state == 0x40:
   death_records.append(dict(before=previous,after=snapshot))
   print('DEATH',json.dumps(death_records[-1]),flush=True)
  previous_players[i] = snapshot

continue_attempts=[]
def accept_continue(mask):
 # Use the first waiting member, respecting the game's shared credit order.
 i=next(i for i in range(a.players) if mask&(1<<i))
 before=dict(frame=r.frames,tick=r.u32('dbg_bc_native_ticks'),player=i+1,
     credits=r.read('credits',1)[0],ranks=list(r.read('unused_continues',4)),
     lives=list(struct.unpack('>4H',r.read('dbg_bc_native_party_lives',8)))[:a.players])
 r.capture(a.output/f'continue-{len(continue_attempts)+1}-offer.png')
 pads=bytearray(8);pads[i*2:i*2+2]=b'\x80\x80';r.write('pad',pads)
 # The scene consumes the press. Do not reinject it on subsequent video frames.
 for _ in range(120):
  r.run(1)
  if not r.read('continue_pending',1)[0]&(1<<i):break
 else:raise AssertionError(('continue press was not consumed',before))
 r.write('pad',bytes(8))
 # An all-out restart reloads the stage before the debug lives snapshot is
 # republished. Await its first simulation update instead of reading stale HUD data.
 ranks=list(r.read('unused_continues',4))
 consumed=r.read('continue_prompts',1,i*3+2)[0]==0
 if consumed:
  for _ in range(2500):
   # Tick increments before drawing publishes the party HUD snapshot.
   # A video-frame boundary can fall between them in a crowded scene.
   if r.u32('dbg_bc_native_ticks')>before['tick'] and not (r.u16('dbg_bc_native_party_lives',i*2)&128):break
   r.run(1)
  else:raise AssertionError(('accepted continue did not resume with published live player',before))
 assert not r.read('scene_paused',1)[0], 'Continue acceptance paused gameplay'
 ranks=list(r.read('unused_continues',4));lives=list(struct.unpack('>4H',r.read('dbg_bc_native_party_lives',8)))[:a.players]
 accepted=not(lives[i]&128)
 assert not consumed or accepted, ('spent continue without live player',before,lives)
 if accepted:
  assert ranks[i]==max(0,before['ranks'][i]-1),('continue rank',before,ranks)
  assert all(ranks[j]==before['ranks'][j] for j in range(a.players) if j!=i)
  if r.read('game_cfg',1,5)[0]!=2:assert r.read('credits',1)[0]==before['credits']-1
 attempt=dict(before=before,accepted=accepted,after_frame=r.frames,credits=r.read('credits',1)[0],ranks=ranks,lives=lives)
 continue_attempts.append(attempt);print('CONTINUE',json.dumps(attempt),flush=True)
 r.capture(a.output/f'continue-{len(continue_attempts)}-after.png')

def dodge_direction(x,y,tx,ty,raw,speed_up=False,terrain=None,camera=(0,0),scroll=None,fixed_position=None):
 # Diagnostic pilot only: read existing actors, then choose ordinary pad bits.
 # Prediction cannot anticipate AI turns, births or future camera-script changes.
 hazards=[]
 for slot in range(32):
  b=raw[slot*50:(slot+1)*50]
  if b[20]!=128 or b[22]&2 or b[38]:continue
  ex=(int.from_bytes(b[:4],'big')>>8)&65535
  ey=(int.from_bytes(b[4:8],'big')>>8)&65535
  if ex>=32768:ex-=65536
  if ey>=32768:ey-=65536
  if not (-64<=ex<=320 and -64<=ey<=288):continue
  hazards.append((ex,ey,int.from_bytes(b[8:10],'big',signed=True)/256,
                  int.from_bytes(b[10:12],'big',signed=True)/256,
                  (b[36]+5)&255,(b[37]+8)&255))
 best=None
 for dx,dy,bits in ((0,0,0),(1,0,1),(-1,0,2),(0,1,4),(0,-1,8),
                    (1,1,5),(1,-1,9),(-1,1,6),(-1,-1,10)):
  # Match bc_direction's cardinal/diagonal speeds and bc_move_step's clamps.
  speed=(3 if dx and dy else 4) if speed_up else (2 if dx and dy else 3)
  move_x,move_y=dx*speed,dy*speed
  score=0.02*((max(16,min(240,x+move_x*6))-tx)**2+(max(32,min(200,y+move_y*6))-ty)**2)
  immediate_collision = False
  px,py=x,y
  fx,fy=fixed_position if fixed_position else (x*256,y*256)
  if scroll:camera_fx,camera_fy,sx,sy,advance=scroll
  for t in range(1,13):
   if terrain and scroll:
    if advance:
     camera_fx=(camera_fx+sx)&0xfffff;camera_fy=(camera_fy+sy)&0xfffff
    fx,fy,crushed=scrolling_step(fx,fy,move_x,move_y,camera_fx>>8,camera_fy>>8,sx,sy,terrain)
    px,py=fx/256,fy/256
    if crushed:score+=10000000;break
   elif terrain:
    px,py=stationary_step(px,py,move_x,move_y,*camera,terrain)
   else:
    px,py=max(16,min(240,px+move_x)),max(32,min(200,py+move_y))
   if t==6:score+=0.02*((px-tx)**2+(py-ty)**2)
   if t not in ((1,2,4,8,12) if a.immediate_safety else (2,4,8,12)):continue
   for ex,ey,vx,vy,hx,hy in hazards:
    gap=max(abs(px-ex-vx*t)-hx,abs(py-ey-vy*t)-hy)
    if gap<0:
     score+=100000+(-gap)*1000
     if t==1:immediate_collision=True
    elif gap<16:score+=(16-gap)**2*4
  candidate=(immediate_collision,score,bits)
  if best is None or candidate[:2]<best[:2]:best=candidate
 return best[2]

last_tick=-1;last_round=-1;last_log=-1;old=[0]*4;transitions=[];reason='update_limit';start_frames=r.frames;start_tick=r.u32('dbg_bc_native_ticks')
# Read-only timing windows locate expensive campaign sections. They include
# round transitions/audio waits and are not isolated CPU-budget measurements.
windows=[];window_tick=start_tick;window_frame=start_frames;window_round=1
for frame in range(a.updates*4+10000):
 if profiler:
  profiler.poll()
  if profiler.done:reason='profile_complete';break
 if a.stop_frame is not None and r.frames>=a.stop_frame:reason='frame_stop';break
 tick=r.u32('dbg_bc_native_ticks');round_=r.u16('dbg_bc_native_current_round');status=r.u16('dbg_bc_native_status')
 if tick>=a.updates:break
 if a.use_continues and (pending:=r.read('continue_pending',1)[0]):
  accept_continue(pending);old=[0]*4;last_tick=-1;continue
 if status not in (0,4,6):reason='status_'+str(status);break
 if r.u16('dbg_bc_native_actor_unmapped') or r.u16('dbg_bc_native_unmapped'):reason='missing_art';break
 if round_==9 and status==6:reason='final_clear';break
 if tick!=last_tick:
  last_tick=tick
  cx,cy=struct.unpack('>HH',r.read('dbg_bc_native_camera',4));positions=struct.unpack('>8H',r.read('dbg_bc_native_party_position',16));lives=list(struct.unpack('>4H',r.read('dbg_bc_native_party_lives',8)))[:a.players]
  raw=read_actor_pool(r);boss=None
  for slot in range(32):
   b=raw[slot*50:(slot+1)*50];x=int.from_bytes(b[0:4],'big')>>8;y=int.from_bytes(b[4:8],'big')>>8
   if b[20]==128 and (b[22]&8 or int.from_bytes(b[34:36],'big')==0x36d0) and x<320 and y<256:
    boss=(x,y,b[24],b[25],slot);break
  if a.death_trace:trace_player_deaths(tick,round_,raw,(cx,cy))
  info=dict(tick=tick,frame=r.frames,round=round_+1,status=status,camera=[cx,cy],lives=lives,boss=boss)
  if tick-window_tick>=1000:
   windows.append(dict(start_tick=window_tick,end_tick=tick,updates=tick-window_tick,
       frames=r.frames-window_frame,start_round=window_round,end_round=round_+1,
       camera=[cx,cy],live_actors=sum(bool(raw[j*50+20]) for j in range(32))))
   window_tick=tick;window_frame=r.frames;window_round=round_+1
  if round_!=last_round:
   transitions.append(info);last_round=round_;r.capture(a.output/f'round-{round_+1}.png');print('ROUND',json.dumps(info),flush=True)
  if tick//2000!=last_log:
   last_log=tick//2000;print('PROGRESS',json.dumps(info),flush=True)
  terrain=player_terrain() if a.dodge else None
  scroll=None
  if a.scroll_prediction:
   o=pilot_layout.o
   sx=int.from_bytes(r.read('stage',2,o['bc_stage_dx']),'big',signed=True)
   sy=int.from_bytes(r.read('stage',2,o['bc_stage_dy']),'big',signed=True)
   scroll=(r.u32('stage'),r.u32('stage',4),sx,sy,not r.read('stage',1,o['bc_stage_stopped'])[0])
  pads=bytearray(8)
  predictions=[]
  fire_sides=[0]*4
  for i in range(a.players):
   x,y=positions[i*2:i*2+2]
   phase=(tick+i*120)%640;tx=48+(phase if phase<320 else 640-phase)//2;ty=120-16*i
   if round_ in (2,5):tx=(146 if 1150<cy<1500 else 128) if round_==2 else (170 if 400<cy<1010 or cy>1550 else 80);phase=(tick+i*120)%480;ty=64+(phase if phase<240 else 480-phase)//2
   elif (round_==6 and cx>1950) or (round_==3 and 1750<cx<2220):ty=72
   else:phase=(tick+i*160)%480;ty=64+(phase if phase<240 else 480-phase)//2
   if a.turret_lanes and round_==6 and cx>2300:ty=40 if i%2==0 else 88
   side=0x10 if tick%200>=100 else 0x20
   if boss:
    tx=(64+i*8) if boss[0]>=112 else (184+i*8);ty=max(24,min(208,boss[1]+(i*8-(a.players-1)*4)));side=0x20 if boss[0]>x else 0x10
   if boss and a.boss_standoff is not None:
    tx=max(16,min(240,boss[0]+(-a.boss_standoff if boss[0]>=112 else a.boss_standoff)))
   if a.seek_pickups and (pickup := pickup_target(raw, x, y)) is not None:
    tx,ty = pickup;pickup_target_updates += 1
   fire_sides[i]=side
   bits=(1 if x<tx-2 else 2 if x>tx+2 else 0)|(4 if y<ty-2 else 8 if y>ty+2 else 0)
   direct_boss_aim = boss and ((a.boss_four_direct_aim and round_==3) or (a.boss_nine_four_direct_aim and round_==8 and int.from_bytes(raw[34:36],'big')==0x36be))
   if a.dodge and not direct_boss_aim:
    address=r.symbols['player'] if i==0 else r.u32('peers')+(i-1)*pilot_layout.o['bc_player_size']
    fixed=tuple(int.from_bytes(bytes(pilot_layout.byte(address+j+k) for k in range(4)),'big')&65535 for j in (0,4))
    bits=dodge_direction(x,y,tx,ty,raw,player_speed(i),terrain,(cx,cy),scroll,fixed)
   if (tick%6<3 if a.rapid_fire else tick%100<80):bits|=side
   if a.lookahead and status==0:
    # Limit expensive branch evaluation to nearby hazards or a visible boss.
    threat = boss is not None or any(
        b[20]==128 and not (b[22]&2) and not b[38] and
        abs(((int.from_bytes(b[:4],'big')>>8)&65535)-x)<64 and
        abs(((int.from_bytes(b[4:8],'big')>>8)&65535)-y)<64
        for b in (raw[j*50:(j+1)*50] for j in range(32)))
    if threat:
     horizon=a.boss_four_lookahead if round_==3 and boss else a.boss_eight_lookahead if round_==7 and boss else a.boss_nine_eight_lookahead if round_==8 and boss and int.from_bytes(raw[34:36],'big')==0x36c0 else 4
     survival=a.boss_nine_eight_survival and round_==8 and boss and int.from_bytes(raw[34:36],'big')==0x36c0
     predictions.append((i,bits,old[i],(tx,ty),horizon,survival))
   if status==6:bits=0
   pads[2*i]=bits;pads[2*i+1]=bits&~old[i];old[i]=bits
  # Build all proposed controllers before forecasting any peer. Each search
  # starts from the same live machine, with earlier selected peer inputs held.
  for i,bits,previous,target,horizon,survival in predictions:
   bits=choose_move(r,pilot_layout,bits,previous,target,horizon=horizon,survival_tiebreak=survival,statistics=survival_statistics if survival else None,player_index=i,party_pads=pads,rapid_fire_sides=tuple(fire_sides) if a.predict_rapid_fire else None)
   pads[2*i]=bits;pads[2*i+1]=bits&~previous;old[i]=bits
  r.write('pad',pads)
 r.run(1)
else:reason='frame_limit'
gameplay_frames=r.frames-start_frames
gameplay_end_ram=hashlib.sha256(bytes(r.ram)).hexdigest()
gameplay_end_frame=r.frames
if a.lookahead or a.record_inputs:
 assert len(controller_record)==gameplay_end_frame*11
 (a.output/'controller-inputs.bin').write_bytes(controller_record)
 (a.output/'gameplay-end-ram.bin').write_bytes(bytes(r.ram))
 from bc_pilot_lookahead import machine_checkpoint
 (a.output/'machine-checkpoint.json').write_text(json.dumps(machine_checkpoint(r),indent=2)+'\n')
if profiler:assert profiler.done, "Campaign ended before profile completed"
(a.output/'timing-windows.json').write_text(json.dumps(dict(rom_sha256=digest,
    players=a.players,debug_protection=a.protect,gameplay_frames=gameplay_frames,
    scope='1000-update windows including intentional waits and transitions; excludes ending',
    windows=windows),indent=2)+'\n')
assert r.read('color_mode',1)[0]==int(a.color_mode=='vivid')
ending={}
gallery_samples=0;gallery_consecutive=0;gallery_expected=None
if a.gallery_palette_baseline:
 assert a.home, 'Gallery palette verification requires Home ending flow'
 import ctypes as C
 old_colors=struct.unpack('>32H',a.gallery_palette_baseline.read_bytes())
 def color_index(c):return (c>>1&7)|((c>>5&7)<<3)|((c>>9&7)<<6)
 gallery_expected=[]
 for i,c in enumerate(old_colors):
  light=(((c&14)*3+((c>>4)&14)*6+((c>>8)&14))//10)&14
  green=14 if light==14 else (light*5//14)*2
  blue=14 if light==14 else (light*2//14)*2
  word=light|(green<<4)|(blue<<8) if i&15 else 0
  if r.read('color_mode',1)[0]:
   word=struct.unpack_from('>H',rom.read_bytes(),r.symbols['vivid_lut']+color_index(word)*2)[0]
  gallery_expected.append(color_index(word))
 gallery_cram=(C.c_uint16*64).in_dll(r.lib,'cram')
if a.home and reason=='final_clear':
 r.write('pad',bytes(8));frozen_tick=r.u32('dbg_bc_native_ticks');ending_start=r.frames;phases=[]
 for _ in range(30000):
  phase=r.read('ending_bonus_phase',1)[0]
  gallery_consecutive=gallery_consecutive+1 if phase==3 else 0
  if gallery_expected is not None and gallery_consecutive>=2:
   assert list(gallery_cram[:32])==gallery_expected,('gallery palette changed',r.frames)
   gallery_samples+=1
  if not phases or phases[-1]!=phase:
   phases.append(phase);r.capture(a.output/f'ending-phase-{phase}.png')
  assert r.u32('dbg_bc_native_ticks')==frozen_tick
  if phase==7:break
  r.run(1)
 else:raise AssertionError(('ending timeout',phases))
 assert r.u16('ending_credit_clock')==5760
 r.run(60);assert r.read('ending_bonus_phase',1)==b'\7'
 ending=dict(phases=phases,frames=r.frames-ending_start,credit_updates=5760,gameplay_ticks_frozen=True)
 if gallery_expected is not None:
  assert gallery_samples>5000
  ending['gallery_palette_samples']=gallery_samples
  ending['gallery_palette_matches_baseline']=True
 button=bytearray(8);button[(a.players-1)*2:(a.players-1)*2+2]=bytes([0x10,0x10]);r.write('pad',button)
 for _ in range(120):
  r.run(1)
  if not r.u16('dbg_bc_native') and r.u32('flow_state')==9:break
 else:raise AssertionError('Home return failed')
 r.write('pad',bytes(8));r.write('dbg_pad_override',b'\0');r.run(30)
 assert r.u32('flow_state')==9 and not r.u16('dbg_bc_native')
 ending['home_returned']=True
game_over_home_returned=False
if a.home and a.use_continues and reason=='status_7':
 assert not r.read('continue_pending',1)[0], 'Stopped with an outstanding continue offer'
 r.capture(a.output/'game-over.png')
 r.write('pad',bytes([0x80,0x80]+[0]*6))
 for _ in range(120):
  r.run(1)
  if r.u32('flow_state')==9 and not r.u16('dbg_bc_native'):break
 else:raise AssertionError('Game-over Start did not return Home')
 r.write('pad',bytes(8));r.write('dbg_pad_override',b'\0');r.run(30)
 assert r.u32('flow_state')==9 and not r.u16('dbg_bc_native')
 game_over_home_returned=True
r.capture(a.output/'final.png');(a.output/'actors.bin').write_bytes(read_actor_pool(r));result=dict(gameplay_end_ram_sha256=gameplay_end_ram,gameplay_end_video_frame=gameplay_end_frame,rom_sha256=digest,players=a.players,debug_protection=a.protect,home_modal_launch=a.home,home_lives=a.home_lives,boss_four_lookahead=a.boss_four_lookahead,boss_eight_lookahead=a.boss_eight_lookahead,boss_nine_four_direct_aim=a.boss_nine_four_direct_aim,boss_nine_eight_lookahead=a.boss_nine_eight_lookahead,boss_nine_eight_survival=a.boss_nine_eight_survival,survival_statistics=survival_statistics,use_continues=a.use_continues,dodge=a.dodge,rapid_fire=a.rapid_fire,boss_standoff=a.boss_standoff,boss_four_direct_aim=a.boss_four_direct_aim,death_trace=a.death_trace,lookahead=a.lookahead,immediate_safety=a.immediate_safety,death_records=death_records,seek_pickups=a.seek_pickups,pickup_target_updates=pickup_target_updates,scroll_prediction=a.scroll_prediction,continue_attempts=continue_attempts,game_over_home_returned=game_over_home_returned,turret_lanes=a.turret_lanes,predict_rapid_fire=a.predict_rapid_fire,ending=ending,forced_boss_defeats=False,forced_player_deaths=False,seeded_health_or_weapons=False,reason=reason,ticks=r.u32('dbg_bc_native_ticks'),start_tick=start_tick,frames=r.frames-start_frames,round=r.u16('dbg_bc_native_current_round')+1,transitions=transitions,full_campaign_verified=False,full_speed_verified=False)
assert hashlib.sha256(rom.read_bytes()).hexdigest()==digest
if music_monitor:
 result['hucard_audio'] = music_monitor.finish(a.output, reason=='final_clear' and ending.get('home_returned',False))
if background_monitor:result['live_background_audit']=background_monitor.finish()
result['color_mode']=a.color_mode
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print('RESULT',json.dumps(result),flush=True)
