"""Append BC-only recolors; never mutate Normal patterns, keys, or CRAM.
Recipes contain RGB3 material colors, not replacement sprite pixels.
"""
import json
from pathlib import Path
import numpy as np
from bc_shading import fit_shades
ROOT=Path(__file__).resolve().parents[1]

def gallery_palettes(palettes):
    # Exactly the integer ramp in bc_scene.c:gallery_colors.
    result=[]
    for palette in palettes:
        out=[]
        for r,g,b in palette:
            light=((r*2*3+g*2*6+b*2)//10)&14
            out.append((7,7,7) if light==14 else (light//2, light*5//14, light*2//14))
        result.append(out)
    return result

def append_variants(raw, md, palettes, bank, index, keys, big, big_index, inc):
    recipes=json.loads((ROOT/'tools/data/bc_recolor_recipes.json').read_text())['recipes']
    decisions={r['id']:r for r in json.loads((ROOT/'tools/data/bc_art_resolved_decisions.json').read_text())['decisions']}
    assert {r['id'] for r in recipes}=={k for k,v in decisions.items() if v['decision']=='recolor'}
    # Pen 15 is an unused duplicate black in both Normal sprite banks.
    # BC gains real middle green/blue shades without touching any used color.
    for data in (bank,big):
        assert all((b&15)!=15 and (b>>4)!=15 for b in data)
    bc_palettes=[list(p)+[(0,0,0)]*(15-len(p)) for p in palettes]
    assert all(tuple(p[-1])==(0,0,0) for p in bc_palettes)
    bc_palettes[0][-1]=(1,4,0)
    bc_palettes[1][-1]=(1,3,7)
    pooled={}
    for recipe in recipes:
        group=(recipe['family'],recipe['source_palette'],recipe['normal_colour'],recipe['size'],recipe['family']==0x3690 and recipe['frame'] in (0x10,0x30))
        counts=pooled.setdefault(group,np.zeros(16,dtype=int))
        for offset in ((0,1,8,9) if recipe['size']==32 else (0,)):
            code=recipe['code']+offset
            for b in raw[code*128:(code+1)*128]:
                counts[b>>4]+=1;counts[b&15]+=1
    records=[];cache={};selectors={}
    for recipe in recipes:
        if recipe['family'] in (0x36d0,0x36d2,0x36d4):continue
        code=recipe['code'];colour=recipe['normal_colour'];size=recipe['size']
        offsets=(0,1,8,9) if size==32 else (0,)
        cells=[raw[(code+a)*128:(code+a+1)*128] for a in offsets]
        pens=np.array([v for cell in cells for b in cell for v in (b>>4,b&15)])
        target=np.array([recipe['pen_targets'].get(str(p),md[512+colour*16+p]) for p in range(15)])
        # Black outline is material, not background. Preserve its exact shade.
        for p in range(15):
            if max(md[512+colour*16+p])<=1:target[p]=md[512+colour*16+p]
        groups=None
        if recipe['family'] in (0x3682,0x3684):
            # These reviewed ships have separate body and exhaust ramps. A
            # white exhaust pen is not part of the neutral metal body ramp.
            blue=[(0,0,2),(1,1,7),(1,3,7),(3,6,7),(7,7,7)]
            green=[(0,2,0),(0,3,0),(1,4,0),(4,7,1),(7,7,7)]
            orange=[(3,0,0),(7,0,0),(7,4,0),(7,7,0),(7,7,7)]
            if recipe['family']==0x3684:
                groups=[list(range(1,6)),list(range(6,10)),list(range(10,15))]
                target[1:6]=green if recipe['source_palette']==4 else blue
                target[10:15]=blue if recipe['source_palette']==4 else orange
            else:
                groups=[list(range(1,6)),list(range(6,10)),list(range(10,15))]
                target[1:6]=orange
                target[10:15]=blue
        if recipe['family']==0x3696 and size==32 and recipe['source_palette']==8:
            # The redrawn capsule's side lobes use pens 6..9. Pixel overlap
            # reverses their sampled brightness against BC's narrower flames;
            # preserve the material ramp instead of fitting green highlights.
            target[6:10]=[(3,0,0),(7,0,0),(7,4,0),(7,7,0)]
        flash=recipe['family']==0x3690 and recipe['frame'] in (0x10,0x30)
        if flash and recipe['source_palette']!=15:
            target[6:10]=[(0,0,7),(1,3,7),(0,6,7),(7,7,7)]
        weights=pooled[(recipe['family'],recipe['source_palette'],colour,size,flash)][:15]
        available=gallery_palettes(palettes) if recipe['source_palette']==15 else bc_palettes
        original=np.array(md[512+colour*16:512+colour*16+15])
        choices=[fit_shades(original,target,weights,palette,groups) for palette in available]
        selection=min(range(2),key=lambda p:choices[p][0]);lut=[p+1 for p in choices[selection][1]]+[0]
        shade_ramps=choices[selection][2]
        converted=[bytes((lut[b>>4]<<4)|lut[b&15] for b in cell) for cell in cells]
        if size==32:
            tl,tr,bl,br=converted;packed=bytearray()
            for x in range(4):
                top,bot=(tl,bl) if x<2 else (tr,br);h=(x&1)*64
                packed+=top[h:h+64]+bot[h:h+64]
        else:packed=converted[0]
        dest,lookup=(big,big_index) if size==32 else (bank,index)
        signature=(size,code,selection,bytes(packed))
        if signature in cache:key=cache[signature]
        else:
            key=next((code|(c<<11) for c in range(15,-1,-1) if not lookup[code|(c<<11)]),None)
            assert key is not None,f'No unused color key for {code:03x}'
            dest.extend(packed);entry=len(dest)//(size*size//2)
            assert entry<32768
            lookup[key]=entry|(selection<<15)
            if size==16:keys.append(key)
            cache[signature]=key
        selector=(recipe['family'],recipe['source_palette'],recipe['frame'])
        assert selector not in selectors or selectors[selector]==key
        selectors[selector]=key
        records.append(dict(**recipe,bc_colour=key>>11,palette=selection,key=key,pen_lut=lut,shade_ramps=shade_ramps))
    from bc_beam_shapes import append_shapes
    append_shapes(bank,index,keys,selectors,records,bc_palettes)
    from bc_unique_shapes import append_shapes as append_unique_shapes
    append_unique_shapes(bank,index,keys,selectors,records,bc_palettes)
    from bc_boss_shots import append_shapes as append_boss_shots
    append_boss_shots(bank,index,keys,selectors,bc_palettes)
    from bc_serpent_shapes import append_shapes as append_serpent
    append_serpent(big,big_index,selectors,bc_palettes)
    from bc_player_death_shapes import append_shapes as append_player_death
    append_player_death(big,big_index,bc_palettes)
    from bc_player_projectile_shapes import append_shapes as append_player_projectiles
    append_player_projectiles(bank,index,keys,bc_palettes)
    # Small nested switches avoid a linear walk through 100 entries each miss.
    lines=['/* Generated BC-only keys. Explicit keep/unresolved poses fall through. */',
           '#pragma once','static unsigned int bc_recolored_pose(unsigned short family, unsigned short frame, unsigned short attributes, unsigned int pose)',
           '{','    if (!(pose & 0x80000u)) return pose;','    switch (family) {']
    for family in sorted({s[0] for s in selectors}):
        lines+= [f'    case 0x{family:04x}:', '        switch (attributes & 15) {']
        for pal in sorted({s[1] for s in selectors if s[0]==family}):
            lines+=[f'        case {pal}:','            switch (frame) {']
            for (f,p,frame),key in sorted(selectors.items()):
                if (f,p)==(family,pal):lines.append(f'            case {frame}: return (pose & ~0x7fffu) | 0x{key:04x}u;')
            lines+=['            default: break;','            }','            break;']
        lines+=['        default: break;','        }','        break;']
    lines+=['    default: break;','    }','    return pose;','}']
    (inc/'bc_recolor_keys.h').write_text('\n'.join(lines)+'\n')
    return records, bc_palettes
