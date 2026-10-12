#include <genesis.h>

/* Shared latch: one Start press skips the entire boot-logo sequence. */
static bool skipped;
bool intro_skip_poll(void)
{
    JOY_update();
    if ((JOY_readJoypad(JOY_1) | JOY_readJoypad(JOY_2)) & BUTTON_START) skipped = TRUE;
    return skipped;
}
void intro_skip_release(void)
{
    do { JOY_update(); VDP_waitVSync(); }
    while ((JOY_readJoypad(JOY_1) | JOY_readJoypad(JOY_2)) & BUTTON_START);
}
