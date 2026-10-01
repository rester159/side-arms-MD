#!/bin/sh
# Copy the owner's local SEGA / CAPCOM intro kits into src/intro/ (gitignored: the
# kits contain data from other games and are never committed). The game builds
# and runs without them; with them, main() plays both intros at boot.
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ports=$(CDPATH= cd -- "$root/../.." && pwd)
sega="$ports/_capcom/son son/sonson_native"
capcom="$ports/_capcom/_capcom logo intro"
mkdir -p "$root/src/intro"
for f in sega_logo.c sega_logo_shinobi.c; do cp "$sega/src/$f" "$root/src/intro/"; done
for f in sega_logo.h sega_logo_shinobi.h; do cp "$sega/inc/$f" "$root/src/intro/"; done
cp "$capcom/capcom_logo.c" "$capcom/capcom_logo.h" "$capcom/capcom_splash.c" "$root/src/intro/"
# SEGA wrapper (from the Son Son port), without its front-end header; SGDK 2.12 API
sed -e '/#include "frontend.h"/d' -e 's/SND_PCM_unloadDriver()/Z80_unloadDriver()/' \
    -e 's/SND_PCM_loadDriver(TRUE);/SND_PCM_loadDriver(FALSE); intro_pcm_fix();/' \
    -e 's/#include "sega_logo.h" /void intro_pcm_fix(void);\n#include "sega_logo.h" /' \
    "$sega/src/sega_splash.c" > "$root/src/intro/sega_splash.c"
cat > "$root/src/intro/intros.c" <<'C'
/* Boot intros (local only, see tools/fetch_intros.sh). Overrides the weak hook in main.c. */
#include <genesis.h>
void sega_splash_run(void);
void capcom_splash(void);
/* SGDK's Z80_upload() is miscompiled by this GCC 16 + LTO toolchain (every byte one address
 * too high, see docs/sound_port.md), so SND_PCM_loadDriver() leaves a broken PCM driver: upload
 * it again with an exact copy, restart the Z80, and restore the null-sample parameters that
 * SND_PCM_loadDriver() writes ($PARAMS+$20). */
extern const u8 drv_pcm[0xB2F];
extern const u8 smp_null[0x100];
void intro_pcm_fix(void)
{
    SYS_disableInts();
    Z80_requestBus(TRUE);
    vu8 *dst = (vu8 *)Z80_RAM;
    const u8 *src = drv_pcm;
    u16 n = sizeof(drv_pcm);
    __asm__ volatile("1: move.b (%1)+,(%0)+\n\tsubq.w #1,%2\n\tbne.s 1b"
                     : "+a"(dst), "+a"(src), "+d"(n) : : "cc", "memory");
    vu8 *pb = (vu8 *)(Z80_DRV_PARAMS + 0x20);
    u32 addr = (u32)smp_null;
    pb[0] = addr >> 8; pb[1] = addr >> 16;
    pb[2] = sizeof(smp_null) >> 8; pb[3] = sizeof(smp_null) >> 16;
    Z80_startReset();
    Z80_releaseBus();
    waitSubTick(50);
    Z80_endReset();
    SYS_enableInts();
    while (!Z80_isDriverReady()) waitMs(1);
}

void boot_intros(void)
{
    sega_splash_run();      /* SEGA logo (Shinobi) + "SEGA" chant */
    capcom_splash();        /* CAPCOM logo + FM jingle */
}
C
echo "intros copied to src/intro/"
