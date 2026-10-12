# BC artwork review decisions

## Current-ROM verification — October 9

Retained 083b48ac passes refreshed original boss-body/attack-piece checks,
15 boss-shot frames (3,840 source pixels / 60 native flip cases), 20 serpent
poses (20,480 pixels / 80 flip cases), all 22 classified player weapon poses
(5,632 pixels / 176 flip/facing cases), and the five death poses in four-player
rendering. Ordered shading assertions pass with no software drops or remaps
in these fixtures. Reports are in `.local/current-content-083b48ac/`.

The historical notes below about unreviewed 1E0–1E6 mappings are superseded
by the current generated records and weapon checks. Those four poses use
loaded-bank evidence, distinguished from the live projectile captures in
the report; this does not turn them into observed live projectile instances.
These bounded content checks do not certify crowded-scene sprite visibility
or final performance. The current performance requirement is at least
50 updates/s with frame skipping allowed, as recorded in expansion-acceptance.md.


## Current boss requirement — supersedes earlier inferred reuse

The user explicitly requires every BC boss and its attacks to be imported from
the original PCE version. Earlier inferred Genesis boss substitutions, including
rounds 1, 3, 5 and 9, are superseded. The ordinary-sprite review decisions are
unchanged. All nine main boss bodies are now imported from their PCE captures (26 poses
and 239 source pieces). The four composite laser/beam poses are also imported. The ordinary boss projectiles and final serpent now also use original PCE shapes. Full-speed checks remain outstanding. Existing native attack behavior must also retain its PCE
correspondence; matching a body alone is not completion.


## Color preservation

### Player weapon correspondence and horizontal-shot correction

The subsequent build extends the original-shape imports to `1A8`–`1B6` and
`1C2`–`1C6`, replacing incorrect arcs, generic impact flashes and crescents.
Together with `1BA`, twelve poses now use capture-verified PCE geometry and
ordered palette shades. Their live SAT position/attribute/pattern checks,
3,072 source pixels and 96 native flip/facing uploads pass without remaps or
software drops. Existing 903 large and 2,890 small sprite keys and both Normal
and BC palettes remain byte-identical. The projectile submission fixture and
four-player controls/individual respawn/re-entry fixture pass. ROM SHA-256:
`69c6ddfbd89a872ffdc6cb10ec66f1f6ae2f790f324791ca7ec071285b5676ad`.
Evidence: `.local/bc-weapon-shapes-fix/`. The source/current comparison page is
`.local/bc-weapon-shapes-review/index.html`, regenerated with
`tools/build_bc_weapon_review.py`; it verifies the screenshot report's ROM
identity before publishing comparisons. These are inferred corrections,
not additional user approvals. Palette hues remain approximations.
The straight-shot and beam pieces, `1D4`/`1D6`, and unobserved `1E0`–`1E6`
remain outside this import set and must still be reviewed.

The new audit finds live SAT matches for 18 of 22 mapped projectile poses.
Each match requires the captured projectile pattern, attributes and position
to agree with its SAT entry; four `1E0`–`1E6` poses remain unobserved in the
sampled captures. Sheets and manifest are under
`.local/bc-projectile-correspondence/`. Several existing mappings are wrong:
`1A8`–`1AC` fireballs use blue arcs, ring phases use generic impact flashes,
and `1BA` used a crescent instead of a horizontal glowing shot. Presence and
mapping coverage did not prove these shapes corresponded.

`1BA` is now corrected with original PCE geometry, using a free BC-only small
sprite key and an ordered fire-color ramp fitted to existing Genesis palettes.
Source capture hashes are in `tools/data/bc_player_projectile_shapes.json`.
`qa_bc_player_projectile_shapes.py` verifies the live source correspondence,
all 256 imported pixels, eight native flip/facing cases, palette selection and
VRAM uploads. No remaps or software drops occur. The general projectile draw
test passes 2,400 pools, 37,177 ordered sprites and 600 packed strips.
All 903 existing big-sprite and 2,889 small-sprite keys and both palettes are
unchanged. The 4 MiB cartridge hash is
`222ea28abbc6baa6ff201a9896c9dff8bd16728d7353c7705254fb0a4c4c34aa`.
Evidence: `.local/bc-projectile-1ba-fix/`; source/before/after is
`comparison.png`. The remaining fireball/ring/orb mappings are not certified
by this single-pose correction.

### Player death sequence correction

New PCE reference capture `player-death-art-sequence` samples every frame
from 2300 to 2500 after an ordinary boot/controller sequence. All five death
poses (`B500`, `B680`, `B800`, `B980`, `BB00`) are visible and matched to the
player's position and SAT attributes. `prepare_bc_player_death_shapes.py`
preserves their pixels, palettes and capture hashes in
`tools/data/bc_player_death_shapes.json`; deterministic regeneration passes.
The optional `pce_oracle.py --snapshot-from` avoids dumping the whole boot at
this sampling frequency; its default capture behavior is unchanged.

The old inferred selection `{0,1,3,5,7}` from Normal's death table selected
the wrong phases. The adapter now reuses Normal `1A6` for BC's solid flash
(`B680`), and imports the original spark, fire and two fading phases. A trial
reuse of `1A4` for `B800` was rejected after rendered comparison showed the
wrong contour. Imported poses use unused colour-eight keys `7E0`, `7E2`,
`7E3`, `7E4`, with ordered red/orange/yellow/white shade levels fitted to the
existing Genesis palettes. The five source animation timings are unchanged.

`qa_bc_player_death.py` verifies native initialization, all 4,096 imported
pixels, ordered ramps and twenty four-player pose uploads. No software sprite
drops or runtime remaps occur. All 899 existing big-sprite keys, 2,889 small
keys and Normal/BC palette bytes remain identical to the preceding build.
Captured player-state coverage, 4P controls/individual respawn/re-entry and
continue-credit/rank tests pass. ROM size remains 4 MiB. Current SHA-256:
`62f456b1fce878a5980093c70544d9f32ac5f4a963eee5c4aa1a2b5aeadc72ef`.
The repeatable comparison page is `.local/bc-player-death-fix/index.html`,
built by `build_bc_player_death_review.py` from source shapes and current-ROM
captures. Geometry is original for the four imported phases; palette hues
remain approximations. Complete weapon correspondence is still outstanding.

### Player entry-pose correspondence

Matched PCE SAT entries to captured player position and attributes before
comparing the four living poses. Idle (`A0C0`) and firing (`A240`) correspond
to Normal `022` and `026`; early entry (`A600`) matches `062`. Late entry
(`A780`) matches the side-facing transform `072`, rather than the previously
selected front-facing `076`. The adapter now selects `072`, retaining the
existing four-player variants and palette choices. These are inferred visual
correspondences, not new user approvals or exact pixel/color identities.

Source capture hashes and decisions are recorded in
`tools/data/bc_player_art_correspondence.json`. The before/after comparison is
`.local/bc-player-entry-fix/comparison.png`. Captured-player coverage, native
four-player initialization and robot/projectile rendering fixtures pass.
ROM `a29a9a2d9474fa238124a804d254abdee4d04dae83ab6e48a5eb2f49b777af6c`
differs from the campaign-tested `2c3fed51...` in only the selected pose byte
and cartridge checksum. Death poses were subsequently corrected as described
above; complete weapon correspondence remains unreviewed. No new source pixel
art was imported by the entry-pose correction.

### Round-one skyline correction

Cell `0D` depicts a low skyline against black sky. Its Normal donor tile 38
also contained an unrelated blue hill and sky field. The generator now removes
the upper half and palette-zero sky pen 5, retaining the donor city's original
pixels and colors. This is an adapted Genesis skyline, not exact PCE geometry.
The source capture confirms a black upper half. Decoded-cell isolation shows
only `0D` changes; the background palette is identical. All-round visibility
and palette checks, native round-one ROM/VRAM camera coverage, the build and
review-page persistence/export checks pass. Evidence and before/after imagery:
`.local/bc-r1-skyline-fix/`. Current ROM SHA-256:
`e38d7e186a3d65bfea1665786fb8659a2702cccbd54fdcbcc4c8d238525d0bea`.
Only 209 ROM bytes differ from the preceding build, within round-one scenery
and its checksum; code and audio are unchanged. Other tile correspondences
remain under review.

Current-build boss verification was repeated against cartridge SHA-256
`548a830328c7db8969cae337435c23fc15f33407a7ac0d6a20f3a4dc284ee03a`.
All nine bodies and four composite attack poses passed source-pixel and native
render checks. Fifteen projectile variants passed 3,840 pixel checks and 60
hardware flip cases; twenty final-serpent poses passed 20,480 pixel checks and
80 flip cases. Capture audits matched 2,828 boss attack uses and 417 serpent
actor uses without unknown attacks or shape mismatches. Two protected-head
orientations are verified from the loaded source bank, rather than observed
live. The composite review page has been regenerated from these current-build
captures. This verifies artwork, not full-speed campaign acceptance or exact
PCE palette hues.

