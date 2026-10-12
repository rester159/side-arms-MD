#pragma once
#include <genesis.h>

/* The frame owner is resolved before execution and remains fixed even when
 * a menu starts a session or a session rebuilds the frontend during that frame. */
enum { SESSION_NORMAL, SESSION_BC, SESSION_HOLD, SESSION_VIDEO };
enum { SESSION_RUN, SESSION_PAUSE, SESSION_RESET, SESSION_HOME };
extern bool home_session, scene_paused;
void flow_session_request_bc(void);
u8 flow_session_prepare(void);

/* BC rules/resource policy; none of these owns the outer game loop. */
u8 bc_scene_control(void);
void bc_scene_pause_display(void);
bool bc_scene_available(void);
void bc_scene_enter(void);
void bc_scene_frame(void);

/* Engine presentation choice; BC can force presentation for a handoff. */
extern bool engine_present, bc_frame_presented;
bool bc_scene_can_skip(void);
