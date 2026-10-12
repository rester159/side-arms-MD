/* Side Arms MD sound control. Arcade music/SFX use the Z80 command FIFO.
 * HuCard scores run natively on the 68000 and publish short YM frame packets;
 * the Z80 owns synthesis timing and all chip writes. The HUD shares the real
 * VInt refill callback, so music does not follow gameplay slowdown. */
#include <genesis.h>
#include "sound.h"
#include "hucard_fm.h"
#include "hucard_music.h"

#define DRV_SIZE   0x1400          /* DRVSIZE in sa_sound_drv.s80 (binary is padded to it) */
#define MB         0x1F00
#define MB_GO      (MB + 0x00)
#define MB_REGION  (MB + 0x01)
#define MB_BANK    (MB + 0x02)
#define MB_WR      (MB + 0x04)
#define MB_RD      (MB + 0x05)
#define MB_READY   (MB + 0x07)
#define MB_HU_MODE (MB + 0x08)
#define MB_HU_WR   (MB + 0x09)
#define MB_HU_RD   (MB + 0x0A)
#define HU_QUEUE   0x1800
#define HU_ACTIVE  0x1B06
#define MB_RING    (MB + 0x10)

extern const u8 sa_sound_drv[];    /* src/sound/sa_sound_drv.s80 (sjasm + bintos) */
extern const u8 sound_z80_data[];  /* src/gen/sound_data.s, 2 x 32 KB, aligned (tools/build_sound.py) */

static bool started;
static u8 music_source;
volatile u16 dbg_hucard_track = 0xffff;
volatile u16 dbg_hucard_starts;

/* Byte copy into Z80 RAM. Not SGDK's Z80_upload(): with the m68k-elf GCC 16.1 LTO toolchain that
 * loop is compiled to "move.b (a0)+,(0,a0,d0.l)", whose destination uses the already incremented
 * a0, so every byte lands one address too high (verified in MAME and Genesis Plus GX: SGDK's own
 * null driver is shifted the same way). Explicit asm keeps the copy exact. len must be > 0. */
static void z80_put(u16 to, const u8 *from, u16 len, bool fill)
{
    vu8 *dst = (vu8 *)(Z80_RAM + to);
    if (fill) {
        const u8 v = *from;
        __asm__ volatile("1: move.b %2,(%0)+\n\tsubq.w #1,%1\n\tbne.s 1b"
                         : "+a"(dst), "+d"(len) : "d"(v) : "cc", "memory");
    } else {
        __asm__ volatile("1: move.b (%1)+,(%0)+\n\tsubq.w #1,%2\n\tbne.s 1b"
                         : "+a"(dst), "+a"(from), "+d"(len) : : "cc", "memory");
    }
}

/* Park the Z80 on SGDK's null driver, copied exactly (SGDK's own Z80_init()/Z80_unloadDriver()
 * upload it one byte too high with this toolchain, and the shifted code runs into the 68000
 * bank window). Bank 0 so nothing it could still touch is RAM or VDP. Safe to call any time. */
extern const u8 drv_null[0x3a];
void z80_idle(void)
{
    SYS_disableInts();
    Z80_requestBus(TRUE);
    Z80_setBank(0);
    z80_put(0, drv_null, sizeof(drv_null), FALSE);
    Z80_startReset();
    Z80_releaseBus();
    waitSubTick(50);
    Z80_endReset();
    SYS_enableInts();
}

/* The score runs ahead by two sound ticks. VInt only refills this bounded
 * queue; the independent Z80 Timer A clock decides when each frame is heard. */
static HucardScore hucard;
static volatile bool hucard_active;
static u8 hucard_packet[HUCARD_FM_FRAME_BYTES];

/* Fixed-size audio packets use byte writes, as required by Z80 RAM. Copy
 * eight bytes per loop to reduce VInt time and the period of bus ownership. */
static inline void hucard_publish(u16 address)
{
    _Static_assert(HUCARD_FM_FRAME_BYTES % 8 == 0, "whole packet copy groups");
    vu8 *dst = (vu8 *)(Z80_RAM + address);
    const u8 *src = hucard_packet;
    u16 groups = HUCARD_FM_FRAME_BYTES / 8 - 1;
    __asm__ volatile("1:\n\t.rept 8\n\tmove.b (%1)+,(%0)+\n\t.endr\n\tdbra %2,1b"
        : "+a"(dst), "+a"(src), "+d"(groups) : : "cc", "memory");
}

