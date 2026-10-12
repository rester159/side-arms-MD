#!/usr/bin/env python3
"""Import all nine original PCE boss bodies into resident Genesis graphics."""
from pathlib import Path
from bc_boss_shapes import build, write_metadata
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'src/gen/bc_boss_art.c'
text='/* Generated original PCE boss bodies; shared Genesis palette indices. */\n'
emitted={}
for number in range(1,10):
    name='bc_boss_patterns' if number==1 else f'bc_boss{number}_patterns'
    packed=build(number)
    signature=bytes(packed)
    if signature in emitted:
        text+=f'extern const unsigned char {name}[{len(packed)}] __attribute__((alias("{emitted[signature]}")));\n'
        continue
    emitted[signature]=name
    text+=f'const unsigned char {name}[{len(packed)}] __attribute__((aligned(512))) = {{\n'+\
        ''.join('    '+','.join('0x%02x'%v for v in packed[i:i+32])+',\n' for i in range(0,len(packed),32))+'};\n'
write_metadata()
out.write_text(text)
print('Nine original PCE boss banks, including captured composite attacks')
