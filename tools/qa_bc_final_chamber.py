#!/usr/bin/env python3
"""Verify the final BC scenery is the intact Normal final-chamber face.

Compare linked ROM pixels, palettes and source maps, independently of the
builder's donor list. This verifies the corresponding Genesis composition,
not pixel equality with PCE's redrawn face or timing acceptance.
"""
import argparse
import hashlib
import json
import re
import struct
from pathlib import Path
import numpy as np
from bc_background_equivalence import rendered_cell
from arcade_source import Source, decode_bgtiles, bgmap_cells, palette_rgb
from quantize import to_md, md_word
from vivid_palette import light, index
import zones
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--baseline',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
def symbols(path):
    result={}
    for line in path.read_text().splitlines():
        v=line.split()
        if len(v)>=3:result[v[2]]=int(v[0],16)
    return result
rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt')
def words(name,count):return struct.unpack_from('>'+str(count)+'H',rom,sy[name])
source=Source();main=source.region('maincpu');bg=decode_bgtiles(source.region('bgtiles'))
codes,cols,_=bgmap_cells(source.region('bgmap'));x,y,w,h=zones.ZONES[21]['rect']
metas=sorted({(int(codes[r,c]),int(cols[r,c]))for r in range(y,y+h)for c in range(x,x+w)})
source_palette=np.array([md_word(to_md(tuple(v//17 for v in palette_rgb(main[0x14a37+i],main[0x14e37+i]))))for i in range(1024)],np.uint16)
source_colors=set()
def original(entry):
    cd,col=metas[entry&4095];assert col in (23,24)
    pens=bg[cd].astype(np.int32);colors=source_palette[col*16+pens]
    source_colors.update(map(int,colors[pens!=15]))
    result=np.where(pens==15,0,0x8000|colors)
    if entry&0x4000:result=result[:,::-1]
    if entry&0x8000:result=result[::-1,:]
    return result
nm=np.fromfile(ROOT/'res/generated/zone21_map.bin','>u2').reshape(17,13)
remap=words('bc_bg10_remap',256);count=max(e&4095 for e in remap if e!=4095)+1
code=rom[sy['bc_round10_code']:sy['bc_round10_code']+65536]
# Source face begins at world (3904,2336), in the original cell map.
from inspect_bc_background import cell_index
checks=0;seen=set();palette=np.array(words('bc_bg10_palette',32),np.uint16)
for y in range(5):
    for x in range(4):
        cell=code[0xc000+cell_index(3904+x*32,2336+y*32)]
        pixels=rendered_cell(rom,sy,'bc_bg10',remap[cell])
        actual=np.array([0 if p is None or not p[0] else 0x8000|int(palette[(p[1]>>13&1)*16+p[0]]) for p in pixels],np.uint16).reshape(32,32)
        expected=original(int(nm[10+y,4+x]))
        assert np.array_equal(actual,expected),(x,y,cell)
        checks+=actual.size;seen.add(cell)
assert seen==set(range(20))
lut=words('vivid_lut',512);ordered=set()
for bank in (palette[1:16],palette[17:32]):
    for a_color in map(int,set(bank)):
        for b_color in map(int,set(bank)):
            rgb=lambda w:(w>>1&7,w>>5&7,w>>9&7)
            if a_color!=b_color and all(a<=b for a,b in zip(rgb(a_color),rgb(b_color))):
                assert light(lut[index(a_color)])<light(lut[index(b_color)])
                ordered.add((a_color,b_color))
# All source round banks include cell IDs, collision descriptors and scripts.
for rnd in range(1,11):
    name=f'bc_round{rnd}_code'
    assert rom[sy[name]:sy[name]+65536]==old[os[name]:os[name]+65536],name
# Remap IDs may change when identical blocks share storage across rounds;
# compare their resolved patterns/templates, mirror bits and palette words.
from bc_background_equivalence import compare_round
for rnd in range(1,10):compare_round(old,os,rom,sy,rnd)
for zone in range(24):
    for kind in ('tiles','attr','map','pal'):
        name=f'zone{zone}_{kind}';expected=(ROOT/f'res/generated/{name}.bin').read_bytes()
        assert rom[sy[name]:sy[name]+len(expected)]==old[os[name]:os[name]+len(expected)]==expected,name
result=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),normal_face_pixels=checks,source_cells=sorted(seen),normal_zone=21,normal_map_rect=[4,10,4,5],source_rgb3_colors=len(source_colors),vivid_ordered_pairs=len(ordered),original_round_banks_unchanged=10,other_bc_scenery_rounds_unchanged=9,normal_zones_unchanged=24,unique_blocks=len({e&4095 for e in remap if e!=4095}),bank_blocks=count)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
