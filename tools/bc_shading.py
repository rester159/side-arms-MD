"""Shade-constrained palette transfer for existing Genesis sprite materials.
Independent nearest-color mapping is unsuitable: it merges entire shade ramps.
"""
import numpy as np

def luminance(rgb):
    return np.asarray(rgb) @ np.array([.299,.587,.114])

def material_groups(original, weights):
    # The source sprite palettes organize their material ramps in these pen
    # ranges. Grouping by hue splits green shadows from pale green highlights
    # and incorrectly joins a white exhaust tip to the metal body.
    return [[p for p in range(lo,hi) if weights[p] and max(original[p])>1]
            for lo,hi in ((1,6),(6,10),(10,15))]


def fit_shades(original, target, weights, palette, groups=None):
    original=np.asarray(original,float);target=np.asarray(target,float);colors=np.asarray(palette,float)
    ol=luminance(original);cl=luminance(colors)
    # Hue is a preference, not permission to erase contrast. Keep brightness
    # from the original geometry even where source pixel correspondence repeats.
    cost=((target[:,None,:]-colors[None,:,:])**2).sum(2)
    cost+=.5*(luminance(target)[:,None]-cl[None,:])**2
    tc=target-target.min(1)[:,None];pc=colors-colors.min(1)[:,None]
    tn=np.linalg.norm(tc,axis=1);pn=np.linalg.norm(pc,axis=1)
    hue=1-(tc @ pc.T)/np.maximum(tn[:,None]*pn[None,:],1)
    cost+=8*hue*(target.max(1)-target.min(1)>=2)[:,None]
    lut=cost.argmin(1);ramps=[]
    for pens in (groups if groups is not None else material_groups(original,weights)):
        pens=[p for p in pens if weights[p]]
        if not pens:continue
        levels=[]
        for pen in sorted(pens,key=lambda p:(ol[p],p)):
            if levels and abs(ol[pen]-ol[levels[-1][0]])<.20:levels[-1].append(pen)
            else:levels.append([pen])
        # Choose ordered distinct palette shades jointly. Dynamic programming
        # can retain a dark neutral shadow instead of making every pen blue.
        n=len(levels);dp=np.full((n,len(colors)),np.inf);prev=np.full(dp.shape,-1,int)
        for i,level in enumerate(levels):
            errors=(cost[level]*np.sqrt(weights[level,None])).sum(0)
            if i==0:dp[i]=errors
            else:
                for j in range(len(colors)):
                    allowed=np.flatnonzero(cl < cl[j]-.20)
                    if len(allowed):
                        k=int(allowed[np.argmin(dp[i-1,allowed])]);dp[i,j]=dp[i-1,k]+errors[j];prev[i,j]=k
        j=int(dp[-1].argmin());assert np.isfinite(dp[-1,j]),'Palette has insufficient ordered shades'
        for i in range(n-1,-1,-1):
            for pen in levels[i]:lut[pen]=j
            j=prev[i,j]
        ramps.append(dict(pens=levels,luminance=[float(cl[lut[level[0]]]) for level in levels]))
    # Preserve outline as opaque black, not the transparency index.
    for p in range(15):
        if max(original[p])<=1:lut[p]=int(((colors-original[p])**2).sum(1).argmin())
    total=float((cost[np.arange(15),lut]*np.sqrt(weights)).sum())
    return total,lut.tolist(),ramps
