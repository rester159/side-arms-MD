#!/usr/bin/env python3
"""Compare consumed music packets with actual Z80 YM2612 writes in MAME.

This validates the packet-to-chip boundary, independently of audible-output
tests. Source-to-packet synthesis and timbre are separate checks.
"""
import argparse
import hashlib
import json
from pathlib import Path
from sound_test import ROOT, CART, mame, symbol


def expected_writes(packet, previous):
    writes = []
    for channel in range(6):
        voice = packet[channel*12:channel*12+12]
        part, offset = 1+channel//3, channel%3
        key = offset + (4 if part == 2 else 0)
        changed = voice[0] != previous[channel]
        if changed:
            writes.append((1, 0x28, key))
            for slot in range(4):
                writes.append((part, 0x30+offset+4*slot, voice[4+slot]))
            for base, value in [(0x50,31),(0x60,0),(0x70,0),(0x80,15),(0x90,0)]:
                writes.extend((part,base+offset+4*slot,value) for slot in range(4))
            writes.append((part,0xb0+offset,voice[3]&0x3f))
            previous[channel] = voice[0]
        writes.extend([(part,0xa4+offset,voice[1]),(part,0xa0+offset,voice[2]),
                       (part,0xb4+offset,voice[3]&0xc0)])
        writes.extend((part,0x40+offset+4*slot,voice[8+slot]) for slot in range(4))
        if changed: writes.append((1,0x28,0xf0|key))
    return writes


def verify(path):
    previous = [255]*6
    packet = None
    writes = []
    count = total = changes = silent = feedback_writes = 0
    last_silent = False
    done = False
    for line in path.read_text().splitlines():
        fields = line.split('|')
        if fields[0] == 'F':
            assert packet is None, 'overlapping packet'
            packet = bytes.fromhex(fields[1]);assert len(packet)==72
            writes = []
        elif fields[0] == 'W':
            assert packet is not None
            write=(int(fields[1]),int(fields[2],16),int(fields[3],16))
            # Busy polling acknowledges Timer A between voice writes.
            if write[:2] == (1,0x27):
                assert write[2]==0x15, ('unexpected timer mode',write)
            else:
                writes.append(write)
        elif fields[0] == 'E':
            assert packet is not None
            changes += sum(packet[ch*12]!=previous[ch] for ch in range(6))
            expected = expected_writes(packet,previous)
            assert writes == expected, (path.name,count,'register mismatch',
                                        writes[:12],expected[:12])
            feedback_writes += sum(0xb0 <= reg <= 0xb2 and bool(value & 0x38)
                                   for part, reg, value in writes)
            last_silent = all(packet[ch*12+8+slot]==127
                              for ch in range(6) for slot in range(4))
            silent += last_silent
            count += 1;total += len(writes);packet=None
        elif fields[0] == 'DONE':
            assert int(fields[1])==0, 'queue underrun'
            done=True
    assert done and count>0, 'incomplete capture'
    # An emulator video boundary can interrupt the final chip transaction.
    # Only E-terminated transactions are counted and verified.
    return dict(frames=count,writes=total,instrument_changes=changes,feedback_writes=feedback_writes,
                silent_frames=silent,last_frame_silent=last_silent,
                trailing_partial=packet is not None)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pal',action='store_true')
    parser.add_argument('--seconds',type=float,default=12)
    parser.add_argument('--songs',type=int,nargs='+',default=list(range(21)))
    parser.add_argument('--verify-only',action='store_true',help='Recheck existing captures without running MAME')
    args=parser.parse_args()
    assert args.seconds>0 and all(0<=s<=20 for s in args.songs)
    label='registers-pal' if args.pal else 'registers-ntsc'
    if args.seconds!=12:
        label+='-'+format(args.seconds,'g')+'s'
    out=ROOT/'.local/pce-hucard'/label
    out.mkdir(parents=True,exist_ok=True)
    rows=[]
    for song in args.songs:
        log=out/f'{song:02x}.log'
        if not args.verify_only:
            mame(['megadriv' if args.pal else 'genesis','-cart',str(CART/'out/release/rom.bin'),
                  '-autoboot_script',str(ROOT/'tools/hucard_register_capture.lua')],out/'work',
                 dict(HC_OUT=str(log),HC_HOST=f'{symbol("host_hucard"):x}',
                      HC_SONG=str(song),HC_SECONDS=str(args.seconds)))
        row=dict(song=song,**verify(log))
        assert row['frames']>args.seconds*60-10, ('missing music frames',row)
        rows.append(row);print(json.dumps(row),flush=True)
    rom_hash=hashlib.sha256((CART/'out/release/rom.bin').read_bytes()).hexdigest()
    if args.verify_only:
        old=json.loads((out/'report.json').read_text())
        assert old['rom_sha256']==rom_hash, 'test ROM changed since capture'
    report=dict(passed=True,pal=args.pal,seconds=args.seconds,tracks=rows,
                rom_sha256=rom_hash)
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':
    main()
