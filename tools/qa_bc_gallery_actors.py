#!/usr/bin/env python3
"""Compare translated ending gallery actor tasks with source entry/exit RAM."""
import ctypes as C
import hashlib
import json
import struct
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_factory import Actor, actor, BYTE_FIELDS, WORD_FIELDS
from qa_bc_enemies import Data,Enemy
class Sprite(C.Structure):
    _fields_=[('code',C.c_uint16),('x',C.c_int16),('y',C.c_int16)]+[(n,C.c_uint8) for n in ('colour','flips','size','visible','handled')]
capture=ROOT/'.local/pce-reference/round10-gallery-actors-v2'
program=(ROOT/'.local/pce-reference/round10-ending-presentation/code-007080.bin').read_bytes()
assert hashlib.sha256(program).hexdigest()=='bbd7f05a8d836aa565e75cabf93a415fa30fc1f47eade5968ed82dfa7ea8788b'
raw=(capture/'gallery-actors.bin').read_bytes();stride=8198;assert raw and len(raw)%(stride*2)==0
rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'gallery.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_gallery','bc_actor_art')),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_gallery_actor_step.argtypes=[C.POINTER(Actor),C.POINTER(Data),C.c_int16,C.c_uint8,C.POINTER(C.c_uint8)]
    lib.bc_gallery_actor_step.restype=C.c_uint8
    lib.bc_actor_sprite.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16];lib.bc_actor_sprite.restype=Sprite
    counts={};entries=set();retired=0;art_states=0
    for off in range(0,len(raw),stride*2):
        frame,slot,phase=struct.unpack_from('<IBB',raw,off)
        end_frame,end_slot,end_phase=struct.unpack_from('<IBB',raw,off+stride)
        assert slot==end_slot and (phase,end_phase)==(0,1) and end_frame>=frame
        before=raw[off+6:off+stride];after=raw[off+stride+6:off+2*stride]
        a=actor(before,slot,program);expected=actor(after,slot,program)
        routine=a.routine if a.body.state==128 else a.death_routine
        count=C.c_uint8(before[0x59]);dx=int.from_bytes(before[0x40:0x42],'big',signed=True)
        # Source camera velocity is high byte $40, low byte $41.
        assert lib.bc_gallery_actor_step(C.byref(a),C.byref(data),dx,before[0x48],C.byref(count)),hex(routine)
        for name,_ in Enemy._fields_:
            assert getattr(a.body,name)==getattr(expected.body,name),(frame,slot,hex(routine),name,getattr(a.body,name),getattr(expected.body,name),dx)
        for name in (*WORD_FIELDS,*BYTE_FIELDS):
            assert getattr(a,name)==getattr(expected,name),(frame,slot,hex(routine),name,getattr(a,name),getattr(expected,name))
        assert count.value==after[0x59]
        sprite=lib.bc_actor_sprite(C.byref(a),32,0)
        assert sprite.handled,(frame,slot,'missing art',hex(a.sprite_base_ref),a.body.sprite-a.body.sprite_base)
        art_states+=sprite.visible
        counts[hex(routine)]=counts.get(hex(routine),0)+1;entries.add(before[0x73]);retired+=not a.body.state
    assert entries.issuperset(range(20)) and all(counts.get(x) for x in ('0x94ad','0xa9fa','0xaa4f'))
    lib.bc_gallery_spawn.argtypes=[C.POINTER(Actor),C.c_uint8,C.POINTER(Data),C.POINTER(C.c_uint16)]
    lib.bc_gallery_spawn.restype=C.c_uint8
    births=(ROOT/'.local/pce-reference/round10-gallery-birth/gallery-birth.bin').read_bytes()
    assert births and len(births)%(stride*2)==0
    born_entries=[];born_parts=0;reused_fractions=0
    for off in range(0,len(births),stride*2):
        frame=struct.unpack_from('<I',births,off)[0]
        before=births[off+6:off+stride];after=births[off+stride+6:off+2*stride]
        pool=(Actor*32)(*[actor(before,i,program) for i in range(32)])
        bases=(C.c_uint16*48)(*struct.unpack('>48H',before[0x1678:0x16d8]))
        entry=before[0x73]
        born=lib.bc_gallery_spawn(pool,entry,C.byref(data),bases)
        assert born==(3 if entry in (13,14) else 1),(frame,entry,born)
        for i,a in enumerate(pool):
            expected=actor(after,i,program)
            for name,_ in Enemy._fields_:
                assert getattr(a.body,name)==getattr(expected.body,name),(frame,entry,i,name,getattr(a.body,name),getattr(expected.body,name))
            for name in (*WORD_FIELDS,*BYTE_FIELDS):
                assert getattr(a,name)==getattr(expected,name),(frame,entry,i,name,getattr(a,name),getattr(expected,name))
            if not before[0xe08+i] and a.body.state:reused_fractions+=bool((a.body.x|a.body.y)&255)
        born_entries.append(entry);born_parts+=born
    assert born_entries==list(range(20)),born_entries
    pool=(Actor*32)();bases=(C.c_uint16*48)()
    before=bytes(pool)
    assert lib.bc_gallery_spawn(pool,20,C.byref(data),bases)==0 and bytes(pool)==before
    for a in pool:a.body.state=128
    before=bytes(pool)
    assert lib.bc_gallery_spawn(pool,13,C.byref(data),bases)==0 and bytes(pool)==before
    a=Actor();a.body.state=128;a.routine=0xffff;before=bytes(a);count=C.c_uint8(7)
    assert not lib.bc_gallery_actor_step(C.byref(a),C.byref(data),2048,0,C.byref(count))
    assert bytes(a)==before and count.value==7
    print(json.dumps(dict(updates=sum(counts.values()),tasks=counts,gallery_entries=sorted(entries),retirements=retired,
        own_art_states=art_states,birth_entries=len(born_entries),born_parts=born_parts,reused_fractions=reused_fractions,unknown_task_unchanged=True,renderer_integrated=False),indent=2))
