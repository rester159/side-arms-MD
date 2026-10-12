#pragma once

/* Shared pool allocation: inspect the live-state byte in each typed record.
 * A zero state is free. Allocation does not initialize or reserve the slot;
 * each mode's birth policy performs that work, including immediate updates.
 * Byte access is valid for every object representation; callers keep their
 * typed records and native strides. No cached occupancy can become stale. */
static inline __attribute__((always_inline)) signed short enemy_pool_free(
    const void *records, unsigned short stride, unsigned short state_offset,
    unsigned short capacity, unsigned char reverse)
{
    if (!capacity) return -1;
    const unsigned char *state = (const unsigned char *)records + state_offset;
    if (reverse) {
        unsigned short index = capacity;
        state += (capacity - 1) * stride;
        do {
            --index;
            if (!*state) return (signed short)index;
            if (!index) break; /* never form a pointer before the array */
            state -= stride;
        } while (1);
    } else {
        for (unsigned short index = 0; index < capacity; ++index) {
            if (!*state) return (signed short)index;
            if (index + 1 < capacity) state += stride;
        }
    }
    return -1;
}
