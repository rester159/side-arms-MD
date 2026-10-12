#!/usr/bin/env python3
"""Check Genesis robot-art coverage over captured BC player states."""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import struct
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_enemies import Data
from qa_bc_player_flow import Control,state

class Art(C.Structure):
    _fields_=[('source',C.c_uint16*9),('genesis',C.c_uint16*9)]
class Sprite(C.Structure):
    _fields_=[('code',C.c_uint16),('x',C.c_int16),('y',C.c_int16),('colour',C.c_uint8),('visible',C.c_uint8),('handled',C.c_uint8)]

def verify(capture,code):
    program=code.read_bytes();rom=(C.c_uint8*len(program)).from_buffer_copy(program);data=Data(rom,0x4000)
    raw=(capture/'player-flow.bin').read_bytes();assert raw and len(raw)%8198==0
    source=(ROOT/'src/gen/player_data.c').read_text()
    death_text=re.search(r'DEATH_CODES\[8\] = \{([^}]+)',source).group(1)
    death=(C.c_uint16*8)(*(int(v.strip(),0) for v in death_text.split(',')))
    shift=program.index(bytes.fromhex('bdcc2df0273a9dcc2dd02c'))+0x4000-0x9204
    death_script=struct.unpack_from('<H',program,0x9ba7+shift-0x4000+30)[0]
    with tempfile.TemporaryDirectory() as directory:
        path=Path(directory)/'robot.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),str(ROOT/'src/bc_robot_art.c'),'-o',str(path)],check=True)
        lib=C.CDLL(str(path));lib.bc_robot_art_init.argtypes=[C.POINTER(Art),C.POINTER(Data),C.c_uint16,C.c_uint16,C.POINTER(C.c_uint16)]
        lib.bc_robot_sprite.argtypes=[C.POINTER(Art),C.POINTER(Control),C.c_uint8,C.c_int16,C.c_int16];lib.bc_robot_sprite.restype=Sprite
        art=Art();lib.bc_robot_art_init(C.byref(art),C.byref(data),0x9c07+shift,death_script,death)
        frames=set();visible=hidden=0
        for off in range(0,len(raw),8198):
            frame=struct.unpack_from('<I',raw,off)[0];p=state(raw[off+6:off+8198]);before=bytes(p)
            sprites=[lib.bc_robot_sprite(C.byref(art),C.byref(p),i,32,0) for i in range(4)]
            assert bytes(p)==before,(frame,'renderer changed simulation')
            assert all(s.handled for s in sprites),(frame,'unmapped body frame',hex(p.body_frame))
            assert all(s.visible==bool(p.world.state and p.body_frame) for s in sprites)
            if p.world.state and p.body_frame:
                frames.add(p.body_frame);visible+=1
                assert all(s.x==C.c_int16(p.world.x>>8).value+16 and s.y==C.c_int16(p.world.y>>8).value-16 for s in sprites)
                assert sprites[0].code==sprites[2].code and sprites[1].code==sprites[3].code
                if p.body_frame in art.source[:4]:assert [s.colour for s in sprites]==[0,4,3,7]
                else:assert all(s.colour==8 for s in sprites)
            else:hidden+=1
        return dict(module='Genesis artwork adapter, not rendered gameplay',visible_states=visible,hidden_states=hidden,
                    source_frames=[hex(v) for v in sorted(frames)],player_variants=4,simulation_unchanged=True,whole_game_verified=False)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--capture',type=Path,required=True);p.add_argument('--code',type=Path,required=True);a=p.parse_args()
    print(json.dumps(verify(a.capture,a.code),indent=2))
