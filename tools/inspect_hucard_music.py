#!/usr/bin/env python3
"""Inspect HuCard music metadata and exact driver-state recurrence captures."""
import argparse,hashlib,json,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ROM_SHA='06b8ac408d5f7942165bb06b5ce0795a6283022d034ca70dc256e17ed1af87cd'

def metadata(rom):
    assert hashlib.sha256(rom).hexdigest()==ROM_SHA,'Unexpected HuCard revision'
    def at(addr,n):return rom[0x10000+addr-0x4000:0x10000+addr-0x4000+n]
    def word(addr):return int.from_bytes(at(addr,2),'little')
    tracks=[];seen={}
    for command in range(at(0x4a00,1)[0]+1):
        address=word(0x4a03+command*2)
        if at(address,1)!=b'\0':continue
        row=dict(command=command,address=address,channels=[word(address+1+i*2) for i in range(6)])
        if address in seen:row['alias_of']=seen[address]
        else:seen[address]=command
        tracks.append(row)
    wave_base=word(0x4a01);wave_end=min(r['address'] for r in tracks)
    assert (wave_end-wave_base)%40==0
    instruments=[]
    for offset in range(wave_base,wave_end,40):
        raw=at(offset,40)
        instruments.append(dict(id=len(instruments)+1,address=offset,wave=list(raw[:32]),envelope_bytes=list(raw[32:])))
        assert max(raw[:32])<32
    return dict(schema=1,source_sha256=ROM_SHA,driver_tick_hz=7159090.909090909/(1024*113),music=tracks,instruments=instruments)

def inspect_capture(path):
    raw=(path/'sound-state.bin').read_bytes();stride=177
    assert raw and len(raw)%stride==0
    states=[];seen={};recurrence=None
    # Preserve timing fraction, fade, tempo and transpose. Scratch pointers and
    # the monotonically advancing high tempo-counter byte are not music state.
    globals_offsets=[a-0x99 for a in (0xa5,0xa6,0xa7,0xa9,0xaa,0xab,0xad)]
    for pos in range(0,len(raw),stride):
        tick,frame,time=struct.unpack_from('<IId',raw,pos)
        globals_=raw[pos+16:pos+39];channels=raw[pos+39:pos+177]
        states.append((tick,frame,time,globals_,channels))
        if frame<65:continue
        key=bytes(globals_[i] for i in globals_offsets)+channels
        if key in seen and recurrence is None:recurrence=(seen[key],len(states)-1)
        seen.setdefault(key,len(states)-1)
    result=dict(ticks=len(states),seconds=states[-1][2],music_silent=all(not int.from_bytes(states[-1][4][i*23:i*23+2],'little') for i in range(6)))
    if recurrence:
        a,b=recurrence;period=b-a;checked=0
        for j in range(b,len(states)):
            old=states[a+(j-b)%period];new=states[j]
            assert old[4]==new[4]
            assert all(old[3][i]==new[3][i] for i in globals_offsets)
            checked+=1
        result.update(loop_start_tick=states[a][0],loop_end_tick=states[b][0],loop_ticks=period,loop_seconds=states[b][2]-states[a][2],repeated_ticks_verified=checked)
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path);a=p.parse_args()
    if a.capture:print(json.dumps(inspect_capture(a.capture),indent=2))
    else:
        data=metadata((ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes())
        out=ROOT/'.local/pce-hucard/music-metadata.json';out.write_text(json.dumps(data,indent=2)+'\n')
        print(f'{len(data["music"])} music commands, {sum("alias_of" not in t for t in data["music"])} unique songs, {len(data["instruments"])} instruments; {out}')
if __name__=='__main__':main()