User review: the BC reference for enemy family `0x3682`, pose `0x0A`, has a
blue/white body and orange exhaust, while the proposed Normal Genesis asset
`0x300` is green. The review page must not treat shape reuse as color approval.
Preserve intentional BC palette differences when reusing regular artwork.

The right-hand image is the regular Genesis conversion, not a captured PC Engine
normal-mode asset. Whether this enemy is green or blue in PC Engine normal mode
is still unverified; do not present the Genesis comparison as proof. No cartridge
palette change or shape approval is recorded by this note.

## Implementation and review update

User direction: reuse matching Genesis artwork, recolor where BC differs,
and keep the Jet's regular colors. Review decisions now distinguish
`keep`, `recolor`, and `new`. Legacy `approve` decisions migrate to `recolor`
because the previous page explicitly promised BC color preservation.

First implementation: 18 prepacked small-sprite variants for references
0x3682/0x3684, using unused color keys 14/15. Body ramps use captured BC
blue/white or green targets, fitted to the existing Genesis sprite palettes.
This is a hardware-palette approximation, not exact PCE RGB reproduction.
Removed the global BC sprite tint so the Jet uses its unchanged Normal patterns
and palette. Original Normal sprite entries, large patterns and palettes are
byte-identical; 4P menu/pause/re-entry tests pass. No other family is declared
finished or user-approved. Cartridge SHA-256:
`b23da8d3026de435f456865549614141009fd419161b5e62295e1a6782517ed4`.

The local review page now contains 204 sprite poses and 689 background
proposals. Expanded ordinary-sprite evidence comes from exact live actor/SAT
matching across 3,597 captured snapshots (34 families observed before merging
with previous cards). Composite bosses and player/weapon comparisons remain
outstanding. No classification is inferred from a missing image.

## User review interpretation — October 8, 2026

Explicit user classifications are authoritative. Unclassified cards are not
rejections: some have incorrect pairings (for example, a robot versus an
explosion). Correct correspondence before extrapolating. Extrapolate within
verified matching families/poses, retaining provenance that a decision was
inferred rather than explicitly selected. Do not overwrite explicit decisions.

User's working assessment is that backgrounds are not recolored. Default to
unchanged Genesis background colors where artwork matches; require clear BC
reference evidence before introducing a palette difference. This supersedes
any blanket assumption that all BC backgrounds should be recolored.

The browser export has now been received and is preserved verbatim in
`tools/data/bc_art_user_decisions.json`. It contains 134 explicit selections:
96 recolor and 38 keep, with no new-asset selections.

`tools/resolve_bc_art_decisions.py` resolves the local review inventory into
`tools/data/bc_art_resolved_decisions.json`: 14 additional same-family/palette
pose inferences, 56 unresolved sprite matches and 689 background defaults.
Explicit mixed choices remain per-pose (for example crab-turret idle stays
unchanged while recoil is recolored). Gallery palette 15 never propagates to
gameplay palettes. Pickups and the questionable 3682 effect poses do not inherit
from unrelated items in their bank. These are classifications; they do not
claim the remaining production recolors are implemented.

The review page seeds these classifications, labels inferred/default decisions,
and preserves locally saved choices. Exported classifications include provenance.

## Implemented reviewed recolors (2026-10-08)

The build now applies 103 recolor cards: all 96 explicit selections and seven
same-family/palette inferences. The 38 explicit keep selections and seven
inferred keeps retain their Normal keys. All 56 unresolved sprite cards retain
the previous mapping. This does not establish that those unresolved mappings
are correct. No background artwork or palette was changed in this pass.

`tools/data/bc_recolor_recipes.json` stores captured RGB3 material targets with
card IDs and provenance. `tools/prepare_bc_recolor_recipes.py` exports these
from the local review captures and an explicit pre-recolor mapping snapshot.
Normal builds consume the saved recipes, not local screenshots or dylibs.
Targets are pooled across matching family/palette material pens; original
black outlines and missile material ramps are protected. The two fixed Genesis
sprite palettes approximate the PCE colors, so exact color identity is not
claimed. The review page now includes the actual built result as a third image.

`tools/bc_sprite_recolors.py` packs small and large BC variants and generates a
family/palette/pose selector. The ending gallery has a separate gold/white
ramp matching its BC reference, rather than the previous mint treatment.
Mixed decisions remain separate, including crab idle/recoil and mine headings.
No sprite geometry, flips, timing, collision, or actor simulation is changed.

Byte-identical Normal patterns are deduplicated before appending BC variants
so the final ROM remains inside the 4 MiB cartridge window. Bank indices may
move, but all original keys resolve to identical pattern bytes and palette
selections. The normal palette itself remains byte-identical.

Validation for ROM SHA-256
`246af6b1265219b6f5b669de3761201a01c7619b9cd8a2b981a5524ee69b316f`:

- Full build and ROM extent/checksum checks passed.
- `qa_bc_reviewed_recolors.py`: 22,061 selection cases, all source flips,
  keep/unresolved fallbacks, unchanged opacity, and all Normal patterns/palettes.
- `qa_bc_menu.py --players 4`: menu, launch, audio, every-controller pause,
  resume, return/re-entry and reset passed.
- `qa_multiplayer.py --players 4`: joins, waves, Boss Rush health, save/reload,
  migration and merge passed.
- Review-page rendering, persistence, export and filters passed.

Exact commands for the asset comparison use the saved local baseline:

```sh
.venv/bin/python tools/qa_bc_reviewed_recolors.py \
  --baseline .local/bc-recolor-baseline \
  --normal-art-source .local/engine-priority-baseline/src/bc_actor_art.c
```

## Shading correction after user feedback (2026-10-08)

The earlier independent nearest-color conversion collapsed different material
shades into one color. It was not adequate. `tools/bc_shading.py` now fits each
source material ramp jointly, requiring strictly increasing output luminance
for its distinct input shade levels. Body and exhaust remain separate ramps.
Weights are pooled across the family and source palette, so animation poses
share the same palette and pen mapping rather than shifting colors per frame.

BC now loads `bc_sprite_pal`, which adds middle green and blue in the two
otherwise unused pen-15 slots. All 30 previously used sprite palette entries
are unchanged. The build and regression verify that no original small or large
sprite pattern uses these spare pens. Normal mode still uses the byte-identical
original palette; explicit keeps, including Jet, retain their original pixels
and used colors. The gallery keeps its separately fitted gold ramp.

The current preview uses these generated ROM patterns and live BC palette.
The previous flat preview is retained locally in `.local/bc-flat-recolor-baseline/`.
Palette quantization still applies; this correction does not claim every PCE
color is reproduced exactly or that the 56 unresolved matches are validated.

Tested ROM SHA-256:
`8a7114d2ac138eb563d62508f8e1d305605e1102f4efe8bd0e48b64de40e957a`.
The build is 4 MiB. Asset regression passes 22,061 selection cases and 265
multi-level material ramps, including strict shade ordering, animation palette
consistency, unchanged opacity and original bank contents. BC menu and Normal
multiplayer regressions pass separately for 3P and 4P; review-page checks pass.
Evidence: `.local/bc-shaded-*.log` and `.local/bc-shaded-assets-qa.json`.

This is not a release-complete claim. The HuCard source has since been found in
`Downloads/SideArms - Hyper Dyne (USA).zip` and integrated as the PC Engine music
option; see `hucard-soundtrack.md` for implementation and playback evidence.
BC performance and unresolved matching work remain.

## Corrected rain-shot correspondence

The source cards `actor-36ce-00-p1` and `actor-36ce-02-p1` show a large orb
followed by a small orb. The previous mapping reversed them. Pose 00 now uses
Genesis pattern `0x127` and pose 02 uses `0x126`. Source flips, timing, palette
selection and collision behavior are unchanged. This corrects correspondence;
the pending color classification is not promoted to a user approval.

Validation: ROM `4abfc77d25e912e1c6e8e217f64bb96f9a85450e9d43bf7f6bc252abb733710c`
builds successfully. The asset regression passes 22,061 selections and 265
ordered shade ramps. The emulator renders 616 actor selections with zero
runtime remaps or dropped sprites and returns to the menu. The review-page
checks pass; the two rain-shot candidate images now follow the corrected size
order. Evidence is in `.local/bc-match-finalize/` and `.local/bc-actor-render/`.

The next correspondence audit has identified these candidate banks by visual
inspection of the original Genesis patterns (not yet applied or approved):

- `0x3690`: the rotating mechanical pod is in the `0x7c0`–`0x7e6` bank;
  the current humanoid robot bank is incorrect. Per-pose order needs checking.
- `0x3694`: shell-to-standing-robot poses resemble `0x2e0`–`0x2e6`;
  the current rotating-pod bank is incorrect. Source orientation needs checking.
- `0x3696`: the capsule resembles `0x340`/`0x342`, with three-bladed drones
  in the `0x350` region; the current cannon/mine pairing is incorrect.

