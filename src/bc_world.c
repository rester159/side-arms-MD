#include "bc_world.h"
#include "enemy_pool.h"
#include "bc_bullet_turn.h"
#if defined(__m68k__)
#include "bc_round_data.h"
#endif

static __attribute__((always_inline)) inline void event_clear(BcActorEvent *event)
{
    /* MOVEP writes alternating bytes and accepts odd addresses. Two passes
     * clear this eight-byte record without changing public alignment/layout. */
#if defined(__m68k__)
    _Static_assert(sizeof(BcActorEvent) == 8, "MOVEP event clear requires eight bytes");
    __asm__ volatile ("movep.l %1,0(%0)\n\tmovep.l %1,1(%0)"
        : : "a"(event), "d"(0) : "memory");
#else
    *event = (BcActorEvent){0};
#endif
}


/* $8119/$8128. Birth code owns initialization and the first immediate update. */
signed short bc_actor_allocate(const BcActor actors[BC_ACTOR_CAPACITY], unsigned char reverse)
{
    return enemy_pool_free(actors, sizeof(*actors),
        __builtin_offsetof(BcActor, body.state), BC_ACTOR_CAPACITY, reverse);
}

static unsigned short word(const unsigned char *record)
{
#if defined(__m68k__)
    /* Source words may start at odd addresses. Build the high byte first so
     * the shift discards the register's old bits; no extra clear/OR is needed. */
    unsigned short value;
    __asm__("move.b %1,%0\n\tlsl.w #8,%0\n\tmove.b %2,%0"
        : "=&d"(value) : "m"(record[1]), "m"(record[0]) : "cc");
    return value;
#else
    return record[0] | ((unsigned short)record[1] << 8);
#endif
}

/* $8137-$81C5. Ordinary templates leave the old bar count intact; composite
 * templates set bars and initialize the current bar to ten HP. Position,
 * velocity, damage lock and family scratch fields are not cleared here. */
void bc_actor_template(BcActor *a, const unsigned char r[19], unsigned short base)
{
    BcEnemy *e = &a->body;
    e->state = r[0]; e->timer = r[1]; e->flags = r[2]; a->pickup = r[3];
    if (e->flags & 8) { e->hp = 10; e->bars = r[4]; }
    else e->hp = r[4];
    a->half_x = r[5]; a->half_y = r[6]; e->score_id = r[7]; a->speed = r[8];
    e->attributes = word(r + 9); a->sprite_base_ref = word(r + 11); e->sprite_base = base;
    e->animation = word(r + 13); a->routine = word(r + 15); a->death_routine = word(r + 17);
    e->move_delay = e->cooldown = a->auxiliary = a->health_fraction = 0;
}

signed short bc_actor_spawn_bullet(BcActor actors[BC_ACTOR_CAPACITY], unsigned char parent,
    unsigned char direction, const BcEnemyData *data, unsigned short template_address,
    unsigned short sprite_base, unsigned short speed_table)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    const BcEnemy *source = &actors[parent].body;
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    a->body.x = (source->x & 0xffff0000u) | (a->body.x & 0xff00);
    a->body.y = (source->y & 0xffff0000u) | (a->body.y & 0xff00);
    a->direction = direction;
    unsigned short vector = word(data->bytes + (unsigned short)(speed_table + a->speed - data->origin));
    const unsigned char *v = data->bytes + (unsigned short)(vector + direction * 4 - data->origin);
    bc_enemy_set_vx(&a->body, (signed short)word(v)); bc_enemy_set_vy(&a->body, (signed short)word(v + 2));
    return slot;
}

/* Scale damage rather than the source byte-sized HP/bar records. Preserve
 * the fractional remainder across bars (two 10-HP bars take 45 unit hits in
 * 4P, not 46). Integral overkill still ends at the current bar, as in 1P.
 * This runs only on vulnerable boss hits, never on ordinary enemy motion. */
static unsigned char __attribute__((noinline)) boss_damage(BcActor *a,
    unsigned char damage, unsigned char players)
{
    unsigned short units = a->health_fraction;
    unsigned short divisor;
    if (players == 3) { units += (unsigned short)damage * 2; divisor = 3; }
    else { units += (unsigned short)damage * 4; divisor = 9; }
    unsigned char applied = units / divisor;
    a->health_fraction = units - (unsigned short)applied * divisor;
    return applied;
}

/* Collision records and weapon scanning belong to the uncommon contact path.
 * Keep them out of the common motion frame used by bullets and effects. */
static unsigned char __attribute__((noinline)) actor_contacts(BcActorEvent *event,
    BcActor *a, BcWorldPlayer *p, unsigned char player_count, unsigned char contact_gate)
{
    /* Low bits: unknown/passed/impossible shots. Bit 2: impossible body contact. */
    unsigned char shot_gate = contact_gate & 3;
    BcEnemy *e = &a->body;
    /* These are the collision helpers' no-op gates. Reject before building
     * their temporary records, especially for enemy bullets and effects. */
    if (shot_gate != 2 && !(e->flags & 1) && (!p->shot_index || p->shot_index->count)) {
        BcTarget target = {bc_enemy_x(e), bc_enemy_y(e), a->half_x, a->half_y,
                           e->flags, e->hp, e->cooldown, e->damage_lock};
        BcHitEvent hit = shot_gate == 1 ?
            bc_enemy_shots_indexed_near(&target, &p->weapons, p->shot_index) :
            bc_enemy_shots_indexed(&target, &p->weapons, p->shot_index);
        if (hit.damaged && player_count > 2 &&
            ((e->flags & 8) || a->sprite_base_ref == 0x36d0)) {
            unsigned char damage = boss_damage(a, p->weapons.shots[hit.slot].body.damage,
                                               player_count);
            hit.depleted = e->hp <= damage;
            target.hp = e->hp - damage;
        }
        e->hp = target.hp;
        if (hit.depleted) {
            /* This helper includes the final lock tick, so return immediately. */
            BcDeathEvent death = bc_enemy_depleted(e);
            event->score_pending = death.award_score; event->score_id = death.score_id;
            event->sound = death.sound;
            return 1;
        }
    }
    if (!(contact_gate & 4) && e->state == 0x80 && !(e->flags & 2) && !p->invulnerability) {
        BcPlayerContact contact = {p->x >> 8, p->y >> 8, p->state, p->invulnerability,
                                   {p->weapons.shots[28].body.state, p->weapons.shots[29].body.state}};
        BcPlayerContactEvent touch = bc_enemy_player(e, a->half_x, a->half_y, a->pickup, &contact);
        /* Every caller starts with a zero event. Without body contact, the
         * player and event are unchanged; shot effects above already ran. */
        if (!touch.contact) return 0;
        if (p->party && contact.state != p->state) p->party->contact_policy = 0;
        p->state = contact.state; p->invulnerability = contact.invulnerability;
        event->sound = touch.sound; event->option_absorbed = touch.option;
        event->player_died = touch.contact && !touch.pickup && !touch.option;
        if (touch.option) bc_shot_hit(&p->weapons.shots[27 + touch.option]);
        if (touch.pickup) {
            BcPickupEvent pickup = bc_pickup_apply(&p->inventory, &p->weapons,
                                                   touch.pickup, p->x >> 8, p->y >> 8);
            if (pickup.consumed) {
                e->state = 0; event->retired = 1; event->pickup = touch.pickup;
                event->score_pending = pickup.score_id != 0; event->score_id = pickup.score_id;
                event->sound = pickup.sound; event->refresh_lives = pickup.refresh_lives;
            }
        }
    }
    return 0;
}

/* Exact player-contact distance predicate, including byte-sized hitbox sums.
 * Keep temporary coordinates off the common party scan's stack frame. */
static inline unsigned char __attribute__((always_inline)) body_near_inline(const BcActor *a,
    const BcWorldPlayer *p)
{
    unsigned short x = bc_enemy_x(&a->body), px = p->x >> 8;
    unsigned short dx = bc_unsigned_distance(x, px);
    if (dx >= (unsigned char)(a->half_x + 5)) return 0;
    unsigned short y = bc_enemy_y(&a->body), py = p->y >> 8;
    unsigned short dy = bc_unsigned_distance(y, py);
    return dy < (unsigned char)(a->half_y + 8);
}

static inline unsigned char __attribute__((always_inline)) body_near_solo(const BcActor *a,
    const BcWorldPlayer *p)
{
#if defined(__m68k__)
    __asm__ goto (
        "move.l %[px],%%d0\n\tlsr.l #8,%%d0\n\tsub.w %[x],%%d0\n\tbcc.s 1f\n\tneg.w %%d0\n"
        "1:\n\tmoveq #0,%%d1\n\tmove.b %[hx],%%d1\n\taddq.b #5,%%d1\n\tcmp.w %%d1,%%d0\n\tbcc %l[far]\n\t"
        "move.l %[py],%%d0\n\tlsr.l #8,%%d0\n\tsub.w %[y],%%d0\n\tbcc.s 2f\n\tneg.w %%d0\n"
        "2:\n\tmoveq #0,%%d1\n\tmove.b %[hy],%%d1\n\taddq.b #8,%%d1\n\tcmp.w %%d1,%%d0\n\tbcc %l[far]"
        : : [px] "m"(p->x), [py] "m"(p->y), [x] "m"(a->body.x), [y] "m"(a->body.y),
            [hx] "m"(a->half_x), [hy] "m"(a->half_y)
        : "d0", "d1", "cc" : far);
    return 1;
far:
    return 0;
#else
    unsigned short x = bc_enemy_x(&a->body), px = p->x >> 8;
    unsigned short dx = bc_unsigned_distance(x, px);
    if (dx >= (unsigned char)(a->half_x + 5)) return 0;
    unsigned short y = bc_enemy_y(&a->body), py = p->y >> 8;
    unsigned short dy = bc_unsigned_distance(y, py);
    return dy < (unsigned char)(a->half_y + 8);
#endif
}

/* Ordered subtraction avoids widened sums without wrapping coordinates.
 * Each half is exactly equivalent to its original unsigned 32-bit sum test,
 * including zero radii and unordered interval endpoints. */
static inline unsigned char __attribute__((always_inline)) body_axis_far(
    unsigned short position, unsigned short minimum, unsigned short maximum,
    unsigned char radius)
{
#if defined(__m68k__)
    /* SUB.W gives both ordering and distance; an unsigned borrow excludes
     * that half of the interval before the exact radius comparison. */
    __asm__ goto (
        "move.w %0,%%d0\n\tsub.w %1,%%d0\n\tbcs.s 1f\n\t"
        "cmp.w %2,%%d0\n\tbcc %l[far]\n"
        "1:\n\tmove.w %1,%%d0\n\tsub.w %3,%%d0\n\tbcs.s 2f\n\t"
        "cmp.w %2,%%d0\n\tbcc %l[far]\n2:"
        : : "g"(minimum), "d"(position), "d"((unsigned short)radius), "g"(maximum)
        : "d0", "cc" : far);
    return 0;
far:
    return 1;
#else
    return (position <= minimum && (unsigned short)(minimum - position) >= radius) ||
        (position >= maximum && (unsigned short)(position - maximum) >= radius);
#endif
}

/* A conservative union rejects only actors outside every vulnerable body.
 * Source hitbox radii still wrap by byte. */
static inline unsigned char __attribute__((always_inline)) party_bodies_far(const BcActor *a, const BcParty *party)
{
#if defined(__m68k__)
    /* Read the second axis only after the first passes. Keep the byte-wrapped
     * radii and ordered word differences inside one register-only check. */
    __asm__ goto (
        "move.w %[x],%%d2\n\tmoveq #0,%%d1\n\tmove.b %[hx],%%d1\n\taddq.b #5,%%d1\n\t"
        "move.w %[lx],%%d0\n\tsub.w %%d2,%%d0\n\tbcs.s 1f\n\tcmp.w %%d1,%%d0\n\tbcc %l[far]\n"
        "1:\n\tmove.w %%d2,%%d0\n\tsub.w %[ux],%%d0\n\tbcs.s 2f\n\tcmp.w %%d1,%%d0\n\tbcc %l[far]\n"
        "2:\n\tmove.w %[y],%%d2\n\tmoveq #0,%%d1\n\tmove.b %[hy],%%d1\n\taddq.b #8,%%d1\n\t"
        "move.w %[ly],%%d0\n\tsub.w %%d2,%%d0\n\tbcs.s 3f\n\tcmp.w %%d1,%%d0\n\tbcc %l[far]\n"
        "3:\n\tmove.w %%d2,%%d0\n\tsub.w %[uy],%%d0\n\tbcs.s 4f\n\tcmp.w %%d1,%%d0\n\tbcc %l[far]\n4:"
        : : [x] "m"(a->body.x), [y] "m"(a->body.y),
          [hx] "m"(a->half_x), [hy] "m"(a->half_y),
          [lx] "m"(party->body_min_x), [ux] "m"(party->body_max_x),
          [ly] "m"(party->body_min_y), [uy] "m"(party->body_max_y)
        : "d0", "d1", "d2", "cc" : far);
    return 0;
far:
    return 1;
#else
    unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
    unsigned char rx = a->half_x + 5, ry = a->half_y + 8;
    return body_axis_far(x, party->body_min_x, party->body_max_x, rx) ||
        body_axis_far(y, party->body_min_y, party->body_max_y, ry);
#endif
}

/* Used after body rejection; nearby shots still use source player order. */
static inline unsigned char __attribute__((always_inline)) party_shots_far(const BcActor *a, const BcParty *party)
{
    unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
    unsigned short rx = a->half_x + party->shot_half_x;
    unsigned short ry = a->half_y + party->shot_half_y;
    return x > (unsigned short)(party->shot_max_x + rx) ||
        (unsigned short)(x + rx) < party->shot_min_x ||
        y > (unsigned short)(party->shot_max_y + ry) ||
        (unsigned short)(y + ry) < party->shot_min_y;
}

static inline __attribute__((always_inline)) unsigned char contact_event_pending(const BcActorEvent *event)
{
#if defined(__m68k__)
    _Static_assert(sizeof(BcActorEvent) == 8 && __builtin_offsetof(BcActorEvent, score_id) == 2,
                   "contact event mask layout");
    unsigned int even, odd;
    /* MOVEP permits either byte alignment. Score ID alone is not an event. */
    __asm__("movep.l 0(%2),%0\n\tmovep.l 1(%2),%1\n\t"
            "andi.l #0xff00ffff,%0\n\tor.l %1,%0"
        : "=&d"(even), "=&d"(odd) : "a"(event), "m"(*event) : "cc");
    return even != 0;
#else
    return event->retired || event->score_pending || event->sound ||
        event->refresh_lives || event->pickup || event->option_absorbed || event->player_died;
#endif
}

/* Detailed contacts need extra registers and temporary event records. Keep
 * them off the no-contact motion path after its whole-party rejection gates. */
#if defined(__m68k__)
__attribute__((optimize("O3")))
#endif
static void __attribute__((noinline)) party_contact_scan(BcActorEvent *event,
    BcActor *a, BcParty *party, unsigned char bodies_far)
{
    BcEnemy *e = &a->body;
    /* Actors immune to shots need only player-body contacts. Split this
     * frequent bullet/effect path before scanning the party so each member
     * does not repeat actor flags, actor state and shot-index tests. */
    if (e->flags & 1) {
        if (bodies_far) {
            if (e->cooldown && e->cooldown != 255) e->cooldown--;
            if (e->damage_lock) e->damage_lock--;
            return;
        }
        unsigned char first = 1;
        for (unsigned char i = 0; i < party->count; i++) {
            BcWorldPlayer *p = party->players[i];
            if (!p || p->state != 0x80) continue;
            if (first) {
                if (e->cooldown && e->cooldown != 255) e->cooldown--;
                first = 0;
                if (e->state != 0x80 || (e->flags & 2)) break;
            }
            if (p->invulnerability || !body_near_inline(a, p)) continue;
            BcActorEvent contact = {0};
            actor_contacts(&contact, a, p, party->count, 0);
            event->retired |= contact.retired;
            if (party->contact && contact_event_pending(&contact))
                party->contact(i, &contact, party->context);
            if (e->state != 0x80) break;
        }
    } else {
        unsigned char first = 1;
        /* Contacts do not change actor flags; a state transition exits this
         * loop immediately. Protection does not expire within the actor pass.
         * Keep those actor-wide gates outside the scan. */
        unsigned char bodies = party->contact_policy != 2 &&
            e->state == 0x80 && !(e->flags & 2);
        if (bodies && bodies_far) bodies = 0;
        /* Policy 3 guarantees a living member, so the skipped scan would
         * decrement cooldown once. Death invalidates that policy immediately. */
        if (!bodies && party->contact_policy == 3 && party->shot_bounds_valid &&
            (party->shot_bounds_valid == 2 || party_shots_far(a, party))) {
            if (e->cooldown && e->cooldown != 255) e->cooldown--;
            if (e->damage_lock) e->damage_lock--;
            return;
        }
        for (unsigned char i = 0; i < party->count; i++) {
            BcWorldPlayer *p = party->players[i];
            if (!p || p->state != 0x80) continue;
            if (first) {
                if (e->cooldown && e->cooldown != 255) e->cooldown--;
                first = 0;
            }
            const BcShotIndex *index = p->shot_index;
            unsigned char shots = !index || index->count;
            if (shots && index) {
                /* Reject impossible shots before materializing a contact. */
                unsigned short x = bc_enemy_x(e), y = bc_enemy_y(e);
                unsigned short rx = a->half_x + index->half_x;
                unsigned short ry = a->half_y + index->half_y;
                if (x > (unsigned short)(index->max_x + rx) ||
                    (unsigned short)(x + rx) < index->min_x ||
                    y > (unsigned short)(index->max_y + ry) ||
                    (unsigned short)(y + ry) < index->min_y) shots = 0;
            }
            unsigned char body = bodies && !p->invulnerability;
            if (!shots && body) body = body_near_inline(a, p);
            if (shots || body) {
                /* Materialize only a possible contact. Most enemy bullets
                 * have no shot collisions and see protected/absent players.
                 * Forward immediately in source slot order, avoiding a second
                 * four-player scan and four zeroed records per moving actor. */
                BcActorEvent contact = {0};
                unsigned char stop = actor_contacts(&contact, a, p, party->count,
                    (!shots ? 2 : index ? 1 : 0) | (!body ? 4 : 0));
                event->retired |= contact.retired;
                if (party->contact && contact_event_pending(&contact))
                    party->contact(i, &contact, party->context);
                if (stop) return;
                if (e->state != 0x80) break;
            }
        }
    }
    if (e->damage_lock) e->damage_lock--;
}

