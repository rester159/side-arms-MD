#!/usr/bin/env python3
"""Run the real score -> VInt queue -> Z80 -> YM2612 path in a test cartridge."""
import argparse
import shutil
import ctypes as C
import json
import hashlib
import wave
from pathlib import Path
import numpy as np
from run_rom import Runner,ROOT

out=ROOT/'.local/pce-hucard';out.mkdir(exist_ok=True)
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pal',action='store_true')
parser.add_argument('--track-seconds',type=float,default=None,
                    help='Measure each track for this duration (default: 600 video frames)')
args=parser.parse_args()
if args.track_seconds is not None and not 0 < args.track_seconds <= 3600:
    parser.error('--track-seconds must be between 0 and 3600')
rom=ROOT/'tests/sound_rom/out/release/rom.bin'
if args.pal:
    dest=out/'pal-output';dest.mkdir(exist_ok=True)
    raw=bytearray(rom.read_bytes());raw[0x1f0:0x200]=b'E'+b' '*15
    (dest/'rom.bin').write_bytes(raw)
    shutil.copy(rom.parent/'symbol.txt',dest/'symbol.txt')
    rom=dest/'rom.bin'
r=Runner(rom=rom)
class Timing(C.Structure):
    _fields_=[('geo',C.c_uint*4),('aspect',C.c_float),('fps',C.c_double),('rate',C.c_double)]
av=Timing();r.lib.retro_get_system_av_info(C.byref(av))
assert (av.fps<55)==args.pal
zram=(C.c_uint8*8192).in_dll(r.lib,'zram')
buf=[]
cb=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)(lambda p,n:buf.append(np.ctypeslib.as_array(p,(n*2,)).copy()) or n)
r.callbacks.append(cb);r.lib.retro_set_audio_sample_batch(cb)
r.run(120)
r.write('host_hucard',b'\x02')
r.run(5)
assert r.read('host_hucard_result',1)==b'\x01'
before=zram[0x1b0c]+256*zram[0x1b0d]
r.run(1800)
after=zram[0x1b0c]+256*zram[0x1b0d]
expected=1800/av.fps*7159090.909090909/(113*1024)
assert abs(((after-before)&65535)-expected)<2,('clock',after-before,expected)
assert zram[0x1b0a]==0,('underrun',zram[0x1b0a])
raw=np.concatenate(buf).reshape(-1,2)
assert np.sqrt(np.mean(raw[-44100:].astype(float)**2))>20,'Silent HuCard output'
audio=out/('native-song01-pal.wav' if args.pal else 'native-song01.wav')
with wave.open(str(audio),'wb') as wav:
    wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(round(av.rate));wav.writeframes(raw.astype('<i2').tobytes())
# Switch tracks while music is active; start must acknowledge its queue reset.
r.write('host_hucard',b'\x03');r.run(5)
assert r.read('host_hucard_result',1)==b'\x01'
r.run(600)
# Existing PSG SFX can run without ending HuCard music.
r.write('host_cmd',b'\x01');r.write('host_n',b'\x01');r.run(120)
assert r.read('hucard_active',1)==b'\x01'
# Stop through the existing public API, then switch back to arcade music.
r.write('host_cmd',b'\x00');r.write('host_n',b'\x01');r.run(120)
assert r.read('hucard_active',1)==b'\0'
assert np.max(np.abs(np.concatenate(buf[-30:]).astype(np.int32)))<4,'Stop left sound playing'
r.write('host_cmd',b'\x21');r.write('host_n',b'\x01');r.run(600)
assert np.sqrt(np.mean(np.concatenate(buf[-30:]).astype(float)**2))>20,'Arcade music did not resume'
tracks=[]
track_frames=max(1,round(args.track_seconds*av.fps)) if args.track_seconds else 600
for song in range(21):
    buf.clear()
    r.write('host_hucard',bytes([song+1]));r.run(5)
    assert r.read('host_hucard_result',1)==b'\x01'
    buf.clear()
    before=zram[0x1b0c]+256*zram[0x1b0d]
    power=0.;count=0;peak=0;remaining=track_frames
    while remaining:
        chunk=min(remaining,300)
        r.run(chunk);remaining-=chunk
        assert zram[0x1b0a]==0,('underrun',song,zram[0x1b0a])
        samples=np.concatenate(buf).astype(np.int32);buf.clear()
        power+=float(np.sum(samples.astype(float)**2));count+=samples.size
        peak=max(peak,int(np.max(np.abs(samples))))
    ticks=((zram[0x1b0c]+256*zram[0x1b0d])-before)&65535
    expected=track_frames/av.fps*7159090.909090909/(113*1024)
    # The counter wraps every ~17 minutes; compare modulo its width.
    error=((ticks-expected+32768)%65536)-32768
    assert abs(error)<2,('track clock',song,ticks,expected)
    rms=float(np.sqrt(power/count))
    assert peak<32767,('clipped output',song,peak)
    assert rms>5,('silent track',song,rms)
    tracks.append(dict(song=song,rms=round(rms,1),peak=peak,ticks=ticks,
                       clock_error=round(error,4),frames=track_frames))
    print('verified track %02x: %d frames, peak %d' % (song,track_frames,peak),flush=True)
r.write('host_cmd',b'\x00');r.write('host_n',b'\x01');r.run(30)
report=dict(passed=True,audio=str(audio),frames=r.frames,underruns=int(zram[0x1b0a]),
            rate=av.rate,pal=args.pal,tracks=tracks,
            rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
            core_sha256=hashlib.sha256(Path(r.lib._name).read_bytes()).hexdigest())
suffix=('-pal' if args.pal else '')+('-long' if args.track_seconds else '')
(out/('output'+suffix+'-qa.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
