#!/usr/bin/env python3
"""Regenerate reference/disasm/sound.txt: region-aware disassembly of the sound program a_04k.rom.

Code regions go through `unidasm -arch z80`; data regions (jump tables, note table, FM patches,
SFX/music sequence data) are dumped as hex so the listing never mis-syncs. Routine comments
summarise docs/re/sound.md. Development-only; output is ignored (reference/).
"""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from arcade_source import Source, ROOT

NOTES = {
    0x0000: 'RESET: im 1, sp=$C800, jp $0055',
    0x0018: 'rst $18: hl += a',
    0x0020: 'rst $20: hl += a ; a = (hl)',
    0x0028: 'rst $28: hl += 2a ; de = (hl) ; hl += 2',
    0x0030: 'rst $30: jump table following the rst, index a',
    0x0038: 'IRQ (YM2203 #1 Timer A, 249.13 Hz): ack/reload timer ($27=$15), $C000++, latch, music, SFX seq, SSG output',
    0x0055: 'init: delay, clear RAM $C000-$C7FF, prescaler ($2D) both chips, Timer A NA=$C8<<2|1=801, enable ($27=$05), ei, idle loop',
    0x009A: 'ym_write: bc=chip addr port, a=reg, d=data (waits busy bit 7)',
    0x00A9: 'read_latch: if ($D000) != last($C001) and != $FF -> dispatch (cmd & $3F) through table $00BB',
    0x00BB: 'COMMAND TABLE: 64 words (see docs/re/sound.md)',
    0x013B: 'cmd $00: stop SFX + stop music',
    0x0141: 'stop SFX: clear SFX slots $C500/$C600 (5 x $20 each)',
    0x015C: 'stop music: clear all 4 music sets $C100-$C400 (6 x $20 each), silence FM',
    0x0182: 'fm_silence: TL=$7F for regs $40-$4D and key-off ch0-2 on both chips, then invalidate patch cache',
    0x01B0: 'patch cache $C010-$C015 := $FF',
    0x01C3: 'clear music set $C100 (also $01CC=$C200, $01D5=$C300, $01DE=$C400)',
    0x01F2: 'music_start: hl=header (tempo, 6x{ptr lo, ptr hi, patch, gate}) -> set ix; $C026=1 (skip a tick)',
    0x0236: 'music_tick: pick highest active set ($C400>$C300>$C200>$C100, tested on channel 0); set change -> silence; run 6 channels',
    0x02B5: 'patch load if channel patch != cache: 24 regs $30-$8C + $B0 (FB/ALG); byte 25 (slot mask) + ch -> key-on byte (ix+6)',
    0x030A: 'channel tick: triplet flag (ix+1F) runs $031B twice on odd ticks',
    0x031B: 'duration countdown; on 0 -> $0362 read events; gate countdown (ix+A/B) -> key-off unless slur (ix+1E)',
    0x0362: 'event reader: see sequence format in docs/re/sound.md',
    0x03B6: 'cmd $DF: dotted note/rest (length table $0472)',
    0x03D7: 'note on: fnum from table ((ix+13/14) + 2*(byte&$1F)), write $A4/$A0, key-on $28',
    0x041A: 'duration (dotted) / $041F duration (normal): tempo*len -> (ix+3/4); gate = dur*(gate&15 or 1)/16 -> (ix+A/B)',
    0x046A: 'length table normal: 0,0,2,4,8,16,32,64 (index byte>>5)',
    0x0472: 'length table dotted: 0,0,3,6,12,24,48,96',
    0x047A: 'mul8: hl = h * e',
    0x048E: 'control byte xx11111: dispatch (byte>>5): octave, tempo, (unused ix+15), jump, mark, loop, dotted, end',
    0x0501: 'read stream byte: a=(ix+C/D)++, (ix+16)=a',
    0x0513: 'NOTE TABLE: entry 0 = rest; entries 1..96 = C#0..C8, big-endian (block<<3|fnum hi), fnum lo',
    0x05D5: 'sfx_tick: run highest active slot of chip 1 ($C580..$C500) and chip 2 ($C680..$C600)',
    0x064C: 'sfx slot tick: wait countdown, tone period slides every tick, volume/noise slides every 4th tick',
    0x0702: 'sfx event reader: top-level (byte>>2)&7: wait, mark, loop, repeat-forever, end',
    0x0785: 'sfx sub-command (byte>>5): 1-3 tone A-C, 4-6 volume A-C, 7 noise',
    0x08C5: 'sfx read byte: (ix+1A)=byte, (ix+1B)=peek next',
    0x08DE: 'SFX command handlers: ld ix,slot ; ld hl,data ; jp $09EC',
    0x09EC: 'sfx_start: set pointers, (ix+0)--, wait=0, mixer=$FF',
    0x0A12: 'ssg_output: per chip, highest active slot -> kill lower non-looping slots -> shadow $C750/$C760 -> 11 SSG regs',
    0x0BFF: 'write SSG regs 0-10 from shadow (de+1..)',
    0x0C3D: 'silent SSG register image (mixer $FF)',
    0x0C49: 'FM PATCHES: 63 x 32 bytes: [0..23] regs $30..$8C (DT/MUL,TL,KS/AR,AM/DR,SR,SL/RR x4 ops), [24] FB/ALG, [25] key-on slot mask',
    0x1429: 'SFX SEQUENCE DATA (SSG)',
    0x2A15: 'MUSIC: per command: call clear_set ; ld hl,header ; jp $01F2, then header + channel streams',
}

