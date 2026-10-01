# Side Arms MD — native architecture

This is a from-scratch Sega Genesis game, written for the Genesis hardware. It does **not** emulate or transliterate the arcade program, its RAM layout or its task kernel.

- The arcade is the **specification**: behaviour (speeds, timings, patterns, HP, scores, spawn schedule) comes from the reverse-engineering notes in `docs/re/`. Code comments cite the arcade address a rule came from (e.g. `/* arcade B2:$8368 */`), so each behaviour can be checked against the original.
- Arcade **data** (graphics, maps, palettes, spawn schedule, motion tables, sound sequences) is converted at build time into Genesis-native formats (`tools/build_*.py` → `res/generated/*.bin`, `src/gen/*.c`, `inc/gen/*.h`). Nothing ROM-derived is committed, and the runtime never reads arcade-format data at arcade addresses.

## Hardware budget (NTSC, 60 Hz, H40 320×224)

| resource | use |
|---|---|
| plane B | background: 64×32 ring of 32×32 world cells, 56-slot metatile VRAM cache (`bg.c`) |
| plane A | starfield, low priority (`video.c`); Home parallax: star depth layers or a far texture (`parallax.c`, docs/parallax.md) |
| window | HUD text, high priority; split by H-interrupt into top rows (scores) and bottom rows (weapons/speed) (`hud.c`) |
| sprites | all game objects, high priority; patterns pre-converted at build time and streamed by DMA (`sprites.c`) |
| PAL0/1 | background zone palettes (+ star colours), swapped per palette zone |
| PAL2/3 | sprites + HUD colours |
| 68000 | game logic + display list each frame; strict 60 fps target |
| Z80 | native sound driver (YM2612 + PSG) in `src/sound/` |

## Coordinates

- **World pixels**: the arcade's 4096×4096 world map (`reports/world.png`), x right, y down.
- **Camera**: world pixel at the screen's top-left. The arcade's "scroll" value S maps to camera = S + (96, 16), which keeps the 320-px view centred in the arcade's 384-px view.
- Gameplay objects use **screen coordinates** (the player and most enemies are positioned relative to the screen, as in the original). Terrain tests convert with world = camera + screen.
- Fixed point: positions are `s16` pixels, sub-pixel motion uses `s32` 16.16 (`fix32`) where needed.

## Module layout

| module | role |
|---|---|
| `main.c` | init, main loop: input → `game_update()` → `game_draw()` → VBlank |
| `game.c` | top-level state machine (boot, title/attract, ranking, intro, stage, game over) |
| `level.c` | camera timeline: auto-scroll legs, triggers, teleports, halts for bosses (data from `build_levels.py`) |
| `player.c` | Mobilsuit movement, terrain, fire, weapons, death/respawn (one struct per player, 2-player co-op) |
| `shots.c` | player projectiles |
| `enemy*.c` | enemy families, enemy bullets, items/POW (data from `build_enemies.py`) |
| `boss*.c` | bosses |
| `fx.c` | explosions, score popups |
| `hud.c` | window-plane HUD and messages |
| `sprites.c` | display list → SAT, pattern cache |
| `bg.c`, `video.c` | planes, scroll, zones |
| `sound/` | Z80 driver + 68k API `sound_command(id)` (ids follow the arcade command numbers) |
| `input.c` | pads → logical inputs: default A = fire left, B = fire right, C = weapon select, Start = start/coin; remapping, 6-button X/Y/Z, autofire (docs/frontend.md) |

## Rules for contributors

1. Write idiomatic native C for the Genesis. Don't reproduce Z80 control flow, RAM layouts or task structure. Implement the *behaviour* the RE doc describes, with Genesis-friendly data structures (structs, enums, fixed-size pools, tables in ROM).
2. Every behavioural constant or rule cites its arcade source in a comment.
3. Hardware access goes through the engine modules. Gameplay code never touches the VDP directly: it submits sprites (`spr_*`) and HUD text (`hud_*`).
4. Budget: a whole frame of game logic must fit the 68000 at 60 fps with the worst case on screen. Avoid per-frame loops over large tables; precompute at build time.
5. Verification compares observable behaviour with the arcade (MAME oracles in `tools/oracle.py` and the `re_*.lua` probes): positions over time, timings, spawn moments, counts. Use the headless runner `tools/run_rom.py` on the port.
