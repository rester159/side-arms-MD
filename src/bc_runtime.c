#include "bc_runtime.h"
#include "engine_step.h"
#include "enemy_pass.h"
#include "bc_round_data.h"

#ifndef __m68k__
/* Standalone host rule tests omit generated cartridge resources. */
const BcTerrain bc_round8_terrain __attribute__((weak)) = {0};
const unsigned char bc_round8_solid[65536] __attribute__((weak)) = {0};
const BcTerrain bc_final_terrain __attribute__((weak)) = {0};
const unsigned char bc_final_solid[65536] __attribute__((weak)) = {0};
#endif

/* Spawn-only temporary state must not enlarge the ordinary frame function
 * when stage dispatch is inlined by the cartridge build. */
static void __attribute__((noinline)) walker_birth_update(BcActorEvent *result,
    const BcStage *s, BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *p, const BcStageEventData *data, unsigned char *count)
{
    /* Birth falls through the terrain routine, not directly to common.
     * Its initial 16-tick counter cannot request RNG or fire here. */
    unsigned short seed = 0;
    BcActorStepData step = {0};
    step.data = data->data; step.round = data->round; step.relocation = data->relocation;
    step.random_state = &seed; step.camera_x = s->x >> 8; step.camera_y = s->y >> 8;
    step.terrain.cells = data->data.bytes + 0xc000;
    step.terrain.attributes = data->data.bytes + s->terrain_attributes - data->data.origin;
    bc_actor_walker_birth(result, actors, slot, p, &step, count, s->shot_limit);
}

static void stage_birth_effects(const BcStageEventData *data, unsigned char slot,
    const BcActorEvent *event)
{
    if (data->score && event->score_pending)
        bc_score_enqueue(data->score, event->score_id, data->playing);
    if (data->birth_sink) data->birth_sink(slot, event, data->birth_context);
}

static signed short __attribute__((noinline)) ceiling_birth(BcActor actors[BC_ACTOR_CAPACITY],
    BcWorldPlayer *p, const BcStageEventData *data, unsigned char *count)
{
    unsigned char slot;
    for (slot = 0; slot <= 28; slot++)
        if (!(actors[slot].body.state | actors[slot+1].body.state |
              actors[slot+2].body.state | actors[slot+3].body.state)) break;
    if (slot > 28) return -1;
    static const unsigned char x[4] = {208,240,192,224};
    for (unsigned char i = 0; i < 4; i++) {
        BcActor *a = &actors[slot+i];
        bc_actor_template(a, data->data.bytes + (data->round == 6 ? 0xbb1c : 0xbe93) - data->data.origin, data->ceiling_base);
        bc_enemy_set_x(&a->body, x[i]);
        bc_enemy_set_y(&a->body, 0x8); bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
    }
    actors[slot].routine = data->round == 6 ? 0xba36 : 0xbdad;
    for (unsigned char i = 0; i < 4; i++) {
        BcActorEvent event;
        bc_actor_common_into(&event, &actors[slot+i], p, &data->data, count);
        stage_birth_effects(data, slot+i, &event);
    }
    return slot;
}

/* Round-four/eight five-pod formation: run each birth before installing formation
 * positions, then advance RNG once for the shared position table. */
static signed short __attribute__((noinline)) formation_birth(BcActor actors[BC_ACTOR_CAPACITY],
    BcWorldPlayer *p, const BcStageEventData *data, unsigned char *count, unsigned char variant)
{
    unsigned short shift = data->round == 7 ? 0x580 : 0;
    unsigned char slot = 0;
    /* An occupied slot rules out every candidate group containing it.
     * Probe backwards and skip those starts, preserving the first free run. */
    while (slot < 28) {
        if (actors[slot+4].body.state) slot += 5;
        else if (actors[slot+3].body.state) slot += 4;
        else if (actors[slot+2].body.state) slot += 3;
        else if (actors[slot+1].body.state) slot += 2;
        else if (actors[slot].body.state) slot++;
        else break;
    }
    if (slot >= 28) return -1;
    for (unsigned char i = 0; i < 5; i++) {
        BcActor *a = &actors[slot+i];
        bc_actor_template(a, data->data.bytes + 0xb59a + shift - data->data.origin, data->ceiling_base);
        a->body.x &= 0xff00; a->body.y &= 0xff00;
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->wait = 0x53;
        BcActorEvent event;
        bc_actor_common_into(&event, a, p, &data->data, count);
        stage_birth_effects(data, slot+i, &event);
    }
    actors[slot].death_routine = 0xb592 + shift; actors[slot].wait = 0x4d;
    *data->random_state = bc_random_next(*data->random_state);
    unsigned char index = ((*data->random_state >> 8) & 7) | variant;
    const unsigned char *entry = data->data.bytes + 0xb5ad + shift + index * 2 - data->data.origin;
    const unsigned char *xy = data->data.bytes + (entry[0] | ((unsigned short)entry[1] << 8)) - data->data.origin;
    for (unsigned char i = 0; i < 5; i++) {
        BcActor *a = &actors[slot+i];
        if (i) a->phase = slot;
        a->turn = 60+i; a->body.timer = 1+i;
        bc_enemy_set_y(&a->body, xy[i*2]);
        bc_enemy_set_x(&a->body, xy[i*2+1]);
    }
    return slot;
}

/* A successful segment birth runs eight contacts against unmoved shots.
 * Cache only this batch: failed allocation retries and ordinary stage events
 * must not pay for building another set of player indices. */
static void __attribute__((noinline)) segment_birth_contacts(
    BcActor actors[BC_ACTOR_CAPACITY], const unsigned char slots[8], BcWorldPlayer *p,
    const BcStageEventData *data, unsigned char *count)
{
    BcShotIndex indices[BC_PARTY_CAPACITY];
    const BcShotIndex *previous[BC_PARTY_CAPACITY];
    BcWorldPlayer *members[BC_PARTY_CAPACITY];
    unsigned char players = p->party && p->party->count > 1 &&
        p->party->count <= BC_PARTY_CAPACITY ? p->party->count : 1;
    unsigned char protected_empty = 1;
    for (unsigned char i = 0; i < players; i++) {
        BcWorldPlayer *member = players == 1 ? p : p->party->players[i];
        members[i] = member;
        if (!member) continue;
        previous[i] = member->shot_index;
        bc_shot_index(&indices[i], &member->weapons);
        member->shot_index = &indices[i];
        if (member->state == 0x80 &&
            (!member->invulnerability || indices[i].count)) protected_empty = 0;
    }
    /* Protection cannot expire during births. With at least one living
     * protected member and no eligible shots, contacts only tick timers. */
    unsigned char old_policy = players > 1 ? p->party->contact_policy : 0;
    unsigned char cached = 0;
    if (players > 1 && protected_empty) {
        for (unsigned char i = 0; i < players; i++)
            if (members[i] && members[i]->state == 0x80) {
                p->party->contact_policy = 4;
                cached = 1;
                break;
            }
    }
    for (unsigned char i = 0; i < 8; i++) {
        BcActorEvent event;
        bc_actor_common_into(&event, &actors[slots[i]], p, &data->data, count);
        stage_birth_effects(data, slots[i], &event);
    }
    if (cached) p->party->contact_policy = old_policy;
    for (unsigned char i = 0; i < players; i++)
        if (members[i]) members[i]->shot_index = previous[i];
}

static signed short __attribute__((noinline)) segment_birth(BcActor actors[BC_ACTOR_CAPACITY],
    BcWorldPlayer *p, const BcStageEventData *data, unsigned char *count, unsigned char variant)
{
    unsigned char slot = 0;
    /* Every start through an occupied member would overlap that member.
     * Skip those candidates while retaining the first free eight-slot run. */
    while (slot <= 24) {
        if (actors[slot+7].body.state) slot += 8;
        else if (actors[slot+6].body.state) slot += 7;
        else if (actors[slot+5].body.state) slot += 6;
        else if (actors[slot+4].body.state) slot += 5;
        else if (actors[slot+3].body.state) slot += 4;
        else if (actors[slot+2].body.state) slot += 3;
        else if (actors[slot+1].body.state) slot += 2;
        else if (actors[slot].body.state) slot++;
        else break;
    }
    unsigned char members[8], sparse = slot > 24;
    if (sparse) {
        /* Co-op retries must not freeze the camera forever when surviving
         * scenery enemies split an otherwise mostly empty pool. Reserve a
         * complete train in ascending free slots; never move live actors. */
        if (!p->party || p->party->count <= 2 || p->party->count > BC_PARTY_CAPACITY)
            return -1;
        unsigned char found = 0;
        for (unsigned char i = 0; i < BC_ACTOR_CAPACITY && found < 8; i++)
            if (!actors[i].body.state) members[found++] = i;
        if (found != 8) return -1;
    } else {
        for (unsigned char i = 0; i < 8; i++) members[i] = slot+i;
    }
    for (unsigned char i = 0; i < 8; i++) {
        BcActor *a = &actors[members[i]];
        bc_actor_template(a, data->data.bytes + (data->round == 7 ? 0xc062 : data->round == 6 ? 0xb942 : data->round == 4 ? 0xb8f8 : data->round == 3 ? 0xb933 : data->round == 2 ? 0xb7fe : 0xbcb9) - data->data.origin, data->segment_bases[1]);
        bc_enemy_set_x(&a->body, 0x108); bc_enemy_set_y(&a->body, 0xa8);
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->wait = 1 + i * 7;
        a->dash_started = 0x42; a->fired = 0; a->body.cooldown = 255;
        a->direction = 8; a->phase = variant;
        /* Segment tasks do not otherwise use these family scratch bytes.
         * Templates clear auxiliary, so normal births/reuse cannot inherit
         * the sparse-link marker. Contiguous source records stay untouched. */
        if (sparse) {
            a->auxiliary = 255;
            a->probe_x = members[i ? i-1 : 0];
            a->probe_y = members[i < 7 ? i+1 : 7];
        }
        if (variant) {
            a->speed = 6; a->body.hp = 3;
            a->body.attributes = (a->body.attributes & 0xff00) | 0x8a;
            a->sprite_base_ref = 0x36a6; a->body.sprite_base = data->segment_bases[4];
        }
    }
    actors[members[0]].dash_started = 0x48; actors[members[0]].body.cooldown = 0;
    actors[members[7]].dash_started = 0x54;
    actors[members[5]].body.score_id = variant ? 12 : 10;
    actors[members[0]].sprite_base_ref = variant ? 0x36a4 : 0x369e;
    actors[members[0]].body.sprite_base = data->segment_bases[variant ? 3 : 0];
    actors[members[7]].sprite_base_ref = variant ? 0x36a8 : 0x36a2;
    actors[members[7]].body.sprite_base = data->segment_bases[variant ? 5 : 2];
    segment_birth_contacts(actors, members, p, data, count);
    return members[0];
}

