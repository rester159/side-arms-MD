#!/usr/bin/env python3
"""Exercise real BC player sound events through the Genesis sound driver."""
import ctypes as C
import json
import numpy as np
from run_rom import Runner,ROOT
r=Runner();r.run(2600)
r.write('dbg_pad_override',b'\1');r.write('dbg_bc_native_protect',b'\0\1')
r.write('dbg_bc_native_audio_manual',b'\0\1');r.write('dbg_bc_native',b'\0\1');r.run(30)
assert r.u16('dbg_bc_native_status')==4
r.write('dbg_bc_native_audio_ack',b'\0\1');r.run(150)
assert r.u16('dbg_bc_native_sfx_commands')==0
chunks=[]
def audio(p,n):chunks.append(C.string_at(p,n*4));return n
ctype=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t);callback=ctype(audio)
r.lib.retro_set_audio_sample_batch.argtypes=[ctype];r.lib.retro_set_audio_sample_batch(callback)
def advance(updates,held,pressed=0):
    target=r.u32('dbg_bc_native_ticks')+updates
    for frame in range(updates*3+10):
        r.write('pad',bytes([held,pressed if frame==0 else 0,0,0,0,0,0,0]))
        r.run(1)
        if r.u32('dbg_bc_native_ticks')>=target:return
    raise AssertionError('native updates stalled')
advance(20,0x20,0x20);advance(25,0)
advance(65,0x20,0x20);advance(50,0)
mask=r.u32('dbg_bc_native_sfx_mask');required=sum(1<<n for n in (1,5,7,0x17))
assert mask&required==required,hex(mask)
assert not r.u16('dbg_bc_native_sfx_dropped')
samples=np.frombuffer(b''.join(chunks),dtype=np.int16).astype(float)
rms=float(np.sqrt(np.mean((samples-samples.mean())**2)));assert rms>1
result=dict(commands=r.u16('dbg_bc_native_sfx_commands'),source_mask=hex(mask),dropped=0,rms=rms,original_pce_samples_verified=False)
r.write('dbg_bc_native',b'\0\0');r.write('dbg_pad_override',b'\0');r.run(120);assert r.u32('flow_state')==0
result['returned_to_menu']=True
(ROOT/'.local/pce-reference/player-sfx.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
