# QA / integration pass

What was tested, how, the numbers, the bugs found (with root causes) and what remains. All runs use
the headless Genesis Plus GX runner (`tools/run_rom.py`) and, for the arcade, MAME 0.288 through the
existing probes. Reproduce the soak with `tools/qa_soak.py` (below).

## 1. AUTO `$11` (star, 3-way rapid fire)

**Finding: the weapon code was right; the "fires nothing" observation came from the lockstep
harness.** AUTO `$11` fires a volley only when the loop counter `$E003 & 7 == 0` (B2:`$8C85`) while
exactly one fire button is held. `tools/enemy_trace.py --fire` drives button 2 four frames on, four
off, so whether a volley ever fires depends only on the phase between that pattern and the
counter:

- the input pattern was placed with a fixed `--align 1042`, while the measured stage-start offset
  is 1045 frames: the port's autofire ran 2 frames ahead of the arcade's;
- the port's `frame` (which plays `$E003`) was never synchronised to the arcade's counter
  (free-running since boot, `$E003` = arcade frame − 20 in every trace).

Evidence: with the port started 0-7 frames later (`frame & 7` phases), 4 phases fire 24-25 volleys
in 200 frames, the other 4 fire 1-2 — "always or never". The player-module probe `weap2`
(`reports/oracle/weap2`, `$F215 = $11` poked, `frame` synchronised) already matched shot for shot.

Fixes (tool only): `run_port()` now syncs `frame` to `$E003` and the input frame to the matched
arcade frame at the first camera step; the stale `Player` offsets (`P_INVULN` wrote `lives` since
`Player.vertical` was added; weapon/level/speed bytes off by one) are corrected; `enemy_trace.lua`
now also traces shot slot 8 (`$F3E0`, the third shot of an AUTO `$11` volley). The fire trace was
re-recorded (6000 frames).

Result, stage 1 autofire, 4953 compared frames: camera identical; 145 big / 65 small / 6 pickups with
identical paths (was 70 identical big before the sync); the star is taken on the same frame (4356);
**all 358 player shots of the AUTO `$11` / `$10` period (frames 4356-6000) spawn in the same slot on
the same frame and follow identical trajectories** (2 end earlier in the arcade, on enemies).

## 2. Scroll crush and vertical spawn

- Crush (`CRUSH_X = -16`, arcade sprite x `$50`, B2:`$846F`): the death frame already matched, but
  the port's dying body sat at x 79 vs the arcade's 80. B2:`$8495` puts back the x of the last drawn
  composite (sprite `+$40`) before calling `$222C`; `player_move()` now restores `old_x` on a crush.
  Stage 2 (`enemy_trace --stage 2`): death at arcade frame 6707 at (y 120, x 80), respawn 6748 — both
  identical; the whole 7443-frame trace is now identical (160 big / 166 small / 8 pickups; before,
  the lockstep ended at the crush, 5160 frames).
- Vertical spawn (`level.vertical`, `$E040` via B0:`$809C/$80B3`): stage 3 (`--stage 3`) deaths at
  3059 / 6195 (crushed at y 31) and respawns at 3100 / 6236 at sprite (y 0, x `$C0`) — frame- and
  position-identical to MAME; section 6 respawns at (0, 192) as in its arcade trace.

## 3. Frame rate

### Measurement

`tools/qa_soak.py` plays each section from its start (`dbg_warp`) to the next section with an
invincible autofire bot (AUTO `$11`, re-armed after a crush; lives topped up; slow vertical sweep;
after 1500 frames of a boss fight `boss_dbg_autohit` makes every boss hit test also count one P1
shot, so the real damage/score/death paths end the fight). A dropped frame = a runner frame in which
`frame_counter` did not advance. `prof_seg[4]` (main.c) gives, for the loop that overran, the
scanlines since VBlank at loop start / after update / after draw / after `video_frame`.

Same bot, first 6000 frames of every section (normal play, mostly before the boss), before (build at
the start of this pass) and after:

