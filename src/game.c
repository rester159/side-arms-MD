#include "game.h"
#include "sprites.h"
#include "flow.h"

/* Top-level entry points called by main.c. The game's state machine (front
 * end, attract demo, intro, stage, continue, game over) lives in flow*.c;
 * see docs/frontend.md. Modules developed separately are reached through
 * weak references so the cartridge links before they exist. */

u16 frame;
void sound_command(u8 cmd) __attribute__((weak));

/* $02F3: sound commands are dropped in attract mode unless the "demo
 * sounds" DIP switch is on ($C804 bit 7). */
void sound_play(u8 id)
{
    if (game_in_demo() && !game_cfg.demo_sounds && id) return;
    if (sound_command) sound_command(id);
}

void game_init(void)
{
    players_init();
    flow_init();
}

void game_update(void)
{
    frame++;
    flow_update();
}

void game_draw(void)
{
    spr_begin();
    flow_draw();
    spr_end();
}
