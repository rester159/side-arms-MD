"""Decode native actor records into the original 50-byte/16.8 QA format."""
from functools import lru_cache
from pathlib import Path
import re
from run_rom import ROOT

@lru_cache(maxsize=None)
def layout(rom):
    rom=Path(rom).resolve()
    header=rom.parent/'bc_rules.h'
    if not header.exists() and rom==(ROOT/'out/release/rom.bin').resolve():
        header=ROOT/'inc/bc_rules.h'
    text=header.read_text() if header.exists() else ''
    def shift(name):
        m=re.search(r'^#define '+name+r' (0|8)$',text,re.M)
        return int(m[1]) if m else 0
    return shift('BC_ENEMY_STORAGE_SHIFT'),shift('BC_ENEMY_VELOCITY_SHIFT')

def read_actor_pool(r,count=32,rom=ROOT/'out/release/rom.bin'):
    position_shift,velocity_shift=layout(str(Path(rom).resolve()))
    stride=54 if velocity_shift else 50
    raw=r.read('actors',stride*count)
    result=bytearray()
    for offset in range(0,len(raw),stride):
        actor=raw[offset:offset+stride]
        for at in (0,4):
            value=int.from_bytes(actor[at:at+4],'big')
            assert not value&((1<<position_shift)-1), 'actor position padding'
            result.extend((value>>position_shift).to_bytes(4,'big'))
        if velocity_shift:
            for at in (8,12):
                value=int.from_bytes(actor[at:at+4],'big',signed=True)
                assert value%256==0 and -8388608<=value<=8388352, 'actor velocity encoding'
                result.extend((value//256).to_bytes(2,'big',signed=True))
            result.extend(actor[16:])
        else:result.extend(actor[8:])
    assert len(result)==count*50
    return bytes(result)
