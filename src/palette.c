#include "palette.h"
#include "gen/assets.h"
#include "bg.h"
#include "bc_background.h"
#include "cave_palette.h"

/* COLOR option. ARCADE = colours as converted from the arcade palette.
 * VIVID = each colour mapped through vivid_lut (build time: saturation x1.4,
 * brightness x1.15, greys kept neutral). Build-time shade guards keep Standard
 * colors where boosting would merge/reverse an ordered material ramp.
 * Normal stage 1 retains the original Vivid boost for background and sprites.
 * Vivid remains an optional deviation from the arcade colors, with no extra runtime
 * work; it cannot restore shades lost in the earlier asset conversion. */

u8 color_mode = COLOR_VIVID;
static u16 source[64];              /* palettes as loaded (before the mode mapping) */
static u16 shown[64];
static const u16 *classic_background;
static u8 current_fade = 7;
static u32 background_revision = 1;

/* Genesis colour word 0000BBB0GGG0RRR0 -> vivid_lut index BBBGGGRRR */
static inline u16 lut_index(u16 c) { return ((c >> 1) & 7) | (((c >> 5) & 7) << 3) | (((c >> 9) & 7) << 6); }

static void push(u16 index, u16 count)
{
    if (index < 32 && count) ++background_revision;
    for (u16 i = index; i < index + count; i++)
        shown[i] = color_mode != COLOR_VIVID ? source[i] :
            classic_background && i < 32 ? classic_background[i] :
            classic_background == zone0_vivid_pal && i >= 32 ? sprite0_vivid_pal[i - 32] :
            vivid_lut[lut_index(source[i])];
    PAL_setColors(index, shown + index, count, DMA_QUEUE);
}

void pal_load(u16 index, const u16 *cols, u16 count)
{
    current_fade = 7;
    if (index == 0 && count >= 32) {
        bool was_classic = classic_background == zone0_vivid_pal;
        classic_background = cols == zone0_pal ? zone0_vivid_pal :
                             cols == bc_bg_palette ? bc_bg_vivid_palette : NULL;
        if (was_classic != (classic_background == zone0_vivid_pal)) push(32, 32);
    }
    memcpy(source + index, cols, count * 2);
    push(index, count);
}

void pal_set_mode(u8 mode)
{
    current_fade = 7;
    color_mode = mode;
    push(0, 64);
}

void pal_fade_level(u8 level)
{
    /* $42A9 component ramp: retain the original quantized fade curve on
     * our own 3-bit Genesis channels, after the selected COLOR mapping. */
    static const u8 ramp[8][8] = {
        {0,0,0,0,0,0,0,0}, {0,0,0,0,1,1,1,1},
        {0,0,0,1,1,1,2,2}, {0,0,1,1,2,2,3,3},
        {0,0,1,1,2,3,3,4}, {0,0,1,2,3,3,4,5},
        {0,0,1,2,3,4,5,6}, {0,1,2,3,4,5,6,7}
    };
    static u16 faded[64];
    if (level > 7) level = 7;
    current_fade = level;
    for (u16 i = 0; i < 64; i++) {
        u16 c = shown[i];
        u16 r = ramp[level][(c >> 1) & 7];
        u16 g = ramp[level][(c >> 5) & 7];
        u16 b = ramp[level][(c >> 9) & 7];
        faded[i] = (r << 1) | (g << 5) | (b << 9);
    }
    PAL_setColors(0, faded, 64, DMA_QUEUE);
}

/* Cavern palette split: restore the top palette each displayed frame, then
 * update ten boundary-unused slots in alternate HBlanks. Prepared state stays
 * separate from the displayed frame until its graphics DMA has completed. */
