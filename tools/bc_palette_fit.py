"""Offline palette fitting that keeps protected source colors and bank choices.

Free colors are selected from the actual source gamut, without averaging hues.
Sublinear pixel weights prevent common flat areas from consuming all shade slots.
"""
import numpy as np
from quantize import _dist,kmeans_colors

def fit(blocks,k,ncol=15,iters=12,fixed=None,pinned=None,weight_power=0.35):
 means=np.array([np.average(list(b),axis=0,weights=list(b.values()))if b else np.zeros(3)for b in blocks]);weights=np.array([sum(b.values())for b in blocks])+1e-6
 centers=kmeans_colors(means,weights,k);assign=_dist(means,centers).argmin(1)
 if pinned is None:pinned=np.full(len(blocks),-1,dtype=int)
 pinned=np.asarray(pinned);locked=pinned>=0;assign[locked]=pinned[locked]
 allc=sorted({c for b in blocks for c in b})
 assert fixed is not None and len(fixed)==k
 assert all(0<len(set(bank))<=ncol for bank in fixed)
 assert len(pinned)==len(blocks) and all(-1<=v<k for v in pinned)
 for iteration in range(iters):
  pals=[]
  for j in range(k):
   acc={c:0.0 for c in allc}
   for b,bank in zip(blocks,assign):
    if bank==j:
     for c,n in b.items():acc[c]+=n
   cl=[c for c in allc if acc[c]>0];wt=np.array([acc[c]**weight_power for c in cl]);seed=list(dict.fromkeys(fixed[j]));d=_dist(cl,cl);best=_dist(cl,seed).min(1)
   while len(seed)<ncol:
    gains=((best[:,None]-np.minimum(best[:,None],d))*wt[:,None]).sum(0)
    at=int(np.argmax(gains))
    if gains[at]<=0:break
    seed.append(cl[at]);best=np.minimum(best,d[:,at])
   pals.append(seed)
  new=[]
  for b in blocks:
   if not b:new.append(0);continue
   cs=list(b);ns=np.array(list(b.values()))**weight_power
   new.append(int(np.argmin([(_dist(cs,p).min(1)*ns).sum()for p in pals])))
  new=np.array(new);new[locked]=pinned[locked]
  if np.array_equal(assign,new):break
  assign=new
 return pals,assign
