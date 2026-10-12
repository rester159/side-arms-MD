#!/usr/bin/env python3
"""Verify BC boss art submission against captured composite states."""
import ctypes as C
import json
from pathlib import Path
import subprocess
import tempfile
from qa_bc_beam import ROOT
from qa_bc_factory import Actor,actor
first_geometry=json.loads((ROOT/'res/generated/bc_boss1_geometry.json').read_text())
geometry=json.loads((ROOT/'res/generated/bc_boss2_geometry.json').read_text())
program=(ROOT/'.local/pce-reference/play-task-round1/code-002160.bin').read_bytes()
class Draw(C.Structure):
    _fields_=[('tile',C.c_uint16),('pal',C.c_uint8),('x',C.c_int16),('y',C.c_int16),('flags',C.c_uint8)]
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory);(d/'gen').mkdir()
    (d/'gen/bc_boss_meta.h').write_text((ROOT/'src/gen/bc_boss_meta.h').read_text())
    (d/'draw.c').write_text((ROOT/'src/bc_boss_draw.c').read_text())
    (d/'bg.h').write_text('''
typedef unsigned char u8; typedef unsigned short u16; typedef signed short s16;
#define DMA_VRAM 0
u16 bg_reserve_blocks(u16,u16*); void bg_release_blocks(void);
void DMA_doDma(int,void*,u16,u16,u16);
void DMA_queueDma(int,void*,u16,u16,u16);
''')
    (d/'sprites.h').write_text('void spr_tile32_flags(unsigned short,unsigned char,signed short,signed short,unsigned char);\nvoid spr_tile32(unsigned short,unsigned char,signed short,signed short);\nvoid spr_16(unsigned short,unsigned char,signed short,signed short,unsigned char);')
    (d/'gen/assets.h').write_text('extern const unsigned char sprite_lut[272];')
    (d/'stub.c').write_text('''
#include "bg.h"
const u8 sprite_lut[272]={[270]=1}; const u8 bc_boss_patterns[3072]={0}; const u8 bc_boss2_patterns[5632]={0};
const u8 bc_boss3_patterns[3072]={0},bc_boss4_patterns[3072]={0},bc_boss5_patterns[3072]={0};
const u8 bc_boss6_patterns[3072]={0},bc_boss7_patterns[3072]={0},bc_boss8_patterns[3072]={0},bc_boss9_patterns[3072]={0};
const u8 bc_boss5_beam_patterns[2048]={0};
struct Draw {u16 tile;u8 pal;s16 x,y;u8 flags;} submitted[11];
u16 count,uploads,fail;
u16 bg_reserve_blocks(u16 n,u16 *t){for(u16 i=0;i<n;i++)t[i]=100+i*16;return n;}
void bg_release_blocks(void){}
void DMA_doDma(int target,void *src,u16 dest,u16 words,u16 step){
 u16 block=uploads<FIRST_BLOCKS?uploads:uploads-FIRST_BLOCKS;
 if(target || src!=(uploads<FIRST_BLOCKS?bc_boss_patterns:bc_boss2_patterns)+block*512 || dest!=(100+block*16)*32 || words!=256 || step!=2)fail=1;
 uploads++;
}
void spr_tile32(u16 tile,u8 pal,s16 x,s16 y){submitted[count++]=(struct Draw){tile,pal,x,y,0};}
void spr_tile32_flags(u16 tile,u8 pal,s16 x,s16 y,u8 flags){submitted[count++]=(struct Draw){tile,pal,x,y,flags};}
void DMA_queueDma(int target,void *src,u16 dest,u16 words,u16 step){(void)target;(void)src;(void)dest;(void)words;(void)step;fail=1;}
void spr_16(u16 code,u8 pal,s16 x,s16 y,u8 flags){(void)code;(void)pal;(void)x;(void)y;(void)flags;fail=1;}
''')
    path=d/'art.dylib'
    subprocess.run(['cc','-DFIRST_BLOCKS='+str(first_geometry['block_count']),'-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(d),'-I'+str(ROOT/'inc'),str(d/'draw.c'),str(d/'stub.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_boss_draw.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16];lib.bc_boss_draw.restype=C.c_uint8
    lib.bc_boss_art_init();assert C.c_uint16.in_dll(lib,'uploads').value==first_geometry['block_count'] and not C.c_uint16.in_dll(lib,'fail').value
    count=C.c_uint16.in_dll(lib,'count');submitted=(Draw*11).in_dll(lib,'submitted');states=visible=0
    for name in ('actor-step-hopper','boss-defeat-task'):
        raw=(ROOT/'.local/pce-reference'/name/'actor-step.bin').read_bytes()
        for off in range(0,len(raw),8198):
            ram=raw[off+6:off+8198]
            slot=raw[off+4]
            a=actor(ram,slot,program)
            if a.sprite_base_ref!=0x36b6 or not a.body.flags&8:continue
            before=bytes(a);count.value=0
            assert lib.bc_boss_draw(C.byref(a),32,0)
            shown=a.body.state and a.body.sprite not in (0,255,0xb4d6)
            pose=next((p for p in first_geometry['poses']if p['frame']==a.body.sprite),None)
            expected=first_geometry['pieces'][pose['first']:pose['first']+pose['count']] if shown else []
            assert count.value==len(expected)
            if shown:
                x=C.c_int16(a.body.x>>8).value+32;y=C.c_int16(a.body.y>>8).value
                for i,piece in enumerate(expected):
                    d=submitted[i]
                    assert (d.tile,d.pal,d.x,d.y,d.flags)==(100+16*piece['tile'],pose['palette'],x+piece['x'],y+piece['y'],piece['flags'])
                visible+=1
            assert bytes(a)==before;states+=1
    assert states and visible
    assert C.c_uint16.in_dll(lib,'uploads').value==first_geometry['block_count']
    lib.bc_boss_art_init_round(1)
    assert C.c_uint16.in_dll(lib,'uploads').value==first_geometry['block_count']+geometry['block_count'] and not C.c_uint16.in_dll(lib,'fail').value
    program=(ROOT/'.local/pce-reference/round02-reference/code-002160.bin').read_bytes()
    raw=(ROOT/'.local/pce-reference/round2-ending/actor-step.bin').read_bytes()
    round2_states=0
    for off in range(8198,len(raw),16396):
        slot=raw[off+4];a=actor(raw[off+6:off+8198],slot,program)
        if a.sprite_base_ref!=0x36c4 or not a.body.flags&8:continue
        before=bytes(a);count.value=0
        assert lib.bc_boss_draw(C.byref(a),32,0)
        shown=a.body.state and a.body.sprite not in (0,255,0xaf3d)
        pose=next((p for p in geometry['poses'] if p['frame']==a.body.sprite),None)
        expected=geometry['pieces'][pose['first']:pose['first']+pose['count']] if shown else []
        assert count.value==len(expected)
        if shown:
            x=C.c_int16(a.body.x>>8).value+32;y=C.c_int16(a.body.y>>8).value
            for i,piece in enumerate(expected):
                d=submitted[i]
                assert (d.tile,d.pal,d.x,d.y,d.flags)==(100+16*piece['tile'],pose['palette'],x+piece['x'],y+piece['y'],piece['flags'])
        assert bytes(a)==before;round2_states+=1
    assert round2_states and C.c_uint16.in_dll(lib,'uploads').value==first_geometry['block_count']+geometry['block_count']
print(json.dumps(dict(round_two_composites=round2_states,captured_composites=states,visible_composites=visible,initial_uploads=first_geometry['block_count'],runtime_uploads=0,simulation_unchanged=True),indent=2))
