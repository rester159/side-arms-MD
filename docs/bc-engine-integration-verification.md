# BC shared-engine integration verification

BC now runs through the regular Genesis engine's frame executor, session
lifecycle, player storage and simulation scheduler. Both modes use the actual
shared projectile collector and ordered hit-query implementations, alongside
the existing shared enemy arena, traversal and graphics backend.

This is a rules variant, not an art-only reskin. BC retains its source movement,
weapons, enemy AI, stage scripts and contact cadence. The exact ownership and
remaining content work are documented in [bc-shared-engine.md](bc-shared-engine.md).
This does not make the broader additions release-complete.

## Build

Cartridge: `out/release/rom.bin`.

SHA-256: `0931a57e41252cd0c26b1d1508c306f5becffc7adaf72fb0f0887ddfd44609b1`.

The private build and main build produce the same cartridge. `tools/check`
rebuilds every game source successfully with no source/header warnings. The player union
saves 1,128 bytes of permanent RAM without reducing either mode's weapon storage.
The engine acquires/releases extra BC player records at session boundaries.

## Behavior checks

Evidence for this exact cartridge is under `.local/engine-priority-qa/direct-*`.
Earlier `final-*` files describe an intermediate callback-scheduler build and
must not be attributed to this cartridge.

- Long native controller replays preserve every canonical gameplay state:
  160,172 solo updates and 96,088 four-player updates. Both recorded routes
  complete without divergence (166,794 and 145,765 video frames respectively).
  These recordings are not proof of a complete ten-round campaign.
- All four player-count configurations pass Normal/Boss Rush entry, wave/health
  scaling, player joining, multiplayer merges, save/reload and old-save migration.
- All four BC configurations pass menu cancellation, launch, every selected
  controller's pause/freeze/resume, terminal return, re-entry and paused reset.
- Populated Normal and active Boss Rush worlds can enter four-player BC, release
  its peers and shared storage, and restart Normal correctly. Debugger aliases
  resolve to the shared engine-owned player and stage records.
- Limited/unlimited continues and simultaneous four-player requests pass,
  including independent scores, ranks, credit consumption and input inhibition.
- The actual native 68000 collector passes 4,096 complete index comparisons,
  including dirty padding, coordinate fractions, high-byte rejection, source
  immutability and output sentinels. Host collector and party-frame checks pass.
- The round-ten four-player 2,000-update stack probe reports no peer-allocation
  overlap, with a 13,630-byte minimum gap. This bounded route is not whole-game stack certification.
- All 40 Normal section/player-count samples preserve baseline gameplay and
  ordered sprite/pixel hashes, with no sprite submission drops or runtime remaps.
  These are 1,000-update samples, not complete campaigns. 1P/2P compare against
  `950214fe...`; 3P/4P compare against the pre-integration `aec8b800...` build.

## Timing limits

Measurements use stock-clock Genesis Plus GX. BC openings have 300 warmup and
600 measured updates, protection and periodic fire. Normal samples measure
1,000 updates. No measurement errors occurred; the timing commands return 1
because their full-speed gates are not met.

| Mode | Players | Total frames across ten samples | Worst sample |
|---|---:|---:|---:|
| Normal | 1 | 10,010 | 1,005 |
| Normal | 2 | 10,013 | 1,005 |
| Normal | 3 | 10,011 | 1,005 |
| Normal | 4 | 10,101 | 1,038 |
| BC | 1 | 6,004 | 602 |
| BC | 2 | 6,018 | 612 |
| BC | 3 | 6,081 | 625 |
| BC | 4 | 6,991 | 919 |

Against the pre-integration opening samples, BC 3P changes from 6,062 to 6,081
frames and 4P from 6,782 to 6,991 (about 3.1% more frames). Normal 3P remains
10,011; 4P changes from 10,094 to 10,101. This integration is not a performance
improvement. Direct phase expressions avoid runtime callback dispatch, but
further native optimization is required, especially in dense BC combat.

## Outstanding additions

Full-speed 3P/4P, composite/background artwork auditing, HuCard synthesis polish
and physical multitap/console verification remain open. HuCard playback and its
saved selector have since been implemented, and the ordinary-sprite review is
complete. See the broader [additions inventory](2026-10-07-additions-status.md)
and [HuCard evidence](hucard-soundtrack.md) for the later work.

## Final-round actor traversal experiment (reverted)

The experimental final-round actor pass advanced its typed pointer alongside the slot
number, instead of deriving the actor address from the byte index each time.
It still uses the shared `ENEMY_PASS_CORE` loop and live-state gate. The initial
slot bound is checked before forming a pointer, and visits, births, retirements,
callback order and early exits retain their existing semantics. Other actor
loops keep their original traversal until separately measured.

Baseline ROM `250a964f9031055ae1916652fa8edc7a022b5d6818ff8e46240d47fcc1930b3a`
versus candidate `0fbcd462929371fab3140899d7f085fc4d1e944aa21ac6e8d08fc347c320b4fe`:

| Final-round sample | Updates | Baseline frames | Candidate frames |
|---|---:|---:|---:|
| 4P, after 300 warmup updates | 600 | 690 | 689 |
| 4P, after 1,000 warmup updates | 1,000 | 1,141 | 1,137 |
| 3P, after 300 warmup updates | 600 | 637 | 636 |
| 1P, after 300 warmup updates | 600 | 603 | 604 |
| 2P, after 300 warmup updates | 600 | 617 | 619 |

All 3,400 per-update normalized simulation hashes and workload records match,
including actor, weapon and submitted-sprite counts. Mean scene cost improves
about 0.44–0.48%. Separate uninstrumented four-player long replays confirm the
1,141 → 1,137 frame result. Three-player instrumented/native final-RAM replay
also agrees. These protected, periodically firing samples are limited tests;
the optimization does not achieve full-speed play. The 1P/2P samples reduce mean
scene processing cost but regress total elapsed video frames by one/two; this
frame-pacing result remains unresolved and must not be presented as an across-
the-board speed improvement. Their state/workload traces also match exactly.

Evidence: `.local/bc-perf-actor-pointer-comparison.json`, the baseline/candidate
budget directories, and `.local/bc-perf-actor-pointer-plain-long.json`.

### Isolation follow-up and restoration

Restricting pointer traversal to 3P/4P required a second compiled loop and a
per-pass dispatch. The 600-update samples became 603/620/637/691 frames for
1P/2P/3P/4P, versus the original 603/617/637/690. All 2,400 state/workload
records matched, but the dispatch erased the four-player gain and retained a
two-player regression. Neither candidate is kept.

`src/bc_runtime.c` and `inc/enemy_pass.h` were restored from the saved baseline,
and the rebuilt ROM is byte-identical to baseline
`250a964f9031055ae1916652fa8edc7a022b5d6818ff8e46240d47fcc1930b3a`.
This preserves all completed sprite and HuCard work while removing the traversal
experiment's regressions. Evidence: `.local/bc-perf-pointer-isolation-results.json`
and `.local/bc-perf-pointer-restored-build.log`.

The next performance investigation should account for `finish_frame`'s bounded
late-VBlank DMA windows: lower scene cost alone did not monotonically improve
elapsed frames. Those queue/scanline limits protect video correctness and must
not be widened without DMA timing and rendered-output evidence.

## Late-VBlank window experiment (reverted)

`profile_bc_budget.py --video-trace` now records VDP VRAM, CRAM and VSRAM hashes
after each completed VBlank process. `qa_bc_frame_pacing.py` compares these,
normalized simulation state, workload, total video frames and late-flush end
scanlines. Its frame-regression assertion intentionally rejects a candidate
even if its state and video output are identical.

Extending only the one-transfer/288-byte late window by one raw V-counter line
(`240` → `241`) produced these final-round measurements:

| Sample | Baseline frames | Experimental frames |
|---|---:|---:|
| 1P, 600 updates after 300 warmup | 603 | 603 |
| 2P, same | 617 | 617 |
| 3P, same | 637 | 637 |
| 4P, same | 690 | 687 |
| 4P, 1,000 updates after 1,000 warmup | 1,141 | 1,143 |

All 3,400 simulation/workload and post-flush VDP-memory samples matched, with
no measured late flush entering active display. Nevertheless, the longer
four-player timing regressed, so `src/main.c` was restored. The short opening
improvement is not a release performance improvement. The standard build is
again byte-identical to `250a964f...`; the profiler and comparison tool remain.
Evidence is in `.local/bc-dma-window-baseline*`, `bc-dma-window-candidate*` and
`bc-dma-window-comparison*.json`. The long comparison exits nonzero by design.

## Small-sprite bucket experiment (reverted, October 8)

The current final-round profile still attributes 11.20% of measured cycles to
actor drawing. An experiment extended the existing large-sprite hash-bucket
cache to small actor sprites, retaining the repeat-key shortcut, residency
checks, clipping, upload limits and submission order. It required no additional
actor-cache RAM. The host cache tests passed, including slot reuse and origins.

Nevertheless, final-round timing regressed for every tested party size:

| Sample | Baseline frames | Experimental frames |
|---|---:|---:|
| 1P, 600 updates after 300 warmup | 603 | 606 |
| 2P, same | 617 | 623 |
| 3P, same | 637 | 642 |
| 4P, same | 690 | 699 |
| 4P, 1,000 updates after 1,000 warmup | 1,141 | 1,152 |

All normalized simulation/workload and post-flush VDP-memory traces match;
the comparison rejects only the slower frame counts. The source changes were
reverted. The baseline and candidate ROMs, symbols, source and traces remain
under `.local/bc-small-bucket-{baseline,candidate}/`, with the comparison in
`.local/bc-small-bucket-comparison.json`. Do not reintroduce this cache extension
based on reduced hashing alone; complete native timing contradicts that benefit.