static inline __attribute__((always_inline)) void party_common_dispatch(BcActorEvent *event,
    BcActor *a, BcParty *party, unsigned char motion)
{
    BcEnemy *e = &a->body;
    if (motion == 1) {
        event->retired = 1;
        if (party->contact) party->contact(0, event, party->context);
        return;
    }
    /* During an actor pass, protected players cannot lose their protection:
     * its countdown belongs to the preceding player update. Shot-immune
     * actors can therefore skip the whole party scan when bodies cannot hit.
     * With no living player shots either, any actor can skip this scan.
     * Any death invalidates the cached living classification immediately. */
    if (!motion && (party->contact_policy == 4 ||
        ((e->flags & 1) && party->contact_policy &&
         (party->contact_policy <= 2 || (e->flags & 2) || e->state != 0x80)))) {
        if (party->contact_policy != 1 && e->cooldown && e->cooldown != 255)
            e->cooldown--;
        if (e->damage_lock) e->damage_lock--;
        return;
    }
    /* Protected bodies cannot collide. Reject a whole party only outside the
     * union of its shot rectangles; near actors retain the ordered scan. */
    if (!motion && party->contact_policy == 2 && party->shot_bounds_valid) {
        unsigned short x = bc_enemy_x(e), y = bc_enemy_y(e);
        unsigned short rx = a->half_x + party->shot_half_x;
        unsigned short ry = a->half_y + party->shot_half_y;
        if (x > (unsigned short)(party->shot_max_x + rx) ||
            (unsigned short)(x + rx) < party->shot_min_x ||
            y > (unsigned short)(party->shot_max_y + ry) ||
            (unsigned short)(y + ry) < party->shot_min_y) {
            if (e->cooldown && e->cooldown != 255) e->cooldown--;
            if (e->damage_lock) e->damage_lock--;
            return;
        }
    }
    /* Vulnerable parties also avoid the detailed scan when neither their
     * body union nor any shot can reach this actor. The helper retains its
     * per-member checks for every potentially nearby contact. */
    unsigned char bodies_far = !motion && party->contact_policy == 3 &&
        party->body_bounds_valid && party_bodies_far(a, party);
    if (bodies_far && ((e->flags & 1) ||
        (party->shot_bounds_valid && (party->shot_bounds_valid == 2 || party_shots_far(a, party))))) {
        if (e->cooldown && e->cooldown != 255) e->cooldown--;
        if (e->damage_lock) e->damage_lock--;
        return;
    }
    if (!motion) party_contact_scan(event, a, party, bodies_far);
    else if (e->damage_lock) e->damage_lock--;

}

/* Keep the ordered party scan compact on 68000. The global O3 setting
 * expands this hot path; O2 saves time in the long four-player fixture. */
#if defined(__m68k__)
__attribute__((optimize("O2")))
#endif
void bc_actor_common_into(BcActorEvent *event, BcActor *a, BcWorldPlayer *p,
    const BcEnemyData *data, unsigned char *limited_count)
{
    BcEnemy *e = &a->body;
    unsigned char motion = bc_enemy_motion(e, data, limited_count);
    /* Motion only updates the actor/count; initialize the contact result
     * afterward to keep its stores out of the motion call's live state. */
    event_clear(event);
    /* bc_party_bind validates 2–4 members before attaching this pointer;
     * solo players use NULL. Do not repeat that invariant per actor. */
    if (p->party) {
        party_common_dispatch(event, a, p->party, motion);
        return;
    }
    if (motion == 1) { event->retired = 1; return; }
    if (!motion && p->state == 0x80) {
        if (e->cooldown && e->cooldown != 255) e->cooldown--;
        const BcShotIndex *index = p->shot_index;
        unsigned char shots = !(e->flags & 1) && (!index || index->count);
        if (shots && index) {
            unsigned short x = bc_enemy_x(e), y = bc_enemy_y(e);
            unsigned short rx = a->half_x + index->half_x;
            unsigned short ry = a->half_y + index->half_y;
            if (x > (unsigned short)(index->max_x + rx) ||
                (unsigned short)(x + rx) < index->min_x ||
                y > (unsigned short)(index->max_y + ry) ||
                (unsigned short)(y + ry) < index->min_y) shots = 0;
        }
        /* With no possible shot hit, reject distant bodies before building
         * contact records. Keep cooldown and damage-lock ticks outside. */
        if (shots || (e->state == 0x80 && !(e->flags & 2) && !p->invulnerability && body_near_solo(a, p))) {
            if (actor_contacts(event, a, p, 1, 0)) return;
        }
    }
    if (e->damage_lock) e->damage_lock--;
}

BcActorEvent bc_actor_common(BcActor *a, BcWorldPlayer *p,
    const BcEnemyData *data, unsigned char *limited_count)
{
    BcActorEvent event;
    bc_actor_common_into(&event, a, p, data, limited_count);
    return event;
}

void bc_actor_party_common_into(BcActorEvent events[BC_PARTY_CAPACITY],
    BcActor *a, BcWorldPlayer *const players[BC_PARTY_CAPACITY],
    unsigned char player_count, const BcEnemyData *data, unsigned char *limited_count)
{
    for (unsigned char i = 0; i < BC_PARTY_CAPACITY; i++) events[i] = (BcActorEvent){0};
    if (!player_count || player_count > BC_PARTY_CAPACITY) return;
    BcEnemy *e = &a->body;
    unsigned char motion = bc_enemy_motion(e, data, limited_count);
    if (motion == 1) { events[0].retired = 1; return; }
    if (!motion) {
        unsigned char first = 1;
        for (unsigned char i = 0; i < player_count; i++) {
            BcWorldPlayer *p = players[i];
            if (!p || p->state != 0x80) continue;
            if (first) {
                if (e->cooldown && e->cooldown != 255) e->cooldown--;
                first = 0;
            }
            if ((!(e->flags & 1) && (!p->shot_index || p->shot_index->count)) ||
                (e->state == 0x80 && !(e->flags & 2) && !p->invulnerability)) {
                if (actor_contacts(&events[i], a, p, player_count, 0)) return;
                if (e->state != 0x80) break;
            }
        }
    }
    if (e->damage_lock) e->damage_lock--;
}

signed short bc_actor_spawn_curve(BcActor actors[BC_ACTOR_CAPACITY], unsigned char y,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    bc_enemy_set_x(&a->body, 0x110);
    bc_enemy_set_y(&a->body, (unsigned short)y);
    bc_enemy_set_vx(&a->body, (template_address == 0xabb1 || template_address == 0xb499 || template_address == 0xafda || template_address == 0xaee2 || template_address == 0xb3b2 || template_address == 0xb335 || template_address == 0xafa4 || template_address == 0xb65e) ? -640 : -512); bc_enemy_set_vy(&a->body, 0);
    a->wait = 30; a->phase = 0; a->fired = 0;
    return slot;
}

static void reaim_direction(BcActor *a, const BcWorldPlayer *p, const BcEnemyData *data)
{
    a->direction = bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body));
    const unsigned char *bytes = data->bytes;
    a->body.animation = word(bytes + 0xb3ff + a->direction * 2 - data->origin);
    unsigned short vector = word(bytes + 0x8262 + a->speed - data->origin) + a->direction * 4;
    bc_enemy_set_vx(&a->body, word(bytes + (unsigned short)(vector - data->origin)));
    bc_enemy_set_vy(&a->body, word(bytes + (unsigned short)(vector + 2 - data->origin)));
}

/* Aim decoding is needed only when the byte timer expires. */
static void __attribute__((noinline)) actor_reaim_expire(BcActor *a,
    BcWorldPlayer *p, const BcEnemyData *data)
{
        if (a->routine == 0xb396) {
            reaim_direction(a, p, data);
            a->body.timer = 1; a->routine = 0xb359; a->wait = 24;
        } else if (bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body)) == a->direction)
            a->wait = 24;
        else {
            a->wait = 32; bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
            a->body.animation = 0xb46f; a->body.timer = 1; a->routine = 0xb396;
        }
}

void __attribute__((noinline)) bc_actor_reaim_common(BcActorEvent *event, BcActor *a, BcWorldPlayer *p,
    const BcEnemyData *data, unsigned char *count)
{
    if (!--a->wait) actor_reaim_expire(a, p, data);
    bc_actor_common_into(event, a, p, data, count);
}

signed short bc_actor_spawn_reaim(BcActor actors[BC_ACTOR_CAPACITY], unsigned char position,
    const BcWorldPlayer *p, const BcEnemyData *data, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + 0xb3cc - data->origin, sprite_base);
    const unsigned char *xy = data->bytes + 0xb3df + position * 4 - data->origin;
    bc_enemy_set_x(&a->body, word(xy));
    bc_enemy_set_y(&a->body, word(xy + 2));
    reaim_direction(a, p, data);
    a->wait = 40;
    return slot;
}

static void curve_prepare(BcActorStepEvent *event, BcActor *a, unsigned char slot,
    BcWorldPlayer *p, const BcEnemyData *data, unsigned char *count,
    unsigned char maximum, unsigned short bullet_base, unsigned char round, signed short relocation)
{
    /* $AA8E/$AB88 share the steering sequence with $AD31/$AE2B,
     * but retain their own animation tables and routine addresses. */
    unsigned char fast = (!round && (a->routine == 0xaa8e || a->routine == 0xab88)) ||
        (round == 1 && (a->routine == 0xb376 || a->routine == 0xb470));
    unsigned short approach = round == 7 ? 0xb53b : round == 6 ? 0xae81 : round == 5 ? 0xb212 : round == 4 ? 0xb28f : round == 3 ? 0xadbf : round == 2 ? 0xaeb7 : round == 1 ? (fast ? 0xb376 : 0xb7fc) : fast ? 0xaa8e : 0xad31;
    /* A waiting approach changes only its byte countdown. Avoid constructing
     * and copying the full curve/body adapter until steering is due. Zero
     * still wraps to 255, exactly like the source decrement. */
    if (a->routine == approach && a->wait != 1) {
        a->wait--;
        return;
    }
    unsigned short escape = round == 7 ? 0xb635 : round == 6 ? 0xaf7b : round == 5 ? 0xb30c : round == 4 ? 0xb389 : round == 3 ? 0xaeb9 : round == 2 ? 0xafb1 : round == 1 ? (fast ? 0xb470 : 0xb8f6) : fast ? 0xab88 : 0xae2b;
    /* Escape AI can only request its one shot. Once latched, the remaining
     * per-update work belongs to the parent common task below the caller. */
    if (a->routine == escape && a->fired) return;
    BcCurveFlight curve = {a->direction, a->speed, a->wait,
                         a->phase, a->turn, a->routine == escape, a->fired};
    BcEnemyFireEvent fire = {0, 0};
    if (curve.escaping)
        fire = bc_enemy_curve_fire(&a->body, &curve, p->x >> 8, p->y >> 8, *count, maximum);
    else
        bc_enemy_curve_flight(&a->body, &curve, p->x >> 8, p->y >> 8, data, 0x8479 + relocation,
            round == 7 ? 0xb676 : round == 6 ? 0xafbc : round == 5 ? 0xb34d : round == 4 ? 0xb3ca : round == 3 ? 0xaefa : round == 2 ? 0xaff2 : round == 1 ? (fast ? 0xb4b1 : 0xb937) : fast ? 0xabc9 : 0xae6c,
            round == 7 ? 0xb689 : round == 6 ? 0xafcf : round == 5 ? 0xb360 : round == 4 ? 0xb3dd : round == 3 ? 0xaf0d : round == 2 ? 0xb005 : round == 1 ? (fast ? 0xb4c4 : 0xb942) : fast ? 0xabdc : 0xae77);
    a->direction = curve.direction; a->speed = curve.speed;
    a->wait = curve.wait; a->phase = curve.phase; a->turn = curve.turn;
    a->routine = curve.escaping ? escape : approach;
    /* The source sets this latch after the child common task returns. */
    if (fire.fire) {
        BcActor *actors = a - slot;
        event->fire_requested = 1;
        event->child_slot = bc_actor_spawn_bullet(actors, slot, fire.direction, data,
            0x8aa4 + relocation, bullet_base, 0x8479 + relocation);
        if (event->child_slot >= 0) {
            bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, data, count);
            (*count)++;
        }
    }
    a->fired = curve.fired;
    return;
}

BcCurveActorEvent bc_actor_curve_prepare(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *p, const BcEnemyData *data, unsigned char *count,
    unsigned char maximum, unsigned short bullet_base)
{
    BcActorStepEvent event;
    event.child_event = (BcActorEvent){0}; event.child_slot = -1;
    event.fire_requested = 0;
    curve_prepare(&event, &actors[slot], slot, p, data, count, maximum, bullet_base, 0, 0);
    BcCurveActorEvent result = {event.child_event, event.child_slot, event.fire_requested};
    return result;
}

unsigned char bc_actor_explosion(BcActor *a, unsigned char kind,
    unsigned short sprite_base, unsigned short animation)
{
    a->body.attributes = kind ? (kind == 2 ? 0x1182 : 0x1181) : 0x0081;
    a->sprite_base_ref = kind ? 0x367e : 0x367c;
    a->body.sprite_base = sprite_base;
    a->body.animation = animation;
    a->body.timer = 1;
    bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
    a->death_routine = 0x9eb1;
    return 4;
}

void bc_actor_scroll(BcActor *a, signed short dx, signed short dy, unsigned char stopped)
{
    if (!stopped && (a->body.flags & 16)) {
        a->body.x -= (unsigned int)((signed int)dx * 256);
        a->body.y -= (unsigned int)((signed int)dy * 256);
    }
}

/* Round-two walking gunner terrain probes and walking-pose reset. */
static unsigned char walker_solid(const BcActor *a, const BcActorStepData *data)
{
    return bc_terrain_solid(&data->terrain,
        data->camera_x + (bc_enemy_x(&a->body)) + (signed char)a->probe_x,
        data->camera_y + (bc_enemy_y(&a->body)) + (signed char)a->probe_y);
}
static void walker_walk(BcActor *a, unsigned short shift)
{
    a->body.animation = (a->wait ? 0xb30e : 0xb2f9) - shift;
    bc_enemy_set_vx(&a->body, a->wait ? -256 : 256); bc_enemy_set_vy(&a->body, 0);
    a->body.timer = 1; a->routine = 0xb1a6 - shift; a->phase = 16;
}

/* $AED3-$B0A2: terrain jumper, before its common task. */
static BcEnemyFireEvent jumper_prepare(BcActor *a, const BcWorldPlayer *p,
    const BcActorStepData *data, unsigned char count, unsigned char maximum)
{
    BcEnemyFireEvent fire = {0, 0};
    unsigned short shift = data->round == 5 ? 0x9b2 : 0;
    if (a->body.move_delay) return fire;
    unsigned char shoot = 0, pose = 0;
    unsigned char px = p->x >> 8, x = bc_enemy_x(&a->body);
    if (a->turn) {
        unsigned char old = a->phase;
        if (old) { a->phase--; shoot = old == 32 || old == 16; }
        else { a->turn = 0; bc_enemy_set_vy(&a->body, 0); }
    } else {
        unsigned char landed = 0;
        if (bc_enemy_vy(&a->body) >= 0) {
            a->probe_x = 0; a->probe_y = 10;
            landed = bc_terrain_solid(&data->terrain,
                data->camera_x + (bc_enemy_x(&a->body)), data->camera_y + (bc_enemy_y(&a->body)) + 10);
        }
        if (!landed) bc_enemy_set_vy(&a->body, (unsigned short)(bc_enemy_vy(&a->body) + 48));
        else {
            unsigned char correction = ((bc_enemy_y(&a->body)) + 10 + data->camera_y) & 15;
            a->body.y -= (unsigned int)correction << 16;
            switch (a->wait) {
            case 0:
                bc_enemy_set_vx(&a->body, -384); bc_enemy_set_vy(&a->body, -1280); a->wait++;
                a->body.move_delay = 16; shoot = 1; break;
            case 1:
                bc_enemy_set_vx(&a->body, -128); bc_enemy_set_vy(&a->body, -640); a->wait++;
                a->body.move_delay = 16; pose = 1; break;
            case 2:
                if ((unsigned char)(x + 32 - px) < 64) {
                    bc_enemy_set_vx(&a->body, 0); bc_enemy_set_vy(&a->body, -1664); a->body.move_delay = 16;
                } else {
                    bc_enemy_set_vx(&a->body, x < px ? -640 : 640); bc_enemy_set_vy(&a->body, -192);
                    a->turn = 1; a->phase = 32; a->wait += x < px ? 1 : 2;
                }
                pose = 1; break;
            case 3: case 4:
                bc_enemy_set_vx(&a->body, a->wait == 3 ? -512 : 512); bc_enemy_set_vy(&a->body, -1024);
                a->body.move_delay = 16; pose = 1; break;
            }
        }
    }
    if (pose) { a->body.animation = px < x ? (0xb0b8 + shift) : (0xb0bf + shift); a->body.timer = 1; }
    unsigned short full_x = bc_enemy_x(&a->body), full_y = bc_enemy_y(&a->body);
    if (shoot && !((full_x | full_y) & 0xff00) && full_y >= 16 && full_y < 224 && count < maximum) {
        unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, full_x, full_y);
        unsigned char cone = (direction + 2) & 15;
        if (cone < 13 && (px >= x ? cone < 5 : cone >= 8)) {
            a->body.timer = 1; a->body.animation = px < x ? (0xb0c6 + shift) : (0xb0cb + shift);
            fire.fire = 1; fire.direction = direction;
        }
    }
    return fire;
}

/* $B3BF-$B494: two-part first boss. Child common tasks occur immediately,
 * before the parent common task; allocation failure ends that burst. */
