#!/usr/bin/env python3
"""Replay Normal or Boss Rush's bot at input-update boundaries, with fixed simulation updates.

The pinned host opcode hook applies QA pads/protection before input_update's
inlined override read. No cartridge instructions or emulated cycles are added.
Hashes cover player/shot records, all enemy records, RNG, frame and selected
level state (plus Rush counters and boss HUD in Rush); they are a comparison aid, not proof of whole-game fidelity.
Concurrent processes must use distinct output directories. Native offset
compilation is isolated per invocation by qa_soak.offsets().
"""
import argparse
import bisect
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
p.add_argument('--mode',choices=('normal','rush'),default='normal')
p.add_argument('--hucard',action='store_true',help='Select HuCard music through Home Options before the fixture')
p.add_argument('--players',type=int,choices=(1,2,3,4),required=True)
p.add_argument('--section',type=int,choices=range(10),default=8)
p.add_argument('--updates',type=int,default=1000)
p.add_argument('--stop-on-home',action='store_true',help='Normal only: stop at a Home return before the update limit; report this termination explicitly')
p.add_argument('--stop-on-rush-end',action='store_true',help='Rush only: stop at its result screen and report defeated bosses, without injecting completion')
p.add_argument('--output',type=Path,required=True)
p.add_argument('--dma-audit',action='store_true',help='Decode queued VDP transfers and inspect redundant sprite-pattern uploads')
p.add_argument('--scheduler-trace',action='store_true',help='Observe scheduler entry and following input boundary without changing guest timing')
p.add_argument('--profile',action='store_true',help='Save guest instruction-cycle attribution for this controlled replay')
p.add_argument('--profile-measurement',action='store_true',help='Restrict instruction attribution to measured updates, excluding intro and warp')
p.add_argument('--profile-window',type=int,nargs=2,metavar=('FIRST','END'),help='Attribute only this half-open range of measured update indices')
p.add_argument('--workload-trace',action='store_true',help='Read live object, weapon record and SAT counts at scheduler entry')
p.add_argument('--auto-level',type=int,choices=(16,17),default=17,help='AUTO pickup ID: 16 tests eight slots, 17 tests nine slots')
p.add_argument('--no-fire',action='store_true',help='Diagnostic controller variant: keep steering but omit fire, allowing more enemies to survive')
p.add_argument('--vulnerable',action='store_true',help='Allow ordinary damage/protection timers; the bot still supplies lives and AUTO weapons')
p.add_argument('--render-trace',action='store_true',help='Hash ordered SAT entries with resident sprite pixels')
p.add_argument('--drop-trace',action='store_true',help='Record sprite-drop changes and end-of-draw count/transfer budget')
p.add_argument('--vdp-trace',action='store_true',help='Hash all VRAM, CRAM and VSRAM at completed input boundaries; record parallax modes')
p.add_argument('--capture-backgrounds',action='store_true',help='Capture the first measured frame in each background zone and the final completed video frame')
p.add_argument('--background-audit-zones',type=int,nargs='+',help='Read-only settled background palette/cache checks at native input boundaries')
a=p.parse_args();assert a.updates>0
assert not a.stop_on_home or a.mode=='normal'
assert not a.stop_on_rush_end or a.mode=='rush'
if a.profile_window:
 assert 0<=a.profile_window[0]<a.profile_window[1]<=a.updates
 a.profile_measurement=True
if a.profile_measurement:a.profile=True
profile_phase=C.c_uint8(0) if a.profile_measurement else None
if a.dma_audit or a.workload_trace:a.scheduler_trace=True
a.output.mkdir(parents=True,exist_ok=True)
build=Path(os.environ.get('SIDEARMS_BUILD',ROOT))
rom=(build/'out/release/rom.bin').read_bytes();rom_hash=hashlib.sha256(rom).hexdigest()
r=Runner()
background_audit=None
if a.background_audit_zones:
 from normal_live_background_audit import NormalBackgroundAudit
 background_audit=NormalBackgroundAudit(r,rom,a.background_audit_zones,a.output)