void sound_vint(void)
{
    if (!started || !hucard_active) return;
    vu8 *z = (vu8 *)Z80_RAM;
    /* Snapshot free slots once. The consumer can only free more slots
     * while packets are prepared; this producer alone advances WR. */
    bool taken = Z80_getAndRequestBus(TRUE);
    u8 wr = z[MB_HU_WR] & 3;
    u8 free = (z[MB_HU_RD] - wr - 1) & 3;
    if (!taken) Z80_releaseBus();
    while (free--) {
        hucard_score_tick(&hucard, &hucard_score_data);
        hucard_fm_frame(&hucard, IS_PAL_SYSTEM, hucard_packet);
        taken = Z80_getAndRequestBus(TRUE);
        hucard_publish(HU_QUEUE + wr * HUCARD_FM_FRAME_BYTES);
        wr = (wr + 1) & 3;
        z[MB_HU_WR] = wr;
        if (!taken) Z80_releaseBus();
    }
}

void sound_hucard_stop(void)
{
    if (!started) return;
    SYS_disableInts();
    hucard_active = FALSE;
    const bool taken = Z80_getAndRequestBus(TRUE);
    *(vu8 *)(Z80_RAM + MB_HU_MODE) = 0;
    if (!taken) Z80_releaseBus();
    SYS_enableInts();
}

bool sound_hucard_start(u8 song)
{
    if (!started || song >= 21) return FALSE;
    sound_hucard_stop();
    /* Wait for the consumer to finish its current packet before reusing slots.
     * The score/packet producer stays disabled during this short handshake. */
    vu8 *z = (vu8 *)Z80_RAM;
    bool idle = FALSE;
    for (u16 attempt = 0; attempt < 100; ++attempt) {
        const bool taken = Z80_getAndRequestBus(TRUE);
        idle = !z[HU_ACTIVE];
        if (!taken) Z80_releaseBus();
        if (idle) break;
        waitSubTick(20);
    }
    if (!idle) return FALSE;
    SYS_disableInts();
    const bool taken = Z80_getAndRequestBus(TRUE);
    z[MB_HU_WR] = z[MB_HU_RD] = 0;
    if (!taken) Z80_releaseBus();
    hucard_score_start(&hucard, &hucard_score_data, song);
    hucard_active = TRUE;
    sound_vint();
    const bool owned = Z80_getAndRequestBus(TRUE);
    z[MB_HU_MODE] = 1;
    dbg_hucard_track = song;
    ++dbg_hucard_starts;
    if (!owned) Z80_releaseBus();
    SYS_enableInts();
    return TRUE;
}

void sound_init(void)
{
    static const u8 zero = 0;
    const u32 bank = ((u32)sound_z80_data) >> 15;
    vu8 *z = (vu8 *)Z80_RAM;
    SYS_disableInts();
    Z80_setVIntCallback(NULL);
    Z80_useBusProtection(0);
    Z80_requestBus(TRUE);                      /* Z80 halted while loading */
    YM2612_reset();
    PSG_reset();
    z80_put(0, sa_sound_drv, DRV_SIZE, FALSE);
    z80_put(DRV_SIZE, &zero, 0x2000 - DRV_SIZE, TRUE);
    for (u16 i = 0; i < 16; i++) z[MB_RING + i] = 0xFF;
    z[MB_REGION] = IS_PAL_SYSTEM ? 1 : 0;
    z[MB_BANK] = bank & 0xFF;
    z[MB_BANK + 1] = (bank >> 8) & 1;
    z[MB_GO] = 1;
    Z80_startReset();                          /* restart the Z80 at $0000 (SGDK sequence) */
    Z80_releaseBus();
    waitSubTick(50);
    Z80_endReset();
    SYS_enableInts();
    started = TRUE;
    SYS_setVIntCallback(sound_vint);
}

bool sound_try_command(u8 cmd)
{
    if (!started || cmd == 0xFF) return FALSE;
    if (music_source) {
        const s8 track = hucard_music_track(cmd);
        if (track >= 0) return sound_hucard_start(track);
    }
    vu8 *z = (vu8 *)Z80_RAM;
    SYS_disableInts();
    const bool taken = Z80_getAndRequestBus(TRUE);
    const u8 wr = z[MB_WR] & 15;
    const u8 next = (wr + 1) & 15;
    const bool accepted = next != z[MB_RD];
    if (accepted) {
        if (hucard_active && (!cmd || cmd >= 0x20)) {
            hucard_active = FALSE;
            z[MB_HU_MODE] = 0;
        }
        z[MB_RING + wr] = cmd;
        z[MB_WR] = next;
    }
    if (!taken) Z80_releaseBus();
    SYS_enableInts();
    return accepted;
}

void sound_set_music_source(u8 source)
{
    source = source ? 1 : 0;
    if (music_source != source) sound_stop_all();
    music_source = source;
}

void sound_command(u8 cmd)
{
    sound_try_command(cmd);
}

void sound_stop_all(void)
{
    sound_command(SOUND_STOP_ALL);
}