static void __attribute__((noinline)) final_serpent_birth(BcActor actors[BC_ACTOR_CAPACITY],
    BcWorldPlayer *p, const BcStageEventData *data, unsigned char *count)
{
    for (unsigned char slot = 0; slot < 8; slot++) {
        BcActor *a = &actors[slot];
        bc_actor_template(a, data->data.bytes + 0xa60f - data->data.origin, data->segment_bases[1]);
        bc_enemy_set_x(&a->body, 0x110); bc_enemy_set_y(&a->body, 0x80);
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->wait = 1 + slot*13;
        a->dash_started = 0x42; a->fired = 0; a->body.cooldown = 255; a->direction = 8;
    }
    actors[0].dash_started = 0x48; actors[0].body.cooldown = 0; actors[0].phase = 90;
    actors[0].body.attributes = (actors[0].body.attributes & 0xff00) | 0x84;
    actors[0].sprite_base_ref = 0x36d0; actors[0].body.sprite_base = data->segment_bases[0];
    actors[7].dash_started = 0x54; actors[7].phase = 100;
    actors[7].body.attributes = (actors[7].body.attributes & 0xff00) | 0x86;
    actors[7].sprite_base_ref = 0x36d4; actors[7].body.sprite_base = data->segment_bases[2];
    actors[5].body.score_id = 25;
    for (unsigned char slot = 0; slot < 8; slot++) {
        BcActorEvent event;
        bc_actor_common_into(&event, &actors[slot], p, &data->data, count);
        stage_birth_effects(data, slot, &event);
    }
}

static void __attribute__((noinline)) round_two_boss_birth(BcStage *s,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *p,
    const BcStageEventData *data, unsigned char *count)
{
    static const unsigned char x[5] = {208,216,216,176,176};
    static const unsigned char y[5] = {120,96,144,110,130};
    s->boss_active = 255;
    for (unsigned char slot = 0; slot < 5; slot++) {
        BcActor *a = &actors[slot];
        bc_actor_template(a, data->data.bytes + (data->round == 8 ? 0xb656 : 0xae67) + slot * 19 - data->data.origin, data->boss_base);
        bc_enemy_set_x(&a->body, x[slot]);
        bc_enemy_set_y(&a->body, y[slot]);
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.damage_lock = 128;
        if (!slot) { a->auxiliary = 1; a->phase = 24; if (data->round == 8) a->body.score_id = 10; }
        else a->body.cooldown = 255;
        BcActorEvent event;
        bc_actor_common_into(&event, a, p, &data->data, count);
        stage_birth_effects(data, slot, &event);
    }
}

static void __attribute__((noinline)) round_three_boss_birth(BcStage *s,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *p,
    const BcStageEventData *data, unsigned char *count, unsigned short handler)
{
    static const unsigned char x[3] = {208,200,200};
    static const unsigned char y[3] = {120,104,136};
    unsigned char fourth = data->round == 3 || (data->round == 8 && handler == 0xac32), fifth = data->round == 4 || (data->round == 8 && handler == 0xc18b), sixth = data->round == 5 || (data->round == 8 && handler == 0xa8c6), eighth = data->round == 7 || (data->round == 8 && handler == 0xbcf0);
    s->boss_active = 255;
    for (unsigned char slot = 0; slot < 3; slot++) {
        BcActor *a = &actors[slot];
        bc_actor_template(a, data->data.bytes + (data->round == 8 ? (eighth ? 0xbf23 : sixth ? 0xaae2 : fifth ? 0xc394 : fourth ? 0xaeaa : 0xb1ee) : eighth ? 0xb279 : sixth ? 0xb068 : fifth ? 0xae59 : fourth ? 0xa9e6 : 0xacc7) + slot * 19 - data->data.origin, data->boss_base);
        bc_enemy_set_x(&a->body, (eighth ? 216 : (sixth ? 200 : x[slot]) + (fourth ? 24 : fifth && !slot ? 8 : 0)));
        bc_enemy_set_y(&a->body, ((fourth || eighth) ? (slot == 1 ? 88 : slot == 2 ? 152 : 120) : y[slot]));
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.damage_lock = 128;
        if (!slot) { a->auxiliary = 1; a->phase = (fourth || eighth) ? 32 : 16; if (fourth) a->fired = 0; if (sixth || eighth) a->turn = 0; if (data->round == 8) a->body.score_id = eighth ? 17 : sixth ? 15 : fifth ? 14 : fourth ? 13 : 12; }
        else a->body.cooldown = 255;
        BcActorEvent event;
        bc_actor_common_into(&event, a, p, &data->data, count);
        stage_birth_effects(data, slot, &event);
    }
}

static signed short __attribute__((noinline)) paired_birth(BcActor actors[BC_ACTOR_CAPACITY],
    BcWorldPlayer *p, const BcStageEventData *data, unsigned char *count)
{
    unsigned char slot;
    for (slot = 0; slot < 31; slot++)
        if (!actors[slot].body.state && !actors[slot+1].body.state) break;
    if (slot == 31) return -1;
    const unsigned char *bytes = data->data.bytes;
    for (unsigned char i = 0; i < 2; i++) {
        BcActor *a = &actors[slot+i];
        bc_actor_template(a, bytes + 0xb9a5 - data->data.origin, data->ceiling_base);
        bc_enemy_set_y(&a->body, 0xe8);
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->turn = 64;
    }
    *data->random_state = bc_random_next(*data->random_state);
    unsigned char delay = bytes[0xb9b8 - data->data.origin + ((*data->random_state >> 8) & 3)];
    for (unsigned char i = 0; i < 2; i++) {
        BcActor *a = &actors[slot+i];
        a->body.move_delay = delay; a->phase = i ? 0x52 : 0x4c; a->wait = 0x43;
        a->body.x = (i ? 0x900000u : 0x700000u) | (a->body.x & 0xff00);
        if (i) a->body.animation = 0xb9c1;
    }
    for (unsigned char i = 0; i < 2; i++) {
        BcActorEvent event;
        bc_actor_common_into(&event, &actors[slot+i], p, &data->data, count);
        stage_birth_effects(data, slot+i, &event);
    }
    return slot;
}

static void __attribute__((noinline)) round_seven_boss_birth(BcStage *s,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *p,
    const BcStageEventData *data, unsigned char *count)
{
    s->boss_active = 255;
    for (unsigned char slot = 0; slot < 3; slot++) {
        BcActor *a = &actors[slot];
        bc_actor_template(a, data->data.bytes + (data->round == 8 ? 0xbb9e : 0xacd5) + slot * 19 - data->data.origin, data->boss_base);
        bc_enemy_set_x(&a->body, (slot ? 224 : 240));
        bc_enemy_set_y(&a->body, (slot == 1 ? 104 : slot == 2 ? 136 : 120));
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.damage_lock = 128;
        if (!slot) { a->auxiliary = 1; a->phase = 16; a->turn = 0; if (data->round == 8) a->body.score_id = 16; }
        else { a->body.cooldown = 255; a->wait = 1; }
        BcActorEvent event;
        bc_actor_common_into(&event, a, p, &data->data, count);
        stage_birth_effects(data, slot, &event);
    }
}

static void __attribute__((noinline)) round_nine_final_birth(BcStage *s,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *p,
    const BcStageEventData *data, unsigned char *count)
{
    s->boss_active = 255;
    for (unsigned char slot = 0; slot < 3; slot++) {
        BcActor *a = &actors[slot];
        bc_actor_template(a, data->data.bytes + 0xc742 + slot * 19 - data->data.origin, data->boss_base);
        bc_enemy_set_x(&a->body, (slot ? 208 : 200));
        bc_enemy_set_y(&a->body, (slot == 1 ? 104 : slot == 2 ? 136 : 120));
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.damage_lock = 128;
        if (!slot) { a->auxiliary = 1; a->turn = 16; }
        else a->body.cooldown = 255;
        BcActorEvent event;
        bc_actor_common_into(&event, a, p, &data->data, count);
        stage_birth_effects(data, slot, &event);
    }
}

/* Successful curve births can touch every living player's shots before the
 * ordinary actor pass builds its indices. Keep this storage off all failed
 * allocations and non-curve events. Consumed shots remain checked live. */
static void __attribute__((noinline)) curve_birth_contact(BcActorEvent *event,
    BcActor *actor, BcWorldPlayer *p, const BcEnemyData *data, unsigned char *count)
{
    BcShotIndex indices[BC_PARTY_CAPACITY];
    const BcShotIndex *previous[BC_PARTY_CAPACITY];
    BcWorldPlayer *members[BC_PARTY_CAPACITY];
    unsigned char players = p->party && p->party->count > 1 &&
        p->party->count <= BC_PARTY_CAPACITY ? p->party->count : 1;
    for (unsigned char i = 0; i < players; i++) {
        BcWorldPlayer *member = players == 1 ? p : p->party->players[i];
        members[i] = member;
        if (!member) continue;
        previous[i] = member->shot_index;
        if (member->state == 0x80 && !member->shot_index) {
            bc_shot_index(&indices[i], &member->weapons);
            member->shot_index = &indices[i];
        }
    }
    bc_actor_common_into(event, actor, p, data, count);
    for (unsigned char i = 0; i < players; i++)
        if (members[i]) members[i]->shot_index = previous[i];
}

