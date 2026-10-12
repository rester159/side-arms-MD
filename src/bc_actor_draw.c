#include "bc_actor_art.h"
#include "sprites.h"
#include "bc_boss_art.h"

/* Animation poses usually survive several updates. Cache only their art
 * selection; screen coordinates are refreshed from simulation on every draw.
 * Composite actors use their separate path; ordinary pose inputs form the key.
 * This also makes slot reuse and scene re-entry independent of cache resets. */
typedef struct {
    unsigned int frame_attributes;
    unsigned short base, ref, key;
    /* Keep only reusable draw inputs; screen positions are never cached. */
    unsigned short flips; /* Precomputed hardware bits; reuses the old padding. */
    unsigned short missing; /* Uses existing padding; avoids byte extension per draw. */
    signed short draw_kind; /* Zero hides the pose; 8/16 ordinary, 17/18/19 cropped poses. */
    void *bucket; /* Stable hash bucket only; never caches VRAM residency. */
} ActorArtCache;
#if defined(__m68k__)
_Static_assert(sizeof(ActorArtCache) == 20, "actor art cache RAM budget");
_Static_assert(__builtin_offsetof(ActorArtCache, missing) == 12, "word flag reuses padding");
#endif
static ActorArtCache art_cache[BC_ACTOR_CAPACITY];
static unsigned char art_boss_mode;

static inline unsigned int frame_key(const BcEnemy *b)
{
#if defined(__m68k__)
    /* The 68000 permits long reads at word alignment. GCC's alias type
     * expresses the adjacent-word read without invoking SGDK's incompatible
     * memcpy declaration (void return and a 16-bit length). */
    typedef unsigned int __attribute__((may_alias, aligned(2))) FrameWords;
    _Static_assert(sizeof(FrameWords) == 4, "frame key needs two words");
    _Static_assert(__builtin_offsetof(BcEnemy, attributes) ==
                   __builtin_offsetof(BcEnemy, sprite) + 2, "adjacent art words");
    return *(const FrameWords *)&b->sprite;
#else
    return ((unsigned int)b->sprite << 16) | b->attributes;
#endif
}

/* Integer words are aligned in the native enemy coordinate container. */
static inline __attribute__((always_inline)) void screen_coordinates(const BcEnemy *b,
    signed short *x, signed short *y)
{
    *x = (signed short)bc_enemy_x(b); *y = (signed short)bc_enemy_y(b);
}

/* Keep this loop outside bc_scene_frame: the measured 68000 build avoids
 * repeated stack spills when actor drawing has its own register allocation. */
unsigned short __attribute__((noinline)) bc_actors_draw(const BcActor actors[BC_ACTOR_CAPACITY], signed short ox, signed short oy)
{
    /* boss_active is a decaying aggression timer, not encounter lifetime.
     * Slot zero holds the composite boss throughout each encounter. */
    unsigned char boss_mode = actors[0].body.state && (actors[0].body.flags & 8) &&
        actors[0].sprite_base_ref >= 0x36b6 && actors[0].sprite_base_ref <= 0x36c6 &&
        !(actors[0].sprite_base_ref & 1);
    /* The final serpent promotes later slots after a head dies. Its shots
     * remain original while any head/body/tail segment is alive. */
    if (!boss_mode) {
        for (unsigned char i = 0; i < 8; i++) {
            unsigned short ref = actors[i].sprite_base_ref;
            if (actors[i].body.state && ref >= 0x36d0 && ref <= 0x36d4 && !(ref & 1)) {
                boss_mode = 1; break;
            }
        }
    }
    if (boss_mode != art_boss_mode) {
        for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++) {
            /* Frame zero is hidden for every family and base. Reset its
             * result too: matching empty inputs may safely hit this entry,
             * while every nonempty frame must refresh its boss context. */
            art_cache[i].frame_attributes = 0;
            art_cache[i].draw_kind = art_cache[i].missing = 0;
        }
        art_boss_mode = boss_mode;
    }
    unsigned short counts = 0;
    const signed short ox16 = ox - 8, oy16 = oy - 8;
    const signed short ox32 = ox - 16, oy32 = oy - 16;
    const BcActor *a = actors;
    ActorArtCache *c = art_cache;
    for (; a != actors + BC_ACTOR_CAPACITY; a++, c++) {
        if (!a->body.state) continue;
        counts += 0x100;
        const BcEnemy *b = &a->body;
        if (b->flags & 8) {
            if (bc_boss_draw(a, ox, oy)) continue;
            /* The ordinary mapper hides empty frames and rejects every other
             * unsupported composite. Preserve those diagnostics directly. */
            if (b->sprite && b->sprite != 255) counts++;
            continue;
        }
        unsigned int frame_attributes = frame_key(b);
        /* Favor unchanged animation words without biasing the whole refresh
         * branch: the broader hint regressed the final-round workload. */
        if (__builtin_expect(c->frame_attributes != frame_attributes, 0) ||
            c->base != b->sprite_base || c->ref != a->sprite_base_ref) {
            unsigned int pose = boss_mode ? bc_actor_boss_pose(a) : bc_actor_pose(a);
            c->draw_kind = pose & 0x80000u ? (pose & 0x40000u ? 16 : 8) : 0;
            c->flips = (pose >> 5) & 0x1800;
            c->missing = !(pose & 0x100000u);
            c->key = pose & 0x7fff;
            if (c->draw_kind == 16) {
                if (c->key == 0x250) c->draw_kind = 17;
                else if (c->key == 0x7ed6) c->draw_kind = 18;
                else if (c->key == 0x7d30) c->draw_kind = 19;
            }
            if (pose & 0x40000u) c->bucket = spr_bc_bucket(c->key, 32);
            c->frame_attributes = frame_attributes; c->base = b->sprite_base;
            c->ref = a->sprite_base_ref;
        }
        counts += c->missing;
        if (!c->draw_kind) continue;
        signed short x, y;
        screen_coordinates(b, &x, &y);
        if (c->draw_kind == 16)
            spr_bc_bits32(c->bucket, c->key, x + ox32, y + oy32, c->flips);
        else if (c->draw_kind == 8)
            spr_bc_bits16(c->key, x + ox16, y + oy16, c->flips);
        else if (c->draw_kind == 17)
            spr_bc_surfacer32(x + ox32, y + oy32, c->flips);
        else if (c->draw_kind == 18)
            spr_bc_pod32(x + ox32, y + oy32, c->flips);
        else
            spr_bc_spike32(c->bucket, x + ox32, y + oy32, c->flips);
    }
    return counts;
}

/* Gallery templates are ordinary actors. Keep its recolor work out of the
 * gameplay renderer and reuse the same converted pixels and art mapping. */
unsigned char bc_gallery_draw(const BcActor actors[BC_ACTOR_CAPACITY], signed short ox, signed short oy)
{
    unsigned char unmapped = 0;
    for (unsigned char i = 0; i < BC_ACTOR_CAPACITY; i++) {
        const BcActor *a = &actors[i];
        if (!a->body.state) continue;
        BcActorSprite s = bc_actor_sprite(a, ox, oy);
        if (!s.handled) unmapped++;
        if (!s.visible) continue;
        unsigned short first = spr_mark();
        if (s.size == 32) spr_32(s.code, s.colour, s.x, s.y, s.flips);
        else spr_16(s.code, s.colour, s.x, s.y, s.flips);
        if ((a->body.attributes & 15) == 15) spr_scene_palettes(first);
    }
    return unmapped;
}
