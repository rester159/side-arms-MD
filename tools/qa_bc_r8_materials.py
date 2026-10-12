#!/usr/bin/env python3
"""Verify linked round-eight Normal materials, source layout and intact fronts."""
import argparse,hashlib,json,struct
from pathlib import Path
import numpy as np
from bc_background_equivalence import symbols,compare_round,rendered_cell
from arcade_source import Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from vivid_palette import light, index
import zones
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt')
rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
definition=json.loads((ROOT/'tools/data/bc_background_r8_materials.json').read_text())
code=rom[sy['bc_round8_code']:sy['bc_round8_code']+65536]
assert hashlib.sha256(code).hexdigest()==definition['source_code_sha256']
# Independent pre-conversion source decode: comparison against already fitted
# Normal pixels would hide the very shade merge this regression prevents.
source=Source();main=source.region('maincpu');bg=decode_bgtiles(source.region('bgtiles'))
codes,cols,_=bgmap_cells(source.region('bgmap'))
x,y,w,h=zones.ZONES[16]['rect']
metas=sorted({(int(codes[r,c]),int(cols[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
source_palette=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(main[0x14a37+i],main[0x14e37+i]))))for i in range(1024)],np.uint16)
remap=struct.unpack_from('>256H',rom,sy['bc_bg8_remap'])
palette=struct.unpack_from('>32H',rom,sy['bc_bg8_palette'])
def block_pixels(meta):
    cd,col=metas[meta];pens=bg[cd].astype(np.int32)
    assert col==19
    return np.where(pens==15,0,0x8000|source_palette[col*16+pens]).astype(np.uint16)
checked=0;actual_patterns={};seen=set()
for rec in definition['cells']:
    cell=rec['cell'];assert list(code[0x6220+cell*8:0x6228+cell*8])==rec['source_descriptor']
    if not rec.get('outside_sampled_gameplay'):assert rec['patterns']==rec['source_descriptor'][::2]
    entry=remap[cell];assert entry!=4095;seen.add(cell)
    actual=np.array([0 if p is None or not p[0] else 0x8000|palette[(p[1]>>13&1)*16+p[0]] for p in rendered_cell(rom,sy,'bc_bg8',entry)],np.uint16).reshape(32,32)
    for q,pattern in enumerate(rec['patterns']):
        src=definition['patterns'][f'{pattern:02x}'];m=src['normal_meta'];nq=src['normal_quadrant']
        donor=block_pixels(m)[nq//2*16:nq//2*16+16,nq%2*16:nq%2*16+16]
        piece=actual[q//2*16:q//2*16+16,q%2*16:q%2*16+16]
        assert np.array_equal(piece,donor),(cell,q,pattern)
        if pattern in actual_patterns:assert np.array_equal(piece,actual_patterns[pattern]),(cell,pattern,'repeat seam')
        actual_patterns[pattern]=piece;checked+=256
assert seen=={i for i,e in enumerate(remap)if e!=4095}
# Independently selected complete Normal front: map cells 23,24 / 27,28,
# at zone16 map (52,1), cropped across their central four quadrants.
nmap=np.fromfile(ROOT/'res/generated/zone16_map.bin','>u2').reshape(17,77)
assert nmap[1:3,52:54].tolist()==[[23,24],[27,28]]
normal_front=np.block([[block_pixels(23)[16:,16:],block_pixels(24)[16:,:16]],[block_pixels(27)[:16,16:],block_pixels(28)[:16,:16]]])
actual_front=np.block([[actual_patterns[0x11],actual_patterns[0x12]],[actual_patterns[0x0b],actual_patterns[0x1a]]])
assert np.array_equal(normal_front,actual_front)
lut=struct.unpack_from('>512H',rom,sy['vivid_lut'])
source_colors=set(map(int,source_palette[19*16:19*16+15]))
assert source_colors<=set(palette[1:16])
ordered=0
for a_color in source_colors:
    for b_color in source_colors:
        rgb=lambda w: (w>>1&7,w>>5&7,w>>9&7)
        if a_color!=b_color and all(a<=b for a,b in zip(rgb(a_color),rgb(b_color))):
            assert light(lut[index(a_color)])<light(lut[index(b_color)])
            ordered+=1
for n in range(1,11):
    name=f'bc_round{n}_code';assert old[os[name]:os[name]+65536]==rom[sy[name]:sy[name]+65536],name
unchanged=[compare_round(old,os,rom,sy,n)for n in range(1,11)if n!=8]
normal_blobs=0
for path in (ROOT/'res/generated').glob('zone*.bin'):
    if path.stem not in sy or path.stem not in os:continue
    data=path.read_bytes();assert rom[sy[path.stem]:sy[path.stem]+len(data)]==old[os[path.stem]:os[path.stem]+len(data)]==data,path.name;normal_blobs+=1
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),source_cells=len(seen),material_quadrants=checked//256,pixel_checks=checked,source_palette=19,source_rgb3_colors=len(source_colors),vivid_ordered_pairs=ordered,unique_source_patterns=len(actual_patterns),intact_cylinder_front_pixels=1024,source_banks_unchanged=10,other_round_cells_unchanged=sum(r['cells']for r in unchanged),normal_blobs_unchanged=normal_blobs,normal_zone=16,adaptation='Shorten barrel repeat at quadrant boundaries; preserve complete Normal circular fronts, all original pre-fit RGB3 material shades and geometry.',outside_sampled_gameplay=[129],full_speed_verified=False)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
