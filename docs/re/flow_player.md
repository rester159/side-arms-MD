# Side Arms — game flow & the player (Mobilsuit)

Scope: top-level flow (attract, credits, start, Earth intro, NAMING, continue, game over, 2P), the player
object (struct, movement, fire, weapons, death), player collision, HUD. Read `docs/re/hardware.md` first.

Citations: `$xxxx` = fixed ROM `sa03.bin`; `B<n>:$xxxx` = bank n window. "OBS" = confirmed in MAME with
the probe `tools/re_player.lua` / `tools/re_player.py` (traces `reports/oracle/{inv,weap,die,die2}`) or the
existing `reports/oracle/{attract,play1}` traces. Anything not confirmed is marked **UNCONFIRMED**.

Tables are extracted reproducibly by `tools/extract_player.py` -> `res/generated/player.json`
(movement deltas, every shot spawn record, BIT orbit path, death anim, extend/coin/lives tables, default
ranking, score table, HUD strings, player descriptors). This doc quotes only the numbers needed to read it.

## 0. Key architectural facts

- **Objects live in sprite RAM.** `$F000-$FFFF` is CPU RAM that the sprite DMA copies; every 32-byte record is
  a hardware sprite at +0..+3 (code, attr, y, x) *and* the logic fields of that object at +4..+$1F. Larger
  objects span several consecutive records. The player is `$F200-$F27F` (P1) / `$F400-$F47F` (P2), its
  BIT/weapon-attachment records follow at `+$80..+$DF`, its shots at `+$E0..+$1DF`.
- **Player coordinates are screen (sprite) coordinates**, not world. 9-bit x = `+3 | (attr bit4 << 8)`,
  y = `+2`. Screen pixel = (x - 64, y - 16) (MAME visible raw area x 64..447, y 16..239). World position is
  only computed for terrain tests: worldX = `$E092` + x, worldY = `$E094` + y (+offset), see §4.
- **Side Arms 2P is simultaneous co-op**, not alternating. Each player has its own start task, naming,
  lives, continue countdown, score and HUD half. A player can join at any time with a credit.
- Main loop runs **once per frame** (OBS: `$E003` increments by 1 every frame; waits on `$E004` at `$221E`).

## 1. RAM map (globals)

