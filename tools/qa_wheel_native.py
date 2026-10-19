#!/usr/bin/env python3
"""Native wheel entry, all frame caches and source lightning; assisted boss damage."""
import argparse,hashlib,json,struct
from pathlib import Path
from run_rom import Runner,PAD
from arcade_source import Source
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--section',type=int,choices=(2,4,9),required=True)
p.add_argument('--players',type=int,choices=(1,4),default=1)
p.add_argument('--plain',action='store_true',help='Normal without Home parallax: original Arcade wheel frames')
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
r=Runner();rom=Path('out/release/rom.bin').read_bytes()
def tap(k):r.run(5,PAD[k]);r.run(20)
r.run(2600);tap('DOWN');tap('A')
if a.plain:r.write('home_cfg',b'\0',6)
for k in ['UP','DOWN','UP','DOWN','LEFT','RIGHT','LEFT','RIGHT']:tap(k)
while r.read('home_cursor',1)!=b'\4':tap('DOWN')
tap('A')
if r.read('developer_mode',1)!=b'\0':tap('LEFT')
for _ in range(4):tap('DOWN')
for _ in range(a.players - 1):tap('RIGHT')
tap('DOWN')
tap('A')
for _ in range(1800):
 r.run(1)
 if r.u32('flow_state')==7:break
assert r.u32('flow_state')==7 and r.read('developer_active',1)==b'\1'
r.run(60);r.write('dbg_warp',((0x200 if a.section == 9 else 0x100)+a.section).to_bytes(2,'big'))
original = Source().region('maincpu')
checks=0;poses=set();cracks=set();entry=False;started=None;initial=None;warnings=[];max_glyphs=0
for tick in range(5000):
 r.run(1)
 active=r.read('w',1)[0]
 if active and not entry:
  entry=True;initial=r.read('w',178)
  for k in range(8):
   delay=original[0x720D+2*k]
   assert delay-2<=initial[8+18*k+4]<=delay,('pod first wait',k,initial.hex())
 if not active and started is not None:break
 if not active:continue
 raw=r.read('w',178);crack=raw[176]
 # The original five crack frames each last six game updates.
 if crack:
  f=(30-crack)//6
  if f not in cracks:r.capture(a.output/f'lightning-{f}.png')
  cracks.add(f)
 max_glyphs=max(max_glyphs,r.u16('game_pool',16))
 assert r.u16('game_pool',16)<r.u16('game_pool',18), 'HUD glyph pool exhausted'
 fr=r.u32('fr')
 if not fr or r.read('fr_state',1)!=b'\2':continue
 if started is None:started=tick
 shown=int.from_bytes(r.read('fr_shown',2),'big',signed=True)
 if shown>=0 and shown not in poses:
  r.capture(a.output/f'pose-{shown}.png');poses.add(shown)
 zone=r.u32('zone');count=struct.unpack_from('>H',rom,zone+8)[0]
 tiles=struct.unpack_from('>I',rom,zone+10)[0];extra=struct.unpack_from('>I',rom,fr+18)[0]
 n=r.u16('fr_nmeta');metas=struct.unpack('>'+str(n)+'H',r.read('fr_meta',n*2))
 for meta in metas:
  assert meta!=65535,('wheel cache exhausted',tick)
  slot=r.read('meta_slot',1,meta)[0];assert slot<56
  address=tiles+meta*512 if meta<count else extra+(meta-count)*512
  v=(160+slot*16)*32;got=bytes(r.vram[(v+i)^1] for i in range(512))
  assert got==rom[address:address+512],('resident wheel artwork',tick,slot,meta)
  checks+=1
 if tick-started==800:r.write('boss_dbg_autohit',b'\1')
assert entry and poses=={0,1,2} and cracks==set(range(5)),(entry,poses,cracks)
assert not r.read('w',1)[0], 'boss did not finish'
assert r.u16('level')==a.section,('section exit',r.u16('level'))
r.run(60);r.capture(a.output/'exit.png')
report=dict(passed=True,section=a.section,players=a.players,parallax=not a.plain,rom_sha256=hashlib.sha256(rom).hexdigest(),
 pattern_checks=checks,poses=sorted(poses),lightning_frames=sorted(cracks),maximum_hud_glyphs=max_glyphs,
 entry_waits_verified=True,assisted_boss_damage=True,warp_before_boss=True)
(a.output/'report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
