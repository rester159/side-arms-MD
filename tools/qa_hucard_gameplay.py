#!/usr/bin/env python3
"""Exercise saved HuCard selection with a real four-player Home mode launch."""
import argparse
import ctypes as C
import hashlib
import shutil
import json
from pathlib import Path
from run_rom import ROOT,Runner,PAD
from qa_soak import O
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--mode',choices=('normal','bc','rush'),required=True)
p.add_argument('--players',type=int,choices=(1,2,3,4),default=4)
p.add_argument('--pal',action='store_true')
p.add_argument('--adapter', choices=('teamplayer1','teamplayer2','wayplay'),
               help='Use emulated six-button controller protocols instead of logical input injection')
p.add_argument('--output',type=Path,help='Keep this validation separate from previous build reports')
a=p.parse_args()
rom=ROOT/'out/release/rom.bin'
if a.pal:
    dest=ROOT/'.local/pce-hucard/gameplay-pal-rom';dest.mkdir(exist_ok=True)
    data=bytearray(rom.read_bytes());data[0x1f0:0x200]=b'E'+b' '*15
    (dest/'rom.bin').write_bytes(data);shutil.copy(rom.parent/'symbol.txt',dest/'symbol.txt')
    rom=dest/'rom.bin'
r=Runner(rom=rom)
controller_masks=[0]*8
if a.adapter:
    callback_type=C.CFUNCTYPE(C.c_int16,C.c_uint,C.c_uint,C.c_uint,C.c_uint)
    def controller_input(port,device,index,button):
        if device!=1 or port>=len(controller_masks):return 0
        mask=controller_masks[port] | (r.mask if port==0 else 0)
        return mask if button==256 else int(bool(mask & (1<<button)))
    callback=callback_type(controller_input);r.callbacks.append(callback)
    r.lib.retro_set_input_state.argtypes=[callback_type]
    r.lib.retro_set_input_state(callback)
    if a.adapter=='teamplayer2':
        # Initialize GX's logical and physical pad-type groups before wiring.
        r.lib.retro_set_controller_port_device(0,1793)
    devices={'teamplayer1':(1793,513),'teamplayer2':(513,1793),'wayplay':(1281,None)}[a.adapter]
    for port,device in enumerate(devices):
        if device is not None:r.lib.retro_set_controller_port_device(port,device)
class Timing(C.Structure):
    _fields_=[('geo',C.c_uint*4),('aspect',C.c_float),('fps',C.c_double),('rate',C.c_double)]
av=Timing();r.lib.retro_get_system_av_info(C.byref(av));assert (av.fps<55)==a.pal
r.run(2600)
zram=(C.c_uint8*8192).in_dll(r.lib,'zram')
out=a.output or ROOT/f'.local/pce-hucard/gameplay-{a.mode}-{a.players}p{"-pal" if a.pal else ""}';out.mkdir(parents=True,exist_ok=True)
def tap(b):r.run(5,PAD[b]);r.run(20)
def state():return r.u32('flow_state')
assert state()==0
tap('DOWN');tap('A');assert state()==9
for _ in range(3):tap('DOWN')
tap('A');assert state()==1
for _ in range(8):tap('DOWN')
tap('RIGHT');assert r.read('home_cfg',1,7)==b'\1'
r.capture(out/'music-option.png')
tap('B');assert state()==9
# Home retains its Options selection, so return to Normal before selecting mode.
for _ in range(3):tap('UP')
for _ in range(('normal','bc','rush').index(a.mode)):tap('DOWN')
tap('A')
for _ in range((a.players-2)%4):tap('DOWN')
tap('A')
assert r.u16('player_limit')==a.players
assert state()=={'normal':6,'bc':14,'rush':12}[a.mode]
tracks=set();underruns=[]
if not a.adapter:r.write('dbg_pad_override',b'\1')
seen_controllers=[False]*a.players
if a.mode=='bc':r.write('dbg_bc_native_protect',b'\0\1')
for frame in range(1800):
    if a.mode!='bc':
        for player in range(a.players):
            r.write('players',b'\xc8',player*O['s_Player']+O['o_Player_invuln'])
    bits=0x10 if frame%8<4 else 0
    if a.adapter:
        controller_masks[:a.players]=[PAD['A'] if bits else 0]*a.players
    else:r.write('pad',bytes([bits,bits]*a.players+[0,0]*(4-a.players)))
    r.run(1)
    if a.adapter:
        assert r.read('dbg_pad_override',1)==b'\0'
        for player in range(a.players):
            seen_controllers[player] |= bool(r.u16('pad_raw',player*4)&0x40)
    tracks.add(r.u16('dbg_hucard_track'))
    if zram[0x1b0a]:underruns.append((frame,int(zram[0x1b0a])))