# (start, end_exclusive, kind)
REGIONS = [
    (0x0000, 0x00BB, 'code'), (0x00BB, 0x013B, 'data'), (0x013B, 0x046A, 'code'), (0x046A, 0x0472, 'data'), (0x0472, 0x047A, 'data'),
    (0x047A, 0x0497, 'code'), (0x0497, 0x04A7, 'data'), (0x04A7, 0x0513, 'code'), (0x0513, 0x05D5, 'data'),
    (0x05D5, 0x070F, 'code'), (0x070F, 0x071F, 'data'), (0x071F, 0x078F, 'code'), (0x078F, 0x079F, 'data'),
    (0x079F, 0x0C3D, 'code'), (0x0C3D, 0x0C49, 'data'),
    (0x0C49, 0x1429, 'data'), (0x1429, 0x2A15, 'data'),
]


def unidasm(rom_path, start, end):
    r = subprocess.run(['unidasm', str(rom_path), '-arch', 'z80', '-skip', str(start), '-basepc', f'{start:x}',
                        '-count', str(end - start)], capture_output=True, text=True, check=True)
    return [l for l in r.stdout.splitlines() if l.strip()]


def main():
    d = Source().region('audiocpu')
    rom = ROOT / 'rom/a_04k.rom'
    regions = list(REGIONS)
    # music area: handler stubs (9 bytes of code) followed by data, per command $20-$38
    stubs = sorted({d[0xBB + 2 * c] | d[0xBC + 2 * c] << 8 for c in range(0x20, 0x39)})
    pos = 0x2A15
    for s in stubs:
        if s > pos: regions.append((pos, s, 'data'))
        regions.append((s, s + 9, 'code')); pos = s + 9
    end = len(d)
    while d[end - 1] == 0xFF: end -= 1
    regions.append((pos, end, 'data')); regions.append((end, len(d), 'fill'))
    out = ['; Side Arms sound program a_04k.rom (audiocpu Z80 @ 4 MHz) - generated by tools/disasm_sound.py',
           '; map: $0000-$7FFF ROM, $C000-$C7FF RAM, $D000 latch (R), $F000/1 YM2203#1, $F002/3 YM2203#2',
           '; see docs/re/sound.md for the driver description', '']
    for a, b, kind in regions:
        out.append(f'; ---- ${a:04X}-${b - 1:04X} {kind}')
        if kind == 'code':
            for line in unidasm(rom, a, b):
                addr = int(line.split(':')[0], 16)
                if addr in NOTES: out.append(f'; {NOTES[addr]}')
                out.append(line)
        elif kind == 'data':
            for r in range(a, b, 16):
                if r == a and a in NOTES: out.append(f'; {NOTES[a]}')
                chunk = d[r:min(r + 16, b)]
                out.append(f'{r:04x}: ' + ' '.join(f'{x:02x}' for x in chunk))
        else:
            out.append(f'{a:04x}: ff x {b - a}')
        out.append('')
    dst = ROOT / 'reference/disasm/sound.txt'
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text('\n'.join(out) + '\n')
    print(dst, len(out), 'lines')


if __name__ == '__main__':
    main()