static void boss_prepare(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    signed short shift = data->round == 8 ? -0xdd7 : 0;
    if (a->routine == (0xb471 + shift) || a->routine == (0xb488 + shift)) {
        if (a->routine == (0xb471 + shift)) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x29; a->routine = (0xb488 + shift);
        }
        bc_enemy_copy_y(&a->body, &actors[0].body);
        return;
    }
    if (a->routine == (0xb3bf + shift)) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x28; a->body.cooldown = 240;
        a->phase = a->turn = 1; a->routine = (0xb3e3 + shift);
    }
    unsigned char py = p->y >> 8, y = bc_enemy_y(&a->body);
    if ((unsigned char)(py - y + 8) < 16) bc_enemy_set_vy(&a->body, 0);
    else {
        signed short speed = data->boss_active ? 256 : 384;
        bc_enemy_set_vy(&a->body, py < y ? -speed : speed);
    }
    if (!--a->phase) {
        a->body.move_delay = 20; a->phase = data->boss_active ? 96 : 48;
        unsigned char child = 0;
        for (unsigned char i = 0; i < 8; i++) {
            /* Immediate common updates can retire this child but cannot free
             * an earlier actor. Resume at this slot, not at zero or child+1,
             * preserving first-free order even when a birth retires at once. */
            while (child < BC_ACTOR_CAPACITY && actors[child].body.state) child++;
            if (child == BC_ACTOR_CAPACITY) break;
            BcActor *b = &actors[child];
            bc_actor_template(b, data->data.bytes + ((0xb5ca + shift) - data->data.origin), data->boss_spread_base);
            const unsigned char *v = data->data.bytes + ((0xb5dd + shift) + i * 8 - data->data.origin);
            bc_enemy_set_vx(&b->body, (signed short)word(v + 2)); bc_enemy_set_vy(&b->body, (signed short)word(v + 4));
            b->body.animation = word(v + 6);
            bc_enemy_set_x(&b->body, (unsigned short)((bc_enemy_x(&a->body)) + (signed char)v[1]));
            bc_enemy_set_y(&b->body, (unsigned short)((bc_enemy_y(&a->body)) + (signed char)v[0]));
            unsigned char n = event->extra_count++;
            event->extra_slots[n] = child;
            bc_actor_common_into(&event->extra_events[n], b, p, &data->data, count);
        }
    }
    if (!--a->turn) {
        a->turn = data->boss_active ? 200 : 100;
        for (unsigned char i = 0; i < 2; i++) {
            const unsigned char *v = data->data.bytes + ((0xb699 + shift) + i * 2 - data->data.origin);
            signed short child = bc_actor_spawn_bullet(actors, slot, v[1], &data->data,
                0x8b66 + data->relocation, data->homing_base, 0x8479 + data->relocation);
            if (child < 0) break;
            BcActor *b = &actors[child];
            bc_enemy_set_x(&b->body, 0xcc);
            bc_enemy_set_y(&b->body, (unsigned short)((bc_enemy_y(&actors[0].body)) + (signed char)v[0]));
            b->body.animation = word(data->data.bytes + (0x8b79 + data->relocation + v[1] * 2 - data->data.origin));
            b->wait = 20;
            unsigned char n = event->extra_count++;
            event->extra_slots[n] = child;
            bc_actor_common_into(&event->extra_events[n], b, p, &data->data, count);
        }
    }
    actors[1].body.damage_lock = actors[0].body.damage_lock;
}

/* Keep this round-specific state machine out of the common per-actor stack
 * frame: LTO otherwise increases spill costs even for round-one actors. */
static void __attribute__((noinline)) walker_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event,
    unsigned short handler)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 4 ? 0xe7 : data->round == 3 ? 0x5b7 : 0;
    handler += shift;

        unsigned char walk = handler == 0xb1a6;
        if (handler == 0xb137) {
            a->probe_x = 0; a->probe_y = 12;
            if (walker_solid(a, data)) {
                a->body.flags = 16; a->probe_x = a->wait ? 244 : 12;
                walker_walk(a, shift); walk = 1;
            }
        }
walker_walking:
        if (walk && !a->body.move_delay) {
            a->probe_y = 0;
            if (walker_solid(a, data)) {
                a->body.animation = (a->wait ? 0xb315 : 0xb300) - shift; a->body.timer = 1;
                bc_enemy_set_vx(&a->body, 0); bc_enemy_set_vy(&a->body, -256); a->routine = 0xb2d1 - shift;
            } else {
                a->probe_y = 12;
                if (!walker_solid(a, data)) a->routine = 0xb270 - shift;
                else if (!--a->phase) {
                    a->phase = 16; *data->random_state = bc_random_next(*data->random_state);
                    unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                    if ((*data->random_state >> 8) < 80 && (unsigned char)x >= 64 &&
                        (unsigned char)x < 192 && !((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
                        unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, x, y);
                        if (direction >= 9) {
                            a->body.animation = (direction < 12 ? (a->wait ? 0xb30c : 0xb2f7) : (a->wait ? 0xb307 : 0xb2f2)) - shift;
                            a->body.timer = 1; a->body.move_delay = 16; event->fire_requested = 1;
                            for (unsigned char i = 0; i < 3; i++) {
                                signed short child = bc_actor_spawn_bullet(actors, slot, (direction + i - 1) & 15,
                                    &data->data, 0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                                if (child >= 0) {
                                    unsigned char n = event->extra_count++; event->extra_slots[n] = child;
                                    bc_actor_common_into(&event->extra_events[n], &actors[child], p, &data->data, count);
                                    (*count)++;
                                }
                            }
                        }
                    }
                }
            }
        }
        /* New fall/climb states execute immediately, but returning to walking
         * from these states reaches the walking logic in the same update. */
        if (a->routine == 0xb270 - shift) {
            a->probe_y = 12;
            if (walker_solid(a, data)) { walker_walk(a, shift); walk = 1; goto walker_walking; }
            else if (((unsigned short)bc_enemy_vy(&a->body) >> 8) != 3) bc_enemy_set_vy(&a->body, (unsigned short)(bc_enemy_vy(&a->body) + 48));
        } else if (a->routine == 0xb2d1 - shift) {
            a->probe_y = 0;
            if (!walker_solid(a, data)) { walker_walk(a, shift); walk = 1; goto walker_walking; }
        }

}

/* Caller provides a cleared envelope; walker bursts populate extra events. */
void bc_actor_walker_common_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, unsigned short handler)
{
    walker_prepare(actors, slot, p, data, count, maximum, event, handler);
    bc_actor_common_into(&event->actor_event, &actors[slot], p, &data->data, count);
}

/* Spawn enters only the walker state machine. Keeping it off the general
 * actor dispatcher preserves cartridge specialization for per-frame updates. */
void bc_actor_walker_birth(BcActorEvent *result, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    BcActorStepEvent event = {0};
    walker_prepare(actors, slot, p, data, count, maximum, &event, data->round == 4 ? 0xb050 : data->round == 3 ? 0xab80 : 0xb137);
    bc_actor_common_into(result, &actors[slot], p, &data->data, count);
}

/* Round-four formation leader fires seven times before releasing the group.
 * Followers sample the leader latch on their own 36-tick timers. */
static void __attribute__((noinline)) formation_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 7 ? 0x580 : 0;
    if (--a->turn) return;
    if (a->routine == (0xb4dc + shift)) {
        a->body.flags = 0; a->body.timer = 1; a->body.animation = (0xb6e0 + shift);
        a->turn = 1;
        if (a->wait == 0x4d) { a->fired = 8; a->routine = (0xb513 + shift); }
        else a->routine = (0xb54e + shift);
        a->turn--;
    }
    if (a->routine == (0xb513 + shift)) {
        a->turn = 44;
        if (--a->fired) {
            unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
            if (!((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
                event->fire_requested = 1;
                event->child_slot = bc_actor_spawn_bullet(actors, slot,
                    bc_aim16(p->x >> 8, p->y >> 8, x, y), &data->data,
                    0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                if (event->child_slot >= 0) {
                    bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                    (*count)++;
                }
            }
            return;
        }
        a->wait = 0x47;
    } else {
        a->turn = 36;
        if (actors[a->phase].wait != 0x47) return;
    }
    a->direction = bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body));
    const unsigned char *bytes = data->data.bytes;
    unsigned short vector = word(bytes + 0x8262 + a->speed - data->data.origin) + a->direction * 4;
    bc_enemy_set_vx(&a->body, word(bytes + vector - data->data.origin));
    bc_enemy_set_vy(&a->body, word(bytes + vector + 2 - data->data.origin));
    a->body.flags = 0; a->body.timer = 1; a->body.animation = (0xb6eb + shift); a->routine = 0x9eb1;
}

/* Round-two ceiling group: the leader releases four falling actors with
 * staggered delays; terrain contact (or death) revives each as a homing shot. */
static void __attribute__((noinline)) ceiling_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, const BcWorldPlayer *p, const BcActorStepData *data,
    unsigned short handler)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 6 ? 0x377 : 0;
    handler += shift;
    unsigned char fall = handler == 0xbe24, release = 0, revive = handler == 0xbe4e;
    if (handler == 0xbdad) {
        unsigned short px = ((p->x >> 8) + 256) & 65535;
        unsigned short x = ((bc_enemy_x(&a->body)) + 256) & 65535;
        unsigned short distance = px >= x ? px - x : x - px;
        if (distance < 32) {
            for (unsigned char i = 1; i < 4; i++) {
                actors[slot + i].routine = 0xbe08 - shift; actors[slot + i].wait = i * 10;
            }
            release = 1;
        }
    } else if (handler == 0xbe08) release = !--a->wait;
    if (release) {
        a->routine = 0xbe24 - shift; a->body.flags = 0; a->wait = 60; fall = 1;
    }
    if (fall) {
        if (a->wait) a->wait--;
        else {
            a->probe_x = 0; a->probe_y = 8;
            revive = walker_solid(a, data);
        }
        if (!revive) bc_enemy_set_vy(&a->body, (unsigned short)(bc_enemy_vy(&a->body) + 8));
    }
    if (revive) {
        a->body.state = 0x80; a->wait = 36; a->body.move_delay = a->body.cooldown = 20;
        a->body.hp = 2; a->direction = 12;
        const unsigned char *bytes = data->data.bytes;
        unsigned short vector = word(bytes + (unsigned short)(0x8479 + data->relocation + a->speed - data->data.origin)) + 48;
        bc_enemy_set_vx(&a->body, word(bytes + (unsigned short)(vector - data->data.origin)));
        bc_enemy_set_vy(&a->body, word(bytes + (unsigned short)(vector + 2 - data->data.origin)));
        a->body.animation = 0xbead - shift; a->body.timer = 1;
        a->routine = 0x8900; a->death_routine = 0x8c7e;
    }
}

static inline __attribute__((always_inline)) void segment_coordinates(const BcEnemy *b,
    unsigned short *x, unsigned short *y)
{
    *x = bc_enemy_x(b); *y = bc_enemy_y(b);
}

/* Explicit scene binding: the round tables remain immutable until rebind.
 * Reference callers and other data objects retain their direct source reads. */
static const BcActorStepData *segment_data;
static unsigned short segment_animation[16];
static signed int segment_vx[2][16], segment_vy[2][16];
static unsigned char segment_speed[2];

#if defined(__m68k__)
static const BcActorStepData *boss_three_vector_data;
static const signed int (*boss_three_vectors)[16][2];
#endif

void bc_actor_bind_segments(const BcActorStepData *data)
{
#if defined(__m68k__)
    boss_three_vector_data = 0;
    if (data && bc_boss3_native_vectors && (data->round == 2 || data->round == 8)) {
        const BcBoss3NativeVectors *native = &bc_boss3_native_vectors[data->round == 8];
        if (native->source.bytes == data->data.bytes && native->source.origin == data->data.origin) {
            boss_three_vectors = native->velocity;
            boss_three_vector_data = data;
        }
    }
#endif
    segment_data = 0;
    if (!data || !(data->round == 1 || data->round == 2 || data->round == 3 ||
        data->round == 4 || data->round == 6 || data->round == 7)) return;
    unsigned short table = data->round == 7 ? 0xc075 : data->round == 6 ? 0xb955 :
        data->round == 4 ? 0xb90b : data->round == 3 ? 0xb946 : data->round == 2 ? 0xb811 : 0xbccc;
    const unsigned char *bytes = data->data.bytes;
    segment_speed[0] = bytes[(unsigned short)(table - 19 + 8 - data->data.origin)];
    segment_speed[1] = 6;
    for (unsigned char d = 0; d < 16; d++) {
        segment_animation[d] = word(bytes + (unsigned short)(table + d * 2 - data->data.origin));
        for (unsigned char k = 0; k < 2; k++) {
            unsigned short vector = word(bytes + (unsigned short)(0x8479 + data->relocation + segment_speed[k] - data->data.origin)) + d * 4;
            segment_vx[k][d] = (signed short)word(bytes + (unsigned short)(vector - data->data.origin)) * 256;
            segment_vy[k][d] = (signed short)word(bytes + (unsigned short)(vector + 2 - data->data.origin)) * 256;
        }
    }
    segment_data = data;
}

static void __attribute__((noinline)) segment_prepare_due(BcActor *a,
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event)
{
    if (!a->wait) {
        a->wait = 7; a->turn = a->direction;
        if (a->dash_started == 0x48) {
            unsigned short x, y;
            segment_coordinates(&a->body, &x, &y);
            unsigned char inside = !((x | y) & 0xff00) && x >= 48 && x < 208 && y >= 56 && y < 184;
            unsigned char target = bc_aim16(inside ? p->x >> 8 : 128,
                inside ? p->y >> 8 : 120, x, y);
            if (target != a->direction) {
                unsigned char difference = a->direction - target;
                a->direction = (a->direction + ((difference >> 2) & 2) - 1) & 15;
            }
        } else a->direction = (a->auxiliary == 255 ? (a-slot)+a->probe_x : a-1)->turn;
        if (data == segment_data && a->direction < 16 &&
            (a->speed == segment_speed[0] || a->speed == segment_speed[1])) {
            unsigned char k = a->speed == segment_speed[0] ? 0 : 1;
            a->body.animation = segment_animation[a->direction];
            a->body.timer = 1;
            a->body.motion_vx = segment_vx[k][a->direction];
            a->body.motion_vy = segment_vy[k][a->direction];
        } else {
        const unsigned char *bytes = data->data.bytes;
        a->body.animation = word(bytes + (data->round == 7 ? 0xc075 : data->round == 6 ? 0xb955 : data->round == 4 ? 0xb90b : data->round == 3 ? 0xb946 : data->round == 2 ? 0xb811 : 0xbccc) + a->direction * 2 - data->data.origin);
        a->body.timer = 1;
        unsigned short vector = word(bytes + (unsigned short)(0x8479 + data->relocation + a->speed - data->data.origin)) + a->direction * 4;
        bc_enemy_set_vx(&a->body, word(bytes + (unsigned short)(vector - data->data.origin)));
        bc_enemy_set_vy(&a->body, word(bytes + (unsigned short)(vector + 2 - data->data.origin)));
        }
    }
    if (a->dash_started == 0x54) {
        unsigned short x, y;
        segment_coordinates(&a->body, &x, &y);
        if (!((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
            unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, x, y) ^ 8;
            if (direction == a->direction) {
                BcActor *actors = a - slot;
                event->fire_requested = 1;
                event->child_slot = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                    0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                if (event->child_slot >= 0) {
                    bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                    (*count)++;
                }
            }
        }
    }
}

/* Most train segments only count down between turns. Keep that path in
 * the caller so it does not save the registers needed by aiming and births.
 * Tail segments still check their firing condition on every update. */
static inline __attribute__((always_inline)) void segment_prepare(BcActor *a,
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event)
{
    if (!--a->wait || a->dash_started == 0x54)
        segment_prepare_due(a, slot, p, data, count, maximum, event);
}

/* Internal loop fast path: the caller supplies an empty child envelope.
 * Common motion overwrites actor_event; firing alone can populate child fields. */
void bc_actor_segment_common_into(BcActorStepEvent *event, BcActor *actor,
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    segment_prepare(actor, slot, p, data, count, maximum, event);
    bc_actor_common_into(&event->actor_event, actor, p, &data->data, count);
}

/* $BC48: promote the next body segment, or finish the final three with
 * delayed explosions. Returns whether this actor explodes this update. */
static unsigned char segment_death_prepare(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot)
{
    BcActor *a = &actors[slot];
    if (a->dash_started != 0x48) return !--a->fired;
    unsigned char next = a->auxiliary == 255 ? a->probe_y : slot+1;
    unsigned char last = a->auxiliary == 255 ? actors[next].probe_y : slot+2;
    if (actors[last].dash_started == 0x54) {
        for (unsigned char i = 1; i <= 2; i++) {
            BcActor *b = &actors[i == 1 ? next : last];
            b->body.state = 0x40; b->fired = i * 10;
            bc_enemy_set_vx(&b->body, bc_enemy_set_vy(&b->body, 0));
        }
    } else {
        BcActor *b = &actors[next];
        b->dash_started = 0x48; b->body.cooldown = 30; b->body.timer = 1;
        b->sprite_base_ref = a->phase ? 0x36a4 : 0x369e;
        /* The dying head has this same variant's resolved head sprite base. */
        b->body.sprite_base = a->body.sprite_base;
    }
    return 1;
}

static void round_two_boss_entry(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    const BcWorldPlayer *p, const BcActorStepData *data, unsigned short handler)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 8 ? 0x7ef : 0;
    handler -= shift;
    if (handler == 0xacb2) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 240;
        a->wait = data->boss_active ? 41 : 26;
        signed short speed = data->boss_active ? 256 : 384;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, (y < 72 || (y < 168 && y < (unsigned char)(p->y >> 8))) ? speed : -speed);
        a->routine = 0xad16 + shift; a->wait--;
        actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
        return;
    }
    unsigned char part;
    switch (handler) {
    case 0xad87: case 0xad9e: part = 0; break;
    case 0xadb3: case 0xadca: part = 1; break;
    case 0xaddf: case 0xadf6: part = 2; break;
    default: part = 3; break;
    }
    static const unsigned short follow[4] = {0xad9e,0xadca,0xadf6,0xae29};
    if (handler != follow[part]) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x28; a->routine = follow[part] + shift;
    }
    unsigned char distance = part < 2 ? actors[0].phase : (unsigned char)(actors[0].phase - 14);
    unsigned short y = (bc_enemy_y(&actors[0].body)) + ((part & 1) ? distance : -(signed short)distance);
    bc_enemy_set_y(&a->body, y);
}

static signed short boss_two_shot(BcActor actors[BC_ACTOR_CAPACITY], unsigned char parent,
    const BcActorStepData *data, unsigned char initial, unsigned char side)
{
    unsigned short shift = data->round == 8 ? 0x7ef : 0;
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *b = &actors[slot], *a = &actors[parent];
    bc_actor_template(b, data->data.bytes + (0xb04e + shift) - data->data.origin, data->boss_spread_base);
    unsigned short x, y;
    if (initial) {
        x = 160; y = (bc_enemy_y(&actors[0].body)) + (side ? 28 : -28);
        b->wait = side ? 6 : 0;
        if (side) { b->body.attributes = (b->body.attributes & 0xff00) | 0x81; b->body.animation = (0xb0bb + shift); }
    } else {
        b->wait = a->wait + 1; if (b->wait == 12) b->wait = 0;
        const unsigned char *row = data->data.bytes + (0xb061 + shift) + b->wait * 4 - data->data.origin;
        x = (bc_enemy_x(&a->body)) + (signed char)row[0];
        y = (bc_enemy_y(&a->body)) + (signed char)row[1];
        b->body.animation = word(row + 2);
        b->body.attributes = (b->body.attributes & 0xff00) | (a->body.attributes & 255);
    }
    bc_enemy_set_x(&b->body, x);
    bc_enemy_set_y(&b->body, y);
    bc_enemy_set_vx(&b->body, bc_enemy_set_vy(&b->body, 0)); b->phase = 4;
    return slot;
}