These are candidate identifications, not completed matches. The local grayscale
atlases `large-200.png`, `large-300.png`, and `large-700.png` preserve the search
evidence. Colors, corresponding poses and source flip attributes still need
verification before replacing these families.

## Shell-to-robot correspondence

Family `0x3694` is now corrected: source offsets `00/08/10/18` use Normal
patterns `2E0/2E2/2E4/2E6`, color 0, with the original source flips. The
captured canonical poses show the same closed shell, partially unfolded body,
raised shell, and standing robot. The mirrored `2F0/2F2/2F4/2F6` bank provides
the opposite facing; it is not needed because BC supplies flip attributes.
Normal's family/color evidence is also documented in `docs/re/objects.md`
under `trooper_red`. The comparison sheet is
`.local/bc-match-finalize/rank-3694.png`; ranking helped locate candidates,
while visual inspection established the pose correspondence.

Five cards (four gameplay poses and the standing gallery pose) now infer
recoloring under the user's instruction to extrapolate corrected matches.
The 134 explicit user choices remain authoritative. Gameplay and gallery
recipes remain separate, and all original Normal patterns remain unchanged.
The review page now displays the corrected Normal candidate and built recolor.
There are now 108 implemented recolors, 45 keeps and 51 unresolved sprite cards.

ROM `1892fcc189b05e8a02db68dd6df4af49ce999f96a8a4faa27d4e8a82d5ad3b77`
passes the full build, 22,056 selection/isolation cases, 280 ordered shade ramps,
616 emulator render selections, and review persistence/export/filter checks.
The runtime render test reports zero remaps and sprite drops. Evidence:
`.local/bc-match-finalize/shell-*.json` and `shell-build.log`.
The reduced selection-case total is caused by five previously unclassified
combinations moving into the recolor checks, not by removing reviewed cards.

## Splitting capsule correspondence

Family `0x3696` now uses the burst-orb capsule patterns `344/346` for source
offsets `00/08`, and three-bladed fragment patterns `350/351/352` for offsets
`10/12/14`, all with Normal color 5. These replace the unrelated cannon and
homing-mine candidates. Canonical reference poses and candidate comparisons are
in `.local/bc-match-finalize/rank-3696.png`; the Normal family is documented as
`orb_burst` in `docs/re/objects.md`. Source size, flips, movement, timing and
collision behavior remain unchanged.

Six previously pending cards now infer recoloring, including the capsule's
gold gallery pose. Material targets and animation weights are pooled separately
by sprite size: the large blue capsule and small orange drones share a source
family but must not share recolor recipes. The capsule's side lobes retain an
ordered dark-red/red/orange/yellow ramp; direct pixel-overlap sampling inverted
this material's brightness because the two versions draw the flames differently.
The gallery palette remains separate. The review page shows corrected Normal
candidates and the actual built recolors. Totals are 114 recolors, 45 keeps,
and 45 unresolved sprite cards; explicit user decisions are unchanged.

Verified ROM `e6fb387609627b8c4ca4e53d9728d15e5b6d35e9b02ee9e64506680d1572221e`:
full build, 22,050 selection/isolation cases, 298 ordered material ramps,
616 emulator render selections with zero remaps/drops, and review-page checks
pass. Evidence: `.local/bc-match-finalize/capsule-*.json` and `capsule-build.log`.

## Rotating pod correspondence

Family `0x3690` now uses Normal's rotating pod, color 5, in this pose order:
`7C0/7C2/7C4/7C6/7D0/7E0/7E2/7E4` for source offsets `00..38` in steps
of eight. The former hover-bike humanoid mapping was unrelated artwork.
The full comparison sheet `.local/bc-match-finalize/pod-candidates.png` shows
the matching front, rear, tilted and starburst poses. In particular, offset
`20` shows the rear barrel at the left (`7D0`), not its opposite-facing `7E6`.
The source's eight-pose sequence does not use every pose in Normal's larger
bank. Existing source X/Y flips and actor behavior remain intact.

Ten cards now infer recoloring: eight palette-11 poses, the palette-5 starburst,
and a gallery pose. Their palette recipes remain separate, with ordered shades
pooled across poses within each palette. The review page displays corrected
Normal candidates and generated recolors. Totals: 124 recolors, 45 keeps and
35 unresolved cards; the 134 explicit user choices remain unchanged.

Starburst offsets `10/30` pool their material targets separately from body
poses: their bright flash ramp is blue/cyan/white in BC, rather than the
Normal orange/yellow ramp. Each still preserves the original Genesis geometry
and ordered shading. This remains a constrained palette approximation, not
pixel-identical PCE artwork.

Verified ROM `b8c0d02a35195771911da091c26abfc59109f6df4ccd1249c674a029550c7366`:
full build, 22,040 selection/isolation cases, 328 ordered shade ramps, 616
emulator render selections with zero remaps/drops, and review-page checks pass.
Evidence: `.local/bc-match-finalize/pod-*.json` and `pod-build.log`.
Most remaining pending cards are beam poses (`0x36cc`: 25); other pending
families are pickups/effects, radial shots, rain-shot colors, and one small
missile pose. Composite bosses and background identity still require the
separate completion audit described above.

## Radial shot and rain colors

Radial-shot family `0x36c8`, offset `02`, now uses the existing horizontal
Genesis beam `122`, color 8, instead of an orb. The canonical source and
Normal opacity masks overlap at 0.986 IoU, and visual inspection confirms the
rounded left head and full-width right trail. The diagonal offset `00` remains
unresolved; shape ranking alone is not approval (its highest-ranked candidates
include unrelated robot fragments). Evidence:
`.local/bc-match-finalize/radial-rank.png` and its generating script.

That horizontal beam and the two previously corrected `0x36ce` rain orbs now
infer BC orange recoloring. Source flips and gameplay behavior remain intact.
There are 127 recolor cards, 45 keeps, and 32 unresolved cards. The 25 turning
beam cards need a separate geometry adaptation pass: their short growth
segments, vertical lines and corner pose are absent from the existing ordinary
beam `120..125` bank. Direct sprite-bank inspection is preserved in
`.local/bc-match-finalize/small-atlas.png` and `small-atlas-zero.png`.

Verified ROM `947fe727af7d0ce9503d1e87b7eb7a773df92b78db131408d0a2afe608c365ef`:
full build, 22,037 selection/isolation cases, 334 ordered shade ramps, 616
emulator render selections with zero remaps/drops, and review-page checks pass.
Evidence: `.local/bc-match-finalize/radial-*.json` and `radial-build.log`.

## Turning-beam geometry

The 25 captured `0x36cc` cards now use BC-specific geometry for the corner,
horizontal/vertical growth segments, and nine turning headings. The former
generic `120..125` choices had incorrect directions and lengths. These cards
are inferred **new assets**, not falsely classified as recolored matches.
Their exported 16×16 shape and shade ranks are versioned in
`tools/data/bc_beam_shapes.json`, with capture/frame provenance and reference
hashes. `tools/prepare_bc_beam_shapes.py` regenerates that export from the
canonical live-SAT-verified comparison images.

`tools/bc_beam_shapes.py` packs these shapes using the existing blue/cyan/white
and red/orange/yellow/white Genesis palette ramps. All five source shade levels
remain distinct and ordered. Only transparent pixels remain transparent; the
growth lengths and corner geometry match the reference. Spare color keys store
the variants without replacing Normal patterns. Source animation, flips, actor
positions, collision and timing remain unchanged. The ordinary recolor selector
dispatches the new geometry at the existing captured family/palette/pose keys.

The review page labels these built BC beams as adapted assets and retains the
old mismatched Normal candidate for comparison. Totals: 127 recolors, 45 keeps,
25 new beam cards and seven unresolved ordinary-sprite cards. This is not a
completion claim for composite bosses, backgrounds, music polish or performance.

ROM `18b4495d58b0e47cebce63d745918614e6570f3a581fef6426a20adfcadafbc0`
builds inside the cartridge window. Asset checks pass 22,012 selection/isolation
cases and 359 ordered ramps. `qa_bc_beam_shapes.py` independently compares all
6,400 pixels against the captured references, checking exact opacity geometry
and strictly ordered output colors for each source shade. The runtime render
check now includes both beam palettes and all source flips.
Evidence: `.local/bc-match-finalize/beam-*.json` and `beam-build.log`.

## Remaining pickup and missile pairings

Four more skipped cards are now inferred recolors following correspondence
inspection (`.local/bc-match-finalize/last-ranks.png`):

- `367A/2A/p1`: spinning option uses `110`, not the unrelated star `111`.
  Its silhouette matches the captured reference exactly.
- `367A/2E/p2`: long blue cross uses `01F`, not the shorter cross `01D`.
  Its silhouette also matches exactly.
- `367A/24/p0`: the existing `104` expanding-shot icon was the correct shape;
  its BC colors are now applied (visible-mask overlap 0.983).
