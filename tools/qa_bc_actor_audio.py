#!/usr/bin/env python3
"""Check actor audio event ordering, bounds and replacement-command coverage."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_actor_step import Event
class Queue(C.Structure):
    _fields_=[('sources',C.c_uint8*128),('count',C.c_uint16),('dropped',C.c_uint16)]
with tempfile.TemporaryDirectory() as d:
    path=Path(d)/'audio.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
                    str(ROOT/'src/bc_actor_audio.c'),str(ROOT/'src/bc_audio.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_audio_actor_append.argtypes=[C.POINTER(Queue),C.POINTER(Event)]
    lib.bc_audio_actor_command.argtypes=[C.c_uint8];lib.bc_audio_actor_command.restype=C.c_uint8
    mapping={0:0,2:0x17,3:0x0f,4:0x11,8:0x1c,12:0x12,13:0x14,22:0x1d}
    for source in range(256):assert lib.bc_audio_actor_command(source)==mapping.get(source,255)
    q=Queue();event=Event();event.setup_sound=13;event.extra_count=3
    for i,v in enumerate((4,0,8)):event.extra_events[i].sound=v
    # Entries outside extra_count must not be read.
    event.extra_events[3].sound=255;event.child_event.sound=12;event.actor_event.sound=3
    before=bytes(event)
    for _ in range(30):lib.bc_audio_actor_append(C.byref(q),C.byref(event))
    expected=[13,4,8,12,3]*30
    assert list(q.sources)==expected[:128] and q.count==128 and q.dropped==22
    assert bytes(event)==before
    q=Queue();event=Event();event.child_event.sound=8;event.actor_event.sound=4
    lib.bc_audio_actor_append(C.byref(q),C.byref(event))
    assert list(q.sources[:q.count])==[8,4], 'Dropped-item pickup must precede parent explosion'
    print('PASS: all 256 mappings; ordered setup/children/parent events; zero suppression; bounded overflow; unchanged events')