static void stage_event_execute(BcStageEventResult *result, BcStage *s,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *p,
    const BcStageEventData *data, unsigned char *count, unsigned short handler)
{
    *result = (BcStageEventResult){0};
    result->slot = -1;
    result->handler = handler;
    if (!result->handler) return;
    if (data->prepare_event) data->prepare_event(result->handler);
    unsigned short canonical = result->handler - data->relocation;
    if (bc_audio_stage_handler(canonical)) {
        if (!data->audio) { result->status = 2; return; }
        if (!data->audio->state) bc_audio_request(data->audio, &data->data, result->handler);
        if (data->audio->handler != result->handler || data->audio->state != 2) {
            result->status = 3; return;
        }
        data->audio->state = 0;
    } else if (result->handler == 0x414c && data->round <= 9) {
        if (!data->palette) { result->status = 2; return; }
        bc_palette_boss(data->palette, &data->data);
    } else if (canonical == 0x8d76) {
        /* Stage cleanup preserves item actors, without running retirement
         * tasks or changing the source's limited-shot counter. */
        for (unsigned char slot = 0; slot < BC_ACTOR_CAPACITY; slot++)
            if (!actors[slot].pickup) actors[slot].body.state = 0;
    } else if ((data->round == 2 && result->handler == 0xaacb) || (data->round == 3 && result->handler == 0xa76e) || (data->round == 4 && result->handler == 0xac50) || (data->round == 5 && result->handler == 0xae4c) || (data->round == 7 && result->handler == 0xb046) || (data->round == 8 && (result->handler == 0xaff2 || result->handler == 0xac32 || result->handler == 0xc18b || result->handler == 0xa8c6 || result->handler == 0xbcf0))) {
        round_three_boss_birth(s, actors, p, data, count, result->handler); result->slot = 0;
    } else if (data->round == 9 && result->handler == 0xa399) {
        final_serpent_birth(actors, p, data, count); result->slot = 0;
    } else if (data->round == 8 && result->handler == 0xc539) {
        round_nine_final_birth(s, actors, p, data, count); result->slot = 0;
    } else if ((data->round == 6 && result->handler == 0xaa0b) || (data->round == 8 && result->handler == 0xb8d4)) {
        round_seven_boss_birth(s, actors, p, data, count); result->slot = 0;
    } else if ((data->round == 1 && result->handler == 0xab95) || (data->round == 8 && result->handler == 0xb384)) {
        round_two_boss_birth(s, actors, p, data, count); result->slot = 0;
    } else if ((!data->round && result->handler == 0xb34b) || (data->round == 8 && result->handler == 0xa574)) {
        s->boss_active = 255;
        for (unsigned char slot = 0; slot < 2; slot++) {
            BcActor *a = &actors[slot];
            unsigned short template_address = (slot ? 0xb4c3 : 0xb4b0) - (data->round == 8 ? 0xdd7 : 0);
            bc_actor_template(a, data->data.bytes + (template_address - data->data.origin), data->boss_base);
            bc_enemy_set_x(&a->body, 0xc8);
            bc_enemy_set_y(&a->body, 0x78);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.damage_lock = 128;
            if (!slot) { a->auxiliary = 1; if (data->round == 8) a->body.score_id = 8; }
            BcActorEvent event = bc_actor_common(a, p, &data->data, count);
            if (!slot) result->actor_event = event;
            else result->second_actor_event = event;
        }
        result->slot = 0;
    } else if (!data->round && result->handler == 0xaa23) {
        /* Round-one checkpoint event $AA23-$AA33. */
        s->checkpoint_x = 9; s->checkpoint_y = 0; s->checkpoint_script = 0xa5dc;
    } else if (data->round == 1 && result->handler == 0xab84) {
        s->checkpoint_x = 9; s->checkpoint_y = 2; s->checkpoint_script = 0xa63f;
    } else if (data->round == 2 && result->handler == 0xaaba) {
        s->checkpoint_x = 0; s->checkpoint_y = 7; s->checkpoint_script = 0xa65d;
    } else if (data->round == 3 && result->handler == 0xa75d) {
        s->checkpoint_x = 9; s->checkpoint_y = 3; s->checkpoint_script = 0xa460;
    } else if (data->round == 4 && result->handler == 0xac3f) {
        s->checkpoint_x = 11; s->checkpoint_y = 4; s->checkpoint_script = 0xa718;
    } else if (data->round == 6 && result->handler == 0xa9fa) {
        s->checkpoint_x = 11; s->checkpoint_y = 6; s->checkpoint_script = 0xa6ef;
    } else if (data->round == 5 && result->handler == 0xac03) {
        s->checkpoint_x = 1; s->checkpoint_y = 7; s->checkpoint_script = 0xa804;
    } else if (data->round == 8 && result->handler == 0xa563) {
        s->checkpoint_x = 11; s->checkpoint_y = 8; s->checkpoint_script = 0xa473;
    } else if (data->round == 8 && result->handler == 0xa552) {
        s->checkpoint_x = 10; s->checkpoint_y = 8; s->checkpoint_script = 0xa45f;
    } else if (data->round == 8 && result->handler == 0xa541) {
        s->checkpoint_x = 9; s->checkpoint_y = 8; s->checkpoint_script = 0xa44b;
    } else if (data->round == 8 && result->handler == 0xa530) {
        s->checkpoint_x = 8; s->checkpoint_y = 8; s->checkpoint_script = 0xa434;
    } else if (data->round == 8 && result->handler == 0xa51f) {
        s->checkpoint_x = 7; s->checkpoint_y = 8; s->checkpoint_script = 0xa426;
    } else if (data->round == 8 && result->handler == 0xa50e) {
        s->checkpoint_x = 6; s->checkpoint_y = 8; s->checkpoint_script = 0xa415;
    } else if (data->round == 8 && result->handler == 0xa4fd) {
        s->checkpoint_x = 5; s->checkpoint_y = 8; s->checkpoint_script = 0xa401;
    } else if (data->round == 8 && result->handler == 0xa4ec) {
        s->checkpoint_x = 4; s->checkpoint_y = 8; s->checkpoint_script = 0xa3ed;
    } else if (data->round == 7 && result->handler == 0xadfd) {
        s->checkpoint_x = 11; s->checkpoint_y = 7; s->checkpoint_script = 0xa6e4;
    } else if (canonical == 0x87d3 || canonical == 0x87df || canonical == 0x87e5) {
        result->slot = bc_actor_spawn_item(actors, 8, canonical == 0x87e5 ? 4 : canonical == 0x87df ? 3 : 1, &data->data,
            0x8908 + data->relocation, 0x8936 + data->relocation, data->item_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (canonical == 0x876d || canonical == 0x875b || canonical == 0x8755) {
        result->slot = bc_actor_spawn_item(actors, 6, canonical == 0x8755 ? 1 : canonical == 0x875b ? 2 : 5, &data->data,
            0x8908 + data->relocation, 0x8936 + data->relocation, data->item_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (canonical == 0x8751 || canonical == 0x8850 || canonical == 0x885a || canonical == 0x8860 || canonical == 0x8866 ||
        (canonical >= 0x8872 && canonical <= 0x8884 && (canonical - 0x8872) % 6 == 0)) {
        result->slot = bc_actor_spawn_item(actors, canonical == 0x8751 ? 6 : 5,
            (canonical == 0x8751 || canonical == 0x8850) ? 0 : canonical == 0x885a ? 2 : canonical == 0x8860 ? 3 : canonical == 0x8866 ? 4 : 6 + (canonical - 0x8872) / 6, &data->data,
            0x8908 + data->relocation, 0x8936 + data->relocation, data->item_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (canonical == 0x883b || canonical == 0x8811 || canonical == 0x880d) {
        if (!p->inventory.life_pickups) {
            result->slot = bc_actor_spawn_item(actors, 9, canonical == 0x880d ? 0 : canonical == 0x8811 ? 1 : 8, &data->data,
                0x8908 + data->relocation, 0x8936 + data->relocation, data->item_base);
            if (result->slot >= 0)
                bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
        }
    } else if (canonical == 0x8790 || canonical == 0x8794) {
        result->slot = bc_actor_spawn_item(actors, 7, canonical == 0x8790 ? 0 : 1,
            &data->data, 0x8908 + data->relocation, 0x8936 + data->relocation, data->item_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (canonical >= 0x879a && canonical <= 0x87c4 && (canonical - 0x879a) % 6 == 0) {
        result->slot = bc_actor_spawn_item(actors, 7, 2 + (canonical - 0x879a) / 6,
            &data->data, 0x8908 + data->relocation, 0x8936 + data->relocation, data->item_base);
        if (result->slot >= 0)
            result->actor_event = bc_actor_common(&actors[result->slot], p, &data->data, count);
    } else if ((data->round == 2 && (result->handler == 0xbb0d || result->handler == 0xbb13)) ||
        (data->round == 5 && (result->handler == 0xb63e || result->handler == 0xb644))) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            bc_actor_template(a, data->data.bytes + (data->round == 5 ? 0xb7fd : 0xbccc) - data->data.origin, data->curve_base);
            bc_enemy_set_x(&a->body, 0x80); bc_enemy_set_y(&a->body, 0xf0);
            a->wait = result->handler == 0xbb13 || result->handler == 0xb644;
            bc_enemy_set_vx(&a->body, a->wait ? 1024 : -1024); bc_enemy_set_vy(&a->body, 0);
            if (a->wait) a->body.animation = data->round == 5 ? 0xb831 : 0xbd00;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if ((data->round == 2 && result->handler >= 0xb9e2 && result->handler <= 0xb9ee &&
        (result->handler - 0xb9e2) % 6 == 0) || (data->round == 3 && result->handler >= 0xb9c6 &&
        result->handler <= 0xb9de && (result->handler - 0xb9c6) % 6 == 0)) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            const unsigned char *bytes = data->data.bytes;
            unsigned char index = data->round == 3 ? 3 + (result->handler - 0xb9c6) / 6 : 5 + (result->handler - 0xb9e2) / 6;
            const unsigned char *position = bytes + (data->round == 3 ? 0xba9d : 0xbaad) - data->data.origin + index * 7;
            bc_actor_template(a, bytes + (data->round == 3 ? 0xba8a : 0xba9a) - data->data.origin, data->fixed_turret_base);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->phase = 50; a->wait = position[0];
            bc_enemy_set_x(&a->body, (position[1] | ((unsigned short)position[2] << 8)));
            bc_enemy_set_y(&a->body, (position[3] | ((unsigned short)position[4] << 8)));
            a->body.animation = position[5] | ((unsigned short)position[6] << 8);
            if (index >= 4) a->body.attributes = (a->body.attributes & 0xff00) | 0x8b;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if ((data->round == 3 && (result->handler == 0xb3e7 || result->handler == 0xb3eb || result->handler == 0xb3f1)) ||
        (data->round == 7 && (result->handler == 0xb967 || result->handler == 0xb96b || result->handler == 0xb971))) {
        if (!data->random_state) { result->status = 2; return; }
        result->wave_size = 5;
        result->slot = formation_birth(actors, p, data, count,
            (result->handler == 0xb3e7 || result->handler == 0xb967) ? 0 :
            (result->handler == 0xb3eb || result->handler == 0xb96b) ? 8 : 16);
    } else if (data->round == 2 && result->handler == 0xb881) {
        if (!data->random_state) { result->status = 2; return; }
        result->wave_size = 2;
        result->slot = paired_birth(actors, p, data, count);
    } else if (data->round == 2 && result->handler >= 0xb4ae && result->handler <= 0xb4ba &&
        (result->handler - 0xb4ae) % 6 == 0) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            const unsigned char *bytes = data->data.bytes;
            const unsigned char *position = bytes + 0xb58b - data->data.origin +
                (5 + (result->handler - 0xb4ae) / 6) * 5;
            bc_actor_template(a, bytes + 0xb578 - data->data.origin, data->hopper_base);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->phase = 50; a->turn = 0; a->wait = position[0];
            bc_enemy_set_x(&a->body, (position[1] | ((unsigned short)position[2] << 8)));
            bc_enemy_set_y(&a->body, (position[3] | ((unsigned short)position[4] << 8)));
            if (a->wait) a->body.animation = 0xb5bc;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 6 && (
        (result->handler >= 0xb5e0 && result->handler <= 0xb5fe && (result->handler - 0xb5e0) % 6 == 0) ||
        (result->handler >= 0xb4ad && result->handler <= 0xb4d1 && (result->handler - 0xb4ad) % 6 == 0) ||
        (result->handler >= 0xb2b1 && result->handler <= 0xb2d5 && (result->handler - 0xb2b1) % 6 == 0))) {
        unsigned char kind = result->handler >= 0xb5e0 ? 0 : result->handler >= 0xb4ad ? 1 : 2;
        static const unsigned short starts[3] = {0xb5e0,0xb4ad,0xb2b1};
        static const unsigned short templates[3] = {0xb6bc,0xb58d,0xb370};
        static const unsigned short positions[3] = {0xb6cf,0xb5a0,0xb383};
        static const unsigned short animations[3] = {0xb700,0xb5d1,0xb3b4};
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            unsigned char index = (kind ? 1 : 2) + (result->handler - starts[kind]) / 6;
            const unsigned char *position = data->data.bytes + positions[kind] - data->data.origin + index * 5;
            bc_actor_template(a, data->data.bytes + templates[kind] - data->data.origin, data->turret_bases[kind]);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->phase = 50; a->wait = position[0];
            if (!kind) a->turn = 0;
            bc_enemy_set_x(&a->body, (position[1] | ((unsigned short)position[2] << 8)));
            bc_enemy_set_y(&a->body, (position[3] | ((unsigned short)position[4] << 8)));
            if (a->wait) a->body.animation = animations[kind];
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 7 && (result->handler == 0xbc76 ||
        (result->handler >= 0xbc7a && result->handler <= 0xbc9e && (result->handler - 0xbc7a) % 6 == 0))) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            const unsigned char *bytes = data->data.bytes;
            unsigned char index = result->handler == 0xbc76 ? 0 : 1 + (result->handler - 0xbc7a) / 6;
            const unsigned char *xy = bytes + 0xbd72 + index * 4 - data->data.origin;
            bc_actor_template(a, bytes + 0xbd5f - data->data.origin, data->fixed_turret_base);
            bc_enemy_set_x(&a->body, (xy[0] | ((unsigned short)xy[1] << 8)));
            bc_enemy_set_y(&a->body, (xy[2] | ((unsigned short)xy[3] << 8)));
            a->direction = bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body));
            const unsigned char *animation = bytes + 0xbd92 + a->direction * 2 - data->data.origin;
            a->body.animation = animation[0] | ((unsigned short)animation[1] << 8);
            const unsigned char *vector = bytes + 0x8262 + a->speed - data->data.origin;
            const unsigned char *v = bytes + (vector[0] | ((unsigned short)vector[1] << 8)) + a->direction * 4 - data->data.origin;
            bc_enemy_set_vx(&a->body, v[0] | ((unsigned short)v[1] << 8)); bc_enemy_set_vy(&a->body, v[2] | ((unsigned short)v[3] << 8));
            a->wait = 40;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 5 && result->handler >= 0xb836 && result->handler <= 0xb848 && (result->handler - 0xb836) % 6 == 0) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_jumper(actors, ((result->handler - 0xb836) / 6) * 40,
            &data->data, 0xba57, data->terrain_jumper_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (data->round == 5 && (result->handler == 0xba82 || result->handler == 0xba88)) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_hopper(actors, result->handler == 0xba82 ? 240 : 32,
            &data->data, 0xbbc5, data->terrain_hopper_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if ((data->round == 5 && result->handler == 0xac14) || (data->round == 7 && result->handler == 0xae0e)) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            bc_actor_template(a, data->data.bytes + (data->round == 7 ? 0xafb6 : 0xadbc) - data->data.origin, data->orbiter_base);
            bc_enemy_set_x(&a->body, 0x110);
            bc_enemy_set_y(&a->body, 0x70);
            bc_enemy_set_vx(&a->body, -512); bc_enemy_set_vy(&a->body, 0);
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 2 && (result->handler == 0xb2e3 ||
        (result->handler >= 0xb2e7 && result->handler <= 0xb30b && (result->handler - 0xb2e7) % 6 == 0))) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_reaim(actors,
            result->handler == 0xb2e3 ? 0 : 1 + (result->handler - 0xb2e7) / 6,
            p, &data->data, data->launcher_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if ((data->round == 2 && result->handler >= 0xae5d && result->handler <= 0xae75 &&
        (result->handler - 0xae5d) % 6 == 0) || (data->round == 3 &&
        result->handler >= 0xad65 && result->handler <= 0xad7d && (result->handler - 0xad65) % 6 == 0) || (data->round == 4 &&
        result->handler >= 0xb235 && result->handler <= 0xb24d && (result->handler - 0xb235) % 6 == 0) || (data->round == 5 &&
        result->handler >= 0xb1b8 && result->handler <= 0xb1d0 && (result->handler - 0xb1b8) % 6 == 0) || (data->round == 6 &&
        result->handler >= 0xae27 && result->handler <= 0xae3f && (result->handler - 0xae27) % 6 == 0) || (data->round == 7 &&
        result->handler >= 0xb4e1 && result->handler <= 0xb4f9 && (result->handler - 0xb4e1) % 6 == 0)) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_curve(actors, 56 + 32 * ((result->handler - (data->round == 7 ? 0xb4e1 : data->round == 6 ? 0xae27 : data->round == 5 ? 0xb1b8 : data->round == 4 ? 0xb235 : data->round == 3 ? 0xad65 : 0xae5d)) / 6),
            &data->data, data->round == 7 ? 0xb65e : data->round == 6 ? 0xafa4 : data->round == 5 ? 0xb335 : data->round == 4 ? 0xb3b2 : data->round == 3 ? 0xaee2 : 0xafda, data->fast_curve_base);
        if (result->slot >= 0) {
            if (data->round == 6)
                curve_birth_contact(&result->actor_event, &actors[result->slot], p, &data->data, count);
            else bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
        }
    } else if ((data->round == 4 && (result->handler == 0xba88 || result->handler == 0xba8e ||
        result->handler == 0xba94 || result->handler == 0xba9a)) ||
        (data->round == 5 && result->handler >= 0xbbf0 && result->handler <= 0xbc02 && (result->handler - 0xbbf0) % 6 == 0) ||
        (data->round == 6 && result->handler >= 0xbc4a && result->handler <= 0xbc5c && (result->handler - 0xbc4a) % 6 == 0) ||
        (data->round == 7 && result->handler >= 0xc0e5 && result->handler <= 0xc0f7 && (result->handler - 0xc0e5) % 6 == 0)) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            unsigned char index = data->round == 7 ? (result->handler - 0xc0e5) / 6 : data->round == 6 ? (result->handler - 0xbc4a) / 6 : data->round == 5 ? (result->handler - 0xbbf0) / 6 : (result->handler - 0xba88) / 6;
            const unsigned char *xy = data->data.bytes + (data->round == 7 ? 0xc2c6 : data->round == 6 ? 0xbe2b : data->round == 5 ? 0xbdd1 : 0xbc69) + index * 4 - data->data.origin;
            bc_actor_template(a, data->data.bytes + (data->round == 7 ? 0xc28b : data->round == 6 ? 0xbdf0 : data->round == 5 ? 0xbd96 : 0xbc2e) - data->data.origin, data->hopper_base);
            unsigned short x = xy[0] | ((unsigned short)xy[1] << 8);
            bc_enemy_set_x(&a->body, x);
            bc_enemy_set_y(&a->body, (xy[2] | ((unsigned short)xy[3] << 8)));
            bc_enemy_set_vy(&a->body, 0); bc_enemy_set_vx(&a->body, (x & 0x8000) ? 512 : -512);
            if (!(x & 0x8000)) a->body.animation = data->round == 7 ? 0xc29e : data->round == 6 ? 0xbe03 : data->round == 5 ? 0xbda9 : 0xbc41;
            unsigned char player_x = p->x >> 8;
            a->phase = bc_enemy_vx(&a->body) > 0 ? player_x < 80 : player_x >= 176;
            a->wait = a->phase ? 100 : 20;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if ((data->round == 4 && result->handler >= 0xb97b && result->handler <= 0xb993 &&
        (result->handler - 0xb97b) % 6 == 0) || (data->round == 6 && result->handler >= 0xbb3d &&
        result->handler <= 0xbb55 && (result->handler - 0xbb3d) % 6 == 0)) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_launcher(actors, 48 + 48 * ((result->handler - (data->round == 6 ? 0xbb3d : 0xb97b)) / 6),
            &data->data, data->round == 6 ? 0xbc1c : 0xba5a, data->launcher_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (data->round == 3 && (result->handler == 0xb1eb ||
        (result->handler >= 0xb1ef && result->handler <= 0xb213 && (result->handler - 0xb1ef) % 6 == 0))) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            unsigned char index = result->handler == 0xb1eb ? 0 : 1 + (result->handler - 0xb1ef) / 6;
            const unsigned char *pos = data->data.bytes + 0xb2c1 - data->data.origin + index*5;
            bc_actor_template(a, data->data.bytes + 0xb2ae - data->data.origin, data->launcher_base);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->phase = 50; a->wait = pos[0];
            bc_enemy_set_x(&a->body, (pos[1] | ((unsigned short)pos[2] << 8)));
            bc_enemy_set_y(&a->body, (pos[3] | ((unsigned short)pos[4] << 8)));
            if (a->wait) a->body.animation = 0xb2f2;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 3 && result->handler == 0xbb03) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            bc_actor_template(a, data->data.bytes + 0xbc40 - data->data.origin, data->hopper_base);
            bc_enemy_set_x(&a->body, 0x20);
            bc_enemy_set_y(&a->body, 0xfff0);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->wait = 1;
            a->body.animation = 0xbc5c;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if ((data->round == 3 && (result->handler == 0xaf18 || result->handler == 0xaf1e)) ||
        (data->round == 4 && (result->handler == 0xb3e8 || result->handler == 0xb3ee)) ||
        (data->round == 5 && (result->handler == 0xb36b || result->handler == 0xb371)) ||
        (data->round == 6 && (result->handler == 0xafda || result->handler == 0xafe0)) ||
        (data->round == 7 && (result->handler == 0xb694 || result->handler == 0xb69a)) ||
        (data->round == 8 && (result->handler == 0xc91e || result->handler == 0xc924))) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_hover(actors, (result->handler == 0xaf18 || result->handler == 0xb3e8 || result->handler == 0xb36b || result->handler == 0xafda || result->handler == 0xb694 || result->handler == 0xc91e) ? 80 : 160,
            &data->data, data->round == 8 ? 0xc9dd : data->round == 7 ? 0xb753 : data->round == 6 ? 0xb099 : data->round == 5 ? 0xb42a : data->round == 4 ? 0xb4a7 : 0xafd7, data->hover_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (data->round == 2 && (result->handler == 0xb010 || result->handler == 0xb016)) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_hover(actors, result->handler == 0xb010 ? 80 : 160,
            &data->data, 0xb0cf, data->hover_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if ((data->round == 1 && (result->handler == 0xba7c || result->handler == 0xba80)) ||
        (data->round == 2 && (result->handler == 0xb5c1 || result->handler == 0xb5c5)) ||
        (data->round == 3 && (result->handler == 0xb6f6 || result->handler == 0xb6fa)) ||
        (data->round == 4 && (result->handler == 0xb6bb || result->handler == 0xb6bf)) ||
        (data->round == 6 && (result->handler == 0xb705 || result->handler == 0xb709)) ||
        (data->round == 7 && (result->handler == 0xbe25 || result->handler == 0xbe29))) {
        result->wave_size = 8;
        result->slot = segment_birth(actors, p, data, count, result->handler == (data->round == 7 ? 0xbe29 : data->round == 6 ? 0xb709 : data->round == 4 ? 0xb6bf : data->round == 3 ? 0xb6fa : data->round == 2 ? 0xb5c5 : 0xba80));
    } else if ((data->round == 1 && result->handler == 0xbd3c) || (data->round == 6 && result->handler == 0xb9c5)) {
        result->wave_size = 4;
        result->slot = ceiling_birth(actors, p, data, count);
    } else if (data->round == 1 && result->handler >= 0xb31c && result->handler <= 0xb334 &&
        (result->handler - 0xb31c) % 6 == 0) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_curve(actors, 56 + 32 * ((result->handler - 0xb31c) / 6),
            &data->data, 0xb499, data->fast_curve_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if ((data->round == 1 && (result->handler == 0xb0e5 || result->handler == 0xb0eb)) ||
        (data->round == 3 && (result->handler == 0xab2e || result->handler == 0xab34)) ||
        (data->round == 4 && (result->handler == 0xaffe || result->handler == 0xb004))) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            bc_actor_template(a, data->data.bytes + (data->round == 4 ? 0xb1f8 : data->round == 3 ? 0xad28 : 0xb2df) - data->data.origin,
                data->round >= 3 ? data->walker_base : data->hopper_base);
            a->wait = result->handler == 0xb0eb || result->handler == 0xab34 || result->handler == 0xb004;
            a->body.x = (a->wait ? 0x01100000u : 0xfff00000u) | (a->body.x & 0xff00);
            bc_enemy_set_y(&a->body, 0x40);
            bc_enemy_set_vx(&a->body, 0); bc_enemy_set_vy(&a->body, 1024); a->phase = 16;
            walker_birth_update(&result->actor_event, s, actors, result->slot, p, data, count);
        }
    } else if ((data->round == 1 && result->handler >= 0xb5bf && result->handler <= 0xb5dd &&
        (result->handler - 0xb5bf) % 6 == 0) ||
        (data->round == 2 && result->handler >= 0xb100 && result->handler <= 0xb11e &&
        (result->handler - 0xb100) % 6 == 0) ||
        (data->round == 3 && result->handler >= 0xb008 && result->handler <= 0xb026 &&
        (result->handler - 0xb008) % 6 == 0) ||
        (data->round == 4 && result->handler >= 0xb4d8 && result->handler <= 0xb4f6 && (result->handler - 0xb4d8) % 6 == 0) ||
        (data->round == 5 && result->handler >= 0xb45b && result->handler <= 0xb479 && (result->handler - 0xb45b) % 6 == 0) ||
        (data->round == 6 && result->handler >= 0xb0ca && result->handler <= 0xb0e8 && (result->handler - 0xb0ca) % 6 == 0) ||
        (data->round == 7 && result->handler >= 0xb784 && result->handler <= 0xb7a2 && (result->handler - 0xb784) % 6 == 0)) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            unsigned char position = (result->handler - (data->round == 7 ? 0xb784 : data->round == 6 ? 0xb0ca : data->round == 5 ? 0xb45b : data->round == 4 ? 0xb4d8 : data->round == 3 ? 0xb008 : data->round == 2 ? 0xb100 : 0xb5bf)) / 6;
            const unsigned char *xy = data->data.bytes + (data->round == 7 ? 0xb95b : data->round == 6 ? 0xb2a1 : data->round == 5 ? 0xb632 : data->round == 4 ? 0xb6af : data->round == 3 ? 0xb1df : data->round == 2 ? 0xb2d7 : 0xb796) - data->data.origin + position * 2;
            bc_actor_template(a, data->data.bytes + (data->round == 7 ? 0xb915 : data->round == 6 ? 0xb25b : data->round == 5 ? 0xb5ec : data->round == 4 ? 0xb669 : data->round == 3 ? 0xb199 : data->round == 2 ? 0xb291 : 0xb750) - data->data.origin, data->jumper_base);
            bc_enemy_set_x(&a->body, xy[0]);
            bc_enemy_set_y(&a->body, xy[1]);
            bc_enemy_set_vx(&a->body, 0); bc_enemy_set_vy(&a->body, position < 3 ? 512 : -512);
            a->phase = 1; a->wait = 0; a->fired = 10; a->dash_started = 0;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 1 && (result->handler == 0xb94f ||
        (result->handler >= 0xb953 && result->handler <= 0xb977 && (result->handler - 0xb953) % 6 == 0))) {
        result->wave_size = 1;
        result->slot = bc_actor_allocate(actors, 0);
        if (result->slot >= 0) {
            BcActor *a = &actors[result->slot];
            const unsigned char *bytes = data->data.bytes;
            const unsigned char *position = bytes + (0xba46 - data->data.origin) +
                (result->handler == 0xb94f ? 0 : 1 + (result->handler - 0xb953) / 6) * 5;
            bc_actor_template(a, bytes + (0xba33 - data->data.origin), data->launcher_base);
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->phase = 50; a->wait = position[0];
            bc_enemy_set_x(&a->body, (position[1] | ((unsigned short)position[2] << 8)));
            bc_enemy_set_y(&a->body, (position[3] | ((unsigned short)position[4] << 8)));
            if (a->wait) a->body.animation = 0xba77;
            bc_actor_common_into(&result->actor_event, a, p, &data->data, count);
        }
    } else if (data->round == 1 && (result->handler == 0xb4cf || result->handler == 0xb4d5)) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_hover(actors, result->handler == 0xb4cf ? 80 : 160,
            &data->data, 0xb58e, data->hover_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (data->round == 1 && result->handler >= 0xb7a2 && result->handler <= 0xb7ba &&
        (result->handler - 0xb7a2) % 6 == 0) {
        result->wave_size = 1;
        result->slot = bc_actor_spawn_curve(actors, 56 + 32 * ((result->handler - 0xb7a2) / 6),
            &data->data, 0xb91f, data->curve_base);
        if (result->slot >= 0)
            bc_actor_common_into(&result->actor_event, &actors[result->slot], p, &data->data, count);
    } else if (!bc_stage_control(s, canonical)) {
        unsigned short base;
        if (data->round) { result->status = 2; return; }
        switch (result->handler) {
        case 0xaa34: case 0xaa3a: case 0xaa40: case 0xaa46: case 0xaa4c:
            base = data->fast_curve_base; break;
        case 0xabe7: case 0xabed: base = data->hover_base; break;
        case 0xacd7: case 0xacdd: case 0xace3: case 0xace9: case 0xacef:
            base = data->curve_base; break;
        case 0xae84: case 0xae8a: case 0xae90: case 0xae96:
            base = data->jumper_base; break;
        case 0xb0d0: case 0xb0d6: base = data->hopper_base; break;
        case 0xb23e: case 0xb244: case 0xb24a: case 0xb250: case 0xb256:
            base = data->launcher_base; break;
        default: result->status = 2; return;
        }
        result->wave_size = 1;
        result->slot = bc_actor_stage_birth(actors, result->handler, &data->data, base);
        if (result->slot >= 0)
            result->actor_event = bc_actor_common(&actors[result->slot], p, &data->data, count);
    }
    if (result->slot >= 0 && !(data->round == 9 && result->handler == 0xa399) && !(data->round == 8 && (result->handler == 0xc539 || result->handler == 0xb8d4 || result->handler == 0xb384 || result->handler == 0xaff2 || result->handler == 0xac32 || result->handler == 0xc18b || result->handler == 0xa8c6 || result->handler == 0xbcf0)) && !(data->round == 7 && (result->handler == 0xbe25 || result->handler == 0xbe29 || result->handler == 0xb967 || result->handler == 0xb96b || result->handler == 0xb971 || result->handler == 0xb046)) && !(data->round == 6 && (result->handler == 0xb9c5 || result->handler == 0xaa0b || result->handler == 0xb705 || result->handler == 0xb709)) && !(data->round == 5 && result->handler == 0xae4c) && !(data->round == 4 && (result->handler == 0xb6bb || result->handler == 0xb6bf || result->handler == 0xac50)) && !(data->round == 3 && (result->handler == 0xb6f6 || result->handler == 0xb6fa ||
        result->handler == 0xb3e7 || result->handler == 0xb3eb || result->handler == 0xb3f1 || result->handler == 0xa76e)) && !(data->round == 2 && (result->handler == 0xaacb || result->handler == 0xb881 || result->handler == 0xb5c1 || result->handler == 0xb5c5)) &&
        !(data->round == 1 && (result->handler == 0xbd3c || result->handler == 0xba7c || result->handler == 0xba80 || result->handler == 0xab95))) {
        stage_birth_effects(data, result->slot, &result->actor_event);
        if ((!data->round && result->handler == 0xb34b) || (data->round == 8 && result->handler == 0xa574))
            stage_birth_effects(data, 1, &result->second_actor_event);
    }
    bc_stage_event_complete(s);
    result->status = 1;
    return;
}

BcStageEventResult bc_runtime_stage_event(BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player,
    const BcStageEventData *data, unsigned char *count)
{
    unsigned short handler = bc_stage_event_next(stage, &data->data);
    BcStageEventResult result;
    stage_event_execute(&result, stage, actors, player, data, count, handler);
    return result;
}

BcStageEventResult bc_runtime_stage_replay(const BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player,
    const BcStageEventData *data, unsigned char *count, unsigned short script)
{
    BcStage copy = *stage;
    copy.script = script;
    const unsigned char *record = data->data.bytes + (unsigned short)(script - data->data.origin);
    unsigned short handler = record[1] | ((unsigned short)record[2] << 8);
    BcStageEventResult result;
    stage_event_execute(&result, &copy, actors, player, data, count, handler);
    return result;
}

/* Keep the actor loop's temporaries out of the scene/player stack frame while
 * allowing the individual actor paths to specialize inside this loop. */
static inline unsigned char __attribute__((always_inline)) actor_loop_core(BcActor actors[BC_ACTOR_CAPACITY], unsigned char first,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped,
    BcActorEventSink sink, void *context, unsigned char round, unsigned char launcher_idle_path)
{
    /* Common-only updates cannot emit child/family events. Keep their empty
     * envelope for the pass; the common task overwrites actor_event each time.
     * Sinks receive const events and must not retain this temporary pointer. */
    unsigned char direct_terrain = &bc_round8_terrain && bc_round8_solid &&
        data->terrain.cells && data->terrain.cells == bc_round8_terrain.cells &&
        data->terrain.attributes == bc_round8_terrain.attributes;
    const unsigned short rain_handler = round == 5 ? 0xb17c : round == 8 ? 0xabf6 : 0;
    const unsigned short train_handler = round == 1 ? 0xbb7e : round == 3 ? 0xb7f8 :
        data->relocation == -535 ? (round == 4 ? 0xb7bd : round == 6 ? 0xb807 : 0) : 0;
    BcActorStepEvent simple;
    unsigned char effect_sink = sink == bc_runtime_actor_events;
    simple.child_event = (BcActorEvent){0}; simple.child_slot = -1;
    simple.setup_sound = simple.fire_requested = simple.extra_count = 0;
    simple.boss_defeat = 0; simple.boss_center_y = 0; simple.handled = 1;
    ENEMY_PASS_INDEX(BcActor, unsigned char, actor, slot, actors, first,
                     BC_ACTOR_CAPACITY, body.state,
        BcActorStepEvent event;
        unsigned short handler = actor->body.state == 0x80 ? actor->routine : actor->death_routine;
        unsigned char rain = rain_handler && handler == rain_handler &&
            actor->body.state == 0x80 && data->random_state;
        if (handler == 0x9eb1 || rain) {
            /* Simple projectiles/effects need no family AI dispatch. Keep the
             * same event contract and common-task order for the event sink. */
            bc_actor_scroll(actor, dx, dy, stopped);
            /* Check rain reversal after scrolling, using the high Y byte.
             * Common motion still runs in the same update. */
            if (rain && (actor->body.y & 0xff000000u)) {
                bc_enemy_set_vx(&actor->body, 0); bc_enemy_set_vy(&actor->body, 512);
                actor->routine = 0x9eb1;
            }
common_actor_update:
            bc_actor_common_into(&simple.actor_event, actor, p, &data->data, count);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
            continue;
        } else if (round == 2 && actor->body.state == 0x80 &&
                   (handler == 0xb359 || handler == 0xb396)) {
            /* Re-aiming only changes the actor/common event; the same empty
             * child envelope is valid for every actor in this pass. */
            bc_actor_scroll(actor, dx, dy, stopped);
            bc_actor_reaim_common(&simple.actor_event, actor, p, &data->data, count);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
            continue;
        } else if (actor->body.state == 0x80 && handler < 0xa000) {
            /* Normalize once for both bullet families; retain the low-handler
             * guard so round-specific family overrides keep precedence. */
            unsigned short canonical = handler - data->relocation;
            if (canonical == 0x8a61 || canonical == 0x8b17) {
                bc_actor_scroll(actor, dx, dy, stopped);
                if (canonical == 0x8a61) {
                    bc_actor_straight_common_into(&simple.actor_event, actor, p, data, count);
                } else {
                    if (direct_terrain) bc_actor_homing_map_into(&simple.actor_event, actor, p, data, count, bc_round8_solid);
                    else bc_actor_homing_common_into(&simple.actor_event, actor, p, data, count);
                }
                if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                    simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
                continue;
            }
            /* Between drift/appearance changes, moving pickups only tick two
             * timers. Preserve scroll, common contacts and event order; keep
             * transition ticks and custom layouts in the full dispatcher. */
            if (round != 7 && canonical == 0x86f0 && data->relocation == -535 &&
                actor->wait != 1 && actor->turn != 1) {
                bc_actor_scroll(actor, dx, dy, stopped);
                actor->wait--; actor->turn--;
                goto common_actor_update;
            }
        }
        /* Enabled only in the separately compiled Round 7 loop. Other loops
         * eliminate this branch entirely. Transition ticks retain dispatch. */
        if (launcher_idle_path && actor->body.state == 0x80 && handler == 0xbb8e &&
            actor->wait != 1 && data->relocation == -535) {
            bc_actor_scroll(actor, dx, dy, stopped);
            actor->wait--;
            goto common_actor_update;
        }
        /* Idle dome and hovering-enemy tasks only count down timers.
         * Firing/transition ticks retain the full family dispatcher and its
         * source-ordered RNG/child updates. Custom resource layouts also
         * retain the original handler precedence. */
        if ((round == 3 || round == 5 || round == 6) && actor->body.state == 0x80 &&
            actor->phase != 1 && data->relocation == -535 && data->random_state) {
            /* Burst turrets share the idle countdown, but keep firing ticks
             * in the family dispatcher for ordered child creation. */
            if (round == 6 && handler == 0xb65c) {
                bc_actor_scroll(actor, dx, dy, stopped);
                actor->phase--;
                goto common_actor_update;
            }
            unsigned char hover = handler == (round == 3 ? 0xaf7c : round == 5 ? 0xb3cf : 0xb03e) && actor->wait != 1;
            if (hover || (round == 3 && handler == 0xba46)) {
                bc_actor_scroll(actor, dx, dy, stopped);
                actor->phase--;
                if (hover) actor->wait--;
                bc_actor_common_into(&simple.actor_event, actor, p, &data->data, count);
                if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                    simple.actor_event.score_pending || simple.actor_event.sound))
                    sink(slot, &simple, context);
                continue;
            }
        }
        if (((round == 5 && handler == 0xb4d2) || (round == 4 && handler == 0xb54f)) &&
            actor->body.state == 0x80 &&
            data->relocation == -535 && data->random_state) {
            bc_actor_scroll(actor, dx, dy, stopped);
            bc_actor_diver_common_into(&simple, actors, slot, p, data, count, maximum);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.actor_event.score_pending || simple.actor_event.sound ||
                simple.child_event.score_pending || simple.child_event.sound))
                sink(slot, &simple, context);
            if (simple.fire_requested) {
                simple.child_event = (BcActorEvent){0};
                simple.child_slot = -1; simple.fire_requested = 0;
            }
            continue;
        }
        /* Walker bursts have ordered extra events. Reset their count after
         * consumption so following actors reuse a clean envelope. */
        if (round == 4 && actor->body.state == 0x80 && data->relocation == -535 &&
            data->random_state && (handler == 0xb050 || handler == 0xb0bf ||
            handler == 0xb189 || handler == 0xb1ea)) {
            bc_actor_scroll(actor, dx, dy, stopped);
            bc_actor_walker_common_into(&simple, actors, slot, p, data, count, maximum, handler);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.extra_count || simple.actor_event.score_pending || simple.actor_event.sound))
                sink(slot, &simple, context);
            simple.extra_count = simple.fire_requested = 0;
            continue;
        }
        /* Round-two/four/five/seven trains share the same ordered child-envelope
         * contract as the round-eight direct path. Bullet precedence above
         * remains unchanged for relocated resource sets. */
        if (actor->body.state == 0x80 &&
            ((train_handler && handler == train_handler) ||
             /* Round-one curves have the same single-child event contract.
              * Custom relocated resources retain general dispatch priority. */
             (round == 0 && data->relocation == 0 &&
              (handler == 0xad31 || handler == 0xae2b || handler == 0xaa8e || handler == 0xab88)) ||
             (round == 7 && (handler == 0xb53b || handler == 0xb635 || (handler == 0xbf27 &&
              (unsigned short)(handler - data->relocation) != 0x8a61 &&
              (unsigned short)(handler - data->relocation) != 0x8b17))))) {
            bc_actor_scroll(actor, dx, dy, stopped);
            if (handler == 0xbf27 || handler == train_handler)
                bc_actor_segment_common_into(&simple, actor, slot, p, data, count, maximum);
            else bc_actor_curve_common_into(&simple, actor, slot, p, data, count, maximum);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.actor_event.score_pending || simple.actor_event.sound ||
                simple.child_event.score_pending || simple.child_event.sound)) sink(slot, &simple, context);
            if (simple.fire_requested) {
                simple.child_event = (BcActorEvent){0};
                simple.child_slot = -1; simple.fire_requested = 0;
            }
            continue;
        }
        /* Round-two turret resources use relocation -535. Keep custom
         * resource sets in the general dispatcher to preserve precedence. */
        if (round == 1 && actor->body.state == 0x80 && handler == 0xb9d2 &&
            data->relocation == -535 && data->random_state) {
            bc_actor_scroll(actor, dx, dy, stopped);
            bc_actor_turret_common_into(&event, actors, slot, p, data, count, maximum);
        } else {
            bc_actor_step_into(&event, actors, slot, p, data, count, maximum, dx, dy, stopped);
        }
        if (!event.handled) return slot;
        if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
            event.extra_count || event.boss_defeat || event.setup_sound ||
            event.actor_event.score_pending || event.actor_event.sound ||
            event.child_event.score_pending || event.child_event.sound))
            sink(slot, &event, context);
    );
    return BC_ACTOR_CAPACITY;
}

