#!/usr/bin/env python3
"""Compare the clear-track wait/handoff to measured source task boundaries."""
import argparse
import csv
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path
from qa_bc_enemies import Data
from run_rom import ROOT

class Audio(C.Structure):
    _fields_=[('handler',C.c_uint16),('parameters',C.c_uint8*8),('state',C.c_uint8)]
class Exit(C.Structure):
    _fields_=[('remaining',C.c_uint16),('phase',C.c_uint8),('pause_disabled',C.c_uint8)]
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--capture',type=Path,default=ROOT/'.local/pce-reference/round-exit-natural');parser.add_argument('--final',action='store_true');args=parser.parse_args()
cap=args.capture
rows=list(csv.DictReader((cap/('final-exit.csv' if args.final else 'round-exit.csv')).open()))
def frame(pc):return int(next(r for r in rows if r['pc']==pc)['frame'])
start,ack,end=frame('a5ff' if args.final else '8db2'),frame('8ba8' if args.final else '8dbf'),frame('6042')
assert frame('8bb5' if args.final else '8dcc')-ack==420 and end-ack==421
code=(cap/'code-002160.bin').read_bytes();rom=(C.c_uint8*len(code)).from_buffer_copy(code);data=Data(rom,0x4000)
signature=bytes.fromhex('bdcc2df0273a9dcc2dd02c');assert code.count(signature)==1
shift=code.index(signature)-0x5204
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'exit.dylib'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                    str(ROOT/'src/bc_round_exit.c'),str(ROOT/'src/bc_audio.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_round_exit_begin.argtypes=[C.POINTER(Exit),C.POINTER(Audio),C.POINTER(Data),C.c_int16]
    lib.bc_round_exit_tick.argtypes=[C.POINTER(Exit),C.POINTER(Audio),C.c_uint8]
    lib.bc_round_exit_tick.restype=C.c_uint8
    lib.bc_audio_music_command.argtypes=[C.POINTER(Audio),C.c_int16];lib.bc_audio_music_command.restype=C.c_uint8
    lib.bc_round_exit_final_begin.argtypes=[C.POINTER(Exit),C.POINTER(Audio),C.POINTER(Data)]
    def begin(state,audio):
        if args.final:lib.bc_round_exit_final_begin(C.byref(state),C.byref(audio),C.byref(data))
        else:lib.bc_round_exit_begin(C.byref(state),C.byref(audio),C.byref(data),shift)
    state=Exit();audio=Audio();begin(state,audio)
    assert bytes(audio.parameters)==bytes.fromhex('4437384044441943' if args.final else '0809404008153343')
    assert lib.bc_audio_music_command(C.byref(audio),shift)==(0x2c if args.final else 0x2a)
    for f in range(start,end+1):
        if f==ack:audio.state=2
        ready=lib.bc_round_exit_tick(C.byref(state),C.byref(audio),0)
        assert ready==(f==end),(f,ready,end)
        assert bool(state.pause_disabled)==(args.final or f>=ack)
    assert not lib.bc_round_exit_tick(C.byref(state),C.byref(audio),0),'handoff must fire once'
    # Independently exercise the decoded pause branch; source capture above is unpaused.
    state=Exit();begin(state,audio);audio.state=2
    assert not lib.bc_round_exit_tick(C.byref(state),C.byref(audio),1)
    for _ in range(500):assert not lib.bc_round_exit_tick(C.byref(state),C.byref(audio),1)
    assert state.remaining==0 and state.phase==2
    assert lib.bc_round_exit_tick(C.byref(state),C.byref(audio),0)==1
print(json.dumps(dict(final_ending=args.final,source_request_frame=start,source_ack_frame=ack,source_handoff_frame=end,
                     delay_frames=end-ack,pause_gate_checked=True,next_round_loader_verified=False),indent=2))
