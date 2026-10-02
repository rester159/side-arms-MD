# Home-mode parallax

A port feature, not in the arcade: in **Home** mode with **OPTIONS > PARALLAX ON** (the default),
the stage view gets depth scrolling. Arcade mode, Home with PARALLAX OFF, menus and scenes use the
plain arcade view (plane scroll, one starfield speed): `par_dbg_mode` stays 0 there (checked in
sections 1, 3, 8, 10).

| file | role |
|---|---|
| `src/parallax.c`, `inc/parallax.h` | runtime: scroll tables, plane A content, scroll-mode switches |
| `src/video.c` | `video_set_parallax()`; runs `bg_update()` + `par_frame()` while BG and stars are on |
| `src/bg.c` | Home zone variants (cut texture cells), BG bands streamed at their own camera |
| `tools/build_parallax.py` | tables → `src/gen/parallax_data.c`, `inc/gen/parallax_data.h` |
| `tools/parallax_split.py` | far-layer / band analysis of the arcade map (used by `build_assets.py`) |
| `tools/parallax_check.py` | QA: frame-drop soak through the HOME screen, screenshots per section |

Everything is derived from the ROM set at build time (star brightness, level legs, BG map);
nothing is hand-drawn.

## Layers

**Stars, rows** (default, plane A). The starfield's 32 rows of 8 lines are spread over four depth
layers by brightness (dim = far): speeds 2, 4, 8, 12 /16 of the camera. (The arcade has no
parallax: its one star layer simply advances at half the BG speed, docs/re/levels.md §3, which
Arcade mode keeps.) Each screen line takes the H offset of the plane row it shows, so a star keeps its
layer while the camera also moves vertically (vertical star speed: the arcade's 8/16).

**Stars, columns** (plane A, `par_col_legs`): on long vertical legs that start and end at a camera
cut (sections 3 and 6), V-scroll per 16-px column, each column at a layer's speed.

**Far layer** (`par_far`): section 5's cave wall is a periodic texture behind the rock. The Home
variant of the zone has the texture pixels cut out of its metatiles and plane A shows the texture
(tiles 64-127) at half the camera speed instead of the stars. The offset is chosen so that cut and
uncut cells always join seamlessly; cells under the HUD rows are never cut.

**Bands** (`par_bands`, plane B): rows of distant scenery without terrain on a horizontal leg,
streamed by `bg.c` at their own camera x and shown with plane-B line scroll. `parallax_split.py`
checks that the rows have no terrain and that band and world agree pixel for pixel where the band
locks again. **None is active in 1.0:** section 1's Mt Fuji band (row 4, 3/4 speed) looked broken,
and its hills band (rows 2-5, 1/2 speed) never matches the world again before the section 1 -> 2
teleport, so the arcade's seamless cut (the end of section 1 already shows the cliff and the sea
that section 2 starts with) showed the hills turning into the cliff. The machinery stays.

| section | parallax |
|---|---|
| 1 | star rows |
| 2, 4, 7, 8, 9, 10 | star rows |
| 3, 6 | star columns on the long vertical legs, star rows elsewhere |
| 5 | star rows, cave-wall far layer on the cave leg |

**Wheel sockets** (Home zone variants and `WheelInfo.frames_home`): the 8 pod sockets on the rim of
the section 2 and 4 wheel bosses are transparent in the arcade map (the pods are sprites orbiting
over them), so the stars show through them, also in the wreck that stays at the start of section 5
(after section 2 the camera moves away from the wheel). With the stars in depth layers that looked like scrolling inside the boss. Home fills those
pixels with the cell's darkest colour: a pixel is filled only where it lies inside the wheel ellipse
(centre = scroll copy + (319, 128), radii 124 x 96) at every use of its metatile, so a changed
metatile replaces the original and the metatile count is unchanged (the wheel fight pins 44 of the
56 cache slots). It covers the sockets; the remaining see-through pixels inside the ellipse are thin
slivers along the rim. The section-9 wheel sits on opaque background. Arcade mode and PARALLAX OFF
use the original art.

Collision, enemies and bosses use the world, not the screen, and are unchanged; the wheel bosses'
plane-B frame pre-render switches bands off (`fr`). Boss Rush arenas get the same parallax.

