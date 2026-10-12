#!/usr/bin/env python3
"""Check the shipping C sequencer against all original HuCard music captures.
Exercises relocated compiled data, six channel records, tempo, envelope and
modulation, including finite endings. This does not test YM synthesis yet.
"""
import csv
import ctypes as C
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from build_hucard_score import ROOT, compile_score, emit

class Voice(C.Structure):
    _fields_ = [('period',C.c_uint16), ('volume',C.c_uint8), ('pan',C.c_uint8), ('instrument',C.c_uint8)]
class State(C.Structure):
    _fields_ = [('voice', Voice * 6), ('channel', (C.c_uint8 * 24) * 6), ('phase', C.c_uint16),
                ('tempo', C.c_uint16), ('clock', C.c_uint8),
                ('transpose', C.c_uint8), ('instrument', C.c_uint8)]
class Data(C.Structure):
    _fields_ = [(name, C.c_void_p) for name in ('score', 'songs', 'envelopes', 'periods')]

def main():
    rom = (ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes()
    compiled = compile_score(rom)
    offsets = {int(k): v for k, v in compiled['offsets'].items()}
    results = []
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)
        emit(compiled, path)
        library = path/'hucard.dylib'
        subprocess.run(['cc', '-std=c99', '-Wall', '-Wextra', '-Werror', '-O2', '-shared', '-fPIC',
                        '-I'+str(ROOT/'inc'), str(ROOT/'src/sound/hucard_score.c'),
                        str(path/'hucard_data.c'), '-o', str(library)], check=True)
        lib = C.CDLL(str(library))
        data = Data.in_dll(lib, 'hucard_score_data')
        lib.hucard_score_tick.argtypes = [C.POINTER(State), C.POINTER(Data)]
        lib.hucard_score_start.argtypes = [C.POINTER(State), C.POINTER(Data), C.c_uint8]
        lib.hucard_score_stop.argtypes = [C.POINTER(State)]
        for command in range(21):
            if command in (8, 19, 20): continue
            raw = (ROOT/f'.local/pce-hucard/music-{command:02x}-reference-v1/sound-state.bin').read_bytes()
            assert raw and len(raw) % 177 == 0
            rows = [raw[i:i+177] for i in range(0,len(raw),177)]
            start = next(i for i,r in enumerate(rows) if struct.unpack_from('<I',r,4)[0]>=62)
            state = State()
            lib.hucard_score_start(C.byref(state), C.byref(data), command)
            # PSG register latches reconstructed independently from actual
            # original chip writes, compared at completed sound interrupts.
            writes = iter(csv.DictReader((ROOT/f'.local/pce-hucard/music-{command:02x}-reference-v1/psg.csv').open()))
            pending = next(writes, None)
            registers = [[0]*10 for _ in range(6)]
            selected = 0
            for i,r in enumerate(rows[start:],start):
                lib.hucard_score_tick(C.byref(state), C.byref(data))
                time = struct.unpack_from('<d',r,8)[0]
                while pending and float(pending['time']) <= time:
                    register, value = int(pending['reg'],16), int(pending['value'],16)
                    if register == 0: selected = value & 7
                    elif selected < 6: registers[selected][register] = value
                    pending = next(writes, None)
                g = r[16:39]
                assert (state.phase,state.clock,state.tempo,state.transpose) == (g[15]*256+g[16],g[19],g[17]*256+g[18],g[20]), ('global',command,i)
                for ch in range(6):
                    expected = list(r[39+ch*23:39+(ch+1)*23]); target = offsets[expected[0]+256*expected[1]]
                    expected[:2] = [target>>8,target&255]
                    expected[20:22] = expected[20:22][::-1]
                    assert state.channel[ch][23] == 0, ('channel padding', command, i, ch)
                    actual = list(state.channel[ch])[:23]
                    expected[5] &= 0xef; actual[5] &= 0xef
                    assert actual == expected, ('channel',command,i,ch,actual,expected)
                    voice = state.voice[ch]; chip = registers[ch]
                    volume = (chip[4] & 31) if chip[4] & 128 else 0
                    assert voice.volume == volume, ('volume',command,i,ch,voice.volume,volume)
                    assert voice.pan == chip[5], ('pan',command,i,ch,voice.pan,chip[5])
                    if volume:
                        period = chip[2] + ((chip[3]&15)<<8)
                        assert voice.period == period, ('period',command,i,ch,voice.period,period)
            lib.hucard_score_stop(C.byref(state))
            assert not any(bytes(state.channel)) and state.tempo == 0
            for _ in range(16): lib.hucard_score_tick(C.byref(state), C.byref(data))
            assert not any(bytes(state.channel))
            results.append(dict(command=command, ticks=len(rows)-start))
        # Aliases must start with identical data and remain identical.
        for alias in (8,19,20):
            a,b = State(),State()
            lib.hucard_score_start(C.byref(a),C.byref(data),alias)
            lib.hucard_score_start(C.byref(b),C.byref(data),4)
            for _ in range(10000):
                lib.hucard_score_tick(C.byref(a),C.byref(data))
                lib.hucard_score_tick(C.byref(b),C.byref(data))
                assert bytes(a) == bytes(b)
    report = dict(passed=True, tracks=results, source_ticks=sum(r['ticks'] for r in results),
                  compiled_score_bytes=len(compiled['score']), aliases=3, audible_pitch_volume_pan_verified=True, synthesis_verified=False)
    (ROOT/'.local/pce-hucard/native-score-qa.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__ == '__main__': main()
