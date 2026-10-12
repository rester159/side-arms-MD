# Additions verification — October 7, 2026

The requested additions are **not release-complete**. This is the pre-integration
build baseline; the later [shared-engine verification](bc-engine-integration-verification.md)
supersedes its cartridge and architecture status. Baseline cartridge SHA-256:
`aec8b8004e372223d8aa6eb7dcd0cd70142a66e4e93196d79dd4886bdd095d1d`.

## Retained fixes

- The standard build regenerates all 14 BC generated C resources, ordered after
  the Normal graphics conversion. Previously it depended on leftover generated
  round/background/ending/font files.
- The organic preview now runs after its starfield and zone-palette inputs exist.
  A genuinely clean build previously failed while reading `star_tiles.bin`.
- Missing BC reference captures and the caption font are reported before asset
  generation. Private snapshot builds use the same complete pipeline and retain
  the build log and failing exit status.

An isolated `make clean` followed by `make -j4` succeeds and produces exactly the
same cartridge as the tested main build. All 14 BC generated files also match
their pre-change hashes. These are build fixes, not gameplay optimizations.

## Current checks

- Warning-free game rebuild.
- `qa_multiplayer.py --players N`: passes for N=1,2,3,4, covering Normal and
  Boss Rush entry, selected team starts, wave/health scaling, merges and saves.
- `qa_bc_menu.py --players N`: passes for N=1,2,3,4, including modal cancellation,
  entry, each selected controller's pause/resume, frozen state, and menu return.
- BC music mapping and native audio scene checks pass for the existing arcade
  replacements. They do not verify or supply a HuCard soundtrack.
- Normal timing: ten sections per count, 1,000 measured updates each, 3P/4P,
  including render traces. No measurement errors, submitted-sprite drops, or
  runtime remaps. Worst samples: 3P 1,005 frames (99.50% simulation speed),
  4P 1,035 frames (96.62%). These are bounded tests, not entire campaigns.
- BC timing: all ten round openings at 3P/4P, 300 warmup updates and 600 measured
  updates, protected players and periodic fire. No measurement errors. Worst
  samples: 3P 621 frames (96.62%), 4P 873 frames (68.73%). Both matrices exit 1
  because their full-speed gates fail.

Evidence is under `.local/finish-additions-qa/`, with the clean-build log under
`.local/build-finish-additions/clean-build.log`.

## Still required

1. Sustained stock-clock performance, especially BC four-player combat. The
   existing projectile batch review identifies useful shared rendering work,
   but its entire measured cost is smaller than BC's frame-budget deficit.
2. Source-grounded BC artwork work described in
   [bc-shared-engine.md](bc-shared-engine.md). Frame/session ownership, player
   storage, the simulation scheduler and projectile collector have since moved
   into the regular engine; see the linked integration verification.
3. HuCard music source, transcription/conversion, native playback, selection,
   persistence, and sound tests. No HuCard ROM/music rip was found in the project
   tree or Downloads. The local CD reference and its BIOS are different inputs.
4. Physical multitap and console verification; current controller regressions
   inject logical pads and do not certify hardware adapters.

No release-complete claim or new distribution package is made.

## HuCard source follow-up (October 8)

The missing-source statement above is superseded: the USA HuCard has now been
found in Downloads, extracted and verified. All 18 distinct scores and 32
instruments are decoded, and score timing matches 18 original-driver captures.
Native Genesis playback and the saved Home selector are now implemented, with
source-based gameplay mapping and 3P/4P checks; see
[hucard-soundtrack.md](hucard-soundtrack.md) for exact evidence and remaining gates.

## Ordinary sprite review follow-up (October 8)

The 204-card ordinary-sprite review inventory is implemented: 131 recolors,
45 unchanged Genesis sprites, and 28 BC-specific shapes where the old proposals
did not match. Incorrect robot/pod, pickup, missile and projectile pairings have
been corrected. All 134 explicit user choices are preserved. Palette conversion
retains ordered shade ramps. See [bc-art-review-decisions.md](bc-art-review-decisions.md)
for source correspondence, versioned recipes, cartridge hashes and validation.

This completes that review inventory, not the release artwork gate. Composite
bosses, player/weapon comparisons and background identity still require audit;
the HuCard synthesis/transition and stock-clock performance gates also remain.
