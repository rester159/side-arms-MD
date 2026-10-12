#!/usr/bin/env python3
"""Compare score events/state with baseline while omitting discarded peer RNG work."""
import argparse
import ctypes as C,random,subprocess,tempfile,sys
from pathlib import Path
from qa_bc_score import Score,Event
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser()
parser.add_argument('--baseline', type=Path, required=True, help='Previous bc_score.c')
args=parser.parse_args()
rng=random.Random(0xbc)
with tempfile.TemporaryDirectory() as d:
 libs=[]
 for label,src in [('before',args.baseline.resolve()),('after',root/'src/bc_score.c')]:
  path=Path(d)/(label+'.dylib')
  subprocess.run(['cc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(root/'inc'),str(src),str(root/'src/bc_rules.c'),'-o',str(path)],check=True)
  l=C.CDLL(str(path));l.bc_score_step_extends.argtypes=[C.POINTER(Score),C.POINTER(C.c_uint16),C.POINTER(C.c_uint8),C.c_void_p,C.c_uint8];l.bc_score_step_extends.restype=Event;libs.append(l)
 for case in range(32768):
  s=Score();s.digits[:]=[rng.randrange(10) for _ in range(8)];s.high[:]=list(s.digits) if case%2 else [rng.randrange(10)for _ in range(8)]
  s.queue[:]=[rng.randrange(256) for _ in range(16)];s.read=rng.randrange(16);s.write=rng.randrange(16);s.next_life=rng.randrange(12)
  table=(C.c_uint8*80)(*[rng.randrange(10)for _ in range(80)]);count=case%11;seed=C.c_uint16(rng.randrange(65536));lives=C.c_uint8(rng.randrange(256));original_seed=seed.value;initial_lives=lives.value
  before=Score.from_buffer_copy(s);e=libs[0].bc_score_step_extends(C.byref(before),C.byref(seed),C.byref(lives),table,count)
  for skip in [False,True]:
   after=Score.from_buffer_copy(s);new_seed=C.c_uint16(original_seed);new_lives=C.c_uint8(initial_lives)
   actual=libs[1].bc_score_step_extends(C.byref(after),None if skip else C.byref(new_seed),C.byref(new_lives),table,count)
   assert bytes(before)==bytes(after) and bytes(e)==bytes(actual) and lives.value==new_lives.value,(case,skip)
   assert new_seed.value==(original_seed if skip else seed.value)
 print('PASS: 32768 score states, both leader and peer paths; queues, score/high score, extends, life wrap, events and leader RNG match baseline')
