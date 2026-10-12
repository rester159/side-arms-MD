#!/usr/bin/env python3
"""Verify the complete player-byte transformation independently of game hashes."""
import random,tempfile
from pathlib import Path
from bc_weapon_layout import normalize_player,beam_rotation,beam_velocity_shift
from bc_scene_state import validate_native_layout

def encode(source):
    result=bytearray(source)
    for slot in range(30):
        for axis in (0,4):
            at=8+slot*32+axis
            word=int.from_bytes(source[at:at+4],'big')
            result[at:at+4]=(((word<<8)|(word>>24))&0xffffffff).to_bytes(4,'big')
    return bytes(result)

validate_native_layout()
rng=random.Random(0xbc3208)
for _ in range(2000):
    source=bytes(rng.randrange(256) for _ in range(1024))
    encoded=encode(source)
    assert normalize_player(encoded,8)==source
    assert normalize_player(source,0)==source
for bit in range(8192):
    changed=bytearray(source);changed[bit//8]^=1<<(bit%8)
    assert normalize_player(encode(changed),8)==bytes(changed),bit
with tempfile.TemporaryDirectory() as temp:
    for name,value,expected in [('old','',0),('plain','#define BC_BEAM_STORAGE_ROTATE 0\n',0),('aligned','#define BC_BEAM_STORAGE_ROTATE 8\n',8)]:
        directory=Path(temp)/name;directory.mkdir()
        (directory/'bc_rules.h').write_text(value)
        assert beam_rotation(directory/'rom.bin')==expected
    bad=Path(temp)/'bad';bad.mkdir();(bad/'bc_rules.h').write_text('#define BC_BEAM_STORAGE_ROTATE 4\n')
    try:beam_rotation(bad/'rom.bin')
    except ValueError:pass
    else:raise AssertionError('Unsupported layout accepted')
print('PASS: 2000 full random player records and 8192 single-bit mutations; coordinates, padding, pointers and all other bytes preserved; old/new archived headers detected')


def encode_scaled(source,rotation):
    raw=encode(source) if rotation else source
    out=bytearray(raw[:8])
    for slot in range(30):
        shot=raw[8+slot*32:8+(slot+1)*32]
        out.extend(shot[:8])
        for at in (8,10):
            out.extend((int.from_bytes(shot[at:at+2],'big',signed=True)*256).to_bytes(4,'big',signed=True))
        out.extend(shot[12:])
    out.extend(raw[968:])
    return bytes(out)
for _ in range(4096):
    source=rng.randbytes(1024)
    for rotation in (0,8):
        assert normalize_player(encode_scaled(source,rotation),rotation,8)==source
for bit in range(8192):
    changed=bytearray(source);changed[bit//8]^=1<<(bit%8)
    assert normalize_player(encode_scaled(changed,8),8,8)==bytes(changed)
rejected=0
raw=encode_scaled(bytes(1024),8)
for slot in range(30):
    for at in (8,12):
        for value in (1,255,0x800000,0xff7fff00):
            damaged=bytearray(raw);offset=8+slot*36+at;damaged[offset:offset+4]=value.to_bytes(4,'big')
            try:normalize_player(damaged,8,8)
            except AssertionError:rejected+=1
            else:raise AssertionError('Invalid velocity accepted')
assert rejected==240
with tempfile.TemporaryDirectory() as temp:
    for name,text,want in [('old','',0),('wide','#define BC_BEAM_VELOCITY_SHIFT 8\n',8)]:
        directory=Path(temp)/name;directory.mkdir();(directory/'bc_rules.h').write_text(text)
        assert beam_velocity_shift(directory/'rom.bin')==want
    bad=Path(temp)/'bad';bad.mkdir();(bad/'bc_rules.h').write_text('#define BC_BEAM_VELOCITY_SHIFT 4\n')
    try:beam_velocity_shift(bad/'rom.bin')
    except ValueError:pass
    else:raise AssertionError('Unsupported velocity layout accepted')
print('PASS: widened velocities: 4096 random players in both position layouts, 8192 bit mutations, 240 invalid encodings rejected; all canonical bytes preserved')
