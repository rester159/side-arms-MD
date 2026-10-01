# Side Arms (MAME `sidearms`, Capcom 1986) — hardware & kernel notes

Ground truth: MAME `src/mame/capcom/sidearms.cpp` + the disassembly in `reference/disasm/` (ignored, regenerated locally).

## Disassembly files
- `reference/disasm/main_0000.txt` — `sa03.bin`, fixed $0000-$7FFF.
- `reference/disasm/bankN.txt` (N=0..3) — banked window $8000-$BFFF. Bank N = maincpu region offset `0x8000+N*0x4000`
  (banks 0,1 = `a_14e.rom` halves; banks 2,3 = `a_12e.rom` halves). Bank written via `$C801` (`&7`); banks 4-7 unpopulated.
  Cite banked code as `B<n>:$xxxx`.
- Linear sweep disassembly: data regions appear as junk instructions.

## Main CPU memory map (Z80 @ 8 MHz, IRQ twice per frame: scanlines 112 and 240)
| addr | use |
|---|---|
| $C000-$C3FF / $C400-$C7FF | palette lo / hi byte (write). **Palette is static**: ROM table at region 0x14A37 (lo) / 0x14E37 (hi) = `B3:$8A37`/`B3:$8E37`. Format xBRG_444: word=(hi<<8)\|lo, B=bits 8-11, R=4-7, G=0-3. Verified equal to palette RAM in every captured frame. |
| $C800 | R: SYSTEM (b0 start1, b1 start2, b3 VBLANK, b6/b7 coins, active low). W: sound latch |
| $C801 | R: P1 (b0 R, b1 L, b2 D, b3 U, b4-b6 buttons 1-3, active low). W: ROM bank |
| $C802 | R: P2. W: sprite DMA request (buffers $F000-$FFFF) |
| $C803 / $C804 / $C805 | R: DSW0 / DSW1 / DSW2. $C804 W: control (b5 starfield on, b6 char layer on, b7 flip). $C805/$C806 W: starfield x/y step |
| $C808-9 / $C80A-B | BG scroll X / Y (12-bit, lo then hi&0x0F). Game copies from RAM **$E092 / $E094** each VBLANK IRQ ($0065) |
| $C80C | b0 BG enable, b1 sprite enable |
| $D000-$D7FF / $D800-$DFFF | text layer 64x32 code / attr (attr b0-5 color, b6-7 code bits 8-9). 2bpp chars, pen 3 transparent, colors 768+ |
| $E000-$EFFF | work RAM |
| $F000-$FFFF | sprite RAM, 128 x 32-byte records: +0 code lo, +1 attr (b0-3 color, b4 x bit8, b5-7 code bits 8-10), +2 y (0 = off), +3 x. Draw order regions 0x700-0x800, 0xE00-0x1000, 0x800-0xF00, 0x000-0x700 (later drawn = on top) |

## Video
- Screen 384x224 visible (MAME raw: htotal 512, visible x 64..447, y 16..239).
- BG: 128x128 map of 32x32 4bpp tiles from `b_03d.rom` (ROM, not RAM!), scroll 4096x4096 world. Cell = code(9 bits), color (5 bits -> palette 0-511), flipx/flipy. Pen 15 transparent (stars show through).
- Sprites: 16x16 4bpp, 2048 codes, colors 512-767, pen 15 transparent.
- Starfield: hardware generator from `b_11j.rom` (+0x3000), color 0x378 | (data>>5).
- Rendered complete world: `tools/render_world.py` -> `reports/world.png`.

