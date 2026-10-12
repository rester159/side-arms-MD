#!/usr/bin/env python3
"""Verify projectile submissions against per-shot art, expanding packed strips."""
import argparse
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_weapons import Weapons
from qa_bc_projectile_art import Sprite
from qa_bc_beam import ROOT, Beam

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--aligned',action='store_true')
parser.add_argument('--baseline',type=Path)
parser.add_argument('--dirty-padding',action='store_true')
args=parser.parse_args()
if args.aligned and not args.baseline:parser.error('--aligned requires an independent --baseline source archive')

with tempfile.TemporaryDirectory() as directory:
    d = Path(directory)
    (d/'draw.c').write_text((ROOT/'src/bc_projectile_draw.c').read_text())
    (d/'sprites.h').write_text('''
typedef signed short s16;
void spr_bc_key16(unsigned short, signed short, signed short, unsigned char);
void spr_bc_bits16(unsigned short, signed short, signed short, unsigned short);
void spr_bc_straight3(signed short, signed short, unsigned char, unsigned char);
''')
    (d/'game.h').write_text('unsigned short game_player_limit(void);\n')
    (d/'submit.c').write_text('''
#include "bc_projectile_art.h"
#include "gen/bc_player_projectile_keys.h"
#include <assert.h>
BcProjectileSprite submitted[30]; unsigned short count, packed, players;
unsigned short game_player_limit(void) { return players; }
void spr_16(unsigned short code, unsigned char colour, signed short x, signed short y, unsigned char flags) {
    BcProjectileSprite s = {code,x,y,colour,flags,1,1}; submitted[count++]=s;
}
void spr_bc_key16(unsigned short key, signed short x, signed short y, unsigned char flags) {
    spr_16(key & 0x7ff, key >> 11, x, y, flags);
}
void spr_bc_bits16(unsigned short key, signed short x, signed short y, unsigned short bits) {
    assert(!(bits & ~0x1800));
    spr_bc_key16(key, x, y, ((bits & 0x0800) ? 1 : 0) | ((bits & 0x1000) ? 2 : 0));
}
void spr_bc_straight3(signed short x, signed short y, unsigned char flags, unsigned char ascending) {
    packed++;
    for (unsigned char i=0; i<3; i++) spr_bc_key16(BC_PROJECTILE_1B8_KEY,x+8*(ascending?i:2-i),y,flags);
}
''')
    libpath=d/'draw.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
        *(['-DBC_TEST_ALIGNED_BEAMS'] if args.aligned else []),'-I'+str(ROOT/'inc'),'-I'+str(ROOT/'src'),str(d/'draw.c'),str(d/'submit.c'),
        str(ROOT/'src/bc_projectile_art.c'),'-o',str(libpath)],check=True)
    lib=C.CDLL(str(libpath))
    lib.bc_projectile_sprite.argtypes=[C.POINTER(Beam),C.c_int16,C.c_int16]
    lib.bc_projectile_sprite.restype=Sprite
    lib.bc_projectiles_draw.argtypes=[C.POINTER(Weapons),C.c_int16,C.c_int16]
    lib.bc_projectiles_draw.restype=C.c_uint8
    count=C.c_uint16.in_dll(lib,'count');packed=C.c_uint16.in_dll(lib,'packed')
    players=C.c_uint16.in_dll(lib,'players');submitted=(Sprite*30).in_dll(lib,'submitted')
    reference=None
    if args.baseline:
        (d/'reference.c').write_text((args.baseline/'src/bc_projectile_draw.c').read_text())
        reference_path=d/'reference.dylib'
        subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
            '-I'+str(args.baseline/'inc'),str(d/'reference.c'),str(d/'submit.c'),
            str(args.baseline/'src/bc_projectile_art.c'),'-o',str(reference_path)],check=True)
        reference=C.CDLL(str(reference_path))
        reference.bc_projectiles_draw.argtypes=lib.bc_projectiles_draw.argtypes
        reference.bc_projectiles_draw.restype=C.c_uint8
        reference_count=C.c_uint16.in_dll(reference,'count')
        reference_packed=C.c_uint16.in_dll(reference,'packed')
        reference_players=C.c_uint16.in_dll(reference,'players')
        reference_submitted=(Sprite*30).in_dll(reference,'submitted')
    rng=random.Random(0xbc30);total=0;strips=0
    for case in range(2400):
        w=Weapons();players.value=1+case%4
        for shot in w.shots:
            b=shot.body;b.state=rng.choice((0,0,64,128));b.sprite=rng.choice(tuple(range(0x1a8,0x1c8,2))+(0x1d4,0x1d6,0x1e0,0xffff))
            b.attributes=rng.randrange(65536);b.facing=rng.randrange(2)
            b.x=rng.randrange(0x100000000 if args.dirty_padding else 0x1000000);b.y=rng.randrange(0x100000000 if args.dirty_padding else 0x1000000)
        # Include end-of-pool triples and both overlap priority orders. Vary
        # one grouping condition to exercise fallback without changing art.
        start=case%28;x=rng.randrange(-128,300);y=rng.randrange(-128,300)
        direction=8 if case&1 else -8;attrs=rng.choice((0,0x800,0x8000,0x8800))
        for j in range(3):
            b=w.shots[start+j].body;b.state=128;b.sprite=0x1b8
            b.x=((x+j*direction)<<8)&0xffffff;b.y=(y<<8)&0xffffff;b.attributes=attrs
        variant=case%(8 if args.dirty_padding else 6)
        if variant==1:w.shots[start+1].body.state=0
        elif variant==2:w.shots[start+2].body.attributes^=0x800
        elif variant==3:w.shots[start+1].body.y+=256
        elif variant==4:w.shots[start+2].body.sprite=0x1ba
        if args.dirty_padding and variant==5:
            for j in range(3):w.shots[start+j].body.y |= 0xa5000000
        elif args.dirty_padding and variant==6:w.shots[start+1].body.y ^= 0x01000000
        elif args.dirty_padding and variant==7:
            for j in range(3):w.shots[start+j].body.x |= (j+1)<<24
        ox,oy=rng.randrange(-64,65),rng.randrange(-64,65)
        expected=[];missing=0;expected_packed=None
        if reference:
            reference_players.value=players.value
            reference_count.value=reference_packed.value=0
            original=bytes(w)
            missing=reference.bc_projectiles_draw(C.byref(w),ox,oy)
            assert bytes(w)==original
            expected=[Sprite.from_buffer_copy(bytes(reference_submitted[i])) for i in range(reference_count.value)]
            expected_packed=reference_packed.value
        else:
            for shot in w.shots:
                if not shot.body.state:continue
                value=lib.bc_projectile_sprite(C.byref(shot.body),ox,oy)
                if value.visible:expected.append(value)
                elif not value.handled:missing+=1
        if args.aligned:
            for shot in w.shots:
                for axis in ('x','y'):
                    value=getattr(shot.body,axis)
                    setattr(shot.body,axis,((value<<8)|(value>>24))&0xffffffff)
        before=bytes(w)
        count.value=packed.value=0
        assert lib.bc_projectiles_draw(C.byref(w),ox,oy)==missing,case
        assert bytes(w)==before and count.value==len(expected),case
        for i,s in enumerate(expected):
            assert all(getattr(submitted[i],n)==getattr(s,n) for n,_ in Sprite._fields_),(case,i)
        if expected_packed is not None:assert packed.value==expected_packed,(case,packed.value,expected_packed)
        assert players.value>1 or packed.value==0
        total+=count.value;strips+=packed.value
    assert strips>0
    print(f'PASS: 2400 projectile pools, {total} ordered sprites, {strips} packed strips; positions, flips, fallback, end slots and simulation bytes')