static unsigned char __attribute__((noinline)) general_actor_loop(BcActor actors[BC_ACTOR_CAPACITY], unsigned char first,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped,
    BcActorEventSink sink, void *context)
{
    return actor_loop_core(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context, data->round, 0);
}

static unsigned char __attribute__((noinline)) seventh_actor_loop(BcActor actors[BC_ACTOR_CAPACITY], unsigned char first,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped,
    BcActorEventSink sink, void *context)
{
    return actor_loop_core(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context, 6, 1);
}

static unsigned char __attribute__((noinline)) eighth_actor_loop(BcActor actors[BC_ACTOR_CAPACITY], unsigned char first,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped,
    BcActorEventSink sink, void *context)
{
    return actor_loop_core(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context, 7, 0);
}

/* The uncommon final-round family path owns its large event envelope. */
static unsigned char __attribute__((noinline)) final_actor_fallback(
    BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot, BcWorldPlayer *p,
    const BcActorStepData *data, unsigned char *count, unsigned char maximum,
    signed short dx, signed short dy, unsigned char stopped,
    BcActorEventSink sink, void *context)
{
    BcActorStepEvent event;
    bc_actor_step_into(&event, actors, slot, p, data, count, maximum, dx, dy, stopped);
    if (!event.handled) return 0;
    if (sink) sink(slot, &event, context);
    return 1;
}