| addr | name | meaning / evidence |
|---|---|---|
| `$E001` | irq_frame | ++ every VBLANK IRQ (`$0086`) |
| `$E003` | loop_frame | ++ every main-loop pass (`$1FBB`); bit0 gates collision, bit2 HUD flash |
| `$E004` | vbl_flag | set `$88` by IRQ (`$008F`), cleared at `$2225` (frame sync) |
| `$E008-$E00F` | rng | 8-byte additive RNG stepped by credit task (`$08E3`) |
| `$E010` | game_active | 0 = attract/demo, `$80` = credits in / game (`$12FE`). Gates sound in attract (`$02F4`) |
| `$E011` | stage_running | `$52` once a stage (or demo) runs (`$0D8E`, `$158B`), 0 in attract screens |
| `$E012` | intro_busy | `$80` during Earth intro (`$1301`), 0 at `$153C`; naming tasks wait for 0 (`$17FA`) |
| `$E013` | naming_mask | players currently entering name (b7 P1, b0 P2) (`$16F3`, `$1809`) |
| `$E014` | combined | 0 normal; `$41`/`$42` = "Side Arms" combined robot led by P1/P2 (`$2E84`) |
| `$E015` | combined_hp | hits left for combined robot: 1 if both players alive else 2 (`$3059`); dec at `$2237` |
| `$E016` | fire_flash | combined robot muzzle-flash timer (`$9021`) |
| `$E018` | alive_mask | players in play (b7 P1, b0 P2) (`$187D`, cleared `$1A8A`) |
| `$E019` | continue_mask | players in CONTINUE countdown (`$1A93`) |
| `$E020/$E021` | target y, x/2 | player enemies aim at, re-picked every 8 frames (B2:`$813A-$821C`); `$78,$E0` if none |
| `$E032` | start_lives | 3 or 5 from DSW0 bit3 via `$09ED` (`$133B`) |
| `$E038` | extend_tbl | pointer to bonus-life table chosen by DSW0 bits4-5 (`$131E`) |
| `$E040` | scroll_axis | `$48` ('H') horizontal stage / `$56` ('V') vertical; set by stage script B0:`$80B8`/`$80A3` |
| `$E080` | scroll_mode | `$80` scrolling, `$40` halted, `$20` timed halt (`$E084` counter) (B0:`$8051-$8098`) |
| `$E088/$E089` | scroll step Y/X | 0 none, 1 = +1/frame, else -1/frame (`$2001-$2041`) |
| `$E090` | script_ptr | stage script pointer (bank 1), stage start `$815C` (`$158E`); see levels.md |
| `$E092/$E094` | scroll X/Y | 12-bit BG scroll (copied to `$C808/$C80A` in IRQ) |
| `$E0A2` | score_player | player struct credited by the current kill (`$2522`) |
| `$E140` | demo_variant | toggles each demo; selects demo input tables (`$0DAB`) |
| `$E148/$E14A` | demo_input P1/P2 | pointers into recorded input (`$9600/$9800` or `$9A00/$9D00`), (value, frames) pairs |
| `$E14C/$E14D` | demo_dur | frames left for current demo input; `$E14F` != 0 = **record** mode (dev leftover, B2:`$800B`) |
| `$E200/$E208` | coinA/coinB | +0 hold counter (max `$64`), +1 pending coins, +4 credits per batch, +5 coins per batch, +6 coin accumulator, +7 counter pulses (`$01A7`, `$098F`) |
| `$E240` | coins_total | (`$09AF`) |
| `$E280/$E281` | input P1/P2 | active-high copy of `$C801`/`$C802` (or demo playback) (B2:`$8014-$80F9`) |
| `$E282` | input_cur | input of the player being processed |
| `$E291/$E294/$E29C` | shadows | of `$C801`(bank), `$C804`(ctrl), `$C80C` |
| `$E600-$E607` | hi_score | 8 BCD digits, one per byte (displayed value = digits ×10) |
| `$E610-$E617` / `$E620-$E627` | score P1 / P2 | same format; `$E610`/`$E620` (top digit) not displayed |
| `$E635-$E637` | credits | 3 BCD digits; coins stop adding when `$E635` = 9 (`$09CA`) |
| `$E680-$E6CF` | ranking | 5 × 16 bytes: 8 score digits, 5 pad, 3-char name at +$0D; default from `$0B34` |
| `$E6CF` | difficulty | `~DSW0 & 7` (`$0B26`) |
| `$EF80-$EFBF` | tasks | kernel task table (hardware.md) |

**Current stage number: UNCONFIRMED** — no stage counter was found on this path; stage progress is the
script pointer `$E090` (and DSW stage-select table `$15B4`, 13 script entry points). Defer to levels.md.

## 2. Game flow

### 2.1 Task map
| slot | entry | role |
|---|---|---|
| 0 | `$0ACA` | boot: init RAM/tables ($E600 hi score, $E680 ranking from `$0B34`), region fixups by `$0AA0` ('N'), spawns slot 6, jumps `$0B84` |
| 6 | `$08DF` | credit task, forever: RNG, coin slots (`$098F`), service coin (`$C800` b5), coin counters (`$09DA`), spawns `$12AE` when credits>0 and `$E010`=0 |
| 0 | `$0B84` | attract: WARNING screen (region text `$0FA9`/`$10AC`/`$11C7`) 240 f (`$022E`) |
| 0 | `$0BD1` | title + RANKING TABLE ($E680, names/scores at `$D459`...) 360 f (`$0241` ×6), then (`J` region only) title anim `$0CFA`, then demo `$0D4A` |
| 0 | `$0D4A` | demo: stage init, `$E011=$52`, P1+P2 both spawned with 1 life, inputs from tables, → main loop `$1D8A` |
| 0 | `$12AE` | "credit" screen: kills tasks 3-5, spawns 1=`$169E` (P1 start watcher) & 2=`$16AC` (P2), clears scores, `$E010=$80`, `$E012=$80`, sets lives/extend from DSW, shows PUSH START / "1 PLAYER ONLY" or "1 OR 2 PLAYERS", 1ST BONUS, CREDIT |
| 1/2 | `$169E`/`$16AC` | per-player start + NAMING + spawn (descriptor `$1CFA`/`$1D24`) |
| 0 | `$13BC` | game start: Earth intro (BG scroll to the Earth picture `$0B00/$0E00`..., sounds `$20,$0C,$0D`, spawns slot 3 `$34FA`), "THE BATTLE FOR SURVIVAL HAS STARTED." ×6 blinks, falls into `$155A` |
| 0 | `$155A` | stage start: clear objects `$F600-$F9FF`, scroll 0, `$E011=$52`, `$E090=$815C` (or DSW1 stage select when service switch on), → `$1D8A` |
| 0 | `$1D8A` | main loop (per frame) |
| 1/2 | `$1A2C`/`$1A3A` | per-player death task (spawned by B2:`$8282` when death anim ends) |

