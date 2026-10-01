# Front end, game flow and HUD

Native Genesis implementation of the arcade's attract loop, credits, NAMING, Earth intro, continue,
game over and ranking, plus the in-game HUD, and the port's own front end (boot screen, Arcade
INSERT COIN screen, Home screen with options, controls, sound test, SRAM settings). Arcade behaviour comes from `docs/re/flow_player.md`
(§2 flow, §7 HUD); the code cites the arcade addresses. Nothing here runs or mirrors the Z80
task kernel: the arcade's cooperative tasks became one top-level state machine and one small
state machine per player.

| file | role |
|---|---|
| `src/game.c` | `game_init/update/draw` entry points, `sound_play` (demo-sound DIP muting) |
| `src/flow.c` | settings in effect (`game_cfg`), difficulty tables, ranking + SRAM, state dispatch |
| `src/flow_menu.c` | port menus: boot screen, Home screen, DIP switches, OPTIONS, CONTROLS, SOUND TEST |
| `src/flow_attract.c` | Arcade INSERT COIN screen, WARNING, title + RANKING TABLE, attract demo |
| `src/flow_game.c` | coins/credits, credit screen, start + NAMING, Earth intro, stage start, continue, game over, 2P join |
| `src/flow_scene.c` | pre-rendered background scenes (title city, Earth intro) on plane B |
| `src/hud.c`, `inc/hud.h` | window-plane text, H-int window split, glyph pools, in-game panel |
| `src/input.c` | pad reading, control mapping (remapping, 6-button extras, autofire) |
| `inc/flow.h` | `GameConfig game_cfg`, flow states, shared helpers |
| `tools/build_frontend.py` | build-time conversion (run by `tools/build_assets.py`) |

## Build-time data (`tools/build_frontend.py`)

Everything is regenerated from the ROM set into `res/generated/fe_*.bin`, `src/gen/frontend.s`,
`src/gen/frontend_data.c` and `inc/gen/frontend.h`:

- **Logo.** The title routine draws the SIDE ARMS logo with `$0DF5` → `$03BD` record `$0EA4`
  (32×8 text-layer chars `$100-$1FF`, attr `$70`, colour `$30`, arcade row 5 col 16). It is
  rendered with the text-pen LUT (`txt_lut`) into 172 deduplicated (with flips) Genesis tiles and
  a 32×8 nametable.
- **MD** (Home screen, not an arcade item). The letters M (of "ARMS") and D (of "SIDE") are cut
  out of the rendered logo: each letter is its white/cyan body (flood fill from seed pixels inside
  it) plus the logo's red outline pixels within 3 px of that body, so stroke shapes, outline and
  the white-to-cyan gradient are the logo's own. Side by side, centred: 8×5 cells, 39 tiles,
  `fe_md_tiles` / `fe_md_map`, drawn under the logo at VRAM tile 1953 (`HUD_MD_TILE`, sprite set 2,
  free on menu screens).
- **Weapon bar.** Glyphs `$50-$63` in the four bar colours of `$1E7C` (`$20` not owned, `$25`
  owned, `$23`/`$24` selected flash): 4×20 tiles, streamed per player at run time.
- **Background scenes.** The fixed world views of the title (`$0C05`: scroll `$180,0`) and the
  Earth intro (`$13E8-$1538`: 15 scroll positions) are rendered from the BG ROMs at the Genesis
  camera (scroll + (96, 16)) and quantized to PAL0/PAL1 with `quantize.fit`, keeping the star
  colours at the indices the starfield tiles use. Set 0 (title): 215 tiles; set 1 (Earth intro):
  617 tiles. The burning-Earth positions (`$480/$600`, `$900/$A00`) are not inside any bg.c zone,
  which is why the front end does not use bg.c for them.
