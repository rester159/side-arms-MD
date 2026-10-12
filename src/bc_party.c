#include "bc_party.h"
#include "engine_step.h"

unsigned char bc_party_bind(BcPartyControl *party,
    BcPlayerControl *const players[BC_PARTY_CAPACITY], unsigned char count,
    BcPartyContactSink sink, void *context)
{
    if (!count || count > BC_PARTY_CAPACITY) return 0;
    for (unsigned char i = 0; i < count; i++) {
        if (!players[i]) return 0;
        for (unsigned char j = 0; j < i; j++) if (players[i] == players[j]) return 0;
    }
    party->contacts.count = count; party->contacts.contact = sink;
    party->contacts.contact_policy = 0;
    party->contacts.body_bounds_valid = 0;
    party->contacts.context = context; party->waiting = 0;
    party->waves = (BcWaveQueue){0};
    for (unsigned char i = 0; i < BC_PARTY_CAPACITY; i++) {
        party->players[i] = i < count ? players[i] : 0;
        party->contacts.players[i] = i < count ? &players[i]->world : 0;
        if (i < count) players[i]->world.party = count > 1 ? &party->contacts : 0;
    }
    return 1;
}

/* Rotate the preferred living target every eight scheduler updates, as in
 * our Home game. Dead/checkpoint-waiting members are never preferred. */
static BcWorldPlayer *target(BcPartyControl *party, unsigned char clock)
{
    /* Valid parties have 2, 3 or 4 players here. Avoid a variable division
     * twice per frame while preserving rotation across the byte-clock wrap. */
    static const unsigned char thirds[32] = {
        0,1,2,0,1,2,0,1,2,0,1,2,0,1,2,0,
        1,2,0,1,2,0,1,2,0,1,2,0,1,2,0,1
    };
    unsigned char first = party->contacts.count == 3 ? thirds[clock >> 3] :
        (clock >> 3) & (party->contacts.count - 1);
    for (unsigned char j = 0; j < party->contacts.count; j++) {
        unsigned char i = first + j;
        if (i >= party->contacts.count) i -= party->contacts.count;
        if (!(party->waiting & (1 << i)) && party->players[i]->world.state == 0x80)
            return &party->players[i]->world;
    }
    return &party->players[0]->world;
}

typedef struct {
    BcPartyFrameResult *result;
    BcPartyControl *party;
    BcFrameCursor *cursor;
    BcActor *actors;
    BcStage *stage;
    const BcStageEventData *stage_data;
    BcActorStepData *actor_data;
    unsigned short pose_table;
    const unsigned char *held, *pressed;
    unsigned char *limited_count;
    BcRuntimeEvents *events;
    unsigned char count;
    signed short dx, dy;
    unsigned short camera_x, camera_y;
} BcPartyStep;

static inline __attribute__((always_inline)) unsigned char party_level_phase(void *context)
{
    BcPartyStep *s = context;
    BcPartyFrameResult *result = s->result;
    BcPartyControl *party = s->party;
    BcFrameCursor *cursor = s->cursor;
    BcActor *actors = s->actors;
    BcStage *stage = s->stage;
    const BcStageEventData *stage_data = s->stage_data;
    BcActorStepData *actor_data = s->actor_data;
    unsigned char *limited_count = s->limited_count;
    unsigned char count = s->count;
    if (cursor->stage_events >= 256) { return 5; }
    BcWorldPlayer *aim = target(party, actor_data->scheduler_counter);
    unsigned char held_camera = 0;
    /* Same stage/audio-wait ordering as the original frame task. All player
     * inputs remain untouched until the due events have completed. */
    unsigned char scroll_frame = !stage->stopped || cursor->scrolling;
    if (scroll_frame) {
        cursor->scrolling = 1;
        for (;;) {
            unsigned short script = stage->script;
            if (count > 2 && party->waves.count) {
                unsigned short handler = bc_stage_event_next(stage, &stage_data->data);
                if (!handler) break;
                if (party->waves.count == BC_WAVE_QUEUE_CAPACITY ||
                    bc_wave_barrier(stage_data->round, handler, stage_data->relocation)) {
                    held_camera = 1; break;
                }
            }
            BcStageEventResult event = bc_runtime_stage_event(stage, actors, aim, stage_data, limited_count);
            result->handler = event.handler;
            if (!event.status) break;
            if (event.status != 1) {
                return event.status == 3 ? 4 : 3;
            }
            if (count > 2 && event.wave_size) {
                if (event.slot < 0) {
                    stage->script = script; held_camera = 1; break;
                }
                bc_wave_enqueue(&party->waves, count, script, event.wave_size);
            }
            result->stage_events++;
            if (++cursor->stage_events == 256) { return 5; }
        }
    }
    cursor->scrolling = held_camera; cursor->stage_events = 0;
    if (count > 2) bc_wave_service(&party->waves, stage, actors, aim, stage_data, limited_count);
    if (scroll_frame && !held_camera) bc_stage_scroll(stage);
    signed short dx = held_camera ? 0 : stage->dx, dy = held_camera ? 0 : stage->dy;
    /* Player updates cannot move the shared stage camera. Convert it once
     * for the whole party, after the stage has finished scrolling. */
    unsigned short camera_x = stage->x >> 8, camera_y = stage->y >> 8;
    actor_data->camera_x = camera_x; actor_data->camera_y = camera_y;
    actor_data->terrain.attributes = actor_data->data.bytes +
        (unsigned short)(stage->terrain_attributes - actor_data->data.origin);
    s->dx = dx; s->dy = dy; s->camera_x = camera_x; s->camera_y = camera_y;
    return 0;
}