typedef struct { u32 command; u16 value; } CaveEvent;
_Static_assert(sizeof(CaveEvent)==6, "packed native event");
typedef struct { u16 top[32], upper[10]; CaveEvent events[10]; u32 revision; u8 mode, fade; s16 start; bool raster, enabled; } CaveFrame;
volatile bool cave_dma_busy;
volatile const CaveEvent *cave_event;
volatile const CaveEvent *cave_end;
volatile u16 cave_first, cave_last;
static CaveFrame cave_frames[2];
static volatile u16 cave_front;
static const CaveFrame * volatile cave_current = &cave_frames[0];
static volatile bool cave_active;
static volatile u16 cave_pending;
static volatile bool cave_ready;
static bool cave_restore_deferred;
volatile u16 cave_dbg_writes, cave_dbg_missed;
static u16 cave_expected;
#include "gen/cave_palette_data.h"
static u16 cave_color(u16 c)
{
    static const u8 ramp[8][8] = {
        {0,0,0,0,0,0,0,0},{0,0,0,0,1,1,1,1},
        {0,0,0,1,1,1,2,2},{0,0,1,1,2,2,3,3},
        {0,0,1,1,2,3,3,4},{0,0,1,2,3,3,4,5},
        {0,0,1,2,3,4,5,6},{0,1,2,3,4,5,6,7}
    };
    if (color_mode == COLOR_VIVID) c = vivid_lut[lut_index(c)];
    return (ramp[current_fade][(c>>1)&7]<<1) |
           (ramp[current_fade][(c>>5)&7]<<5) |
           (ramp[current_fade][(c>>9)&7]<<9);
}
void cave_prepare(void)
{
    bool enabled=bg_is_enabled() && bg_zone_index()==10;
    if (!enabled && !cave_current->enabled && !cave_ready) return;
    u16 back = cave_front ^ 1;
    CaveFrame *f = &cave_frames[back];
    f->raster = FALSE;
    f->enabled = FALSE;
    if (enabled) {
        f->enabled = TRUE;
        s16 x,y; bg_view(&x,&y);
        f->start = x >= 1536 ? 2036-y : 32700;
        if (!(f->start & 1)) ++f->start; /* H-counter=1: odd scanlines. */
        /* Each buffer owns its cached colors, including DMA source storage.
         * Rebuild only when source colors, display mode or fade changes. */
        if (f->revision != background_revision || f->mode != color_mode ||
            f->fade != current_fade) {
            for (u16 i=0;i<32;i++) f->top[i]=cave_color(source[i]);
            for (u16 i=0;i<10;i++) {
                u16 slot=cave_slots[i];
                f->upper[i]=f->top[slot];
                f->events[i].command=0xC0000000UL | ((u32)slot*2<<16);
                f->events[i].value=cave_color(cave_lower[slot]);
            }
            f->revision=background_revision;
            f->mode=color_mode;
            f->fade=current_fade;
        }
        for (u16 i=0;i<10;i++)
            f->top[cave_slots[i]]=f->start+2*i<1 ? f->events[i].value : f->upper[i];
        f->raster=f->start<222 && f->start+24>=1;

    }
    cave_pending=back; cave_ready=TRUE;
}
static void cave_reset_events(void)
{
    cave_current=&cave_frames[cave_front];
    cave_active=cave_current->raster;
    if (!cave_current->enabled) return;
    s16 start=cave_current->start;
    cave_expected = start < 1 ? (u16)((2-start)/2) : 0;
    if (cave_expected>10) cave_expected=10;
    cave_event=&cave_current->events[cave_expected];
    cave_end=&cave_current->events[10];
    cave_first=start+2*cave_expected;
    cave_last=start+24>221 ? 221 : start+24;
}
/* One native call site also permits instruction-level restore auditing. */
static __attribute__((noinline)) void cave_restore(void)
{
    PAL_setColors(0,cave_current->top,32,CPU);
    cave_restore_deferred=FALSE;
}
void cave_vint(void)
{
    cave_reset_events();
    if (cave_active) {
        if (cave_dma_busy) cave_restore_deferred=TRUE;
        else cave_restore();
    }
}
bool cave_raster_active(void) { return cave_active; }

/* Called with interrupts masked after the queued picture has reached VRAM. */
bool cave_commit(void)
{
    if (!cave_ready) return FALSE;
    bool was_active=cave_active;
    const CaveFrame *old=cave_current;
    const CaveFrame *next=&cave_frames[cave_pending];
    bool restore=cave_restore_deferred;
    if (next->enabled) {
        /* A queued palette load/fade supplies the new upper colors. Without
         * one, VBlank already restored the currently displayed frame's top. */
        bool loaded=!old->enabled || old->revision!=next->revision ||
            old->mode!=next->mode || old->fade!=next->fade;
        for (u16 i=0;i<10;i++) {
            u16 slot=cave_slots[i];
            if (next->top[slot]!=(loaded ? next->upper[i] : old->top[slot]))
                restore=TRUE;
        }
    }
    cave_front=cave_pending;
    cave_ready=FALSE;
    cave_reset_events();
    if (next->enabled && restore) cave_restore();
    else cave_restore_deferred=FALSE;
    return was_active || cave_active;
}

bool cave_has_pending(void) { return cave_ready; }
