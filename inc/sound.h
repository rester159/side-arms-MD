/* Side Arms MD - sound (native Genesis driver: YM2612 music, PSG SFX; see docs/sound_port.md).
 *
 * Command numbers are the arcade sound-latch values (docs/re/sound.md): $00 stop all,
 * $01-$1E SFX, $10/$16/$19/$1F stop SFX, $20-$38 music, $39-$3F stop music (only bits 0-5 are
 * used, like the arcade dispatch at a_04k $00B8; $FF is ignored). Native $FE/$FD
 * start/fully silence the finite Before Christ credits arrangement.
 * The caller models the arcade latch (src/game.c): every call here is executed, there is no
 * "same as previous command" filter. One queued command is taken per driver tick (~249 Hz).
 */
#pragma once
#include <genesis.h>

/* $FE selects the finite native Before Christ credits arrangement. */
#define SOUND_BC_CREDITS  0xFE
#define SOUND_BC_CREDITS_STOP 0xFD

#define SOUND_STOP_ALL    0x00
#define SOUND_STOP_SFX    0x10
#define SOUND_STOP_MUSIC  0x39

/* Load the Z80 driver and start it (YM2612 + PSG are reset). Call once after SGDK init. */
void sound_init(void);
/* Exact SGDK null-driver copy for cartridge boot and intro teardown. */
void z80_idle(void);
/* Submit an arcade event ID. HuCard mode maps music starts to the source score;
 * SFX and arcade music use the FIFO (15 pending entries). Bus holds stay short.
 * Replacing a HuCard score waits briefly for the consumer's current frame. */
void sound_command(u8 cmd);
/* Same queue operation, with acceptance reported for callers that must retry. */
bool sound_try_command(u8 cmd);
/* Same as sound_command(SOUND_STOP_ALL). */
void sound_stop_all(void);

/* HuCard native playback. The UI/mode command mapper selects source song IDs. */
bool sound_hucard_start(u8 song);
void sound_hucard_stop(void);
/* Called by the real VInt, including while gameplay is lagging or paused. */
void sound_vint(void);

/* Gameplay soundtrack selection: 0 Arcade, 1 PC Engine. */
void sound_set_music_source(u8 source);