static void __attribute__((noinline)) boss_two_cycle(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event, unsigned short handler)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 8 ? 0x7ef : 0;
    handler -= shift;
    if (handler == 0xad16) {
move:
        if (--a->wait) goto common;
        a->body.flags = 0x28; bc_enemy_set_vy(&a->body, 0); a->wait = 9; a->routine = 0xad35 + shift;
        handler = 0xad35;
    }
    if (handler == 0xad35) {
        a->phase += 2;
        if (--a->wait) goto common;
        a->wait = 20;
        for (unsigned char side = 0; side < 2; side++) {
            signed short child = boss_two_shot(actors, slot, data, 1, side);
            if (child < 0) break;
            unsigned char n = event->extra_count++;
            event->extra_slots[n] = child;
            bc_actor_common_into(&event->extra_events[n], &actors[child], p, &data->data, count);
        }
        a->routine = 0xad54 + shift; handler = 0xad54;
    }
    if (handler == 0xad54) {
        if (--a->wait) goto common;
        a->wait = 9; a->routine = 0xad68 + shift; handler = 0xad68;
    }
    if (handler == 0xad68) {
        a->phase -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29;
        a->wait = data->boss_active ? 41 : 26;
        signed short speed = data->boss_active ? 256 : 384;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, (y < 72 || (y < 168 && y < (unsigned char)(p->y >> 8))) ? speed : -speed);
        a->routine = 0xad16 + shift;
        goto move;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

/* Round-four core alternates an eight-shot ascending/descending beam sweep,
 * then opens its two moving shells. Preserve same-update state fallthroughs. */
static void __attribute__((noinline)) boss_four_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 8 ? 0x4c4 : 0;
    unsigned short handler = a->routine;
    const unsigned char *bytes = data->data.bytes;
    if (handler == (0xa972 + shift) || handler == (0xa989 + shift) || handler == (0xa99e + shift) || handler == (0xa9b5 + shift)) {
        unsigned char lower = handler == (0xa99e + shift) || handler == (0xa9b5 + shift);
        if (handler == (0xa972 + shift) || handler == (0xa99e + shift)) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x28; a->routine = lower ? (0xa9b5 + shift) : (0xa989 + shift);
        }
        unsigned short y = (bc_enemy_y(&actors[0].body)) + (lower ? actors[0].phase : -(signed short)actors[0].phase);
        bc_enemy_set_y(&a->body, y);
        return;
    }
    if (handler == (0xa824 + shift)) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 0xf0;
choose_direction:
        bc_enemy_set_vy(&a->body, data->boss_active ? 384 : 512);
        if ((unsigned short)(p->y >> 8) < (unsigned short)(bc_enemy_y(&a->body))) bc_enemy_set_vy(&a->body, -bc_enemy_vy(&a->body));
        handler = a->routine = (0xa878 + shift);
    }
    if (handler == (0xa878 + shift)) {
        unsigned char y = bc_enemy_y(&a->body);
        if (!((bc_enemy_vy(&a->body) < 0 && y < 80) || (bc_enemy_vy(&a->body) >= 0 && y >= 160) ||
              (unsigned char)((p->y >> 8) - y + 8) < 16)) goto common;
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->fired ^= 1; a->wait = 1;
        a->turn = a->fired ? 7 : 0;
        handler = a->routine = a->fired ? (0xa8f8 + shift) : (0xa8c5 + shift);
    }
    if (handler == (0xa8c5 + shift) || handler == (0xa8f8 + shift)) {
        if (--a->wait) goto common;
        a->wait = 10;
        if ((handler == (0xa8c5 + shift) && a->turn != 8) || (handler == (0xa8f8 + shift) && !(a->turn & 128))) {
            event->child_slot = bc_actor_allocate(actors, 0);
            if (event->child_slot >= 0) {
                BcActor *b = &actors[event->child_slot];
                bc_actor_template(b, bytes + (0xaafa + shift) - data->data.origin, data->boss_beam_base);
                unsigned short y = (bc_enemy_y(&actors[0].body)) + word(bytes + (0xab0d + shift) + actors[0].turn * 2 - data->data.origin);
                bc_enemy_set_x(&b->body, 0xe8);
                bc_enemy_set_y(&b->body, y);
                bc_enemy_set_vx(&b->body, -1024); bc_enemy_set_vy(&b->body, 0);
                bc_actor_common_into(&event->child_event, b, p, &data->data, count);
            }
            a->turn += handler == (0xa8c5 + shift) ? 1 : -1;
            goto common;
        }
        a->body.flags = 0x28; a->wait = 6; handler = a->routine = (0xa925 + shift);
    }
    if (handler == (0xa925 + shift)) {
        a->phase += 2;
        if (--a->wait) goto common;
        a->wait = 20; handler = a->routine = (0xa93f + shift);
    }
    if (handler == (0xa93f + shift)) {
        if (--a->wait) goto common;
        a->wait = 6; handler = a->routine = (0xa953 + shift);
    }
    if (handler == (0xa953 + shift)) {
        a->phase -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29;
        goto choose_direction;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

/* Round-five articulated boss: RNG-selected vertical runs and paired beams. */
static void __attribute__((noinline)) boss_five_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 8 ? 0x153b : 0;
    unsigned short handler = a->routine;
    const unsigned char *bytes = data->data.bytes;
    if (handler == (0xade5 + shift) || handler == (0xadfc + shift) || handler == (0xae11 + shift) || handler == (0xae28 + shift)) {
        unsigned char lower = handler == (0xae11 + shift) || handler == (0xae28 + shift);
        if (handler == (0xade5 + shift) || handler == (0xae11 + shift)) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x28; a->routine = lower ? (0xae28 + shift) : (0xadfc + shift);
        }
        unsigned short y = (bc_enemy_y(&actors[0].body)) + (lower ? actors[0].phase : -(signed short)actors[0].phase);
        bc_enemy_set_y(&a->body, y);
        return;
    }
    if (handler == (0xad03 + shift)) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 0xf0;
start_move:
        *data->random_state = bc_random_next(*data->random_state);
        a->wait = bytes[(data->boss_active ? (0xae92 + shift) : (0xaea2 + shift)) + ((*data->random_state >> 8) & 15) - data->data.origin];
        signed short speed = data->boss_active ? 320 : 448;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, (y < 72 || (y < 168 && y < (unsigned char)(p->y >> 8))) ? speed : -speed);
        handler = a->routine = (0xad71 + shift);
    }
    if (handler == (0xad71 + shift)) {
        if (--a->wait) goto common;
        a->body.flags = 0x28; bc_enemy_set_vy(&a->body, 0);
        a->wait = 7; handler = a->routine = (0xad93 + shift);
    }
    if (handler == (0xad93 + shift)) {
        a->phase += 2;
        if (--a->wait) goto common;
        a->wait = 31;
        for (unsigned char side = 0; side < 2; side++) {
            signed short child = bc_actor_allocate(actors, 0);
            if (child < 0) break;
            BcActor *b = &actors[child];
            bc_actor_template(b, bytes + (0xaf66 + shift) - data->data.origin, data->boss_beam_base);
            unsigned short y = (bc_enemy_y(&actors[0].body)) + word(bytes + (0xaf79 + shift) + side*2 - data->data.origin);
            bc_enemy_set_x(&b->body, 0xc8);
            bc_enemy_set_y(&b->body, y);
            bc_enemy_set_vx(&b->body, -768); bc_enemy_set_vy(&b->body, 0); b->auxiliary = 1;
            unsigned char n = event->extra_count++;
            event->extra_slots[n] = child;
            bc_actor_common_into(&event->extra_events[n], b, p, &data->data, count);
        }
        handler = a->routine = (0xadb2 + shift);
    }
    if (handler == (0xadb2 + shift)) {
        if (--a->wait) goto common;
        a->wait = 7; handler = a->routine = (0xadc6 + shift);
    }
    if (handler == (0xadc6 + shift)) {
        a->phase -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29; goto start_move;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

/* Homing shots emit no child or family events; steering precedes common motion. */
static inline __attribute__((always_inline)) void boss_three_homing_prepare(BcActor *a,
    BcWorldPlayer *p, const BcActorStepData *data)
{
    const unsigned char *bytes = data->data.bytes;
    if (!--a->phase) {
        a->phase = 10;
        if (a->speed != 8) a->speed += 2;
    }
    if (!--a->wait) {
        a->wait = 30;
        unsigned char aim = bc_aim16(0xffe0, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body));
        if (aim != a->direction) {
            unsigned char delta = a->direction - aim;
            a->direction = (a->direction + ((delta >> 2) & 2) - 1) & 15;
            a->body.animation = word(bytes + 0x8962 + a->direction * 2 - data->data.origin);
            a->body.timer = 1;
        }
    }
#if defined(__m68k__)
    if (data == boss_three_vector_data && a->speed <= 8 && !(a->speed & 1) && a->direction < 16) {
        const signed int *velocity = boss_three_vectors[a->speed >> 1][a->direction];
        a->body.motion_vx = velocity[0]; a->body.motion_vy = velocity[1];
        return;
    }
#endif
    unsigned short vector = word(bytes + 0x8262 + a->speed - data->data.origin) + a->direction * 4;
    bc_enemy_set_vx(&a->body, word(bytes + vector - data->data.origin));
    bc_enemy_set_vy(&a->body, word(bytes + vector + 2 - data->data.origin));
    return;
}

static void __attribute__((noinline)) boss_three_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 8 ? 0x527 : 0;
    unsigned short handler = a->routine;
    const unsigned char *bytes = data->data.bytes;
    if (handler == (0xadcf + shift)) {
        boss_three_homing_prepare(a, p, data);
        return;
    }
    if (handler == (0xac53 + shift) || handler == (0xac7f + shift)) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x28;
        a->routine = handler = handler == (0xac53 + shift) ? (0xac6a + shift) : (0xac96 + shift);
    }
    if (handler == (0xac6a + shift) || handler == (0xac96 + shift)) {
        unsigned short y = bc_enemy_y(&actors[0].body);
        y += handler == (0xac6a + shift) ? -actors[0].phase : actors[0].phase;
        bc_enemy_set_y(&a->body, y);
        return;
    }
    if (handler == (0xab7e + shift)) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 240;
        goto start_move;
    }
move:
    if (handler == (0xabe2 + shift)) {
        if (--a->wait) goto common;
        a->body.flags = 0x28; bc_enemy_set_vy(&a->body, 0);
        a->wait = 8; a->routine = handler = (0xac01 + shift);
    }
    if (handler == (0xac01 + shift)) {
        a->phase += 2;
        if (--a->wait) goto common;
        a->wait = 20;
        for (unsigned char i = 0; i < 5; i++) {
            signed short child = bc_actor_spawn_bullet(actors, slot, i + 6, &data->data,
                (0xae4a + shift), data->homing_base, 0x8262);
            if (child < 0) break;
            BcActor *b = &actors[child];
            bc_enemy_set_x(&b->body, 0xb6);
            b->wait = 40; b->phase = 10;
            b->body.animation = word(bytes + 0x8962 + (i + 6) * 2 - data->data.origin);
            unsigned char n = event->extra_count++;
            event->extra_slots[n] = child;
            bc_actor_common_into(&event->extra_events[n], b, p, &data->data, count);
        }
        a->routine = handler = (0xac20 + shift);
    }
    if (handler == (0xac20 + shift)) {
        if (--a->wait) goto common;
        a->wait = 8; a->routine = handler = (0xac34 + shift);
    }
    if (handler == (0xac34 + shift)) {
        a->phase -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29;
start_move:
        a->wait = data->boss_active ? 31 : 21;
        signed short speed = data->boss_active ? 256 : 448;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, (y < 48 || (y < 192 && y < (unsigned char)(p->y >> 8))) ? speed : -speed);
        a->routine = handler = (0xabe2 + shift);
        goto move;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

void __attribute__((noinline)) bc_actor_boss3_homing_common(BcActorEvent *event, BcActor *a,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count)
{
    boss_three_homing_prepare(a, p, data);
    bc_actor_common_into(event, a, p, &data->data, count);
}

static void __attribute__((noinline)) terrain_cycle_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 5 ? 0x4cf : 0;
    if (a->routine == (0xbb67 - shift)) {
        a->probe_x = a->probe_y = 0;
        if (!walker_solid(a, data)) return;
        bc_enemy_set_vx(&a->body, 0); a->body.flags = 16; a->body.cooldown = 255;
        a->phase = 80; a->routine = (0xbb94 - shift);
    }
    if (a->routine == (0xbb94 - shift)) {
        if (--a->phase) return;
        *data->random_state = bc_random_next(*data->random_state);
        if ((*data->random_state >> 8) >= 100) { a->phase = 50; return; }
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.cooldown = 255;
        a->phase = 50; a->routine = (0xbbca - shift);
    }
    if (a->routine == (0xbbca - shift)) {
        if (--a->phase) return;
        bc_enemy_set_vx(&a->body, a->wait ? -256 : 256); bc_enemy_set_vy(&a->body, 256);
        a->body.animation = a->wait ? (0xbcf2 - shift) : (0xbcdf - shift);
        a->body.cooldown = 0; a->body.timer = 1; a->phase = 32; a->routine = (0xbc22 - shift);
    }
    if (a->routine == (0xbc22 - shift)) {
        if (--a->phase) return;
        unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
        if (!((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
            event->fire_requested = 1;
            for (unsigned char i = 0; i < 2; i++) {
                unsigned char direction = a->wait ? 8 : 0;
                signed short child = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                    0x8b66 + data->relocation, data->homing_inherited_base, 0x8479 + data->relocation);
                if (child < 0) continue;
                BcActor *b = &actors[child];
                b->sprite_base_ref = 0x3684;
                b->body.attributes = (b->body.attributes & 0xff00) | (a->body.attributes & 255);
                b->wait = i ? 20 : 10;
                b->body.animation = word(data->data.bytes + 0x8b79 + data->relocation + direction*2 - data->data.origin);
                b->body.timer = 1;
                unsigned char n = event->extra_count++;
                event->extra_slots[n] = child;
                bc_actor_common_into(&event->extra_events[n], b, p, &data->data, count);
                (*count)++;
            }
        }
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->phase = 20; a->routine = (0xbc6c - shift);
    }
    if (a->routine == (0xbc6c - shift)) {
        if (--a->phase) return;
        bc_enemy_set_vx(&a->body, a->wait ? 256 : -256); bc_enemy_set_vy(&a->body, -256);
        a->body.animation = a->wait ? (0xbcfa - shift) : (0xbce7 - shift);
        a->phase = 32; a->body.timer = 1; a->routine = (0xbcc1 - shift);
    }
    if (a->routine == (0xbcc1 - shift) && !--a->phase) {
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.cooldown = 255;
        a->phase = 49; a->routine = (0xbbca - shift); /* falls through the first wait tick */
    }
}

/* Round-five/six turning surfacer. Entry delay and the subsequent half-circle
 * are separate source tasks; the upward-facing pause can launch two missiles. */
