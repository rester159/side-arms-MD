#!/usr/bin/env python3
"""Check BC score/life formatting and unchanged-value caching at the text API."""
import ctypes as C
import subprocess
import tempfile
from pathlib import Path
from qa_bc_beam import ROOT
from qa_bc_score import Score
with tempfile.TemporaryDirectory() as directory:
    d=Path(directory);(d/'hud.c').write_text((ROOT/'src/bc_hud.c').read_text())
    (d/'hud.h').write_text('''
#include <string.h>
#define HUD_COLS 40
typedef unsigned char u8; typedef unsigned short u16; typedef signed short s16;
void hud_begin_fixed(u16);void hud_text(s16,s16,u8,const char*);
void hud_blank(s16,s16,u16);void hud_codes(s16,s16,u8,const u16*,u16);
void hud_number(s16,s16,u8,unsigned int,u16);void hud_frame(void);
''')
    (d/'stub.c').write_text('''
#include "hud.h"
char row[80]; unsigned int writes,frames;u16 fixed_rows;
void hud_begin_fixed(u16 n){fixed_rows=n;memset(row,' ',80);}
void hud_text(s16 x,s16 y,u8 c,const char *s){(void)c;x+=y*40;while(*s)row[x++]=*s++;writes++;}
void hud_blank(s16 x,s16 y,u16 n){x+=y*40;memset(row+x,' ',n);writes++;}
void hud_codes(s16 x,s16 y,u8 c,const u16 *s,u16 n){(void)c;x+=y*40;while(n--)row[x++]='0'+*s++;writes++;}
void hud_number(s16 x,s16 y,u8 c,unsigned int v,u16 n){(void)c;x+=y*40;memset(row+x,' ',n);do{row[x+--n]='0'+v%10;v/=10;}while(v&&n);writes++;}
void hud_frame(void){frames++;}
''')
    path=d/'hud.dylib';subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(d),'-I'+str(ROOT/'inc'),str(d/'hud.c'),str(d/'stub.c'),'-o',str(path)],check=True)
    lib=C.CDLL(str(path));lib.bc_hud_draw.argtypes=[C.POINTER(Score),C.c_uint8]
    row=(C.c_char*80).in_dll(lib,'row');writes=C.c_uint.in_dll(lib,'writes');lib.bc_hud_begin()
    assert C.c_uint16.in_dll(lib,'fixed_rows').value==1
    s=Score()
    for points,lives in ((0,3),(50,2),(12900,1),(99999999,0),(100,255),(0,127)):
        s.digits[:]=list(map(int,f'{points:08d}'));s.high[:]=list(map(int,'99999999'));before=bytes(s)
        lib.bc_hud_draw(C.byref(s),lives)
        assert bytes(row)[4:12].decode()==f'{points:8d}'
        assert bytes(row)[18:26]==b'99999999'
        assert bytes(row)[35:38].decode()==f'{0 if lives&128 else lives:3d}'
        count=writes.value;lib.bc_hud_draw(C.byref(s),lives);assert writes.value==count
        assert bytes(s)==before
    lib.bc_hud_party_draw.argtypes=[C.POINTER(C.POINTER(Score)),C.POINTER(C.c_uint8),C.c_uint8]
    scores=(C.POINTER(Score)*4)(*[C.pointer(s)]*4)
    reserves=(C.c_uint8*4)(0,6,127,255)
    for total in (0,1):
        lib.bc_hud_show_total_lives(total);lib.bc_hud_begin()
        for life in (0,6,127,255):
            lib.bc_hud_draw(C.byref(s),life)
            assert bytes(row)[35:38].decode()==f'{0 if life&128 else life+total:3d}'
        for players in (2,3,4):
            lib.bc_hud_party_begin(players);lib.bc_hud_party_draw(scores,reserves,players)
            assert C.c_uint16.in_dll(lib,'fixed_rows').value==(2 if players>2 else 1)
            for i in range(players):
                at=(i//2)*40+(i%2)*20+13
                expected='OUT' if reserves[i]&128 else f'{reserves[i]+total:3d}'
                assert bytes(row)[at:at+3].decode()==expected
            count=writes.value;lib.bc_hud_party_draw(scores,reserves,players);assert writes.value==count
print('PASS: scores, source reserves/Home total lives, 128-life display, underflow/OUT, 1-4P layout, caching and unchanged simulation')
