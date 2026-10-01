# Side Arms — stages, camera/scrolling, progression, BG collision

Scope: how the camera (BG scroll `$E092` X / `$E094` Y) moves, the stage script, stage order and
bosses, starfield, BG collision and debug aids for capturing traces.
Data extractor: `tools/extract_levels.py` writes `res/generated/levels.json` (script decoded and
simulated, per-section legs/world rectangles/bosses, command library, collision bitmap).
Probe: `tools/re_levels.lua` + `tools/re_levels_run.py STAGE FRAMES` write traces to
`reports/oracle/stageNN/`. Contact sheets: `reports/levels/stageNN_sheet.png` (one frame every 180).
Overlay of all camera legs on the world: `reports/levels/world_paths.png`.

Coordinates: scroll values are tilemap pixels. MAME applies no offset to the BG scroll
(`set_scrollx(0, scrollx)`), and the visible area is raw x 64..447, y 16..239. So for scroll (X,Y)
the screen shows `reports/world.png` pixels **[X+64, X+448) x [Y+16, Y+240)**. I checked this
against `play1/snap/f01200.png` and it matched on 96% of pixels. Sprite raw coordinates have no
offset either, so a sprite's world position is (X+sx, Y+sy).

---

## 1. Scroll engine (auto-scroll; the player cannot push it)

The scroll engine is the main game loop `$1D8A -> $1FB7 -> $1FE5 -> $2133 -> B2:$8000 ...`. One
main-loop iteration is normally one frame (it syncs on `$0200`/`$E004`).

| RAM | meaning |
|---|---|
| `$E092/$E094` | scroll X / Y (12-bit, masked `&$0FFF` at `$2010`/`$2030`) |
| `$E080` | mode: `$80` scrolling, `$40` halted (boss), `$20` timed pause (`$E084` count, `$2122`) |
| `$E088/$E089` | live Y / X direction: 0 = stop, 1 = +1, anything else = -1 (`$2001-$2034`) |
| `$E08A/$E08B` | latched Y / X direction. Copied to `$E088/$E089` each loop at `$1FD3` while mode=`$80`. When mode≠`$80` the live directions are forced to 0 (`$1FC9`) |
| `$E003` | loop counter. Scrolling runs only when bit0 is set (`$1FE5`) |
| `$E090` | script pointer (bank 1) |

- **Speed:** 1 px every 2 main-loop iterations on each moving axis, i.e. 0.5 px/frame. Diagonal
  moves are possible (both axes at once, see section 2 leg 3). Observed in `play1`: X +$19 every
  50 frames.
  - Under CPU load the loop overruns and the scroll slows. Two runs of section 2 differed by
    127 frames over 3,200 frames (~4%).
- **The only writers of `$E092/$E094` during play** are:
  - the engine (`$2014`, `$2034`)
  - the teleport routines B0:`$8194-$82CB`
  - the BG-wheel boss (`$706E/$7077` animation, `$7530/$7539` death)

  The player code only reads them. The player code at B2:`$8451-$8492` reads `$E088/$E089` to
  push the player back when they are stuck in terrain. The other writers (`$0275`, `$04E1`,
  `$0C08`, `$0D71`, `$1350-$1586`, B3:`$8505`) are title, intro, attract and test-mode code.
- **Script interpreter** `$2044-$211F`. Bank 1 is mapped (`$2044`: bank |= 1). The engine does the
  following:
  - **Choosing the coordinate:** it compares the *low byte* of the moving coordinate (`$E092` if
    `$E089`≠0, else `$E094` if `$E088`≠0, else no compare) with `trig` = byte +1 of the record.
  - **Firing:** a matching record runs, and the engine immediately re-checks the next record in
    the same tick (`jp $2044`). A record that teleports therefore lets the following records match
    against the new position in that same tick.
  - **Record format:** 4 bytes `{cmd, trig, lo, hi}`, or 2 bytes `{FF, FF}`:

