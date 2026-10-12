#!/usr/bin/env python3
"""Render an independent gallery font; never reads reference font pixels."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from inspect_bc_captions import KANA
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--font', type=Path, default=Path('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'))
a = p.parse_args()
font = ImageFont.truetype(str(a.font), 8)
words = []
for code in range(0x20, 0xbd):
    im = Image.new('L', (8,8)); draw = ImageDraw.Draw(im)
    char = KANA.get(code, chr(code) if code < 0x7f else ' ')
    if 0x68 <= code <= 0x6f:
        # Independently drawn single-pixel portrait frame, in source code order.
        if code in (0x68, 0x69, 0x6c): draw.line((0,0,7,0), fill=255)
        if code in (0x6a, 0x6b, 0x6d): draw.line((0,7,7,7), fill=255)
        if code in (0x68, 0x6a, 0x6e): draw.line((0,0,0,7), fill=255)
        if code in (0x69, 0x6b, 0x6f): draw.line((7,0,7,7), fill=255)
    elif code in (0xba, 0xbb):
        # Independent punctuation strokes sit just above the preceding kana.
        if code == 0xbb:
            draw.line((3,5,4,6), fill=255); draw.line((6,5,7,6), fill=255)
        else:
            draw.rectangle((4,4,6,6), outline=255)
    elif char.strip():
        draw.text((0,7), char, font=font, fill=255, anchor='ls')
    for y in range(8):
        word=0
        for x in range(8): word=(word<<4)|(2 if im.getpixel((x,y))>=96 else 0)
        words.append(word)
output='/* Independently rendered caption glyphs; PAL3 pen2, not PCE artwork. */\n#include "bc_ending_data.h"\n'
output+='const unsigned long bc_caption_tiles[1256] = {\n'
output+=''.join('    '+','.join(f'0x{x:08x}' for x in words[i:i+8])+',\n' for i in range(0,len(words),8))+'};\n'
(ROOT/'src/gen/bc_caption_font.c').write_text(output)
print(f'{len(words)//8} independently rendered 8x8 glyphs from {a.font.name}')
