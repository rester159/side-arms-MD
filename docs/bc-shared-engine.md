# Before Christ as a regular-engine mode

BC runs as a rules variant of the native Genesis engine. It is not an art-only
reskin: its fractional movement, charge/return/options weapons, source wave
order, collision cadence, boss behavior and ending remain BC-specific rules.
No PCE CPU emulator executes in the cartridge.

## Engine ownership

| Engine responsibility | Implementation |
|---|---|
| One frame executor and completion path | `game_frame` in `game.c`; `main.c` samples input once and finishes one VBlank transaction |
| Session entry, pause authority and ordered release | `flow_session.c`; menu requests take effect on the next frame, and exit input cannot activate the rebuilt menu |
| Simulation scheduling and early stops | `engine_step.h`; Normal and BC instantiate level/player/actor/finish policies, preserving checkpoint and audio-wait stops |
| Player and weapon storage | `PlayerArena` in `player.c`; Normal's four records and BC's primary record share a typed union, with BC peer allocations acquired/released by the engine |
| Level/camera state | `level.c` owns Normal's `Level` and BC's fixed-point `level_bc`; each mode retains its content decoding and timing rules |
| Enemy storage/allocation | One 2,880-byte `EnemyArena`, typed views, shared ordered free-slot allocation |
| Actor traversal | `enemy_pass.h`, specialized for native record formats and ordering |
| Projectile candidate collection | `enemy_shot_index_impl.h`, used by the actual Normal and BC native collectors |
| Ordered projectile-hit processing | `enemy_shot_query_impl.h`, with mode-specific geometry, protection and damage policies |
| Graphics submission/background streaming | The existing sprite cache, SAT, DMA and background engine |

The shared player arena occupies 1,144 bytes instead of separate 1,128-byte
Normal and 1,144-byte BC allocations, saving 1,128 bytes. Extra BC controllers
are still allocated after temporary boot-font buffers are released. Each rules
variant retains its native records, including BC's 28 main shots and two options;
there is no per-frame record conversion or reduction of weapon capacity.

Normal C code accesses `normal_players`; BC accesses `player_arena.bc` and the
engine-owned peer allocation. `players` and `player` remain debugger aliases.
Consumers must use the selected type's length rather than assuming an alias's
ELF size equals that view's size. `stage` is a debugger alias of `level_bc`.

BC's scene policy no longer allocates/frees players, owns an independent active
session, reconstructs the frontend, or intercepts `main`. It supplies BC control
and content behavior to the engine. Normal's animation clock remains frozen
through BC-owned frames. The engine retains the current frame's owner across
menu launch and release, and paused BC frames hold the completed display without
advancing score, RNG, camera, actors, weapons or ending clocks.

The phase scheduler uses direct, typed phase expressions at compile time. The
native build inlines phase policies; it does not add per-entity virtual dispatch. Solo BC runs
a level/wait phase followed by the same scheduler's player/actor/trail phases.
Co-op schedules all four phases together, preserving deferred wave barriers,
allocation retries, targeting and independent checkpoint waits.

## Shared background source storage

The same background renderer streams Normal and BC through its 56-slot cache.
`bg_set_stage` optionally accepts a table of aligned 512-byte ROM block sources;
Normal continues to use contiguous zone tiles. BC's 361 logical blocks currently
reference 140 existing Normal blocks and 195 unique private blocks (221 private
references). Exact eight-pixel characters can be shared within a source block;
the template indices select their positions. Per-cell templates,
flip bits and per-round palettes remain independent of storage. Source lookup
occurs only on cache misses; no PCE emulation or runtime decompression is added.
Normal/Rush entry and session reset clear the optional table. Native tests check
both pixel/DMA identity and populated Normal → BC → Rush → BC → Normal handoffs.

## Rules that intentionally differ

The shared engine does not replace BC movement or weapons with Normal's arcade
algorithms. Normal's integer terrain retries and nine-shot records cannot encode
BC's fractional wall interaction and charge weapon faithfully. Player/weapon
kernels, outer body/party contacts, stage content decoding and enemy family AI
remain typed rules implementations. Candidate builders and projectile reaction
traversal are genuinely shared; their collision arithmetic, source order and
cadence remain mode policies. Sharing these responsibilities does not require
making unlike gameplay rules identical.

