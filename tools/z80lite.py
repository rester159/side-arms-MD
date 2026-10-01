"""Small Z80 interpreter used by the RE extractors (development-only).

Purpose: execute short, side-effect-only ROM routines (enemy spawn routines, table setup) against a
sparse RAM model so their *effects* (object records written, task spawns, sound requests) can be
recorded without hand-decoding every per-family parameter table. It is not cycle-accurate and only
implements the documented instruction set needed by the Side Arms main program (flags S Z H? P/V C,
H/N approximated). Unknown opcodes raise Unsupported.
"""


class Unsupported(Exception):
    pass


class Stop(Exception):
    pass


def _parity(v):
    v &= 0xFF
    v ^= v >> 4; v ^= v >> 2; v ^= v >> 1
    return (v & 1) == 0


class Z80:
    def __init__(self, read_rom, hooks=None):
        """read_rom(addr) -> byte for $0000-$BFFF (caller resolves banking).
        hooks: {addr: fn(cpu) -> None}; called *instead of* executing a CALL/JP target; the hook must
        emulate the routine (typically just cpu.ret())."""
        self.read_rom = read_rom
        self.ram = {}
        self.hooks = hooks or {}
        self.a = self.f = self.b = self.c = self.d = self.e = self.h = self.l = 0
        self.a_ = self.f_ = self.b_ = self.c_ = self.d_ = self.e_ = self.h_ = self.l_ = 0
        self.ix = self.iy = 0
        self.sp = 0xEE00
        self.pc = 0
        self.writes = []          # (addr, value) log of RAM writes
        self.copies = []          # (src, dst, len) of every LDIR
        self.steps = 0

    # ---- memory
    def rb(self, a):
        a &= 0xFFFF
        if a < 0xC000:
            return self.read_rom(a)
        return self.ram.get(a, 0)

    def wb(self, a, v):
        a &= 0xFFFF; v &= 0xFF
        if a < 0xC000:
            return  # ROM write ignored (bank latch etc. not modelled)
        self.ram[a] = v
        self.writes.append((a, v))

    def rw(self, a):
        return self.rb(a) | (self.rb(a + 1) << 8)

    def ww(self, a, v):
        self.wb(a, v & 0xFF); self.wb(a + 1, v >> 8)

    def fetch(self):
        v = self.rb(self.pc); self.pc = (self.pc + 1) & 0xFFFF; return v

    def fetchw(self):
        v = self.rw(self.pc); self.pc = (self.pc + 2) & 0xFFFF; return v

    def push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF; self.ww(self.sp, v)

    def pop(self):
        v = self.rw(self.sp); self.sp = (self.sp + 2) & 0xFFFF; return v

    def ret(self):
        self.pc = self.pop()

    # ---- register pairs
    @property
    def hl(self): return (self.h << 8) | self.l
    @hl.setter
    def hl(self, v): self.h = (v >> 8) & 0xFF; self.l = v & 0xFF
    @property
    def de(self): return (self.d << 8) | self.e
    @de.setter
    def de(self, v): self.d = (v >> 8) & 0xFF; self.e = v & 0xFF
    @property
    def bc(self): return (self.b << 8) | self.c
    @bc.setter
    def bc(self, v): self.b = (v >> 8) & 0xFF; self.c = v & 0xFF
    @property
    def af(self): return (self.a << 8) | self.f
    @af.setter
    def af(self, v): self.a = (v >> 8) & 0xFF; self.f = v & 0xFF

    # flags: S=80 Z=40 H=10 PV=04 N=02 C=01
    def _szp(self, v, c=None):
        v &= 0xFF
        f = (v & 0x80) | (0x40 if v == 0 else 0) | (0x04 if _parity(v) else 0)
        if c is not None:
            f |= 1 if c else 0
        else:
            f |= self.f & 1
        self.f = f

    def _add(self, v, carry=0):
        r = self.a + v + carry
        ov = (~(self.a ^ v) & (self.a ^ r) & 0x80) != 0
        self.f = (r & 0x80) | (0x40 if (r & 0xFF) == 0 else 0) | (0x04 if ov else 0) | (1 if r > 0xFF else 0)
        self.a = r & 0xFF

    def _sub(self, v, carry=0, store=True):
        r = self.a - v - carry
        ov = ((self.a ^ v) & (self.a ^ r) & 0x80) != 0
        f = (r & 0x80) | (0x40 if (r & 0xFF) == 0 else 0) | (0x04 if ov else 0) | 0x02 | (1 if r < 0 else 0)
        self.f = f
        if store:
            self.a = r & 0xFF

    def cond(self, n):
        f = self.f
        return [not f & 0x40, bool(f & 0x40), not f & 1, bool(f & 1),
                not f & 4, bool(f & 4), not f & 0x80, bool(f & 0x80)][n]

    # ---- 8-bit register access by index (0..7 = b c d e h l (hl) a)
    def getr(self, i, idx=None, d=0):
        if i == 0: return self.b
        if i == 1: return self.c
        if i == 2: return self.d
        if i == 3: return self.e
        if i == 4: return self.h if idx is None else (getattr(self, idx) >> 8)
        if i == 5: return self.l if idx is None else (getattr(self, idx) & 0xFF)
        if i == 6: return self.rb((self.hl if idx is None else getattr(self, idx) + d) & 0xFFFF)
        return self.a

    def setr(self, i, v, idx=None, d=0):
        v &= 0xFF
        if i == 0: self.b = v
        elif i == 1: self.c = v
        elif i == 2: self.d = v
        elif i == 3: self.e = v
        elif i == 4:
            if idx is None: self.h = v
            else: setattr(self, idx, (getattr(self, idx) & 0xFF) | (v << 8))
        elif i == 5:
            if idx is None: self.l = v
            else: setattr(self, idx, (getattr(self, idx) & 0xFF00) | v)
        elif i == 6: self.wb((self.hl if idx is None else getattr(self, idx) + d) & 0xFFFF, v)
        else: self.a = v

    def get_rp(self, n, idx=None, af=False):
        if n == 0: return self.bc
        if n == 1: return self.de
        if n == 2: return self.hl if idx is None else getattr(self, idx)
        return self.af if af else self.sp

    def set_rp(self, n, v, idx=None, af=False):
        v &= 0xFFFF
        if n == 0: self.bc = v
        elif n == 1: self.de = v
        elif n == 2:
            if idx is None: self.hl = v
            else: setattr(self, idx, v)
        else:
            if af: self.af = v
            else: self.sp = v

    def alu(self, op, v):
        if op == 0: self._add(v)
        elif op == 1: self._add(v, self.f & 1)
        elif op == 2: self._sub(v)
        elif op == 3: self._sub(v, self.f & 1)
        elif op == 4: self.a &= v; self._szp(self.a, 0); self.f |= 0x10
        elif op == 5: self.a ^= v; self.a &= 0xFF; self._szp(self.a, 0)
        elif op == 6: self.a |= v; self.a &= 0xFF; self._szp(self.a, 0)
        else: self._sub(v, store=False)

    def rot(self, op, v):
        c = self.f & 1
        if op == 0: r = ((v << 1) | (v >> 7)) & 0xFF; nc = v >> 7
        elif op == 1: r = ((v >> 1) | (v << 7)) & 0xFF; nc = v & 1
        elif op == 2: r = ((v << 1) | c) & 0xFF; nc = v >> 7
        elif op == 3: r = ((v >> 1) | (c << 7)) & 0xFF; nc = v & 1
        elif op == 4: r = (v << 1) & 0xFF; nc = v >> 7
        elif op == 5: r = (v >> 1) | (v & 0x80); nc = v & 1
        elif op == 6: r = ((v << 1) | 1) & 0xFF; nc = v >> 7
        else: r = v >> 1; nc = v & 1
        self._szp(r, nc)
        return r

    # ---- execution
    def call(self, addr, ret_to=0xFFFF):
        """Call addr; returns when the routine returns to ret_to (sentinel)."""
        self.push(ret_to)
        self.pc = addr
        self.run(until=ret_to)

    def run(self, until, max_steps=20000):
        while self.pc != until:
            if self.pc in self.hooks:
                self.hooks[self.pc](self)
                continue
            self.step()
            self.steps += 1
            if self.steps > max_steps:
                raise Unsupported('step limit at %04X' % self.pc)

    def step(self):
        pc0 = self.pc
        op = self.fetch()
        idx = None
        if op in (0xDD, 0xFD):
            idx = 'ix' if op == 0xDD else 'iy'
            op = self.fetch()
            if op == 0xCB:
                d = self.fetch(); d = d - 256 if d > 127 else d
                o2 = self.fetch()
                a = (getattr(self, idx) + d) & 0xFFFF
                self._cb(o2, a)
                return
        x, y, z = op >> 6, (op >> 3) & 7, op & 7
        p, q = y >> 1, y & 1

        def disp():
            d = self.fetch(); return d - 256 if d > 127 else d

        if op == 0xCB:
            self._cb(self.fetch(), None); return
        if op == 0xED:
            self._ed(self.fetch()); return
        if x == 1:
            if op == 0x76: raise Stop('halt')
            if idx and (y == 6 or z == 6):
                d = disp()
                if y == 6: self.setr(6, self.getr(z), idx, d)
                else: self.setr(y, self.getr(6, idx, d))
            else:
                self.setr(y, self.getr(z, idx), idx)
            return
        if x == 2:
            d = disp() if (idx and z == 6) else 0
            self.alu(y, self.getr(z, idx, d)); return
        if x == 0:
            if z == 0:
                if y == 0: return
                if y == 1: self.af, self.a_, self.f_ = (self.a_ << 8) | self.f_, self.a, self.f; return
                if y == 2:
                    d = disp(); self.b = (self.b - 1) & 0xFF
                    if self.b: self.pc = (self.pc + d) & 0xFFFF
                    return
                d = disp()
                if y == 3 or self.cond(y - 4): self.pc = (self.pc + d) & 0xFFFF
                return
            if z == 1:
                if q == 0: self.set_rp(p, self.fetchw(), idx)
                else:
                    r = self.get_rp(2, idx) + self.get_rp(p, idx)
                    self.f = (self.f & 0xFE) | (1 if r > 0xFFFF else 0)
                    self.set_rp(2, r, idx)
                return
            if z == 2:
                if p == 0: (self.wb(self.bc, self.a) if q == 0 else setattr(self, 'a', self.rb(self.bc)))
                elif p == 1: (self.wb(self.de, self.a) if q == 0 else setattr(self, 'a', self.rb(self.de)))
                elif p == 2:
                    nn = self.fetchw()
                    if q == 0: self.ww(nn, self.get_rp(2, idx))
                    else: self.set_rp(2, self.rw(nn), idx)
                else:
                    nn = self.fetchw()
                    if q == 0: self.wb(nn, self.a)
                    else: self.a = self.rb(nn)
                return
            if z == 3:
                v = self.get_rp(p, idx) + (1 if q == 0 else -1)
                self.set_rp(p, v, idx); return
            if z in (4, 5):
                d = disp() if (idx and y == 6) else 0
                v = self.getr(y, idx, d)
                r = (v + (1 if z == 4 else -1)) & 0xFF
                c = self.f & 1
                self._szp(r, c)
                if z == 5: self.f |= 2
                self.setr(y, r, idx, d); return
            if z == 6:
                d = disp() if (idx and y == 6) else 0
                self.setr(y, self.fetch(), idx, d); return
            if z == 7:
                a = self.a; c = self.f & 1
                if y == 0: self.a = ((a << 1) | (a >> 7)) & 0xFF; self.f = (self.f & 0xC4) | (a >> 7)
                elif y == 1: self.a = ((a >> 1) | (a << 7)) & 0xFF; self.f = (self.f & 0xC4) | (a & 1)
                elif y == 2: self.a = ((a << 1) | c) & 0xFF; self.f = (self.f & 0xC4) | (a >> 7)
                elif y == 3: self.a = ((a >> 1) | (c << 7)) & 0xFF; self.f = (self.f & 0xC4) | (a & 1)
                elif y == 5: self.a = (~a) & 0xFF; self.f |= 0x12
                elif y == 6: self.f = (self.f & 0xC4) | 1
                elif y == 7: self.f = (self.f & 0xC4) | (0 if c else 1)
                else: raise Unsupported('daa at %04X' % pc0)
                return
        if x == 3:
            if z == 0:
                if self.cond(y): self.ret()
                return
            if z == 1:
                if q == 0:
                    self.set_rp(p, self.pop(), idx, af=True); return
                if p == 0: self.ret(); return
                if p == 1:
                    for r in 'bcdehl':
                        v = getattr(self, r); setattr(self, r, getattr(self, r + '_')); setattr(self, r + '_', v)
                    return
                if p == 2: self.pc = self.get_rp(2, idx); return
                self.sp = self.get_rp(2, idx); return
            if z == 2:
                nn = self.fetchw()
                if self.cond(y): self.pc = nn
                return
            if z == 3:
                if y == 0: self.pc = self.fetchw(); return
                if y in (6, 7): return          # di / ei
                if y == 4:
                    v = self.rw(self.sp); self.ww(self.sp, self.get_rp(2, idx)); self.set_rp(2, v, idx); return
                if y == 5:
                    self.de, self.hl = self.hl, self.de; return
                raise Unsupported('io at %04X' % pc0)
            if z == 4:
                nn = self.fetchw()
                if self.cond(y): self.push(self.pc); self.pc = nn
                return
            if z == 5:
                if q == 0: self.push(self.get_rp(p, idx, af=True)); return
                if p == 0: nn = self.fetchw(); self.push(self.pc); self.pc = nn; return
            if z == 6:
                self.alu(y, self.fetch()); return
            if z == 7:
                self.push(self.pc); self.pc = y * 8; return
        raise Unsupported('op %02X at %04X' % (op, pc0))

    def _cb(self, o, addr):
        x, y, z = o >> 6, (o >> 3) & 7, o & 7
        v = self.rb(addr) if addr is not None else self.getr(z)
        if x == 0:
            r = self.rot(y, v)
        elif x == 1:
            self.f = (self.f & 1) | 0x10 | (0 if v & (1 << y) else 0x44); return
        elif x == 2:
            r = v & ~(1 << y)
        else:
            r = v | (1 << y)
        if addr is not None: self.wb(addr, r)
        else: self.setr(z, r)

    def _ed(self, o):
        if o == 0xB0:  # ldir
            self.copies.append((self.hl, self.de, self.bc))
            while True:
                self.wb(self.de, self.rb(self.hl))
                self.hl = self.hl + 1; self.de = self.de + 1; self.bc = self.bc - 1
                if self.bc == 0: break
            self.f &= ~0x04; return
        if o == 0x44:
            v = self.a; self.a = 0; self._sub(v); return
        if o in (0x43, 0x53, 0x63, 0x73):
            self.ww(self.fetchw(), self.get_rp((o >> 4) & 3)); return
        if o in (0x4B, 0x5B, 0x6B, 0x7B):
            self.set_rp((o >> 4) & 3, self.rw(self.fetchw())); return
        if o in (0x42, 0x52, 0x62, 0x72):
            r = self.hl - self.get_rp((o >> 4) & 3) - (self.f & 1)
            self.f = (0x40 if (r & 0xFFFF) == 0 else 0) | ((r >> 8) & 0x80) | 2 | (1 if r < 0 else 0)
            self.hl = r & 0xFFFF; return
        if o in (0x4A, 0x5A, 0x6A, 0x7A):
            r = self.hl + self.get_rp((o >> 4) & 3) + (self.f & 1)
            self.f = (0x40 if (r & 0xFFFF) == 0 else 0) | ((r >> 8) & 0x80) | (1 if r > 0xFFFF else 0)
            self.hl = r & 0xFFFF; return
        if o in (0x56, 0x5E, 0x46):
            return  # im
        raise Unsupported('ED %02X at %04X' % (o, self.pc - 2))