| cmd | action |
|---|---|
| `$FE` | `call lo|hi` with bank 0 mapped. It goes through the RAM stub `$E0F8: CD nn nn C9` (`$20C6`) |
| `$FB/$FC/$FD` | spawn a task in slot 3/4/5 at `lo|hi` (`$20DE-$2105`) |
| `$FF` | page marker `{FF,FF}`. It fires at low byte `$FF`, advances 2 and stops for the tick (`$2108`). This splits the script into 256-px pages |
| other | object spawn (`$2080`). Copies the 32-byte template `lo|hi` into a free `$FF00` slot. When X-scrolling, y = cmd. When Y-scrolling, y = `$F0` and x = (cmd&$FE)<<1 with bit7 → x bit8 (`$2086-$20C0`). Details belong to objects.md |

**Command library** (bank 0, all called through `$FE`; full list in `levels.json` `library`):

| target | effect |
|---|---|
| B0:`$809C` / `$80A7` / `$80AD` | Y dir latch +1 / 0 / -1 (`$809C` also sets `$E040=$56`) |
| B0:`$80B3` / `$80BE` / `$80C4` | X dir latch +1 / 0 / -1 (`$80B3` also sets `$E040=$48`) |
| B0:`$8057` | **halt**: `$E080=$40`, saves directions to `$E08A/B` (always right after a boss spawn) |
| B0:`$8051` | resume (`$E080=$80`). Not used by the script; called by the boss-death tasks (`$3976`, `$3A66`) and by timed-pause expiry (`$212D`) |
| B0:`$8069-$8082` | timed pause of 30/150/300/600/900/1800 ticks. **Unused** by the script |
| B0:`$8194-$82CB` | 26 teleports `ld hl,Y; ld ($E094),hl; ld hl,X; ld ($E092),hl` |
| B0:`$80CA-$8109` | stage music: sound `$21..$29`, `$36`. Each also loads `$E050` from a table indexed by DSW0&7 (UNCONFIRMED meaning) |
| B0:`$8000-$8030` | rank: `$E017 = base + table $8049[~DSW0&7]` (min 0) |
| B0:`$82CC-$830E` | `$E048` = enemy parameter (objects.md) |
| others (`$A4DA`, `$AD32`, `$AAB3`, `$5523`, ...) | enemy-wave spawners → objects.md |

---

## 2. Stage structure, order and bosses

### Sections and the debug start table

The script starts at B1:`$815C` and its last real record is B1:`$A402`. Everything after that is
`FF` padding.

The table at `$15B4` gives 10 entry points: `$815C, $84D6, $8906, $8C0A, $93FC, $9750, $9A16,
$9D22, $A13C, $A3E2`. Indices 0, 1 and 11-15 all map to `$815C`. The game's debug start reads it
(section 5 below).

Each entry begins with a copy of the teleport that closes the previous section. In normal play
both copies fire in the same tick, so it is harmless. I call these **sections 1-10**. Mapping them
to the player-facing stage numbers is **UNCONFIRMED**:
- Music changes inside section 5 (to `$26`), and that music carries through section 6.
- Section 7 opens directly with a boss.

All sections play in order with no branching. Section boundaries are teleports or BG-wheel-boss
deaths.

### Per-section table

How to read the table:
- **Start scroll** and **halt/boss positions** are in hex.
- **Path legs:** R/L/U/D = direction, `→` = teleport.
- **World rects** are pixels in `world.png`, unwrapped.
- **Frames** is the nominal length at 0.5 px/frame from the section's first event to the next
  section's first event. It excludes the time spent in boss fights.