static void __attribute__((noinline)) surfacer_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    const unsigned char *bytes = data->data.bytes;
    if (a->routine == (data->round == 7 ? 0xc182 : data->round == 6 ? 0xbce7 : data->round == 5 ? 0xbc8d : 0xbb25)) {
        if (--a->wait) return;
        unsigned char px = p->x >> 8;
        if (!a->phase && (unsigned short)((bc_enemy_x(&a->body)) + 80 - px) >= 160) {
            a->wait = 1; return;
        }
        unsigned char right = px >= (unsigned char)(bc_enemy_x(&a->body));
        a->body.timer = 1; a->body.animation = data->round == 7 ? (right ? 0xc2b7 : 0xc2a8) : data->round == 6 ? (right ? 0xbe1c : 0xbe0d) : data->round == 5 ? (right ? 0xbdc2 : 0xbdb3) : (right ? 0xbc5a : 0xbc4b);
        a->direction = a->phase = right ? 0 : 8;
        a->routine = data->round == 7 ? 0xc215 : data->round == 6 ? 0xbd7a : data->round == 5 ? 0xbd20 : 0xbbb8; a->wait = 4;
    } else if (a->body.move_delay) {
        unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
        if ((a->body.move_delay == 18 || a->body.move_delay == 8) &&
            !((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
            event->fire_requested = 1;
            event->child_slot = bc_actor_spawn_bullet(actors, slot, a->phase, &data->data,
                0x8b66 + data->relocation, data->homing_inherited_base, 0x8479 + data->relocation);
            if (event->child_slot >= 0) {
                BcActor *child = &actors[event->child_slot];
                child->sprite_base_ref = 0x3684;
                child->body.attributes = (child->body.attributes & 0xff00) | (a->body.attributes & 255);
                child->wait = 32;
                child->body.animation = word(bytes + 0x8b79 + data->relocation + a->phase * 2 - data->data.origin);
                child->body.timer = 1;
                bc_actor_common_into(&event->child_event, child, p, &data->data, count);
                (*count)++;
            }
        }
        return;
    } else {
        if (--a->wait) return;
        a->direction = (a->direction + (a->phase ? 1 : -1)) & 15;
        if (a->direction == 12) a->body.move_delay = 20;
        if (!(a->direction & 7)) a->routine = 0x9eb1;
        a->wait = 2;
    }
    unsigned short vector = word(bytes + 0x8262 + a->speed - data->data.origin) + a->direction * 4;
    bc_enemy_set_vx(&a->body, word(bytes + vector - data->data.origin));
    bc_enemy_set_vy(&a->body, word(bytes + vector + 2 - data->data.origin));
}

/* Direct live straight-bullet path, equivalent to canonical $8A61 below.
 * Scrolling has already run. Terrain contact bypasses common but still ticks
 * damage_lock, and emits an empty actor event. */
void __attribute__((noinline)) bc_actor_straight_common_into(BcActorEvent *event,
    BcActor *a, BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count)
{
    a->probe_x = a->probe_y = 0;
    if (bc_terrain_solid(&data->terrain, data->camera_x + (bc_enemy_x(&a->body)),
                         data->camera_y + (bc_enemy_y(&a->body)))) {
        a->body.state = 0x40;
        if (a->body.damage_lock) a->body.damage_lock--;
        event_clear(event);
        return;
    }
    bc_actor_common_into(event, a, p, &data->data, count);
}

/* Only the expiry update needs aim/vector decoding. Keep its register-heavy
 * work out of the common four non-turning updates, preserving byte wrap. */
static void __attribute__((noinline)) actor_homing_turn(BcActor *a,
    BcWorldPlayer *p, const BcActorStepData *data)
{
    BcBulletFlight flight = {a->direction, a->speed, a->wait, 0, 0};
    BcEnemyBulletData resources = {data->data, 0x8479 + data->relocation,
        0x8b79 + data->relocation, 0x8abc + data->relocation, data->bullet_death_base};
    bc_enemy_bullet_turn(&a->body, &flight, p->x >> 8, p->y >> 8, &resources);
    a->direction = flight.direction; a->wait = flight.turn_timer;
}

/* Live homing flight has only an actor/common event, like straight flight.
 * Keep the source terrain-before-turn order and byte-sized timer wrap. */
void __attribute__((noinline)) bc_actor_homing_common_into(BcActorEvent *event,
    BcActor *a, BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count)
{
    a->probe_x = a->probe_y = 0;
    if (bc_terrain_solid(&data->terrain, data->camera_x + bc_enemy_x(&a->body),
                         data->camera_y + bc_enemy_y(&a->body))) {
        a->body.state = 0x40;
        if (a->body.damage_lock) a->body.damage_lock--;
        event_clear(event);
        return;
    }
    if (a->wait == 1) actor_homing_turn(a, p, data);
    else --a->wait;
    bc_actor_common_into(event, a, p, &data->data, count);
}

/* Same straight task with immutable terrain decoded at asset-build time. */
void __attribute__((noinline)) bc_actor_straight_map_into(BcActorEvent *event,
    BcActor *a, BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    const unsigned char *solid)
{
    unsigned short x = data->camera_x + (bc_enemy_x(&a->body));
    unsigned short y = data->camera_y + (bc_enemy_y(&a->body));
    a->probe_x = a->probe_y = 0;
    if (solid[((x >> 4) & 255) | ((y & 4080) << 4)]) {
        a->body.state = 0x40;
        if (a->body.damage_lock) a->body.damage_lock--;
        event_clear(event);
        return;
    }
    bc_actor_common_into(event, a, p, &data->data, count);
}

/* The caller validated this exact map against both immutable terrain sources. */
void __attribute__((noinline)) bc_actor_homing_map_into(BcActorEvent *event,
    BcActor *a, BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    const unsigned char *solid)
{
    unsigned short x = data->camera_x + (bc_enemy_x(&a->body));
    unsigned short y = data->camera_y + (bc_enemy_y(&a->body));
    a->probe_x = a->probe_y = 0;
    if (solid[((x >> 4) & 255) | ((y & 4080) << 4)]) {
        a->body.state = 0x40;
        if (a->body.damage_lock) a->body.damage_lock--;
        event_clear(event);
        return;
    }
    if (a->wait == 1) actor_homing_turn(a, p, data);
    else --a->wait;
    bc_actor_common_into(event, a, p, &data->data, count);
}

/* Final serpent: thirteen-update heading propagation and eight-way volleys. */
void __attribute__((noinline)) bc_actor_final_serpent_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    const unsigned char *bytes = data->data.bytes;
    if (!--a->wait) {
        a->wait = 13; a->turn = a->direction;
        if (a->dash_started == 0x48) {
            unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
            unsigned char inside = !((x | y) & 0xff00) && x >= 96 && x < 160 && y >= 88 && y < 152;
            unsigned char target = bc_aim16(inside ? p->x >> 8 : 128, inside ? p->y >> 8 : 120, x, y);
            if (target != a->direction) {
                unsigned char difference = a->direction - target;
                a->direction = (a->direction + ((difference >> 2) & 2) - 1) & 15;
            }
        } else a->direction = actors[slot-1].turn;
        a->body.animation = word(bytes + 0xa662 + a->direction*2 - data->data.origin);
        a->body.timer = 1;
        const unsigned char *vector = bytes + 0xa622 + a->direction*4 - data->data.origin;
        bc_enemy_set_vx(&a->body, word(vector)); bc_enemy_set_vy(&a->body, word(vector+2));
    }
    if (a->dash_started != 0x42 && !--a->phase) {
        a->phase = 80;
        unsigned char first = (*data->random_state >> 8) & 1;
        event->fire_requested = 1;
        for (unsigned char i = 0; i < 8; i++) {
            signed short child = bc_actor_spawn_bullet(actors, slot, first+i*2, &data->data,
                0x888d, data->bullet_base, 0x8262);
            if (child < 0) continue;
            unsigned char n = event->extra_count++;
            event->extra_slots[n] = child;
            bc_actor_common_into(&event->extra_events[n], &actors[child], p, &data->data, count);
            (*count)++;
        }
    }
    if (a->dash_started == 0x48 && !a->body.cooldown)
        a->body.attributes = (a->body.attributes & 0xff00) | 0x84;
}

/* Round-nine final core and six accelerating, curling missiles. */
static void __attribute__((noinline)) boss_final_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    const unsigned char *bytes = data->data.bytes;
    unsigned short handler = a->routine;
    if (handler == 0xc864) {
        if (!--a->turn) {
            a->direction += a->wait ? 1 : -1;
            a->body.animation = word(bytes + 0x8962 + a->direction * 2 - data->data.origin);
            a->body.timer = 1;
            unsigned short vector = word(bytes + 0x8262 + a->speed - data->data.origin) + a->direction * 4;
            bc_enemy_set_vx(&a->body, word(bytes + vector - data->data.origin));
            bc_enemy_set_vy(&a->body, word(bytes + vector + 2 - data->data.origin));
            if (!a->phase) {
                if (a->direction != 8) a->turn = 4;
                else {
                    a->phase++;
                    a->turn = bytes[0xc90e + ((*data->random_state >> 8) & 15) - data->data.origin];
                }
            } else {
                a->turn = 6;
                if ((a->direction & 7) == 4) a->routine = 0x9eb1;
            }
        }
        if (!--a->fired) {
            a->fired = 8;
            if (a->speed != 6) a->speed += 2;
        }
        return;
    }
    if (handler == 0xc6ce || handler == 0xc6e5 || handler == 0xc6fa || handler == 0xc711) {
        unsigned char lower = handler == 0xc6fa || handler == 0xc711;
        if (handler == 0xc6ce || handler == 0xc6fa) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x28; a->routine = lower ? 0xc711 : 0xc6e5;
        }
        unsigned short y = (bc_enemy_y(&actors[0].body)) + (lower ? actors[0].turn : -(int)actors[0].turn);
        bc_enemy_set_y(&a->body, y);
        return;
    }
    if (handler == 0xc5e1) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 240;
start_move:
        a->wait = data->boss_active ? 40 : 30;
        signed short speed = data->boss_active ? 256 : 384;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, y < 48 || (y < 192 && y < (unsigned char)(p->y >> 8)) ? speed : -speed);
        a->routine = handler = 0xc645;
    }
    if (handler == 0xc645) {
        if (--a->wait) goto common;
        a->body.flags = 0x28; bc_enemy_set_vy(&a->body, 0);
        a->wait = 8; a->routine = handler = 0xc664;
    }
    if (handler == 0xc664) {
        a->turn += 2;
        if (--a->wait) goto common;
        a->wait = 1; a->phase = 0; a->routine = handler = 0xc681;
    }
    if (handler == 0xc681) {
        if (--a->wait) goto common;
        a->wait = 4;
        if (a->phase != 6) {
            signed short child = bc_actor_allocate(actors, 0);
            if (child >= 0) {
                BcActor *b = &actors[child];
                bc_actor_template(b, bytes + 0xc8e3 - data->data.origin, data->homing_base);
                const unsigned char *position = bytes + 0xc8f6 + a->phase * 4 - data->data.origin;
                bc_enemy_set_x(&b->body, position[0]);
                unsigned short y = (bc_enemy_y(&a->body)) + (signed char)position[1];
                bc_enemy_set_y(&b->body, y);
                b->turn = position[3]; b->fired = 10; b->phase = 0; b->wait = position[2];
                b->direction = ((b->wait << 3) | 4) ^ 8;
                b->body.animation = word(bytes + 0x8962 + b->direction * 2 - data->data.origin);
                unsigned short vector = word(bytes + 0x8262 + b->speed - data->data.origin) + b->direction * 4;
                bc_enemy_set_vx(&b->body, word(bytes + vector - data->data.origin));
                bc_enemy_set_vy(&b->body, word(bytes + vector + 2 - data->data.origin));
                event->child_slot = child;
                bc_actor_common_into(&event->child_event, b, p, &data->data, count);
            }
            a->phase++;
            goto common;
        }
        a->wait = 8; a->routine = handler = 0xc6af;
    }
    if (handler == 0xc6af) {
        a->turn -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29; goto start_move;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

/* Round-seven core opens vertically; each shell owns an RNG-timed fan. */
/* Round-eight opening core and growing, turning projectile chains. */
static void __attribute__((noinline)) boss_eight_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event, unsigned short handler)
{
    BcActor *a = &actors[slot];
    const unsigned char *bytes = data->data.bytes;
    unsigned short shift = data->round == 8 ? 0xcaa : 0;
    handler -= shift;
    if (handler == 0xb475 || handler == 0xb47a) {
        if (handler == 0xb475) a->body.state = 0x80;
        if (--a->wait) return;
        signed short child = bc_actor_allocate(actors, 0);
        if (child < 0) return;
        BcActor *b = &actors[child];
        bc_actor_template(b, bytes + 0xb487 + shift - data->data.origin, data->boss_spread_base);
        b->phase = a->phase;
        unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
        if (b->phase) {
            y += b->phase == 1 ? 14 : -14;
            b->body.animation = (b->phase == 1 ? 0xb4cb : 0xb4d6) + shift;
        } else {
            x -= 14;
            if ((unsigned char)(p->x >> 8) >= (unsigned char)x) {
                b->phase = (unsigned char)(p->y >> 8) >= (unsigned char)y ? 1 : 2;
                b->body.animation = (b->phase == 1 ? 0xb4b5 : 0xb4c0) + shift;
            }
        }
        bc_enemy_set_x(&b->body, x);
        bc_enemy_set_y(&b->body, y);
        bc_enemy_set_vx(&b->body, bc_enemy_set_vy(&b->body, 0)); b->wait = 6;
        event->child_slot = child;
        bc_actor_common_into(&event->child_event,b,p,&data->data,count);
        return;
    }
    if (handler == 0xb1f3 || handler == 0xb20a || handler == 0xb228 || handler == 0xb23f) {
        unsigned char lower = handler == 0xb228 || handler == 0xb23f;
        if (handler == 0xb1f3 || handler == 0xb228) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x28; a->routine = (lower ? 0xb23f : 0xb20a) + shift;
        }
        unsigned short separation = ((unsigned short)actors[0].phase << 8) | actors[0].turn;
        a->body.y = actors[0].body.y + (unsigned int)((lower ? (int)separation : -(int)separation) * 256);
        return;
    }
    if (handler == 0xb0fc) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 240;
start_move:
        *data->random_state = bc_random_next(*data->random_state);
        a->wait = bytes[(data->boss_active ? 0xb2b2 : 0xb2c2) + shift + ((*data->random_state >> 8) & 15) - data->data.origin];
        signed short speed = data->boss_active ? 384 : 512;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, y < 80 || (y < 160 && y < (unsigned char)(p->y >> 8)) ? speed : -speed);
        handler = 0xb16a; a->routine = handler + shift;
    }
    if (handler == 0xb16a) {
        if (--a->wait) goto common;
        a->body.flags = 0x28; bc_enemy_set_vy(&a->body, 0);
        a->wait = 6; handler = 0xb189; a->routine = handler + shift;
    }
    if (handler == 0xb189) {
        a->phase += 2;
        if (--a->wait) goto common;
        a->wait = 1; a->fired = 0; handler = 0xb1a6; a->routine = handler + shift;
    }
    if (handler == 0xb1a6) {
        if (--a->wait) goto common;
        a->wait = 30;
        if (a->fired != 4) {
            signed short child = bc_actor_allocate(actors,0);
            if (child >= 0) {
                BcActor *b = &actors[child];
                bc_actor_template(b,bytes + 0xb487 + shift - data->data.origin,data->boss_spread_base);
                const unsigned char *position = bytes + 0xb49a + shift + a->fired * 4 - data->data.origin;
                bc_enemy_set_x(&b->body, word(position));
                bc_enemy_set_y(&b->body, (unsigned short)((bc_enemy_y(&a->body)) + word(position+2)));
                bc_enemy_set_vx(&b->body, bc_enemy_set_vy(&b->body, 0)); b->phase = 0; b->wait = 6;
                event->child_slot = child;
                bc_actor_common_into(&event->child_event,b,p,&data->data,count);
            }
            a->fired++;
            goto common;
        }
        a->wait = 6; handler = 0xb1d4; a->routine = handler + shift;
    }
    if (handler == 0xb1d4) {
        a->phase -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29; goto start_move;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

static void __attribute__((noinline)) boss_seven_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    unsigned short shift = data->round == 8 ? 0xec9 : 0;
    unsigned short handler = a->routine - shift;
    const unsigned char *bytes = data->data.bytes;
    if (handler == 0xaba7 || handler == 0xabbe || handler == 0xac30 || handler == 0xac47) {
        unsigned char lower = handler == 0xac30 || handler == 0xac47;
        if (handler == 0xaba7 || handler == 0xac30) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x28; a->routine = (lower ? 0xac47 : 0xabbe) + shift;
        }
        unsigned short separation = ((unsigned short)actors[0].phase << 8) | actors[0].turn;
        a->body.y = actors[0].body.y + (unsigned int)((lower ? (int)separation : -(int)separation) * 256);
        if (!--a->wait) {
            *data->random_state = bc_random_next(*data->random_state);
            a->wait = bytes[(data->boss_active ? 0xad0e : 0xad1e) + shift + ((*data->random_state >> 8) & 15) - data->data.origin];
            unsigned short y = (bc_enemy_y(&actors[0].body)) + (lower ? 56 : -56);
            a->turn = y; a->phase = y >> 8;
            unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, 200, y);
            *data->random_state = bc_random_next(*data->random_state);
            unsigned char kind = (*data->random_state >> 8) & 7;
            unsigned char shots = kind < 2 ? 5 : kind < 6 ? 3 : 1;
            direction -= shots / 2;
            event->fire_requested = 1;
            for (unsigned char i = 0; i < shots; i++) {
                signed short child = bc_actor_allocate(actors, 0);
                if (child < 0) break;
                BcActor *b = &actors[child];
                bc_actor_template(b, bytes + 0xae14 + shift - data->data.origin, data->boss_beam_base);
                bc_enemy_set_x(&b->body, 0xc8);
                bc_enemy_set_y(&b->body, y);
                b->direction = (direction + i) & 15;
                unsigned short vector = word(bytes + 0x8262 + b->speed - data->data.origin) + b->direction * 4;
                bc_enemy_set_vx(&b->body, word(bytes + vector - data->data.origin));
                bc_enemy_set_vy(&b->body, word(bytes + vector + 2 - data->data.origin));
                unsigned char n = event->extra_count++;
                event->extra_slots[n] = child;
                bc_actor_common_into(&event->extra_events[n], b, p, &data->data, count);
            }
        }
        return;
    }
    if (handler == 0xaacb) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 240;
start_move:
        a->wait = data->boss_active ? 31 : 16;
        signed short speed = data->boss_active ? 320 : 512;
        unsigned char y = bc_enemy_y(&a->body);
        bc_enemy_set_vy(&a->body, y < 72 || (y < 168 && y < (unsigned char)(p->y >> 8)) ? speed : -speed);
        handler = 0xab2f; a->routine = handler + shift;
    }
    if (handler == 0xab2f) {
        if (--a->wait) goto common;
        a->body.flags = 0x28; bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
        a->wait = 8; handler = 0xab57; a->routine = handler + shift;
    }
    if (handler == 0xab57) {
        a->phase += 2;
        if (--a->wait) goto common;
        a->wait = 20; handler = 0xab74; a->routine = handler + shift;
    }
    if (handler == 0xab74) {
        if (--a->wait) goto common;
        a->wait = 8; handler = 0xab88; a->routine = handler + shift;
    }
    if (handler == 0xab88) {
        a->phase -= 2;
        if (--a->wait) goto common;
        a->body.flags = 0x29; goto start_move;
    }
common:
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

/* Round-six core oscillation, opening shells and six-tick rain shots. */
static void __attribute__((noinline)) boss_six_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, BcActorStepEvent *event)
{
    BcActor *a = &actors[slot];
    signed short shift = data->round == 8 ? -0x586 : 0;
    unsigned short handler = a->routine - shift;
    if (handler == 0xb17c) {
        if (a->body.y & 0xff000000u) { bc_enemy_set_vx(&a->body, 0); bc_enemy_set_vy(&a->body, 512); a->routine = 0x9eb1; }
        return;
    }
    if (handler == 0xafe2 || handler == 0xaff9 || handler == 0xb017 || handler == 0xb02e) {
        unsigned char lower = handler == 0xb017 || handler == 0xb02e;
        if (handler == 0xafe2 || handler == 0xb017) {
            if (a->body.damage_lock) return;
            a->body.flags = 0x28; a->routine = (lower ? 0xb02e : 0xaff9) + shift;
        }
        unsigned short distance = ((unsigned short)actors[0].phase << 8) | actors[0].turn;
        a->body.y = actors[0].body.y + (unsigned int)((lower ? (int)distance : -(int)distance) * 256);
        return;
    }
    if (handler == 0xaf02) {
        if (a->body.damage_lock) return;
        a->body.flags = 0x29; a->body.cooldown = 240;
        a->fired = 1; a->dash_started = 0; bc_enemy_set_vy(&a->body, -384);
start_move:
        a->wait = data->boss_active ? 60 : 120; handler = 0xaf40; a->routine = handler + shift;
    }
    if (handler == 0xaf40) {
        if (--a->wait) {
            bc_enemy_set_vy(&a->body, (unsigned short)(bc_enemy_vy(&a->body) + ((unsigned char)(bc_enemy_y(&a->body)) < 128 ? 16 : -16)));
            goto common;
        }
        a->body.flags = 0x28; a->body.move_delay = 6; handler = 0xaf86; a->routine = handler + shift;
    }
    if (handler == 0xaf86) {
        a->phase += 2;
        if (a->body.move_delay) goto common;
        a->body.move_delay = 20; handler = 0xafa0; a->routine = handler + shift;
    }
    if (handler == 0xafa0) {
        if (a->body.move_delay) goto common;
        a->body.move_delay = 6; handler = 0xafb4; a->routine = handler + shift;
    }
    if (handler == 0xafb4) {
        a->phase -= 2;
        if (a->body.move_delay) goto common;
        a->body.flags = 0x29;
        goto start_move;
    }
common:
    if (!--a->fired) {
        a->fired = 6;
        signed short child = bc_actor_allocate(actors, 0);
        if (child >= 0) {
            BcActor *b = &actors[child];
            bc_actor_template(b, data->data.bytes + 0xb19e + shift - data->data.origin, data->boss_spread_base);
            bc_enemy_copy_x(&b->body, &a->body);
            bc_enemy_copy_y(&b->body, &a->body);
            *data->random_state = bc_random_next(*data->random_state);
            bc_enemy_set_vx(&b->body, (unsigned short)(-608 + 2*(*data->random_state >> 8) + (*data->random_state & 255)));
            bc_enemy_set_vy(&b->body, -384);
            event->child_slot = child;
            bc_actor_common_into(&event->child_event,b,p,&data->data,count);
        }
    }
    actors[1].body.damage_lock = actors[2].body.damage_lock = actors[0].body.damage_lock;
}

