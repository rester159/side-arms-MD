#!/usr/bin/env python3
"""Compare all gallery scheduler frames and actors with recorded source RAM."""
import ctypes as C
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_factory import Actor,actor,BYTE_FIELDS,WORD_FIELDS
from qa_bc_enemies import Data,Enemy
class Gallery(C.Structure):
    _fields_=[('remaining',C.c_uint16),('camera_x',C.c_uint16)]+[(n,C.c_uint8) for n in ('entry','phase','spawn')]
p=ROOT/'.local/pce-reference'
program=(p/'round10-ending-presentation/code-007080.bin').read_bytes()
assert hashlib.sha256(program).hexdigest()=='bbd7f05a8d836aa565e75cabf93a415fa30fc1f47eade5968ed82dfa7ea8788b'
raw=(p/'round10-ending-complete/state.bin').read_bytes()
frames={struct.unpack_from('<I',raw,o)[0]:raw[o+4:o+8196] for o in range(0,len(raw),8196)}
rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
bases=(C.c_uint16*48)(*struct.unpack('>48H',frames[7292][0x1678:0x16d8]))
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'sequence.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_gallery','gen/bc_ending_data')),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_gallery_begin.argtypes=[C.POINTER(Gallery),C.POINTER(Actor)]
    data=Data.in_dll(lib,'bc_gallery_data')
    packed_bases=(C.c_uint16*48).in_dll(lib,'bc_gallery_bases')
    assert list(packed_bases)==list(bases)
    bases=packed_bases
    lib.bc_gallery_tick.argtypes=[C.POINTER(Gallery),C.POINTER(Actor),C.POINTER(Data),C.POINTER(C.c_uint16),C.POINTER(C.c_uint8)]
    lib.bc_gallery_tick.restype=C.c_uint8
    pool=(Actor*32)();g=Gallery();lib.bc_gallery_begin(C.byref(g),pool);count=C.c_uint8(frames[7292][0x59])
    transitions=[];visible=0
    for f in range(7293,13105):
        result=lib.bc_gallery_tick(C.byref(g),pool,C.byref(data),bases,C.byref(count))
        assert result in (1,2,3),(f,result)
        r=frames[f]
        assert g.entry==r[0x73] and g.camera_x==int.from_bytes(r[0x2e:0x30],'big'),(f,'scheduler',g.entry,g.camera_x,r[0x73],r[0x2e:0x30].hex())
        for i,a in enumerate(pool):
            want=actor(r,i,program)
            for name,_ in Enemy._fields_:
                assert getattr(a.body,name)==getattr(want.body,name),(f,i,name,getattr(a.body,name),getattr(want.body,name))
            for name in (*WORD_FIELDS,*BYTE_FIELDS):
                assert getattr(a,name)==getattr(want,name),(f,i,name,getattr(a,name),getattr(want,name))
            visible+=bool(a.body.state)
        assert count.value==r[0x59]
        if result==2:transitions.append(f)
    assert g.phase==4 and result==3 and len(transitions)==20 and not any(a.body.state for a in pool)
    before=bytes(g),bytes(pool),count.value
    for _ in range(60):assert lib.bc_gallery_tick(C.byref(g),pool,C.byref(data),bases,C.byref(count))==4
    assert before==(bytes(g),bytes(pool),count.value)
    print(json.dumps(dict(frames=13105-7293,actor_slots=(13105-7293)*32,active_states=visible,
        transitions=transitions,final_camera=g.camera_x,final_scroll_complete=True,
        generated_resource_verified=True,renderer_integrated=False),indent=2))
