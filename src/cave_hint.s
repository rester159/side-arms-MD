    .text
    .align 2
    .global cave_raster_hint
cave_raster_hint:
    tst.b cave_dma_busy
    bne.w 9f
    movem.l %d0-%d1/%a0,-(%sp)
    moveq #0,%d0
    move.b 0xc00008,%d0
    tst.b flush_guard
    bne.s 7f
    cmpi.w #-1,cave_hud_line
    beq.s 6f
    cmp.w cave_hud_line,%d0
    bcs.s 7f
    tst.w cave_hud_value
    beq.s 7f
    move.w cave_hud_value,0xc00004
    clr.w cave_hud_value
    bra.s 7f
6:
    move.w %d0,%d1
    andi.w #7,%d1
    cmpi.w #7,%d1
    bne.s 7f
    move.w %d0,%d1
    lsr.w #3,%d1
    addq.w #1,%d1
    cmpi.w #28,%d1
    bcs.s 8f
    moveq #0,%d1
8:
    add.w %d1,%d1
    lea cave_hud_words,%a0
    move.w (%a0,%d1.w),0xc00004
7:
    cmp.w cave_first,%d0
    bcs.w 2f
    cmp.w cave_last,%d0
    bhi.w 2f
    /* Most interrupts only inspect the HUD and palette interval. */
    movem.l %d2-%d5,-(%sp)
    move.w %sr,-(%sp)
    ori.w #0x0700,%sr
    tst.b cave_dma_busy
    bne.s 3f
    movea.l cave_event,%a0
    cmpa.l cave_end,%a0
    bcc.s 3f
    move.l (%a0)+,%d1
    move.w (%a0)+,%d2
    moveq #0x3f,%d4
    moveq #-91,%d5
4:
    move.b 0xc00009,%d3
    sub.b %d5,%d3
    cmp.b %d4,%d3
    bhi.s 4b
    move.l %d1,0xc00004
    move.w %d2,0xc00000
    move.l %a0,cave_event
    addq.w #1,cave_dbg_writes
3:
    move.w (%sp)+,%sr
    movem.l (%sp)+,%d2-%d5
2:
    movem.l (%sp)+,%d0-%d1/%a0
9:
    rte
