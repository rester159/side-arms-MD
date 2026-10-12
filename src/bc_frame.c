#include "bc_runtime.h"
#include "engine_step.h"

typedef struct {
    BcFrameCursor *cursor;
    BcPlayerControl *player;
    BcActor *actors;
    BcStage *stage;
    const BcStageEventData *stage_data;
    BcActorStepData *actor_data;
    unsigned short pose_table;
    unsigned char held, pressed, *limited_count;
    BcRuntimeEvents *events;
    BcFrameResult result;
} BcFrameStep;

static inline __attribute__((always_inline)) unsigned char solo_level_phase(void *context)
{
    BcFrameStep *s = context;
    BcFrameCursor *cursor = s->cursor;
    BcPlayerControl *player = s->player;
    BcActor *actors = s->actors;
    BcStage *stage = s->stage;
    const BcStageEventData *stage_data = s->stage_data;
    BcActorStepData *actor_data = s->actor_data;
    unsigned char *limited_count = s->limited_count;
    BcFrameResult *result = &s->result;
    if (cursor->stage_events >= 256) { return 5; }
    /* $6ECA gates the whole scroll task only on entry. A due stop event still
     * reaches $6ED4 this iteration; subsequent iterations skip both parts. */
    if (!stage->stopped || cursor->scrolling) {
        cursor->scrolling = 1;
        for (;;) {
            BcStageEventResult event = bc_runtime_stage_event(stage, actors,
                &player->world, stage_data, limited_count);
            result->handler = event.handler;
            if (!event.status) break;
            if (event.status != 1) {
                return event.status == 3 ? 4 : 3;
            }
            result->stage_events++;
            if (++cursor->stage_events == 256) {
                return 5;
            }
        }
        bc_stage_scroll(stage);
    }
    cursor->scrolling = 0;
    cursor->stage_events = 0;
    actor_data->camera_x = stage->x >> 8;
    actor_data->camera_y = stage->y >> 8;
    actor_data->terrain.attributes = actor_data->data.bytes +
        (unsigned short)(stage->terrain_attributes - actor_data->data.origin);
    return 0;
}

static inline __attribute__((always_inline)) unsigned char solo_play_phase(void *context)
{
    BcFrameStep *s = context;
    s->result.play = bc_runtime_play(s->player, s->actors, s->stage, s->actor_data,
        s->pose_table, s->held, s->pressed, s->limited_count, s->events);
    return s->result.play.status;
}

BcFrameResult bc_runtime_frame(BcFrameCursor *cursor, BcPlayerControl *player,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcStageEventData *stage_data, BcActorStepData *actor_data,
    unsigned short pose_table, unsigned char held, unsigned char pressed,
    unsigned char *limited_count, BcRuntimeEvents *events)
{
    BcFrameStep step = {.cursor=cursor, .player=player, .actors=actors, .stage=stage,
        .stage_data=stage_data, .actor_data=actor_data, .pose_table=pose_table,
        .held=held, .pressed=pressed, .limited_count=limited_count, .events=events};
    /* The inner play policy uses the same engine scheduler for its player,
     * actor and trail phases; an audio wait prevents it from running at all. */
    ENGINE_STEP(step.result.status, solo_level_phase(&step), 0, 0, solo_play_phase(&step));
    return step.result;
}
