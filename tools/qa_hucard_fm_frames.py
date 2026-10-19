#!/usr/bin/env python3
"""Check all 16-bit pitch inputs, repeated keys and region changes against math."""
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path
from qa_hucard_native_score import State
from run_rom import ROOT

with tempfile.TemporaryDirectory() as directory:
    libpath=Path(directory)/'fm.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-O2',
                    '-I'+str(ROOT/'inc'),str(ROOT/'src/sound/hucard_fm.c'),
                    str(ROOT/'src/gen/hucard_fm_data.c'),'-o',str(libpath)],check=True)
    lib=C.CDLL(str(libpath))
    lib.hucard_fm_frame.argtypes=[C.POINTER(State),C.c_uint8,C.POINTER(C.c_uint8)]
    patches=((C.c_uint8*8)*32).in_dll(lib,'hucard_fm_patches')
    algorithms=(C.c_uint8*32).in_dll(lib,'hucard_fm_algorithms')
    state=State();packet=(C.c_uint8*72)();alternate=(C.c_uint8*72)();frames=0
    pan_levels=[0,3,5,7,9,11,13,15,16,19,21,23,25,27,29,31]
    for period in range(65536):
        # Region switches exercise cache invalidation; repeats change the
        # non-pitch fields while every voice reuses its pitch key.
        for region,repeat in [(0,0),(0,1),(1,0),(1,1)]:
            expected=[]
            for ch,voice in enumerate(state.voice):
                voice.period=(period+ch*137)&65535
                voice.instrument=(period+ch+repeat)%33
                voice.volume=(period+ch*3+repeat)%32
                voice.pan=(period+ch*17+repeat)&255
                divisor=voice.period or 4096;block=0
                numerator=4444560 if region else 4404020
                fnum=(numerator+divisor//2)//divisor
                while fnum>2047 and block<7:
                    block+=1;divisor*=2;fnum=(numerator+divisor//2)//divisor
                fnum=min(fnum,2047)
                left,right=pan_levels[voice.pan>>4],pan_levels[voice.pan&15]
                patch=list(patches[(voice.instrument or 1)-1])
                algorithm=algorithms[(voice.instrument or 1)-1]
                attenuation=2*(62-voice.volume-max(left,right))
                assert algorithm & 7 in (5,6,7)
                levels=[min(127,max(0,v+(0 if algorithm & 7 in (5,6) and i==0 else attenuation-8)))
                        if voice.volume and voice.instrument else 127 for i,v in enumerate(patch[4:])]
                expected += [voice.instrument,block*8+(fnum>>8),fnum&255,
                             (128 if left else 0)|(64 if right else 0)|algorithm]+patch[:4]+levels
            lib.hucard_fm_frame(C.byref(state),region,packet)
            assert list(packet)==expected,(period,region,repeat)
            # An unchanged voice must still write every byte to a different
            # destination; cached outputs cannot depend on prior packet RAM.
            C.memset(alternate,0xa5,72)
            lib.hucard_fm_frame(C.byref(state),region,alternate)
            assert list(alternate)==expected,('repeated output',period,region,repeat)
            frames+=2
result=dict(passed=True,frames=frames,voices=frames*6,period_inputs=65536,regions=2,
            repeated_pitch_with_changed_envelope=True,unchanged_voice_to_poisoned_destination=True)
(ROOT/'.local/pce-hucard/fm-frame-qa.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