- `3682/0C/p5`: use bomb-column pose `309` with lower crossbars, replacing
  `301`'s broad top flare. This is the same Genesis family, redrawn with wider
  body details than PCE; it is not claimed as pixel-identical artwork.

These changes preserve source flips, animation and gameplay behavior. Inference
is restricted to the four exact card identities, not the entire mixed pickup
bank. Explicit user choices remain unchanged. The review page now displays
the corrected candidates and generated shaded recolors.

ROM `26dcf4ac7c13a5d6b6824182a2d54fcd5ad93ac06e8515194431fdaa3616650f`
passes the full build, 22,008 selection/isolation cases, 366 ordered shade ramps,
652 emulator render selections with zero remaps/drops, and review-page checks.
Evidence: `.local/bc-match-finalize/pickups-*.json` and `pickups-build.log`.
Three ordinary-sprite cards remain unresolved: the diagonal radial shot,
the aimed-laser flash, and the `367A/28` pickup.

## Completed ordinary-sprite review inventory

The final three cards now use BC-specific shapes: `36C8/00/p1` diagonal radial
shot, `36B4/00/p9` aimed-laser flash, and `367A/28/p0` pickup. Their shapes do
not correspond to the formerly proposed orb, large cross, or side-on pickup.
`tools/prepare_bc_unique_shapes.py` verifies exact live actor/SAT correspondence
and exports the canonical VRAM pixels and source palette into
`tools/data/bc_unique_shapes.json`. Capture hashes, frame, pattern and attributes
are retained. This includes transparent pen zero and opaque black source pens;
black is not inferred as transparency from a screenshot.

`tools/bc_unique_shapes.py` fits each source material's ordered shades to the
existing Genesis palette and stores the results in unused sprite keys. The
diagonal shot retains its orange/yellow/white ramp; the flash keeps separate
orange and teal ramps; the pickup keeps separate orange and blue ramps.
Normal assets and explicit user choices remain unchanged.

All **204 ordinary-sprite cards** now have implemented outcomes: **131 recolors,
45 keeps, 28 BC-specific shapes**, with no unresolved cards in that inventory.
This does not cover composite bosses, player/weapon comparisons, or validate
the 689 background identity proposals. Those remain separate release work,
along with HuCard synthesis/transition checks and stock-clock performance.

ROM `687f9d821f15a48b87a2a73b7659d1dac40526b1cc4f710f4a2664bcd09bf3f8`
passes the full build, 22,005 selection/isolation cases, 371 ordered shade ramps,
652 emulator render selections with zero remaps/drops, and review-page checks.
`qa_bc_unique_shapes.py` additionally verifies all 768 pixels directly against
source VRAM, including 21 opaque black pixels. Evidence:
`.local/bc-match-finalize/unique-*.json` and `unique-build.log`.

## Background palette policy applied (October 8)

The old scenery draft still applied custom colors despite the user's direction
to keep Normal Genesis background colors by default. Those blanket recolors
are now removed. Round 1 reads `zone0_pal.bin`; rounds 2–10 read `zone1_pal.bin`,
matching the actual Normal tile atlases used by their builders. The existing
Arcade/Vivid display setting still applies normally.

`qa_bc_background_colors.py --baseline .local/bc-background-colors-baseline`
checks all ten generated palettes against their original material palettes and
confirms that every tile byte, template attribute and source-cell remap is
unchanged. The correction changes 209 palette words across the ten rounds.
The full build and round-1/round-4 emulator background upload/render checks
pass, as do the review-page persistence/export checks. The review page's third
background image has been regenerated with these corrected colors.

This applies the user's color policy, not an approval of the 689 proposed tile
identities. Adapted contours, questionable matches and composite artwork still
need their separate source correspondence audit. Evidence and the previous
generated scenery are in `.local/bc-background-colors-baseline/`. Main ROM:
`e2baaabb9c07ec3cd295a221d705990358565079aac933b0f3650fee83ac885c`.

## Background material-reuse inventory (October 8)

`tools/audit_bc_background_reuse.py` compares each built background cell's
rendered pen geometry, palette bank and priority with every current Normal
Genesis metatile in the corresponding zone, including whole-cell flips.
Across the 689 review cards, **561 are exact unchanged metatiles, 15 are flipped
copies, and 113 are adapted geometry**. Every exact/flipped match includes the
previously proposed donor tile; none resolves only to a different donor.

The versioned results are `tools/data/bc_background_reuse_audit.json`. Review
cards now distinguish these outcomes, while preserving user decisions. The
reference atlases were regenerated from current assets and source captures;
the page's rendering, persistence, filtering and export checks pass.

These results verify material reuse, not semantic correspondence with PCE BC.
For example, a reused building texture can still depict the wrong building
part. All entries retain `pce_identity_verified: false`; source-object matching
and the 113 adapted contours still require review. No ROM artwork is changed
by this inventory pass.

## Round-one striped tower-foot correction (October 8)

Source cell `07` shows the foot of a striped tower, while its former Normal
proposal (zone 0 tile 24) shows distant city blocks. Inspection against the
complete zone-zero atlas identified tile 32 as a suitable striped-facade
material. The built BC cell now mirrors/crops that facade to put the tower on
the left and reuses tile 9's blue material for the lower band. It retains the
Normal palette. This is an adapted composition, not a pixel-identical PCE copy.

The generator and review card now reference donor tile 32. An isolation check
against the previous generated scenery confirms that only source cell `07`
changes; the palette and all other cells remain identical. The full build,
round-one emulator tile-upload/nametable coverage, all-round palette check and
review-page checks pass. Evidence: `.local/bc-r1-tower-fix/`; visual source and
donor comparisons: `.local/bc-background-colors-baseline/building-candidates.png`.
The current material audit has 560 exact, 15 flipped and 114 adapted cells.
Other source-object pairings remain unverified.

Main ROM SHA-256:
`d2c002c385aefcbf844f8ed73527a5e0cfefc5f7106a96a1342d6f14b65f93da`.

## Missing round-one rock tip restored (October 8)

Source cell `27` was incorrectly mapped to blank Normal tile 0. The captured
BC artwork contains a small rock tip at x=16–31, y=26–31. The builder now uses
Normal zone-zero rock material 67, clipped to the widening source outline.
It emits 90 textured pixels in those bounds, preserving the Normal palette;
this is adapted Genesis texture rather than imported PCE color pixels.

The isolation check confirms that cell `27` alone changes and the palette is
identical. Full build, round-one emulator background upload/camera coverage,
all-round palette checks and review-page checks pass. The source/proposed/built
sheet has been refreshed. Evidence: `.local/bc-r1-rock-tip-fix/`.
Material inventory now contains 559 exact, 15 flipped and 115 adapted cells.
Remaining background pairings still need source-object review.

Main ROM SHA-256:
`6a119090f62961c7d4ac0b2f78743f028bef495ff9bd6185a5867cd3798758ad`.

## All-round blank-substitution check and round-seven repairs (October 8)

`qa_bc_background_visibility.py` compares visible source pixels with generated
scenery for all 689 mapped review cells. After the round-one repair it found
two remaining fully blank substitutions: round-seven cells `18` (667 visible
source pixels) and `37` (276). Both had incorrectly selected Normal tile 0.

The machinery base now uses Normal tile 112, with tile 92's original lava
material along its lower four rows. The sloped wall uses Normal tile 65.
Both are clipped to the captured source's visible row envelopes, stored with
capture hashes in `tools/data/bc_background_r7_missing_contours.json`. Their
interior texture and colors remain Genesis assets. The two materials used in
the base's shared tile row are asserted to use the same palette bank.

The isolation check confirms that only these two cells change and the palette
is unchanged. Build, round-seven emulator tile/nametable coverage, all-round
palette preservation and review-page checks pass. The visibility check now
passes all 689 cells with zero fully blank substitutions. Evidence and the
previous scenery are in `.local/bc-r7-omissions-fix/`.

This closes the blank-substitution check only; it does not certify that every
nonblank cell has the correct source subject or contour. Current material
inventory: 557 exact, 15 flipped, 117 adapted. Main ROM SHA-256:
`5d4ecfacfbf81d67c95de28f34c6b249a4a28ad0d12913a9fdededaf4fb13446`.

## Round-one water/cliff correction (October 8)

Cell `1B` was incorrectly replaced by an entirely rocky Normal metatile 61,
losing its left water strip. The built cell now uses a column of Normal water
metatile 4 on the left and retains the other three columns of cliff metatile
61. Both original palette banks and material pixels are preserved. The source
strip is eleven pixels wide; the adaptation uses an eight-pixel tile boundary
to keep water and rock on their separate original Genesis palettes. This is
an adapted composition, not an exact source contour match.

