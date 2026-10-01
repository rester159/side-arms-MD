#include <genesis.h>

/* SGDK header template: the fixed-size text fields are deliberately not NUL-terminated */
#pragma GCC diagnostic ignored "-Wunterminated-string-initialization"

/* Plain cartridge: no bank mapper, battery SRAM at $200000-$20FFFF switched by $A130F1.
 *
 * The console name is fixed to "SEGA MEGA DRIVE" on purpose. SGDK's template writes "SEGA SSF"
 * whenever the (shared) SGDK install is built with ENABLE_BANK_SWITCH=1, and Genesis Plus GX,
 * Mega EverDrive and MegaSD then emulate the extended SSF mapper, where a byte write to $A130F1
 * selects the 512 KB bank shown at $000000. SRAM_enable()/SRAM_enableRO() write 1/3 there, so
 * the vectors and all code below $80000 were replaced by ROM $080000/$180000 at the first save
 * read: boot hang whose exact symptom depended on what code happened to sit at +$180000
 * (docs/sound_port.md, "Boot crash"). tools/finalize_rom.py rejects any other console name. */
__attribute__((externally_visible))
const ROMHeader rom_header = {
    "SEGA MEGA DRIVE ",
    "(C)SGDK 2024    ",
    "SIDE ARMS MD                                    ",
    "SIDE ARMS MD                                    ",
    "GM 00000000-00",
    0x000,
    "JD              ",
    0x00000000,
    0x000FFFFF,                     /* ROM end: set to the real size by tools/finalize_rom.py */
    0xE0FF0000,
    0xE0FFFFFF,
    "RA",
    0xF820,
    0x00200000,
    0x0020FFFF,
    "            ",
    "SAVE: HIGH SCORES AND SETTINGS          ",
    "JUE             "
};
