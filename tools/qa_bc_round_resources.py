#!/usr/bin/env python3
"""Check all ten compiled Genesis round descriptors against original captures."""
import hashlib
import json
import struct
from run_rom import ROOT,Runner

r=Runner()
rom=(ROOT/'out/release/rom.bin').read_bytes()
assert len(rom)<=0x400000
address=r.symbols['bc_round_resources']
layout=struct.Struct('>IHIIHHhBx') # 68000 pointers/u16, two-byte structure alignment.
results=[]
for i in range(10):
    code_ptr,origin,bases_ptr,header_ptr,reset,pose,relocation,round_id=layout.unpack_from(rom,address+i*layout.size)
    assert origin==0x4000 and round_id==i
    capture=ROOT/'.local/pce-reference'/f'round{i+1:02d}-reference'
    expected=(capture/'code-002160.bin').read_bytes()
    ram=(capture/'f002400-ram.bin').read_bytes()
    actual=rom[code_ptr:code_ptr+65536]
    assert actual==expected,('round code',i+1)
    assert rom[bases_ptr:bases_ptr+94]==ram[0x167a:0x16d8],('initialized bases',i+1)
    header=rom[header_ptr:header_ptr+8]
    assert header[:2]+header[6:8]==ram[0x67:0x6b],('initial checkpoint',i+1)
    assert header[4:6]==ram[0x44:0x46],('terrain pointer',i+1)
    assert actual[0x260e:0x2615]==b'\x73'+struct.pack('<H',reset)+bytes.fromhex('94202000')
    signature=bytes.fromhex('bdcc2df0273a9dcc2d')
    assert actual[0x5204+relocation:0x5204+relocation+len(signature)]==signature
    assert pose==0x9c07+relocation
    assert code_ptr<=header_ptr<code_ptr+65536
    results.append(dict(round=i+1,relocation=relocation,player_template=hex(reset),pose_table=hex(pose),
                        checkpoint=[header[0]*256,header[1]*256],code_sha256=hashlib.sha256(actual).hexdigest()))
for round_number,prefix in ((8,'bc_round8'),(10,'bc_final')):
    # Exhaust the generated final-round acceleration table against source addressing.
    final_code = r.symbols[f'bc_round{round_number}_code']
    cells_ptr = final_code + 0xc000
    attrs_ptr = final_code + int.from_bytes(rom[final_code+0x621c:final_code+0x621e], 'little') - 0x4000
    # LTO may fold the immutable descriptor into its callers.
    if prefix+'_terrain' in r.symbols:
        assert struct.unpack_from('>II', rom, r.symbols[prefix+'_terrain']) == (cells_ptr, attrs_ptr)
    direct = rom[r.symbols[prefix+'_solid']:r.symbols[prefix+'_solid']+65536]
    for y in range(0, 4096, 16):
        for x in range(0, 4096, 16):
            cell = ((x >> 5)&7) | (((y >> 5)&7)<<3) | (((x >> 8)&15)<<6) | (((y >> 8)&15)<<10)
            quadrant = ((x&16)>>3) | ((y&16)>>2)
            expected = rom[attrs_ptr+rom[cells_ptr+cell]*8+quadrant+1]&15
            assert direct[(y>>4)*256+(x>>4)] == expected, ('direct terrain', x, y)
result=dict(direct_terrain_subcells=131072,rounds=results,rom_bytes=len(rom),cartridge_limit=0x400000,all_rounds_playable=False)
out=ROOT/'.local/pce-reference/round-resources-qa.json';out.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