## Kernel (cooperative tasks) — $0038 IRQ, $00AC scheduler
- Task table `$EF80`, 8 slots x 8 bytes: +0 state (0 free, 1 sleeping, 2 running, 4 ready, 8 fresh start), +1 sleep timer, +2/3 saved SP or entry PC.
- VBLANK half of IRQ ($0050 when $C800&8): sprite DMA, scroll copy $E092/$E094 -> $C808/$C80A, pop one sound command from ring at `($E316)` (16-entry, $FF = empty) -> $C800, `$E001`++ (frame counter), decrement timers of sleeping tasks -> ready (4).
- `$00EF` spawn task (A = slot?, BC = entry), `$010F` sleep (A = frames) saving all regs, `$012E` yield/kill-self, `$0102` free.
- Reset `$0145`: clears $E000-$FFFF, service DSW0.7 -> bank 3 `$8000` (test mode); else reads DSW -> $E200/$E208 coin tables, `$02E1`, spawns first task `$0ACA` in slot 0.

## Oracle tooling
- `tools/oracle.py NAME FRAMES [--snap N] [--dump N] [--input FILE]` runs `tools/capture.lua` under MAME headless; output `reports/oracle/NAME/events.txt`:
  - `F|frame|ctrl=..|gfx=..|bank=..|sx=<lo><hi>|sy=..|star=..|snd=<latch writes>` (every dump frame)
  - `S|<4096 bytes hex spriteram>`, `R|<4096 bytes hex $E000-$EFFF>`
  - `P|frame|pal lo|pal hi`, `V|frame|videoram|colorram` and `snap/fNNNNN.png` every snap frames
- Input file lines: `<frame> <port> "<field>" <0|1>`, ports `:SYSTEM` ("Coin 1","1 Player Start"), `:P1` ("P1 Right","P1 Left","P1 Up","P1 Down","P1 Button 1".."P1 Button 3").
- Existing traces: `reports/oracle/attract` (4000 frames, attract), `reports/oracle/play1` (6000 frames: coin@300, start@400, hold right + autofire Button 1 from 500, periodic up/down; dies, game over ~4800, back to attract).
- For custom probes write your own `tools/re_<topic>.lua` (MAME Lua: `manager.machine.devices[':maincpu'].spaces.program`, `install_write_tap`, `emu.wait_next_update()`, debugger via `-debug -debugger none` + `cpu.debug:bpset`).

## Confirmed additions (flow/player RE, see docs/re/flow_player.md)
- Sprite RAM `$F000-$FFFF` doubles as the game's object RAM: each 32-byte record = hardware sprite (+0..+3)
  plus that object's logic fields (+4..+$1F). Player 1 = `$F200-$F27F`, player 2 = `$F400-$F47F`.
- Sprite x is 9-bit (`+3 | attr bit4 << 8`); on-screen pixel = (x − 64, y − 16) for the 384×224 visible area.
- MAME also skips a sprite record whose byte +5 == `$C3` (driver `draw_sprites_region`).
- DSW0 bit7 (service) is only tested for test mode at reset (`$0158`); flipped on later it enables debug
  features (invincibility, scroll-coordinate display, all weapons, stage select) — see flow_player.md §2.6.

## Confirmed additions (levels RE, see docs/re/levels.md)
- BG visible window: for scroll (X,Y) the screen shows tilemap pixels [X+64,X+448) x [Y+16,Y+240) (MAME applies no scroll offset; verified against a play1 snapshot). Sprites also have no offset: world = scroll + raw sprite x/y.
- DSW0.7 is the test-mode switch only at reset (`$0158`). Switched on after reset it enables in-game debug (`~DSW0&mask==mask`): `$80` start section `~DSW1&$0F` via table `$15B4`, `$81` invincible to enemy hits, `$82` scroll coordinates on text layer, `$84` slow, `$88` fast, `$90` full power. Verified in MAME.
- `$C805/$C806` writes come only from the scroll engine (`$201E/$203E`): one per 4 frames while that axis scrolls; MAME counters only increment.
- maincpu region as built by `arcade_source.Source().region('maincpu')` is 0x18000 bytes (fixed + banks 0-3).
- BG collision bitmap in ROM at B2:`$A000-$BFFF` (1 bit per 16x16 world cell).
