# Side Arms MD — native Genesis port (SGDK)

**v2.1** restores the Normal first-level background and Vivid colors from v1.2,
raises PC Engine music volume, and corrects instrument-change key-on ordering.
It also fixes BC rapid fire, wheel-boss gun placement and stale animation tiles,
and restores the wheel's original lightning animation when it loses a health bar.
BC level 1 now uses the original PCE BC background tiles and layout. Standard
is closest to the PCE colors; Vivid boosts them while preserving shade detail.

It includes 1–4-player Home modes, Before Christ, the PC Engine HuCard
soundtrack, Start pause, and the hidden Developer menu described below.
Release ROM: `dist/Side Arms MD v2.1.bin`.

The user accepted the existing frame-skipping performance on October 11, 2026.
The preceding full-campaign build (`5f6aa68a`) reached a minimum rolling five-second
rate of 50.93 gameplay updates/sec in protected four-player BC testing. That is
simulation throughput, not 50 newly displayed frames/sec. The v2.0 release adds
pause and developer-menu validation; historical campaign measurements retain their
original ROM hashes in [expansion acceptance](docs/expansion-acceptance.md).
Testing is emulator-only.


Current build and acceptance: [expansion verification](docs/expansion-acceptance.md).
Engine architecture: [BC shared-engine verification](docs/bc-engine-integration-verification.md).
Build/additions inventory: [October 7 status](docs/2026-10-07-additions-status.md).

A native Sega Mega Drive/Genesis version of Capcom's **Side Arms – Hyper Dyne** (arcade, 1986), written from scratch for the Genesis with SGDK 2.12. It does not emulate or transliterate the arcade program. The original is the specification: its behaviour was reverse-engineered (`docs/re/`) and is re-implemented in native C, with arcade addresses cited in comments. See [docs/architecture.md](docs/architecture.md).

**Source-only.** This repository contains no ROM data. Graphics, palettes and level maps are converted from your own MAME `sidearms` ROM set at build time.

## Build

Requirements: SGDK at `~/mars/m68k-elf` (override with `GDK=`), Java, Python 3, MAME 0.288 (only needed for the reverse-engineering oracles).

1. Put the 27 files of the MAME `sidearms` (World) set in `rom/`, or set `SIDEARMS_SOURCE=/path`. `tools/rom_manifest.json` checks every file by SHA-256.
2. `make` builds `out/release/rom.bin`. `make run` opens it in RetroArch with Genesis Plus GX.

### Before Christ build inputs

The current cartridge also links Before Christ. In addition to the arcade ROM set,
it requires the local, user-supplied CD reference captures below. These are ignored
by Git and are not included in a source checkout:

- `.local/pce-reference/play-task-round1/code-002160.bin` and `play-task.bin`.
- `.local/pce-reference/round02-reference/` through `round10-reference/`, each
  containing `code-002160.bin` and `f002400-ram.bin`.
- `.local/pce-reference/round10-ending-presentation/code-007080.bin`.
- The caption generator's Hiragino Kaku Gothic W6 font at its macOS system path.

`make check-bc-inputs` lists missing inputs. Capture tooling is described in
`tools/pce_oracle.py`; the generators validate the reference data before packaging
it. `make` now regenerates all BC round data, boss/background artwork, ending data,
and caption tiles after the Normal assets. `make bc-data` runs this same ordered
asset pipeline. Private builds use it too, with the local reference directory
linked into the snapshot. A PC Engine HuCard soundtrack source is separate from
these CD captures. Put the USA cartridge at
`.local/pce-hucard/SideArms - Hyper Dyne (USA).pce`, or set `HUCARD_ROM=/path/file.pce`
when building. The converter verifies its SHA-256. Native HuCard playback and a
saved Home soundtrack selector are implemented; instrument conversion still
needs polish. See [HuCard soundtrack status](docs/hucard-soundtrack.md).