/* Select the final-round specialization once per pass, so other rounds do
 * not pay another handler test for each actor. All uncommon paths still use
 * the general task implementation and its complete event envelope. */
static unsigned char __attribute__((noinline)) final_actor_loop(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char first, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, signed short dx, signed short dy,
    unsigned char stopped, BcActorEventSink sink, void *context)
{
    unsigned char direct_terrain = &bc_final_terrain && bc_final_solid &&
        data->terrain.cells && data->terrain.cells == bc_final_terrain.cells &&
        data->terrain.attributes == bc_final_terrain.attributes;
    BcActorStepEvent simple;
    unsigned char effect_sink = sink == bc_runtime_actor_events;
    simple.child_event = (BcActorEvent){0}; simple.child_slot = -1;
    simple.setup_sound = simple.fire_requested = simple.extra_count = 0;
    simple.boss_defeat = 0; simple.boss_center_y = 0; simple.handled = 1;
    ENEMY_PASS_INDEX(BcActor, unsigned char, actor, slot, actors, first,
                     BC_ACTOR_CAPACITY, body.state,
        unsigned short handler = actor->body.state == 0x80 ? actor->routine : actor->death_routine;
        if (handler == 0x9eb1 || (actor->body.state == 0x80 && handler == 0xa446)) {
            bc_actor_scroll(actor, dx, dy, stopped);
            if (handler == 0xa446)
                bc_actor_final_serpent_prepare(actors, slot, p, data, count, &simple);
            bc_actor_common_into(&simple.actor_event, actor, p, &data->data, count);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.extra_count || simple.actor_event.score_pending || simple.actor_event.sound))
                sink(slot, &simple, context);
            simple.fire_requested = simple.extra_count = 0;
        } else if (actor->body.state == 0x80 &&
                   handler == (unsigned short)(0x8a61 + data->relocation)) {
            bc_actor_scroll(actor, dx, dy, stopped);
            if (direct_terrain)
                bc_actor_straight_map_into(&simple.actor_event, actor, p, data, count, bc_final_solid);
            else bc_actor_straight_common_into(&simple.actor_event, actor, p, data, count);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
        } else {
            if (!final_actor_fallback(actors, slot, p, data, count, maximum,
                dx, dy, stopped, sink, context)) return slot;
        }
    );
    return BC_ACTOR_CAPACITY;
}