## VDP

- H-scroll mode: per 8-line cell (28 entries per plane) when every boundary falls on a cell row
  (horizontal legs: the camera y is 16 mod 32), per line (224 entries) otherwise. Column V-scroll on
  the column legs.
- The H-scroll table moved from `0xF400` to `0x1000` (tiles 128-155): line scroll needs 896 bytes and
  sprite tiles 1953+ live in the old area. Stars use tiles 0-62. This applies in every mode; the
  arcade view only uses the table's first 4 bytes.
- Tables are DMA'd in VBlank (SGDK queue) only when they change; the scroll-mode register is switched
  from the VBlank callback (`par_vblank`) after the matching tables have been delivered.

## Camera cuts

Teleports (section starts, the wheel deaths) are instant cuts in the arcade, often between two
views drawn to look alike (end of section 1 -> start of section 2: 18 of 19 metatiles shared).

- Stars: a layer's position = speed x camera + an offset that absorbs each cut (a camera move of
  more than 16 px in a frame), so the stars keep drifting through a cut as the arcade's do. The
  vertical offset moves in whole 8-line rows (keeps cell H-scroll possible): at most a 4-px nudge.
- Background (all modes, `bg.c`): a cut into another zone used to flush the metatile cache, load
  the new palette first and overwrite tiles still on screen, which showed one garbled frame. Now the
  switch takes two frames: the new tiles go to free slots while the old picture stays on screen
  (its slots held, old scroll and palette), then nametable, palette and scroll switch in one VBlank
  (`set_zone`, `sw_state`). If the cache cannot hold both views, it falls back to the old way.

## Cost

`par_frame()` does nothing when the camera, band and zone are unchanged (50-72% of frames: the
camera moves every other frame or less). When the camera moves (scanlines, 488 68000 cycles each):

| case | lines |
|---|---|
| star rows, cell mode (most horizontal legs) | ~12 (plane A 5, plane B 2, DMA queueing 4) |
| star rows, line mode (vertical legs), when the star row offset changes (every 4th frame) | ~20 |
| star columns | ~9 |

Two fixes went in during tuning: the line-mode table was written by a `fill()` call per row (~40 lines a
frame on vertical legs: section 8's first leg dropped frames that the plain view did not); it is now
written inline from a per-layer value table. Multiplications use `muls.w` (`mul16`): a C 32-bit
multiply is a libgcc call.

## Verification

`tools/parallax_check.py soak` (the `tools/qa_soak.py` bot, game started through the HOME screen),
first 6000 frames of every section, dropped frames:

| | 1P | 2P |
|---|---|---|
| Home, PARALLAX ON | 96 / 58775 (0.16%) | 846 / 58766 (1.44%) |
| Home, PARALLAX OFF | 164 / 58774 (0.28%) | 718 / 58767 (1.22%) |
| Arcade | 136 / 58852 (0.23%) | — |

1P: no difference beyond noise (the remaining drops are the existing spikes of docs/qa.md).
2P: the plain view already drops frames in sections 2, 7, 8, 9 (busy 2P frames run within a few
lines of the 262-line budget); parallax adds about 0.2 points, mostly in section 9 (204 vs 148). Runs
diverge after a dropped frame, so single sections vary by ±50 drops between runs.

Other checks:
- Frame-identical to the first implementation (screen hashes, 900 frames each) in sections 1 and 8;
  section 9 differs from frame 452 only because the old build dropped a frame there.
- Screenshots of every section, ON vs OFF (`reports/parallax/final/`): same playfield, layers
  moving at their speeds; section 5 far layer.
- Boss fights in Home with parallax: sections 2 and 9 (wheel bosses) and 10 (final boss) played
  through to the next section / the ending.
- SRAM: PARALLAX OFF is saved (settings version 3, byte 66), survives a power cycle and then keeps
  the engine off in a Home game; a version-2 save loads with PARALLAX ON and its other settings.

## Open issues

- 2P frame drops (pre-existing, slightly higher with parallax); not tested on real hardware.
- One-line glitches at the HUD's window split (the H-interrupt's register write lands a line early
  or late depending on the instruction being executed) appear on isolated frames, with or without
  parallax; they move between frames when CPU timing changes.
