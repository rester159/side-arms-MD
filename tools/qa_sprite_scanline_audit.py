#!/usr/bin/env python3
"""Check SAT audit boundaries against the pinned native core's overflow flag."""
import ctypes as C
import hashlib
from run_rom import Runner, CORE
from sprite_scanline_audit import SpriteScanlineAudit
assert hashlib.sha256(CORE.read_bytes()).hexdigest() == '20903bdbe7dde068ebc55eabb00a2bf45238a254f24fbe2285d12389520dbba0'
r=Runner();r.run(2600)
status=C.c_uint16.in_dll(r.lib,'status')
r.lib.parse_satb_m5.argtypes=[C.c_int]
r.lib.parse_satb_m5.restype=None
# (count,width,height,top,x,expected entry-over lines,width-over lines)
cases=[(20,8,8,100,10,0,0),(21,8,8,100,10,8,0),
       (10,32,8,100,10,0,0),(11,32,8,100,10,0,8),
       (11,32,8,100,-100,0,8),(21,8,16,-8,10,8,0),
       (21,8,16,220,10,4,0),(21,8,8,224,10,0,0)]
for count,width,height,y,x,entry_lines,width_lines in cases:
 a=SpriteScanlineAudit(r);base=C.c_uint16.in_dll(r.lib,'satb').value//2
 C.memset(C.addressof(a.sat),0,C.sizeof(a.sat))
 for i in range(count):
  q=i*4;a.sat[q]=(y+128)&511
  size=((width//8-1)<<2)|(height//8-1)
  a.sat[q+1]=(size<<8)|(i+1 if i<count-1 else 0)
  a.vram[base+q+2]=0;a.vram[base+q+3]=(x+128)&511
 a.observe();result=a.result()
 assert result['entry_over_limit_lines']==entry_lines,(cases,result)
 assert result['width_over_limit_lines']==width_lines,(cases,result)
 native=[]
 for line in range(224):
  status.value=0;r.lib.parse_satb_m5(line-1)
  if status.value&0x40:native.append(line)
 assert native==result['worst']['entry_over_lines'],(native,result)
print(f'PASS: {len(cases)} synthetic SAT boundary cases, 1792 native parser scanlines; width-demand boundary and offscreen-X cases.')

# One opaque pen in the second tile column/row of a 32x32 pattern.
# Every flip must identify the same source crop, independently of palette.
signatures=set()
for flip in (0,0x800,0x1000,0x1800):
 a=SpriteScanlineAudit(r,crop_inventory=True)
 C.memset(C.addressof(a.sat),0,C.sizeof(a.sat))
 for word in range(64*16,80*16):a.vram[word]=0
 a.vram[(64+5)*16]=0x1000
 a.sat[0]=128;a.sat[1]=15<<8
 a.vram[base+2]=64|flip|0x6000;a.vram[base+3]=128
 a.observe();inventory=a.result()['crop_inventory']
 assert len(inventory)==1
 signature,item=next(iter(inventory.items()));signatures.add(signature)
 assert item['crop']==[8,8,8,8] and item['occurrences']==1
 assert item['pressured_occurrences']==0
assert len(signatures)==1
print('PASS: four flipped/paletted patterns normalize to the same transparent-border crop.')
