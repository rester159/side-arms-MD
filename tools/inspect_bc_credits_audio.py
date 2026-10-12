#!/usr/bin/env python3
"""Measure native credits audio coverage against the captured CD request.

Forces credits setup after entering the real BC scene. This isolates soundtrack
coverage; it is not a final-boss/campaign playthrough or a fidelity pass.
"""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import numpy as np
from run_rom import ROOT, Runner

code_path=ROOT/'.local/pce-reference/round10-ending-presentation/code-007080.bin'
code=code_path.read_bytes()
assert hashlib.sha256(code).hexdigest()=='bbd7f05a8d836aa565e75cabf93a415fa30fc1f47eade5968ed82dfa7ea8788b'
request=code[0x998e-0x4000:0x9996-0x4000]
assert request==bytes.fromhex('4444194046371743')
def bcd(v):
    assert (v>>4)<10 and (v&15)<10
    return (v>>4)*10+(v&15)
def sector(msf):
    m,s,f=map(bcd,msf)
    assert s<60 and f<75
    return (m*60+s)*75+f
source_seconds=(sector(request[4:7])-sector(request[:3]))/75
r=Runner();r.run(2600)
r.write('home_session',b'\1')
for name,value in [('dbg_bc_native_players',1),('dbg_bc_native_start_round',9),
                   ('dbg_bc_native_protect',1),('dbg_bc_native',1)]:
    r.write(name,value.to_bytes(2,'big'))
r.run(180)
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8))
r.write('dbg_bc_native_status',b'\0\6');r.write('ending_bonus_phase',b'\5')
# One-second bins use 60 emulated video frames, matching the ending's update
# clock. Energy includes every delivered stereo sample, not only track onset.
bins=math.ceil(source_seconds)+10
energy=np.zeros(bins);samples=np.zeros(bins,dtype=np.int64)
sums=np.zeros((bins,2))
stop_frame=None
current=0
def audio(pointer,count):
    values=np.ctypeslib.as_array(pointer,shape=(count*2,)).astype(np.float64)
    energy[current]+=np.dot(values,values);samples[current]+=len(values)
    sums[current]+=values.reshape(-1,2).sum(axis=0)
    return count
callback_type=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
callback=callback_type(audio)
r.lib.retro_set_audio_sample_batch.argtypes=[callback_type]
r.lib.retro_set_audio_sample_batch(callback)
for frame in range(bins*60):
    current=frame//60;r.run(1)
    assert r.u16('dbg_bc_native')==1
    if stop_frame is None and r.u16('ending_music_clock')==6778:stop_frame=frame
assert r.read('ending_bonus_phase',1)==b'\7'
assert r.u16('dbg_bc_native_music_command')==0xfe
assert np.all(samples>0)
rms=np.sqrt(energy/samples)
# Remove each stereo channel's DC bias before assessing terminal silence.
means=sums/(samples[:,None]/2)
ac_rms=np.sqrt(np.maximum(0,energy/samples-(means**2).mean(axis=1)))
threshold=100.0
quiet=[i for i,value in enumerate(rms[:96]) if value<threshold]
assert not quiet, ('credits music stopped during scroll', quiet)
assert stop_frame == 6779, ('finite credits timer changed', stop_frame)
# Allow one bin for the queued stop and output filter to settle, then require
# actual zero samples throughout the remaining eight seconds of input wait.
assert ac_rms[113] < 20 and np.all(energy[114:] == 0), ac_rms[113:]
result=dict(rom_sha256=hashlib.sha256((ROOT/'out/release/rom.bin').read_bytes()).hexdigest(),
    source_request=request.hex(),source_playback_seconds=source_seconds,
    stop_frame=stop_frame, ending_music_clock=r.u16("ending_music_clock"),
    ac_rms_by_bin=[round(float(v),3) for v in ac_rms],
    credits_scroll_updates=5760,bin_video_frames=60,rms_threshold=threshold,
    rms_by_bin=[round(float(v),3) for v in rms],quiet_scroll_bins=quiet,
    last_audible_bin=max(i for i,v in enumerate(rms) if v>=threshold),
    uninterrupted_scroll_audio_verified=not quiet,terminal_silence_verified=True,
    full_fidelity_verified=False,
    fixture='credits phase injected; actual native driver output')
out=ROOT/'.local/bc-credits-audio';out.mkdir(exist_ok=True)
(out/'coverage.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('rms_by_bin','ac_rms_by_bin')},indent=2))
