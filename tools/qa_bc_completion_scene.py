#!/usr/bin/env python3
"""Native Home ending-bonus boundary, separate scores and frozen gameplay."""
import argparse
import hashlib
import json
import ctypes as C
import struct
import subprocess
import tempfile
import re
import numpy as np
from pathlib import Path
from run_rom import ROOT,Runner,PAD
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--players',type=int,choices=range(1,5),required=True);p.add_argument('--wrapped',action='store_true',help='Exercise a living player whose three-digit bonus wraps to zero');p.add_argument('--hucard',action='store_true');p.add_argument('--rom',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
rom_path=a.rom or ROOT/'out/release/rom.bin'
rom_digest=hashlib.sha256(rom_path.read_bytes()).hexdigest()
r=Runner(rom=rom_path);r.run(2600)
if a.hucard:
    def choose(key):
        r.run(5,PAD[key]);r.run(20)
    choose('DOWN');choose('A');assert r.u32('flow_state')==9
    for _ in range(3):choose('DOWN')
    choose('A');assert r.u32('flow_state')==1
    for _ in range(8):choose('DOWN')
    choose('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
    choose('B');assert r.u32('flow_state')==9
zram=(C.c_uint8*8192).in_dll(r.lib,'zram')
hucard_underruns=[]

# Capture actual driver output separately during gallery and credits.
audio_chunks={3:[],6:[]}
def audio_output(samples,count):
    phase=r.read('ending_bonus_phase',1)[0]
    if a.hucard and zram[0x1b0a]:hucard_underruns.append(r.frames)
    if phase in audio_chunks and len(audio_chunks[phase])<180:
        audio_chunks[phase].append(C.string_at(samples,count*4))
    return count
audio_type=C.CFUNCTYPE(C.c_size_t,C.POINTER(C.c_int16),C.c_size_t)
audio_callback=audio_type(audio_output)
r.lib.retro_set_audio_sample_batch.argtypes=[audio_type]
r.lib.retro_set_audio_sample_batch(audio_callback)

# Enter the real final-round scene with the public Home presentation enabled.
# Boss completion is injected below; the separate serpent verifier covers it.
r.write('home_session',b'\1')
for key,value in [('dbg_bc_native_players',a.players),('dbg_bc_native_start_round',9),('dbg_bc_native_protect',1),('dbg_bc_native',1)]:r.write(key,value.to_bytes(2,'big'))
r.write('dbg_pad_override',b'\1');r.write('pad',bytes(8));r.run(180)
assert r.u16('dbg_bc_native_current_round')==9
scores=[]
for i in range(a.players):
    name='score' if i==0 else 'peer_scores';offset=0 if i==0 else (i-1)*35
    digits=bytes(map(int,f'{12345+i*100000:08d}'))
    r.write(name,digits,offset);r.write(name,bytes(8),offset+8)
    scores.append((name,offset,12345+i*100000))
reserves=([124] if a.players==1 else [124,0,1,255][:a.players]) if a.wrapped else ([2] if a.players==1 else [0,1,3,255][:a.players])
with tempfile.TemporaryDirectory() as directory:
    c=Path(directory)/'offset.c';assembly=c.with_suffix('.s')
    c.write_text('#include "bc_player.h"\nint life=__builtin_offsetof(BcPlayerControl,world.inventory.lives);\nint size=sizeof(BcPlayerControl);\n')
    subprocess.run([str(Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'),'-m68000','-I'+str(ROOT/'inc'),'-S',str(c),'-o',str(assembly)],check=True)
    offsets={name:int(value) for name,value in re.findall(r'(life|size):\s*\.long\s+(\d+)',assembly.read_text())}
def party_snapshot():
    primary=r.read('player',offsets['size'])
    address=r.u32('peers')
    return primary+bytes(r.ram[((address+i)&65535)^1] for i in range((a.players-1)*offsets['size']))
def assert_gameplay_frozen(expected):
    actual_party=party_snapshot()
    if actual_party!=expected[0]:
        (out/'party-before.bin').write_bytes(expected[0]);(out/'party-after.bin').write_bytes(actual_party)
        differences=[(i//offsets['size']+1,i%offsets['size'],before,after)
            for i,(before,after) in enumerate(zip(expected[0],actual_party)) if before!=after]
        raise AssertionError(('party changed',hex(r.u32('peers')),differences[:48],len(differences)))
    assert (actual_party,r.u32('dbg_bc_native_ticks'),r.read('seed',2))==expected
for i,life in enumerate(reserves):
    if not i:r.write('player',bytes([life]),offsets['life'])
    else:r.ram[((r.u32('peers')+(i-1)*offsets['size']+offsets['life'])&65535)^1]=life
units=[0 if life&128 else ((life+1)*32)%1000 for life in reserves]
duration=max(0 if life&128 else units[i] or 1000 for i,life in enumerate(reserves))
r.write('dbg_bc_native_status',b'\0\6')
cram=(C.c_uint16*64).in_dll(r.lib,'cram')
fade_in=[]; clear_fade=[]; clear_state=None
for _ in range(60):
    r.run(1)
    if r.read('ending_bonus_phase',1)==b'\x0a':
        frozen=(r.read('actors',1600),party_snapshot(),r.u32('dbg_bc_native_ticks'),r.read('seed',2))
        if clear_state is None:clear_state=frozen
        assert frozen==clear_state,'gameplay changed during final-clear fade'
        if r.u16('ending_bonus_clock')%3==2:
            clear_fade.append((7-r.u16('ending_bonus_clock')//3,tuple(cram)))
        if r.u16('ending_bonus_clock')==11:
            image_path=ROOT/f'.local/bc-completion-{a.players}p/clear-fade.png'
            image_path.parent.mkdir(exist_ok=True)
            r.capture(image_path)
    if r.read('ending_bonus_phase',1)==b'\x08' and r.u16('ending_bonus_clock')%3==2:
        fade_in.append((r.u16('ending_bonus_clock')//3,tuple(cram)))
    if r.read('ending_bonus_phase',1)==b'\1':break
assert r.read('ending_bonus_phase',1)==b'\1'
assert r.u16('ending_bonus_clock')==0
full_palette=struct.unpack('>64H',r.read('faded.0',128))
reference=(ROOT/'.local/pce-reference/round10-ending-presentation/code-007080.bin').read_bytes()
ramp=reference[0x2a9:0x2e9]
def expected_palette(level):
    return tuple(ramp[level*8+((c>>1)&7)] |
                 (ramp[level*8+((c>>5)&7)]<<3) |
                 (ramp[level*8+((c>>9)&7)]<<6) for c in full_palette)
assert [level for level,_ in clear_fade]==list(range(7,0,-1)),clear_fade
scene_palette=clear_fade[0][1]
for level,colors in clear_fade:
    expected=tuple(sum(ramp[level*8+((c>>shift)&7)]<<shift for shift in (0,3,6)) for c in scene_palette)
    assert colors==expected,(level,'final-clear fade CRAM')
assert [level for level,_ in fade_in]==list(range(7)),fade_in
for level,colors in fade_in:assert colors==expected_palette(level),(level,'fade-in CRAM')

sfx_before=r.u16('dbg_bc_native_actor_sfx_commands')
drops_before=r.u16('dbg_bc_native_actor_sfx_dropped')
assert list(struct.unpack('>'+str(a.players)+'H',r.read('ending_bonus_units',a.players*2)))==units, (r.read('ending_bonus_units',a.players*2).hex(),r.read('ending_robots',a.players).hex())
for i,(name,offset,value) in enumerate(scores):
    assert r.read(name,8,offset)==bytes(map(int,f'{value+units[i]*10000:08d}')), (i,r.read(name,8,offset).hex(),value,units[i],r.u16('player_limit'))
    assert r.read(name,8,offset+8)==r.read(name,8,offset)
state=(r.read('actors',1600),party_snapshot(),r.u32('dbg_bc_native_ticks'),r.read('seed',2))
out=a.output or ROOT/(f'.local/bc-completion-{a.players}p'+('-wrapped' if a.wrapped else '')+('-hucard' if a.hucard else '')); out.mkdir(exist_ok=True)
r.capture(out/'bonus-start.png')
# Start cannot dismiss counting or its final hold. Each bonus update consumes
# one normal frame; the initial text upload is outside this measured interval.
r.write('pad',bytes([0x80,0x80]+[0]*6))
start=r.u32('frame_counter')
seen=[]
while r.read('ending_bonus_phase',1)==b'\1':
    clock=r.u16('ending_bonus_clock')
    if not seen or clock!=seen[-1]:seen.append(clock)
    r.run(1)
    assert r.u16('dbg_bc_native')==1
assert seen==list(range(duration)),seen
# Sampling may catch phase 1 before the initial screen's frame has returned.
assert r.u32('frame_counter')-start in (duration,duration+1)
assert r.u16('ending_bonus_clock')==180
assert r.u16('dbg_bc_native_actor_sfx_commands')-sfx_before==duration
assert r.u16('dbg_bc_native_actor_sfx_dropped')==drops_before
assert r.u32('dbg_bc_native_actor_sfx_mask') & (1<<2)
if a.wrapped:
    # The rolled-over amount must show zero, not 10,000,000; the eliminated
    # P4 row also stays at zero throughout the other players' tally.
    zero=r.u16('digit_cache')
    for row in (8+4*i for i,amount in enumerate(units) if not amount):
        words=struct.unpack('>8H',r.read('win',16,(row*40+23)*2))
        assert words==(0,0,0,0,0,0,0,zero),(row,words,zero)
start=r.u32('frame_counter')
music_requests=r.u16('dbg_bc_native_music_requests')
while r.read('ending_bonus_phase',1)==b'\2':
    r.run(1)
    if r.u16('ending_bonus_clock')==178:r.capture(out/'bonus-total.png')
assert r.u32('frame_counter')-start==180
assert_gameplay_frozen(state[1:])
assert r.read('ending_bonus_phase',1)==b'\x09'
fade_start=r.u32('frame_counter')
fade_out=[]
while r.read('ending_bonus_phase',1)==b'\x09':
    if r.u16('ending_bonus_clock')%3==2:
        level=7-r.u16('ending_bonus_clock')//3
        assert tuple(cram)==expected_palette(level),(level,'fade-out CRAM')
        fade_out.append(level)
    r.run(1)
    assert r.u16('dbg_bc_native')==1
assert r.u32('frame_counter')-fade_start==21
assert fade_out==list(range(7,0,-1)),fade_out
assert r.read('actors',1600)==bytes(1600)
r.write('pad',bytes(8));r.run(2)
r.capture(out/'bonus-complete.png')
assert r.u16('dbg_bc_native_music_command')==0x21
if a.hucard:assert r.u16('dbg_hucard_track')==0x05 and r.read('hucard_active',1)==b'\1'
assert r.u16('dbg_bc_native_music_requests')==music_requests+1
# Run the actual gallery with early Start pressed; every portrait must appear
# and no mapped artwork may be missing. Check all native caption cells too.
r.write('pad',bytes([0x80,0x80]+[0]*6))
entries=set();recolored=set();normal_colors=set();caption_entries=set();steps=0
from build_bc_ending import extract
from inspect_bc_captions import layout
ending_code=(ROOT/'.local/pce-reference/round10-ending-presentation/code-007080.bin').read_bytes()
_,_,captions,_=extract(ending_code)
frame_text=ending_code[0x9d25-0x4000:0x9d4f-0x4000-1]
rom=rom_path.read_bytes()
font_start=r.symbols['bc_caption_tiles']
def vram_word(address): return (r.vram[address^1]<<8)|r.vram[(address+1)^1]
gallery_drops=r.u32('spr_dbg_dropped');gallery_remaps=r.u32('spr_dbg_remap')
gallery_start=r.u32('frame_counter')
while r.read('ending_bonus_phase',1)==b'\3':
    remaining,camera,entry,phase,spawn=struct.unpack('>HHBBB',r.read('ending_gallery',7))
    if phase==2 and entry not in entries:
        entries.add(entry)
        r.capture(out/f'gallery-{entry:02}.png')
    if phase==2 and 200<remaining<240 and entry not in caption_entries:
        page=((entry+1)&1)*32
        expected=[0]*1024
        for x,y,code in layout(frame_text):
            expected[(y+6)*32+x+4]=(3<<13)|(160+code-0x20)
        for x,y,code in layout(captions[entry]):
            expected[(y+4)*32+x+11]=(3<<13)|(160+code-0x20)
        for y in range(32):
            for x in range(32):
                address=0xe000+((y*64)+page+x)*2
                assert vram_word(address)==expected[y*32+x],(entry,x,y,'caption tile')
        assert vram_word(0x1002)==(32-camera)&65535,('caption scroll',entry,camera)
        if not caption_entries:
            assert bytes(r.vram[(160*32+i)^1] for i in range(157*32))==rom[font_start:font_start+157*32]
        caption_entries.add(entry)
    if phase==2 and (remaining>=255 or 32<remaining<100):
        sat=struct.unpack('>320H',r.read('vdpSpriteCache',640))
        palettes=[]
        for j in range(80):
            y,size,attr,x=sat[j*4:j*4+4]
            if size>>8:palettes.append((attr>>13)&3)
            if not size&127:break
        if palettes:
            if remaining>=255:
                assert all(pal>=2 for pal in palettes),(entry,remaining,palettes)
                normal_colors.add(entry)
            else:
                assert all(pal<2 for pal in palettes),(entry,remaining,palettes)
                if entry not in recolored:
                    recolored.add(entry);r.capture(out/f'gallery-{entry:02}-recolored.png')
    assert not r.u16('dbg_bc_native_actor_unmapped')
    assert r.u16('dbg_bc_native')==1
    r.run(1);steps+=1
    assert steps<6200
gallery_updates=r.u32('frame_counter')-gallery_start
assert gallery_updates==5810, ('gallery update duration',gallery_updates,steps)
assert entries==caption_entries==set(range(20)),(entries,caption_entries)
assert recolored==normal_colors==entries,(entries,recolored,normal_colors)
assert r.u32('spr_dbg_dropped')==gallery_drops and r.u32('spr_dbg_remap')==gallery_remaps
assert r.read('ending_bonus_phase',1)==b'\4'
assert r.u16('ending_gallery',2)==5376
assert_gameplay_frozen(state[1:])
# Preserve the source's 180-frame gallery hold before credits setup.
start=r.u32('frame_counter')
while r.read('ending_bonus_phase',1)==b'\4':r.run(1)
assert r.u32('frame_counter')-start==180
while r.read('ending_bonus_phase',1)==b'\5':r.run(1)
assert r.read('ending_bonus_phase',1)==b'\6'
# Compare every sampled vertical-scroll value with the captured source clock.
raw=(ROOT/'.local/pce-reference/round10-ending-complete/state.bin').read_bytes()
source={struct.unpack_from('<I',raw,o)[0]:int.from_bytes(raw[o+4+0x31:o+4+0x34],'big')>>8
        for o in range(0,len(raw),8196) if 13286<=struct.unpack_from('<I',raw,o)[0]<=19045}
vsram=(C.c_uint16*64).in_dll(r.lib,'vsram')
credit_start_clock=r.u16('ending_credit_clock')
# A faster scene can complete setup and the first credits update within one
# emulator video step. Account for that boundary without losing clock checks.
assert credit_start_clock<=2, ('late credits observation',credit_start_clock)
start=r.u32('frame_counter')-credit_start_clock;seen=set()
while r.read('ending_bonus_phase',1)==b'\6':
    clock=r.u16('ending_credit_clock')
    if a.hucard and clock==3:
        assert r.u16('dbg_hucard_track')==0x0f and r.read('hucard_active',1)==b'\1'
    if clock:
        assert (vsram[0]&0x7ff)==source[13285+clock],(clock,vsram[0],source[13285+clock])
        seen.add(clock)
    if clock in (512,2048,4096,5600):r.capture(out/f'credits-{clock}.png')
    r.run(1)
assert seen and min(seen)<=2
assert seen==set(range(min(seen),5760)),(len(seen),min(seen),max(seen))
assert r.u16('ending_credit_clock')==5760 and r.read('ending_bonus_phase',1)==b'\7'
assert r.u16('dbg_bc_native_music_command')==0xfe
assert r.u16('dbg_bc_native_music_requests')==music_requests+2
for phase,chunks in audio_chunks.items():
    assert len(chunks)==180,(phase,len(chunks))
    samples=np.frombuffer(b''.join(chunks),dtype=np.int16).astype(float)
    rms=float(np.sqrt(np.mean((samples-samples.mean())**2)))
    assert rms>1,('silent ending music',phase,rms)
    print('ending audio',phase,'RMS',round(rms,2))
assert r.u32('frame_counter')-start==5760
assert (vsram[0]&0x7ff)==1440
r.capture(out/'credits-final.png')
# Final credits remain still without input. Any selected player can return.
r.write('pad',bytes(8));r.run(60)
assert r.read('ending_bonus_phase',1)==b'\7' and r.u16('ending_credit_clock')==5760
assert_gameplay_frozen(state[1:])
button=bytearray(8);button[(a.players-1)*2:(a.players-1)*2+2]=bytes([0x10,0x10])
r.write('pad',button)
for _ in range(120):
    r.run(1)
    if not r.u16('dbg_bc_native') and r.u32('flow_state')==9:break
assert not r.u16('dbg_bc_native') and r.u32('flow_state')==9
if a.hucard:
    assert r.read('hucard_active',1)==b'\0', 'BC music still active after Home return'
# Re-enter through the public Home modal: background shadow reuse must not
# leave ending tiles/cache state in the next gameplay session.
r.write('dbg_pad_override',b'\0');r.run(20)
def tap(button):
    r.run(5,PAD[button]);r.run(20)
for _ in range(5):
    if r.read('home_cursor',1)==b'\1':break
    tap('DOWN')
assert r.read('home_cursor',1)==b'\1'
tap('A');assert r.read('player_dialog',1)==b'\1'
for _ in range((a.players-r.read('home_cfg',1,5)[0])%4):tap('DOWN')
tap('A');r.run(100)
assert r.u32('flow_state')==14 and r.u16('player_limit')==a.players
assert r.u16('dbg_bc_native_current_round')==0 and r.u32('dbg_bc_native_ticks')>30
assert r.u16('dbg_bc_native_background_active')==1
assert not r.u16('dbg_bc_native_unmapped') and not r.u16('dbg_bc_native_actor_unmapped')
assert not r.u16('dbg_bc_native_protect')
r.capture(out/'reentry.png')
if a.hucard:
    assert r.read('home_cfg',1,7)==b'\1'
    assert r.u16('dbg_hucard_track')==0x05 and r.read('hucard_active',1)==b'\1'
    assert not hucard_underruns, hucard_underruns[:10]
print(f'PASS: {a.players}P individual bonus/high scores, {duration} count updates, bonus/gallery holds, twenty portraits, 5760 credit updates matching source scroll, early Start inhibit and Home return; all twenty caption/frame layouts and font pixels verified; final-clear and bonus fades verified')

assert hashlib.sha256(rom_path.read_bytes()).hexdigest()==rom_digest, 'ROM changed during ending test'
(out/'result.json').write_text(json.dumps(dict(rom_sha256=rom_digest,players=a.players,
    hucard=a.hucard,hucard_underruns=len(hucard_underruns),wrapped=a.wrapped,reserves=reserves,bonus_units=units,count_updates=duration,
    frozen_party_bytes=a.players*offsets['size'],gallery_entries=20,
    gallery_updates=gallery_updates,gallery_video_frames=steps,credit_updates=5760,
    first_observed_credit_clock=min(seen),credit_scroll_samples=len(seen),
    final_clear_fade_verified=True,bonus_fades_verified=True,caption_pixels_verified=True,
    ending_audio_onset_verified=True,home_return_verified=True,gameplay_reentry_verified=True,
    fixture='Final completion injected into real native Home scene; not a campaign playthrough',
    full_campaign_verified=False,full_speed_verified=False),indent=2)+'\n')