### 2.2 Credits / start (code `$08DF`, `$01A7`, `$169E`)
- Coin switch must be held 2..`$63` IRQs (IRQ runs twice per frame) then released to count (`$01A7`).
  Each coin: sound `$1E`; every `coins_per_batch` coins add `credits_per_batch` credits (table `$0A7F`,
  indexed by inverted DSW1 coin field). Service (`$C800` b5) adds 1 credit.
- Start watcher (`$16B8`): waits for its start bit (`$1CFA`+0) with credits>0, takes 1 credit; if nothing is
  running (`$E013`=0 and `$E011`=0) it spawns the intro `$13BC` in slot 0 (game start), then runs NAMING.
  With a stage already running this is a **mid-game join** (no intro). OBS die2: 2P start at f900 → P2
  spawned f1066 while P1 played.

### 2.3 NAMING (`$16F6-$181A`)
- Name buffer drawn at `$D6D9/$D6DB/$D6DD` (P1, 3 cells 2 apart), "NAMING" at `$D6D2` (P1) / `$D6EA` (P2)
  blinking with the timer (bit2). Letters are char codes `$80..$9B`; initial `$9B`. L/R on the joystick
  steps the letter (wrap `$80↔$9B`, 6-frame repeat `$1788`). Any of buttons 1-3 (mask `$70`) confirms the
  letter and moves on (press must be released in between; `+$26` debounce). 3 letters or timeout ends it.
- Timeout: 16-bit counter `$F238` (P1) = `$0150` at game start, `$0100` when joining (`$16F6`); one tick
  per 2-frame loop (≈672 / 512 frames). OBS: 3 button taps → NAMING cleared 60 f later (`$17E4`).
- Name copied to player `+$3C..+$3E`; then waits `$E012`=0 (intro over), clears score, spawns the player
  (`$1839`: speed 1, weapons cleared, lives=`$E032`, `$1871` spawn). OBS die: start f400 → spawn f770.

### 2.4 Main loop `$1D8A` (each frame)
1. Debug (service switch ON + DSW0 bit4 low): all weapons maxed (`$1D8E`).
2. For each alive player: weapon bar HUD + weapon select `$1E03` (§6).
3. `$1FB7`: `$E003`++, scroll step, `$700B` (script/scroll engine, see levels.md), bank 2 → B2:`$8000`:
   read inputs (live or demo), **player update B2:`$821F`** for P1 then P2, choose aim target, → `$21B2`.
4. `$21B2`: object lists — `$F000-$F1FF` (16 small, `$23CB`), `$F600-$FA7F` (9 large ×128 B, `$2784`),
   `$FB00` (`$2B0B`), `$FF00-$FFFF` (8 small, `$23CB`); then frame wait (`$221E`).

### 2.5 Death, respawn, continue, game over (`$222C`, B2:`$8226`, `$1A2D`)
- Kill `$222C`: sound `$0F`; (combined robot: `$E015`-- instead). Sets death anim ptr `$23AD`,
  **speed level := 1**, state `+$08 = $C0`, and clears `+$80..+$1FF` (BIT orbiters and all shots).
- Death anim (B2:`$822E`): 8 frames × 5 f, 32×32 composite codes `$164,$166,$174,$176,$1A4,$1A6,$1B4,$1B6`
  (attr `$28`: color 8, code bit8). OBS: state `$C0` at f1003 → 0 at f1044 (41 f).
- Then death task `$1A2D`: **zeroes the level of the currently selected weapon and sets selection to 0**
  (`$1A50`, OBS die2: MBL lost f1044, BIT lost f1168; other weapons kept), lives−1 (`+$0B`);
  lives>0 → respawn `$1871` at once (OBS same frame).
- Respawn `$1871`: sprite codes from descriptor, `+$28 = $E040`, entry timer `+$29 = $50`,
  invulnerability `+$0E = $50`, state `$80`, facing right `$72`, sound `$09`. Spawn position:
  H stage P1 (y`$40`,x`$20`), P2 (y`$A0`,x`$20`); V stage P1 (y0,x`$C0`), P2 (y0,x`$120`).
