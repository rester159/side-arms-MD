#!/usr/bin/env python3
"""Verify only the four reviewed R2 whole-frame vertical orientations change."""
import argparse,json,hashlib,struct
from pathlib import Path
from bc_background_equivalence import symbols,rendered_cell,compare_round
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
old=(a.baseline/'rom.bin').read_bytes();os=symbols(a.baseline/'symbol.txt');rom=(ROOT/'out/release/rom.bin').read_bytes();sy=symbols(ROOT/'out/release/symbol.txt')
def cells(data,table):
 remap=struct.unpack_from('>256H',data,table['bc_bg2_remap']);pal=struct.unpack_from('>32H',data,table['bc_bg2_palette'])
 return {c:[None if not v or not v[0] else pal[((v[1]>>13)&1)*16+v[0]]for v in rendered_cell(data,table,'bc_bg2',m)]for c,m in enumerate(remap)if m!=4095},pal
before,bp=cells(old,os);after,ap=cells(rom,sy);assert bp==ap and before.keys()==after.keys();flipped={0x39,0x45,0x4d,0x58}
for c,pixels in before.items():
 expected=[pixels[(31-y)*32+x]for y in range(32)for x in range(32)]if c in flipped else pixels
 assert after[c]==expected,(c,'frame pixels/opacity')
for n in range(1,11):
 key=f'bc_round{n}_code';assert rom[sy[key]:sy[key]+65536]==old[os[key]:os[key]+65536]
others=[compare_round(old,os,rom,sy,n)for n in range(1,11)if n!=2]
r=dict(passed=True,rom_sha256=hashlib.sha256(rom).hexdigest(),vertical_frame_cells=sorted(flipped),unchanged_r2_cells=len(before)-4,r2_pixels_checked=len(before)*1024,other_round_cells_unchanged=sum(x['cells']for x in others),source_collision_banks_unchanged=10,r2_palette_unchanged=True,remaining_rom_bytes=len(rom)-sy['_etext'],scope='Four complete-frame orientations only; not R2 cave/machinery visual acceptance.')
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
