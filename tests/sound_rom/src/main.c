/* Sound test cartridge (tests/sound_rom). Jukebox: LEFT/RIGHT +-1, UP/DOWN +-16, A play,
 * B stop all, C stop SFX. Host hook for tools/sound_test.py: write commands to host_cmd[] and
 * the count to host_n; each frame the queue is sent through sound_command(). */
#include <genesis.h>
#include "sound.h"

volatile u8 host_cmd[16];
volatile u8 host_n;
volatile u32 frames;

static void show(u8 cmd)
{
    char s[40];
    sprintf(s, "SIDE ARMS SOUND TEST  CMD %02X", cmd);
    VDP_drawText(s, 2, 4);
    VDP_drawText("L/R +-1  U/D +-16  A PLAY", 2, 6);
    VDP_drawText("B STOP ALL  C STOP SFX", 2, 7);
}

int main(bool hard)
{
    (void)hard;
    JOY_init();
    sound_init();
    u8 cmd = 0x21;
    u16 prev = 0;
    show(cmd);
    for (;;) {
        u16 pad = JOY_readJoypad(JOY_1);
        u16 hit = pad & ~prev;
        prev = pad;
        if (hit & BUTTON_RIGHT) cmd = (cmd + 1) & 0x3F;
        if (hit & BUTTON_LEFT) cmd = (cmd - 1) & 0x3F;
        if (hit & BUTTON_UP) cmd = (cmd + 16) & 0x3F;
        if (hit & BUTTON_DOWN) cmd = (cmd - 16) & 0x3F;
        if (hit & (BUTTON_LEFT | BUTTON_RIGHT | BUTTON_UP | BUTTON_DOWN)) show(cmd);
        if (hit & BUTTON_A) sound_command(cmd);
        if (hit & BUTTON_B) sound_stop_all();
        if (hit & BUTTON_C) sound_command(SOUND_STOP_SFX);
        u8 n = host_n;
        if (n) {
            for (u8 i = 0; i < n && i < 16; i++) sound_command(host_cmd[i]);
            host_n = 0;
        }
        frames++;
        SYS_doVBlankProcess();
    }
    return 0;
}