- **Strings** from their `$03BD` records: region warning (`$0AA0` = 'N' → `$11C7`), ranking header
  `$0DFC`, ordinals `$0E16`, copyright `$0E6C`, PUSH START `$160B`, `$1621`/`$1633`, 1ST BONUS
  `$1646`, CREDIT `$165F`, battle text `$166D`, 1UP/HI/2UP `$06C3/$06CB/$06D2`, NAMING `$1A16`,
  CONTINUE `$1D4E`, GAME OVER `$1D6C`, INSERT COIN `$0E94`. Placement: Genesis cell = arcade
  (col − 12, row − 2). `$0E94` ("INSERT COIN", 1×11, attr 2, address `$D140` = row 5 col 0) sits
  next to the logo record `$0EA4` but no code of this World set references it (scan of every
  `ld rr,$0E94`); the arcade attract never shows it (MAME, 4600 frames, no coin).
- **Enemy bullet speed** per difficulty: B0:`$813C` (10 stage musics × 8 DIP levels), loaded with
  the stage music by B0:`$80CA` → `fe_bullet_speed`; `game_bullet_speed()` replaces the
  default-difficulty value the level data carries.
- **Default ranking** `$0B34` (5th name's first letter patched by region as `$0B04`), bonus
  tables `$09EF`, lives `$09ED`, difficulty rank offsets B0:`$8049`.
- **Attract demo.** Recorded inputs B2:`$9600/$9800` (variant 1) and `$9A00/$9D00` (variant 2)
  as (value, frames) pairs read the way B2:`$802C` reads them (the first pair is at +2, a 0
  duration is 256 frames), capped at 4000 frames. The demo scroll scripts B1:`$8000` and
  B1:`$8074` are simulated (1 px per 2 frames, record fires when the moving axis' low byte equals
  its trigger) into camera-triggered events: teleport, direction, music (`$8130` → sound `$27`),
  spawn, end (`$806E`: call `$0BD1`). Spawn records are matched to the stage spawn table entry
  with the same command and target (`tools/build_levels.py` ordering).

## HUD (window plane)

The window plane (VRAM `$B000`, 64×32, high priority) carries all text. The rows that show the
window are every row holding text plus forced rows (kept as a bit mask, updated by each cell write).
When that mask is one top block plus one bottom block (the in-game HUD: rows 0-2 and 25-27, and
any screen without text in the middle rows), VDP register `$12` can express each block directly
(`$0n`: rows 0..n-1, `$80|n`: rows n..27): the VBlank interrupt sets the top block and a single
H-interrupt between the blocks switches to the bottom block — two register writes per frame.
Any other mask (title/ranking text, the ending) uses an H-interrupt every 8 lines (counter 7: end
of lines 7, 15, …, 223) that sets `$80` (on) or `$00` (off) for the row that starts next; the
VBlank interrupt prepares row 0. The row mask and split computed by `hud_frame()` are applied by
the next VBlank interrupt, together with the nametable DMA of the same rows (applied at once, a
cleared row vanished one frame before its text: a 24/12 blink measured 23/13). (QA: the 28 interrupts of the general mode cost ~8% of the
68000 — ~20 lines a frame — so the game uses the 2-interrupt mode.) Plane A's starfield stays visible on all other rows. All nametable and tile
writes go through SGDK's DMA queue; the window shadow is a 40×28 RAM array sent row by row when
dirty.

Glyphs are arcade text chars (codes 0-1023, colour 0-63), converted on first use from
`font_pens` with `txt_lut` and uploaded as one `DMA_QUEUE_COPY` run per frame:

| pool | VRAM tiles | used for |
|---|---|---|
| bar tiles | 1312-1351 (2 × 20) | weapon bars, re-streamed when a slot changes state |
| game pool | 1352-1407, 1520-1535 (window rows 28-31, never displayed), 1940-1951 (SAT bytes `$280-$3FF`; 80 sprites use `$280`), 2033-2047 (after the sprite module's last 32×32 slot) — 99 tiles | HUD rows 0-2 and 25-27, and every row while sprites are drawn |
| logo | 1056-1227 (front-end screens) or 160-331 (demo variant 1, BG off) | SIDE ARMS logo |
| screen pool | 1232-1311, 1664-1791 — 208 tiles | rows 3-24 on screens without sprites |

The logo and the screen pool use the sprite pattern area, so they exist only while no sprite is
drawn; `stage_sprites_on()` (`spr_init()`) hands the area back before the demo or a stage.
The scenes use the BG metatile cache area while bg.c is switched off; `stage_video_on()` selects
the zone under the camera with `bg_set_zone()`, which flushes bg.c's cache.

### In-game layout (40 columns; the arcade's is 48)

| row (y) | content | arcade |
|---|---|---|
| 0 (0) | `1UP` col 0, P1 score cols 4-11, `HI` col 14, hi score cols 17-24, `2UP` col 28, P2 score cols 32-39 | row 2 (`$D08A..$D0AE`), score format `$0627` (7 digits, leading zeros blank, fixed final 0, zero = blank) |
| 1 (8) | lives icons (char `$40`, lives − 1, max 5) under 1UP / 2UP | row 3, `$067B` |
| 2 (16) | boss hit bars: one `$6C-$6F` group per remaining bar, right-aligned | row 4, `$089F` |
| 25 (200) | per player (P1 cols 0-19, P2 20-39): `NAMING` + 3 letters 2 cells apart / `CONTINUE` + 2 digits / ` GAME OVER` (colour 4) | row 27 |
| 26 (208) | weapon bar, 20 cells per player | row 28, `$19BE`, colours `$1E7C` |
| 27 (216) | `SPEED` (colour `$2F`) + meter: speed × (`$78,$79,$7A,$7B`), colours `$27/$29/$2B` ↔ `$28/$2A/$2C` on frame bit 2 | row 29, `$19F0`, `$275D`, `$1EE2` |

Weapon bar: slot = `$20` not owned, `$25` owned, the selected weapon flashes `$23`/`$24` on frame
bit 2 (`$1E7C`). Bars and SPEED show while a player plays, continues or shows GAME OVER.

## Flow

```
boot screen (ARCADE / HOME, "PORTED BY RESTER 159, 2026")
 ARCADE -> INSERT COIN screen --(Up Up Down Down Left Right Left Right: chime $1D)--> DIP SWITCHES
           |  idle 900 f                                                            BACK / B -> boot
           v
           WARNING -> TITLE -> DEMO -> TITLE -> DEMO ...           (attract)
           coin (Start with no credit, or C) on any of these -> CREDIT -> Start -> INTRO -> PLAY
           PLAY: all players out -> WARNING                         ($1BD9 -> $0B84)
 HOME   -> Home screen (logo + MD): START GAME -> INTRO -> PLAY; all players out -> Home screen
                                    OPTIONS -> CONTROLS, SOUND TEST;  BACK / B -> boot
A+B+C+Start on pad 1: back to the boot screen.
```

| state | arcade | timing (frames) |
|---|---|---|
| COIN (port) | title look (`$0BD1` city, logo, 1UP/HI, copyright) + INSERT COIN (`$0E94`, colour 2, cell 14,16) + CREDIT n (`$165F`, digits `$D6A1`) | INSERT COIN and CREDIT n blink 24 on / 12 off (`$1545`, the arcade's text blink); 900 f without input → WARNING |
| WARNING | `$0B84`: region text (colour 4), BG and stars off | 240 (`$022E`) |
| TITLE | `$0BD1`: city (scroll `$180,0`), logo, RANKING TABLE, copyright, top row 1UP/HI | 360 (`$0241` × 6), then ranking cleared, logo stays 30 (`$021C`) |
| DEMO | `$0D4A`: scroll 0,0 → script teleport, rank 2 (`$0DC7`), both players 1 life (`$0DCC`), recorded inputs; variant toggles each time (`$E140`) | until the script's end record (variant 1: 3012 frames, arcade trace 3221 incl. init), a player's death (`$1A46` → `$1BF7`), or 3600 frames (variant 2 has no end record) |
| CREDIT | `$12AE`: Earth (scroll `$B00,$E00`), PUSH START BUTTON, 1 PLAYER ONLY / 1 OR 2 PLAYERS (credits ≥ 2), 1ST BONUS xx0000 PTS (first bonus score), CREDIT n; top row 1UP/HI/2UP (`$E010` = `$80`) | until Start |
| INTRO | `$13BC`: music `$20` + sound `$0C`; Earth 30; 24×(Earth 2, flash 2); burnt 2 + 23×(flash 2, burnt 2); burnt 42; sound `$0D`; 12 burning scenes × 9 (sound `$0D` before the 6th); burnt Earth: intro over (`$E012` = 0, `$153C`), 60; 6 × (battle text 24, off 12) | stage at 646 frames (arcade play1: start f400 → stage f1050) |
| PLAY | `$155A`: `level_start(0)`, bg.c and sprites back, enemies/bosses reset | |

**The arcade's INSERT COIN.** The World set never draws an INSERT COIN text and nothing blinks on
its attract or credit screens (MAME: text RAM of 4600 attract frames, and the credit screen frame by
frame after coins at f300 / f500: the only text changes are the screen changes and the credit
digit). A coin opens the credit screen at once (MAME: coin f300-f306 → credit screen f308; the
credit task `$08DF` spawns `$12AE` when credits > 0). The port's COIN screen is therefore built
from arcade parts: the title screen without the ranking table, the ROM's unused INSERT COIN record
and the credit screen's CREDIT line, blinking with the only blink the game has for text (the
battle text `$1545`, 24/12). Measured in the port: 24 frames shown, 12 hidden, period 36.

Per player (`PFlow`):

- **Start / coins** (`$16B8`). Arcade: a coin = pad C on the attract/credit/COIN screens, or Start
  while there is no credit ("Start adds a coin"; sound `$1E`, max 9); with credits, Start takes
  one and starts (or joins, or continues). With credits on any attract screen the credit screen
  opens (`$08DF`), also after a game over with credits left. Home: START GAME on the Home screen
  starts at once with the CREDITS setting (default 3); the starter takes one, a 2P join takes one,
  a continue takes one (CONTINUE = LIMITED) or none (UNLIMITED).
  A start in the attract screens starts the game and the intro; a start while the game runs is a
  join (pad 2 Start for player 2).
- **NAMING** (`$16F6-$181A`): timer `$150` ticks at game start / `$100` when joining, one tick per
  2 frames; label blinks with tick bit 2; joystick right/left steps the letter (A-Z, blank, bar;
  wrap; 6-frame pause after a step); buttons 1-3 confirm a letter (released in between); each
  letter starts at the bar (`$9B`). After 3 letters or the timeout the name stays 60 frames, then
  the player waits for the intro (`$E012`), starts the stage if it is not running yet (this cuts the
  battle text short, as in the arcade: run `die`), and spawns (`player_start`, lives from the
  settings).
- **Continue** (`$1A81`, `$1ACA`): when `player_out_of_lives()`: CONTINUE 10 → 0, 60 frames per
  step, sound `$0E` per step; Start (+ credit) → `player_continue()`. Offered in Arcade when the
  CONTINUE DIP is on; in Home when CONTINUE is UNLIMITED, or LIMITED with a credit left.
- **Game over** (`$1B5F`): ranking insertion of the best score of the game (kept over continues,
  `$1A96`) with the NAMING name (`$1C02`), GAME OVER (colour 4) for 210 frames, sound `$2E`. When
  nobody plays, continues or names, Arcade restarts the attract at the WARNING (`$1BD9`), Home
  returns to the Home screen.
- The ending (`boss_game_cleared()`) also ranks the players and leaves the same way.

While `players_world_frozen()` (combined-robot merge) the level, enemies and bosses are not
updated. Scoring follows `score_enabled` (off in the demo), the bonus-life table `extend_setting`.

### Settings

Menus read the physical pad: Up/Down choose, Left/Right change a value, A / C / Start select or
step a value, B goes back. Every exit saves to SRAM.

| | Arcade (DIP SWITCHES, hidden: code on the COIN screen) | Home (OPTIONS) |
|---|---|---|
| difficulty | 1-8 (DSW0 `~DSW0 & 7`, default 4) | EASY, 1-8, HARD (default 4) |
| lives | 3 / 5 (`$09ED`) | 1-7 (default 3) |
| bonus life | 100K only / every 100K / 150K… / 200K… (`$09EF`) | same + NONE |
| continue | ON / OFF (DSW1 bit 6) | OFF / LIMITED (uses credits, default) / UNLIMITED (free) |
| credits | coins (Start / C) | CREDITS 1-9 per game (default 3) |
| demo sounds | ON / OFF (DSW1 bit 7, `$02FA`) | ON |
| COLOR | ARCADE / VIVID | same (shared) |
| controls, sound test | — (the Home settings apply in both modes) | CONTROLS, SOUND TEST submenus |

Difficulty effects (both from the arcade): enemy bullet cap `$E017` = rank + B0:`$8049[d]`
(`game_rank_offset()`: −3 −2 −1 0 1 2 2 3) and enemy bullet speed level `$E050` from B0:`$813C`
per stage music (`game_bullet_speed()`). The Home presets extend the DIP range by one step each
way (port choice): **EASY** = cap offset −4, bullet speed 3 (the slowest) on every stage;
**HARD** = cap offset +4, bullet speed one level above DIP 8's (max 6).

`game_cfg` (`inc/flow.h`) holds the settings in effect, built by `flow_apply_config()` from
`dip_cfg` (Arcade) or `home_cfg` (Home).

**SOUND TEST**: MUSIC `$20-$38` and SOUND `$01-$1E`, every command id, with names from
docs/re/sound.md and the port's own calls (`?` = use not confirmed; `(EMPTY)` = an empty set);
A/C plays, STOP sends `$00`, leaving stops all.

### Controls (`src/input.c`, OPTIONS > CONTROLS)

`input_update()` maps the physical pad (`pad_raw`, SGDK `BUTTON_*`) to the logical `IN_*` bits the
game reads (`pad[]`), so the game code is unchanged:

| setting | values | default |
|---|---|---|
| FIRE LEFT / FIRE RIGHT / WEAPON | A B C X Y Z (X/Y/Z fall back to the action's default A/B/C on a 3-button pad) | A / B / C |
| BUTTON X / Y / Z (6-button pad, `JOY_getJoypadType`) | NONE, PREV WEAPON, NEXT WEAPON, BIT, S.G., M.B.L., 3WAY, AUTO, LOCK FIRE | PREV / NEXT / LOCK FIRE |
| AUTOFIRE LEFT / RIGHT | OFF / ON | OFF |

- The arcade fires one normal shot per press (latch `+$06`, B2:`$86E2`). **Autofire** turns a held
  fire button into one press every 4 frames (2 on, 2 off), the cadence of the arcade's AUTO weapon
  `$10` (1 shot / 4 frames, B2:`$8BEA`). It is off while the ship is not alive and in play, with
  the AUTO weapon and in the combined robot (both already repeat on frame phase while held).
  Measured: 30 shot onsets in 120 frames held, all 4 frames apart; without autofire 1.
- **Weapon buttons** (PREV/NEXT/BIT…AUTO): `pad_weapon_req` → `weapon_select()` (weapons.c) picks the
  previous/next owned weapon or that weapon if owned, at once, with the effects of a button-3 step
  (sound `$1C`, shots cleared, orbit rebuilt). Not in the arcade (one select button). Measured with
  BIT, S.G., 3WAY owned: NEXT ×3 → 4 1 2, PREV ×2 → 1 4.
- **LOCK FIRE**: while held it is the fire button of the current facing (`facing_left`), so the ship
  fires without turning; it follows that side's autofire setting.

### Ranking / SRAM

5 entries {score, 3 arcade char codes}, saved at every insertion; settings saved when a menu is
left. Cartridge SRAM (header "RA", `$200001`, odd bytes), byte offsets:

| offset | content |
|---|---|
| 0-3 | magic `SAR2` (v1 saves: `SAR1`) |
| 4-38, 39 | ranking 5 × 7 bytes, checksum — the v1 layout, so a v1 save keeps its ranking |
| 40-60, 61 | settings: version 1, DIP ×5, Home ×5, COLOR, last mode, controls ×8; checksum |

Loading: a bad checksum, an unknown settings version or an out-of-range value resets that block
to the defaults (the ranking to `$0B34`). `hi_score` (player module) starts at the top entry.

## Verification

Headless runner (`SIDEARMS_BUILD=.local/build-frontend`, `tools/run_rom.py`; pads through
`dbg_pad_override`, enemy spawns muted with `en_dbg_mute` where noted):

- Attract cycle timings: WARNING f84 → TITLE f324 (240) → DEMO f714 (390) → TITLE f3734 (demo 1:
  3020 frames incl. the scroll to the first teleport; arcade attract trace f666 → f3887 with the
  arcade's init) → DEMO 2 f4124 → TITLE f4544 (demo 2 ended by a death) → DEMO 1 again.
- Screens compared with the arcade snapshots (`reports/oracle/attract/snap`, `play1` sheet): warning
  text, ranking table (logo, city, columns), demo with logo + both HUD bars, Earth intro sequence and
  the battle text, NAMING blinking, CONTINUE countdown (10 right after the last death animation, 5 after
  300 more frames), GAME OVER 210 frames, ranking insertion (50000 "ABC" → 4TH), SRAM bytes written, credit
  screen with 1 and 2 credits, 2P join during the intro (both names concurrently), Home options.
- Window split: top rows / bottom rows show the window, stars visible in between, no line errors at
  the row 1/2 and 24/25 boundaries in Genesis Plus GX.
- Front-end frames finish within VBlank work (`prof_line` ≈ 10 lines on scenes); the HUD itself costs
  one H-int per frame in game (28 in the general mode) plus the panel diff.

Front end 2 (boot / COIN / Home screens, menus, controls, SRAM v2), driven through the libretro pad
(6-button device) rather than `dbg_pad_override`, screenshots in `reports/frontend2/`:

- COIN screen: INSERT COIN shown 24 frames, hidden 12 (sampled every frame over 110 frames:
  runs 24/12/24/12); `cmp_title_vs_coin.png` against the MAME title (f300). Code: 9 presses with a
  wrong start stay on the screen, the 8-press code then opens the DIP screen; B → boot screen.
  Start → CREDIT (credits 1), C → 2, Start → INTRO (credits 1); 896 frames idle → WARNING; Start in
  the WARNING / demo → CREDIT (the demo is ended before the Earth scene is set up).
- Credit screen identical in text and layout to MAME f400 after one coin (`cmp_credit.png`).
- Home: START GAME → INTRO with credits 3 − 1; three continues allowed exactly while credits last
  (2 → 1 → 0), then GAME OVER and back to the Home screen.
- SRAM power cycle: settings changed in OPTIONS/CONTROLS (HARD, CREDITS 5, AUTOFIRE LEFT) and the
  DIP screen, the core's save RAM (`retro_get_memory_data(RETRO_MEMORY_SAVE_RAM)`, magic `SAR2` at
  the odd bytes) copied into a freshly loaded core before its first frame: the boot screen opens on
  the last mode and every value is restored; the game then runs at HARD.
- Autofire / LOCK / X Y Z: see Controls. No dropped frame on any menu or with autofire held
  (`frame_counter` checked every frame).
- `tools/qa_soak.py`: the 2P join presses Start twice (coin, then start).

## Deviations / limits

- 40 columns: the HUD is a native layout (above); boss bars are right-aligned to column 39 (the
  arcade's right edge is off the Genesis screen).
- Window rows replace plane A on the whole row: stars are hidden on rows that hold text (e.g. the
  logo rows on the title).
- Demo variant 2 plays over real terrain, so plane B's VRAM is in use and the logo is not shown
  (variant 1 shows it). Demo 1's item carriers (`$4DCF`, `$513D`…) are not in any stage spawn
  table: they appear only if the enemies module provides `enemy_spawn_record(cmd, target)`.
- The intro's slot-3 task `$34FA` is not reproduced (not analysed in the RE notes).
- No name entry after GAME OVER: the arcade's ranking takes the NAMING name (`$1B73`).
- Port additions, not in the arcade: the boot / Home / menu screens, "MD", the COIN screen (built from
  arcade parts, see Flow), the EASY/HARD presets, NONE bonus, Home credits/continue modes, remapping,
  autofire, X/Y/Z functions, sound test, settings in SRAM. Arcade mode: Start inserts a coin only
  when there is no credit, so a start from zero credits takes two presses (coin, start).
- The DIP screen has no CONTROLS entry: the Home CONTROLS settings apply in both modes.
- `video.c` / `bg.c` write scroll registers directly from the main loop (`VDP_setHorizontalScroll`,
  `VDP_setVerticalScroll`). If an H-int writes register `$12` between such an address write and its
  data write, that one scroll value is lost for a frame. Their `...VSync` variants (applied in
  VBlank) would remove that race.
