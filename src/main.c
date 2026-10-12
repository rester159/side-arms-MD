#include <genesis.h>
#include "game.h"
#include "hud.h"
#include "sound.h"

volatile u32 frame_counter;
volatile u16 prof_line;        /* debug: scanline when the frame's work ended */
/* debug profile of the last completed loop, in scanlines from the VBlank interrupt (line 224):
 * [0] loop start (after the VBlank process: DMA queue flush), [1] after game_update,
 * [2] after game_draw, [3] after video_frame. A value >= 262 means the frame overran. */
volatile u16 prof_seg[4];
void sound_init(void) __attribute__((weak));
/* SEGA / CAPCOM boot intros: local-only kits in src/intro/ (gitignored, tools/fetch_intros.sh).
 * Absent in a clean clone, so the hook is weak. They expect to run right after SGDK's VDP init
 * and before the game's own video and sound setup. */
void boot_intros(void) __attribute__((weak));

/* lines since the VBlank interrupt that started frame vt0 (8-bit V counter, NTSC: 0-234 then
 * 229-255 for the last lines; read as line numbers, close enough for profiling) */
static u16 since(u32 vt0)
{
    u16 vc = GET_VCOUNTER;
    u16 rel = vc >= 224 ? vc - 224 : vc + 262 - 224;
    return (u16)(vtimer - vt0) * 262 + rel;
}

static inline void finish_frame(u32 vt0)
{
    /* The repeated NTSC counter values 229..234 can be six lines
     * later than their first occurrence. The smaller queue cap keeps
     * headroom for that later interpretation and transfer overhead. The
     * final six-counter window admits only one tiny transfer. */
    /* VInt can interrupt this decision and spend much of blank refilling
     * HuCard audio. Reject a sample spanning that interrupt; never admit
     * DMA with the scanline read before it. Exclude the interrupt's first
     * line too, so it cannot begin just after the final coherence check. */
    u32 sampled_vt = vtimer;
    u16 vc = GET_VCOUNTER;
    if (!IS_PAL_SYSTEM && sampled_vt != vt0 && vc >= 225 && vc <= 240 &&
        DMA_getQueueTransferSize() <= (vc <= 228 ? 2048 : vc <= 234 ? 1024 : 288) &&
        DMA_getQueueSize() <= (vc <= 228 ? 8 : vc <= 234 ? 4 : 1) &&
        vtimer == sampled_vt)
        SYS_doVBlankProcessEx(ON_VBLANK);
    else SYS_doVBlankProcess();
}

int main(bool hardReset)
{
    (void)hardReset;
    z80_idle();                 /* v1.4: replace the shifted SDK idle program immediately */
    JOY_init();
    if (boot_intros) boot_intros();
    z80_idle();                 /* Also protect builds using older private intro kits. */
    video_init();
    if (sound_init) sound_init();
    game_init();
    for (;;) {
        u32 vt0 = vtimer;
        u16 s0 = since(vt0);
        input_update();
        bool preview = game_frame(vt0, s0);
        frame_counter++;
        if (preview) SYS_doVBlankProcess();
        else finish_frame(vt0);
        hud_flush_done();      /* Both scheduling paths have completed their DMA flush. */
    }
    return 0;
}