| # | script (B1) | start X,Y | path legs | world rect(s) [x0,y0,x1,y1) | frames | music | boss → halt at |
|---|---|---|---|---|---|---|---|
| 1 | `815C-84D6` | 180,000 | R 180→DFF,000 | 448,16,4031,240 | 6400 | `$21` | sprite boss `$69D0` (snd `$32`) at X=DF0; halt DFE,000 |
| 2 | `84D6-8906` | 000,100 | D →200; R →500,200; **RD** →600,300; R →E3F,300; → 180,100 R →2FD | 64,272,448,752 / 65,528,1728,752 / 1345,529,1984,1008 / 1601,784,4095,1008 / 448,272,1213,496 | 8574 | `$22` | **BG wheel #1** `$7192` (E0D0=`$61`) at 1F8,100; halt 2FE,100; death → 000,300 |
| 3 | `8906-8C0A` | 000,300 | D 300→EFF; → 180,300 D →4FF | 64,784,448,4079 / 448,784,832,1519 | 7168 | `$23` | sprite boss `$6C12` (snd `$33`) at 180,4FC; halt 180,4FE |
| 4 | `8C0A-93FC` | 300,400 | R →DFF,400; → 300,600 R →DFF; → 300,500 R →AFF; → 980,900 R →AFD | 832,1040,4031,1264 / 832,1552,4031,1776 / 832,1296,3263,1520 / 2496,2320,3261,2544 | 16126 | `$24` | **BG wheel #2** `$719C` (`$62`) at 9F8,900; halt AFE,900; death → C80,500 |
| 5 | `93FC-9750` | C80,500 | R →DFF; → 180,700 R →5C0; D →800; R →E00,800; **U** →700; → 740,700 R →8C0 | 3264,1296,4031,1520 / 448,1808,1920,2032 / 1536,1809,1920,2288 / 1537,2064,4032,2288 / 3648,1810,4032,2287 / 1920,1808,2688,2032 | 8960 | `$25`, then `$26` after the boss | sprite boss `$6C12` at 741,700; halt 742,700 |
| 6 | `9750-9A16` | 180,800 | D →EFF; → 300,800 D →DFF | 448,2064,832,4079 / 832,2064,1216,3823 | 6658 | (keeps `$26`) | none |
| 7 | `9A16-9D22` | 300,E00 | D →F00; R →DFF,F00; → 480,E00 R →7FF | 832,3600,1216,4080 / 833,3856,4031,4080 / 1216,3600,2495,3824 | 7936 | `$27` after the first boss | sprite `$6DB4` (snd `$34`) at 300,E40 (halt 300,E4E); sprite `$6DB4` at 7F0,E00 (halt 7FE,E00) |
| 8 | `9D22-A13C` | 480,D00 | **U** →C00; R →C7F,C00; → 600,D00 R →C7F | 1216,3088,1600,3568 / 1217,3088,3647,3312 / 1600,3344,3647,3568 | 7936 | `$28` (again after the mid-boss) | sprite `$6DB4` at 640,C00 (halt 642); sprite `$6DB4` at C7C,D00 (halt C7E) |
| 9 | `A13C-A3E2` | C80,D00 | R →DFF; → 480,B00 R →C7F; → 980,A00 R →AFD | 3264,3344,4031,3568 / 1216,2832,3647,3056 / 2496,2576,3261,2800 | 5630 | `$29` (again after the mid-boss) | sprite `$6DB4` at B40,B00 (halt B42); **BG wheel #3** `$71A6` (`$63`) at 9F8,A00 (halt AFE,A00); death → E00,B00 |
| 10 | `A3E2-A406` | E00,B00 | D →BFD | 3648,2832,4032,3309 | 508 | `$36` | **final boss** `$5FC3` at E00,BF0; halt E00,BFE |

Notes on the path:
- Section 2's leg at X≥`$E00` and the section 1/5 legs ending at X=`$E00`/`$DFF` show
  columns past 4095. The BG tilemap wraps, so the right edge shows world columns 0-63.
- The only diagonal leg is in section 2. The only upward legs are in sections 5 and 8.

### Boss kinds

