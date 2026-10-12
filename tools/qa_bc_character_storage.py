#!/usr/bin/env python3
"""Exercise sentinel, shared-block, full-block and flipped-template storage cases."""
from bc_background_storage import pack, flip_character

def resolve(block, words):
    return [None if not w else (flip_character(block[(w&2047)*32:(w&2047)*32+32],w&0x1800),w&0xe000) for w in words]

# PAL0 at donor index zero must try a later duplicate or reject this donor.
a=bytes([0x12])*32;b=bytes([0x34])*32
normal=a+a+b+bytes(13*32)
source=bytes(32)+a+b+bytes(13*32)
words=[0,1,0x1802]+[0]*13
# Active transparent PAL0 also must remain active, not the blank sentinel.
transparent=[0x801]+[0]*15
# Sixteen distinct characters can fill a block when index zero is safe.
full=b''.join(bytes([i+1])+bytes([0x22])*31 for i in range(16))
full_words=[0x2000+i for i in range(16)]
# Two mixed subsets cannot use the Normal donor but fit in one private block.
c=bytes([0x56])*32;d=bytes([0x78])*32
blocks=[source,bytes(512),full,a+c+bytes(14*32),b+d+bytes(14*32)]
templates=words+transparent+full_words+[0x2000,1]+[0]*14+[0x2000,1]+[0]*14
private,new,sources,reused=pack(b''.join(blocks),templates,[('normal',normal)])
assert new[1]==1 and new[2]==0x1802
assert sources[3]==sources[4] and reused==2
for i,block in enumerate(blocks):
 name,offset=sources[i];data=normal if name=='normal' else private
 assert resolve(block,templates[i*16:(i+1)*16])==resolve(data[offset:offset+512],new[i*16:(i+1)*16])
assert pack(b''.join(blocks),templates,[('normal',normal)])==(private,new,sources,reused)
# A full block and a permutation of it must share storage. A blank index zero
# was previously reserved even though the palette bits make it active.
rotated = full[32:]+full[:32]
private,new,sources,reused=pack(full+rotated,full_words*2,[])
assert len(private)==512 and sources[0]==sources[1]
for i,block in enumerate((full,rotated)):
 assert resolve(block,full_words)==resolve(private,new[i*16:(i+1)*16])

# All but one color are PAL0/low priority. Conflicting choices for the safe
# zero slot must split the groups, even with the same sixteen characters.
low_words=[0x2000]+list(range(1,16))
private,new,sources,_=pack(full+rotated,low_words*2,[])
assert sources[0]!=sources[1]
for i,block in enumerate((full,rotated)):
 _,offset=sources[i]
 assert resolve(block,low_words)==resolve(private[offset:offset+512],new[i*16:(i+1)*16])
 assert all(new[i*16:(i+1)*16])
print('PASS: PAL0 sentinel, active transparency, flips, shared subsets, full 16-character sharing, conflicting zero slots and deterministic output.')

# Four asymmetric orientations can all reuse one Normal source character.
asymmetric = bytes((i*37+11)&255 for i in range(32))
donor = flip_character(asymmetric,0x1800)+bytes(15*32)
blocks = [flip_character(asymmetric,f)+bytes(15*32) for f in (0,0x800,0x1000,0x1800)]
words = [0x8000]+[0]*15
private,templates,sources,reused = pack(b''.join(blocks),words*4,[('normal',donor)])
assert reused==4 and not private
for i,block in enumerate(blocks):
 assert resolve(block,words)==resolve(donor,templates[i*16:(i+1)*16])
# A flip-only active template must not disappear when normalization cancels
# that flip. The private fallback must retain its visibility and geometry.
from bc_background_storage import canonical_character
canonical,_ = canonical_character(asymmetric)
flipped=flip_character(canonical,0x800)
assert canonical_character(flipped)[1]==0x800
block=flipped+bytes(15*32);words=[0x800]+[0]*15
private,templates,sources,_=pack(block,words,[])
assert templates[0]
assert resolve(block,words)==resolve(private,templates)
print('PASS: asymmetric H/V Normal-source reuse and flip-only sentinel preservation.')
