#!/usr/bin/env python3
"""Compare checkpoint reset components with original reset/restore captures.
Loader presentation, life decrement and time between components are separate.
"""
import argparse
import ctypes as C
import json
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_enemies import Data
from qa_bc_factory import Actor,actor
from qa_bc_player_flow import Control,state
from qa_bc_stage import Stage,state as stage_state
from qa_bc_play import FrameCursor
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--capture',type=Path,required=True);p.add_argument('--code',type=Path,required=True);a=p.parse_args()
program=a.code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
header=(C.c_uint8*8).from_buffer_copy(program[0x6218:0x6220])
raw=(a.capture/'player-reset.bin').read_bytes();stride=8198;assert raw and len(raw)%(2*stride)==0
with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'reset.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),
        *(str(ROOT/f'src/{n}.c') for n in ('bc_rules','bc_world','bc_stage','bc_runtime','bc_player','bc_score','bc_palette','bc_audio')),
        '-o',str(path)],check=True)
    lib=C.CDLL(str(path));fn=lib.bc_runtime_checkpoint_reset
    fn.argtypes=[C.POINTER(FrameCursor),C.POINTER(Control),C.POINTER(Actor),C.POINTER(Stage),
                 C.POINTER(Data),C.c_uint8,C.c_uint16,C.POINTER(C.c_uint8),C.POINTER(C.c_uint8)]
    for off in range(0,len(raw),2*stride):
        before=raw[off+6:off+stride];after=raw[off+stride+6:off+2*stride]
        player=state(before);expected=state(after);stage=stage_state(before)
        pool=(Actor*32)(*(actor(before,i,program) for i in range(32)))
        cursor=FrameCursor(13,1);count=C.c_uint8(before[0x59])
        fn(C.byref(cursor),C.byref(player),pool,C.byref(stage),C.byref(data),before[0x4b],0x9ba7,header,C.byref(count))
        for field,_ in Control._fields_[1:]:assert getattr(player,field)==getattr(expected,field),field
        for field in ('x','y','state','invulnerability'):assert getattr(player.world,field)==getattr(expected.world,field),field
        assert bytes(player.world.inventory)==bytes(expected.world.inventory)
        assert bytes(player.world.weapons)==bytes(expected.world.weapons)
        for i in range(32):assert bytes(pool[i])==bytes(actor(after,i,program)),i
        assert count.value==after[0x59]==0 and stage.stopped==after[0x48]==0
        assert stage.x==before[0x67]<<16 and stage.y==before[0x68]<<16
        assert stage.script==int.from_bytes(before[0x69:0x6b],'little')
        assert stage.terrain_attributes==int.from_bytes(bytes(header[4:6]),'little')
        assert not cursor.stage_events and not cursor.scrolling and not player.world.shot_index
print(json.dumps(dict(resets=len(raw)//(2*stride),source_player_actor_reset_verified=True,
                      camera_uses_saved_checkpoint=True,complete_loader_verified=False),indent=2))