static inline __attribute__((always_inline)) unsigned char party_player_phase(void *context)
{
    BcPartyStep *s = context;
    BcPartyFrameResult *result = s->result;
    BcPartyControl *party = s->party;
    BcActorStepData *actor_data = s->actor_data;
    unsigned short pose_table = s->pose_table;
    const unsigned char *held = s->held;
    const unsigned char *pressed = s->pressed;
    unsigned char count = s->count;
    signed short dx = s->dx;
    signed short dy = s->dy;
    unsigned short camera_x = s->camera_x;
    unsigned short camera_y = s->camera_y;
    for (unsigned char i = 0; i < count; i++) {
        if (party->waiting & (1 << i)) continue;
        bc_player_step_into(&result->players[i], party->players[i], held[i], pressed[i],
            camera_x, camera_y, dx, dy, &actor_data->terrain,
            &actor_data->data, pose_table);
        if (result->players[i].control.checkpoint) {
            party->waiting |= 1 << i; result->checkpoints |= 1 << i;
        }
    }
    if (party->waiting == (1 << count) - 1) { return 1; }
    return 0;
}

static inline __attribute__((always_inline)) unsigned char party_actor_phase(void *context)
{
    BcPartyStep *s = context;
    BcPartyFrameResult *result = s->result;
    BcPartyControl *party = s->party;
    BcStage *stage = s->stage;
    BcActorStepData *actor_data = s->actor_data;
    BcActor *actors = s->actors;
    unsigned char *limited_count = s->limited_count;
    BcRuntimeEvents *events = s->events;
    signed short dx = s->dx;
    signed short dy = s->dy;
    if (stage->boss_active && !(actor_data->scheduler_counter & 3)) stage->boss_active--;
    actor_data->boss_active = stage->boss_active;
    BcWorldPlayer *aim = target(party, actor_data->scheduler_counter);
    result->next_slot = bc_runtime_actor_loop(actors, 0, aim, actor_data, limited_count,
        stage->shot_limit, dx, dy, stage->stopped,
        events ? bc_runtime_actor_events : 0, events);
    if (result->next_slot != BC_ACTOR_CAPACITY) { return 2; }
    return 0;
}

static inline __attribute__((always_inline)) unsigned char party_trail_phase(void *context)
{
    BcPartyStep *s = context;
    BcPartyControl *party = s->party;
    unsigned char count = s->count;
    for (unsigned char i = 0; i < count; i++) {
        if (party->waiting & (1 << i)) continue;
        BcWorldPlayer *p = &party->players[i]->world;
        bc_weapons_record_position(&p->weapons, p->x >> 8, p->y >> 8);
    }
    return 0;
}

void bc_runtime_party_frame_into(BcPartyFrameResult *result, BcPartyControl *party, BcFrameCursor *cursor,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcStageEventData *stage_data, BcActorStepData *actor_data,
    unsigned short pose_table, const unsigned char held[BC_PARTY_CAPACITY],
    const unsigned char pressed[BC_PARTY_CAPACITY], unsigned char *limited_count,
    BcRuntimeEvents *events)
{
    *result = (BcPartyFrameResult){0};
    unsigned char count = party->contacts.count;
    if (!count || count > BC_PARTY_CAPACITY) { result->status = 5; return; }
    if (count == 1) {
        BcFrameResult single = bc_runtime_frame(cursor, party->players[0], actors, stage,
            stage_data, actor_data, pose_table, held[0], pressed[0], limited_count, events);
        result->players[0] = single.play.player_event;
        result->handler = single.handler; result->stage_events = single.stage_events;
        result->status = single.status; result->next_slot = single.play.next_slot;
        result->checkpoints = single.status == 1;
        return;
    }
    BcPartyStep step = {
        .result=result, .party=party, .cursor=cursor, .actors=actors, .stage=stage,
        .stage_data=stage_data, .actor_data=actor_data, .pose_table=pose_table,
        .held=held, .pressed=pressed, .limited_count=limited_count, .events=events,
        .count=count
    };
    ENGINE_STEP(result->status, party_level_phase(&step), party_player_phase(&step),
        party_actor_phase(&step), party_trail_phase(&step));
}

BcPartyFrameResult bc_runtime_party_frame(BcPartyControl *party, BcFrameCursor *cursor,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcStageEventData *stage_data, BcActorStepData *actor_data,
    unsigned short pose_table, const unsigned char held[BC_PARTY_CAPACITY],
    const unsigned char pressed[BC_PARTY_CAPACITY], unsigned char *limited_count,
    BcRuntimeEvents *events)
{
    BcPartyFrameResult result;
    bc_runtime_party_frame_into(&result, party, cursor, actors, stage, stage_data,
        actor_data, pose_table, held, pressed, limited_count, events);
    return result;
}
