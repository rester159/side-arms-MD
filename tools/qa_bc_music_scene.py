#!/usr/bin/env python3
"""Verify autonomous BC music requests reach the Genesis driver and produce audio.
Tests our replacement soundtrack, not CD recording or original BIOS latency.
"""
import argparse
import struct
import ctypes as C
import json
import wave
import numpy as np
from run_rom import ROOT,Runner
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--round',type=int,choices=(1,9),default=1)
args=parser.parse_args()
r=Runner();r.run(2600)
r.write('dbg_bc_native_start_round',struct.pack('>H',args.round-1))
class Geometry(C.Structure):
    _fields_=[(n,C.c_uint) for n in ('width','height','max_width','max_height')]+[('aspect',C.c_float)]
class Timing(C.Structure):
    _fields_=[('fps',C.c_double),('rate',C.c_double)]
class AV(C.Structure):
    _fields_=[('geometry',Geometry),('timing',Timing)]
av=AV();r.lib.retro_get_system_av_info.argtypes=[C.POINTER(AV)];r.lib.retro_get_system_av_info(C.byref(av))
chunks=[]
def audio(p,n):chunks.append(C.string_at(p,n*4));return n
ctype=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t);callback=ctype(audio)
r.lib.retro_set_audio_sample_batch.argtypes=[ctype];r.lib.retro_set_audio_sample_batch(callback)
r.write('dbg_bc_native_protect',b'\0\1');r.write('dbg_bc_native',b'\0\1')
if args.round==9:
    r.write('dbg_bc_native_audio_manual',b'\0\1');r.run(180)
    assert r.u16('dbg_bc_native_status')==4 and r.u32('dbg_bc_native_ticks')==0
    r.write('dbg_bc_native_audio_manual',b'\0\0')
out=ROOT/('.local/bc-music-round9' if args.round==9 else '.local/bc-music');out.mkdir(parents=True,exist_ok=True)
seen=0;window=0;results=[];max_wait=wait=0
for frame in range(10000):
    r.run(1)
    status=r.u16('dbg_bc_native_status');assert status in (0,4)
    assert not r.u16('dbg_bc_native_audio_ack') and not r.u16('dbg_bc_native_audio_manual')
    wait=wait+1 if status==4 else 0;max_wait=max(max_wait,wait)
    count=r.u16('dbg_bc_native_music_requests')
    if count!=seen:
        assert count==seen+1;seen=count;window=300;chunks.clear()
        command=r.u16('dbg_bc_native_music_command');assert command==(0x29 if args.round==9 else 0x21 if seen==1 else 0x32)
    elif window:
        window-=1
        if not window:
            data=b''.join(chunks);samples=np.frombuffer(data,dtype=np.int16).astype(float)
            rms=float(np.sqrt(np.mean((samples-samples.mean())**2)))
            assert rms>1,('silent output',seen,rms)
            name='stage' if seen==1 else 'boss';path=out/(name+'.wav')
            with wave.open(str(path),'wb') as w:
                w.setnchannels(2);w.setsampwidth(2);w.setframerate(round(av.timing.rate));w.writeframes(data)
            results.append(dict(request=seen,command=hex(command),rms=rms,path=str(path)))
            if seen==(1 if args.round==9 else 2):break
    else:chunks.clear()
assert seen==len(results)==(1 if args.round==9 else 2) and max_wait<10
r.write('dbg_bc_native',b'\0\0');r.run(120);assert r.u32('flow_state')==0
result=dict(round=args.round,loader_gate_checked=args.round==9,requests=results,max_wait_frames=max_wait,test_acknowledgements=0,returned_to_menu=True,
            original_cd_audio_verified=False)
(out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