- Entry glide (B2:`$829F`): while `+$29` counts down from `$50`: x += 3/2/1 (H) or y += 3/2/1 (V) for
  `+$29` ≥`$3C`/`$28`/`$14`, sprite codes `$62,$66,$72,$76` (−2 if facing left). From `+$29 < $3C` any
  joystick direction latches `+$2A` and returns control early. The sprite blinks (invisible on odd `+$29`,
  B2:`$8F02`) and only the normal shot can be fired until `+$29` = 0. OBS: x `$20→$98` f770-f840.
- Lives = 0: `$E019` set; if DSW1 "Allow continue" (`$C804` b6): "CONTINUE" + digits at `$D6D4`, counts
  **10 → 0, one step per 60 frames** (`$1ACA`, sound `$0E`); Start + credit continues: score cleared,
  extend pointer reset, lives=`$E032`, respawn. OBS die: CONTINUE10 at f1290 … CONTINUE 0 at f1890.
- Timeout: ranking insertion `$1C02` (compares with 5 entries, shifts table, `$E102` = rank 1-5;
  rank entry UI UNCONFIRMED), "GAME OVER" at `$D6D4` (sound `$2E`) for 210 f; if no player is left
  (`$E018`,`$E019`,`$E013` all 0) → slot 0 = `$0B84` (attract). OBS die: GAME OVER f1950-f2160.
- In the demo (`$E010`=0) the first death task jumps to `$1BF7` → ranking screen `$0BD1`
  (OBS attract trace: demo f666-f3887; P2 combined robot at f3277).

### 2.6 Debug features on the service DIP (`DSW0` bit7, read after boot)
Service ON after boot plus other DSW0 bits (active-low, tested as `~DSW0 & mask == mask`):
`$81` invincible (`$2648`; OBS run `inv`), `$82` scroll coordinates printed at `$D60A/$D64A` (`$2140`, OBS),
`$84` half speed (`$2213`), `$88` no frame wait (`$2208`), `$90` all weapons max (`$1D8E`),
`$80` + DSW1 low nibble = stage select at stage start (`$1594`, table `$15B4`).

## 3. Player struct (`$F200` P1, `$F400` P2; same layout)

| off | meaning | evidence |
|---|---|---|
| +$00/+$20/+$40/+$60 | sprite codes of the 2×2 composite: c, c+1, c+8, c+9 | B2:`$8F38` |
| +$01 | attr: b0-3 color (P1 0, P2 4), b4 = x bit8, b5-7 code bits8-10 | |
| +$02 / +$03 | y / x low byte (screen sprite coords) | B2:`$8384` |
| +$22,+$23 / +$42,+$43 / +$62,+$63 | pieces at (y,x+16), (y+16,x), (y+16,x+16) | B2:`$8F48` OBS |
| +$06 | fire latch (5 after a shot; cleared only when buttons 1+2 released) | B2:`$86E2` |
| +$07 | weapon-select latch (`$43`, cleared on button 3 release) | `$1E24` |
| +$08 | state: `$80` alive, `$C0` dying, 0 off | |
| +$09 | facing: `$6C` left, `$72` right | B2:`$86FC` OBS |
| +$0A | player bit (`$80` P1, `$01` P2) | `$1874` |
| +$0B | lives | `$1850`, HUD `$067B` |
| +$0C | firing-pose timer (adds +4 to code while >0) | B2:`$8F13` |
| +$0E | invulnerability frames after spawn (`$50`) | `$18DD`, `$2643` |
| +$0F | death-anim frame timer | B2:`$822E` |
| +$10 | selected weapon slot 0..5 (0 = normal shot only) | |
| +$11..+$15 | levels: BIT 0-3, S.G. 0-3, M.B.L. 0-2, 3WAY 0-2, AUTO 0/`$10`/`$11` | `$26C2-$271D` |
| +$17 | x/2 (9-bit x >> 1), used by all collisions | B2:`$8074` |
| +$18 | speed level 1..3 | `$2694`, B2:`$8371` |
| +$1A/+$1B | pointer to next bonus-life score | `$22AE` |
| +$1C/+$1D | death-anim pointer | |
| +$28 | copy of `$E040` (H/V) | `$1896` |
| +$29 | entry/blink timer (`$50`) | |
| +$2A | early-control latch during entry | B2:`$82B5` |
| +$30/+$31/+$32 | previous attr / y / x (terrain revert) | B2:`$8085-$8094` |
| +$34 | combined-robot leader id (`$41/$42`) | `$2E87` |
| +$35 | combined robot shot-pattern toggle | B2:`$8D88` |
| +$38/+$39 | naming timer; +$3A debounce; +$3B letter index; +$3C..+$3E name | descriptor |
| +$80/+$A0/+$C0 | BIT orbiters (or M.B.L. launcher sprite at +$80) | `$1F26`, B2:`$8583` |
| +$E0..+$1DF | shot slots, 32 B each (normal: first 4; weapons up to 9) | |