zone_symbol='zone_id'
assert zone_symbol in r.symbols
background_zones_seen=set()
if a.workload_trace:
 from workload_metrics import WorkloadMetrics
 workload=WorkloadMetrics(r,a.players)
# Locate the compiler's absolute byte read of the existing override flag.
# LTO may duplicate it across loop-entry branches. Require validated opcode
# and placement in main; don't assume a fixed ROM address or destination Dn.
# The shared lifecycle may spill this byte directly to d16(SP), retaining the
# same input boundary. Accept only those two verified destination forms.
syms=[]
for line in (build/'out/release/symbol.txt').read_text().splitlines():
 v=line.split()
 if len(v)>=3 and v[1] in ('t','T'):syms.append((int(v[0],16),v[2]))
start=next(at for at,name in syms if name.startswith('main.'))
end=min(at for at,name in syms if at>start)
operand=struct.pack('>I',r.symbols['dbg_pad_override'])
pcs=[at for at in range(start,end-5,2) if rom[at+2:at+6]==operand
     and ((int.from_bytes(rom[at:at+2],'big')&0xf1ff)==0x1039
          or (int.from_bytes(rom[at:at+2],'big')==0x1f79 and at+8<=end))]
boundary_kind='inlined override read in main'
if not pcs and 'input_update' in r.symbols:
 # Current shared scheduling keeps input_update out of line. Hook entry,
 # before any pad fields can be loaded, and verify its override-read prologue.
 target=r.symbols['input_update']
 reads=[at for at in range(target,target+32,2) if rom[at+2:at+6]==operand
        and ((int.from_bytes(rom[at:at+2],'big')&0xf1ff)==0x1039
             or int.from_bytes(rom[at:at+2],'big')==0x1f79)]
 assert len(reads)==1,('unknown input_update prologue',reads)
 pcs=[target];boundary_kind='verified out-of-line input_update entry'
assert 1<=len(pcs)<=8,('unrecognized input boundary',pcs)
def tap(b):r.run(5,PAD[b]);r.run(15)
r.run(2600);tap('DOWN');tap('START')
if a.mode=='normal' or a.hucard:
 for _ in range(3):tap('DOWN')
 tap('A');assert r.u32('flow_state')==1
 assert r.read('home_cfg',1,6)==b'\1'
 if a.hucard:
  for _ in range(8):tap('DOWN')
  tap('RIGHT') # The setting becomes active when Options closes.
 tap('B')
 for _ in range(3):tap('UP')
if a.mode=='rush':
 assert not (a.dma_audit or a.workload_trace), 'Normal-specific audits unsupported in Rush'
 tap('DOWN');tap('DOWN')
assert r.read('music_source',1)==bytes([int(a.hucard)]), 'Unexpected music-source fixture'
tap('A');assert r.read('player_dialog',1)==b'\1'
for _ in range((a.players-2)%4):tap('DOWN')
# Release A at the first hooked input boundary, rather than advancing an
# unobserved number of gameplay frames after launch.
if a.mode=='rush':
 for _ in range(10):
  r.run(1,PAD['A'])
  if r.u32('flow_state')==12:break
 assert r.u32('flow_state')==12 and r.u16('player_limit')==a.players
else:tap('A')
r.write('dbg_pad_override',b'\1')
phase='intro';intro=0;completed=0;started=None;ended=None;hashes=[];worst=0;last_frame=None
update_video_frames=[]
drop_samples=[];drop_last=[None]
presentation_start=[None];skips_start=[0]
termination=None
scheduler_rows=[];scheduler_pending=None
control_tick=0;boss_indices=set();rush_states=set()
work_start_clock=None
scheduler_pcs=[at for at,name in syms if name.startswith('SYS_doVBlankProcessEx')]
cpu=C.addressof(C.c_uint8.in_dll(r.lib,'m68k'))
if a.workload_trace:assert C.c_uint32.in_dll(r.lib,'mcycles_vdp').value==896040
watch_pcs=pcs+scheduler_pcs if a.scheduler_trace else pcs
assert len(watch_pcs)<=8
vdp_hashes=[];parallax_modes={}
render_hashes=[];drops_start=remaps_start=0;drops_end=remaps_end=0

