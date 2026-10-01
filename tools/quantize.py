"""Palette fitting for Genesis: blocks (8x8 tiles / whole arcade palettes) share K
palettes of 15 colours; each block uses exactly one palette.

Colours are handled in Genesis 3-bit-per-channel space (0..7)."""
import numpy as np

W = np.array([3.0, 4.0, 2.0])  # rough perceptual channel weights


def to_md(rgb444):
    """arcade 4-bit channels (0..15) -> Genesis 3-bit (0..7), rounded."""
    return tuple(int(round(c * 7 / 15)) for c in rgb444)


def md_word(c):
    r, g, b = c
    return (b << 9) | (g << 5) | (r << 1)


def _dist(a, b):
    d = (np.asarray(a, float)[:, None, :] - np.asarray(b, float)[None, :, :]) * W
    return (d * d).sum(-1)


def kmeans_colors(colors, weights, k, iters=12):
    colors = np.asarray(colors, float); weights = np.asarray(weights, float)
    if len(colors) <= k:
        return [tuple(int(v) for v in c) for c in colors]
    # init: k-means++ style deterministic (heaviest, then farthest)
    centers = [colors[np.argmax(weights)]]
    for _ in range(k - 1):
        d = _dist(colors, np.array(centers)).min(1) * weights
        centers.append(colors[np.argmax(d)])
    centers = np.array(centers)
    for _ in range(iters):
        lab = _dist(colors, centers).argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                centers[j] = (colors[m] * weights[m, None]).sum(0) / weights[m].sum()
    out = sorted({tuple(int(round(v)) for v in c) for c in np.clip(centers, 0, 7)})
    return out


def fit(blocks, k, ncol=15, iters=6, fixed=None):
    """blocks: list of dict colour(md tuple)->pixel count. Returns (palettes, assignment).
    fixed: optional list of colour lists pre-seeded into palettes (kept)."""
    allc = {}
    for b in blocks:
        for c, n in b.items():
            allc[c] = allc.get(c, 0) + n
    # initial split: k-means on block mean colour
    means = np.array([np.average(np.array(list(b)), axis=0, weights=list(b.values())) if b else np.zeros(3) for b in blocks])
    wts = np.array([sum(b.values()) for b in blocks], float) + 1e-6
    if k == 1:
        assign = np.zeros(len(blocks), int)
    else:
        c0 = kmeans_colors(means, wts, k)
        while len(c0) < k:
            c0.append(c0[-1])
        assign = _dist(means, np.array(c0)).argmin(1)
    pals = None
    for _ in range(iters):
        pals = []
        for j in range(k):
            acc = {}
            for b, a in zip(blocks, assign):
                if a == j:
                    for c, n in b.items():
                        acc[c] = acc.get(c, 0) + n
            if not acc:
                acc = allc
            seed = list(fixed[j]) if fixed and j < len(fixed) else []
            free = ncol - len(seed)
            cl = list(acc); wl = [acc[c] for c in cl]
            pal = seed + [c for c in kmeans_colors(cl, wl, free) if c not in seed]
            pals.append(pal[:ncol])
        # reassign by total error
        new = []
        for b in blocks:
            if not b:
                new.append(0); continue
            cs = np.array(list(b)); ns = np.array(list(b.values()), float)
            errs = [(_dist(cs, np.array(p)).min(1) * ns).sum() for p in pals]
            new.append(int(np.argmin(errs)))
        new = np.array(new)
        if (new == assign).all():
            break
        assign = new
    return pals, assign


def nearest(color, pal):
    return int(_dist([color], np.array(pal)).argmin(1)[0])
