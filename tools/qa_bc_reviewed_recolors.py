#!/usr/bin/env python3
"""Verify BC selection isolation, Normal bank preservation and sprite geometry."""
import ctypes as C,json,subprocess,tempfile,argparse,hashlib
from pathlib import Path
import numpy as np
from qa_bc_factory import Actor
from resolve_bc_art_decisions import identity
ROOT=Path(__file__).resolve().parents[1]
def corrected_normal_pose(ref,frame,pose):
    # Permit documented correspondence corrections against the frozen baseline.
    # Each correction specifies its Normal code/color; source flips, size,
    # visibility and handling bits must still agree.
    if ref==0x36ce and frame in (0,2) and pose&0x80000:
        return (pose&~2047)|(0x127 if frame==0 else 0x126)
    if ref==0x3694 and frame in (0,8,16,24) and pose&0x80000:
        return (pose&~32767)|(0x2e0+(frame>>2))
    if ref==0x3696 and frame in (0,8,16,18,20) and pose&0x80000:
        code=(0x344+(frame>>2)) if frame<16 else 0x350+((frame-16)>>1)
        return (pose&~32767)|code|(5<<11)
    if ref==0x3690 and frame in range(0,64,8) and pose&0x80000:
        code=[0x7c0,0x7c2,0x7c4,0x7c6,0x7d0,0x7e0,0x7e2,0x7e4][frame>>3]
        return (pose&~32767)|code|(5<<11)
    if ref==0x36c8 and frame==2 and pose&0x80000:
        return (pose&~32767)|0x122|(8<<11)
    if ref==0x3682 and frame==12 and pose&0x80000:
        return (pose&~2047)|0x309
    if ref==0x367a and frame in (0x2a,0x2e) and pose&0x80000:
        return (pose&~2047)|(0x110 if frame==0x2a else 0x1f)
    return pose

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--baseline',type=Path,required=True);ap.add_argument('--normal-art-source',type=Path,required=True)
    ap.add_argument('--normal-shade-baseline',type=Path,help='Explicit pre-repair banks for independent source-exact Normal shade verification')
    ap.add_argument('--selection-only',action='store_true',help='Verify BC decisions, source geometry and shade ramps; omit the historical whole-Normal-bank preservation audit')
    args=ap.parse_args()
    gen=ROOT/'res/generated';records=json.loads((gen/'bc_sprite_recolors.json').read_text());byid={r['id']:r for r in records}
    boss_shots=json.loads((gen/'bc_boss_shots.json').read_text())
    boss_shots += json.loads((gen/'bc_serpent_shapes.json').read_text())
    overrides={(r['family'],r['frame'],r['source_palette']):r for r in boss_shots if not r.get('boss_context_only',False)}
    repairs={};normal_shades=None
    if not args.selection_only:
        if args.normal_shade_baseline:
            from qa_normal_sprite_shades import verify
            normal_shades=verify(args.normal_shade_baseline)
            for row in json.loads((ROOT/'tools/data/normal_sprite_shade_repairs.json').read_text())['repairs']:
                for key in row['keys']:repairs[row['size'],key]=row
            prior=np.fromfile(args.baseline/'sprite_pal.bin','>u2');current=np.fromfile(gen/'sprite_pal.bin','>u2')
            assert set(np.flatnonzero(prior!=current))=={15,31}
        else:
            assert (args.baseline/'sprite_pal.bin').read_bytes()==(gen/'sprite_pal.bin').read_bytes()
        for name,stride in (('spr_bank',128),('spr_big',512)):
            old=np.fromfile(args.baseline/(name+'_index.bin'),'>u2');new=np.fromfile(gen/(name+'_index.bin'),'>u2')
            ob=(args.baseline/(name+'.bin')).read_bytes();nb=(gen/(name+'.bin')).read_bytes()
            for k in np.flatnonzero(old):
                a=int(old[k]);b=int(new[k]);assert (a&32768)==(b&32768)
                before=ob[((a&32767)-1)*stride:(a&32767)*stride];after=nb[((b&32767)-1)*stride:(b&32767)*stride]
                if before!=after:
                    repair=repairs.get((16 if stride==128 else 32,int(k)));assert repair,(name,k)
                    assert hashlib.sha256(before).hexdigest()==repair['before_sha256']
                    assert hashlib.sha256(after).hexdigest()==repair['after_sha256']
        normal_pal=np.fromfile(gen/'sprite_pal.bin','>u2');bc_pal=np.fromfile(gen/'bc_sprite_pal.bin','>u2')
        assert list(np.flatnonzero(normal_pal!=bc_pal))==[15,31]
        for bank in ('spr_bank','spr_big'):
            original=(args.baseline/(bank+'.bin')).read_bytes()
            assert all((b&15)!=15 and (b>>4)!=15 for b in original)
    family_luts={};shade_count=0
    for r in records:
        group=(r['family'],r['source_palette'],r['normal_colour'],r['size'],r['family']==0x3690 and r['frame'] in (0x10,0x30))
        lut=(r['palette'],r['pen_lut'])
        assert family_luts.setdefault(group,lut)==lut,('animation palette flicker',group)
        for ramp in r['shade_ramps']:
            light=ramp['luminance']
            assert all(b-a>.19 for a,b in zip(light,light[1:])),r['id']
            shade_count+=len(light)>1
    assert shade_count>100
    with tempfile.TemporaryDirectory() as td:
        libs=[]
        for i,src in enumerate([args.normal_art_source,ROOT/'src/bc_actor_art.c']):
            path=Path(td)/f'art{i}.dylib';subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'inc'),str(src),'-o',str(path)],check=True)
            lib=C.CDLL(str(path));lib.bc_actor_pose.argtypes=[C.POINTER(Actor)];lib.bc_actor_pose.restype=C.c_uint;libs.append(lib)
        counts=dict(recolor=0,keep=0,pending=0,new=0);cases=0
        for row in json.loads((ROOT/'tools/data/bc_art_resolved_decisions.json').read_text())['decisions']:
            ident=identity(row['id'])
            if not ident:continue
            ref,frame,pal=ident;counts[row['decision']]+=1
            for flips in (0,0x800,0x8000,0x8800):
                a=Actor();a.sprite_base_ref=ref;a.body.state=1;a.body.sprite_base=0x100;a.body.sprite=0x100+frame;a.body.attributes=pal|flips
                before=bytes(a);old,new=[lib.bc_actor_pose(C.byref(a)) for lib in libs];assert bytes(a)==before
                old=corrected_normal_pose(ref,frame,old)
                if (ref,frame,pal) in overrides:
                    # Later explicit instruction imports all original boss attacks.
                    r=overrides[(ref,frame,pal)]
                    assert (new&32767)==r['key'] and (new&~32767)==(old&~32767)
                elif row['decision'] in ('recolor','new'):
                    r=byid[row['id']];assert (new&32767)==r['key'];assert (new&~32767)==(old&~32767)
                    size=r['size'];bank='spr_big' if size==32 else 'spr_bank';length=size*size//2
                    data=(gen/(bank+'.bin')).read_bytes();idx=np.fromfile(gen/(bank+'_index.bin'),'>u2')
                    def mask(key):
                        n=int(idx[key])&32767;assert n
                        raw=data[(n-1)*length:n*length];return [(b>>4)!=0 for b in raw],[(b&15)!=0 for b in raw]
                    if row['decision']=='new':
                        assert r['geometry_source'] in ('bc_beam_shapes','bc_unique_shapes')
                        n=int(idx[new&32767])&32767
                        raw=data[(n-1)*length:n*length]
                        for y in range(16):
                            for x in range(16):
                                b=raw[((x//8)*2+y//8)*32+(y%8)*4+(x%8)//2]
                                pen=b>>4 if x%2==0 else b&15
                                assert pen==r['pen_lut'][int(r['rows'][y][x],16)],(row['id'],x,y)
                    else:assert mask(new&32767)==mask(old&32767),row['id']
                else:assert new==old,(row['id'],hex(old),hex(new))
                cases+=1
        # Unreviewed palette/pose combinations must fall back exactly, including Jet.
        selected={(r['family'],r['frame'],r['source_palette']) for r in records}|set(overrides)
        for ref in range(0x367a,0x36d6,2):
            for frame in range(0,58,2):
                for pal in range(16):
                    if (ref,frame,pal) in selected:continue
                    a=Actor();a.sprite_base_ref=ref;a.body.state=1;a.body.sprite_base=0x100;a.body.sprite=0x100+frame;a.body.attributes=pal
                    old,new=[lib.bc_actor_pose(C.byref(a)) for lib in libs];old=corrected_normal_pose(ref,frame,old);assert old==new,(ref,frame,pal);cases+=1
    print(json.dumps(dict(decisions=counts,user_requested_boss_shot_overrides=len(overrides),selection_cases=cases,normal_preservation_checked=not args.selection_only,normal_assets_unchanged=(normal_shades is None) if not args.selection_only else None,normal_shade_repairs=normal_shades,recolored_normal_opacity_unchanged=True,new_geometry_cards=counts['new'],distinct_ordered_shade_ramps=shade_count),indent=2))
if __name__=='__main__':main()
