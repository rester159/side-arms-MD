#include "game.h"
#include "sprites.h"
#include "flow.h"
#include "game_session.h"
#include "hud.h"

/* Top-level entry points called by main.c. The game's state machine (front
 * end, attract demo, intro, stage, continue, game over) lives in flow*.c;
 * see docs/frontend.md. Modules developed separately are reached through
 * weak references so the cartridge links before they exist. */

u16 frame;
bool engine_present = TRUE;
bool game_paused;
extern volatile u8 dbg_pad_override;
static u32 normal_update_clock;
static bool normal_clock_active;
volatile u32 dbg_normal_render_skips;
static u32 bc_update_clock;
static bool bc_clock_active;
volatile u32 dbg_bc_render_skips, dbg_bc_catchup_batches;

void sound_command(u8 cmd) __attribute__((weak));

/* $02F3: sound commands are dropped in attract mode unless the "demo
 * sounds" DIP switch is on ($C804 bit 7). */
void sound_play(u8 id)
{
    static u16 last_frame;
    static u8 last_id = 0xFF;
    /* Four simultaneous identical shots need one sound command, not four Z80
     * bus acquisitions. This changes no weapon cadence or projectile count. */
    if (game_player_limit() > 2 && id == last_id && frame == last_frame) return;
    last_id = id; last_frame = frame;
    if (game_in_demo() && !game_cfg.demo_sounds && id) return;
    if (sound_command) sound_command(id);
}

void game_init(void)
{
    game_paused = FALSE;
    input_configure();
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

static u16 frame_lines(u32 vblank)
{
    u16 vc = GET_VCOUNTER;
    u16 relative = vc >= 224 ? vc - 224 : vc + 262 - 224;
    return (u16)(vtimer - vblank) * 262 + relative;
}

/* Start remains join/continue for inactive slots and coin/start in Arcade.
 * Hold the simulation and its presentation together; audio remains on VInt. */
static bool __attribute__((noinline)) normal_pause(void)
{
    if (game_cfg.mode != MODE_HOME || (flow_state != FS_PLAY && flow_state != FS_RUSH)) {
        game_paused = FALSE;
        return FALSE;
    }
    /* Let the existing A+B+C+Start reset chord reach flow_update, even paused. */
    bool reset = (pad[0].held & 0xf0) == 0xf0 && pad[0].pressed;
    bool toggle = FALSE;
    if (!reset) for (u16 i = 0; i < game_player_limit(); ++i)
        if (normal_players[i].in_play && (pad[i].pressed & IN_START)) toggle = TRUE;
    if (reset || toggle) {
        game_paused = reset ? FALSE : !game_paused;
        hud_pause_display(game_paused);
        if (!reset) for (u16 i = 0; i < game_player_limit(); ++i)
            pad[i].pressed &= ~IN_START;
    }
    return game_paused;
}

static bool normal_can_skip(void)
{
    return game_cfg.mode == MODE_HOME && game_player_limit() > 2 &&
        ((flow_state == FS_PLAY && game_stage_running()) || flow_state == FS_RUSH) &&
        !players_world_frozen();
}

bool __attribute__((noinline)) game_frame(u32 vblank, u16 start_line)
{
    extern bool bc_robot_preview_frame(void);
    extern volatile u16 prof_seg[4], prof_line;
    if (bc_robot_preview_frame()) return TRUE;
    u8 owner = flow_session_prepare();
    if (owner != SESSION_BC) bc_clock_active = FALSE;
    if (owner == SESSION_NORMAL) {
        if (!normal_clock_active || !normal_can_skip()) {
            normal_update_clock = vtimer - 1;
            normal_clock_active = TRUE;
        }
        /* Preserve simulation cadence while limiting input/presentation latency.
         * Flush before another update if it queued graphics, and keep drawing
         * during heavy sprite streaming so recurring poses stay resident. */
        for (u16 batch = 0; batch < 8; batch++) {
            if (normal_pause()) {
                normal_clock_active = FALSE;
                return FALSE;
            }
            u32 debt = vtimer - normal_update_clock;
            if (debt > 9) normal_update_clock = vtimer - 9;
            game_update();
            ++normal_update_clock;
            if (batch == 7 || debt <= 1 || !normal_can_skip() ||
                spr_stream_busy() || DMA_getQueueSize()) break;
            ++dbg_normal_render_skips;
            if (dbg_pad_override) {
                for (u16 i = 0; i < MAX_PLAYERS; i++) {
                    pad[i].pressed = 0; pad_raw[i].pressed = 0;
                }
            } else JOY_update();
            input_update();
        }
        u16 update_line = frame_lines(vblank);
        game_draw();
        u16 draw_line = frame_lines(vblank);
        video_frame();
        prof_seg[3] = frame_lines(vblank);
        prof_seg[0] = start_line;
        prof_seg[1] = update_line; prof_seg[2] = draw_line;
        prof_line = GET_VCOUNTER;
    } else {
        normal_clock_active = FALSE;
        if (owner == SESSION_BC) {
            if (!bc_clock_active || !bc_scene_can_skip()) {
                bc_update_clock = vtimer - 1;
                bc_clock_active = TRUE;
            }
            /* Bound input latency and prevent starvation of presentation.
             * Time debt is measured in real VInts, never in rendered frames. */
            for (u16 batch = 0; batch < 8; ++batch) {
                u32 debt = vtimer - bc_update_clock;
                if (debt > 9) bc_update_clock = vtimer - 9;
                engine_present = batch == 7 || debt <= 1 || !bc_scene_can_skip();
                bc_scene_frame();
                ++bc_update_clock;
                if (bc_frame_presented) break;
                ++dbg_bc_render_skips;
                if (!batch) ++dbg_bc_catchup_batches;
                /* Poll controllers and advance mapping/autofire once per
                 * simulation update, including updates without presentation.
                 * The logical test hook supplies its own edges per update. */
                if (dbg_pad_override) {
                    for (u16 i = 0; i < MAX_PLAYERS; ++i) {
                        pad[i].pressed = 0; pad_raw[i].pressed = 0;
                    }
                } else JOY_update();
                input_update();
                owner = flow_session_prepare();
                if (owner != SESSION_BC) {
                    bc_clock_active = FALSE;
                    if (owner == SESSION_VIDEO) video_frame();
                    break;
                }
            }
            engine_present = TRUE;
        }
        else if (owner == SESSION_VIDEO) video_frame();
        /* Normal's animation clock and diagnostic sampling stay frozen
         * during BC, including held and consumed release frames. */
        prof_seg[0] = start_line; prof_seg[3] = frame_lines(vblank);
    }
    return FALSE;
}