| section | 1P before | 1P after | 2P before | 2P after |
|---|---|---|---|---|
| 1 | 1.52 % | 0.00 % | 11.97 % | 0.13 % |
| 2 | 10.85 % | 0.07 % | 12.65 % | 0.88 % |
| 3 | 1.90 % | 0.05 % | 8.82 % | 0.22 % |
| 4 | 5.18 % | 0.07 % | 17.50 % | 0.67 % |
| 5 | 1.20 % | 0.07 % | 3.12 % | 0.10 % |
| 6 | 4.52 % | 0.17 % | 14.20 % | 1.00 % |
| 7 | 2.03 % | 0.07 % | 12.28 % | 2.35 % |
| 8 | 2.32 % | 0.10 % | 8.37 % | 2.87 % |
| 9 | 13.82 % | 0.57 % | 22.63 % | 2.68 % |
| 10 | 0.08 % | 0.14 % | 3.43 % | 0.78 % |

Whole sections including the bosses (`reports/qa/soak_1p.txt`, `soak_2p.txt`; every section reached
the next one, section 10 the ending and the title):

| section | frames 1P | dropped 1P | frames 2P | dropped 2P |
|---|---|---|---|---|
| 1 | 8038 | 1 (0.01 %) | 7827 | 16 (0.20 %) |
| 2 | 9653 | 10 (0.10 %) | 9989 | 191 (1.91 %) |
| 3 | 9430 | 15 (0.16 %) | 9396 | 57 (0.61 %) |
| 4 | 17228 | 11 (0.06 %) | 17605 | 206 (1.17 %) |
| 5 | 11184 | 7 (0.06 %) | 11165 | 37 (0.33 %) |
| 6 | 6666 | 10 (0.15 %) | 6714 | 60 (0.89 %) |
| 7 | 12708 | 13 (0.10 %) | 12723 | 196 (1.54 %) |
| 8 | 12523 | 13 (0.10 %) | 12903 | 367 (2.84 %) |
| 9 | 9189 | 118 (1.28 %) | 9137 | 267 (2.92 %) |
| 10 | 4886 | 7 (0.14 %) | 4746 | 37 (0.78 %) |

In 1P, sections 1-8 and 10 drop frames almost only at camera jumps: the warp/section start (2-3
frames: the first frame reloads the view and the following one flushes its DMA), each in-section
teleport and each wheel death (2 frames each: e.g. section 3 at tick 320, section 9 at 448 and
768), plus single frames where a sprite boss appears or dies (update 230-260 lines: boss setup,
enemy wipe, POW drop). Normal 1P play runs at 60 fps except section 9's sprite-boss fight and the
section 8/9 combined-robot waves (below).

### Causes found and fixed

| cause | evidence | fix |
|---|---|---|
| 32x32 sprite uploads: 8 `DMA_queueDmaFast` (~800 cycles each) + 4 binary searches of a 2297-entry bank per upload; ~15-20 scanlines per new 2x2 frame, several a frame in waves (enemy anim/explosion frames) | V-counter timing of `spr_32`: +15-20 lines per upload; DMA queue call 1.75 lines measured | build: `spr_big`, every 2x2-aligned composite pre-interleaved in sprite tile order (714 blocks, 357 KB) → one 512-byte DMA; `spr_bank_index` / `spr_big_index` direct tables (no search) |
| sprite cache lookup: 2-way hash where a miss also overwrote the hash of a resident key (re-uploads), ~2 lines per hit | profile | per-code 2-way index, SAT attribute kept per slot, SAT entry written directly (sprites.c rewritten; same VRAM layout, A/B screenshots identical) |
| 109 (code, colour) patterns not in the bank went through the runtime remap (2.5 k cycles per cell) | `spr_dbg_remap` ring in the soak | `qa_soak.py --collect` adds them to `tools/sprite_pairs.json` (pages expanded at build time) |
| H-interrupt every 8 lines for the window split: ~350 cycles × 28 = ~8 % of the 68000 | 20000-cycle `dbra` loop: 46 lines with interrupts, 42 without | in-game masks (top block + bottom block) use 2 register writes: VBlank sets the top block, one H-int switches to the bottom block (frontend.md) |
| score digits by 32-bit `/` and `%` (libgcc, ~1000 cycles each, 16 per score) | `game_panel` 25-90 lines on kill frames | subtraction-based digits; cached digit / speed-meter glyph entries; window-row mask kept incrementally |
| BG strip load (8 cells, ~40 lines) on every 32-px boundary | periodic 65-frame slow loops in horizontal sections | look-ahead column loaded 2 cells a frame before it enters the view (bg.c); `cell_words` unrolled per flip case |
| BG reload at teleports | 340-400 lines | new cells acquired before the old ones are released (no needless re-upload), no plane clear, hoisted map rows (~10 % less); still 2 frames, within the brief |
| boss bank misses searched every frame | — | negative cache in `bs_draw` / `bc_get` |

