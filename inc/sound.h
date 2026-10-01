/* Side Arms MD - sound (native Genesis driver: YM2612 music, PSG SFX; see docs/sound_port.md).
 *
 * Command numbers are the arcade sound-latch values (docs/re/sound.md): $00 stop all,
 * $01-$1E SFX, $10/$16/$19/$1F stop SFX, $20-$38 music, $39-$3F stop music (only bits 0-5 are
 * used, like the arcade dispatch at a_04k $00B8; $FF is ignored).
 * The caller models the arcade latch (src/game.c): every call here is executed, there is no
 * "same as previous command" filter. One queued command is taken per driver tick (~249 Hz).
 */
#pragma once
#include <genesis.h>

#define SOUND_STOP_ALL    0x00
#define SOUND_STOP_SFX    0x10
#define SOUND_STOP_MUSIC  0x39

/* Load the Z80 driver and start it (YM2612 + PSG are reset). Call once after SGDK init. */
void sound_init(void);
/* Queue one arcade sound command. Non-blocking: holds the Z80 bus for a few microseconds.
 * Up to 15 commands can be pending; further ones are dropped until the driver catches up. */
void sound_command(u8 cmd);
/* Same as sound_command(SOUND_STOP_ALL). */
void sound_stop_all(void);