The decoded-cell isolation check confirms that only `1B` changes and its
palette is unchanged. The full build, 103-camera round-one emulator check
(115,360 subtiles), ten-round palette preservation, 689-cell blank-omission
check, and review-page checks pass. The review includes the corrected preview
and a material-reuse note. Evidence is in `.local/bc-r1-water-cliff-fix/`.
Current material inventory is 556 exact, 15 flipped, 118 adapted. ROM SHA-256:
`968172e82c64be1df4044fb3e18815bf9634e1ce916481b84d42eff55c9d9bdb`.

## First composite boss correspondence (October 8)

The source round-one boss is a long blue spacecraft with an orange central
eye and paired side pods. Its old replacement used the cyan creature at
Normal `4A0`, color 14. Visual comparison with all three available Genesis
boss designs identifies `4E0`, color 0 as the closer corresponding spacecraft.
The generator now uses that existing blue/orange shaded asset. Its six-block
layout and existing 128-to-96 horizontal adaptation are unchanged; the draw
path selects its original palette bank. This is an inferred match under the
user's reuse direction, not an explicit new user approval or a pixel identity.

Only `bc_boss_patterns` changes among the ten generated arrays; the other
bosses and beam are unchanged. Both round one and the round-nine reprise pass
actual ROM-to-VRAM pixel, palette, position and release checks in
`qa_bc_boss1_render.py`. The refreshed host fixture passes 14,772 first-boss
and 18,040 second-boss captured states without simulation mutation. The full
build and existing review-page persistence/export checks pass.

Decision evidence is versioned in `tools/data/bc_composite_art_decisions.json`.
The source/before/after page is `.local/bc-composite-review/index.html`, linked
from the main review page; build/isolation/render evidence is under
`.local/bc-boss1-match-fix/`. Other composite matches remain unresolved.
ROM SHA-256: `5e9f3e3b83d7385148ada83bd42e8622c4b27273c26de3196712ea839058b8be`.

### Composite-boss source audit: rounds 2–9

The remaining eight composite replacements are not valid shape matches. Direct
comparison with their captured PCE scenes shows different silhouettes and
articulated parts, not merely palette differences. The existing replacements
remain in the ROM pending a renderer/artwork correction; this audit does not
classify them as finished recolors or user-approved matches.

`tools/prepare_bc_composite_shapes.py` now preserves 24 source poses (23 visible)
and 215 constituent 16×16 pieces in
`tools/data/bc_composite_source_shapes.json`. It resolves live actor frame records,
applies their horizontal/vertical flips, and saves the indexed source pixels,
source palettes, part bounds, and SHA-256 hashes of code/RAM/VRAM/palette and
screenshot evidence. `--check` verifies reproducibility against those captures.
The data is source evidence, not production Genesis artwork. No sprite bank or
palette is changed by this exporter.

The expanded `.local/bc-composite-review/index.html` presents every PCE scene
beside its current Genesis placeholder and exposes the extracted source parts.
The right-hand previews use separate test poses, not synchronized gameplay.
`bc_composite_art_decisions.json` records the rejected placeholder matches
without changing the user's ordinary-sprite decisions.

Independent rectangular 32×32 packing would require 12, 10, 10, 7, 12, 12, 10,
and 12 body blocks for rounds 2 through 9 respectively, before blank-block
removal and deduplication. The current body allocation is six blocks. Correct
integration therefore needs explicit resident-block accounting and encounter
reload checks, particularly the round-nine reprise and round-five beam. Simply
recoloring the six current blocks cannot recover the missing geometry.

Validation: exporter and `--check` passed; all eight review sections and local
image/link references resolve. Production ROM remains unchanged at
`5e9f3e3b83d7385148ada83bd42e8622c4b27273c26de3196712ea839058b8be`.

### Corrected reusable selections for composite bosses 3, 5 and 9

The source-part audit also distinguishes wrong donor selection from missing new
geometry. Three existing Genesis designs provide better correspondences:

| BC boss | Previous selection | Current selection | Visual basis |
|---|---|---|---|
| 3 | 4E0 / color 5 | 4C0 / color 14 | Green tapered craft, dorsal fin and split rear |
| 5 | 4A0 / color 8 | 4A0 / color 14 | Twin cylindrical cannons; cyan body instead of red |
| 9 | 4C0 / color 8 | 4E0 / color 5 | Long mechanical nose, side pods and blue central eye |

These are inferred correspondences under the user's instruction to extrapolate,
not pixel-identical copies or new user approvals. All three preserve the donor's
indexed shade ramps and the existing six-block articulated adaptation. No
additional graphics allocation is needed for these selections. The earlier
source-geometry block estimates apply to reproducing the PCE shapes literally,
not to these reused Genesis adaptations. Rounds 2, 4, 6, 7, 8 and the final-round
art inventory still require work.

Only `bc_boss3_patterns`, `bc_boss5_patterns` and `bc_boss9_patterns` changed in
the generated boss bank. They are byte-identical to the selected donor conversion;
the other seven arrays, including the beam, are byte-identical to the prior
build. Runtime palette selection is PAL3 for the green/cyan bodies and PAL2 for
the gold spacecraft. Beam palette and geometry remain unchanged.

Validation on ROM
`9400ae77243ab0a741b328197ba02f0f42116f626e411bc0ad7ac59c23881357`:

- Full build passed.
- `qa_bc_boss_reused_matches.py`: five native preview cases passed, including
  pixel-identical round-nine reprises for bosses 3 and 5, resident VRAM bytes,
  palette banks, six-sprite chains, zero runtime remaps/drops and cache release.
- Existing boss 3/5/9 pose checks passed, including the short/full beam geometry.
- Captured-state host renderer check passed for bosses 1 and 2.
- `qa_bc_round9_scene.py --players 4 --next-round`: all nine encounters loaded
  their correct resident banks, with zero missing art, sprite drops or runtime
  remaps; score/lives survived round-ten entry, followed by 1,800 updates and
  return to Home. This fixture uses protection and explicitly forced defeats;
  it does not prove normal combat completion or full-speed performance.
- Sprite/background review persistence, export and filter checks passed.

Evidence is in `.local/bc-boss-matches-359/`; the composite review now shows
PCE, previous replacement and current selection for these three bosses.

### Round-two BC-specific composite shape integrated

The round-two green-creature placeholder is replaced with the captured BC
articulated hull, center and paired shells. `tools/bc_boss2_shapes.py` reads the
versioned source geometry and emits eleven nonempty 32×32 blocks plus per-pose
positions. Source-transparent pixels remain transparent and opaque black
outlines remain opaque. The 4,332 visible source pixels are retained without
resizing. The hull's three shades and white highlight map to four strictly
ordered brightness levels; eye/exhaust materials retain two levels. These are
approximations within the existing shared Genesis palettes, not exact PCE hues.

The native renderer uses the generated positions for all four frame records,
including the empty collision-only record. Round two reserves eleven blocks;
the round-nine sequence also reserves eleven. Because its round-two encounter
can overwrite the four beam slots, entering encounter five explicitly reloads
the beam after loading that boss's six body blocks. Other regular encounters
retain their previous allocation and artwork. Eight Genesis-derived boss banks
were verified byte-for-byte against their selected donors.

The additional art initially exceeded the cartridge window. The generator now
aliases byte-identical banks rather than writing them twice: bosses one and
four share the same 3,072-byte bank. Both symbols resolve to the same ROM address,
and all encounter relocation checks pass. The finished build remains 4 MiB.

Validation on ROM
`c4d49364a874fbda00ca6c9d658d19c31da4daf223d1bb5f3e4b1d12f72b2566`:

- Full build and cartridge-size check passed after bank deduplication.
- `qa_bc_boss2_geometry.py` reconstructs packed blocks and compares 147,456
  pixels across four poses, including 4,332 opaque pixels; ordered shade ramps
  and opacity checks pass.
- `qa_bc_boss2_render.py` verifies all eleven resident blocks, hardware sprite
  positions/palettes/chains across three opening poses, and cache release.
- Captured-state host checks and all nine encounter frame-relocation checks pass.
- Four-player round-one to round-two entry passes, including all eleven loaded
  blocks and 1,000 subsequent updates.
- Four-player round-two to round-three progression passes with `--clear-fire
  combat`, preserving score/lives and the next round's artwork/music. The
  no-fire diagnostic stalled behind surviving enemies at camera (1728,512);
  it is recorded as a failed fixture, not completion evidence.
- Four-player round-nine sequence and round-ten handoff pass: every encounter's
  required resident bank and the restored beam match ROM; no missing artwork,
  sprite drops or runtime remaps; 1,800 round-ten updates and Home return pass.
- Review-page persistence/export/filter checks and local image links pass.

The progression fixtures use protection and forced boss defeat; they do not
prove natural campaign completion or full-speed performance. Evidence is saved
in `.local/bc-boss2-shape-fix/`. Composite artwork remaining: rounds 4, 6, 7, 8,
and the final-round inventory.

### Shared mirrored source blocks prepare the original-boss imports

