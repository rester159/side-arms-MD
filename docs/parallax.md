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

## Source-fidelity correction (October 2026)

The far-layer cut mask now removes a pixel only when the repeating texture
reproduces its original source value at the locked position. Shared palette pens
also occur in irregular texture patches and outlines, so palette membership alone
was insufficient. Intersecting the mask across all mirrored uses of each source
metatile preserves one stored variant per metatile. `tools/qa_parallax_cut_fidelity.py`
checks the actual generated variants, all 326 cut cells, and the HUD exclusion.
The correction preserves 16,463 previously replaced source pixels without changing
runtime code or ROM size. The 5,000-update four-player stage-five comparison is
unchanged at 5,005 video frames; it does not establish full speed or the requested
all-level extension.

## October 9 expansion audit

The generic whole-zone 32-pixel texture splitter was evaluated for all 24 Normal
zones. Only the already active section-5 cave layer passed. Other zones would
hide visible stars or lacked a HUD-safe horizontal segment. An independent
pixel-by-pixel route check found that the previously proposed repeated materials
in zones 1, 14, 16 and 19 have no visible material pixels along their camera
routes. This rules out those generic candidates, not bespoke layer designs.
Evidence: `.local/parallax-route-audit/whole-zone-study.json` and
`candidates.json`.

BC uses source collision attributes, not Normal's zone geometry. The new
`tools/audit_bc_parallax.py --output PATH` resolves every linked BC cell and
classifies it using the same attribute selection as `bc_terrain_solid`.
Collision-free/nonempty counts for rounds 1–10 are 58, 41, 16, 8, 25, 61, 44,
44, 42 and 20. These counts include defensive margin fills and are **not**
parallax eligibility: visibility, attached enemies/platforms, joins and streaming
costs remain to be checked. Rounds 8 and 10 provide useful next candidates for
assembly-level inspection. Evidence: `bc-collision-materials.json` beside the
Normal audit, bound to cartridge `f97004d1`.

A far-map setup experiment replaced per-entry modulo with a wrapping column
counter. In a protected four-player Normal section-5 replay it retained all
5,001 state, sprite and full VDP-memory snapshots (including 1,545 far-layer
snapshots), but regressed 5,005 to 5,006 video frames for 5,000 updates. It was
rejected and source/cartridge `f97004d1` restored. Evidence:
`.local/parallax-wrap-current/rejected.json`. `qa_normal_fixed_updates.py` now
supports `--vdp-trace` for VRAM/CRAM/VSRAM comparisons; this does not cover
mid-scanline register timing or certify full speed.

### BC Round 8 separation study

The linked R8 backing is a 64×64 repeat made from cells 0/1/4/5. The complete
224-pixel route strip was decoded across x=512..3135. A whole-character split
can move 474,688 of 587,776 pixels while exactly reconstructing the original
at zero offset, but visibly leaves stationary background fragments around the
cylinders. A pixel-equality split is also rejected: shared dark colors cause
holes in the cylinders, and reused cells yield 85 phase-dependent masks.
Neither prototype is linked into the cartridge.

There is a usable transition interval: cameras x=535..2583 at y=1792. At half
speed, its ending offset is 1,024 pixels (16 complete periods), and the rendered
endpoint exactly rejoins the original image before the irregular right-edge
map cells. This solves only the boundary transition. Explicit foreground masks,
VRAM/storage allocation and native timing remain necessary. Evidence and
rejected previews: `.local/bc-r8-parallax-study/study.json` and `index.html`.

The inspected final-round chamber has a fixed camera and a static face over
rib texture; camera-relative parallax would not move that inspected view.
This is not a proposal to introduce unrelated idle background animation.

A source-tile polygon study protects the larger cylinder regions but still
changes 24,544 original pixels at aligned phase; the contours are provisional
and rejected for production. The repeated backing and foreground use the same
13 RGB3 colors, so color-only masking cannot identify ownership. Evidence:
`.local/bc-r8-parallax-study/source-foreground.png` and
`authored-contours-study.json`. The `f97004d1` test build excludes this work.

### Whole-backdrop experiment

Moving the intact Round 8 background at half speed avoids foreground masking,
but changes the landmark sequence. At stage x=2816, the normal background
camera is 2784; the prototype samples x=1632. Later unique machinery therefore
does not appear at its intended stage position. Collision-free artwork is not
necessarily a disposable repeat. The prototype is rejected on that basis.

Its 1,000-update protected four-player HuCard sample matches every simulation
and workload record. Video frames change from 1,799 to 1,797, while mean scene
ticks increase from 938,973 to 941,226; this is mixed bounded timing evidence,
not a performance improvement claim. The accepted `67846589` cartridge is
restored byte-for-byte. Evidence: `.local/bc-r8-backdrop-depth/rejected.json`;
the prototype remains archived under `candidate/`. Further parallax work needs
separate layers that retain the original landmarks and respect the Home toggle.

