#!/usr/bin/env python3
"""Package ending lookup data; source instructions and pixels are excluded."""
import hashlib
import json
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA = 'bbd7f05a8d836aa565e75cabf93a415fa30fc1f47eade5968ed82dfa7ea8788b'
ORIGIN, END = 0xa478, 0xaabe


def extract(program):
    assert hashlib.sha256(program).hexdigest() == SOURCE_SHA
    def at(address, length):
        return program[address-0x4000:address-0x4000+length]
    packed = bytearray(END-ORIGIN)
    # Preserve source addresses, but leave the translated task code gap zero.
    for start, end in ((ORIGIN, 0xa9fa), (0xaa9e, END)):
        packed[start-ORIGIN:end-ORIGIN] = at(start, end-start)
    assert at(0xae39, 8) == bytes.fromhex('7341ae7836600060')
    bases = struct.unpack('>48H', at(0xae41, 96))
    for entry, address in enumerate(struct.unpack('<20H', at(ORIGIN, 40))):
        for part in range(3 if entry in (13, 14) else 1):
            record = address + part*56
            assert 0xa4a0 <= record < 0xa9fa-19
            ref, animation, routine, death = struct.unpack('<4H', at(record+11, 8))
            assert 0x3678 <= ref < 0x36d8 and not ref & 1
            assert record+19 == animation
            assert routine in (0x94ad, 0xa9fa, 0xaa4f) and death == 0x94ad
    captions = []
    for address in struct.unpack('<20H', at(0x9d4f, 40)):
        start = address-0x4000
        captions.append(program[start:program.index(b'\\', start)])
    start = END-0x4000
    rows = program[start:program.index(b'\\', start)].decode('ascii').split('/')
    assert len(rows) == 181 and rows[-1] == ''
    return bytes(packed), bases, captions, rows


def main():
    reference = ROOT/'.local/pce-reference'
    program = (reference/'round10-ending-presentation/code-007080.bin').read_bytes()
    packed, bases, captions, rows = extract(program)
    frame = program[0x9d25-0x4000:0x9d4f-0x4000-1]
    assert frame == b'hlllli/n    o/n    o/n    o/n    o/jmmmmk'
    def array(name, values, ctype='unsigned char'):
        return f'const {ctype} {name}[{len(values)}] = {{\n'+''.join(
            '    '+','.join(hex(v) for v in values[i:i+16])+',\n'
            for i in range(0, len(values), 16))+'};\n'
    output = '/* Generated ending data. No source CPU instructions or artwork. */\n#include "bc_ending_data.h"\n'
    output += array('bc_gallery_frame', frame)
    output += array('bc_gallery_bytes', packed)
    output += 'const BcEnemyData bc_gallery_data = {bc_gallery_bytes, 0xa478};\n'
    output += array('bc_gallery_bases', bases, 'unsigned short')
    for i, caption in enumerate(captions):
        output += array(f'bc_gallery_caption_{i}', caption)
    output += 'const BcEndingCaption bc_gallery_captions[20] = {\n'+''.join(
        f'    {{bc_gallery_caption_{i}, {len(caption)}}},\n' for i, caption in enumerate(captions))+'};\n'
    output += 'const char * const bc_credit_rows[] = {\n'+''.join(
        '    '+json.dumps(row)+',\n' for row in rows)+'};\n'
    output += f'const unsigned short bc_credit_row_count = {len(rows)};\n'
    target = ROOT/'src/gen/bc_ending_data.c'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(output)
    manifest = dict(source_sha256=SOURCE_SHA, gallery_origin=ORIGIN, gallery_bytes=len(packed),
        gallery_sha256=hashlib.sha256(packed).hexdigest(), zeroed_instruction_bytes=0xaa9e-0xa9fa,
        portraits=20, sprite_bases=len(bases), caption_bytes=sum(map(len, captions)),
        credit_rows=len(rows), frame_bytes=len(frame),
        renderer_verification="tools/qa_bc_completion_scene.py")
    (reference/'native-ending-data.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