Per-player constant descriptor (ROM): `$1CFA` (P1) / `$1D24` (P2): start mask, player bit, base sprite code
(`$62`/`$E2`), spawn attr/positions, and pointers to its HUD strings, score, naming vars (see JSON).

Sprite codes (P1; P2 = same +`$80`, color 4, B2:`$8FB8`): idle right `$22`, idle left `$20`; firing +4
(`$26`/`$24`); weapon pose: slot 3 (M.B.L.) +`$10`, slot 4 (3WAY) +`$20`, slot 5 (AUTO) +`$30`
(B2:`$8583-$85E6`). OBS: wsel3 code `$32`, wsel4 `$40`, wsel5 `$50`.

## 4. Movement (B2:`$8368`) and terrain

```
dir = input & 0x0F                        ; b0 R, b1 L, b2 D, b3 U  ($E282, active high)
(dy,dx) = MOVE[speed][dir]                ; tables B2:$864C/$866C/$868C (combined robot: B2:$86AC)
y += dy; x(9-bit) += dx
clamp y to [$20,$C0]; x to [$50,$190]     ; B2:$83A1-$83EA
if entry timer == 0: terrain test (B2:$84B5); on hit try: old y, then old x, then both (B2:$840F-$8445)
if still inside terrain: pushed 1px/frame against the scroll (x-- if X scroll active, y-- if Y)
   and killed (call $222C) if pushed past x<$50 / y<$20  (B2:$8451-$84B1)  = crushed by scrolling
```
Speeds (px/frame): level 1 = 4 orthogonal / 3+3 diagonal, level 2 = 5 / 4+4, level 3 = 6 / 5+5.
OBS: speed1 x +4/frame (run `inv` f900-960), speed2 y −5 and diag −4 (run `weap`), speed3 y +6, diag +5,+5;
clamps y=`$20`/`$C0`, x=`$50` observed.

Terrain: a 1-bit collision map in **B2:`$A000-$BFFF`** (bank 2 selected while the player code runs):
16×16-px cells over the 4096×4096 world. For world (X,Y): byte = `$A002 + ((X>>3)&~1) + (Y>>8)*512 +
((Y&$FF)>=$80)`, bit = `7 - ((Y & $70)>>4)` (B2:`$84B5`). Player probe point: X = `$E092`+x, Y =
`$E094`+y+`$10`; shots: X = `$E092`+x+8, Y = `$E094`+y+8 (B2:`$949C`). **Terrain blocks the player, never
kills by contact** (only scroll-crush). OBS run `inv`: player stuck at (y`$98`,x`$110`) holding down-right.
Exact pixel origin of the map vs BG tiles: UNCONFIRMED (levels.md should cross-check).

## 5. Fire and weapons (B2:`$86CC-$8D11`)

**Buttons**: Button 1 = fire **left** (facing `$6C`), Button 2 = fire **right** (facing `$72`); facing
persists (B2:`$86FA`). Button 3 = cycle weapon slot (`$1E24`). OBS run `inv`. One shot per press for all
weapons except AUTO (fire latch +$06; a press with no free slot is lost). Pressing both 1+2 = no new shot
for AUTO (`$8BF5`). Shot spawn = 8-byte record (code, attr, dy, dx, vy, vx, half-height, half-width)
relative to player (y,x) (`$938F`); shots move linearly each frame (`$93FB`), die when y ≥ `$F4`, or off the
x range (x<`$30` with bit8 clear / x≥`$1C0`), or on terrain → explode (state `$C0`, codes `$1C→$1E`, color 5,
16 f, `$9467`). All player shots use color 8.

