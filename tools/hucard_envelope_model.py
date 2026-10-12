"""Development model of the HuCard envelope and modulation, $46AF-$480A."""
from hucard_score_model import Score

class EnvelopeScore(Score):
    instrument_address=0x4a57
    def step(self,channel,c):
        if c[0] or c[1]:self.instrument(c)
        super().step(channel,c)
    def instrument_on(self,channel,c):self.instrument(c)
    def instrument(self,c):
        if c[16]:self.instrument_address=self.read(0x4a01)+256*self.read(0x4a02)+(c[16]-1)*40
        base=self.instrument_address
        return [self.read(base+i) for i in range(40)]
    def gate_off(self,channel,c):c[17]=(c[17]&248)|3
    def note_on(self,channel,c,tied,changed):
        if not tied:c[18]=0;c[17]&=224
        if changed or (self.instrument(c)[36]&128 and not tied):
            c[19]=0;c[22]=255;c[17]&=7
    def hold(self,channel,c):
        ins=self.instrument(c);phase=c[17]&7;level=c[18]
        if phase==4:return
        advance=False
        if phase==0:
            level+=self.read(0x4259+ins[32])
            if level>=248:level=248;advance=True
        elif phase==1:
            step=self.read(0x4259+ins[33]);level-=step
            if not ins[33] or level<ins[34]:level=ins[34];advance=True
        elif phase==3 and ins[35]:
            level-=self.read(0x4259+ins[35])
            if level<0:level=0;advance=True
        c[18]=level
        if advance:c[17]=(c[17]+1)&255
        def signed(v):return v if v<128 else v-256
        delta=signed(c[10])
        if ins[37]:delta+=signed((-ins[37])&255 if c[17]&64 else ins[37])
        period=(c[20]+256*c[21]+delta)&65535;c[20]=period&255;c[21]=period>>8
        if ins[38]:c[22]=max(0,c[22]-ins[38]) if c[17]&32 else min(255,c[22]+ins[38])
        c[19]=(c[19]+1)&255
        if c[19]==(ins[36]&127):
            c[19]=0;c[17]^=128
            if c[17]&128:c[17]^=64
            c[17]^=32
