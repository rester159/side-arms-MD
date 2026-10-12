"""Read-only estimate of conservative spatial rejection after existing shot bounds."""
import re
import subprocess
import tempfile
from pathlib import Path
from run_rom import ROOT


class ContactGridAudit:
    def __init__(self, runner, rom):
        self.r = runner
        self.pc = runner.symbols['party_contact_scan']
        # This verified prologue reads event/actor/party at SP+4/+8/+12.
        # Refuse a new compiler ABI instead of guessing stack arguments.
        expected = bytes.fromhex('4fef fff4 48e7 3c3e 286f 0034 2c6f 0038 266f 003c')
        assert rom[self.pc:self.pc+len(expected)] == expected, 'Revalidate contact-scan ABI'
        fields = {'actor_x':('BcActor','body.x'),'actor_y':('BcActor','body.y'),
                  'actor_flags':('BcActor','body.flags'),'actor_state':('BcActor','body.state'),
                  'half_x':('BcActor','half_x'),'half_y':('BcActor','half_y'),
                  'party_count':('BcParty','count'),'party_policy':('BcParty','contact_policy'),
                  'player_state':('BcWorldPlayer','state'),'invulnerability':('BcWorldPlayer','invulnerability'),
                  'player_index':('BcWorldPlayer','shot_index'),'index_count':('BcShotIndex','count'),
                  'index_x':('BcShotIndex','x'),'index_y':('BcShotIndex','y'),
                  'min_x':('BcShotIndex','min_x'),'max_x':('BcShotIndex','max_x'),
                  'min_y':('BcShotIndex','min_y'),'max_y':('BcShotIndex','max_y'),
                  'index_half_x':('BcShotIndex','half_x'),'index_half_y':('BcShotIndex','half_y')}
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'offsets.c';s=c.with_suffix('.s')
            c.write_text('#include "bc_world.h"\n'+''.join(f'int {name}=__builtin_offsetof({t},{field});\n'for name,(t,field) in fields.items()))
            subprocess.run([str(Path.home()/'mars/m68k-elf/bin/m68k-elf-gcc'),'-m68000','-S','-I'+str(ROOT/'inc'),str(c),'-o',str(s)],check=True)
            self.o={n:0 if k=='zero' else int(v)for n,k,v in re.findall(r'^(\w+):\s*\.(long|zero)\s+(\d+)',s.read_text(),re.M)}
        assert set(fields)<=self.o.keys()
        self.counts=dict(contact_scan_calls=0,shot_immune_calls=0,living_members=0,missing_indices=0,
                         indexed_candidates=0,existing_bounds_rejected=0,bounds_passed=0,
                         row8_rejected=0,grid4x4_rejected=0,row8_whole_contact_rejected=0,
                         grid4x4_whole_contact_rejected=0,out_of_screen_targets=0,indexed_records_examined=0)

    def byte(self, at):return self.r.ram[(at&65535)^1]
    def word(self, at):return self.byte(at)*256+self.byte(at+1)
    def long(self, at):return self.word(at)*65536+self.word(at+2)

    def observe(self):
        c,o=self.counts,self.o
        sp=self.r.lib.m68k_get_reg(15)
        actor,party=self.long(sp+8),self.long(sp+12)
        bodies_far=self.byte(sp+19)
        count=self.byte(party+o['party_count']);assert 2<=count<=4
        c['contact_scan_calls']+=1
        flags=self.byte(actor+o['actor_flags'])
        if flags&1:c['shot_immune_calls']+=1;return
        # Native rotated coordinate containers expose their integer as first word.
        x,y=self.word(actor+o['actor_x']),self.word(actor+o['actor_y'])
        hx,hy=self.byte(actor+o['half_x']),self.byte(actor+o['half_y'])
        bodies=not bodies_far and self.byte(party+o['party_policy'])!=2 and self.byte(actor+o['actor_state'])==128 and not flags&2
        for owner in range(count):
            player=self.long(party+owner*4)
            if not player or self.byte(player+o['player_state'])!=128:continue
            c['living_members']+=1
            index=self.long(player+o['player_index'])
            if not index:c['missing_indices']+=1;continue
            n=self.byte(index+o['index_count']);assert n<=28
            if not n:continue
            c['indexed_candidates']+=1
            rx,ry=hx+self.byte(index+o['index_half_x']),hy+self.byte(index+o['index_half_y'])
            if x>((self.byte(index+o['max_x'])+rx)&65535) or ((x+rx)&65535)<self.byte(index+o['min_x']) or y>((self.byte(index+o['max_y'])+ry)&65535) or ((y+ry)&65535)<self.byte(index+o['min_y']):
                c['existing_bounds_rejected']+=1;continue
            c['bounds_passed']+=1
            if x>255 or y>255:c['out_of_screen_targets']+=1;continue
            x0,x1=max(0,x-rx),min(255,x+rx);y0,y1=max(0,y-ry),min(255,y+ry)
            xs=[self.byte(index+o['index_x']+i)for i in range(n)]
            ys=[self.byte(index+o['index_y']+i)for i in range(n)]
            c['indexed_records_examined']+=n
            row_hit=any(y0//32<=sy//32<=y1//32 for sy in ys)
            grid_hit=any(x0//64<=sx//64<=x1//64 and y0//64<=sy//64<=y1//64 for sx,sy in zip(xs,ys))
            body=bodies and not self.byte(player+o['invulnerability'])
            if body:
                px,py=self.long(player)>>8,self.long(player+4)>>8
                body=abs(x-px)<((hx+5)&255) and abs(y-py)<((hy+8)&255)
            c['row8_rejected']+=not row_hit;c['grid4x4_rejected']+=not grid_hit
            c['row8_whole_contact_rejected']+=not row_hit and not body
            c['grid4x4_whole_contact_rejected']+=not grid_hit and not body

    def result(self):
        return dict(**self.counts,scope='Read-only opportunities at party-contact entry, before earlier player hits can change actor state. Grid uses all cached records, including consumed shots, and widened maximum radii. Counts are an upper-bound opportunity study, not executed-call savings, cycle savings or a runtime optimization. Targets outside0..255 are excluded from grid estimates.')
