# Side Arms MD — native Genesis port (SGDK)

A native Sega Mega Drive/Genesis version of Capcom's **Side Arms – Hyper Dyne** (arcade, 1986), written from scratch for the Genesis with SGDK 2.12. It does not emulate or transliterate the arcade program. The original is the specification: its behaviour was reverse-engineered (`docs/re/`) and is re-implemented in native C, with arcade addresses cited in comments. See [docs/architecture.md](docs/architecture.md).

**Source-only.** This repository contains no ROM data. Graphics, palettes and level maps are converted from your own MAME `sidearms` ROM set at build time.

## Build

Requirements: SGDK at `~/mars/m68k-elf` (override with `GDK=`), Java, Python 3, MAME 0.288 (only needed for the reverse-engineering oracles).

1. Put the 27 files of the MAME `sidearms` (World) set in `rom/`, or set `SIDEARMS_SOURCE=/path`. `tools/rom_manifest.json` checks every file by SHA-256.
2. `make` builds `out/release/rom.bin`. `make run` opens it in RetroArch with Genesis Plus GX.

## Layout

| path | contents |
|---|---|
| `src/`, `inc/` | native game code |
| `src/gen/`, `inc/gen/`, `res/generated/` | generated from the ROM set (ignored) |
| `tools/arcade_source.py` | hash-checked ROM access and graphics decoders (MAME layouts) |
| `tools/build_assets.py` | ROM → Genesis tiles, palettes, maps, sprite patterns |
| `tools/oracle.py` + `capture.lua` | run the original in MAME headlessly and record video state per frame |
| `tools/run_rom.py` | headless Genesis Plus GX runner for the built cartridge |
| `tools/build_levels.py` | native level timelines + terrain map from the extracted data |
| `tools/agent_build.sh NAME` | private snapshot build (parallel work) |
| `tools/qa_soak.py` | QA bot: every section 1P/2P, dropped frames, hangs, contact sheets (`docs/qa.md`) |
| `tools/check` | rebuild all game sources, fail on any compiler warning |
| `docs/re/` | reverse-engineering notes (hardware, flow/player, levels, objects, sound) |

## Video architecture

| arcade | Genesis |
|---|---|
| 384×224 screen | 320×224 (H40); the view sits centred in the arcade's, offset 32 px |
| BG: 4096×4096 world of 32×32 tiles straight from ROM, 32 palettes | plane B (high priority), a 64×32 ring buffer fed by a 56-slot cache of 32×32 metatiles (≤53 needed on screen); per-stage zones quantized to PAL0/PAL1 |
| starfield generator (`b_11j`) | plane A (low priority): the generator's 512×256 period precomputed (140 tiles), hardware-scrolled |
| 128 16×16 sprites, 16 palettes | SAT from a native display list. Patterns are pre-converted at build time into PAL2/PAL3 and streamed into 16×16 and 32×32 VRAM caches. |
| 64×32 text layer, 2bpp | native 40-column HUD on the window plane (an H-interrupt splits it into top and bottom rows) |
| static 1024-colour palette (ROM `B3:$8A37`) | quantized per zone; the colour fit is checked visually |

Checks so far: BG scroll alignment against an arcade snapshot is pixel-exact (offset 0,0). Replayed arcade sprite RAM lands at identical positions.

## Playing

The boot screen offers two modes:

- **ARCADE**: the arcade's flow. The INSERT COIN screen blinks INSERT COIN and the credit count;
  **Start inserts a coin** (C too), then Start starts; with credits, Start lets player 2 join or
  continue. Up Up Down Down Left Right Left Right on that screen plays a chime and opens the
  **DIP switches** (difficulty 1-8, lives 3/5, bonus life, continue, demo sounds, COLOR; BACK or B
  returns to the boot screen).
- **HOME**: the Home screen (SIDE ARMS + MD): START GAME (3 credits by default), OPTIONS, BACK.
  OPTIONS: difficulty (EASY, the arcade's levels 1-8, HARD), lives 1-7, bonus life (the four arcade
  tables or none), continue (off / limited by credits / unlimited), credits 1-9, COLOR,
  CONTROLS, SOUND TEST.

Controls (default): **A** fire left, **B** fire right, **C** next weapon, **Start** start / coin.
CONTROLS remaps the three actions to A/B/C (or X/Y/Z on a 6-button pad), sets X/Y/Z (6-button) to
previous / next / a given weapon or LOCK FIRE (fires the way the ship faces without turning; default
X = previous, Y = next, Z = lock), and switches autofire on per fire button (one shot every 4 frames,
the arcade AUTO weapon's rate). Menus: B goes back. A+B+C+Start returns to the boot screen.

The ranking and all settings are kept in battery SRAM.

## Colour

The arcade palette (4 bits per channel) is converted to the Genesis's 3 bits per channel. Each background zone gets two fitted palettes; sprite patterns each choose the better of two shared sprite palettes. The DIP-switch / options screens have a **COLOR** setting:

- **ARCADE**: the converted arcade colours.
- **VIVID** (default): every palette passes through a build-time table that raises saturation (×1.4) and brightness (×1.15), keeping greys neutral. It compensates for the Genesis's coarser colour steps and the darker output of common emulators.
