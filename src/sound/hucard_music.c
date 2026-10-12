#include "hucard_music.h"

/* HuCard source: stage callbacks $92E5-$9309 (ROM bank 1), regular bosses
 * $71A7/$71B4/$71C3 and wheel $7819 (bank 5), clear $7E50, game over $EC94,
 * opening $F155 and credits $EDB7 (bank 0). See docs/hucard-soundtrack.md. */
signed char hucard_music_track(unsigned char command)
{
    static const signed char tracks[25] = {
        0x11, 0x05, 0x04, 0x02, 0x03, 0x01, 0x06, 0x07, 0x08, 0x0e,
        0x0a, -1, 0x0f, -1, 0x0b, -1, -1, -1,
        0x12, 0x0e, 0x0c, 0x0d, 0x10, -1, -1
    };
    /* BC's finite gallery presentation retains its own stop timer. */
    if (command == 0xfe) return 0x0f;
    return command >= 0x20 && command <= 0x38 ? tracks[command - 0x20] : -1;
}
