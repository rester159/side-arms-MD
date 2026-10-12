#!/usr/bin/env python3
"""Package all ten local BC round resources for the translated native engine.
No PCE instructions execute on Genesis. Inputs and generated outputs remain
local and ignored, as with the existing arcade asset pipeline.
"""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def word(code, offset):
    return int.from_bytes(code[offset:offset+2], 'little')

def array(name, data):
    return 'const unsigned char '+name+'['+str(len(data))+'] = {\n'+''.join(
        '    '+','.join('0x%02x'%v for v in data[i:i+16])+',\n' for i in range(0,len(data),16))+'};\n'

def inspect(code, ram, round_index):
    assert len(code) == 65536 and len(ram) == 8192
    assert ram[0x4b] == round_index and ram[0x94] == 128, 'Expected live gameplay RAM from the selected round'
    signature = bytes.fromhex('bdcc2df0273a9dcc2d')
    assert code.count(signature) == 1
    relocation = code.index(signature) + 0x4000 - 0x9204
    # $660E copies the round-specific 32-byte player reset record to $2094.
    assert code[0x260e] == 0x73 and code[0x2611:0x2615] == bytes.fromhex('94202000')
    player_template = word(code, 0x260f)
    assert player_template == 0x9ba7 + relocation
    # $660B calls a round-specific TII of sprite-base words into $3678.
    assert code[0x260b] == 0x20
    init = word(code, 0x260c) - 0x4000
    assert code[init] == 0x73 and code[init+3:init+8] == bytes.fromhex('7836600060')
    source = word(code, init+1) - 0x4000
    bases = code[source+2:source+96]
    assert bases == ram[0x167a:0x16d8], 'Sprite bases differ from captured initialized RAM'
    # Header fetches are fixed at $A218/$A219/$A21E/$A21F in every round.
    assert code[0x2786:0x27a3] == bytes.fromhex('a54b0aaaad18a28567ad19a28568a54b0aaaad1ea28569ad1fa2856a60')
    header = code[0x6218:0x6220]
    assert word(header,4) == int.from_bytes(ram[0x44:0x46], 'little')
    return bases, dict(round=round_index+1, relocation=relocation, player_template=player_template,
                       pose_table=0x9c07+relocation, header_address=0xa218,
                       checkpoint=list(header[:2]), initial_script=word(header,6),
                       sprite_base_init=init+0x4000, sprite_base_table=source+0x4000,
                       code_sha256=hashlib.sha256(code).hexdigest(),
                       base_sha256=hashlib.sha256(bases).hexdigest())

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,default=ROOT/'.local/pce-reference/play-task-round1')
    p.add_argument('--reference-root',type=Path,default=ROOT/'.local/pce-reference')
    a=p.parse_args()
    generated=['/* Generated local round resources, never executable PCE code. */\n#include "bc_round_data.h"\n']
    manifest=[];rows=[];boss_vectors=[]
    for i in range(10):
        capture=a.capture if i==0 else a.reference_root/f'round{i+1:02d}-reference'
        code=(capture/'code-002160.bin').read_bytes()
        if i==0:
            trace=(capture/'play-task.bin').read_bytes()
            assert len(trace)>=8198 and len(trace)%8198==0
            ram=trace[6:8198]
        else:
            ram=(capture/'f002400-ram.bin').read_bytes()
        bases,info=inspect(code,ram,i)
        name=f'bc_round{i+1}'
        generated.extend((array(name+'_code',code),array(name+'_sprite_bases',bases)))
        if i in (7, 9):
            # Exact 16-pixel terrain flags for the two heaviest bullet stages.
            attr_offset = word(code, 0x621c) - 0x4000
            cells = code[0xc000:0x10000]
            attrs = code[attr_offset:attr_offset+2048]
            solid = bytearray(65536)
            for y in range(256):
                for x in range(256):
                    cell = cells[((y//16)*16+x//16)*64+(y%16//2)*8+x%16//2]
                    solid[y*256+x] = attrs[cell*8+(x&1)*2+(y&1)*4+1]&15
            prefix = 'bc_final' if i == 9 else 'bc_round8'
            generated.append(array(prefix+'_solid', solid))
            generated.append(f'const BcTerrain {prefix}_terrain = '+'{'+f'{name}_code+0xc000,{name}_code+0x{attr_offset:x}'+'};\n')
        if i in (2, 8):
            speeds=[]
            for speed in range(0, 10, 2):
                address=word(code, 0x8262+speed-0x4000)
                vectors=[]
                for direction in range(16):
                    at=address+direction*4-0x4000
                    pair=[int.from_bytes(code[at+axis:at+axis+2], 'little', signed=True)*256 for axis in (0,2)]
                    assert all(-8388608 <= value <= 8388352 for value in pair)
                    vectors.append('{%d,%d}' % tuple(pair))
                speeds.append('{'+','.join(vectors)+'}')
            boss_vectors.append('    {{'+name+'_code,0x4000},{'+','.join(speeds)+'}}')
        rows.append('    {{%s_code,0x4000},%s_sprite_bases,%s_code+0x6218,0x%04x,0x%04x,%d,%d}' %
                    (name,name,name,info['player_template'],info['pose_table'],info['relocation'],i))
        info['source']=str(capture.resolve());manifest.append(info)
    generated.append('const BcRoundResource bc_round_resources[BC_ROUND_COUNT] = {\n'+',\n'.join(rows)+'\n};\n')
    assert len(boss_vectors)==2
    generated.append('const BcBoss3NativeVectors bc_boss3_native_vectors[2] = {\n'+',\n'.join(boss_vectors)+'\n};\n')
    out=ROOT/'src/gen/bc_data.c';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(''.join(generated))
    result=dict(rounds=manifest,output=str(out),source_data_only=True,all_rounds_playable=False)
    (a.reference_root/'native-data.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(rounds=len(manifest),code_bytes=655360,sprite_base_bytes=940,output=str(out)),indent=2))

if __name__=='__main__':main()
