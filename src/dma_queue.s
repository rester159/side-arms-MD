/* Keep SGDK's memory-to-word DMA trigger, but make its two-word command
 * atomic. An H-int window-register write between the words is interpreted
 * as the DMA command's second half, corrupting destination and length.
 * d0/d1/a0/a1 are caller-saved under the 68000 ABI. */
#include "asm_mac.i"

func flushQueue
    move.b #1,cave_dma_busy
    move.w 6(%sp),%d0
    jeq .fq_atomic_end
    move.l dmaQueues,%a0
    move.l #0xC00004,%a1
    subq.w #1,%d0
.fq_atomic_loop:
    move.l (%a0)+,(%a1)
    move.l (%a0)+,(%a1)
    move.l (%a0)+,(%a1)
    move.w %sr,%d1
    ori.w #0x0700,%sr
    move.w (%a0)+,(%a1)
    move.w (%a0)+,(%a1)
    move.w %d1,%sr
    dbra %d0,.fq_atomic_loop
.fq_atomic_end:
    clr.b cave_dma_busy
    rts
