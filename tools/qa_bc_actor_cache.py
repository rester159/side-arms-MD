#!/usr/bin/env python3
"""Compare cached actor drawing with fresh art selection across slot reuse."""
import json
import ctypes as C
import random
import subprocess
import tempfile
from pathlib import Path
from qa_bc_factory import Actor
from qa_bc_beam import ROOT

class Sprite(C.Structure):
    _fields_ = [('code', C.c_uint16), ('x', C.c_int16), ('y', C.c_int16)] + [
        (n, C.c_uint8) for n in ('colour', 'flips', 'size', 'visible', 'handled')]

with tempfile.TemporaryDirectory() as directory:
    d = Path(directory)
    # Replace only the hardware submission boundary; compile actual cache code.
    (d/'draw.c').write_text((ROOT/'src/bc_actor_draw.c').read_text())
    (d/'sprites.h').write_text('''
unsigned short spr_mark(void);
void spr_scene_palettes(unsigned short);
void spr_bc_key16(unsigned short, signed short, signed short, unsigned char);
void spr_bc_bits16(unsigned short, signed short, signed short, unsigned short);
void spr_bc_bits32(void *, unsigned short, signed short, signed short, unsigned short);
void spr_bc_surfacer32(signed short, signed short, unsigned short);
void spr_bc_pod32(signed short, signed short, unsigned short);
void spr_bc_spike32(void *, signed short, signed short, unsigned short);
void spr_bc_key32(unsigned short, signed short, signed short, unsigned char);
void *spr_bc_bucket(unsigned short, unsigned char);
void spr_bc_hint32(void *, unsigned short, signed short, signed short, unsigned char);
void spr_16(unsigned short, unsigned char, signed short, signed short, unsigned char);
void spr_32(unsigned short, unsigned char, signed short, signed short, unsigned char);
''')
    (d/'submit.c').write_text('''
#include "bc_actor_art.h"
#include <assert.h>
#include <stdint.h>
BcActorSprite submitted[32]; unsigned short count; unsigned char boss_handled;
unsigned char bc_boss_draw(const BcActor *a, signed short x, signed short y) { (void)a; (void)x; (void)y; return boss_handled; }
void spr_16(unsigned short code, unsigned char colour, signed short x, signed short y, unsigned char flags) {
    BcActorSprite s = {code,x,y,colour,flags,16,1,1}; submitted[count++]=s;
}
void spr_32(unsigned short code, unsigned char colour, signed short x, signed short y, unsigned char flags) {
    spr_16(code,colour,x,y,flags); submitted[count-1].size=32;
}
unsigned short spr_mark(void) { return count; }
void spr_scene_palettes(unsigned short first) { (void)first; }
void spr_bc_key16(unsigned short key, signed short x, signed short y, unsigned char flags) {
    spr_16(key&0x7ff,key>>11,x,y,flags);
}
void spr_bc_key32(unsigned short key, signed short x, signed short y, unsigned char flags) {
    spr_32(key&0x7ff,key>>11,x,y,flags);
}
void *spr_bc_bucket(unsigned short key, unsigned char size) {
    return (void *)(((uintptr_t)key << 1) + (size == 32) + 1);
}
void spr_bc_hint32(void *bucket, unsigned short key, signed short x, signed short y, unsigned char flags) {
    assert(bucket == spr_bc_bucket(key, 32)); spr_bc_key32(key,x,y,flags);
}
void spr_bc_bits16(unsigned short key, signed short x, signed short y, unsigned short bits) {
    assert(!(bits & ~0x1800)); spr_bc_key16(key,x,y,bits>>11);
}
void spr_bc_bits32(void *bucket, unsigned short key, signed short x, signed short y, unsigned short bits) {
    assert(!(bits & ~0x1800)); spr_bc_hint32(bucket,key,x,y,bits>>11);
}
/* Test the logical pose submitted by the cache; the native renderer checks
 * prove each specialized entry point's hardware cropping separately. */
void spr_bc_surfacer32(signed short x, signed short y, unsigned short bits) {
    spr_bc_bits32(spr_bc_bucket(0x250,32),0x250,x,y,bits);
}
void spr_bc_pod32(signed short x, signed short y, unsigned short bits) {
    spr_bc_bits32(spr_bc_bucket(0x7ed6,32),0x7ed6,x,y,bits);
}
void spr_bc_spike32(void *bucket, signed short x, signed short y, unsigned short bits) {
    spr_bc_bits32(bucket,0x7d30,x,y,bits);
}
''')
    libpath=d/'cache.dylib'
    subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',
                    '-I'+str(ROOT/'inc'),str(d/'draw.c'),str(d/'submit.c'),
                    str(ROOT/'src/bc_actor_art.c'),'-o',str(libpath)],check=True)
    lib=C.CDLL(str(libpath))
    lib.bc_actor_sprite.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16]
    lib.bc_actor_sprite.restype=Sprite
    lib.bc_actors_draw.argtypes=[C.POINTER(Actor),C.c_int16,C.c_int16]
    lib.bc_actors_draw.restype=C.c_uint16
    lib.bc_actor_boss_sprite.argtypes=lib.bc_actor_sprite.argtypes
    lib.bc_actor_boss_sprite.restype=Sprite
    actors=(Actor*32)(); count=C.c_uint16.in_dll(lib,'count')
    submitted=(Sprite*32).in_dll(lib,'submitted')
    # A zero cache key denotes a hidden sprite0, not an uninitialized visible
    # pose. Cover first use before any cache entry has been populated.
    for flags in (0,8):
        for actor in actors:actor.body.state=128;actor.body.flags=flags
        before=bytes(actors);count.value=0
        assert lib.bc_actors_draw(actors,0,0)==32<<8
        assert count.value==0 and bytes(actors)==before
    actors=(Actor*32)()
    rng=random.Random(0xBC)
    refs=[0x367a,0x367c,0x367e,0x3682,0x3684,0x3686,0x3688,
          0x36d0,0x36d2,0x36d4,0x368c,0x368e,0x3692,0x3698,0x36c8,0x36b6,0xffff]
    rendered=0
    for frame in range(1200):
        # Mutate keys individually, interspersed with coordinate-only cache hits.
        for a in actors:
            b=a.body
            b.x=rng.randrange(0x1000000); b.y=rng.randrange(0x1000000)
            field=frame%8
            if field==0: b.state=rng.choice([0,1,128,255])
            elif field==1: b.sprite_base=rng.randrange(0x180,0x360)
            elif field==2: b.sprite=b.sprite_base+rng.randrange(0,66,2)
            elif field==3: a.sprite_base_ref=rng.choice(refs)
            elif field==4: b.attributes=rng.randrange(65536)
            elif field==5: b.flags=rng.choice([0,8,16,128])
            elif field==6: b.sprite=rng.choice([0,255,b.sprite_base,b.sprite_base+8])
        ox,oy=rng.randrange(-128,129),rng.randrange(-128,129)
        expected=[];missing=0;before=bytes(actors)
        for a in actors:
            if not a.body.state: continue
            root=actors[0]
            boss_mode=(root.body.state and root.body.flags&8 and root.sprite_base_ref in range(0x36b6,0x36c7,2)) or any(z.body.state and z.sprite_base_ref in (0x36d0,0x36d2,0x36d4) for z in actors[:8])
            mapper=lib.bc_actor_boss_sprite if boss_mode else lib.bc_actor_sprite
            s=mapper(C.byref(a),ox,oy)
            missing+=not s.handled
            if s.visible: expected.append(s)
        count.value=0
        assert lib.bc_actors_draw(actors,ox,oy)==missing + (sum(bool(a.body.state) for a in actors) << 8),frame
        assert bytes(actors)==before,frame
        assert count.value==len(expected),frame
        for i,s in enumerate(expected):
            assert all(getattr(submitted[i],n)==getattr(s,n) for n,_ in Sprite._fields_), (frame,i)
        rendered+=count.value
    # Synchronized formations stress cross-slot reuse, including hidden poses,
    # composite rejection, mirrored artwork, palette changes and slot rebirth.
    synchronized = 0
    for frame in range(256):
        for i,a in enumerate(actors):
            b=a.body
            b.state=0 if frame%13==0 and i%3==0 else 128
            b.sprite_base=0x200+(16 if frame%7==0 and i%2 else 0)
            b.sprite=(0 if frame%17==0 else 255 if frame%19==0 else
                      b.sprite_base+2*(frame%5))
            a.sprite_base_ref=(0x369e,0x36a0,0x36a2,0x36a4,0x36a6,0x36a8)[frame%6]
            b.attributes=(frame*0x813)&65535
            b.flags=8 if frame%23==0 else 0
            b.x=((i*17-frame)&65535)<<8; b.y=((frame+i*7)&65535)<<8
        expected=[];missing=0;before=bytes(actors)
        for a in actors:
            if not a.body.state: continue
            s=lib.bc_actor_sprite(C.byref(a),-8,12)
            missing+=not s.handled
            if s.visible: expected.append(s)
        count.value=0
        assert lib.bc_actors_draw(actors,-8,12)==missing+(sum(bool(a.body.state) for a in actors)<<8),frame
        assert bytes(actors)==before and count.value==len(expected),frame
        for i,s in enumerate(expected):
            assert all(getattr(submitted[i],n)==getattr(s,n) for n,_ in Sprite._fields_),(frame,i)
        synchronized+=count.value
    # Coordinate-origin arithmetic must preserve signed-word wrapping at both
    # limits, including an origin whose extent subtraction itself wraps.
    boundary_submissions = 0
    edges = [-32768, -32767, -16, -8, -1, 0, 7, 8, 15, 16, 32760, 32767]
    for ox in edges:
        for oy in edges:
            for i,a in enumerate(actors):
                b=a.body
                b.state=128; b.flags=0; b.sprite_base=0x200
                b.sprite=0x200; a.sprite_base_ref=0x367c if i%2 else 0x369e
                b.attributes=0x1181
                b.x=(edges[i%len(edges)]&65535)<<8
                b.y=(edges[(i+3)%len(edges)]&65535)<<8
            expected=[lib.bc_actor_sprite(C.byref(a),ox,oy) for a in actors]
            before=bytes(actors);count.value=0
            assert lib.bc_actors_draw(actors,ox,oy)==32<<8
            assert bytes(actors)==before and count.value==32
            for i,s in enumerate(expected):
                assert all(getattr(submitted[i],n)==getattr(s,n) for n,_ in Sprite._fields_),(ox,oy,i)
            boundary_submissions+=count.value
    print(f'PASS: signed-word origin boundaries, {boundary_submissions} submissions')
    # Composite bosses can bypass ordinary art resolution, but still count.
    C.c_uint8.in_dll(lib,'boss_handled').value=1
    for a in actors:
        a.body.state=128; a.body.flags|=8
    before=bytes(actors); count.value=0
    assert lib.bc_actors_draw(actors,0,0)==32<<8
    assert count.value==0 and bytes(actors)==before
    for a in actors: a.body.state=0
    assert lib.bc_actors_draw(actors,0,0)==0 and count.value==0
    # Unchanged shot keys must switch at boss entry/defeat, slot reuse and
    # checkpoint resets. Compare against fresh selection and generated keys.
    shared=[r for r in json.loads((ROOT/'res/generated/bc_boss_shots.json').read_text()) if r['boss_context_only']]
    transitions=0
    for rec in shared:
        actors=(Actor*32)(); shot=actors[3];b=shot.body
        b.state=128;b.sprite_base=0x400;b.sprite=0x400+rec['frame']
        b.attributes=0x80|rec['source_palette'];b.x=128<<8;b.y=112<<8
        shot.sprite_base_ref=rec['family']
        for family,state,flags in [(0,0,0),(0x36b6,128,8),(0x36b6,255,8),
                                    (0x36b6,0,8),(0,0,0),(0x36c2,128,8),
                                    (0x36c6,128,8),(0x36c6,0,8),(0x367c,128,8),
                                    (0x36c6,128,0),(0,0,0)]:
            root=actors[0];root.sprite_base_ref=family;root.body.state=state;root.body.flags=flags
            boss_mode=bool(state and flags&8 and family in range(0x36b6,0x36c7,2))
            mapper=lib.bc_actor_boss_sprite if boss_mode else lib.bc_actor_sprite
            expected=mapper(C.byref(shot),0,0);before=bytes(actors);count.value=0
            lib.bc_actors_draw(actors,0,0)
            assert bytes(actors)==before and count.value==1
            assert all(getattr(submitted[0],n)==getattr(expected,n) for n,_ in Sprite._fields_)
            if boss_mode:assert expected.code|(expected.colour<<11)==rec['key']
            transitions+=1
    # Final heads promote to successive slots; the shared orb must stay PCE.
    orb=next(r for r in shared if r['family']==0x3698)
    actors=(Actor*32)();shot=actors[12];shot.sprite_base_ref=0x3698
    shot.body.state=128;shot.body.sprite_base=shot.body.sprite=0x400;shot.body.attributes=0x82
    for slot in range(8):
        for a in actors[:8]:a.body.state=0
        actors[slot].body.state=128;actors[slot].sprite_base_ref=0x36d0
        count.value=0;lib.bc_actors_draw(actors,0,0)
        assert count.value==1 and submitted[0].code|(submitted[0].colour<<11)==orb['key']
    for a in actors[:8]:a.body.state=0
    count.value=0;lib.bc_actors_draw(actors,0,0)
    normal=lib.bc_actor_sprite(C.byref(shot),0,0)
    assert submitted[0].code==normal.code and submitted[0].colour==normal.colour
    print(f'PASS: final-serpent eight-slot promotion and exit')
    # Resetting a pose key must also reset its visible/missing result. An
    # matching empty frame must hide the preceding visible actor; unknown
    # families and nonempty frames must still refresh normally.
    reset_cases=0
    for entering in (False,True):
        for sprite in (0,255,0x400,0xffff):
            for attrs in (0,0x82,0xffff):
                for base in (0x100,0x400):
                    for family in (0x3698,0xffff):
                        actors=(Actor*32)();root=actors[0];root.sprite_base_ref=0x36b6
                        root.body.flags=8;root.body.state=0 if entering else 128
                        shot=actors[3];shot.body.state=128;shot.sprite_base_ref=0x3698
                        shot.body.sprite_base=base;shot.body.sprite=base;shot.body.attributes=0x82
                        count.value=0;lib.bc_actors_draw(actors,0,0)
                        assert count.value==1
                        root.body.state=128 if entering else 0
                        shot.sprite_base_ref=family;shot.body.sprite=sprite;shot.body.attributes=attrs
                        expected=lib.bc_actor_boss_sprite(C.byref(shot),0,0) if entering else lib.bc_actor_sprite(C.byref(shot),0,0)
                        count.value=0;before=bytes(actors)
                        actual=lib.bc_actors_draw(actors,0,0)
                        assert actual==((2 if entering else 1)<<8)+(not expected.handled)
                        assert count.value==int(expected.visible) and bytes(actors)==before
                        if expected.visible:
                            assert all(getattr(submitted[0],n)==getattr(expected,n) for n,_ in Sprite._fields_)
                        reset_cases+=1
    print(f'PASS: {reset_cases} hidden/unknown cache-reset collisions')
    print(f'PASS: {transitions} shared-shot boss entry/defeat/reset/reprise transitions')
    print(f'PASS: 1200 cache updates, {rendered} submissions; 256 synchronized updates, {synchronized} submissions; keys/buckets, coordinates, slot reuse, composite/empty counts and simulation bytes match')
