/* Intentionally no include guard: compile-time typed query implementation.
 * Each inclusion supplies storage, geometry, order and reaction policies.
 * This owns the contact pipeline, not merely a traversal around a VISIT body.
 *
 * ORDER 0: contiguous cached records; ORDER 1: ascending rows, chain order;
 * ORDER 2: compact/fallback ordinal slots. Native induction remains typed and
 * direct: no generic cursor, pointer difference, record conversion or vtable.
 *
 * Geometry policies are pure expressions. Binding/caching policies do not
 * change live state. Reactions run only at the explicit ordered stages below.
 * Consumption precedes protection and damage; source liveness is freshly
 * checked for every candidate, even if its geometry was cached earlier.
 */
static inline __attribute__((always_inline)) ESQ_RESULT ESQ_NAME ESQ_ARGUMENTS
{
    ESQ_RESULT result = ESQ_EMPTY;
    if (!(ESQ_TARGET_ELIGIBLE)) return result;
    ESQ_PREPARE
    if (!(ESQ_HAS_CANDIDATES) || !(ESQ_TARGET_BROAD)) return result;
#if ESQ_ORDER == 0
    ESQ_CANDIDATE candidate = ESQ_FIRST;
    for (ESQ_COUNT_TYPE n = 0; n < (ESQ_COUNT); n++, candidate++) {
#elif ESQ_ORDER == 1
    for (ESQ_ROW_TYPE row = ESQ_FIRST_ROW; row <= (ESQ_LAST_ROW); row++)
        for (ESQ_CANDIDATE candidate = ESQ_ROW_HEAD(row); candidate; candidate = ESQ_NEXT(candidate)) {
#elif ESQ_ORDER == 2
    for (ESQ_COUNT_TYPE candidate = 0; candidate < (ESQ_COUNT); candidate++) {
#else
#error Unsupported shot query traversal policy
#endif
        if (!(ESQ_CANDIDATE_BROAD(candidate))) continue;
        ESQ_SLOT_TYPE slot = ESQ_SLOT(candidate);
        ESQ_SOURCE_TYPE *source = ESQ_SOURCE(slot);
        if (!(ESQ_SOURCE_LIVE(source))) continue;
        if (!(ESQ_SOURCE_ELIGIBLE(source))) continue;
        if (!(ESQ_EXACT(candidate, source))) continue;
        ESQ_OWNER_TYPE owner = ESQ_OWNER(slot);
        (void)owner;
        ESQ_CONTACT(result);
        if (ESQ_CONSUMES(source)) ESQ_CONSUME(owner, source);
        if (ESQ_PROTECTED) continue;
        ESQ_HP_TYPE old_hp = ESQ_HP;
        ESQ_DAMAGE_TYPE damage = ESQ_DAMAGE(source);
        ESQ_HP = (ESQ_HP_TYPE)(old_hp - damage);
        unsigned char depleted = ESQ_DEPLETED(old_hp, damage, ESQ_HP);
        ESQ_RECORD_DAMAGE(result, slot, depleted);
        if (depleted) ESQ_DEATH(owner);
        if (ESQ_STOP_ON_DAMAGE || depleted) return result;
    }
    return result;
}

#undef ESQ_RESULT
#undef ESQ_NAME
#undef ESQ_ARGUMENTS
#undef ESQ_EMPTY
#undef ESQ_TARGET_ELIGIBLE
#undef ESQ_PREPARE
#undef ESQ_HAS_CANDIDATES
#undef ESQ_TARGET_BROAD
#undef ESQ_ORDER
#undef ESQ_CANDIDATE
#undef ESQ_FIRST
#undef ESQ_COUNT_TYPE
#undef ESQ_COUNT
#undef ESQ_ROW_TYPE
#undef ESQ_FIRST_ROW
#undef ESQ_LAST_ROW
#undef ESQ_ROW_HEAD
#undef ESQ_NEXT
#undef ESQ_CANDIDATE_BROAD
#undef ESQ_SLOT_TYPE
#undef ESQ_SLOT
#undef ESQ_SOURCE_TYPE
#undef ESQ_SOURCE
#undef ESQ_SOURCE_LIVE
#undef ESQ_SOURCE_ELIGIBLE
#undef ESQ_EXACT
#undef ESQ_OWNER_TYPE
#undef ESQ_OWNER
#undef ESQ_CONTACT
#undef ESQ_CONSUMES
#undef ESQ_CONSUME
#undef ESQ_PROTECTED
#undef ESQ_HP_TYPE
#undef ESQ_HP
#undef ESQ_DAMAGE_TYPE
#undef ESQ_DAMAGE
#undef ESQ_DEPLETED
#undef ESQ_RECORD_DAMAGE
#undef ESQ_DEATH
#undef ESQ_STOP_ON_DAMAGE
