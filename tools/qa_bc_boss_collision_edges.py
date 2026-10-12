#!/usr/bin/env python3
"""Exercise PCE-derived boss part sizes at contact edges and protection gates.

Expected strict overlap/consumption semantics are those of the PCE contact
routine, separately checked by qa_bc_contacts against actual emulator traces.
This synthetic boundary sweep supplements (does not replace) source replays.
"""
import argparse,ctypes as C,itertools,json,subprocess,tempfile
from pathlib import Path
from qa_bc_weapons import Weapons,Target,Hit
from qa_bc_enemies import Enemy
from qa_bc_player_contacts import Player,Event
ROOT=Path(__file__).resolve().parents[1]
class Index(C.Structure):
 _fields_=[('slots',C.c_uint8*28),('count',C.c_uint8),('x',C.c_uint8*28),('y',C.c_uint8*28)]+[(n,C.c_uint8)for n in ('min_x','max_x','min_y','max_y','half_x','half_y')]

def run(report):
 parts={(p['half_width'],p['half_height'])for r in report['rounds']for p in r['parts']}
 shot_cases=body_cases=0
 with tempfile.TemporaryDirectory()as td:
  path=Path(td)/'rules.dylib'
  subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(ROOT/'inc'),str(ROOT/'src/bc_rules.c'),'-o',str(path)],check=True)
  lib=C.CDLL(str(path))
  lib.bc_enemy_shots.argtypes=[C.POINTER(Target),C.POINTER(Weapons)];lib.bc_enemy_shots.restype=Hit
  lib.bc_enemy_shots_indexed.argtypes=[C.POINTER(Target),C.POINTER(Weapons),C.POINTER(Index)];lib.bc_enemy_shots_indexed.restype=Hit
  lib.bc_shot_index.argtypes=[C.POINTER(Index),C.POINTER(Weapons)]
  lib.bc_enemy_player.argtypes=[C.POINTER(Enemy),C.c_uint8,C.c_uint8,C.c_uint8,C.POINTER(Player)];lib.bc_enemy_player.restype=Event
  for hx,hy in sorted(parts):
   for sx,sy in ((0,0),(4,4),(8,8),(16,2),(2,16)):
    rx,ry=hx+sx,hy+sy
    xs=(-rx-1,-rx,-rx+1,0,rx-1,rx,rx+1)
    ys=(-ry-1,-ry,-ry+1,0,ry-1,ry,ry+1)
    for dx,dy,(flags,cool,lock),kind,damage in itertools.product(xs,ys,((8,0,0),(9,0,0),(8,1,0),(8,255,0),(8,0,1)),(0,2),(1,10,12)):
     w=Weapons();b=w.shots[0].body;b.state=128;b.x=(128+dx)<<8;b.y=(112+dy)<<8;b.half_x=sx;b.half_y=sy;b.damage=damage;w.shots[0].kind=kind
     target=Target(128,112,hx,hy,flags,10,cool,lock)
     inside=abs(dx)<rx and abs(dy)<ry and not flags&1
     damaged=inside and not(cool or lock)
     index=Index();lib.bc_shot_index(C.byref(index),C.byref(w))
     expected=(int(inside),int(damaged),int(damaged and damage>=10))
     for indexed in (False,True):
      t=Target.from_buffer_copy(target);shots=Weapons.from_buffer_copy(w)
      hit=lib.bc_enemy_shots_indexed(C.byref(t),C.byref(shots),C.byref(index))if indexed else lib.bc_enemy_shots(C.byref(t),C.byref(shots))
      assert (hit.contacts,hit.damaged,hit.depleted)==expected,(hx,hy,dx,dy,indexed,'shot edge')
      assert t.hp==((10-damage)&255 if damaged else 10)
      assert shots.shots[0].body.state==(64 if inside and kind==0 else 128)
      shot_cases+=1
   rx,ry=hx+5,hy+8
   for dx,dy,(flags,state,invuln),option in itertools.product((-rx-1,-rx,-rx+1,0,rx-1,rx,rx+1),(-ry-1,-ry,-ry+1,0,ry-1,ry,ry+1),((8,128,0),(10,128,0),(8,64,0),(8,128,1)),(False,True)):
    enemy=Enemy();enemy.x=128<<8;enemy.y=112<<8;enemy.state=state;enemy.flags=flags
    player=Player(128+dx,112+dy,128,invuln,(C.c_uint8*2)(128 if option else 0,0))
    contact=state==128 and not flags&2 and not invuln and abs(dx)<rx and abs(dy)<ry
    hit=lib.bc_enemy_player(C.byref(enemy),hx,hy,0,C.byref(player))
    assert bool(hit.contact)==contact,(hx,hy,dx,dy,'body edge')
    assert player.state==(64 if contact and not option else 128)
    assert player.invulnerability==(16 if contact and option else invuln)
    assert enemy.state==state,'Composite body must survive player contact'
    body_cases+=1
 result=dict(passed=True,unique_boss_part_sizes=len(parts),shot_boundary_gate_cases=shot_cases,body_boundary_gate_cases=body_cases,rounds=len(report['rounds']),source='Part dimensions from current PCE boss replay report; strict-edge rules independently checked against PCE contact traces.')
 return result

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('report',type=Path);a=p.parse_args();result=run(json.loads(a.report.read_text()));out=a.report.with_name('boundaries.json');out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