### BC Round9 whole-backdrop study

The linked horizontal route strip x512..3135, y2048..2271 appears to repeat
its ribbed machinery every96 pixels. The middle three tile rows contain
irregular machine cells, however. Full-height checks at periods16/32/48/64/
96/128/192 find no useful scrolling corridor. An exhaustive all-phase scan
finds only320-pixel repeating spans at48/96/192 pixels, leaving zero camera
travel for a320-pixel view. Eighty cells also carry floor collision
attributes. A whole-backdrop scroll is therefore rejected: it would move
nonrepeating machinery relative to its stage position, like the earlier R8
problem. This is an offline artifact/geometry result, not a performance result.
Evidence: `.local/bc-r9-parallax-study/period.json` and route previews. Separate
foreground masks would still need art, collision/attachment and native timing
validation; no new parallax is enabled.

### BC Round5 source-aware separation study

Current8d5e4ffc's reused Normal materials permit a more specific mask thanR8:
source palette21 opaque pixels and palette11's blue pens0/8/9/10/11. Over
world rectangle[512,1024,3136,1536],319788 pixels meet that source rule.
A16px texture matches297331;22457 nonperiodic blue pixels remain foreground.
Keeping those residuals reconstructs every original pixel exactly at zero
offset. In inspected previews the residuals include a hatched ceiling strip
and rock-edge details. Moving the backing preserves the rock silhouettes;
complete ownership/attachment review is not claimed.

Canonical8x8 pattern comparison across all linked BC cells estimates100 new
characters,3200 raw pattern bytes, plus at most2336 bytes of cell templates.
This excludes packing/alignment, tables, the far map and runtime code; it is
not a linker or VRAM proof. No runtime change is installed.

The next obstacle is the Window HUD: it replaces planeA on its rows, so a
naive planeB cut would reveal black behind transparent glyph pixels instead
of the moving backing. A safe design must preserve those backgrounds without
foreground loss or extra frame-cost regression. Merely moving the intact
background or silently changing the HUD is not the proposed solution. Native
Home-toggle, phase-transition, storage and3P/4P performance checks remain.
Evidence: `.local/bc-r5-parallax-study/` (`split.json`, `storage.json`,
`status.json`, and animated offline `index.html`).

### Round5 HUD-row protection check on 082f88aa

The linked Round5 reconstruction and source mask are byte-identical to the
earlier study. The repeating texture has two colors and sixteen distinct
columns, so horizontal phase changes are visible. Restoring the original
background in the sixteen Window rows would prevent holes, but attach that
strip to the foreground while the backing below moves independently.

An offline check of ten measured campaign camera positions at all sixteen
relative horizontal phases finds new boundary discontinuities in 30 of 160
cases (up to 42 pixels across the boundary). At most 1,209 background pixels
inside the protected strip differ from the intended moving layer. The
comparison excludes HUD glyphs and is not a runtime or performance test.
This workaround is rejected; no additional BC parallax is installed.
Evidence: `.local/bc-r5-hud-protection-082f88aa/hud-protection.json`,
repeatable `check.py`, and `hud-strip-comparison.png` in the same directory.
Compositing or a different layer arrangement would still need palette,
storage, foreground-priority and native timing validation.

## Cavern color split

Normal zone 10 uses two background palettes across the organic cave boundary
(world x >= 1536, y >= 2048). This preserves the source pink/purple shade ramps
while retaining the existing metatile count and far texture. It applies with
or without Home parallax. tools/build_cavern_palette.py runs after BC donor
conversion, so Before Christ keeps its own material conversion. The generator
rebuilds route masks from levels.json, checks source asset hashes, and produces
the palette constants consumed by src/palette.c. No optimizer or exploratory
.local script is needed to build the assets.

VBlank restores the displayed picture's starting colors only when its raster
split changed them. Queued pictures become current after their DMA completes.
The raster handler writes ten colors in alternate HBlanks within the verified
unused-color interval. cave_dma_busy excludes the whole queued-DMA setup and
transfer; the existing v1.4 flush_guard still protects HUD register changes.
Repeated video frames repeat the color split even when simulation is late.

The verified 4P route takes 10,313 video frames for 10,000 updates, compared
with 10,108 before this shading restoration (about 2% additional duration).
This is a shading-fidelity tradeoff, not a claim of improved frame rate.
The route masks cover normal authored traversal; developer teleports outside
that traversal are not guaranteed to preserve all original colors.
