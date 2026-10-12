#!/usr/bin/env python3
"""Compare the pilot's stationary-camera prediction with production C rules."""
import ctypes as C
from pathlib import Path
import random
import subprocess
import tempfile
from bc_pilot_terrain import solid, stationary_step, scrolling_step
ROOT=Path(__file__).resolve().parents[1]
class Motion(C.Structure):
    _fields_=[('x',C.c_uint16),('y',C.c_uint16),('dx',C.c_int8),('dy',C.c_int8)]
class Terrain(C.Structure):
    _fields_=[('cells',C.POINTER(C.c_ubyte)),('attributes',C.POINTER(C.c_ubyte))]
source=(ROOT/'src/bc_rules.c').read_text()
def function(name):
    start=source.index(name+'(');start=source.rfind('\n',0,start)+1
    return source[start:source.index('\n}',start)+2]
rng=random.Random(0xbc7e22)
cells=bytes(rng.randrange(256) for _ in range(16384))
attributes=bytes(rng.choice((0,0,0,0,1,2,8,15,128)) for _ in range(2048))
ca=(C.c_ubyte*len(cells)).from_buffer_copy(cells)
aa=(C.c_ubyte*len(attributes)).from_buffer_copy(attributes)
terrain=Terrain(ca,aa)
with tempfile.TemporaryDirectory() as td:
    path=Path(td);c=path/'rules.c';libpath=path/'rules.dylib'
    c.write_text('#include "bc_rules.h"\n'+'\n'.join(function(n) for n in ('bc_direction','bc_terrain_solid','bc_move_step')))
    subprocess.run(['cc','-std=c99','-O2','-shared','-fPIC','-I'+str(ROOT/'inc'),str(c),'-o',str(libpath)],check=True)
    lib=C.CDLL(str(libpath))
    lib.bc_terrain_solid.argtypes=[C.POINTER(Terrain),C.c_uint16,C.c_uint16];lib.bc_terrain_solid.restype=C.c_ubyte
    lib.bc_move_step.argtypes=[C.POINTER(Motion),C.c_ubyte,C.c_ubyte,C.c_uint16,C.c_uint16,C.c_uint16,C.c_uint16,C.POINTER(Terrain)]
    for i in range(20000):
        x,y=rng.randrange(65536),rng.randrange(65536)
        assert solid(cells,attributes,x,y)==lib.bc_terrain_solid(C.byref(terrain),x,y)
        px,py=rng.randrange(16,241),rng.randrange(32,201)
        dx,dy=rng.randrange(-1,2),rng.randrange(-1,2);up=rng.randrange(2)
        speed=(3 if dx and dy else 4) if up else (2 if dx and dy else 3)
        direction=(2 if dx>0 else 8 if dx<0 else 0)|(4 if dy>0 else 1 if dy<0 else 0)
        motion=Motion(px*256,py*256,0,0)
        crushed=lib.bc_move_step(C.byref(motion),direction,up,x,y,0,0,C.byref(terrain))
        expected=stationary_step(px,py,dx*speed,dy*speed,x,y,lambda wx,wy:solid(cells,attributes,wx,wy))
        assert not crushed and expected==(motion.x//256,motion.y//256),(i,expected,motion.x,motion.y)
        sx,sy=rng.choice((-512,-85,0,85,512)),rng.choice((-512,-85,0,85,512))
        fx,fy=px*256+rng.randrange(256),py*256+rng.randrange(256)
        motion=Motion(fx,fy,0,0)
        crushed=lib.bc_move_step(C.byref(motion),direction,up,x,y,sx,sy,C.byref(terrain))
        predicted=scrolling_step(fx,fy,dx*speed,dy*speed,x,y,sx,sy,lambda wx,wy:solid(cells,attributes,wx,wy))
        assert predicted==(motion.x,motion.y,bool(crushed)),(i,predicted,motion.x,motion.y,crushed)
print('PASS: 20000 terrain lookups, stationary steps and scrolling steps match production C, including fractional positions, wrap and crushes')
