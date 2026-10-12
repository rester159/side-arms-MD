"""Read-only load counts for native QA; object kinds differ between the modes."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
from run_rom import ROOT
from bc_weapon_layout import beam_velocity_shift, player_layout

class WorkloadMetrics:
    scope = ('World counts include active enemies, enemy shots, pickups and dying records; '
             'Normal has additional separate effect pools. Weapon records include BC options, '
             'while Normal counts its main shot array. SAT entries include submitted hardware '
             'sprites of different sizes. Equal counts do not imply equal AI or pixel workload.')
    def __init__(self, runner, players):
        self.r, self.players = runner, players
        gdk = Path(os.environ.get('GDK', Path.home()/'mars/m68k-elf'))
        source = '''#include "enemy_int.h"
#include "bc_player.h"
#include "bc_stage.h"
#define V(n,v) int n=(v);
#define O(t,f) V(o_##t##_##f,__builtin_offsetof(t,f))
V(enemy_size,sizeof(Enemy)) O(Enemy,live)
V(player_size,sizeof(Player)) O(Player,shots)
V(shot_size,sizeof(Shot)) O(Shot,active)
V(actor_size,sizeof(BcActor)) O(BcActor,body.state)
V(actor_flags,__builtin_offsetof(BcActor,body.flags))
V(actor_routine,__builtin_offsetof(BcActor,routine))
V(actor_death_routine,__builtin_offsetof(BcActor,death_routine))
V(bc_player_size,sizeof(BcPlayerControl))
V(bc_stage_dx,__builtin_offsetof(BcStage,dx))
V(bc_stage_dy,__builtin_offsetof(BcStage,dy))
V(bc_stage_stopped,__builtin_offsetof(BcStage,stopped))
V(bc_speed,__builtin_offsetof(BcPlayerControl,speed))
V(bc_state,__builtin_offsetof(BcPlayerControl,world.state))
V(bc_invulnerability,__builtin_offsetof(BcPlayerControl,world.invulnerability))
V(bc_terrain_cells,__builtin_offsetof(BcActorStepData,terrain.cells))
V(bc_terrain_attributes,__builtin_offsetof(BcActorStepData,terrain.attributes))
V(bc_shots,__builtin_offsetof(BcPlayerControl,world.weapons.shots))
V(bc_shot_size,sizeof(BcShot)) V(bc_shot_state,__builtin_offsetof(BcShot,body.state))
V(bc_shot_kind,__builtin_offsetof(BcShot,kind))
V(small_count,N_SMALL) V(big_count,N_BIG) V(item_count,N_ITEM) V(shot_count,MAX_SHOTS)
'''.replace('O(BcActor,body.state)', 'V(actor_state,__builtin_offsetof(BcActor,body.state))')
        with tempfile.TemporaryDirectory() as directory:
            c=Path(directory)/'offsets.c';s=c.with_suffix('.s');c.write_text(source)
            subprocess.run([str(gdk/'bin/m68k-elf-gcc'),'-m68000','-ffreestanding','-S',str(c),'-o',str(s),
                '-I'+str(ROOT/'inc'),'-I'+str(ROOT/'src'),'-I'+str(gdk/'inc'),'-I'+str(gdk/'res')],check=True)
            self.o={name:0 if kind=='zero' else int(value) for name,kind,value in
                re.findall(r'^(\w+):\s*\.(long|zero)\s+(\d+)',s.read_text(),re.M)}
        assert self.o['actor_size'] in (50,54) and self.o['bc_player_size']==player_layout(beam_velocity_shift())['player_bytes']

    def byte(self,address):
        return self.r.ram[(address&65535)^1]

    def count(self,address,size,offset,n):
        return sum(bool(self.byte(address+i*size+offset)) for i in range(n))

    def sample(self,mode):
        r,o=self.r,self.o
        if mode=='bc':
            world=self.count(r.symbols['actors'],o['actor_size'],o['actor_state'],32)
            addresses=[r.symbols['player']]+[r.u32('peers')+i*o['bc_player_size'] for i in range(self.players-1)]
            shots=[self.count(at+o['bc_shots'],o['bc_shot_size'],o['bc_shot_state'],30) for at in addresses]
            pools={'actors':world}
        else:
            pools={name:self.count(r.symbols['en_'+name],o['enemy_size'],o['o_Enemy_live'],o[count+'_count'])
                   for name,count in [('small','small'),('big','big'),('item','item')]}
            world=sum(pools.values())
            shots=[self.count(r.symbols['players']+i*o['player_size']+o['o_Player_shots'],
                             o['shot_size'],o['o_Shot_active'],o['shot_count']) for i in range(self.players)]
        return dict(world_objects=world,world_pools=pools,weapon_records=sum(shots),
                    weapon_records_per_player=shots,sat_entries=r.u16('count'))

    def actor_families(self):
        """Scene-entry occupancy, not executed update counts (births can add work)."""
        r,o=self.r,self.o
        raw=r.read('actors',32*o['actor_size'])
        families={}
        for slot in range(32):
            actor=raw[slot*o['actor_size']:(slot+1)*o['actor_size']]
            state=actor[o['actor_state']]
            if not state:continue
            at=o['actor_routine'] if state==0x80 else o['actor_death_routine']
            handler=int.from_bytes(actor[at:at+2],'big')
            key=f"{handler:04x}/state-{state:02x}/flags-{actor[o['actor_flags']]:02x}"
            families[key]=families.get(key,0)+1
        return families

    def weapon_families(self):
        """Active weapon kinds per selected player at observation time."""
        r,o=self.r,self.o
        addresses=[r.symbols['player']]+[r.u32('peers')+i*o['bc_player_size'] for i in range(self.players-1)]
        result=[]
        for address in addresses:
            kinds={}
            for i in range(30):
                at=address+o['bc_shots']+i*o['bc_shot_size']
                state=self.byte(at+o['bc_shot_state'])
                if state:
                    key=f"kind-{self.byte(at+o['bc_shot_kind'])}/state-{state:02x}"
                    kinds[key]=kinds.get(key,0)+1
            result.append(kinds)
        return result
