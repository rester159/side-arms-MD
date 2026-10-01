#include <genesis.h>
#include "game.h"

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

int main(bool hardReset)
{
    (void)hardReset;
    JOY_init();
    if (boot_intros) boot_intros();
    video_init();
    if (sound_init) sound_init();
    game_init();
    for (;;) {
        u32 vt0 = vtimer;
        u16 s0 = since(vt0);
        input_update();
        game_update();
        u16 s1 = since(vt0);
        game_draw();
        u16 s2 = since(vt0);
        video_frame();
        prof_seg[3] = since(vt0);
        prof_seg[0] = s0; prof_seg[1] = s1; prof_seg[2] = s2;
        prof_line = GET_VCOUNTER;
        frame_counter++;
        SYS_doVBlankProcess();
    }
    return 0;
}
