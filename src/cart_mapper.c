/* This cartridge has a fixed, linear ROM window (at most 4 MiB; enforced by
 * finalize_rom.py). Override SGDK's mapper module, including FAR helpers, so a
 * shared SDK built with ENABLE_BANK_SWITCH cannot emit SSF2 register writes.
 * On small-ROM MiSTer cartridges those addresses alias the SRAM enable latch.
 * SRAM itself remains controlled by SGDK SRAM_enable/disable at $A130F1.
 */
#include <genesis.h>

static bool nextRegion;

void SYS_resetBanks(void) { nextRegion = FALSE; }
u16 SYS_getBank(u16 regionIndex) { return regionIndex; }
/* No bank-switch hardware is present on this cartridge. */
void SYS_setBank(u16 regionIndex, u16 bankIndex)
{
    (void)regionIndex;
    (void)bankIndex;
}
void* SYS_getFarData(void* data) { return data; }
void* SYS_getFarDataEx(void* data, bool high)
{
    (void)high;
    return data;
}
bool SYS_isCrossingBank(void* data, u32 size)
{
    return size && (((u32)data ^ ((u32)data + size - 1)) & BANK_OUT_MASK);
}
void* SYS_getFarDataSafe(void* data, u32 size)
{
    (void)size;
    return data;
}
void* SYS_getFarDataSafeEx(void* data, u32 size, bool high)
{
    (void)size;
    (void)high;
    return data;
}
bool SYS_getNextFarAccessRegion(void) { return nextRegion; }
void SYS_setNextFarAccessRegion(bool high) { nextRegion = high; }
