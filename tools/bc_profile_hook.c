/* Host-side 68000 instruction attribution for the hash-pinned test core.
   Internal offsets are guarded by profile_bc_cpu.py before installation. */
#include <stdint.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
typedef void (*Handler)(void);
static Handler original[65536],*dispatch;
static uint8_t *cpu,*base_cycles;
uint64_t instruction_cycles[0x200000],instruction_counts[0x200000],phase_cycles[256];
static volatile uint8_t *phase_lo;   /* host address of the low byte of dbg_phase (optional) */
static uint32_t watch_pc[64];
static unsigned watch_count;
static void (*watch_callback)(void);
int profile_watch(const uint32_t *pcs,unsigned count,void (*callback)(void)){
 if(count>64)return -1;
 memcpy(watch_pc,pcs,count*sizeof(*pcs));watch_count=count;watch_callback=callback;
 return 0;
}
static int only_mask=-1;   /* bit per phase counted in instruction_cycles (-1 = all) */
void profile_only(int m){only_mask=m;}
void profile_phase(void *p){phase_lo=p;memset(phase_cycles,0,sizeof phase_cycles);}
static uint32_t word(unsigned offset){return *(uint32_t*)(cpu+offset);}
/* Optional bounded instruction trace for one scheduler call. These reads
 * change no emulated state or cycle accounting. Register IDs follow the
 * pinned core's m68k_get_reg API (D0..D7, A0..A7). */
typedef struct { uint32_t pc,clock,scanline,reg[16]; } TraceRow;
TraceRow instruction_trace[8192];
unsigned instruction_trace_count, instruction_trace_overflow;
static int tracing;
static uint16_t *trace_scanline;
static uint32_t (*trace_register)(unsigned);
void profile_trace(int enabled,void *counter,void *getter){
 tracing=enabled;
 if(enabled){instruction_trace_count=instruction_trace_overflow=0;
  trace_scanline=counter;trace_register=getter;}
}
static void sample(void){
 uint32_t pc=(word(0x2858)-2)&0xffffff,op=word(0x28b4),before=word(0x280c);
 if(watch_callback)for(unsigned i=0;i<watch_count;i++)if(pc==watch_pc[i]){watch_callback();break;}
 if(tracing){
  if(instruction_trace_count<8192){TraceRow *r=&instruction_trace[instruction_trace_count++];
   r->pc=pc;r->clock=before;r->scanline=*trace_scanline;
   for(unsigned i=0;i<16;i++)r->reg[i]=trace_register(i);
  }else instruction_trace_overflow=1;
 }
 original[op]();
 if(pc<0x400000){int64_t c=(int32_t)(word(0x280c)-before)+((int64_t)base_cycles[op]*word(0x29c8)>>20);if(!phase_lo||(only_mask>>(*phase_lo&31)&1)){instruction_cycles[pc>>1]+=c;instruction_counts[pc>>1]++;}if(phase_lo)phase_cycles[*phase_lo]+=c;}
}
int profile_begin(void *state,void *table,void *timing){
 cpu=state;dispatch=table;base_cycles=timing;watch_callback=0;watch_count=0;tracing=0;
 long pagesize=sysconf(_SC_PAGESIZE);uintptr_t start=(uintptr_t)table&~(pagesize-1);
 if(mprotect((void*)start,(uintptr_t)table+65536*sizeof(Handler)-start,PROT_READ|PROT_WRITE))return -1;
 memcpy(original,dispatch,sizeof original);
 memset(instruction_cycles,0,sizeof instruction_cycles);memset(instruction_counts,0,sizeof instruction_counts);
 for(unsigned i=0;i<65536;i++)dispatch[i]=sample;
 return 0;
}
void profile_end(void){tracing=0;memcpy(dispatch,original,sizeof original);}
