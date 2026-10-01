#!/usr/bin/env python3
"""Reference model of the port's SSG -> PSG reduction (src/sound/sa_sound_drv.s80, `psgmap`), used by
tools/sound_test.py to turn the arcade's logged SSG register images into the PSG state the driver must
produce. Any change to psgmap must be mirrored here (and vice versa)."""

# SSG volume 0..15 -> PSG attenuation: 0 -> off, else min(14, round((15 - v) * 1.5))
ATT = [15, 14, 14, 14, 14, 14, 14, 12, 11, 9, 8, 6, 5, 3, 2, 0]
PSG_MUL = {'ntsc': 27, 'pal': 29}     # N = TP - round(TP * mul / 256): x0.8945 / x0.8867
NOISE_T3_BELOW = 13                   # NP < 13: noise clocked by tone 3 (when it wins tone 3)
NOISE_512_BELOW = 26                  # 13 <= NP < 26: /512, else /1024


def tpn(tp, mul):
    tp = tp or 1
    n = tp - ((tp * mul + 128) >> 8)
    while n > 1023:
        n = (n + 1) >> 1
    return n or 1


class PSGState:
    def __init__(self):
        self.n = [0, 0, 0]
        self.att = [15, 15, 15, 15]
        self.nctl = None

    def audible(self):
        """Comparable state: what can be heard."""
        out = []
        for k in range(3):
            out.append((self.att[k], self.n[k] if self.att[k] < 15 else None))
        noise = (self.att[3], self.nctl if self.att[3] < 15 else None,
                 self.n[2] if self.att[3] < 15 and self.nctl == 0xE7 else None)
        return tuple(out) + (noise,)


def reduce(img1, img2, st, region='ntsc'):
    """img1/img2: 11 SSG register values (regs 0-10) the arcade chip 1/2 receive this tick."""
    mul = PSG_MUL[region]
    voices = []
    for img in (img2, img1):
        mix = img[7]
        for j in range(3):
            vol = 0 if mix >> j & 1 else img[8 + j] & 15
            voices.append([vol, img[2 * j] | (img[2 * j + 1] & 15) << 8])

    def nvol(img):
        return max([img[8 + j] & 15 for j in range(3) if not img[7] >> (3 + j) & 1], default=0)
    n2, n1 = nvol(img2), nvol(img1)
    nv, np_ = (n2, img2[6] & 31) if n2 >= n1 else (n1, img1[6] & 31)
    vols = [v[0] for v in voices]
    picks = []
    for _ in range(3):
        best, bv = -1, 0
        for i, v in enumerate(vols):
            if v > bv:
                best, bv = i, v
        picks.append([best, bv])
        if best >= 0:
            vols[best] = 0
    t3 = False
    if nv:
        if np_ >= NOISE_T3_BELOW:
            st.nctl = 0xE4 if np_ < NOISE_512_BELOW else 0xE5
        elif picks[2][1] == 0 or nv >= picks[2][1]:
            t3 = True; picks[2][0] = -1; st.nctl = 0xE7
        else:
            st.nctl = 0xE4
    for k in range(3):
        idx, v = picks[k]
        if idx >= 0:
            st.n[k] = tpn(voices[idx][1], mul); st.att[k] = ATT[v]
        else:
            st.att[k] = 15
    if t3:
        st.n[2] = tpn(np_, mul)
    st.att[3] = ATT[nv]
    return st


def psg_apply(st, byte, latch):
    """SN76489 write protocol; returns the new latch (channel, is_volume)."""
    if byte & 0x80:
        ch, vol = byte >> 5 & 3, byte >> 4 & 1
        if vol:
            st.att[ch] = byte & 15
        elif ch == 3:
            st.nctl = byte
        else:
            st.n[ch] = (st.n[ch] & 0x3F0) | (byte & 15)
        return (ch, vol)
    ch, vol = latch
    if not vol and ch < 3:
        st.n[ch] = (st.n[ch] & 15) | (byte & 0x3F) << 4
    return latch