/* Round-three steering uses a compact loop and shares the uncommon family
 * dispatcher with the final round. Keep other rounds' per-actor paths intact. */
static unsigned char __attribute__((noinline)) third_actor_loop(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char first, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, signed short dx, signed short dy,
    unsigned char stopped, BcActorEventSink sink, void *context)
{
    unsigned char direct_terrain = &bc_round8_terrain && bc_round8_solid &&
        data->terrain.cells && data->terrain.cells == bc_round8_terrain.cells &&
        data->terrain.attributes == bc_round8_terrain.attributes;
    BcActorStepEvent simple;
    unsigned char effect_sink = sink == bc_runtime_actor_events;
    simple.child_event = (BcActorEvent){0}; simple.child_slot = -1;
    simple.setup_sound = simple.fire_requested = simple.extra_count = 0;
    simple.boss_defeat = 0; simple.boss_center_y = 0; simple.handled = 1;
    ENEMY_PASS_INDEX(BcActor, unsigned char, actor, slot, actors, first,
                     BC_ACTOR_CAPACITY, body.state,
        unsigned short handler = actor->body.state == 0x80 ? actor->routine : actor->death_routine;
        if (handler == 0x9eb1 || (actor->body.state == 0x80 &&
            (handler == 0xadcf || handler == 0xb359 || handler == 0xb396))) {
            bc_actor_scroll(actor, dx, dy, stopped);
            if (handler == 0xadcf)
                bc_actor_boss3_homing_common(&simple.actor_event, actor, p, data, count);
            else if (handler == 0xb359 || handler == 0xb396)
                bc_actor_reaim_common(&simple.actor_event, actor, p, &data->data, count);
            else bc_actor_common_into(&simple.actor_event, actor, p, &data->data, count);
            if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
        } else {
            unsigned short canonical = handler - data->relocation;
            if (actor->body.state == 0x80 && handler < 0xa000 &&
                (canonical == 0x8a61 || canonical == 0x8b17)) {
                bc_actor_scroll(actor, dx, dy, stopped);
                if (canonical == 0x8a61)
                    bc_actor_straight_common_into(&simple.actor_event, actor, p, data, count);
                else if (direct_terrain)
                    bc_actor_homing_map_into(&simple.actor_event, actor, p, data, count, bc_round8_solid);
                else bc_actor_homing_common_into(&simple.actor_event, actor, p, data, count);
                if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                    simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
            } else if (actor->body.state == 0x80 && data->relocation == -535 &&
                canonical == 0x86f0 && actor->wait != 1 && actor->turn != 1) {
                bc_actor_scroll(actor, dx, dy, stopped);
                actor->wait--; actor->turn--;
                bc_actor_common_into(&simple.actor_event, actor, p, &data->data, count);
                if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                    simple.actor_event.score_pending || simple.actor_event.sound)) sink(slot, &simple, context);
            } else if (actor->body.state == 0x80 &&
                ((handler == 0xb6c3 && canonical != 0x8a61 && canonical != 0x8b17) ||
                 (data->relocation == -535 && (handler == 0xaeb7 || handler == 0xafb1)))) {
                /* Segment trains only add ordered child events when firing.
                 * Reuse the same envelope contract as rounds two and eight. */
                bc_actor_scroll(actor, dx, dy, stopped);
                if (handler == 0xb6c3)
                    bc_actor_segment_common_into(&simple, actor, slot, p, data, count, maximum);
                else bc_actor_curve_common_into(&simple, actor, slot, p, data, count, maximum);
                if (sink && (!effect_sink || !((BcRuntimeEvents *)context)->effects_only ||
                    simple.actor_event.score_pending || simple.actor_event.sound ||
                    simple.child_event.score_pending || simple.child_event.sound))
                    sink(slot, &simple, context);
                if (simple.fire_requested) {
                    simple.child_event = (BcActorEvent){0};
                    simple.child_slot = -1; simple.fire_requested = 0;
                }
            } else if (!final_actor_fallback(actors, slot, p, data, count, maximum,
                dx, dy, stopped, sink, context)) return slot;
        }
    );
    return BC_ACTOR_CAPACITY;
}

