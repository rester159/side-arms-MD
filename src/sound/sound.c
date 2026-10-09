/* Side Arms MD - 68000 side of the sound driver (docs/sound_port.md).
 * The Z80 program (sa_sound_drv.s80) plays the compiled music / SFX data; this file only loads it
 * and feeds its command FIFO. Mailbox layout must match MBOX in sa_sound_drv.s80. The data is two
 * 32 KB banks starting at sound_z80_data (music, SFX); the driver gets the first bank number. */
#include <genesis.h>
#include "sound.h"

#define DRV_SIZE   0x1400          /* DRVSIZE in sa_sound_drv.s80 (binary is padded to it) */
#define MB         0x1F00
#define MB_GO      (MB + 0x00)
#define MB_REGION  (MB + 0x01)
#define MB_BANK    (MB + 0x02)
#define MB_WR      (MB + 0x04)
#define MB_RD      (MB + 0x05)
#define MB_READY   (MB + 0x07)
#define MB_RING    (MB + 0x10)

extern const u8 sa_sound_drv[];    /* src/sound/sa_sound_drv.s80 (sjasm + bintos) */
extern const u8 sound_z80_data[];  /* src/gen/sound_data.s, 2 x 32 KB, aligned (tools/build_sound.py) */

static bool started;

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
}

void sound_command(u8 cmd)
{
    if (!started || cmd == 0xFF) return;
    vu8 *z = (vu8 *)Z80_RAM;
    SYS_disableInts();
    const bool taken = Z80_getAndRequestBus(TRUE);
    const u8 wr = z[MB_WR] & 15;
    const u8 next = (wr + 1) & 15;
    if (next != z[MB_RD]) {
        z[MB_RING + wr] = cmd;
        z[MB_WR] = next;
    }
    if (!taken) Z80_releaseBus();
    SYS_enableInts();
}

void sound_stop_all(void)
{
    sound_command(SOUND_STOP_ALL);
}
