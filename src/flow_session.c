#include "game_session.h"
#include "game.h"
#include "flow.h"
#include "bg.h"
#include "boss.h"
#include "enemies.h"
#include "sound.h"

/* Engine-owned session authority. Debug fields are request/status adapters,
 * not a second execution loop. Normal/Rush retain their FlowState policies. */
bool home_session, scene_paused;
static bool session_active;
static u16 saved_player_limit;
extern volatile u16 dbg_bc_native, dbg_bc_native_players, dbg_bc_native_status;

void flow_session_request_bc(void)
{
    home_session = TRUE;
    scene_paused = FALSE;
    dbg_bc_native = 1;
    flow_goto(FS_BC);
}

u8 flow_session_prepare(void)
{
    bool return_home = FALSE;
    if (home_session && session_active) {
        u8 action = bc_scene_control();
        if (action == SESSION_RESET || action == SESSION_HOME) {
            dbg_bc_native = 0;
            return_home = action == SESSION_HOME;
        } else if (action == SESSION_PAUSE) {
            scene_paused = !scene_paused;
            bc_scene_pause_display();
        }
    }
    if (!dbg_bc_native) {
        bool leaving = session_active;
        if (leaving) {
            session_active = FALSE;
            /* Session-owned music and effects must not outlive BC, including
             * credits dismissed before their finite playback window ends. */
            sound_stop_all();
            players_bc_release();
            player_limit = saved_player_limit;
            bg_release_blocks();
            enemies_clear();
            video_init();
            game_init();
        }
        if (return_home) flow_goto(FS_HOME);
        home_session = scene_paused = FALSE;
        /* Consume the release input; the new menu runs next frame. */
        return leaving ? SESSION_VIDEO : SESSION_NORMAL;
    }
    if (!bc_scene_available()) { dbg_bc_native_status = 0xffff; return SESSION_HOLD; }
    if (!session_active) {
        u16 count = dbg_bc_native_players >= 2 && dbg_bc_native_players <= 4 ? dbg_bc_native_players : 1;
        if (!players_bc_acquire(count)) { dbg_bc_native_status = 0xfffe; return SESSION_HOLD; }
        bosses_reset();
        enemies_clear();
        saved_player_limit = player_limit;
        bc_scene_enter();
        session_active = TRUE;
    }
    return scene_paused ? SESSION_HOLD : SESSION_BC;
}