assert not underruns,underruns[:10]
if a.adapter:
    assert all(seen_controllers),seen_controllers
    controller_masks[:]=[0]*8
assert r.read('hucard_active',1)==b'\1'
assert state()=={'normal':7,'bc':14,'rush':12}[a.mode]
if a.mode=='normal':assert {0x11,0x05} <= tracks,tracks
if a.mode=='bc':assert 0x05 in tracks,tracks
if a.mode=='rush':assert 0x12 in tracks,tracks
r.capture(out/'play.png')
# Pause uses actual controller edges; music keeps advancing while simulation holds.
pause_checks=[]
if a.adapter:
    pause_symbol='scene_paused' if a.mode=='bc' else 'game_paused'
    def simulation():
        return r.u32('dbg_bc_native_ticks') if a.mode=='bc' else r.u16('frame')
    def starts(indices, count):
        controller_masks[:]=[0]*8
        for index in indices:controller_masks[index]=PAD['START']
        r.run(count)
    r.run(10)
    for player in range(a.players):
        starts([player],5)
        assert r.read(pause_symbol,1)==b'\1',player
        frozen=simulation();heard=zram[0x1b0c]+256*zram[0x1b0d]
        # Holding Start must not toggle again.
        starts([player],120)
        assert r.read(pause_symbol,1)==b'\1' and simulation()==frozen
        assert ((zram[0x1b0c]+256*zram[0x1b0d]-heard)&65535)>100
        assert not zram[0x1b0a]
        if player==0:r.capture(out/'paused.png')
        starts([],10);starts([player],5);starts([],20)
        assert r.read(pause_symbol,1)==b'\0' and simulation()!=frozen
        pause_checks.append(player+1)
    starts(list(range(a.players)),5)
    assert r.read(pause_symbol,1)==b'\1'
    starts([],10)
    # The existing soft-reset chord must still work from a paused game.
    controller_masks[0]=PAD['A']|PAD['B']|PAD['C']|PAD['START']
    r.run(5);starts([],20)
    assert state()==0,state()

elif a.mode=='bc':
    r.write('dbg_pad_override',b'\0');r.run(10)
    tap('START');assert r.read('scene_paused',1)==b'\1'
    simulation=r.u32('dbg_bc_native_ticks');heard=zram[0x1b0c]+256*zram[0x1b0d]
    r.run(120)
    assert r.u32('dbg_bc_native_ticks')==simulation
    assert ((zram[0x1b0c]+256*zram[0x1b0d]-heard)&65535)>100
    assert not zram[0x1b0a]
    tap('START');assert r.read('scene_paused',1)==b'\0'

# A reset reloads the real version-5 SRAM written by Options and party launch.
l=r.lib;l.retro_get_memory_data.argtypes=[C.c_uint];l.retro_get_memory_data.restype=C.c_void_p
l.retro_get_memory_size.argtypes=[C.c_uint];l.retro_get_memory_size.restype=C.c_size_t
n=l.retro_get_memory_size(0);save=(C.c_ubyte*n).from_address(l.retro_get_memory_data(0))
logical=bytes(save)[1::2]
assert logical[40]==5 and logical[67]==a.players and logical[68]==1
l.retro_reset();r.run(2600)
assert r.read('home_cfg',1,7)==b'\1' and r.read('home_cfg',1,5)==bytes([a.players])
# Older settings retain player count and default to Arcade, without losing rank.
old=bytearray(logical);old[40]=4;checksum=0x5a
for byte in old[40:68]:checksum=(((checksum<<1)|(checksum>>7))&255)^byte
old[68]=checksum
for i,byte in enumerate(old):save[2*i+1]=byte
l.retro_reset();r.run(2600)
assert r.read('home_cfg',1,7)==b'\0'
assert r.read('home_cfg',1,5)==bytes([a.players])
report=dict(passed=True,mode=a.mode,players=a.players,pal=a.pal,tracks=sorted(tracks),underruns=0,
            adapter=a.adapter,controller_input_override=not bool(a.adapter),
            pause_controllers=pause_checks,saved_music=True,version4_migration=True,rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest())
(out/'result.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
