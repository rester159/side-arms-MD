/* Read-only host hook for the hash-pinned Genesis Plus GX test core. */
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
typedef void (*Handler)(void);
/* This core exports the one-argument API; 15=A7 and 16=PC. */
typedef uint32_t (*GetReg)(unsigned);
static Handler original[65536], *dispatch;
static GetReg get_reg;
static uint8_t *cpu, *ram;
static unsigned peer_address, tick_address, players, player_size;
uint32_t lowest_sp=0x1000000, lowest_pc, lowest_tick, minimum_gap=0xffffffff;
uint32_t gap_sp, gap_end, gap_pc, gap_tick, overlap_samples;
uint64_t samples;
static uint32_t logical_long(unsigned address) {
 uint32_t v=0; for(unsigned i=0;i<4;i++)v=(v<<8)|ram[((address+i)&65535)^1]; return v;
}
static void observe(uint32_t pc) {
 uint32_t sp=get_reg(15)&0xffffff;
 samples++;
 if(sp<lowest_sp){lowest_sp=sp;lowest_pc=pc;lowest_tick=logical_long(tick_address);}
 uint32_t peer=logical_long(peer_address)&0xffffff;
 if(players>1 && peer>=0xff0000){
  uint32_t end=peer+(players-1)*player_size;
  int32_t gap=(int32_t)sp-(int32_t)end;
  if(minimum_gap==0xffffffff || gap<(int32_t)minimum_gap){
   minimum_gap=(uint32_t)gap;gap_sp=sp;gap_end=end;gap_pc=pc;gap_tick=logical_long(tick_address);
  }
  if(gap<0)overlap_samples++;
 }
}
static void sample(void) {
 uint32_t pc=(*(uint32_t*)(cpu+0x2858)-2)&0xffffff, op=*(uint32_t*)(cpu+0x28b4);
 observe(pc);original[op]();observe(pc);
}
int stack_begin(void *state,void *table,void *reader,void *memory,
 unsigned peers,unsigned ticks,unsigned count,unsigned size) {
 lowest_sp=0x1000000;minimum_gap=0xffffffff;lowest_pc=lowest_tick=0;
 gap_sp=gap_end=gap_pc=gap_tick=overlap_samples=0;samples=0;
 cpu=state;dispatch=table;get_reg=reader;ram=memory;
 peer_address=peers;tick_address=ticks;players=count;player_size=size;
 long page=sysconf(_SC_PAGESIZE);uintptr_t start=(uintptr_t)table&~(page-1);
 if(mprotect((void*)start,(uintptr_t)table+65536*sizeof(Handler)-start,PROT_READ|PROT_WRITE))return -1;
 memcpy(original,dispatch,sizeof original);
 for(unsigned i=0;i<65536;i++)dispatch[i]=sample;
 return 0;
}
void stack_end(void){memcpy(dispatch,original,sizeof original);}
