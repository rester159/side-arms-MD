"""Structured, development-only HuCard score timing model.
Models score semantics decoded at $4383-$46AE; not a CPU emulator and not linked.
"""
from dataclasses import dataclass,field

@dataclass
class Score:
    rom:bytes
    channels:list
    phase:int=0
    clock:int=0
    tempo:int=0
    transpose:int=0
    events:list=field(default_factory=list)
    step_number:int=0
    envelope_allowed:bool=True

    def read(self,address):
        assert 0x4000<=address<0x8000,hex(address)
        return self.rom[0x10000+address-0x4000]
    def byte(self,c):
        pc=c[0]+256*c[1];value=self.read(pc);pc+=1;c[0]=pc&255;c[1]=pc>>8
        return value
    def jump(self,c,address):c[0]=address&255;c[1]=address>>8
    def tick(self):
        self.phase=(self.phase+self.tempo)&65535
        iterations=0
        while self.clock!=self.phase>>8:
            self.clock=(self.clock+1)&255;self.step_number+=1
            self.envelope_allowed=iterations==0
            for channel,c in enumerate(self.channels):self.step(channel,c)
            iterations+=1;assert iterations<256
    def step(self,channel,c):
        if not(c[0]or c[1]):return
        if c[2]>1:
            c[2]-=1
            if c[3]:
                c[3]-=1
                if not c[3] and not c[5]&4:self.gate_off(channel,c)
            if self.envelope_allowed:self.hold(channel,c)
            return
        for _ in range(1000):
            pc=c[0]+256*c[1];op=self.byte(c)
            if op>=31:
                length=(2 if c[5]&8 else 3)*(1<<((op>>5)-1))
                if c[5]&1:
                    if (op>>5)>1:length+=length//2
                    c[5]&=~1
                c[2]=length&255;c[3]=max(2,(length*c[4])>>8)
                pitch=op&31
                if not pitch:
                    c[3]=1;self.events.append((self.step_number,channel,pc,'rest',c[2]));return
                previous_tie=c[5]&4
                c[5]=(c[5]|4) if c[5]&2 else (c[5]&~4)
                if not previous_tie:
                    note=(pitch-1+(c[7]&127)+(24 if c[7]&128 else 0)+self.transpose+c[8])&255
                    address=0x4279+((note*2)&255)
                    period=(self.read(address)+256*self.read(address+1)+(c[9] if c[9]<128 else c[9]-256))&65535
                    c[20]=(period*4)&255;c[21]=(period*4>>8)&255
                self.note_on(channel,c,bool(previous_tie),bool(c[5]&16))
                c[5]&=~16
                self.events.append((self.step_number,channel,pc,'note',c[2],(c[20]+256*c[21])>>2,c[16],c[6],c[15],bool(previous_tie)))
                return
            if op==0:
                self.tempo=0x3000//self.byte(c);self.phase=0;self.clock=0
            elif op==1:c[4]=self.byte(c)
            elif op==2:c[6]=((self.byte(c)&31)-31)&255
            elif op==3:
                instrument=self.byte(c)+1
                if instrument!=c[16]:
                    c[16]=instrument;c[5]|=16;self.instrument_on(channel,c)
            elif op==4:c[5]^=8
            elif op==5:c[5]^=2
            elif op==6:c[5]|=1
            elif op==7:c[7]=(c[7]&128)|self.byte(c)
            elif op==8:c[7]|=128
            elif op==9:c[7]&=127
            elif op==10:self.transpose=self.byte(c)
            elif op==11:c[8]=self.byte(c)
            elif op==12:c[9]=self.byte(c)
            elif op==13:c[10]=self.byte(c)
            elif 14<=op<=17:
                slot=op-14+11;count=self.byte(c);lo=self.byte(c);hi=self.byte(c)
                if c[slot]:c[slot]=(c[slot]-1)&255
                else:c[slot]=count
                if c[slot]:self.jump(c,lo+256*hi)
            elif 18<=op<=21:
                slot=op-18+11;lo=self.byte(c);hi=self.byte(c)
                if c[slot]==1:c[slot]=0;self.jump(c,lo+256*hi)
            elif op==22:
                lo=self.byte(c);hi=self.byte(c);self.jump(c,lo+256*hi)
            elif op==23:self.jump(c,0);self.end(channel,c);return
            elif op==24:c[5]^=128
            elif op==25:c[15]=self.byte(c)
            else:raise AssertionError((hex(pc),op))
        raise AssertionError('Score control loop without a note')

    def gate_off(self,channel,c):pass
    def hold(self,channel,c):pass
    def note_on(self,channel,c,tied,changed):pass
    def instrument_on(self,channel,c):pass
    def end(self,channel,c):pass