Round-two mirrored shells now share packed blocks using hardware sprite flips.
A shifted packing grid changes only transparent padding; source pixel positions
and sprite priority remain unchanged. Its body uses seven resident blocks rather
than eleven, saving 2,048 ROM bytes. The boss sequence again reserves ten blocks,
including room for the round-five body/beam; the existing beam reload remains
required because round two temporarily occupies its first slot.

On ROM `218e96cfaf585b803851f924b2925b8528421a04ee099dc693d2660790a1db0b`,
the full build passed. All three native round-two preview frames are pixel-identical
to the previous eleven-block renderer. Independent source-geometry reconstruction,
shade/opacity checks, captured-state host checks and hardware position/palette/
flip checks pass. Four-player round-nine loading verifies every encounter bank,
the beam restoration, round-ten handoff and Home return with no missing artwork,
sprite drops or runtime remaps. These fixtures retain their documented protection
and forced-defeat limitations. Evidence: `.local/bc-boss2-sharing/`.

### All nine original PCE boss bodies integrated

`tools/bc_boss_shapes.py` now packs every captured boss body. All previous
regular-Genesis body substitutions are removed from the builder and renderer.
The shared renderer uses source-relative part positions, per-pose palette fits,
and mirrored resident blocks; it retains empty collision-only poses. Per-boss
resident body counts are 3, 7, 6, 6, 6, 6, 5, 6 and 7. The round-nine sequence
reserves ten blocks and restores the provisional round-five beam when needed.

`tools/qa_bc_pce_boss_bodies.py` validates the actual ROM data against the source
geometry for every pose, including opacity and ordered material shades. It then
checks native VRAM contents, sprite positions, palette/flip/tile attributes, and
pixel-identical relocated poses for every round-nine reprise. Native comparison
images compose the bodies using their captured actor positions. The body colors
remain fits to the shared Genesis palettes; exact PCE hues are not claimed.

Evidence on ROM
`aec86f6cc262eae09a599a10c6e2506078429d9aee26bba7413381c8aa7fbe40`:

- Full build fits 4 MiB.
- All 26 poses pass reconstruction from ROM: 958,464 compared pixels, including
  33,556 opaque body pixels; every imported body preserves its source geometry.
- Native per-pose hardware checks and round-nine reprise image comparisons pass.
- Captured-state host checks for bosses one and two pass after using the new
  generated source geometry rather than the superseded donor layout.
- The four-player nine-encounter fixture verifies every resident bank and the
  provisional beam reload, with zero missing art, sprite drops or runtime remaps;
  round-ten handoff, 1,800 updates and Home return pass. Protection and explicit
  forced defeats remain fixture limitations; full-speed performance is unproven.
- Existing short/full beam geometry checks still pass, but those graphics remain
  substitutions and are not evidence of PCE attack-art fidelity.

The comparison page is reproducible with `tools/build_bc_boss_review.py`.
Evidence and the nine-body contact sheet are in `.local/bc-all-original-bosses/`.
Legacy individual body render commands now use the full PCE-source verifier.
Attack graphics, including the explicit round-four laser and round-five beam
substitutions, remain outstanding and must be imported before boss completion.

### Original composite boss attacks imported

The round-four laser (`36C8/AB1D`) and all three round-five beam poses
(`36CA/AF7D`, `AF97`, `AFC9`) now use captured PCE graphics. Their versioned
source pixels, palettes, piece flips and capture hashes are exported by
`tools/prepare_bc_boss_attacks.py` to `bc_boss_attack_shapes.json`.
The original part positions and transparency are preserved; colors use the same
ordered-shade fit to the shared Genesis palettes as the boss bodies.

Attack pieces are now packed into their owner's complete resident bank and
selected by family plus frame. The old Genesis laser calls and separate
Genesis-derived beam array are removed. Loading/reloading a bank therefore
loads its original body and composite attacks together; no special beam-slot
restoration or extra four-block allocation is needed. Smaller ordinary
projectiles still pass through the regular art mapper and remain pending.

On ROM `27cc712fcb5f41ff68bc8f4a41775bc82ff6999b0d137f7954039359d6f0a879`:

- Full build fits 4 MiB.
- All 30 body/attack poses pass reconstruction from actual ROM, hardware
  position/palette/flip/tile checks and round-nine reprise image comparisons:
  1,105,920 compared pixels, including 38,650 opaque pixels.
- The dedicated relocation verifier matches all 30 frames, including all four
  attacks, with no sprite drops or runtime remaps.
- Captured-state host checks pass; the renderer does not alter simulation state.
- The protected four-player nine-encounter fixture validates all complete banks,
  has no missing art, drops or remaps, and passes round-ten handoff plus 1,800
  updates and Home return. Forced defeats and unverified full-speed performance
  remain limitations of this fixture.
- Source export reproducibility and updated comparison-page links pass.

Evidence: `.local/bc-original-composite-attacks/` plus the current complete
pixel/render report in `.local/bc-all-original-bosses/bodies.json`.
The review page now includes PCE-pattern/Genesis comparisons for the four attacks.
`bc_boss_projectile_audit.json` records the remaining smaller-projectile families
observed in selected boss captures. It explicitly does not claim exhaustive pose
coverage or spawn-parent proof; those families must be audited before declaring
all attacks complete.

### Dedicated radial and rain projectile frames imported

The ordinary `36C8` radial frames 00/02 and `36CE` rain frames 00/02 now use
original PCE pixels. These families are dedicated boss attacks, so the later
explicit boss-import instruction supersedes their older Genesis art selections.
Shared enemy/boss families `3682` and `3698` are deliberately not changed by this
step; their boss-context import remains required. The existing source-derived
`36CC` and `36B4` attack artwork still needs cross-encounter coverage verification.

`prepare_bc_boss_shots.py` preserves four source frames, palettes and capture
hashes. `bc_boss_shots.py` appends or reuses identical sprite-bank entries and
replaces only those four selectors. Red/orange/yellow/white shades are fitted
jointly in strict brightness order. The earlier user choices remain saved; the
runtime and preview selection for these four dedicated boss poses follows the
newer explicit instruction. Normal sprites and unrelated BC choices are unchanged.

Validation on ROM
`94efc2efaba30655d440e4ab5f4d4cf362164c68e332177b0cd13f5fd1ff3e7a`:

- Full build fits the cartridge limit.
- `qa_bc_boss_shots.py`: 1,024 source-pixel checks and all 16 native flip cases
  pass; ROM-to-VRAM bytes, palette/flip bits, placement, opacity and ordered
  shades match. No runtime remaps or sprite drops.
- 109 captured uses across rounds 1, 6 and 9 match the imported source pixels
  and palettes without differences (bounded capture coverage, not every frame).
- Recolor isolation: 22,005 selection cases pass with exactly four explicit
  boss-shot overrides; Normal banks remain unchanged and 371 ordered ramps pass.
- All nine bodies and four composite attacks pass their full ROM/render/reprise
  regression checks on this build.
- Protected four-player round-nine sequence, round-ten handoff, 1,800 subsequent
  updates and Home return pass with no missing art, remaps or sprite drops.
  Forced defeats and unverified full-speed performance remain limitations.
- Source export reproducibility and review persistence/export/filter checks pass.

The current sprite previews use the actual dedicated-shot selectors, and the
boss review includes PCE/Genesis comparisons for all four frames. Evidence is in
`.local/bc-original-boss-shots/`. Shared-family boss projectile work remains open.


## Original shared boss shots and final serpent (October 8)

The explicit all-bosses instruction supersedes the earlier serpent recolor
choices. All twenty final head/body/tail poses now come from the loaded PCE
pattern bank, including both head palettes. Fifteen old Genesis-based recolors
are omitted from generation; their historical review choices remain recorded.
The imported geometry is selected by the ordinary final-segment pose mapper.

Shared shot families 3682 and 3698 have eleven boss-only frame/palette variants.
Encounter detection uses the composite boss actor, not the decaying aggression
timer, and recognizes final segments across all eight slots after head promotion.
Cache entries invalidate when encounter context changes. Ordinary enemy uses
retain the reviewed Genesis artwork. Dedicated 36C8/36CE shots, composite beams,
and existing source-derived 36CC/36B4 attacks retain original PCE geometry.

Verification: 3,840 projectile pixels and 60 hardware flip cases; 20,480 serpent
pixels and 80 hardware flip cases; 121 cache context transitions plus eight-slot
final promotion; 2,828 independently captured projectile uses and 417 final
segment uses without geometry mismatches. Eighteen of twenty serpent
pose/palette combinations appear live in the sampled captures; the two other
protected-head orientations are extracted from the same loaded pattern bank.
Normal sprite banks and palettes remain unchanged. Four-player final progression
passes through six successive heads and the ending handoff with forced defeats;
this is not a natural-combat or full-speed claim. Colors use ordered shades in
the shared Genesis palettes, so exact PCE hues are not claimed.