/* Round-six/eight pod splits into eight orbiting drones, or an aimed fan on death.
 * Return zero only for the source's state-$40 transition without common motion. */
static unsigned char __attribute__((noinline)) orbiter_prepare(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum, BcActorStepEvent *event, unsigned short handler)
{
    BcActor *a = &actors[slot];
    const unsigned char *bytes = data->data.bytes;
    unsigned short shift = data->round == 7 ? 0x1fa : 0;
    handler -= shift;
    if (handler == 0xac49 || handler == 0xaca9) {
        unsigned char dying = handler == 0xaca9;
        if (!dying && (unsigned short)(bc_enemy_x(&a->body)) >= 160) return 1;
        for (unsigned char n = 8; n; n--) {
            signed short child = bc_actor_allocate(actors, 0);
            if (child < 0) break;
            BcActor *b = &actors[child];
            bc_actor_template(b, bytes + 0xadcf + shift - data->data.origin, a->body.sprite_base);
            bc_enemy_copy_x(&b->body, &a->body);
            bc_enemy_copy_y(&b->body, &a->body);
            if (dying) {
                unsigned short table = 0xadfc + shift + (n-1)*2 - data->data.origin;
                b->direction = (bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&b->body), bc_enemy_y(&b->body)) + bytes[table]) & 15;
                b->body.move_delay = bytes[table+1]; b->routine = 0x9eb1;
            } else {
                b->turn = bc_enemy_x(&a->body); b->fired = bc_enemy_y(&a->body);
                b->direction = (n*2) & 15; b->wait = 15;
            }
            unsigned short vector = word(bytes + 0x8262 + b->speed - data->data.origin) + b->direction*4;
            bc_enemy_set_vx(&b->body, word(bytes + vector - data->data.origin));
            bc_enemy_set_vy(&b->body, word(bytes + vector + 2 - data->data.origin));
            unsigned char index = event->extra_count++;
            event->extra_slots[index] = child;
            bc_actor_common_into(&event->extra_events[index], b, p, &data->data, count);
        }
        a->body.state = 0x40;
        event->setup_sound = bc_actor_explosion(a, 1, data->large_explosion_base, 0x8f1e + data->relocation);
        return 1;
    }
    unsigned char fire = 0, end = 0;
    if (handler == 0xad34) {
        if (--a->wait) return 1;
        a->direction = (a->direction*2) & 31; a->routine = 0xad75 + shift;
        bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->wait = 1; a->phase = 100; fire = 1;
    } else {
        if (!--a->phase) { fire = 1; end = 1; }
        else if (!--a->wait) {
            unsigned short table = 0xae0c + shift + a->direction*2 - data->data.origin;
            bc_enemy_low_x(&a->body, (a->turn + bytes[table]));
            bc_enemy_low_y(&a->body, (a->fired + bytes[table+1]));
            a->wait = 2; a->direction = (a->direction+1) & 31;
        }
    }
    unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
    if (fire && !((x|y)&0xff00) && y >= 16 && y < 224 && *count < maximum) {
        event->fire_requested = 1;
        event->child_slot = bc_actor_spawn_bullet(actors, slot, bc_aim16(p->x >> 8, p->y >> 8,x,y),
            &data->data,0x8aa4+data->relocation,data->bullet_base,0x8479+data->relocation);
        if (event->child_slot >= 0) {
            bc_actor_common_into(&event->child_event,&actors[event->child_slot],p,&data->data,count);
            (*count)++;
        }
    }
    if (!end) return 1;
    a->body.state = 0x40;
    if (a->body.damage_lock) a->body.damage_lock--;
    return 0;
}

void bc_actor_curve_common_into(BcActorStepEvent *event, BcActor *a,
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    /* The caller initialized the child fields. Populate them directly rather
     * than constructing and copying a second event on every curve update. */
    curve_prepare(event, a, slot, p, &data->data, count, maximum,
        data->bullet_base, data->round, data->relocation);
    bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
}

static void turret_prepare(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    BcActor *a = &actors[slot];
    if (!--a->phase) {
        a->phase = 32;
        *data->random_state = bc_random_next(*data->random_state);
        unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
        if ((*data->random_state >> 8) < 100 && !((x | y) & 0xff00) &&
            y >= 16 && y < 224 && *count < maximum) {
            a->body.animation = data->round == 6 ? (a->wait ? 0xb5cf : 0xb5c8) : (a->wait ? 0xba75 : 0xba6e); a->body.timer = 1;
            unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, x, y);
            event->fire_requested = 1;
            /* The source checks the shot limit once for the whole burst.
             * Each successful birth gets its immediate update and count. */
            for (unsigned char i = 0; i < 3; i++) {
                signed short child = bc_actor_spawn_bullet(actors, slot, (direction + i - 1) & 15,
                    &data->data, 0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                if (child >= 0) {
                    unsigned char n = event->extra_count++;
                    event->extra_slots[n] = child;
                    bc_actor_common_into(&event->extra_events[n], &actors[child], p, &data->data, count);
                    (*count)++;
                }
            }
        }
    }
}

/* The loop has checked the live turret handler, resource layout and RNG. */
void bc_actor_turret_common_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    event->child_event = (BcActorEvent){0}; event->child_slot = -1;
    event->setup_sound = event->fire_requested = event->extra_count = 0;
    event->boss_defeat = 0; event->boss_center_y = 0; event->handled = 1;
    turret_prepare(event, actors, slot, p, data, count, maximum);
    bc_actor_common_into(&event->actor_event, &actors[slot], p, &data->data, count);
}

/* Shared diver preparation; callers preserve scroll and event-envelope order. */
static inline void __attribute__((always_inline)) diver_prepare(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    BcActor *a = &actors[slot];
        if (!a->body.move_delay) {
            if (!a->dash_started && !--a->fired) {
                unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                if (((*data->random_state >> 8) & 15) < 12 && !((x | y) & 0xff00) &&
                    y >= 16 && y < 224 && *count < maximum) {
                    event->fire_requested = 1;
                    event->child_slot = bc_actor_spawn_bullet(actors, slot,
                        bc_aim16(p->x >> 8, p->y >> 8, x, y), &data->data,
                        0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                    if (event->child_slot >= 0) {
                        bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                        (*count)++;
                    }
                }
                a->fired = 20;
            }
            if (!--a->phase) {
                unsigned char x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                unsigned char transition = 0;
                if (!a->wait) {
                    /* CLC before SBC makes this (enemy Y + 3 - player Y). */
                    if ((unsigned char)(y + 3 - (unsigned char)(p->y >> 8)) < 8) {
                        a->turn = (unsigned char)(p->x >> 8) >= 208;
                        a->wait++; a->dash_started++; transition = 1;
                        bc_enemy_set_vx(&a->body, 768); a->body.animation = data->round == 7 ? 0xb950 : data->round == 6 ? 0xb296 : data->round == 5 ? 0xb627 : data->round == 4 ? 0xb6a4 : data->round == 3 ? 0xb1d4 : data->round == 2 ? 0xb2cc : 0xb78b;
                    }
                } else if (a->wait == 1) {
                    if (x >= 224) {
                        a->wait++; transition = 1; bc_enemy_set_vx(&a->body, -768); a->body.animation = data->round == 7 ? 0xb945 : data->round == 6 ? 0xb28b : data->round == 5 ? 0xb61c : data->round == 4 ? 0xb699 : data->round == 3 ? 0xb1c9 : data->round == 2 ? 0xb2c1 : 0xb780;
                        if (!a->turn) a->routine = 0x9eb1;
                    }
                } else if (a->wait == 2 && x < 64) {
                    transition = 1; bc_enemy_set_vx(&a->body, 768); a->body.animation = data->round == 7 ? 0xb950 : data->round == 6 ? 0xb296 : data->round == 5 ? 0xb627 : data->round == 4 ? 0xb6a4 : data->round == 3 ? 0xb1d4 : data->round == 2 ? 0xb2cc : 0xb78b;
                    a->routine = 0x9eb1;
                }
                if (transition) { bc_enemy_set_vy(&a->body, 0); a->body.move_delay = 16; a->body.timer = 1; }
                a->phase = 1;
            }
        }
}

void bc_actor_diver_common_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY],
    unsigned char slot, BcWorldPlayer *p, const BcActorStepData *data,
    unsigned char *count, unsigned char maximum)
{
    diver_prepare(event, actors, slot, p, data, count, maximum);
    bc_actor_common_into(&event->actor_event, &actors[slot], p, &data->data, count);
}

/* Both actor loops need the specialized task body. Without this, LTO
 * outlines the large shared dispatcher and adds costly per-actor calls. */