| slot | weapon | behaviour | records / numbers |
|---|---|---|---|
| 0 | normal | 1 shot per press, max 4 alive, v=14 px/f, sound `$01` | code `$16`, dy+2, dx 0 / +16, hit 3×9 (`B2:$90DF`) |
| 1 | BIT (lv 1-3) | 1-3 orbiting "bits" (codes `$0C-$0F` color 3) circling the player on a 32-step path (`$1F56`, 1 step/frame); each press fires the normal shot plus one `$0B` shot (v 14) from every bit | start phases: L2 0/16, L3 0/10/22 (`$1F26`) OBS |
| 2 | S.G. (shotgun, lv 1-3) | 3/5/7 pellets spread (needs all 7 slots free), live 15 f then burst (sound `$03`); sound `$02` | codes `$83`/`$8E`/`$8F`, v up to (±9,±9) (`B2:$910F-$91F7`) OBS L3 |
| 3 | M.B.L. (lv 1-2) | piercing beam of 6 (lv1: 4) segments (`+$07=$4D` = no explode on hit), released 1 frame apart, v=16; launcher sprite on the player; sound `$04` | codes head `$13`/body `$14`/tail `$15` right, `$10/$11/$12` left (`B2:$91FF`) OBS |
| 4 | 3WAY (lv 1-2) | 3 shots (−5,11),(0,14),(5,11); up to 3 volleys; lv2 shots animate codes `$18-$1B`; sound `$01` | `B2:$920F/$9227` OBS |
| 5 | AUTO `$10` | hold one fire button: 1 shot / 4 frames, max 8, v 14, sound `$05` | code `$03` (`B2:$923F`) OBS |
| 5 | AUTO `$11` | hold: every 8 frames 3 shots up(v−10)/forward(16)/down(+10), max 3 volleys, sound `$06` | `B2:$924F/$9267` (code only) |

Names on the bar (OBS screenshot): `BIT`, `S.G.`, `M.B.L.`, `3WAY`, `AUTO`. What the two AUTO variants
(item `$10`/`$11`) are called in-game: UNCONFIRMED.

Weapon select `$1E03`: if slot is 0 and any weapon owned, pick the first owned; button 3 (edge) moves to the
next owned slot cyclically, sound `$1C`. OBS order 3→4→5→1→2→3.

Items (picked up by touching an object whose `+$0A` ≠ 0, `$2657`): `$80` speed+1 (max 3), `$81` speed−1
(min 1), `$01` BIT+1 (max 3), `$02` S.G.+1 (3), `$03` M.B.L.+1 (2), `$04` 3WAY+1 (2), `$10`/`$11` AUTO
type, `$06` combine, `$07` nothing, `$08` extra life. Which POW form gives which code: objects.md.

**Combined "Side Arms" robot** (item `$06`, `$2E4E`): sound `$0A`, shots cleared, partner object `$FA80`
(template `$30E6`/`$31DA`) flies in from a fixed point, or starts at the other player's position (that player
is hidden) if the other player is alive (`$2F1B-$2F8A`); then `$2F9A` merges both structs
into one 32×48 sprite (P1-led codes `$40..`, P2-led `$80..`), `$E014=$41/$42`, hit points `$E015`
(1 or 2). Movement table B2:`$86AC` (speed 5/4) driven by the OR of both joysticks; fires an 8-way ring
(codes `$90-$9E`) every 4 frames alternating two patterns (B2:`$8D51`, `$927F/$92BF`). Unmerge on hits
exhausted (`$223F`). Details beyond this: UNCONFIRMED (not exercised live; seen in the attract demo).

## 6. Collision with enemies / bullets (`$2500`, `$2591`, `$2617`)

Runs inside each object's update on **even frames only** (`$2500`):
- Player shots (`$F2E0+`, 9 slots per player) vs object if object `+$09` b0 = 0: hit when
  `|ys − yo| < hs.h + ho.h` and `|x/2s − x/2o| < hs.w + ho.w` (`+$0C/+$0D` half sizes, x in half pixels).
  Shot explodes unless `+$07` ≠ 0 (M.B.L.); object `+$0B` (HP) −1; at 0 → score `$2272` (index `+$15` into
  `$2337`: 50/100/200/300/500/800/1000/3000/5000/10000/30000) credited to the shooter, hi-score and
  bonus-life check (`$22AE`: extra life, sound `$1D`).