Current ROM SHA-256: `1f6a20e5a70271b5d9127b76f927f9ffe5ecb7885f0de09ef128bcd32d8561fa`.
Evidence: `.local/bc-shared-attack-audit.json`, `.local/bc-original-boss-shots/`,
`.local/bc-serpent-render/`, `.local/bc-final-serpent-scene.log`.
The composite review page includes the final serpent and shared attack variants.

## Round-one waterfront correction (October 8)

Cell `10` showed a large blue hill where the PCE reference has small buildings
on the left and open water on the right. It now combines the left half of
Normal city metatile 38 with the lower water band from Normal metatile 5.
The donor's unrelated sky/hill is removed around the retained city silhouette.
This is adapted Genesis artwork, not an exact PCE building outline, and both
materials preserve their original palette colors.

Only decoded cell `10` changes. All ten background palettes remain unchanged;
689 cells pass the blank-omission check, and the emulator validates 103 camera
positions / 115,360 subtiles. Review rendering, saved decisions, filters and
export pass. Reuse inventory: 554 exact, 15 flipped, 120 adapted cells;
semantic correspondence of the remaining mappings is still under review.

Evidence and the visual comparison are in `.local/bc-r1-waterfront-fix/`.
ROM SHA-256: `b9fb7b5d0294fbe1ede69e3bc2eb009800e9679acf84be619187e9ca87b82281`.
The 4 MiB ROM differs from its predecessor in 324 bytes, exclusively round-one
art/templates and the checksum; symbol addresses are identical.

## Round-one city boundary and rock-edge corrections (October 8)

Three further source-composition mismatches are corrected:

- `12`: the previous donor put the city across the bottom of the cell. Use
  Normal tile 19's left city columns and tile 9's water on the right, matching
  the source's left-city/right-water composition.
- `28`: move Normal tile 83's upper ledge down to the foot of the cell and
  trim it to the source low-ridge envelope.
- `32`: trim Normal tile 64's full cliff to the small lower-right rock edge.

The rock-edge envelopes are recorded with source hashes in
`tools/data/bc_background_r1_edge_contours.json`; the same source RGB geometry
appears in 29 snapshots from frame 1920 through 5280. Earlier snapshots precede
this loaded gameplay bank and are excluded. Interiors and palette colors are
Genesis materials; these are adapted compositions, not PCE texture imports.

Isolation confirms only these three decoded cells change. Full build, all ten
Normal palette checks, the 689-cell blank-omission check, 103 emulator cameras
(115,360 subtiles), and review-page persistence/export/filter checks pass.
The reuse inventory is 551 exact, 15 flipped and 123 adapted cells; this does
not certify semantic identity for the remaining background mappings.

Evidence: `.local/bc-r1-edge-fixes/`, including `comparison.png`.
ROM SHA-256: `ef853ea841cbffda4b71419cbbcd8eb72aae16c4da3a9e75f54c181efad56b78`.
Only 923 bytes differ from the preceding ROM, within round-one art/templates
and the checksum. Symbol addresses and the 4 MiB ROM size are unchanged.


### Background review display profile corrected (2026-10-08)

The atlas and main review previously compared a Standard-profile Normal donor
against a Vivid-profile BC preview. That presentation could imply a BC-specific
recolor even when palette words were unchanged. Both Genesis columns now use
Standard colors; the original PCE reference remains unchanged. All 689 cards
and their stable IDs remain, and persistence/export/filter checks pass. This
changes review artifacts only, not the ROM, game palettes or user decisions.
The corrected round-two page visually confirms matching donor/BC colors where
the indexed artwork is reused. Semantic correspondence still needs review.

## Final-chamber background correspondence corrected

Round ten previously substituted zone-one gray/cyan machinery for the PCE
mechanical face. The corresponding Normal drawing is in zone 21, map rectangle
(4,10), size 4×5 metatiles. BC now reuses that complete drawing and the repeating
zone-21 rib texture, preserving its original palette and shades. Cell-level
PCE redraw/offset differences are not interpreted as a need to recolor or chop
up the intact Genesis face. The face is static scenery, separate from the
original-PCE serpent and attacks.

All 20 BC source IDs resolve to ten exact/mirrored Normal blocks. Existing
metatile flip bits share symmetric halves; no renderer changes are needed.
`qa_bc_final_chamber.py` verifies the full composition against the Normal map
independently of the generator's donor list. The full review retains stable
card IDs and user decisions; round-ten notes identify the corrected match.
Comparison: `.local/bc-final-chamber/index.html`.

## Shared storage preserves current artwork

The BC background generator now shares byte-identical pattern/template blocks
across rounds. All 689 mapped source cells retain their pixels, palette banks,
priority and mirror bits. Palettes remain per round. Review card IDs and user
choices are unchanged. This is storage consolidation to make room for remaining
art corrections, not new evidence that existing round-eight substitutions are
correct. Current verification: `.local/bc-background-pool/equivalence.json`.

Round-eight investigation confirms the red pipe lattice has direct Normal
zone-16 counterparts. The blue cylinders share the mechanical-cylinder subject,
but PCE's repeating cylinder spans three cells while Normal's spans two; blindly
matching individual cells produces wrong seams. Compare complete components
before authoring those replacements. Source and Normal composite references are
in `.local/bc-background-final-review/{pce-r8-strip,normal-r8-strip}.png`.

## Round-eight machinery correspondence implemented

The red pipes and crossed panels now reuse their matching Normal zone-16
quadrants instead of generic zone-one machinery. The authored composition is
`tools/data/bc_background_r8_materials.json`; `bc_background_r8.py` copies the
original Normal tiles and palette-bank attributes. There is no recoloring.

The PCE cylinder repeat is three 16-pixel quadrants wide versus four in Normal.
The authored layout shortens the barrel between fronts, retaining all four
original quadrants of the complete Normal circular front (23:3, 24:2, 27:1,
28:0). This is an adapted Genesis cylinder, not a PCE-pixel import. The 62
material-pattern recipes cover all 45 retained source IDs; unmapped source
IDs stay unmapped. ID 0x81 remains a pipe filler outside the sampled route.

`qa_bc_r8_materials.py` checks source descriptors against the linked PCE bank,
all 180 copied material quadrants, intact circular fronts, palette preservation,
and unchanged other-round/Normal content. Native samples cover 30 cameras.
The full review keeps its stable user-choice IDs and shows the assembled
Genesis composition for round eight, avoiding a misleading single-donor pair.
Comparison page: `.local/bc-r8-materials/index.html`.


## Round-nine chamber materials (October 8)

Replaced unrelated zone-one machinery with the corresponding Normal zone-19
oval chambers, floating panels and ornament. The versioned recipe in
`tools/data/bc_background_r9_materials.json` copies whole 8-pixel characters,
with explicit flips and unchanged palette banks. PCE repeats its chambers
more narrowly than Normal; repeated shaft sections and well widths are
adapted at character boundaries. No background recoloring or pixel resampling
is applied. This does not assert pixel-identical PCE geometry.

The 49 cells pass 50,176 material pixel checks and 103 native camera checks.
Source collision/script banks and the other nine rounds remain unchanged.
Four-player HuCard preserves 600 state/workload records and slightly reduces
sample video frames (873 to 871). Original PCE bosses and attacks remain intact.
The review retains existing decision IDs and shows the assembled material
composition for round nine, avoiding a misleading single-donor comparison.
Evidence: `.local/bc-r9-materials/`. Full-speed/release work remains open.


## Lossless mirrored background storage (October 8)

`bc_background_mirror.py` consolidates exact mirrored material blocks using
existing whole-cell flip bits. It preserves palette banks and the inactive
character sentinel; source map/collision data remains intact. All 689 cells
compare identically after decoding the stored blocks and flips. Native checks
cover 499 cameras in all ten rounds. This creates 12,800 linked bytes of room
for the remaining material replacements without dropping art. The bounded
four-player HuCard round-nine sample costs seven extra video frames (871 to
878 for 600 updates); this small regression is recorded for later performance
work, not described as a speed improvement. Evidence: `.local/bc-mirror-pool/`.


## Round-four corresponding organic scenery (October 8)

Normal zone 6 supplies the grass-topped ledges, organic rocks, attached weapon
and machinery details, vertical supports, and complete paired oval machine.
These replace unrelated zone-one stone/robot-face substitutions. The original
Normal palette is retained exactly. The isolated boulder is sampled smaller;
whole 8-pixel characters adapt the oval machinery without losing palette-bank
colors. This is adapted Genesis artwork, not exact PCE geometry. The first
shrunk RGB machinery draft was not imported: it mixed both palette banks in
single characters. The retained composition avoids that problem.

`tools/bc_background_r4.py` contains the material composition and palette-bank
checks. The renderer's inactive zero template is avoided for nonempty PAL0
first characters by storing a mirrored character with its hardware H-flip bit.
The palette and all 25,600 resulting pixels are verified in the ROM; native
checks cover 58 camera positions. Other rounds and source stage/collision data
remain unchanged. Original PCE bosses and their attacks are unaffected.
Four-player HuCard has identical 600 simulation/workload records, with six
extra video frames in this sample (1,113 to 1,119). Full-speed work remains
open. The review shows assembled components and keeps existing decision IDs.
Evidence: `.local/bc-r4-materials/`.