The project build adapts SGDK's boot entry with `tools/cart_boot.mk`: flash-cart launch
and console reset both initialize RAM and perform the TMSS check. Use the project
Makefile so this startup fix and the cartridge-header validation are included.

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
| `tools/build_parallax.py`, `tools/parallax_split.py`, `tools/parallax_check.py` | Home parallax tables, map analysis, soak/screenshots (`docs/parallax.md`) |
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
- **HOME**: the Home screen (SIDE ARMS + MD): NORMAL (3 credits by default), BOSS RUSH, OPTIONS, BACK.
  Selecting a game opens a 1/2/3/4-player dialog; B cancels and A/C/Start confirms.
  Every selected player starts together. BEFORE CHRIST uses the same player
  dialog and has its ten-round campaign, continues, and ending implemented;
  its performance, engine integration, and artwork remain under development.
  OPTIONS: difficulty (EASY, the arcade's levels 1-8, HARD), lives 1-7, bonus life (the four arcade
  tables or none), continue (off / limited by credits / unlimited), credits 1-9, COLOR, PARALLAX, PLAYERS, MUSIC (ARCADE / PC ENGINE),
  CONTROLS, SOUND TEST. Music applies to Normal, Before Christ and Boss Rush;
  existing saves default to Arcade. Sound Test has its own independent Source choice.

**1–4 players (Home, displayed-rate acceptance pending)**: the launch dialog selects the player count
and saves it in SRAM; OPTIONS > PLAYERS changes its default. One-player sessions use P1 only.
Scaling follows the selected
setting: 3P has 150% of the 2P enemy population and boss energy; 4P has 225%. Wave order,
enemy types and boss phases stay the same. Fractional enemies carry forward; linked formations
are added whole, carrying their fractional remainder to later formations of the same size.
Pickups and stage shutters are not multiplied. Extra copies enter with staggered timing.
P3 recolors P1's body, and P4 recolors P2's; the compact HUD shows all players. Merging pairs
P1/P2 or P3/P4, with one merged robot at a time, leaves the other players independent.

Connect a Sega Team Player before boot: on port 1, its A/B/C/D controllers are P1/P2/P3/P4;
on port 2, the ordinary port-1 pad is P1 and adapter A/B/C are P2/P3/P4. EA 4-Way Play uses
its four pads in order. Hardware adapter polling has not yet been verified on a physical console.
Boss Rush uses the same player count and boss-energy scaling. The shared catch-up
scheduler now covers Rush too: protected3P/4P HuCard runs on bc389f61 finish all
12 bosses at a minimum58.32 simulation updates/sec, with matching compared
states and no sprite drops or audio underruns. These use protected players,
not unassisted combat.

Current acceptance requires at least 50 simulation updates/sec, with frame skipping
allowed; PAL uses its nominal 50 Hz cadence. The expansion is **not release-complete**.
Normal now catches up simulation in 3P/4P while preserving input polling and
flushing pending graphics before another update. Build 965be78d passes all 40
protected section/player/soundtrack fixtures: minimum 55.13 updates/sec, zero
HuCard audio underruns, and matching compared gameplay states. Presentation
averages 30.44–59.92 pictures/sec in these fixtures. Two crowded cases retain
brief sprite-upload misses; this is not full-campaign or clipping-free acceptance.
See [multiplayer QA](docs/multiplayer-qa.md) and
[current acceptance evidence](docs/expansion-acceptance.md).

Before Christ now shares the regular engine's frame/session control, player
storage, simulation scheduler, enemy arena, and projectile index/query code.
It retains BC-specific movement, weapons, stage events and enemy behavior; it
is not an art-only reskin. See [engine ownership](docs/bc-shared-engine.md).

BC now catches up simulation while skipping rendering in 3P/4P. The preceding
03a94363 build passes all ten protected 4P NTSC round fixtures over 6,000 video
frames each; its lowest five-second rate is 50.34 updates/sec. Presentation is
separate and can fall far below 50 distinct pictures/sec. Reproduce a round with
`.venv/bin/python tools/qa_bc_frameskip_timing.py --rom out/release/rom.bin --round 7 --players 4 --frames 6000 --output .local/bc-timing-check`.
These are bounded emulator fixtures, not unassisted full-campaign acceptance.

For controlled Normal optimization comparisons, use
`.venv/bin/python tools/qa_normal_fixed_updates.py --players 3 --section 8 --updates 1000 --output .local/normal-fixed-check`.
This applies the bot at input-update boundaries and records per-update state
hashes. Compare those hashes before attributing a timing difference to an
optimization; the older video-frame-driven stress bot can follow a different
trajectory after a timing change. Add `--render-trace` to also hash sprite
order and resident pixels. `tools/qa_normal_timing_matrix.py --output .local/normal-matrix`
runs all 40 player-count/section combinations; `--baseline <previous-output>`
compares their state hashes and frame counts. Neither test establishes full-game speed.