def state_hash():
 data=r.read('players',O['s_Player']*4)
 for name,n in [('en_small',1600),('en_big',960),('en_item',320),
                ('en_rng',1),('en_rnd',7),('en_rng_div',1),('en_target_tick',1),('frame',2)]:
  data+=r.read(name,n)
 for name in ['section','scroll_x','scroll_y','mode','tick']:
  data+=r.read('level',2,O['o_Level_'+name])
 if a.mode=='rush':
  for name,n in [('rush_rs',1),('rush_idx',1),('rush_timer',2),('rush_frames',4),('rush_defeated',1),('boss_kills',2),('boss_hud',4)]:
   data+=r.read(name,n)
 return hashlib.sha256(data).hexdigest()

def render_hash():
 # Normalize away cache tile addresses; compare the ordered sprite attributes,
 # positions, dimensions and actual resident pattern bytes instead.
 sat=struct.unpack('>320H',r.read('vdpSpriteCache',640));data=bytearray();seen=set();slot=0
 for _ in range(80):
  assert slot<80 and slot not in seen, ('invalid SAT link',slot)
  seen.add(slot);y,size,attr,x=sat[slot*4:slot*4+4]
  data.extend(struct.pack('>4H',y,size&0xff00,attr&0xf800,x))
  length=(((size>>10)&3)+1)*(((size>>8)&3)+1)*32
  address=(attr&0x7ff)*32
  data.extend(r.vram[((address+i)&65535)^1] for i in range(length))
  slot=size&127
  if not slot:break
 else:raise AssertionError('unterminated SAT')
 return hashlib.sha256(data).hexdigest()

def vdp_hash():
 # Raw native memory representation is stable within the pinned emulator.
 # Includes background maps/pixels and scroll tables, unlike SAT-only tracing.
 data=bytes(r.vram)
 data+=bytes((C.c_uint8*128).in_dll(r.lib,'cram'))
 data+=bytes((C.c_uint8*128).in_dll(r.lib,'vsram'))
 mode=r.read('par_dbg_mode',1)[0]
 parallax_modes[mode]=parallax_modes.get(mode,0)+1
 return hashlib.sha256(data).hexdigest()

def dma_audit():
 # DMAOpInfo is four big-endian longwords in this pinned SGDK build.
 def memory(address,size):
  address &= 0xffffff
  if address+size<=len(rom):return rom[address:address+size]
  assert address>=0xff0000,(hex(address),size)
  return bytes(r.ram[((address+i)&65535)^1] for i in range(size))
 pointer=r.u32('dmaQueues');count=r.u16('queueIndex')
 assert count<=r.u16('queueSize')
 raw_vram=bytes(r.vram)
 shadow=bytearray(raw_vram[i^1] for i in range(65536))
 candidates=[];total=0
 bank_ranges=[]
 for bank,index,size in [('spr_bank','spr_bank_index',128),('spr_big','spr_big_index',512)]:
  values=struct.unpack_from('>32768H',rom,r.symbols[index])
  bank_ranges.append((bank,r.symbols[bank],max(v&32767 for v in values)*size,size))
 for i in range(count):
  lh,ms,hl,control=struct.unpack('>4I',memory(pointer+i*16,16))
  words=((lh>>16)&255)|((lh&255)<<8)
  assert words>0
  source=((hl&0x7f0000)|((ms>>8)&0xff00)|(hl&255))<<1
  target=((control>>16)&0x3fff)|((control&3)<<14)
  step=ms&255;kind=control&0xc00000f0
  assert kind in (0x40000080,0xc0000080,0x40000090),hex(control)
  total+=words*(2 if kind==0x40000080 else 1)
  if kind!=0x40000080:continue
  pixels=memory(source,words*2)
  for bank,start,length,size in bank_ranges:
   if step==2 and words*2==size and start<=source<start+length and (source-start)%size==0:
    old=bytes(shadow[target:target+size])
    slots=([1056*32+j*128 for j in range(48 if a.players>2 else 64)] if size==128 else
      [1664*32+j*512 for j in range(8)]+[1953*32+j*512 for j in range(5)]+
      ([1056*32+48*128+j*512 for j in range(4)] if a.players>2 else []))
    # Extra large slots beyond the shared small region use HUD tiles; omit
    # them here rather than guess. Other-slot matches are opportunities only.
    slots=[v for v in slots if v+size<=65536]
    other=[v for v in slots if v!=target and bytes(shadow[v:v+size])==pixels]
    candidates.append(dict(bank=bank,source=source,target=target,bytes=size,
      blank=not any(pixels),destination_identical=old==pixels,other_resident_matches=len(other),
      pixel_sha256=hashlib.sha256(pixels).hexdigest()))
  for word in range(words):
   address=(target+word*step)&65535
   shadow[address]=pixels[word*2];shadow[(address+1)&65535]=pixels[word*2+1]
 assert total==r.u16('queueTransferSize'),(total,r.u16('queueTransferSize'))
 return dict(transfer_count=count,transfer_bytes=total,sprite_uploads=candidates)