## Normal/BC background source sharing (October 8)

BC now references 113 exact Normal pattern blocks at their original aligned
ROM addresses instead of storing duplicate pixels. It keeps 138 BC-only
blocks, with 251 logical template/remap entries. The shared renderer accepts
an optional source table on explicit stage setup and clears it for Normal,
Boss Rush and reset. A cache miss reads one pointer; there is no decompression.
All current artwork and source collision/script data are unchanged. This frees
56,832 linked bytes for the detailed round-three draft and later replacements.

All 689 source cells and the full logical pattern bank compare identically.
Native tests cover all ten rounds / 499 cameras, mode handoffs, and original
PCE bosses/attacks. Normal's ten four-player samples preserve 6,010 state and
render records and all frame counts, with two additional worst-case scanlines
in three sections. Full-speed acceptance remains open. Evidence:
`.local/bc-normal-storage/`.


## Detailed round-three cyan cavern (October 8)

The zone-3 Normal cavern supplies detailed cyan rock, embedded rails, striped
supports and yellow emitters at the original PCE cell positions. Whole 8-pixel
characters preserve the original palette colors and shading. Subject review
rejected automatic matches that substituted purple blades for emitters or
circular panels for striped supports. The corrected donor recipes are in
`tools/data/bc_background_r3_materials.json`. Source IDs 0–80 follow the primary
pattern table; 81–130 retain defensive machinery fill for expanded viewport
margins rather than copying stray pattern fragments in those source captures.

The linked material check compares all 134,144 pixels to the specified Normal
donors, including character flips and the PAL0 inactive-template workaround.
All other rounds, Normal material blobs and source script/collision banks stay
unchanged. Native camera checks cover 57 positions. The four-player HuCard
sample preserves 600 simulation/workload records with two extra video frames
(708 to 710). This is an adapted material composition, not a claim that PCE
and Genesis drawings are pixel-identical. Original PCE bosses and attacks
remain imported and pass the current-ROM tests. Full-speed work remains open.
Evidence: `.local/bc-r3-materials/`.


## Round-five corresponding cavern materials

The zone-one placeholders are replaced by Normal zone-10 pink and purple rock,
skulls, bones and machinery. Original Normal palette words and donor character
shades are preserved. Pattern/palette pairs remain distinct, and decorative
objects are assembled as complete subjects before adapting their dimensions.
This is an inferred match under the user's existing reuse policy, not a new
user approval. The PCE boss and attacks remain original imports.

ROM `67da8b9464208872b2c9ec88a91f3a81a80a73900fc8350a3acfe91a41cd8ae5`:
73 cells / 74,752 material pixels, 36 native camera positions / 44,352 subtiles,
unchanged source banks, 616 unchanged other-round cells and 113 Normal blobs.
Four-player HuCard preserves 600 simulation/workload records and the same 853
video frames; full speed remains unverified. Review:
`.local/bc-r5-materials/index.html`. The main review shows actual assembled
round-five cells and retains stable decision IDs.


## Exact-character storage reuse

ROM `ae67a8c4686ca91bdb222fbca96d517fe062cbe1834f161071c24388990ecb90`
repackages exact eight-pixel characters into existing Normal blocks or shared
private DMA blocks. This changes storage, not artwork decisions. All 689 cells,
705,536 pixels, 320 palette words and 113 Normal blobs remain identical.
The actual loader passes 499 camera positions with reserved PCE boss banks.
No recoloring, new shapes or runtime conversion is introduced. Review renderers
now follow template character indices, so the review matches repacked ROM data.
Evidence: `.local/bc-character-storage/`.


## User correction: posterized shading and broken wall joins

The user rejects the flat pink/purple shading and mismatched round-five window
parts. Converted-Normal pixel equality is insufficient: the shared quantizer
already discarded source shades and mapped neutral highlights to green.
Audit shading across backgrounds and sprites, including BC variants. Keep
original material hues while preserving distinct shade steps where possible.

The current wall fix uses all four quadrants of Normal metatile 61 as one
window and matching wall-frame halves. ROM
`9325951092e1f6941f0bcb031a37a5c4d629e8afca35aeb6afd0c901ca516f2a`
passes native rendering and four-player HuCard regression. This fixes assembly,
not shading. The rock-ramp palette experiment is rejected for production because
it flattens machinery; `.local/shading-audit/index.html` labels it accordingly.


## R5 source-shade restoration

The retained R5 conversion now works from the original Genesis-port source
characters, before global Normal quantization. It preserves the user's reuse
geometry and complete windows but fits a round-specific background palette.
Protected bank assignments keep the five pink/purple rock steps distinct and
preserve neutral highlights and blue texture. The gradient retains four of five
native-gamut colors, with lower source error than the old four-color result.
The selected fit improves source RGB error for every used material group;
earlier experiments that worsened machinery were not retained.

ROM `e2e77365c2189263b8162c617202b28fba0e335793c5053c3fa57a03ceda8bc1`
passes 74,752 source geometry pixels / 53,949 protected shade pixels, native R5
rendering and unchanged four-player HuCard simulation/workload/frame-count
checks. Other rounds and Normal assets are unchanged. This does not close the
user's request to audit shading everywhere or constitute new art approval.

## October 8: Vivid display shade guard

The source-ramp repair alone did not guarantee that default Vivid mode preserved
its shades: the later saturation/brightness lookup could merge or reverse them.
`tools/build_vivid_palette.py` now runs after all Normal and BC generators.
It protects componentwise palette steps and explicit BC material ramps, using
Standard colors when necessary. It does not alter user asset decisions or
claim that upstream quantization is fixed. No runtime computation was added.
The cartridge changes only its Vivid table and checksum; native Standard/Vivid
checks cover all ten rounds, and the four-player HuCard R5 workload/timing is
unchanged. Comparison: `.local/vivid-shade-guard/index.html`.

## October 8: R6 corresponding materials and exact source shades

The generic zone-one draft is replaced with Normal zone-13 shaft materials.
`tools/data/bc_background_r6_materials.json` records all 131 cell compositions
as whole Normal 8-pixel characters. The connector uses all four quadrants of
Normal metatile 48; the main curved housing uses metatile 8. Central characters
from diagonal donors 24/29 replace the incorrect blank quarter that broke rails.
These are inferred correspondences, not new user approvals.

Only source palettes 7 and 14 are used. `tools/bc_background_r6.py` preserves both
complete RGB3 palettes, with a bijective pen permutation to reuse existing bytes.
No PCE pixels, new recoloring, merged shades or runtime conversion are introduced.
Linked-ROM checks compare all 134,144 geometry pixels and all 76,272 opaque shade
pixels directly to the source. Native coverage checks 23 cameras / 29,280 subtiles
with the six-block boss reserve. All other round materials and Normal blobs remain
unchanged. Review: `.local/bc-r6-materials/index.html`.

The protected 4P HuCard R6 sample preserves simulation/workload but needs one
extra video frame over 600 updates (1124 to 1125). Performance is still open.
The retained ROM has 6,972 bytes free; remaining assets require more space recovery.

## October 8: full character-block capacity

The packer now shares full sixteen-character sets when the template attribute
bits make index zero safe. It records every PAL0/low-priority character that
cannot occupy zero and separates groups with conflicting requirements. Twenty-
five private blocks are removed (12,800 bytes), with no changes to art, palettes,
source maps or the runtime renderer. All 689 cells are pixel-identical to the
R6-material build; native coverage passes 499 cameras and the protected R6 4P
HuCard sample preserves all 600 scene timings and 1,125 video frames. Evidence:
`.local/bc-character-capacity/`.

## October 8: R7 corresponding foundry material

The zone-one placeholder bank is replaced with original Normal zone-14 foundry
material. Source palette 17 retains every RGB3 shade without further fitting.
The faceted wall uses the corresponding Normal 54 material, clipped only at
reference row envelopes. Machinery, lava and columns reuse original characters;
complete 27/38/42/47 assemblies are kept where applicable. Recess frames adapt
Normal 44/45 pieces and remove unrelated green/blue backdrop inside openings.
The four wider-viewport defensive fills are identified separately in the recipe.
No PCE interior texture is copied and no source collision bank changes.

Linked checks cover 63 cells, 64,512 geometry pixels, 40,864 retained shade pixels
and 1,008 contour rows against the source. Native R7 coverage passes 30 cameras /
36,736 subtiles with the boss bank reserved. Other round art and Normal blobs
remain unchanged. The protected 4P HuCard R7 sample preserves 600 state/workload
records and the same 986 video frames; all twelve late flushes are in VBlank.
Comparison: `.local/bc-r7-materials/index.html`. This is inferred correspondence,
not new user approval; R2, broader shading, performance and parallax remain open.