Normal runs the original wave timeline. The authored organic-map preview remains development
source and no longer replaces ordinary gameplay. Regression command:
`.venv/bin/python tools/qa_multiplayer.py --players 4` (also run with 1, 2 and 3).

**PARALLAX** (Home, a port mode, ON by default): depth scrolling in every section — the starfield
split into four depth layers (per row, or per column on the long vertical legs), section 5's cave
wall as a slower far layer. Gameplay is unchanged; Arcade mode keeps the arcade view. Details: [docs/parallax.md](docs/parallax.md).

**BOSS RUSH** (Home, a port mode): the game's 12 bosses in the arcade order — the sprite bosses of
sections 1, 3, 5, 7 (x2), 8 (x2), 9, the three wheels and the final boss — each in its own arena
(the arcade's boss halt of that section, normal enemies off, the arcade's boss behaviour). No lives:
an 8-segment energy bar under 1UP / 2UP; a hit costs one segment (2 s blinking invulnerability,
weapons kept), a terrain crush too (the ship re-enters at its spawn point). +2 segments after each
boss. Start loadout: BIT, S.G., M.B.L., 3WAY at level 1, AUTO, speed 2 (the boss POW drops still
work). Player 2 joins with Start. The best run (bosses defeated, then fight time) is saved in SRAM
and shown on the Home screen. Details: [docs/frontend.md](docs/frontend.md#boss-rush).

Controls (default): **A** fire left, **B** fire right, **C** next weapon, **Start** pauses/resumes an active Home game (Normal, BC, or Boss Rush). For inactive players it still joins/continues; in Arcade it retains start / coin. Music continues during pause.
CONTROLS remaps the three actions to A/B/C (or X/Y/Z on a 6-button pad), sets X/Y/Z (6-button) to
previous / next / a given weapon or LOCK FIRE (fires the way the ship faces without turning; default
X = previous, Y = next, Z = lock), and switches autofire on per fire button (one shot every 4 frames,
the arcade AUTO weapon's rate). Menus: B goes back. A+B+C+Start returns to the boot screen.

The ranking, all settings and the Boss Rush record are kept in battery SRAM.

## Colour

The arcade palette (4 bits per channel) is converted to the Genesis's 3 bits per channel. Each background zone gets two fitted palettes; sprite patterns each choose the better of two shared sprite palettes. The DIP-switch / options screens have a **COLOR** setting:

- **ARCADE**: the converted arcade colours.
- **VIVID** (default): every palette passes through a build-time table that raises saturation (×1.4) and brightness (×1.15), keeping greys neutral. It compensates for the Genesis's coarser colour steps and the darker output of common emulators.

Before Christ reuses matching Genesis artwork, including in 4-player mode.
Background materials retain their original Genesis palettes. Reviewed sprites
keep their original colors or use shade-preserving BC recolors; BC-specific
shapes are used where no matching Genesis sprite exists. VIVID applies to both
modes. All colors remain within the Genesis's four 16-entry palette banks,
and recolored patterns are generated at build time. Background/composite-art
matching and full-speed 3- and 4-player gameplay remain under review; see
[BC art decisions](docs/bc-art-review-decisions.md).

## Boot intros (local only)

The SEGA logo (with the "SEGA" chant) and the CAPCOM logo (with its FM jingle) play at boot when the intro kits are present in `src/intro/`. Those kits contain data from other games, so the folder is gitignored and never committed. Run `tools/fetch_intros.sh` to copy them from the sibling ports (`_capcom/son son/sonson_native`, `_capcom/_capcom logo intro`). Without them the game builds and boots straight to its menu.

### v2.0 developer menu

On the Home screen, enter **Up, Down, Up, Down, Left, Right, Left, Right**.
The Developer entry appears on Home and remains available until a hardware reset.
Select it with Up/Down and press A, C or Start to open it.
Choose Normal or Before Christ, round 1–10, 1–4 players, invincibility and infinite
lives, then Launch. Sound Test is also available. These are practice sessions:
normal rankings are disabled, and returning Home or using A+B+C+Start clears the
practice effects. Ordinary Home launches retain their normal rules. The timer
and currency cheats from Black Tiger do not apply to Side Arms.

Press Start during either boot logo to skip both logos. Home uses two columns; Up/Down cycles entries through both columns. Options uses Left/Right to change values. Developer occupies the reserved lower-right slot after unlocking.
