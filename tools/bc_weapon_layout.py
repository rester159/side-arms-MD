"""Normalize native projectile storage without excluding any gameplay bytes."""
from functools import lru_cache
from pathlib import Path
import re
from run_rom import ROOT

@lru_cache(maxsize=None)
def _shift(rom, macro):
    rom=Path(rom).resolve()
    header=rom.parent/'bc_rules.h'
    if not header.exists() and rom==(ROOT/'out/release/rom.bin').resolve():
        header=ROOT/'inc/bc_rules.h'
    if not header.exists():
        raise ValueError(f'Missing matching projectile-layout header for {rom}')
    match=re.search(r'^#define '+macro+r' (\S+)',header.read_text(),re.M)
    if match and match[1] not in ('0','8'):
        raise ValueError(f'Unsupported {macro} layout {match[1]} in {header}')
    return int(match[1]) if match else 0

def beam_rotation(rom=ROOT/'out/release/rom.bin'):
    return _shift(str(Path(rom).resolve()),'BC_BEAM_STORAGE_ROTATE')

def beam_velocity_shift(rom=ROOT/'out/release/rom.bin'):
    return _shift(str(Path(rom).resolve()),'BC_BEAM_VELOCITY_SHIFT')

def player_layout(velocity_shift):
    assert velocity_shift in (0,8)
    extra=120 if velocity_shift else 0
    return dict(player_bytes=1024+extra,shot_bytes=36 if velocity_shift else 32,
                pointer_start=1000+extra,pointer_end=1008+extra)

def normalize_player(raw, rotation, velocity_shift=0):
    """Return original 1024 bytes, preserving coordinates, padding and pointers."""
    layout=player_layout(velocity_shift)
    assert len(raw)==layout['player_bytes'] and rotation in (0,8)
    stride=layout['shot_bytes']
    result=bytearray(raw[:8])
    for slot in range(30):
        shot=raw[8+slot*stride:8+(slot+1)*stride]
        for axis in (0,4):
            a,b,c,d=shot[axis:axis+4]
            result.extend((d,a,b,c) if rotation else (a,b,c,d))
        if velocity_shift:
            for axis in (8,12):
                v=int.from_bytes(shot[axis:axis+4],'big',signed=True)
                assert v%256==0 and -8388608<=v<=8388352, ('invalid projectile velocity',slot,axis,v)
                result.extend((v//256).to_bytes(2,'big',signed=True))
            result.extend(shot[16:])
        else:result.extend(shot[8:])
    result.extend(raw[8+30*stride:])
    assert len(result)==1024
    return bytes(result)