static inline unsigned char selected_actor_loop(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char first, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, signed short dx, signed short dy,
    unsigned char stopped, BcActorEventSink sink, void *context)
{
    if (data->round == 9 && data->random_state)
        return final_actor_loop(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context);
    /* The round is fixed for this actor pass. Give the compiler a native
     * round-eight loop without its unrelated round-family branches. */
    if (data->round == 6)
        return seventh_actor_loop(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context);
    if (data->round == 7)
        return eighth_actor_loop(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context);
    if (data->round == 2)
        return third_actor_loop(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context);
    return general_actor_loop(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context);
}

/* Peer indices live only for this actor pass. Keep their storage out of the
 * original 1P stack frame and restore every pointer on early/normal exits. */
static unsigned char __attribute__((noinline)) party_actor_loop(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char first, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, signed short dx, signed short dy,
    unsigned char stopped, BcActorEventSink sink, void *context)
{
    BcParty *party = p->party;
    BcShotIndex indices[BC_PARTY_CAPACITY];
    const BcShotIndex *previous[BC_PARTY_CAPACITY];
    unsigned char policy = 1, shots = 0;
    party->body_bounds_valid = 0;
    party->shot_min_x = party->shot_min_y = 255;
    party->shot_max_x = party->shot_max_y = party->shot_half_x = party->shot_half_y = 0;
    for (unsigned char i = 0; i < party->count; i++) {
        BcWorldPlayer *member = party->players[i];
        if (!member) continue;
        /* Non-live members cannot contact actors in this pass. Avoid building
         * an unused acceleration index; null retains uncached fallback behavior.
         * Restore the caller's pointer after normal and early loop exits. */
        previous[i] = member->shot_index;
        if (member->state == 0x80) {
            if (!member->invulnerability) {
                policy = 3;
                unsigned short x = member->x >> 8, y = member->y >> 8;
                if (!party->body_bounds_valid) {
                    party->body_min_x = party->body_max_x = x;
                    party->body_min_y = party->body_max_y = y;
                    party->body_bounds_valid = 1;
                } else {
                    if (x < party->body_min_x) party->body_min_x = x;
                    if (x > party->body_max_x) party->body_max_x = x;
                    if (y < party->body_min_y) party->body_min_y = y;
                    if (y > party->body_max_y) party->body_max_y = y;
                }
            }
            else if (policy == 1) policy = 2;
            bc_shot_index(&indices[i], &member->weapons);
            if (indices[i].count) {
                shots = 1;
                const BcShotIndex *index = &indices[i];
                if (index->min_x < party->shot_min_x) party->shot_min_x = index->min_x;
                if (index->max_x > party->shot_max_x) party->shot_max_x = index->max_x;
                if (index->min_y < party->shot_min_y) party->shot_min_y = index->min_y;
                if (index->max_y > party->shot_max_y) party->shot_max_y = index->max_y;
                if (index->half_x > party->shot_half_x) party->shot_half_x = index->half_x;
                if (index->half_y > party->shot_half_y) party->shot_half_y = index->half_y;
            }
            member->shot_index = &indices[i];
        } else member->shot_index = 0;
    }
    party->shot_bounds_valid = shots ? 1 : 2;
    party->contact_policy = policy == 2 && !shots ? 4 : policy;
    unsigned char result = selected_actor_loop(actors, first, p, data, count, maximum,
        dx, dy, stopped, sink, context);
    party->contact_policy = party->shot_bounds_valid = party->body_bounds_valid = 0;
    for (unsigned char i = 0; i < party->count; i++)
        if (party->players[i]) party->players[i]->shot_index = previous[i];
    return result;
}