#if defined(__m68k__)
__attribute__((always_inline)) inline
#endif
void bc_actor_step_into(BcActorStepEvent *event, BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped)
{
    /* Only extra_count entries are valid. Avoid clearing the ten-child
     * buffers for every ordinary enemy update on the 68000. */
    event->child_event = (BcActorEvent){0};
    event->child_slot = -1;
    event->setup_sound = event->fire_requested = event->handled = event->extra_count = 0;
    event->boss_defeat = 0; event->boss_center_y = 0;
    BcActor *a = &actors[slot];
    if (!a->body.state) { event->actor_event = (BcActorEvent){0}; event->handled = 1; return; }
    unsigned char alive = a->body.state == 0x80;
    unsigned short handler = alive ? a->routine : a->death_routine;
    /* Most projectile/effect slots go straight to the common task. Avoid the
     * family-dispatch comparisons and temporary AI state on this hot path. */
    if (handler == 0x9eb1) {
        event->handled = 1;
        bc_actor_scroll(a, dx, dy, stopped);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    /* Round-eight formations spend most of their lifetime in these two
     * curve tasks; bypass unrelated boss-family dispatch comparisons. */
    if (alive && data->round == 7) {
        if (handler == 0xb53b || handler == 0xb635) {
            event->handled = 1;
            bc_actor_scroll(a, dx, dy, stopped);
            bc_actor_curve_common_into(event, a, slot, p, data, count, maximum);
            return;
        }
        /* Segment trains are another frequent round-eight family. Preserve
         * relocated bullet precedence for custom resource sets. */
        if (handler == 0xbf27 &&
            (unsigned short)(handler - data->relocation) != 0x8a61 &&
            (unsigned short)(handler - data->relocation) != 0x8b17) {
            event->handled = 1;
            bc_actor_scroll(a, dx, dy, stopped);
            segment_prepare(a, slot, p, data, count, maximum, event);
            bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
            return;
        }
    }
    /* The two fast paths above always overwrite actor_event in common. */
    event->actor_event = (BcActorEvent){0};
    if ((data->round == 5 && ((alive && (handler == 0xac49 || handler == 0xad34 || handler == 0xad75)) ||
        (!alive && handler == 0xaca9))) ||
        (data->round == 7 && ((alive && (handler == 0xae43 || handler == 0xaf2e || handler == 0xaf6f)) ||
        (!alive && handler == 0xaea3)))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        if (orbiter_prepare(actors,slot,p,data,count,maximum,event,handler))
            bc_actor_common_into(&event->actor_event,a,p,&data->data,count);
        return;
    }
    if (!alive && data->round == 9 && handler == 0xa579) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        unsigned char explode;
        if (a->dash_started == 0x48 && actors[slot+2].dash_started == 0x54) {
            for (unsigned char i = 1; i <= 2; i++) {
                BcActor *last = &actors[slot+i];
                last->body.state = 0x40; last->fired = i*10;
                bc_enemy_set_vx(&last->body, bc_enemy_set_vy(&last->body, 0));
            }
            for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++)
                if (actors[i].body.state == 0x80) actors[i].body.state = 0;
            event->boss_defeat = 2; explode = 1;
        } else if (a->dash_started == 0x48) {
            BcActor *next = &actors[slot+1];
            next->dash_started = 0x48; next->body.cooldown = 120;
            next->body.attributes = (next->body.attributes & 0xff00) | 0x83;
            next->sprite_base_ref = 0x36d0; next->body.sprite_base = a->body.sprite_base;
            next->body.timer = 1; explode = 1;
        } else explode = !--a->fired;
        if (explode) event->setup_sound = bc_actor_explosion(a, 1,
            data->large_explosion_base, 0x8f1e + data->relocation);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && data->round == 9 && handler == 0xa446) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        bc_actor_final_serpent_prepare(actors, slot, p, data, count, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && data->round == 8 && (handler == 0xc5e1 || handler == 0xc645 ||
        handler == 0xc664 || handler == 0xc681 || handler == 0xc6af || handler == 0xc6ce ||
        handler == 0xc6e5 || handler == 0xc6fa || handler == 0xc711 || handler == 0xc864)) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        boss_final_prepare(actors, slot, p, data, count, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if ((data->round == 7 && ((alive && (handler == 0xb0fc || handler == 0xb16a || handler == 0xb189 ||
        handler == 0xb1a6 || handler == 0xb1d4 || handler == 0xb1f3 || handler == 0xb20a ||
        handler == 0xb228 || handler == 0xb23f || handler == 0xb47a)) || (!alive && handler == 0xb475))) ||
        (data->round == 8 && ((alive && (handler == 0xbda6 || handler == 0xbe14 || handler == 0xbe33 || handler == 0xbe50 || handler == 0xbe7e || handler == 0xbe9d || handler == 0xbeb4 || handler == 0xbed2 || handler == 0xbee9 || handler == 0xc124)) || (!alive && handler == 0xc11f)))) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
        boss_eight_prepare(actors,slot,p,data,count,event,handler);
        bc_actor_common_into(&event->actor_event,a,p,&data->data,count);
        return;
    }
    if (data->round == 6 && ((alive && (handler == 0xb330 || handler == 0xb3ef)) ||
        (!alive && handler == 0xb400))) {
        if (handler == 0xb330 && !data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        if (handler == 0xb330) {
            if (!--a->phase) {
                a->phase = 48;
                *data->random_state = bc_random_next(*data->random_state);
                if ((*data->random_state >> 8) >= 180) {
                    a->body.animation = a->wait ? 0xb3b2 : 0xb3ab; a->body.timer = 1;
                    event->fire_requested = 1;
                    event->child_slot = bc_actor_spawn_bullet(actors, slot,
                        bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body)),
                        &data->data, 0xb458, data->boss_spread_base, 0x8262);
                    if (event->child_slot >= 0)
                        bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                }
            }
        } else if (handler == 0xb3ef) {
            a->probe_x = a->probe_y = 0;
            if (walker_solid(a, data)) {
                a->body.state = 0x40;
                if (a->body.damage_lock) a->body.damage_lock--;
                return;
            }
        } else {
            a->body.state = 0x80; a->body.flags = 0x11;
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.timer = 1;
            a->body.animation = 0xb472; a->sprite_base_ref = 0x367e;
            a->body.sprite_base = data->large_explosion_base; a->body.attributes = 0x1181;
            a->half_x = a->half_y = 10;
            a->routine = 0x9eb1; a->death_routine = 0x8c9e;
        }
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (data->round == 7 && alive && (handler == 0xbcec || handler == 0xbd29)) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        if (!--a->wait) {
            unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body));
            if (handler == 0xbd29) {
                const unsigned char *bytes = data->data.bytes;
                a->direction = direction;
                a->body.animation = word(bytes + 0xbd92 + direction * 2 - data->data.origin);
                unsigned short vector = word(bytes + 0x8262 + a->speed - data->data.origin) + direction * 4;
                bc_enemy_set_vx(&a->body, word(bytes + vector - data->data.origin));
                bc_enemy_set_vy(&a->body, word(bytes + vector + 2 - data->data.origin));
                a->body.timer = 1; a->routine = 0xbcec; a->wait = 24;
            } else if (direction == a->direction) a->wait = 24;
            else {
                a->wait = 32; bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
                a->body.animation = 0xbe02; a->body.timer = 1; a->routine = 0xbd29;
            }
        }
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    unsigned short canonical = handler - data->relocation;
    /* Bullet tasks are frequent during boss fights. Dispatch before testing
     * the unrelated creature families, preserving scroll/common task order. */
    unsigned char bullet = alive && (canonical == 0x8a61 || canonical == 0x8b17);
    unsigned char bullet_death = !alive && canonical == 0x8a72;
    if (bullet || bullet_death) {
        event->handled = 1;
        bc_actor_scroll(a, dx, dy, stopped);
        if (a->body.state != 0x80) {
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
            a->body.timer = 1;
            a->body.animation = 0x8abc + data->relocation;
            a->body.sprite_base = data->bullet_death_base;
            a->sprite_base_ref = 0x367a; a->death_routine = 0x9eb1;
        } else {
            unsigned char terrain_hit;
            if (canonical == 0x8a61) {
                /* Straight shots have no heading timer or resource lookups. */
                a->probe_x = a->probe_y = 0;
                terrain_hit = bc_terrain_solid(&data->terrain,
                    data->camera_x + (bc_enemy_x(&a->body)), data->camera_y + (bc_enemy_y(&a->body)));
                if (terrain_hit) a->body.state = 0x40;
            } else {
                BcBulletFlight b = {a->direction, a->speed, a->wait, a->probe_x, a->probe_y};
                BcEnemyBulletData resources = {data->data, 0x8479 + data->relocation,
                    0x8b79 + data->relocation, 0x8abc + data->relocation, data->bullet_death_base};
                terrain_hit = bc_enemy_bullet_flight(&a->body, &b, 1,
                    p->x >> 8, p->y >> 8, data->camera_x, data->camera_y, &data->terrain, &resources);
                a->direction = b.direction; a->speed = b.speed;
                a->wait = b.turn_timer; a->probe_x = b.probe_x; a->probe_y = b.probe_y;
            }
            if (terrain_hit) {
                /* $A20A bypasses common movement/collisions but ticks the lock. */
                if (a->body.damage_lock) a->body.damage_lock--;
                return;
            }
        }
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (data->round == 3 && ((alive && (handler == 0xb26e || handler == 0xb32d)) ||
        (!alive && handler == 0xb33e))) {
        if (handler == 0xb26e && !data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        if (handler == 0xb26e) {
            if (!--a->phase) {
                a->phase = 48;
                *data->random_state = bc_random_next(*data->random_state);
                if ((*data->random_state >> 8) >= 180) {
                    a->body.animation = a->wait ? 0xb2f0 : 0xb2e9; a->body.timer = 1;
                    unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, bc_enemy_x(&a->body), bc_enemy_y(&a->body));
                    event->fire_requested = 1;
                    event->child_slot = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                        0xb396, data->boss_spread_base, 0x8262);
                    if (event->child_slot >= 0)
                        bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                }
            }
        } else if (handler == 0xb32d) {
            a->probe_x = a->probe_y = 0;
            if (walker_solid(a, data)) {
                a->body.state = 0x40;
                if (a->body.damage_lock) a->body.damage_lock--;
                return;
            }
        } else {
            a->body.state = 0x80; a->body.flags = 0x11;
            bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->body.timer = 1;
            a->body.animation = 0xb3b0; a->sprite_base_ref = 0x367e;
            a->body.sprite_base = data->large_explosion_base; a->body.attributes = 0x1181;
            a->half_x = a->half_y = 10; a->routine = 0x9eb1; a->death_routine = 0x8c9e;
        }
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && (data->round == 2 || data->round == 3 || data->round == 5)) {
        if (data->round == 3 && (handler == 0xa824 || handler == 0xa878 || handler == 0xa8c5 ||
            handler == 0xa8f8 || handler == 0xa925 || handler == 0xa93f || handler == 0xa953 ||
            handler == 0xa972 || handler == 0xa989 || handler == 0xa99e || handler == 0xa9b5)) {
            event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
            boss_four_prepare(actors, slot, p, data, count, event);
            bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
            return;
        }
        if (data->round == 2 && (handler == 0xab7e || handler == 0xabe2 ||
            handler == 0xac01 || handler == 0xac20 || handler == 0xac34 || handler == 0xac53 ||
            handler == 0xac6a || handler == 0xac7f || handler == 0xac96 || handler == 0xadcf)) {
            event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
            boss_three_prepare(actors, slot, p, data, count, event);
            bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
            return;
        }
        if ((data->round == 2 && (handler == 0xbb67 || handler == 0xbb94 ||
            handler == 0xbbca || handler == 0xbc22 || handler == 0xbc6c || handler == 0xbcc1)) ||
            (data->round == 5 && (handler == 0xb698 || handler == 0xb6c5 || handler == 0xb6fb ||
            handler == 0xb753 || handler == 0xb79d || handler == 0xb7f2))) {
            if (!data->random_state) return;
            event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
            terrain_cycle_prepare(actors, slot, p, data, count, maximum, event);
            bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
            return;
        }
        if (data->round == 2 && (handler == 0xb359 || handler == 0xb396)) {
            event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
            bc_actor_reaim_common(&event->actor_event, a, p, &data->data, count);
            return;
        }
        if ((data->round == 2 && handler == 0xba56) || (data->round == 3 && handler == 0xba46)) {
            if (!data->random_state) return;
            event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
            if (!--a->phase) {
                a->phase = 32;
                *data->random_state = bc_random_next(*data->random_state);
                unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                if ((*data->random_state >> 8) < 200 && !((x | y) & 0xff00) &&
                    y >= 16 && y < 224 && *count < maximum) {
                    const unsigned char *pose = data->data.bytes + (data->round == 3 ? 0xbad5 : 0xbae5) + a->wait * 3 - data->data.origin;
                    unsigned char direction = pose[0];
                    a->body.animation = word(pose + 1); a->body.timer = 1;
                    event->fire_requested = 1;
                    event->child_slot = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                        0x8b66 + data->relocation, data->homing_base, 0x8479 + data->relocation);
                    if (event->child_slot >= 0) {
                        BcActor *child = &actors[event->child_slot];
                        child->wait = 42;
                        child->body.animation = word(data->data.bytes + 0x8b79 + data->relocation + direction * 2 - data->data.origin);
                        child->body.timer = 1;
                        bc_actor_common_into(&event->child_event, child, p, &data->data, count);
                        (*count)++;
                    }
                }
            }
            bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
            return;
        }
    }
    if (alive && data->round == 8 && (handler == 0xace8 || handler == 0xad3c || handler == 0xad89 || handler == 0xadbc || handler == 0xade9 || handler == 0xae03 || handler == 0xae17 || handler == 0xae36 || handler == 0xae4d || handler == 0xae62 || handler == 0xae79)) {
        event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
        boss_four_prepare(actors,slot,p,data,count,event);
        bc_actor_common_into(&event->actor_event,a,p,&data->data,count);
        return;
    }
    if (alive && data->round == 8 && (handler == 0xb0a5 || handler == 0xb109 || handler == 0xb128 ||
        handler == 0xb147 || handler == 0xb15b || handler == 0xb17a || handler == 0xb191 ||
        handler == 0xb1a6 || handler == 0xb1bd || handler == 0xb2f6)) {
        event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
        boss_three_prepare(actors,slot,p,data,count,event);
        bc_actor_common_into(&event->actor_event,a,p,&data->data,count);
        return;
    }
    if (data->round == 8) {
        unsigned short local = handler - 0x7ef;
        if ((alive && local == 0xb041) || (!alive && local == 0xb03c)) {
            event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
            if (!alive) a->body.state = 0x80;
            if (!--a->phase) {
                event->child_slot = boss_two_shot(actors,slot,data,0,0);
                if (event->child_slot >= 0)
                    bc_actor_common_into(&event->child_event,&actors[event->child_slot],p,&data->data,count);
            }
        } else if (alive && (local == 0xad16 || local == 0xad35 || local == 0xad54 || local == 0xad68)) {
            event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
            boss_two_cycle(actors,slot,p,data,count,event,handler);
        } else if (alive && (local == 0xacb2 || local == 0xad87 || local == 0xad9e || local == 0xadb3 ||
            local == 0xadca || local == 0xaddf || local == 0xadf6 || local == 0xae12 || local == 0xae29)) {
            event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
            round_two_boss_entry(actors,slot,p,data,handler);
        }
        if (event->handled) { bc_actor_common_into(&event->actor_event,a,p,&data->data,count); return; }
    }
    if (data->round == 1 && ((alive && handler == 0xb041) || (!alive && handler == 0xb03c))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        if (!alive) a->body.state = 0x80;
        if (!--a->phase) {
            event->child_slot = boss_two_shot(actors, slot, data, 0, 0);
            if (event->child_slot >= 0)
                bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
        }
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && data->round == 1 && (handler == 0xad16 || handler == 0xad35 || handler == 0xad54 || handler == 0xad68)) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        boss_two_cycle(actors, slot, p, data, count, event, handler);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && data->round == 1 && (handler == 0xacb2 || handler == 0xad87 ||
        handler == 0xad9e || handler == 0xadb3 || handler == 0xadca || handler == 0xaddf ||
        handler == 0xadf6 || handler == 0xae12 || handler == 0xae29)) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        round_two_boss_entry(actors, slot, p, data, handler);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (!alive && ((data->round == 1 && handler == 0xbc48) || (data->round == 2 && handler == 0xb78d) || (data->round == 3 && handler == 0xb8c2) || (data->round == 4 && handler == 0xb887) || (data->round == 6 && handler == 0xb8d1) || (data->round == 7 && handler == 0xbff1))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        if (segment_death_prepare(actors, slot))
            event->setup_sound = bc_actor_explosion(a, 0, data->small_explosion_base, 0x8f15 + data->relocation);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && ((data->round == 1 && handler == 0xbb7e) || (data->round == 2 && handler == 0xb6c3) || (data->round == 3 && handler == 0xb7f8) || (data->round == 4 && handler == 0xb7bd) || (data->round == 6 && handler == 0xb807) || (data->round == 7 && handler == 0xbf27))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        segment_prepare(a, slot, p, data, count, maximum, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if ((data->round == 1 && ((alive &&
        (handler == 0xbdad || handler == 0xbe08 || handler == 0xbe24)) || (!alive && handler == 0xbe4e))) ||
        (data->round == 6 && ((alive && (handler == 0xba36 || handler == 0xba91 || handler == 0xbaad)) ||
        (!alive && handler == 0xbad7)))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        ceiling_prepare(actors, slot, p, data, handler);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if ((data->round == 4 && ((alive && handler == 0xaf52) || (!alive && handler == 0xaf4d))) ||
        (data->round == 8 && ((alive && handler == 0xc48d) || (!alive && handler == 0xc488)))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        /* Source $AF4F deliberately addresses slot zero, not the beam slot. */
        if (!alive) actors[0].body.state = 0x80;
        bc_enemy_set_vx(&a->body, (unsigned short)(bc_enemy_vx(&a->body) - 32));
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && ((data->round == 6 && (handler == 0xaacb || handler == 0xab2f || handler == 0xab57 ||
        handler == 0xab74 || handler == 0xab88 || handler == 0xaba7 || handler == 0xabbe ||
        handler == 0xac30 || handler == 0xac47)) ||
        (data->round == 8 && (handler == 0xb994 || handler == 0xb9f8 || handler == 0xba20 || handler == 0xba3d || handler == 0xba51 || handler == 0xba70 || handler == 0xba87 || handler == 0xbaf9 || handler == 0xbb10)))) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        boss_seven_prepare(actors, slot, p, data, count, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && ((data->round == 5 && (handler == 0xaf02 || handler == 0xaf40 || handler == 0xaf86 ||
        handler == 0xafa0 || handler == 0xafb4 || handler == 0xafe2 || handler == 0xaff9 ||
        handler == 0xb017 || handler == 0xb02e || handler == 0xb17c)) ||
        (data->round == 8 && (handler == 0xa97c || handler == 0xa9ba || handler == 0xaa00 || handler == 0xaa1a || handler == 0xaa2e || handler == 0xaa5c || handler == 0xaa73 || handler == 0xaa91 || handler == 0xaaa8 || handler == 0xabf6)))) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a,dx,dy,stopped);
        boss_six_prepare(actors,slot,p,data,count,event);
        bc_actor_common_into(&event->actor_event,a,p,&data->data,count);
        return;
    }
    if (alive && ((data->round == 4 && (handler == 0xad03 || handler == 0xad71 || handler == 0xad93 ||
        handler == 0xadb2 || handler == 0xadc6 || handler == 0xade5 || handler == 0xadfc || handler == 0xae11 || handler == 0xae28)) || (data->round == 8 && (handler == 0xc23e || handler == 0xc2ac || handler == 0xc2ce || handler == 0xc2ed || handler == 0xc301 || handler == 0xc320 || handler == 0xc337 || handler == 0xc34c || handler == 0xc363)))) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        boss_five_prepare(actors, slot, p, data, count, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && ((data->round == 4 && (handler == 0xbb25 || handler == 0xbbb8)) ||
        (data->round == 5 && (handler == 0xbc8d || handler == 0xbd20)) ||
        (data->round == 6 && (handler == 0xbce7 || handler == 0xbd7a)) ||
        (data->round == 7 && (handler == 0xc182 || handler == 0xc215)))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        surfacer_prepare(actors, slot, p, data, count, maximum, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (alive && ((data->round == 3 && (handler == 0xb4dc || handler == 0xb513 || handler == 0xb54e)) ||
        (data->round == 7 && (handler == 0xba5c || handler == 0xba93 || handler == 0xbace)))) {
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        formation_prepare(actors, slot, p, data, count, maximum, event);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    if (!alive && ((data->round == 3 && handler == 0xb592) || (data->round == 7 && handler == 0xbb12))) {
        a->wait = 0x47; canonical = 0x8eb5;
    }
    if (alive && ((data->round == 1 &&
        (handler == 0xb137 || handler == 0xb1a6 || handler == 0xb270 || handler == 0xb2d1)) ||
        (data->round == 3 &&
        (handler == 0xab80 || handler == 0xabef || handler == 0xacb9 || handler == 0xad1a)) ||
        (data->round == 4 &&
        (handler == 0xb050 || handler == 0xb0bf || handler == 0xb189 || handler == 0xb1ea)))) {
        if (!data->random_state) return;
        event->handled = 1; bc_actor_scroll(a, dx, dy, stopped);
        walker_prepare(actors, slot, p, data, count, maximum, event, handler);
        bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
        return;
    }
    /* Classify once instead of keeping sixteen family booleans live across
     * the entire dispatcher. This reduces 68000 register spills per actor. */
    enum { NONE, BOSS, BOSS_PART_DEATH, BOSS_DEFEAT, BOSS_SHOT_REVIVE,
        CURVE, EXPLOSION, JUMPER, ITEM_OPEN, HOPPER, LAUNCHER, HOVER,
        HOVER_DEATH, MOVING_ITEM, DIVER, TURRET, BURST_TURRET, PAIRED } action = NONE;
    if (canonical == 0x86f0) action = MOVING_ITEM;
    else if (alive) {
        if (!data->round) {
            switch (handler) {
            case 0xb3bf: case 0xb3e3: case 0xb471: case 0xb488: action = BOSS; break;
            case 0xad31: case 0xae2b: case 0xaa8e: case 0xab88: action = CURVE; break;
            case 0xaed3: action = JUMPER; break;
            case 0xb11f: action = HOPPER; break;
            case 0xb28f: action = LAUNCHER; break;
            case 0xac29: case 0xac4b: action = HOVER; break;
            }
        } else if (data->round == 1) {
            switch (handler) {
            case 0xb7fc: case 0xb8f6: case 0xb376: case 0xb470: action = CURVE; break;
            case 0xb511: case 0xb533: action = HOVER; break;
            case 0xb636: action = DIVER; break;
            case 0xb9d2: action = TURRET; break;
            }
        } else if (data->round == 2) {
            switch (handler) {
            case 0xaeb7: case 0xafb1: action = CURVE; break;
            case 0xb052: case 0xb074: action = HOVER; break;
            case 0xb177: action = DIVER; break;
            case 0xb518: action = BURST_TURRET; break;
            case 0xb90a: action = PAIRED; break;
            }
        } else if (data->round == 3) {
            if (handler == 0xaf5a || handler == 0xaf7c) action = HOVER;
            else if (handler == 0xb07f) action = DIVER;
            else if (handler == 0xbb4c) action = HOPPER;
            else if (handler == 0xadbf || handler == 0xaeb9) action = CURVE;
        } else if (data->round == 4) {
            if (handler == 0xb42a || handler == 0xb44c) action = HOVER;
            else if (handler == 0xb54f) action = DIVER;
            else if (handler == 0xb9cc) action = LAUNCHER;
            else if (handler == 0xb28f || handler == 0xb389) action = CURVE;
        } else if (data->round == 8) {
            if (handler == 0xc960 || handler == 0xc982) action = HOVER;
            else if (handler == 0xa5e8 || handler == 0xa60c || handler == 0xa69a || handler == 0xa6b1) action = BOSS;
        } else if (data->round == 7) {
            if (handler == 0xb6d6 || handler == 0xb6f8) action = HOVER;
            else if (handler == 0xb7fb) action = DIVER;
        } else if (data->round == 6) {
            if (handler == 0xb01c || handler == 0xb03e) action = HOVER;
            else if (handler == 0xae81 || handler == 0xaf7b) action = CURVE;
            else if (handler == 0xb141) action = DIVER;
            else if (handler == 0xbb8e) action = LAUNCHER;
            else if (handler == 0xb65c) action = BURST_TURRET;
            else if (handler == 0xb52c) action = TURRET;
        } else if (data->round == 5) {
            if (handler == 0xb3ad || handler == 0xb3cf) action = HOVER;
            else if (handler == 0xb212 || handler == 0xb30c) action = CURVE;
            else if (handler == 0xb4d2) action = DIVER;
            else if (handler == 0xb885) action = JUMPER;
            else if (handler == 0xbad1) action = HOPPER;
        }
    } else {
        switch (canonical) {
        case 0x8e78: action = BOSS_PART_DEATH; break;
        case 0x8e95: case 0x8eb5: case 0x8ec1: action = EXPLOSION; break;
        case 0x88cb: action = ITEM_OPEN; break;
        }
        if (!data->round) {
            if (handler == 0xb497) action = BOSS_DEFEAT;
            else if (handler == 0xb5c2) action = BOSS_SHOT_REVIVE;
            else if (handler == 0xac9e) action = HOVER_DEATH;
        } else if (data->round == 1) {
            if (handler == 0xae45) action = BOSS_DEFEAT;
            else if (handler == 0xb586) action = HOVER_DEATH;
        } else if (data->round == 2) {
            if (handler == 0xb0c7) action = HOVER_DEATH;
            else if (handler == 0xacab) action = BOSS_DEFEAT;
        } else if (data->round == 3) {
            if (handler == 0xafcf) action = HOVER_DEATH;
            else if (handler == 0xa9ca) action = BOSS_DEFEAT;
            else if (handler == 0xaaf2) action = BOSS_SHOT_REVIVE;
        } else if (data->round == 4) {
            if (handler == 0xb49f) action = HOVER_DEATH;
            else if (handler == 0xae3d) action = BOSS_DEFEAT;
        } else if (data->round == 8) {
            if (handler == 0xc9d5) action = HOVER_DEATH;
            else if (handler == 0xa7eb || handler == 0xafb6) action = BOSS_SHOT_REVIVE;
            else if (handler == 0xa6c0 || handler == 0xb634 || handler == 0xb1d2 || handler == 0xae8e || handler == 0xc378 || handler == 0xaac6 || handler == 0xbb82 || handler == 0xbf07 || handler == 0xc726) action = BOSS_DEFEAT;
        } else if (data->round == 7) {
            if (handler == 0xb74b) action = HOVER_DEATH;
            else if (handler == 0xb25d) action = BOSS_DEFEAT;
        } else if (data->round == 6) {
            if (handler == 0xb091) action = HOVER_DEATH;
            else if (handler == 0xacb9) action = BOSS_DEFEAT;
        } else if (data->round == 5) {
            if (handler == 0xb422) action = HOVER_DEATH;
            else if (handler == 0xb04c) action = BOSS_DEFEAT;
        }
    }
    if (action == NONE) return;
    if (((action == HOVER) || (action == HOVER_DEATH) || (action == TURRET) || (action == DIVER)) && !data->random_state) return;
    event->handled = 1;
    bc_actor_scroll(a, dx, dy, stopped);
    if (action == BOSS_DEFEAT) {
        /* $B497/$8E5C: task 2 owns the later explosion sequence. */
        unsigned char parts = (data->round == 1 || (data->round == 8 && handler == 0xb634)) ? 5 : ((data->round >= 2 && data->round <= 7) || (data->round == 8 && (handler == 0xb1d2 || handler == 0xae8e || handler == 0xc378 || handler == 0xaac6 || handler == 0xbb82 || handler == 0xbf07 || handler == 0xc726))) ? 3 : 2;
        for (unsigned char i = 1; i < parts; i++) actors[i].body.state = 0x40;
        for (unsigned char i = parts; i < BC_ACTOR_CAPACITY; i++)
            if (!actors[i].pickup) actors[i].body.state = 0;
        event->boss_defeat = 1; event->boss_center_y = bc_enemy_y(&a->body);
        event->setup_sound = 13;
        a->body.animation = 0x8e94 + data->relocation; a->body.timer = 80; a->death_routine = 0x9eb1;
    } else if (action == BOSS_PART_DEATH) {
        a->body.animation = 0x8e94 + data->relocation;
        a->body.timer = 80; a->death_routine = 0x9eb1;
    } else if (action == BOSS) {
        boss_prepare(actors, slot, p, data, count, event);
    } else if (action == BOSS_SHOT_REVIVE) {
        a->body.state = 0x80;
    } else if (action == JUMPER) {
        BcEnemyFireEvent fire = jumper_prepare(a, p, data, *count, maximum);
        if (fire.fire) {
            event->fire_requested = 1;
            event->child_slot = bc_actor_spawn_bullet(actors, slot, fire.direction, &data->data,
                0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
            if (event->child_slot >= 0) {
                bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                (*count)++;
            }
        }
    } else if (action == DIVER) {
        diver_prepare(event, actors, slot, p, data, count, maximum);
    } else if (action == PAIRED) {
        if (!a->body.move_delay && !--a->turn) {
            if (a->wait == 0x4f) {
                a->wait = 0x43; a->body.move_delay = 50; a->turn = 128;
                bc_enemy_set_vx(&a->body, a->phase == 0x4c ? 64 : -64);
            } else {
                a->wait = 0x4f; a->body.move_delay = 70; a->turn = 64;
                bc_enemy_set_vx(&a->body, a->phase == 0x4c ? -128 : 128);
            }
        }
        unsigned char x = bc_enemy_x(&a->body);
        unsigned char bright = a->phase == 0x4c ? x >= 107 && x < 111 : x >= 145 && x < 149;
        a->body.attributes = (a->body.attributes & 0xff00) | (bright ? 14 : 13);
    } else if (action == BURST_TURRET) {
        if (!--a->phase) {
            a->phase = 22;
            if (a->turn == 4) { a->turn = 0; a->phase = 60; }
            else {
                a->turn++;
                unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                if (!((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
                    unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, x, y);
                    if (a->wait ? direction >= 9 : direction > 0 && direction < 8) {
                        a->body.animation = data->round == 6 ? (a->wait ? 0xb6fe : 0xb6f7) : (a->wait ? 0xb5ba : 0xb5b3); a->body.timer = 1;
                        event->fire_requested = 1;
                        event->child_slot = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                            0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                        if (event->child_slot >= 0) {
                            bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                            (*count)++;
                        }
                    }
                }
            }
        }
    } else if (action == TURRET) {
        turret_prepare(event, actors, slot, p, data, count, maximum);
    } else if (action == HOVER_DEATH) {
        /* $8683: reverse allocation, random item selection, then its immediate
         * common task before the parent's large-explosion setup. */
        signed short child = bc_actor_allocate(actors, 1);
        if (child >= 0) {
            BcActor *b = &actors[child];
            const unsigned char *bytes = data->data.bytes;
            bc_actor_template(b, bytes + (unsigned short)(0x88f5 + data->relocation - data->data.origin),
                data->bullet_death_base);
            bc_enemy_copy_x(&b->body, &a->body);
            bc_enemy_copy_y(&b->body, &a->body);
            bc_enemy_set_vx(&b->body, bc_enemy_set_vy(&b->body, 0));
            b->phase = b->direction = 0; b->wait = 3; b->turn = 120;
            *data->random_state = bc_random_next(*data->random_state);
            b->pickup = ((*data->random_state >> 8) & 3) + 1;
            b->body.attributes = (b->body.attributes & 0xff00) |
                bytes[(unsigned short)(0x891a + data->relocation + b->pickup - data->data.origin)];
            b->body.animation = word(bytes + (unsigned short)(0x8922 + data->relocation + b->pickup * 2 - data->data.origin));
            event->child_slot = child;
            bc_actor_common_into(&event->child_event, b, p, &data->data, count);
        }
        bc_actor_explosion(a, 1, data->large_explosion_base, 0x8f1e + data->relocation);
    } else if (action == MOVING_ITEM) {
        const unsigned char *bytes = data->data.bytes;
        if (!--a->wait) {
            a->wait = bytes[(unsigned short)(0x8741 + data->relocation + (a->phase & 15) - data->data.origin)];
            a->phase++;
            a->direction = (a->direction + 1) & 15;
            unsigned short vector = word(bytes + (unsigned short)(0x8479 + data->relocation + a->speed - data->data.origin));
            const unsigned char *v = bytes + (unsigned short)(vector + a->direction * 4 - data->data.origin);
            bc_enemy_set_vx(&a->body, (signed short)word(v)); bc_enemy_set_vy(&a->body, (signed short)word(v + 2));
        }
        if (!--a->turn) {
            a->turn = 120; a->pickup = (a->pickup & 3) + 1;
            a->body.attributes = (a->body.attributes & 0xff00) |
                bytes[(unsigned short)(0x891a + data->relocation + a->pickup - data->data.origin)];
            a->body.animation = word(bytes + (unsigned short)(0x8922 + data->relocation + a->pickup * 2 - data->data.origin));
            a->body.timer = 1;
        }
    } else if (action == ITEM_OPEN) {
        const unsigned char *bytes = data->data.bytes;
        a->body.attributes = (a->body.attributes & 0xff00) |
            bytes[(unsigned short)(0x891a + data->relocation + a->pickup - data->data.origin)];
        a->body.animation = word(bytes + (unsigned short)(0x8922 + data->relocation + a->pickup * 2 - data->data.origin));
        a->body.state = 0x80; a->body.timer = 1; a->body.flags = 0x11;
    } else if (action == HOPPER) {
        if (!a->body.move_delay) {
            unsigned char landed = 0;
            if (bc_enemy_vy(&a->body) >= 0) {
                a->probe_x = 0; a->probe_y = 10;
                landed = bc_terrain_solid(&data->terrain,
                    data->camera_x + (bc_enemy_x(&a->body)), data->camera_y + (bc_enemy_y(&a->body)) + 10);
            }
            if (!landed) {
                a->probe_y = 0; a->probe_x = bc_enemy_vx(&a->body) < 0 ? 240 : 16;
                if (bc_terrain_solid(&data->terrain,
                    data->camera_x + (bc_enemy_x(&a->body)) + (bc_enemy_vx(&a->body) < 0 ? -16 : 16),
                    data->camera_y + (bc_enemy_y(&a->body)))) {
                    a->wait = (a->wait + 1) & 1; bc_enemy_set_vx(&a->body, 0);
                }
                bc_enemy_set_vy(&a->body, (unsigned short)(bc_enemy_vy(&a->body) + 32));
            } else {
                unsigned char correction = ((bc_enemy_y(&a->body)) + a->probe_y + data->camera_y) & 15;
                a->body.y -= (unsigned int)correction << 16;
                bc_enemy_set_vy(&a->body, -768); bc_enemy_set_vx(&a->body, a->wait ? 384 : -384);
                unsigned char right = (unsigned char)(p->x >> 8) >= (unsigned char)(bc_enemy_x(&a->body));
                a->body.timer = 1; a->body.animation = data->round == 5 ? (right ? 0xbbdf : 0xbbd8) : data->round == 3 ? (right ? 0xbc5a : 0xbc53) : (right ? 0xb22d : 0xb226);
                a->body.move_delay = 16;
                unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                if (!((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
                    unsigned char direction = bc_aim16(p->x >> 8, p->y >> 8, x, y);
                    unsigned char cone = (direction + 2) & 15;
                    if (cone < 13 && (right ? cone < 5 : cone >= 8)) {
                        a->body.timer = 1; a->body.animation = data->round == 5 ? (right ? 0xbbeb : 0xbbe6) : data->round == 3 ? (right ? 0xbc66 : 0xbc61) : (right ? 0xb239 : 0xb234);
                        event->fire_requested = 1;
                        event->child_slot = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                            0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                        if (event->child_slot >= 0) {
                            bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                            (*count)++;
                        }
                        a->body.move_delay = 26;
                    }
                }
            }
        }
    } else if (action == LAUNCHER) {
        if (!--a->wait) {
            if (!a->phase) {
                unsigned char right = (unsigned char)(p->x >> 8) >= (unsigned char)(bc_enemy_x(&a->body));
                a->turn = right ? 0x52 : 0x4c;
                a->body.animation = data->round == 6 ? (right ? 0xbc3f : 0xbc34) : data->round == 4 ? (right ? 0xba7d : 0xba72) : (right ? 0xb340 : 0xb335);
                a->body.timer = 1; a->phase = 1; a->wait = 25; a->body.flags = 16;
            } else {
                unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                if (!((x | y) & 0xff00) && y >= 16 && y < 224 && *count < maximum) {
                    unsigned char direction = a->turn == 0x52 ? 14 : 10;
                    event->fire_requested = 1;
                    event->child_slot = bc_actor_spawn_bullet(actors, slot, direction, &data->data,
                        0x8b66 + data->relocation, data->homing_inherited_base, 0x8479 + data->relocation);
                    if (event->child_slot >= 0) {
                        BcActor *child = &actors[event->child_slot];
                        child->sprite_base_ref = 0x3684;
                        child->body.attributes = (child->body.attributes & 0xff00) | (a->body.attributes & 255);
                        child->wait = a->phase == 2 ? 60 : 48;
                        child->body.animation = word(data->data.bytes + (unsigned short)(0x8b79 + data->relocation + direction * 2 - data->data.origin));
                        child->body.timer = 1;
                        bc_actor_common_into(&event->child_event, child, p, &data->data, count);
                        (*count)++;
                    }
                    if (a->phase == 2) a->routine = 0x9eb1;
                    else { a->phase++; a->wait = 16; }
                }
            }
        }
    } else if (action == HOVER) {
        unsigned short firing_handler = data->round == 8 ? 0xc982 : data->round == 7 ? 0xb6f8 : data->round == 6 ? 0xb03e : data->round == 5 ? 0xb3cf : data->round == 4 ? 0xb44c : data->round == 3 ? 0xaf7c : data->round == 2 ? 0xb074 : data->round == 1 ? 0xb533 : 0xac4b;
        unsigned char firing_phase = handler == firing_handler;
        if (!firing_phase && !--a->wait) {
            bc_enemy_set_vx(&a->body, 0); a->phase = 255; a->wait = 1;
            a->routine = firing_handler; firing_phase = 1;
        }
        if (firing_phase) {
            if (!--a->phase) {
                bc_enemy_set_vx(&a->body, 512); a->body.animation = data->round == 8 ? 0xca01 : data->round == 7 ? 0xb777 : data->round == 6 ? 0xb0bd : data->round == 5 ? 0xb44e : data->round == 4 ? 0xb4cb : data->round == 3 ? 0xaffb : data->round == 2 ? 0xb0f3 : data->round == 1 ? 0xb5b2 : 0xacca; a->body.timer = 1;
                a->routine = 0x9eb1;
            } else if (!--a->wait) {
                a->wait = 10;
                *data->random_state = bc_random_next(*data->random_state);
                unsigned short x = bc_enemy_x(&a->body), y = bc_enemy_y(&a->body);
                if (((*data->random_state >> 8) & 15) < 12 && !((x | y) & 0xff00)
                    && y >= 16 && y < 224 && *count < maximum) {
                    event->fire_requested = 1;
                    event->child_slot = bc_actor_spawn_bullet(actors, slot,
                        bc_aim16(p->x >> 8, p->y >> 8, x, y), &data->data,
                        0x8aa4 + data->relocation, data->bullet_base, 0x8479 + data->relocation);
                    if (event->child_slot >= 0) {
                        bc_actor_common_into(&event->child_event, &actors[event->child_slot], p, &data->data, count);
                        (*count)++;
                    }
                }
            }
        }
    } else if (action == CURVE) {
        bc_actor_curve_common_into(event, a, slot, p, data, count, maximum);
        return;
    } else if (action == EXPLOSION) {
        unsigned char kind = canonical == 0x8e95 ? 0 : canonical == 0x8eb5 ? 1 : 2;
        event->setup_sound = bc_actor_explosion(a, kind,
            kind ? data->large_explosion_base : data->small_explosion_base,
            (kind ? 0x8f1e : 0x8f15) + data->relocation);
    }
    bc_actor_common_into(&event->actor_event, a, p, &data->data, count);
    /* The drop's immediate pickup sound precedes the parent explosion sound.
     * A dying parent's common task has no player/shot contacts of its own. */
    if (action == HOVER_DEATH) event->actor_event.sound = 4;
    return;
}

BcActorStepEvent bc_actor_step(BcActor actors[BC_ACTOR_CAPACITY], unsigned char slot,
    BcWorldPlayer *p, const BcActorStepData *data, unsigned char *count,
    unsigned char maximum, signed short dx, signed short dy, unsigned char stopped)
{
    BcActorStepEvent event;
    bc_actor_step_into(&event, actors, slot, p, data, count, maximum, dx, dy, stopped);
    return event;
}

signed short bc_actor_spawn_hover(BcActor actors[BC_ACTOR_CAPACITY], unsigned char y,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    bc_enemy_set_x(&a->body, 0x110);
    bc_enemy_set_y(&a->body, (unsigned short)y);
    bc_enemy_set_vx(&a->body, -512); bc_enemy_set_vy(&a->body, 0); a->wait = 56;
    return slot;
}

signed short bc_actor_spawn_launcher(BcActor actors[BC_ACTOR_CAPACITY], unsigned char x,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    bc_enemy_set_x(&a->body, (unsigned short)x);
    bc_enemy_set_y(&a->body, 0xb8);
    bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->wait = 32; a->phase = 0;
    return slot;
}

signed short bc_actor_spawn_hopper(BcActor actors[BC_ACTOR_CAPACITY], unsigned char x,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    bc_enemy_set_x(&a->body, (unsigned short)x);
    bc_enemy_set_y(&a->body, 0xfff0);
    bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
    a->wait = x == 240 ? 0 : 1;
    if (a->wait) a->body.animation = template_address == 0xbbc5 ? 0xbbe1 : 0xb22f;
    return slot;
}

signed short bc_actor_stage_birth(BcActor actors[BC_ACTOR_CAPACITY], unsigned short handler,
    const BcEnemyData *data, unsigned short sprite_base)
{
    switch (handler) {
    case 0xabe7: return bc_actor_spawn_hover(actors, 80, data, 0xaca6, sprite_base);
    case 0xabed: return bc_actor_spawn_hover(actors, 160, data, 0xaca6, sprite_base);
    case 0xaa34: return bc_actor_spawn_curve(actors, 56, data, 0xabb1, sprite_base);
    case 0xaa3a: return bc_actor_spawn_curve(actors, 88, data, 0xabb1, sprite_base);
    case 0xaa40: return bc_actor_spawn_curve(actors, 120, data, 0xabb1, sprite_base);
    case 0xaa46: return bc_actor_spawn_curve(actors, 152, data, 0xabb1, sprite_base);
    case 0xaa4c: return bc_actor_spawn_curve(actors, 184, data, 0xabb1, sprite_base);
    case 0xacd7: return bc_actor_spawn_curve(actors, 56, data, 0xae54, sprite_base);
    case 0xacdd: return bc_actor_spawn_curve(actors, 88, data, 0xae54, sprite_base);
    case 0xace3: return bc_actor_spawn_curve(actors, 120, data, 0xae54, sprite_base);
    case 0xace9: return bc_actor_spawn_curve(actors, 152, data, 0xae54, sprite_base);
    case 0xacef: return bc_actor_spawn_curve(actors, 184, data, 0xae54, sprite_base);
    case 0xae84: return bc_actor_spawn_jumper(actors, 0, data, 0xb0a5, sprite_base);
    case 0xae8a: return bc_actor_spawn_jumper(actors, 40, data, 0xb0a5, sprite_base);
    case 0xae90: return bc_actor_spawn_jumper(actors, 80, data, 0xb0a5, sprite_base);
    case 0xae96: return bc_actor_spawn_jumper(actors, 120, data, 0xb0a5, sprite_base);
    case 0xb0d0: return bc_actor_spawn_hopper(actors, 240, data, 0xb213, sprite_base);
    case 0xb0d6: return bc_actor_spawn_hopper(actors, 32, data, 0xb213, sprite_base);
    case 0xb23e: return bc_actor_spawn_launcher(actors, 48, data, 0xb31d, sprite_base);
    case 0xb244: return bc_actor_spawn_launcher(actors, 96, data, 0xb31d, sprite_base);
    case 0xb24a: return bc_actor_spawn_launcher(actors, 144, data, 0xb31d, sprite_base);
    case 0xb250: return bc_actor_spawn_launcher(actors, 192, data, 0xb31d, sprite_base);
    case 0xb256: return bc_actor_spawn_launcher(actors, 240, data, 0xb31d, sprite_base);
    default: return -2;
    }
}

signed short bc_actor_spawn_jumper(BcActor actors[BC_ACTOR_CAPACITY], unsigned char y,
    const BcEnemyData *data, unsigned short template_address, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    bc_enemy_set_x(&a->body, 0x110);
    bc_enemy_set_y(&a->body, (unsigned short)y);
    bc_enemy_set_vx(&a->body, -256); bc_enemy_set_vy(&a->body, 0); a->wait = 0; a->turn = 0;
    return slot;
}

signed short bc_actor_spawn_item(BcActor actors[BC_ACTOR_CAPACITY], unsigned char item,
    unsigned char position, const BcEnemyData *data, unsigned short template_address,
    unsigned short positions, unsigned short sprite_base)
{
    signed short slot = bc_actor_allocate(actors, 1);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(template_address - data->origin), sprite_base);
    const unsigned char *coordinates = data->bytes + (unsigned short)(positions + position * 4 - data->origin);
    bc_enemy_set_x(&a->body, word(coordinates));
    bc_enemy_set_y(&a->body, word(coordinates + 2));
    bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0)); a->pickup = item;
    return slot;
}

signed short bc_actor_spawn_boss_effect(BcActor actors[BC_ACTOR_CAPACITY],
    unsigned short center_y, const BcEnemyData *data, signed short relocation,
    unsigned short sprite_base, unsigned short *random_state)
{
    signed short slot = bc_actor_allocate(actors, 0);
    if (slot < 0) return slot;
    BcActor *a = &actors[slot];
    bc_actor_template(a, data->bytes + (unsigned short)(0x8f02 + relocation - data->origin), sprite_base);
    *random_state = bc_random_next(*random_state);
    unsigned short x = 208 - 48 + ((*random_state >> 8) & 63) + (*random_state & 31);
    *random_state = bc_random_next(*random_state);
    unsigned short y = center_y - 32 + ((*random_state >> 8) & 63);
    bc_enemy_set_x(&a->body, x);
    bc_enemy_set_y(&a->body, y);
    bc_enemy_set_vx(&a->body, bc_enemy_set_vy(&a->body, 0));
    return slot;
}
