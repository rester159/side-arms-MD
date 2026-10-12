/* Re-includable, compile-time typed projectile-index builder.
 * Owns source order, live/eligibility checks, appends, envelope comparison,
 * row-head insertion, maximum half sizes, output advance and publication.
 * Storage and arithmetic traits retain each engine's existing native layout.
 * UNROLL28 preserves literal BC slot displacements; the other backend retains
 * typed per-owner/per-source induction. No source or record conversion.
 */
#if ESI_BOX_RECORD
#define ESI_PREPARE_EARLY ESI_PREPARE_X(source) ESI_PREPARE_Y(source)
#define ESI_PREPARE_LATE_X
#define ESI_PREPARE_LATE_Y
#define ESI_STORE_EARLY ESI_RECORD_X0 = ESI_X_MIN; ESI_RECORD_X1 = ESI_X_MAX; \
    ESI_RECORD_Y0 = ESI_Y_MIN; ESI_RECORD_Y1 = ESI_Y_MAX;
#define ESI_STORE_X
#define ESI_STORE_Y
#define ESI_STORE_REFERENCE ESI_RECORD_SOURCE = source; ESI_RECORD_OWNER = owner;
#else
#define ESI_PREPARE_EARLY
#define ESI_PREPARE_LATE_X ESI_PREPARE_X(source)
#define ESI_PREPARE_LATE_Y ESI_PREPARE_Y(source)
#define ESI_STORE_EARLY
#define ESI_STORE_X ESI_RECORD_X = ESI_X_MIN;
#define ESI_STORE_Y ESI_RECORD_Y = ESI_Y_MIN;
#define ESI_STORE_REFERENCE ESI_RECORD_SLOT = slot;
#endif
#define ESI_UPDATE_HALF \
    if (ESI_TRACK_HALF_X && ESI_HALF_X > ESI_MAX_HALF_X) ESI_MAX_HALF_X = ESI_HALF_X; \
    if (ESI_TRACK_HALF_Y && ESI_HALF_Y > ESI_MAX_HALF_Y) ESI_MAX_HALF_Y = ESI_HALF_Y;
#if ESI_HAS_ROWS
#define ESI_LINK_ROW_OR \
    if (ESI_USE_ROWS) { \
        ESI_ROW_TYPE row = ESI_ROW_KEY; \
        if (row >= ESI_ROW_COUNT) row = ESI_ROW_BELOW ? 0 : ESI_ROW_COUNT - 1; \
        ESI_RECORD_NEXT = ESI_ROW_HEAD(row); \
        ESI_ROW_HEAD(row) = ESI_CURRENT_RECORD; \
        ESI_UPDATE_HALF \
    } else
#define ESI_FINISH_ENVELOPE
#else
#define ESI_LINK_ROW_OR
#define ESI_FINISH_ENVELOPE ESI_UPDATE_HALF
#endif
#define ESI_APPEND(source_ref, slot_value) do { \
    ESI_SOURCE_TYPE *source = (source_ref); \
    ESI_SLOT_TYPE slot = (slot_value); \
    (void)slot; \
    if (ESI_SOURCE_LIVE(source) && ESI_SOURCE_ELIGIBLE(source)) { \
        ESI_PREPARE_EARLY \
        ESI_STORE_REFERENCE \
        ESI_STORE_EARLY \
        ESI_LINK_ROW_OR { \
            ESI_PREPARE_LATE_X \
            ESI_STORE_X \
            if (ESI_X_MIN < ESI_MIN_X) ESI_MIN_X = ESI_X_MIN; \
            if (ESI_X_MAX > ESI_MAX_X) ESI_MAX_X = ESI_X_MAX; \
            ESI_PREPARE_LATE_Y \
            ESI_STORE_Y \
            if (ESI_Y_MIN < ESI_MIN_Y) ESI_MIN_Y = ESI_Y_MIN; \
            if (ESI_Y_MAX > ESI_MAX_Y) ESI_MAX_Y = ESI_Y_MAX; \
            ESI_FINISH_ENVELOPE \
        } \
        ESI_ADVANCE_OUTPUT \
        n++; \
    } \
} while (0)