/* Keep the solo index scan out of the actor-pass caller. Multiplayer retains
 * its existing inlining; outlining that shared path regressed long 4P routes. */
static void __attribute__((noinline)) solo_shot_index(BcShotIndex *index,
    const BcWeapons *weapons)
{
    bc_shot_index(index, weapons);
}

unsigned char bc_runtime_actor_loop(BcActor actors[BC_ACTOR_CAPACITY], unsigned char first,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped,
    BcActorEventSink sink, void *context)
{
    if (p->party && p->party->count > 1 && p->party->count <= BC_PARTY_CAPACITY)
        return party_actor_loop(actors, first, p, data, count, maximum, dx, dy, stopped, sink, context);
    BcShotIndex index;
    const BcShotIndex *previous = p->shot_index;
    solo_shot_index(&index, &p->weapons);
    p->shot_index = &index;
    unsigned char result = selected_actor_loop(actors, first, p, data, count, maximum,
        dx, dy, stopped, sink, context);
    p->shot_index = previous;
    return result;
}

/* Keep the effect-delivery stack frame off the common empty-event path. */
static void __attribute__((noinline)) actor_effects(unsigned char slot,
    const BcActorStepEvent *event, void *context)
{
    BcRuntimeEvents *events = context;
    if (event->boss_defeat == 1 && events->defeat)
        bc_runtime_defeat_begin(events->defeat, event->boss_center_y);
    if (events->score) {
        for (unsigned char i = 0; i < event->extra_count; i++)
            if (event->extra_events[i].score_pending)
                bc_score_enqueue(events->score, event->extra_events[i].score_id, events->playing);
        if (event->child_event.score_pending)
            bc_score_enqueue(events->score, event->child_event.score_id, events->playing);
        if (event->actor_event.score_pending)
            bc_score_enqueue(events->score, event->actor_event.score_id, events->playing);
    }
    if (events->next) events->next(slot, event, events->context);
}

void bc_runtime_actor_events(unsigned char slot, const BcActorStepEvent *event, void *context)
{
    BcRuntimeEvents *events = context;
    if (events->effects_only && !event->extra_count && !event->boss_defeat &&
        !event->setup_sound && !event->actor_event.score_pending &&
        !event->actor_event.sound && !event->child_event.score_pending &&
        !event->child_event.sound) return;
    actor_effects(slot, event, context);
}

typedef struct {
    BcPlayerControl *player;
    BcActor *actors;
    BcStage *stage;
    BcActorStepData *data;
    unsigned short pose;
    unsigned char held, pressed, *limited;
    BcRuntimeEvents *events;
    BcPlayResult result;
} BcPlayStep;

static inline __attribute__((always_inline)) unsigned char bc_player_phase(void *context)
{
    BcPlayStep *s = context;
    bc_player_step_into(&s->result.player_event, s->player, s->held, s->pressed,
        s->stage->x >> 8, s->stage->y >> 8, s->stage->dx, s->stage->dy,
        &s->data->terrain, &s->data->data, s->pose);
    return s->result.player_event.control.checkpoint ? 1 : 0;
}

static inline __attribute__((always_inline)) unsigned char bc_actor_phase(void *context)
{
    BcPlayStep *s = context;
    /* BC rules decrement boss cadence immediately before actor traversal. */
    if (s->stage->boss_active && !(s->data->scheduler_counter & 3)) s->stage->boss_active--;
    s->data->boss_active = s->stage->boss_active;
    s->result.next_slot = bc_runtime_actor_loop(s->actors, 0, &s->player->world,
        s->data, s->limited, s->stage->shot_limit, s->stage->dx, s->stage->dy,
        s->stage->stopped, s->events ? bc_runtime_actor_events : 0, s->events);
    return s->result.next_slot != BC_ACTOR_CAPACITY ? 2 : 0;
}

static inline __attribute__((always_inline)) unsigned char bc_trail_phase(void *context)
{
    BcPlayStep *s = context;
    bc_weapons_record_position(&s->player->world.weapons,
        s->player->world.x >> 8, s->player->world.y >> 8);
    return 0;
}

BcPlayResult bc_runtime_play(BcPlayerControl *p, BcActor actors[BC_ACTOR_CAPACITY],
    BcStage *stage, BcActorStepData *data, unsigned short pose_table,
    unsigned char held, unsigned char pressed, unsigned char *count, BcRuntimeEvents *events)
{
    BcPlayStep step = {p, actors, stage, data, pose_table, held, pressed, count,
                      events, {{{0}, {0}, 0}, 0, 0}};
    ENGINE_STEP(step.result.status, 0, bc_player_phase(&step), bc_actor_phase(&step), bc_trail_phase(&step));
    return step.result;
}

void bc_runtime_defeat_begin(BcDefeatSequence *sequence, unsigned short center_y)
{
    sequence->center_y = center_y; sequence->remaining = 50; sequence->wait = 3;
}

unsigned char bc_runtime_defeat_tick(BcDefeatSequence *sequence, unsigned char paused)
{
    if (!sequence->remaining || paused) return 0;
    if (--sequence->wait) return 0;
    sequence->wait = 3;
    return --sequence->remaining ? 1 : 2;
}

BcDefeatTaskResult bc_runtime_defeat_step(BcDefeatSequence *sequence, BcStage *stage,
    BcActor actors[BC_ACTOR_CAPACITY], BcWorldPlayer *player, const BcEnemyData *data,
    signed short relocation, unsigned short sprite_base, unsigned short *random_state,
    unsigned char *limited_count, unsigned char paused, BcRuntimeEvents *events)
{
    BcDefeatTaskResult result = {{0}, -1, 0};
    unsigned char due = bc_runtime_defeat_tick(sequence, paused);
    if (!due) return result;
    result.slot = bc_actor_spawn_boss_effect(actors, sequence->center_y, data,
        relocation, sprite_base, random_state);
    if (result.slot >= 0) {
        result.actor_event = bc_actor_common(&actors[result.slot], player, data, limited_count);
        if (events && events->score && result.actor_event.score_pending)
            bc_score_enqueue(events->score, result.actor_event.score_id, events->playing);
    }
    if (due == 2) {
        result.completion = stage->stopped ? 1 : 2;
        stage->stopped = 0;
    }
    return result;
}

void bc_runtime_checkpoint_reset(BcFrameCursor *cursor, BcPlayerControl *player,
    BcActor actors[BC_ACTOR_CAPACITY], BcStage *stage,
    const BcEnemyData *data, unsigned char round, unsigned short player_template,
    const unsigned char header[8], unsigned char *limited_count)
{
    /* $65DE-$6609 clears the enemy pool, limited-shot count and scroll stop.
     * Camera/script reconstruction is $737C; checkpoint selection is retained. */
    for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++) actors[i] = (BcActor){0};
    *limited_count = 0;
    stage->stopped = 0;
    bc_player_reset(player, round, data, player_template);
    bc_stage_checkpoint_restore(stage, header);
    cursor->stage_events = cursor->scrolling = 0;
    player->world.shot_index = 0;
}
