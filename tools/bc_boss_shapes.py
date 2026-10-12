"""Pack original PCE articulated bosses without flattening its shades."""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades
ROOT = Path(__file__).resolve().parents[1]


def build(number=2):
    boss = next(b for b in json.loads((ROOT/'tools/data/bc_composite_source_shapes.json').read_text())['bosses'] if b['round']==number)
    assert 1 <= number <= 9
    attacks=json.loads((ROOT/'tools/data/bc_boss_attack_shapes.json').read_text())['attacks']
    source_poses=boss['poses']+[a['pose'] for a in attacks if a['round']==number]
    words = np.frombuffer((ROOT/'res/generated/sprite_pal.bin').read_bytes(), '>u2').copy()
    # Preserve the original boss fit; Normal's recovered spare shades are private.
    words[15] = words[31] = 0
    palettes = [np.array([(int(w)>>1&7, int(w)>>5&7, int(w)>>9&7)
                          for w in words[i+1:i+16]]) for i in (0,16)]
    packed = bytearray(); poses = []; pieces = []; shared = {}
    for pose in source_poses:
        x0,y0,w,h = pose['bounds']
        pixels = np.zeros(((h+31)//32*32,(w+31)//32*32),dtype=np.uint8)
        for part in pose['pieces']:
            p = np.array([[int(v,16) for v in row] for row in part['rows']])
            y,x=part['y']-y0,part['x']-x0
            dst=pixels[y:y+16,x:x+16];dst[p!=0]=p[p!=0]
        colors=np.array(pose['colors'][1:]);weights=np.bincount(pixels.ravel(),minlength=16)[1:]
        # Captured palettes: pens 1–3 are hull shades, 6 its white highlight;
        # pens 4–5 are eye/exhaust shades, 7 is an opaque black outline.
        options=[fit_shades(colors,colors,weights,p,[[0,1,2,5],[3,4]]) for p in palettes]
        bank=min(range(2),key=lambda i:options[i][0]);_,lut,ramps=options[bank]
        lut=[0]+[int(p)+1 for p in lut];mapped=np.array(lut,dtype=np.uint8)[pixels]
        first=len(pieces)
        candidates=[]
        # Moving the 32px grid leaves source pixels at the same coordinates,
        # but lets mirrored 48px-high shells share complete hardware blocks.
        for oy in range(0,32,16):
            for ox in range(0,32,16):
                canvas=np.pad(mapped,((oy,32),(ox,32)))
                blocks=[]
                for y in range(0,canvas.shape[0]-31,32):
                    for x in range(0,canvas.shape[1]-31,32):
                        block=canvas[y:y+32,x:x+32]
                        if not np.any(block):continue
                        variants=[block,block[:,::-1],block[::-1,:],block[::-1,::-1]]
                        signature,flags=min((v.tobytes(),i) for i,v in enumerate(variants))
                        blocks.append((signature,flags,x0+x-ox,y0+y-oy))
                missing={b[0] for b in blocks if b[0] not in shared}
                candidates.append(((len(missing),len(blocks),ox+oy,oy,ox),blocks))
        blocks=min(candidates,key=lambda pair:pair[0])[1]
        for signature,flags,x,y in blocks:
            if signature not in shared:
                shared[signature]=len(packed)//512
                block=np.frombuffer(signature,dtype=np.uint8).reshape(32,32)
                packed.extend(int(block[ty*8+py,tx*8+px])<<4|int(block[ty*8+py,tx*8+px+1])
                              for tx in range(4) for ty in range(4) for py in range(8) for px in range(0,8,2))
            pieces.append(dict(tile=shared[signature],x=x,y=y,flags=flags))
        poses.append(dict(frame=pose['frame'],family=pose.get('family',boss['family']),first=first,count=len(pieces)-first,palette=bank,
                          pen_lut=lut,shade_ramps=ramps))
    count=len(packed)//512
    assert 0 < count <= 16
    meta=dict(round=number,family=boss['family'],block_count=count,pieces=pieces,poses=poses)
    (ROOT/f'res/generated/bc_boss{number}_geometry.json').write_text(json.dumps(meta,indent=2)+'\n')
    return packed


def write_metadata():
    banks=[json.loads((ROOT/f'res/generated/bc_boss{n}_geometry.json').read_text()) for n in range(1,10)]
    capacity=max(b['block_count'] for b in banks)
    header='/* Generated original PCE boss geometry, mapped to shared Genesis palettes. */\n'
    header+=f'#define BC_BOSS_BLOCK_CAPACITY {capacity}\n'
    header+='typedef struct { unsigned char tile; signed char x,y; unsigned char flags; } BcBossPiece;\n'
    header+='typedef struct { unsigned short frame,family; unsigned char first,count,palette; } BcBossPose;\n'
    header+='typedef struct { unsigned short family; unsigned char blocks,pose_count; const BcBossPiece *pieces; const BcBossPose *poses; } BcBossBank;\n'
    for bank in banks:
        n=bank['round']
        header+=f'static const BcBossPiece bc_boss{n}_pieces[] = {{\n'+''.join('    {%d,%d,%d,%d},\n'%(p['tile'],p['x'],p['y'],p['flags']) for p in bank['pieces'])+'};\n'
        header+=f'static const BcBossPose bc_boss{n}_poses[] = {{\n'+''.join('    {0x%04x,0x%04x,%d,%d,%d},\n'%(p['frame'],p['family'],p['first'],p['count'],p['palette']) for p in bank['poses'])+'};\n'
    header+='static const BcBossBank bc_boss_banks[] = {\n'+''.join('    {0x%04x,%d,%d,bc_boss%d_pieces,bc_boss%d_poses},\n'%(b['family'],b['block_count'],len(b['poses']),b['round'],b['round']) for b in banks)+'};\n'
    (ROOT/'src/gen/bc_boss_meta.h').write_text(header)
    (ROOT/'res/generated/bc_boss_geometry.json').write_text(json.dumps(dict(capacity=capacity,banks=banks),indent=2)+'\n')