Simulation and presentation remain fused within BC's frame policy. The previous
obligatory update/draw split added native calling and register-spill overhead.
The current integration shares authoritative session and simulation ownership
without requiring that expensive boundary or adding a second DMA/video flush.

This architectural change is not a 60 FPS fix or completion of the graphics
remaster or HuCard soundtrack. Native replay, mode-handoff, rendering, stack and
timing evidence is recorded under `.local/engine-priority-qa/`.

## Graphics matching and remastering

Existing BC graphics are manual adaptations, not a verified identity map. The audit under
`.local/bc-asset-matching-review/` includes 689 background source IDs across all ten rounds,
50 original/Normal/current-BC comparison pages, and an enemy manifest covering 45 source
base IDs. The original background decoder was checked against captured PCE nametables.

The current background materials use Normal zones 0, 1, 3, 6, 10, 13, 14, 16,
19 and 21 as the respective donor sets for BC rounds 1–10. Round 2's cave and
small-machine geometry includes BC-specific patterns with Normal material
colors; its compound housings use corresponding Normal halves. Round 6 now
uses zone 13's complete connectors, housings and both original source palettes.
Round 7's 61 reachable cells now match the original BC geometry and RGB3 colors
exactly, replacing the mismatched floor and machinery substitutions. The
per-round manifests distinguish imports from adapted Normal material reuse.
The converted Normal set has 24 zones and 1,344 metatiles. Including
the authored organic zone gives 25 zones and 1,623 metatiles. Match all relevant existing
art before creating a replacement. Numeric similarity is only a review aid: water, lava
and machinery can rank highly while depicting the wrong subject. Record matches as verified
reuse, adapted reuse or new artwork required, with source IDs and explicit transforms.

The first corrected family is round-1 cells `0x20`, `0x21`, `0x22`, `0x3A` and `0x3B`.
Their new contours use Normal zone-0 stone/rock materials and preserve source quadrant
composition. The old metatile-79 substitution gave the wrong rock orientation and corner;
flipping that whole tile was insufficient. The contour/provenance manifests under
`tools/data/bc_background_r1_*` distinguish authored shapes from verified material reuse.
Native camera/VRAM checks pass, and the bounded replay and Normal4P timings are unchanged.
Other stage artwork remains under review. All nine BC boss bodies, composite
attacks, dedicated/shared boss projectiles and the final serpent now import
original PCE geometry; they supersede the earlier inferred Normal substitutions.
Their shared Genesis sprite palettes preserve ordered shading, with some hue
differences. See the current cartridge evidence in `expansion-acceptance.md`.

The first reviewed ordinary families reuse Normal artwork: homing enemy `0x3684`,
trooper `0x3686`, jet `0x368C`, and launcher `0x3688`. Pose correspondence does not
establish identical AI. The launcher's corrected mapping now uses existing Normal
poses with an XOR horizontal flip for the standing/airborne frames. All 28 pose/flip
combinations pass native SAT and exact VRAM checks; the generator preserves every
existing pattern and palette assignment while adding two composites and eight cells
(2,048 pattern bytes). The durable mapping is `tools/bc_sprite_matches.json`.
Five launcher poses were decoded
from the resident source pattern bank; only offsets `0x20` and `0x28` were also
matched to live actor/SAT observations in the scoped capture set.

Round-1 source cell `0x3A` is exactly the right half of `0x20` followed by the left
half of `0x21`; `0x3B` combines `0x21`'s right half and `0x22`'s left half, and
`0x22`'s right half equals `0x20`'s left half. Those relationships now hold in the
generated Genesis pixels too, with source collision data unchanged.

Use our existing robot/enemy/background pixels where they match. Author genuinely missing
shapes and poses, retaining BC's collision geometry and animation timing. Refit colors
within the actual Genesis CRAM allocation; the current sprite/HUD banks do not provide
an expanded simultaneous palette. Preserve four-player identification and HUD readability.


R5 shading restoration fits the reused source characters into its own two
background palettes before Normal's global quantization. This recovers distinct
rock ramps without recoloring Normal or changing runtime rendering. BC does not
use the Normal starfield here; its unused star colors are not reserved in that
fit. The broader shading audit and performance-gated tiled-background parallax
extension remain open.