The dropped frames that remain are heavy scenes, not spikes: in 2P with two AUTO `$11` players (18
shots) and in the combined-robot mode (the ring adds 8 shots and big objects are tested every
frame, `$E014`) the update takes 150-210 lines (enemy objects: motion, terrain probe and shot
tests ~2-4 lines each) and drawing 100-150 lines (~1 line per sprite). The original arcade slows
down in the same places (levels.md: sections 2 and 5). Next steps if needed: cheaper enemy
collision (per-shot interval tests, or the shot box sorted by y), a cheaper `hud_panel` diff,
splitting the camera-jump reload over two frames behind a blank plane.

## 4. Score credit

Kills by a shot were credited to the shooter. B0:`$2516-$2548` (small), `$293A-$296C` (big) and
`$2D1D-$2D43` (bosses) credit the shot's owner unless that player has no lives left (`+$0B` = 0),
then the other player — the case of the combined robot's ring, which flies in the partner's shot
slots. `player_credit()` (player.c) implements it for enemies and bosses. Found with it:

- **enemy collision skipped the shots of a `PL_OFF` player**, i.e. all ring shots of a robot whose
  partner is hidden or out of play never hit anything (the arcade tests only the shot state,
  `$2525`). Fixed in `collect_shots()`.
- the extra-life item went to the "last scorer"; `$2747` credits `$E0A2`, which the contact test
  sets to the touching player (`$2568/$2573`): it now goes to the collector.

## 5. Soak

1P and 2P (P2 joins with pad 2 Start through NAMING), every section from start to the boss kill and
the next section, section 10 to the ending, staff roll and title: no hang (frame_counter never
froze), no stuck state, `spr_dbg_dropped` = 0 (no sprite lost to the 80-entry SAT or to a pattern
that was not resident), no runtime remap left. Contact sheets: `reports/qa/section<N>_<1|2>p.png`
(16 frames each, looked at). A/B screenshots against the pre-QA build, keyed by camera position,
enemies muted and player hidden (BG + HUD + palettes), are identical in all 10 sections except
where the old build was wrong (below).

Bugs found:

- **VRAM corruption: DMA sources straddling a 128 KB boundary.** Generated blobs were only
  word-aligned, so 2 sprite patterns, 5 BG metatiles (zones 1, 8, 12, 16, 23) and one boss 32x32
  block crossed a 128 KB ROM boundary, which a VDP DMA cannot (it wraps inside
  the bank): garbage tiles, seen in section 9 (A/B, camera 3224,3328). All DMA'd blobs are now
  512-byte aligned (`data.s`, `frontend.s`, `boss_data.c`).
- **Final boss tail motion**: `final_motion` (first step, count) pairs were `u8` while the step table
  has 272 entries: indices 256-258 wrapped to 0-2, so the tail used the head's steps for headings
  26-31. Now `u16` (this was the one compiler warning of the build).
- `tools/enemy_trace.py` stale offsets (above); `qa_soak.py`'s own 2P join needed `pressed` edges
  kept until a loop that started after the write has run (a long frame spans several runner frames).

## 6. Build

`make clean && make` from a tree without any generated file now works: the Makefile runs the ROM
extractors first (`extract_levels`, `extract_spawns`, `extract_player`, `extract_sound` →
`res/generated/*.json`, re-run only when missing or changed), then `build_assets.py` (which runs
build_player, build_levels, build_frontend, build_enemies, build_bosses) and `build_sound.py`. Verified
in a fresh copy: the ROM is byte-identical to the working tree's. `tools/check` rebuilds every game
source and fails on any compiler warning in `src/` / `inc/`: clean (the `rom_header.c` SGDK template
warnings are silenced in that file; the generated `boss_data.c` overflow is fixed). ROM size 2.4 MB
(sprite index tables and 32x32 blocks).

## Remaining issues

- 2P / combined-robot heavy waves drop 1-3 % (sections 2, 4, 7-9), 1P section 9's boss fight ~1 %.
- Camera jumps (warps, section starts, teleports, wheel deaths) cost 2 frames (3 for a warp to a
  section start).
- `hud_panel`'s per-frame diff still costs a few lines; the sampling profile suggests more than the
  call counts justify (H-int sampling aliases with the raster), not pursued.
- The window/H-int register writes and the scroll registers share the VDP control port with the main
  loop (frontend.md); unchanged, now with 1 H-int per frame instead of 28.