- **Sprite bosses** `$69D0` / `$6C12` / `$6DB4`. Each plays sound `$13` then `$32`/`$33`/`$34`,
  and copies a 32-byte template (`$69F7`/`$6C39`/`$6DDB`) into `$FB00`. The main loop runs it
  (`$21E7` → `$2B0B`).
  - `$6DB4` is used for all 5 bosses in sections 7-9 with the same template. Whether they look
    different is UNCONFIRMED; the sheets show different bosses, so something else selects the
    variant.
  - On death, the explosion tasks (`$3963-$3979`, `$3A53-$3A69`) call `$8051` and the scroll
    resumes.
- **BG wheel bosses** `$7192` / `$719C` / `$71A6`. Each spawns task `$3B3A`/`$3B42`/`$3B4A` (slot 5)
  and plays sound `$35`. Once the halt lands, the task writes `$E0D0 = $61/$62/$63` (`$3B52-$3B67`).
  - The boss is **drawn in the BG layer**. It animates by cycling `$E092/$E094` through 3 copies
    of the wheel in the world map (`$7048-$7077`, tables `$70D2`/`$70E2`/`$70F2`):
    - `$61`: (X,Y) 300,100 / 600,100 / 480,100
    - `$62`: B00,900 / E00,900 / C80,900
    - `$63`: B00,A00 / E00,A00 / C80,A00

    The cycle period depends on the phase `$FA10` (`$7014`).
  - On death, `$7511-$753F` sets the scroll to the 4th table entry (the next section's start) and
    clears `$E0D0`.
  - Observed: in the section 2 trace, X alternates `$300`/`$480` at Y=`$100` during the halt.
- **Final boss** `$5FC3`: an 8-segment chain in `$F600-$F9FF` (`$5FC3-$602D`). Its death spawns
  task `$3B8A`, which:
  1. plays sound `$2C`
  2. prints "CONGRATURATIONS" (text `$3BC9`)
  3. prints "SUPER STAFF" (text `$3BF9`)
  4. spawns `$0B84` in slot 0. `$0B84` kills all tasks, clears `$E010/$E011` and restarts the
     warning → title → attract cycle.

  **So the game does not loop to stage 1. It ends.** (Static reading; UNCONFIRMED live, because no
  probe killed the final boss.)

### Stage clear sequence

The pattern is: boss-spawn record, then the `$8057` halt a few pixels later. The scroll stops and
the live directions become 0. When the boss dies, `$8051` resumes the scroll in the saved
direction (wheel bosses teleport first). Scrolling continues until the next teleport record,
which starts the next section with its music, direction and rank records.

There is no separate "stage clear" screen in the scroll code. Bonus or score screens, if any,
belong to flow_player.md (UNCONFIRMED).

### World areas that are not stage paths

These are used by intro and attract code:
- Title background: X=`$180`, Y=0 (`$0272`, `$0C05`).
- Intro planet scenes cycled by `$13E8-$1538`, around X `$B00-$E00`, Y `$E00` (Earth), plus
  `$9C0-$E40`/`$100-$200` and `$480-$600`/`$900-$A00`.
- Attract demo scripts start at B1:`$8000` / `$8074` with recorded inputs at `$9600`/`$9A00`
  (`$0D99-$0DC4`). Observed demo camera: (B00,700), scrolling right.

### Validation (simulation vs MAME)

Each section was run with the debug start (section 5). I measured frames from the section's
start teleport to each halt and compared them with the simulator in `extract_levels.py`:

| section | event | sim | trace |
|---|---|---|---|
| 1 | halt | 6396 | 6395 |
| 2 | RD turn | 3072 | 3072 (first run) / 3199 (second run, slowdown) |
| 3 | halt | 7164 | 7164 |
| 4 | halt | 16124 | 16124 |
| 6→7 | boss halt | 6814 | 6811 |
| 7 | halt 1 / halt 2 | 156 / 7776 | 156 / 7775 |
| 8 | halt 1 / halt 2 | 1412 / 6520 | 1412 / 6519 |
| 9 | halt 1 / halt 2 | 4228 / 1400 | 4228 / 1399 |
| 10 | halt | 508 | 508 |

The section-5 mid-boss came 152 frames late in the trace. That was slowdown: the positions
matched.

---

## 3. Starfield

- `$C804` bit5 (stars on) is set by `$12D4`, `$04CE` and `$0BF4`, and is on throughout play
  (`ctrl=6c`).
- The scroll engine writes `$C806` (Y) or `$C805` (X) once every 4 main-loop iterations
  (`$E003` bit1, `$2017-$201E` and `$2037-$203E`), and only while that axis is moving.
- Per MAME, each write increments the star counters `hcount_191` / `vcount_191` by 1. Those
  counters only count up.
- Result: the stars move at **half the BG speed (0.25 px/frame)** in the scroll direction. They
  stop during halts. They move the **same way even when the BG scrolls up or left**: the write
  does not depend on the sign.
- Observed:
  - Section 1: 1599 X-steps over 3198 px.
  - Section 8: the upward leg still advanced the Y count by 128 over 256 px.

---

## 4. BG collision

**It exists.** It is a 1-bit-per-16x16-cell map in **B2:`$A000-$BFFF`**. The BG map ROM `b_03d`
is not CPU-visible, so this is a separate map.

**Layout:**
- `$200` bytes per 256-px band (`Y>>8`).
- 2 bytes per 16-px column `c = X>>4`: byte 0 holds rows 0-7 of the band, byte 1 holds rows 8-15.
- The bit for a row is `7 - ((Y&$7F)>>4)`.
- Cell (c, r) covers world pixels [16c, 16c+16) x [16r, 16r+16). I checked the alignment against
  `world.png`: cells set in the map average 84% non-black pixels, versus 31% elsewhere, and
  shifting the map by one cell lowers the match.
- Exported in `levels.json` `collision.rows_hex`: 256 rows, 64 hex digits each, MSB = left.

**Test routines:**

| routine | used by | test point (world) | on solid |
|---|---|---|---|
| B2:`$84B5` | player (`$F200`/`$F400`) | (X+sx+16, Y+sy+16) | return+3 skip (`$0384`) |
| `$07C0` | `$F000` objects without flag (ix+9)&4 (from `$24E1`) | (X+sx+8+16, Y+sy+8) | (UNCONFIRMED which object classes) |
| `$082F` | bank-0 enemy code (`B0:$8417`, `$8559`, ...) | (X+sx+16, Y+sy+16) | |
| B2:`$949C` | objects in bank 2 (`B2:$9461`) | (X+sx+8+16, Y+sy+8) | sets (iy+8)=`$C0` (destroy), likely player shots (UNCONFIRMED) |

`$07C0` and `$082F` temporarily map bank 2.

**Player response** (B2:`$8402-$84B4`):
- The player moves, and the position is clamped to y∈[`$20`,`$C0`] and x∈[`$50`,`$190`]
  (`$83A1-$83EA`).
- If the new point is solid, the game tries in turn: the old y, then the old x, then both
  (`$840F-$844E`).
- If the player is still embedded and the screen is scrolling, it pushes the player by one pixel:
  x-1 when X-scrolling, y-1 when Y-scrolling. The push is always left/up regardless of the scroll
  sign (`$8451-$848F`).
- **Crush:** if a push takes x below `$50` or y below `$20`, the game restores the saved
  position and calls `$222C` (player death) at `B2:$84B1`.
- The debug invincibility does **not** cover the crush. In early probe runs, sections 3-6 ended in
  game over this way.

---

## 5. Debug features (DSW) and trace capture

DSW0 = `$C803` (MAME `:DSW0`, active low). Bit 7 is MAME's "Service Mode".
- At reset, bit7 = 0 enters test mode (`$0158`).
- If bit7 is switched to 0 **after** reset, the game's own debug functions turn on. The condition
  is `~DSW0 & mask == mask`:

| mask | effect | code |
|---|---|---|
| `$80` | start at section `~DSW1 & $0F` (table `$15B4`, read at game start `$1594`) | `$1594-$15AD` |
| `$81` | invincible to enemy collisions (skips `$222C` at `$2648`, `$2AFC`, `$2E41`). **Not** to crush (`B2:$84B1`) | |
| `$82` | print scroll Y,X (hex) on the text layer at `$D60A`/`$D64A` | `$2140` |
| `$84` | extra frame wait (slow motion) | `$2213` |
| `$88` | skip the per-loop wait (fast) | `$2208` |
| `$90` | full power-up at game start (`$F211-$F215`) | `$1D8E` |

The default Difficulty (`$04`) already has bits 0 and 1 clear, so `$81` and `$82` come on with
bit7.

**Probe** (`tools/re_levels.lua`, run with `tools/re_levels_run.py N FRAMES --unstick 1500`):
1. At frame 120 it sets Service Mode=0, puts the section index in Coin A/B, and clears Bonus
   Life bit4 for full power.
2. Coin at frame 300, start at 400, autofire from 500.
3. When `$E090` becomes non-zero (the stage select has been consumed), it switches debug off
   again.
4. It patches `$222C`→`RET` in the ROM region. This is a full no-death patch, and it does not
   touch gameplay RAM.
5. Logs `T|frame|x|y|mode/dirs/ptr|star counts` on change and every 60 frames, plus snapshots
   every 60 frames.
6. `--unstick N`: after N frames of halt it forces `$E080=$80` for sprite bosses (`U|` line). For
   wheel bosses it ends the trace instead, because their exit teleport comes from the death
   handler.

Probe pitfalls:
- Debug invincibility on its own can hang the game. With the alpha/beta pod combine
  (`$2E4E`, `$E014=$41/$42`) the main task never wakes again. Once, it also reset the machine
  (in section 2).
- Holding up/down (`SA_SWEEP=1`) makes the pod pickup likely. Leave it off.

With the debug start, the scroll first creeps from (0,0) until the section's trigger byte matches.
That takes ~256-512 frames of garbage display before the start teleport (traces show it at frame
~1027-1283). The bosses were never killed by the static autofire probe; every halt in the traces
was ended by `--unstick`.

Trace status:

| section | ends | sheet |
|---|---|---|
| 1 | forced resume then into section 2 | `reports/levels/stage01_sheet.png` |
| 2 | wheel #1, not killed | `stage02_sheet.png` |
| 3 | forced resume then section 4 start | `stage03_sheet.png` |
| 4 | wheel #2, not killed | `stage04_sheet.png` |
| 5 | through the mid-boss into section 6 | `stage05_sheet.png` |
| 6 | into section 7's first boss | `stage06_sheet.png` |
| 7 | both bosses (forced) | `stage07_sheet.png` |
| 8 | both bosses (forced), into section 9 | `stage08_sheet.png` |
| 9 | mid-boss (forced), wheel #3 not killed | `stage09_sheet.png` |
| 10 | final boss forced; the scroll then runs into `FF` padding (not real behaviour) | `stage10_sheet.png` |

---

## UNCONFIRMED / open

- Player-facing stage numbering versus the 10 script sections.
- What selects the different boss graphics for the shared spawner `$6DB4`.
- What the per-stage `$E050` table means.
- The ending sequence and the absence of a loop. This is from static code (`$3B8A` → `$0B84`);
  no live run killed the final boss.
- The exact object classes that use `$07C0` and B2:`$949C` (likely enemy bullets/objects and
  player shots).
- The scroll slowdown mechanism. Main-loop overrun is inferred from timing differences, not
  traced.
