#!/usr/bin/env python3
"""Check native soundtrack mapping against source callback bytes and script order."""
import ctypes as C
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
from inspect_hucard_music import ROOT,ROM_SHA
rom=(ROOT/'.local/pce-hucard/SideArms - Hyper Dyne (USA).pce').read_bytes()
assert hashlib.sha256(rom).hexdigest()==ROM_SHA
# Ten music callbacks in campaign order, used by the ordered event stream.
handlers=[0x92e5+4*i for i in range(10)]
stage_tracks=[];locations=[]
for handler in handlers:
    at=0x2000+handler-0x8000
    assert rom[at]==0xa9
    track=rom[at+1]
    if handler!=0x9309:
        assert rom[at+2]==0x80 and handler+4+rom[at+3]==0x930b
    stage_tracks.append(track)
    # Event stream is in banks 2/3 mapped at $A000-$DFFF. Search only its
    # campaign range; identical byte pairs in graphics are not references.
    refs=[i for i in range(0x51e3,0x7000) if rom[i:i+2]==handler.to_bytes(2,'little')]
    assert refs
    locations.append(refs[0])
assert locations==sorted(locations)
assert rom[0x330b:0x3317]==bytes.fromhex('a6 60 d0 03 20 60 e4 a9 04 85 6b 60')
expected=dict(zip(list(range(0x21,0x2a))+[0x36],stage_tracks))
# Source immediate music requests: opening, three regular boss forms, wheel,
# stage-clear, game-over and credits. Each calls the same sound queue.
for command,offset in [(0x20,0x1155),(0x32,0xb1ad),(0x33,0xb1bc),(0x34,0xb1cb),
                       (0x35,0xb81d),(0x2a,0xbe50),(0x2e,0xc94),(0x2c,0xdb7)]:
    assert rom[offset]==0xa9 and rom[offset+2:offset+5]==bytes.fromhex('20 60 e4')
    expected[command]=rom[offset+1]
expected[0xfe]=expected[0x2c] # BC gallery policy shares credits; its own timer stops it.
with tempfile.TemporaryDirectory() as d:
    libpath=Path(d)/'mapping.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),str(ROOT/'src/sound/hucard_music.c'),'-o',str(libpath)],check=True)
    lib=C.CDLL(str(libpath));lib.hucard_music_track.argtypes=[C.c_uint8];lib.hucard_music_track.restype=C.c_int8
    for command in range(256):assert lib.hucard_music_track(command)==expected.get(command,-1),(command,expected.get(command))
report=dict(passed=True,commands={f'{k:02x}':f'{v:02x}' for k,v in expected.items()},
            stage_script_references=[hex(i) for i in locations],source_sha256=ROM_SHA)
(ROOT/'.local/pce-hucard/music-mapping-qa.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
