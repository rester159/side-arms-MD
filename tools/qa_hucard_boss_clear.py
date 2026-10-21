#!/usr/bin/env python3
"""Native Home/PCE first boss-clear regression; assisted boss damage, real stage progression."""
import sys,os,ctypes as C,json,wave,hashlib
from pathlib import Path
import numpy as np
sys.path.insert(0,'tools')
from run_rom import Runner,PAD
out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
r=Runner()
import struct
rom=Path('out/release/rom.bin').read_bytes()
cram=(C.c_uint16*64).in_dll(r.lib,'cram')
palette_checks=[]
def tap(k):r.run(5,PAD[k]);r.run(20)
r.run(60);r.run(1,PAD['START']);r.run(90)
tap('DOWN');tap('A')
for _ in range(3):tap('DOWN')
tap('A')
for _ in range(8):tap('DOWN')
tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
tap('B')
for k in ['UP','DOWN','UP','DOWN','LEFT','RIGHT','LEFT','RIGHT']:tap(k)
while r.read('home_cursor',1)!=b'\4':tap('DOWN')
tap('A')
for _ in range(5):tap('DOWN')
tap('A');assert r.read('developer_active',1)==b'\1'
z=(C.c_uint8*8192).in_dll(r.lib,'zram');buf=[]
cb=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)(lambda p,n:buf.append(np.ctypeslib.as_array(p,(n*2,)).copy()) or n)
r.callbacks.append(cb);r.lib.retro_set_audio_sample_batch(cb)
records=[];prev=None;boss_start=None;clear=None;audio=[]
for t in range(22000):
 r.run(1,PAD['C'])
 assert z[0x1f0b] == 3, ('PCE SFX mix reset', t, z[0x1f0b])
 state=r.u32('flow_state')
 if state==7 and t in (1000,2200,4000,8400):
  zone=r.u16('zone_id');name='zone0_vivid_pal' if zone==0 else f'zone{zone}_pal'
  colors=struct.unpack_from('>32H',rom,r.symbols[name])
  pack=lambda w:(w>>1&7)|(w>>5&7)<<3|(w>>9&7)<<6
  if zone!=0:
   lut=struct.unpack_from('>512H',rom,r.symbols['vivid_lut']);colors=[lut[pack(w)]for w in colors]
  assert list(cram[:32])==[pack(w)for w in colors], ('CRAM',t,zone)
  sp=struct.unpack_from('>32H',rom,r.symbols['sprite0_vivid_pal' if zone==0 else 'sprite_pal'])
  if zone!=0:sp=[lut[pack(w)]for w in sp]
  assert list(cram[32:])==[pack(w)for w in sp],('sprite CRAM',t,zone)
  palette_checks.append(dict(frame=t,zone=zone,words=64))
 track=r.u16('dbg_hucard_track');starts=r.u16('dbg_hucard_starts')
 if t in (120,1000,2200,4000):r.capture(out/f'stage-{t}.png')
 key=(state,track,starts)
 if key!=prev:
  records.append(dict(frame=t,state=state,track=track,starts=starts,underruns=int(z[0x1b0a])))
  print(records[-1],flush=True);prev=key
 if track==18 and boss_start is None:boss_start=t
 if boss_start is not None and t-boss_start==240:
  r.capture(out/'boss.png');r.write('boss_dbg_autohit',b'\1')
 if track==10 and clear is None:clear=t;r.capture(out/'clear.png')
 if boss_start is not None:audio+=buf
 buf.clear()
 if clear is not None and t-clear>1000:break
assert clear is not None,records
samples=np.concatenate(audio).astype('<i2')
with wave.open(str(out/'boss-clear.wav'),'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(44100);w.writeframes(samples.tobytes())
report=dict(events=records,boss_start=boss_start,clear=clear,peak=int(abs(samples.astype(int)).max()),clipped=int((abs(samples.astype(int))>=32767).sum()),underruns=int(z[0x1b0a]),assisted_boss_hits=True)
report['palette_checks']=palette_checks
assert {c['zone'] for c in palette_checks}=={0,1}
assert report['clipped']==0 and report['underruns']==0, report
report['persistent_sfx_attenuation']=3
report['players']=r.u16('player_limit')
report['rom_sha256']=hashlib.sha256(Path('out/release/rom.bin').read_bytes()).hexdigest()
(out/'report.json').write_text(json.dumps(report,indent=2));print(report)