ESI_FUNCTION ESI_NAME ESI_ARGUMENTS
{
    ESI_PREPARE
#if ESI_HAS_ROWS
    if (ESI_USE_ROWS) {
        memset(ESI_ROW_STORAGE, 0, sizeof(ESI_ROW_STORAGE));
        if (ESI_TRACK_HALF_X) ESI_MAX_HALF_X = 0;
        if (ESI_TRACK_HALF_Y) ESI_MAX_HALF_Y = 0;
    }
#endif
    ESI_AFTER_ROW_INIT
    ESI_COUNT_TYPE n = 0;
    ESI_MIN_X = ESI_MIN_Y = ESI_MIN_INIT;
    ESI_MAX_X = ESI_MAX_Y = ESI_MAX_INIT;
#if !ESI_HAS_ROWS
    if (ESI_TRACK_HALF_X) ESI_MAX_HALF_X = 0;
    if (ESI_TRACK_HALF_Y) ESI_MAX_HALF_Y = 0;
#endif
    for (ESI_OWNER_INDEX_TYPE oi = 0; oi < ESI_OWNER_COUNT; oi++) {
        ESI_OWNER_TYPE *owner = ESI_OWNER_AT(oi);
        ESI_PREPARE_OWNER(owner, oi)
        if (!(ESI_SCAN_OWNER)) continue;
#if ESI_UNROLL28
        ESI_APPEND(ESI_SOURCE_AT(owner, 0), 0);
        ESI_APPEND(ESI_SOURCE_AT(owner, 1), 1);
        ESI_APPEND(ESI_SOURCE_AT(owner, 2), 2);
        ESI_APPEND(ESI_SOURCE_AT(owner, 3), 3);
        ESI_APPEND(ESI_SOURCE_AT(owner, 4), 4);
        ESI_APPEND(ESI_SOURCE_AT(owner, 5), 5);
        ESI_APPEND(ESI_SOURCE_AT(owner, 6), 6);
        ESI_APPEND(ESI_SOURCE_AT(owner, 7), 7);
        ESI_APPEND(ESI_SOURCE_AT(owner, 8), 8);
        ESI_APPEND(ESI_SOURCE_AT(owner, 9), 9);
        ESI_APPEND(ESI_SOURCE_AT(owner, 10), 10);
        ESI_APPEND(ESI_SOURCE_AT(owner, 11), 11);
        ESI_APPEND(ESI_SOURCE_AT(owner, 12), 12);
        ESI_APPEND(ESI_SOURCE_AT(owner, 13), 13);
        ESI_APPEND(ESI_SOURCE_AT(owner, 14), 14);
        ESI_APPEND(ESI_SOURCE_AT(owner, 15), 15);
        ESI_APPEND(ESI_SOURCE_AT(owner, 16), 16);
        ESI_APPEND(ESI_SOURCE_AT(owner, 17), 17);
        ESI_APPEND(ESI_SOURCE_AT(owner, 18), 18);
        ESI_APPEND(ESI_SOURCE_AT(owner, 19), 19);
        ESI_APPEND(ESI_SOURCE_AT(owner, 20), 20);
        ESI_APPEND(ESI_SOURCE_AT(owner, 21), 21);
        ESI_APPEND(ESI_SOURCE_AT(owner, 22), 22);
        ESI_APPEND(ESI_SOURCE_AT(owner, 23), 23);
        ESI_APPEND(ESI_SOURCE_AT(owner, 24), 24);
        ESI_APPEND(ESI_SOURCE_AT(owner, 25), 25);
        ESI_APPEND(ESI_SOURCE_AT(owner, 26), 26);
        ESI_APPEND(ESI_SOURCE_AT(owner, 27), 27);
#else
        ESI_SOURCE_TYPE *scan = ESI_SOURCE_AT(owner, 0);
        for (ESI_SLOT_TYPE slot_index = 0; slot_index < ESI_SOURCE_COUNT; slot_index++, scan++)
            ESI_APPEND(scan, slot_index);
#endif
    }
    ESI_PUBLISH_COUNT = n;
}

#undef ESI_ADVANCE_OUTPUT
#undef ESI_AFTER_ROW_INIT
#undef ESI_APPEND
#undef ESI_ARGUMENTS
#undef ESI_BOX_RECORD
#undef ESI_COUNT_TYPE
#undef ESI_CURRENT_RECORD
#undef ESI_FINISH_ENVELOPE
#undef ESI_FUNCTION
#undef ESI_HALF_X
#undef ESI_HALF_Y
#undef ESI_HAS_ROWS
#undef ESI_LINK_ROW_OR
#undef ESI_MAX_HALF_X
#undef ESI_MAX_HALF_Y
#undef ESI_MAX_INIT
#undef ESI_MAX_X
#undef ESI_MAX_Y
#undef ESI_MIN_INIT
#undef ESI_MIN_X
#undef ESI_MIN_Y
#undef ESI_NAME
#undef ESI_OWNER_AT
#undef ESI_OWNER_COUNT
#undef ESI_OWNER_INDEX_TYPE
#undef ESI_OWNER_TYPE
#undef ESI_PREPARE
#undef ESI_PREPARE_EARLY
#undef ESI_PREPARE_LATE_X
#undef ESI_PREPARE_LATE_Y
#undef ESI_PREPARE_OWNER
#undef ESI_PREPARE_X
#undef ESI_PREPARE_Y
#undef ESI_PUBLISH_COUNT
#undef ESI_RECORD_NEXT
#undef ESI_RECORD_OWNER
#undef ESI_RECORD_SLOT
#undef ESI_RECORD_SOURCE
#undef ESI_RECORD_X
#undef ESI_RECORD_X0
#undef ESI_RECORD_X1
#undef ESI_RECORD_Y
#undef ESI_RECORD_Y0
#undef ESI_RECORD_Y1
#undef ESI_ROW_BELOW
#undef ESI_ROW_COUNT
#undef ESI_ROW_HEAD
#undef ESI_ROW_KEY
#undef ESI_ROW_STORAGE
#undef ESI_ROW_TYPE
#undef ESI_SCAN_OWNER
#undef ESI_SLOT_TYPE
#undef ESI_SOURCE_AT
#undef ESI_SOURCE_COUNT
#undef ESI_SOURCE_ELIGIBLE
#undef ESI_SOURCE_LIVE
#undef ESI_SOURCE_TYPE
#undef ESI_STORE_EARLY
#undef ESI_STORE_REFERENCE
#undef ESI_STORE_X
#undef ESI_STORE_Y
#undef ESI_TRACK_HALF_X
#undef ESI_TRACK_HALF_Y
#undef ESI_UNROLL28
#undef ESI_UPDATE_HALF
#undef ESI_USE_ROWS
#undef ESI_X_MAX
#undef ESI_X_MIN
#undef ESI_Y_MAX
#undef ESI_Y_MIN