- Object vs player if object `+$09` b1 = 0 (`$2617`): `|(py+8) − yo| < o.+$0E` and `|(px/2+4) − xo/2| <
  o.+$0F`; player must be alive. Hostile object (`+$0A` = 0) kills unless player `+$0E` > 0 or debug
  invincible; otherwise it is an item. Enemy bullets are objects of the same lists, so they use the same
  test (large objects have equivalents around `$2A20`/`$2DEB` — UNCONFIRMED details).

## 7. HUD (text layer; `$D000` code / `$D800` attr, row r col c = `$D000+64r+c`, screen x = (c−8)·8, y = (r−2)·8)

| item | VRAM | routine / data |
|---|---|---|
| `1UP` / `HI` / `2UP` | `$D08A` / `$D09A` / `$D0AA` (row 2) | strings `$06C3/$06CB/$06D2` |
| P1 score / hi / P2 score | `$D08E` / `$D09E` / `$D0AE` | `$05F2/$0603/$0614` → `$0627`: 7 digits from `$E611`/`$E601`/`$E621`, leading zeros blank, then a fixed `0` |
| lives icons (char `$40`, lives−1, max 5) | `$D0CA` / `$D0EA` (row 3) | `$067B` |
| CREDIT n | `$D69B` / digits `$D6A1` | `$15D4` |
| NAMING / CONTINUE nn / GAME OVER | P1 `$D6D2`/`$D6D4`, P2 `$D6EA`/`$D6EC` (row 27) | §2 |
| weapon bar (chars `$50-$63` = BIT S.G. M.B.L. 3WAY AUTO, 4 cells each) | `$D70A` / `$D722` (row 28) | `$19BE/$19D7`; colors written each frame by `$1E7C`: attr `$20` none, `$25` owned, selected flashes `$23/$24` (every 4 f) at `$DF0A`/`$DF22` |
| SPEED label (chars `$70-$77`) + meter | `$D74A` / `$D762` (row 29) | `$19F0/$1A03`; meter `$275D`: speed × (`$78,$79,$7A,$7B`) at `$D752`/`$D76A`; attrs flash `$27/$29/$2B` ↔ `$28/$2A/$2C` |

OBS run `inv` screenshot f1000 (bar + SPEED meter) and HUD text dumps (runs `die`, `inv`).

## 8. Constants summary
- Lives 3/5 (`$09ED`); extend tables `$09F7` (100k once), `$0A07` (every 100k to 500k), `$0A37`
  (150k,300k,450k,600k), `$0A5F` (200k,400k,600k); hi score default 100000; ranking TAK/TOY/KEI/AOK.
- Spawn invulnerability 80 f, entry 80 f, death anim 40 f, continue 10 steps × 60 f, GAME OVER 210 f,
  naming timeout ≈672 f (start) / 512 f (join).
- Normal shot speed 14 px/f, max 4; M.B.L. 16 px/f; S.G. pellets live 15 f.
- Sound commands (queued via `$02F3`; meaning in sound.md): fire `$01`, SG `$02/$03`, MBL `$04`, AUTO
  `$05/$06`, combined fire `$07`, spawn `$09`, combine `$0A/$0B`, continue tick `$0E`, death `$0F`,
  kill `$12`, speed up/down `$1A/$1B`, weapon `$1C`, 1UP `$1D`, coin `$1E`, game over `$2E`.

## 9. Open / UNCONFIRMED
- Stage counter variable; stage-clear and stage-transition flow (script-driven, levels.md).
- Ranking name-entry screen after a high score (`$E102` rank is set by `$1C02`; UI not traced).
- AUTO `$11` and the combined robot were not exercised live (code reading + attract demo only).
- In-game names for item codes / POW cycling (objects.md); terrain-map pixel alignment.
- `$34FA` (slot 3 during intro) and `$700B` (scroll/script engine) not analysed here.

## Probes
`tools/re_player.py NAME FRAMES --input FILE [--snap N] [--snapat a,b]` runs `tools/re_player.lua`
(input lines as capture.lua, plus `<f> :DSW0 "dip:Service Mode" 0` and `<f> poke <addr> <byte>`), logs per
frame `$E000-$E2FF` + `$F000-$FFFF`, text RAM at snapshot frames, and every write to `$F208/$F408` with PC.
Runs used: `inv` (invincible movement/fire), `weap` (poked weapon levels, speed 2/3), `die` (3 deaths →
continue → game over), `die2` (weapon loss on death, P2 join).