def boundary():
 global phase,intro,completed,started,ended,worst,last_frame,drops_start,remaps_start,drops_end,remaps_end
 global scheduler_pending,work_start_clock,control_tick,termination
 if phase=='done':return
 if a.drop_trace and phase=='measure':
  current=r.u32('spr_dbg_dropped')
  if drop_last[0] is not None and current!=drop_last[0]:
   drop_samples.append(dict(update=completed,frame=r.u16('frame'),delta=(current-drop_last[0])&0xffffffff,
    submitted=r.u16('count'),remaining_sprite_transfer_budget=r.u16('budget')))
  drop_last[0]=current
 if a.scheduler_trace:
  pc=(C.c_uint32.from_address(cpu+0x2858).value-2)&0xffffff
  if pc in scheduler_pcs:
   if phase=='measure':
    assert scheduler_pending is None
    scheduler_pending=dict(frame=r.u16('frame'),scanline=C.c_uint16.in_dll(r.lib,'v_counter').value,
      vtimer=r.u32('vtimer'),dma_bytes=r.u16('queueTransferSize'),dma_operations=r.u16('queueIndex'))
    if a.workload_trace:
     scheduler_pending['workload']=workload.sample('normal')
     scheduler_pending['work_lines']=r.u16('prof_seg',6)-r.u16('prof_seg',0)
     assert work_start_clock is not None
     scheduler_pending['work_ticks']=r.frames*896040+C.c_uint32.from_address(cpu+0x280c).value-work_start_clock
    if a.dma_audit:scheduler_pending['dma_audit']=dma_audit()
   return
  assert pc in pcs
  if scheduler_pending is not None:
   scheduler_pending.update(next_input_scanline=C.c_uint16.in_dll(r.lib,'v_counter').value,
      next_input_vtimer=r.u32('vtimer'))
   scheduler_rows.append(scheduler_pending);scheduler_pending=None
 if a.mode=='rush' and phase=='intro':
  assert r.u32('flow_state')==12
  if r.read('rush_rs',1)==b'\1' and r.read('boss_hud',1)!=b'\0':phase='warp'
 # FS_PLAY becomes visible before the players spawn. Warping during that
 # interval can be overwritten by stage initialization; changed render cost
 # can then make two ROMs start the same fixture at different logical states.
 if a.mode=='normal' and phase=='intro' and (r.u32('flow_state')!=7 or
     any(r.u32('players',i*O['s_Player']+O['o_Player_state'])!=1 for i in range(a.players))):
  b=0x80 if intro%40==0 else 0x10 if intro%40==20 else 0
  r.write('pad',bytes([b,b]*a.players+[0,0]*(4-a.players)));intro+=1;return
 if a.mode=='normal' and phase=='intro':
  assert r.u16('player_limit')==a.players
  r.write('frame',bytes(2));r.write('en_rng',b'\0');r.write('en_rnd',bytes(7))
  r.write('en_rng_div',b'\0');r.write('en_target_tick',b'\0')
  r.write('dbg_warp',struct.pack('>H',a.section+1));phase='warp'
 elif phase=='warp' and (a.mode=='rush' or not r.u16('dbg_warp')):
  if profile_phase is not None:profile_phase.value=1
  phase='measure';started=r.frames;hashes.append(state_hash());last_frame=r.u16('frame')
  drops_start=r.u32('spr_dbg_dropped');remaps_start=r.u32('spr_dbg_remap')
  drop_last[0]=drops_start;presentation_start[0]=r.u32('frame_counter')
  if 'dbg_normal_render_skips' in r.symbols:skips_start[0]=r.u32('dbg_normal_render_skips')
  if a.render_trace:render_hashes.append(render_hash())
  if a.vdp_trace:vdp_hashes.append(vdp_hash())
 elif phase=='measure':
  if background_audit:background_audit.observe(completed)
  zone=r.u16(zone_symbol)
  if zone not in background_zones_seen:
   background_zones_seen.add(zone)
   if a.capture_backgrounds:r.capture(a.output/f'zone-{zone}.png')
  now=r.u16('frame');assert now==(last_frame+1)&65535,('input boundary cadence',last_frame,now)
  last_frame=now
  completed+=1;hashes.append(state_hash());update_video_frames.append(r.frames)
  if a.render_trace:render_hashes.append(render_hash())
  if a.vdp_trace:vdp_hashes.append(vdp_hash())
  worst=max(worst,r.u16('prof_seg',6))
  if completed==a.updates:
   if profile_phase is not None:profile_phase.value=0
   ended=r.frames;phase='done';termination='update_limit'
   drops_end=r.u32('spr_dbg_dropped');remaps_end=r.u32('spr_dbg_remap');return
 if a.stop_on_home and phase=='measure' and r.u32('flow_state')==9:
  if profile_phase is not None:profile_phase.value=0
  ended=r.frames;phase='done';termination='home_return'
  drops_end=r.u32('spr_dbg_dropped');remaps_end=r.u32('spr_dbg_remap');return
 if a.stop_on_rush_end and phase=='measure' and r.u32('flow_state')==13:
  if profile_phase is not None:profile_phase.value=0
  ended=r.frames;phase='done';termination='rush_result'
  drops_end=r.u32('spr_dbg_dropped');remaps_end=r.u32('spr_dbg_remap');return
 assert r.u32('flow_state')==(12 if a.mode=='rush' else 7),('left gameplay',r.u32('flow_state'),completed)
 if a.mode=='rush':
  boss_indices.add(r.read('rush_idx',1)[0]);rush_states.add(r.read('rush_rs',1)[0])
 if a.workload_trace:
  work_start_clock=r.frames*896040+C.c_uint32.from_address(cpu+0x280c).value
 if a.profile_window and phase=='measure':
  profile_phase.value=int(a.profile_window[0]<=completed<a.profile_window[1])
 bits=[]
 for i in range(a.players):
  off=i*O['s_Player']
  if not a.vulnerable:r.write('players',b'\xc8',off+O['o_Player_invuln'])
  if a.mode=='normal':r.write('players',b'\x07',off+O['o_Player_lives'])
  x=int.from_bytes(r.read('players',2,off+O['o_Player_x']),'big',signed=True)
  y=int.from_bytes(r.read('players',2,off+O['o_Player_y']),'big',signed=True)
  tx=48+i*24;ty=32+i*40+int(12*math.sin((control_tick if a.mode=='rush' else completed)/90+i))
  b=(0 if a.no_fire else 0x20)|(1 if x<tx-3 else 2 if x>tx+3 else 0)|(4 if y<ty-3 else 8 if y>ty+3 else 0)
  if r.read('players',1,off+O['o_Player_weapon'])!=b'\x05':
   if a.mode=='normal':r.write('dbg_player_cmd',bytes([a.auto_level]),i)
   elif (control_tick//4)%2==0:b|=0x40
  bits.extend([b,b])
 r.write('pad',bytes(bits+[0,0]*(4-a.players)))
 control_tick+=1

audio_ram=(C.c_uint8*8192).in_dll(r.lib,'zram');underrun_frames=0
with instruction_profile(r,a.output/'cpu',enabled=a.profile,watch=(watch_pcs,boundary),phase=profile_phase):
 for _ in range(a.updates*10+5000):
  r.run(1)
  if a.hucard and audio_ram[0x1b0a]:underrun_frames+=1
  if phase=='done':break
assert phase=='done',('replay did not finish',phase,completed)
if a.capture_backgrounds:r.capture(a.output/'final-background.png')
assert hashlib.sha256((build/'out/release/rom.bin').read_bytes()).hexdigest()==rom_hash
class AVInfo(C.Structure):
 _fields_=[('geometry',C.c_uint*4),('aspect',C.c_float),('fps',C.c_double),('sample_rate',C.c_double)]
av=AVInfo();r.lib.retro_get_system_av_info(C.byref(av))
window=round(av.fps*5)
rolling=[(bisect.bisect_right(update_video_frames,t+window)-bisect.bisect_right(update_video_frames,t))*av.fps/window
 for t in range(started,ended-window+1)]
result=dict(mode=a.mode,rom_sha256=rom_hash,players=a.players,section=a.section if a.mode=='normal' else None,updates=completed,
 music_source='hucard' if a.hucard else 'arcade',
 hucard_underrun_frames=underrun_frames,
 refresh_hz=av.fps,updates_per_second=completed*av.fps/(ended-started),
 presentation_batches=r.u32('frame_counter')-presentation_start[0],
 presentation_batches_per_second=(r.u32('frame_counter')-presentation_start[0])*av.fps/(ended-started),
 render_skips=r.u32('dbg_normal_render_skips')-skips_start[0] if 'dbg_normal_render_skips' in r.symbols else 0,
 minimum_rolling_five_second_rate=min(rolling) if rolling else None,
 ntsc_50_update_gate=(min(rolling)>=50) if rolling and av.fps>55 else None,
 update_video_frames=[f-started for f in update_video_frames],
 background_zones_seen=sorted(background_zones_seen),
 emulated_frames=ended-started,worst_lines=worst,input_boundary_pcs=pcs,
 input_boundary_kind=boundary_kind,
 protected=not a.vulnerable,parallax=True,state_hashes=hashes,instruction_profile=a.profile,
 no_fire=a.no_fire,auto_level=a.auto_level if a.mode=='normal' else None,profile_scope="measured updates" if a.profile_measurement else "whole hooked run",
 profile_update_window=a.profile_window,
 full_game_verified=False,sprite_drops=(drops_end-drops_start)&0xffffffff,
 runtime_remaps=(remaps_end-remaps_start)&0xffffffff)
if a.stop_on_home or a.stop_on_rush_end:
 # The core finishes its video frame after the watched instruction returns.
 # Latch the reason at the stopping boundary, before flow can advance again.
 assert termination in ('home_return','rush_result','update_limit')
 result['termination']=termination
 result['requested_update_limit']=a.updates
if a.mode=='rush':
 result['bosses_defeated']=r.read('rush_defeated',1)[0]
 result.update(boss_indices=sorted(boss_indices),rush_states=sorted(rush_states),
  loadout='Rush defaults; AUTO selected through C',
  state_scope='Players, enemies, RNG, selected level fields, Rush counters and boss HUD; excludes private boss internals',
  render_scope='Ordered SAT and resident sprite patterns; excludes background and HUD raster timing')
if a.render_trace:result['render_hashes']=render_hashes
if a.drop_trace:result['drop_trace']=drop_samples
if a.vdp_trace:
 result.update(vdp_hashes=vdp_hashes,parallax_modes=parallax_modes,
  vdp_scope='Raw VRAM/CRAM/VSRAM at input boundaries; excludes register/raster timing')
if a.scheduler_trace:result['scheduler_rows']=scheduler_rows
if a.workload_trace:
 result['workload_scope']=workload.scope
 result['workload_abi']=workload.o
if background_audit:result['background_audit']=background_audit.result()
(a.output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('state_hashes','render_hashes','vdp_hashes','scheduler_rows','update_video_frames')},indent=2))
raise SystemExit(0 if ended-started==completed else 1)
