#!/usr/bin/env python3
"""Inspect the locally captured ending overlay; no linked graphics are produced."""
import argparse
import hashlib
import json
import struct
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--capture',type=Path,required=True)
p.add_argument('--code',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();code=a.code.read_bytes()
assert hashlib.sha256(code).hexdigest()=='bbd7f05a8d836aa565e75cabf93a415fa30fc1f47eade5968ed82dfa7ea8788b'
def at(address,length):return code[address-0x4000:address-0x4000+length]
def decimal(digits):
    assert all(x<10 for x in digits)
    return int(''.join(str(x) for x in digits))
rates=[decimal(at(0x6293+4*i,4))*10000 for i in range(6)]
assert rates==[10000,20000,40000,80000,160000,320000]
raw=(a.capture/'state.bin').read_bytes();assert len(raw)%8196==0
records=[(struct.unpack_from('<I',raw,i)[0],raw[i+4:i+8196]) for i in range(0,len(raw),8196)]
assert records
previous=records[0];bonus=None;gallery=[];last_gallery=0
for frame,ram in records[1:]:
    if bonus is None and ram[0xc4:0xcc]!=previous[1][0xc4:0xcc]:
        before=previous[1];remaining=before[0x4a];lives=before[0x4d]+1
        assert remaining<6 and lives<128
        # $60F3-$610B accumulates three decimal columns; $6112-$6122
        # adds only those columns, dropping overflow above column one.
        units=(rates[remaining]//10000*lives)%1000
        expected=bytearray(before[0xc4:0xcc]);value=(decimal(expected[1:4])+units)%1000
        expected[1:4]=bytes(map(int,f'{value:03d}'))
        assert ram[0xc4:0xcc]==expected
        assert ram[0xcc:0xd4]==bytes([0])+bytes(map(int,f'{units:03d}'))+bytes(4)
        bonus=dict(frame=frame,remaining_continues=remaining,total_robots=lives,
                   rate=rates[remaining],bonus=units*10000,score_before=decimal(before[0xc4:0xcc]),score_after=decimal(expected))
    if bonus and ram[0x73]!=last_gallery:
        index=ram[0x73]
        if 1<=index<=20:
            assert index==last_gallery+1,(frame,index,last_gallery)
            gallery.append(dict(frame=frame,completed_entries=index))
            last_gallery=index
    previous=(frame,ram)
assert bonus and len(gallery)==20
assert all(b['frame']-a['frame']==289 for a,b in zip(gallery,gallery[1:]))
assert records[-1][1][0xc4:0xcc]==records[-1][1][0xd4:0xdc], 'Final high-score copy differs'
# Source credit text uses slash for a new line and backslash to terminate.
credit_start=0xaabe-0x4000;credit_end=code.index(b'\\',credit_start)
credits=code[credit_start:credit_end].decode('ascii').split('/')
scroll=[];last_scroll=0
for frame,ram in records:
    if frame<gallery[-1]['frame']:continue
    value=int.from_bytes(ram[0x31:0x34],'big')
    if value!=last_scroll:scroll.append((frame,value));last_scroll=value
assert len(scroll)==(len(credits)-1)*16==2880
assert scroll[0][1]==128
assert all(b[0]-a[0]==2 and b[1]-a[1]==128 for a,b in zip(scroll,scroll[1:]))
assert records[-1][0]>scroll[-1][0]+32
credit_scroll=dict(first_step=scroll[0][0],last_step=scroll[-1][0],steps=len(scroll),
                   step_fixed_point=128,frames_per_step=2,pixels=scroll[-1][1]//256)
gallery_records=[]
for i in range(20):
    address=struct.unpack('<H',at(0x9d4f+2*i,2))[0]
    end=code.index(b'\\',address-0x4000)
    gallery_records.append(dict(index=i,address=hex(address),text_bytes=code[address-0x4000:end].hex()))
result=dict(code_sha256=hashlib.sha256(code).hexdigest(),capture=str(a.capture),
    capture_frames=[records[0][0],records[-1][0]],bonus_rates=rates,observed_bonus=bonus,
    gallery_completed=gallery,gallery_interval_frames=289,gallery_records=gallery_records,
    credit_lines=credits,credit_scroll=credit_scroll,reference_only=True,genesis_ending_implemented=False)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(bonus=bonus,gallery_entries=len(gallery),gallery_interval_frames=289,
    credit_lines=len(credits),credit_scroll=credit_scroll,report=str(a.output)),indent=2))
