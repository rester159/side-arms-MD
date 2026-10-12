# Home multiplayer QA — 2026-10-03

**Status: functionality implemented; the required 60 fps / 100% speed is not met.**
Do not treat this build as performance-complete.

## Functional checks

`tools/check` rebuilt the game without warnings. `tools/qa_multiplayer.py --players N`
passed for N = 2, 3 and 4 against the final build:

- Real Home/options menu selection, all selected players joining and playing.
- Four single-enemy wave records produce 4 / 6 / 9 enemies respectively.
- Boss Rush begins with 20 / 30 / 45 hits per energy bar respectively.
- P3/P4 merge (P3 solo merge in 3P), while P1 remains independent.
- SRAM player-count save/reload, and version-3 save migration preserving old settings.

Additional checks compared all 65,536 byte-expanded terrain cells in the built ROM with
the original packed bitmap, and 100,000 deterministic collision cases with the original
interval predicate, including the spatial bucket boundaries. Both passed.

Normal now starts the original stage timeline directly. The authored organic-map
preview remains in the source but does not replace normal gameplay. The performance
harness warps to individual sections to exercise scaled waves; Boss Rush exercises real bosses.
Controller input for additional players is injected through the logical pad hook. SGDK
Team Player / EA 4-Way Play mappings are implemented but require physical hardware testing.

## Performance gate

Reproduce with the stock-speed Genesis Plus GX core used by `tools/run_rom.py`:

```sh
.venv/bin/python tools/qa_multiplayer_perf.py --players 3 --sections 0-9 --frames 3000
.venv/bin/python tools/qa_multiplayer_perf.py --players 4 --sections 0-9 --frames 3000
```

Each configuration runs 3,000 emulated frames per section, after a 120-frame warp/loading
warm-up. Every selected player uses AUTO $11, fires continuously, and slowly steers;
invulnerability and lives are maintained to keep the load active. Later transitions count.
Speed is completed game-loop updates / emulated frames, not the host's rendering speed.
No CPU overclock is applied. These samples are not whole-game certification and do not
cover every weapon/merge combination. The harness exits nonzero on any missed update.

| Section | 3P missed / 3000 | 3P speed | 4P missed / 3000 | 4P speed |
|---|---:|---:|---:|---:|
| 1 | 4 | 99.87% | 47 | 98.43% |
| 2 | 7 | 99.77% | 154 | 94.87% |
| 3 | 48 | 98.40% | 329 | 89.03% |
| 4 | 143 | 95.23% | 680 | 77.33% |
| 5 | 2 | 99.93% | 47 | 98.43% |
| 6 | 67 | 97.77% | 286 | 90.47% |
| 7 | 5 | 99.83% | 16 | 99.47% |
| 8 | 19 | 99.37% | 443 | 85.23% |
| 9 | 280 | 90.67% | 730 | 75.67% |
| 10 | 292 | 90.27% | 810 | 73.00% |

Four-player section 4 also recorded 24 failed sprite submissions; all other sampled sections
recorded zero. No runtime sprite remaps occurred. This counter does not detect the VDP's
per-scanline sprite limit, so zero submissions lost does not guarantee zero visual flicker.

The opening-section four-player test improved from roughly 65% speed to 98.43% after the
optimizations below, but the broader gate exposes substantially heavier workloads.

## Changes made for performance

- Compact HUD caches individual fields instead of redrawing four panels.
- Shot candidates are bucketed by screen row in 3P/4P; exact hit bounds still decide hits.
- Cached sprite attributes have a fast lookup, and Home 3P/4P uses 19 large sprite slots
  with 48 small slots, using tiles freed by the compact HUD.
- AUTO volleys retain their cadence but use per-player phases to distribute work.
- Enemy templates are generated in runtime layout; terrain uses a byte lookup in ROM.
- Boss projectile loops stop at the highest occupied slot, avoiding idle full-pool scans.
- Home avoids an extra per-frame sprite occupancy estimate and rotates enemy draw priority.
- Sprite-table DMA uses the persistent SAT buffer directly; that buffer is not modified
  before the following VBlank flush.

## Remaining work

Map/zone transitions synchronously rebuild the visible background and can take more than
one frame on their own. Heavy multi-player combat and boss scenes also exceed the 68000
frame budget. A bounded background streaming transition and further object/collision/render
work are needed. Lowering spawn counts, slowing the simulation, or overclocking would not
satisfy the requested behavior and have not been used as substitutes.

## Player modal follow-up

Normal and Boss Rush now open a player-count overlay with 1/2/3/4-player choices.
B cancels without saving. Confirm saves the count and starts every selected player;
Start respects the highlighted menu action. The existing settings format also
accepts a saved one-player count and retains its legacy two-player migration.
The functional harness now covers all four counts through this dialog, including
cancel, normal enemy spawning, and immediate team starts without join inputs.
Before Christ remains unfinished and is not included in these gameplay checks.

A fresh four-player section-4 sample after the modal/team-start changes completed
2,458 updates over 3,000 emulated frames (81.93%, 542 missed updates), with zero
failed sprite submissions and zero runtime remaps. Enemy update/draw work dominates
its slow frames. This still fails the full-speed requirement; the changed starting
team timing makes this a fresh baseline, not an isolated optimization comparison.

2026-10-04 final-round direct terrain optimization: ROM e62d273e. Exact lookup
data reduced the measured later final-round 4P ordinary-fire sample from
1464 to 1341 frames/1000 updates and charged-fire from 1329 to 1271, with
all 2000 compared gameplay hashes matching. Normal's 40 samples retain all
40040 state hashes. Full speed remains unverified/unachieved; no player-count,
spawn-density, wave-order or boss-health reductions were used. See
`.local/bc-final-direct-map/verified.json` and the corresponding BC technical log.

2026-10-04 direct homing task (ROM 1801a927): round-8 4P later sample improved
1607→1500 frames/1000 updates with identical gameplay hashes; long 4P waves
9896→9737 frames, identical screenshots/spawn counts. All 40 Normal timings
and 40040 state hashes are unchanged. No actor/shot limits, waves, or HP scaling
were reduced. Full-speed requirement remains open; see
`.local/bc-homing-dispatch/verified.json`.


### Successful segment-birth shot indexing

ROM `e38f16a90e6a40b33e98af222d8ac974ed1868cf1d14ab271c282c35f9699bb6`
retains shot indices only during a successfully allocated eight-segment birth.
Stage births precede player updates, so the ordinary actor-pass indices were
absent here. The measured round-eight spike had no live shots, yet each segment
scanned all 28 slots per player. Building indices once for this batch cuts the
update-2951 scene from 2026780 to 1416856 core ticks (three video frames to two),
with identical gameplay state. Previous index pointers are restored afterward.
No collision order, spawn count, shot limit or damage scaling changes.
The birth-effect callbacks in production only deliver audio/score effects;
positions remain fixed during the batch, while consumed shots are rechecked.

An initial variant indexed every stage event. It increased the long route from
9708 to 9828 frames by charging ordinary events and failed allocation retries;
that implementation is rejected and archived under `all-events`. The retained
batch-only version improves the round-eight 1000-update sample 1489→1487 frames
and its 5404-update route 9708→9699, preserving 152 original/184 extra births,
2253 allocation blocks and both screenshots. All 1000 gameplay hashes match,
and independent full-RAM replays pass. Normal-damage round four remains
348 frames/300 updates with all gameplay hashes matching.

`qa_bc_segment_birth_index.py` compares the production path against the original
eight-contact loop in 384 cases: six rounds, both variants, 1–4 players, empty,
live and mixed shots, preexisting indices, null party members, occupied prefixes
and failed allocations. It checks ordered callbacks, all gameplay state and
restoration of index pointers. Party routing/frame tests also pass. The
3000-update 4P round-eight native stack sample retains 1204 bytes of clearance
and no observed overlap. The 40 BC openings tie in 37 and cost one extra frame
in three; Normal has 39 identical timings and one one-frame improvement, with
all 40040 gameplay hashes identical. This is a targeted spike reduction, not
sustained full speed. Evidence: `.local/bc-stage-shot-index/verified.json`.


### Protected empty-party segment births

ROM `d708aaae5704b96dc1f3c45ace5393d5bc8406739351626c187a63ecafc3a0bc`
adds a temporary contact policy inside successful eight-segment births when
all living players are protected and have no eligible shots. Player protection
cannot expire during these contacts. The existing common-task fast path ticks
cooldown and damage protection once without scanning all player slots. The
previous party policy and shot-index pointers are restored after the batch;
normal contacts remain in use for vulnerable players or eligible shots.

The isolated round-eight update at 2951 drops 1416856→1351084 core ticks (4.6%),
still two video frames. The 1000-update route remains 1487 frames, with mean
scene cost 909472.900→909341.160 ticks, identical gameplay hashes and successful
independent full-RAM replay. The long 5404-update route remains 9699 frames and
both screenshots match. All 40 BC opening timings and all 40 Normal timings
are identical; Normal's 40040 gameplay hashes also match. The sampled 4P stack
clearance remains 1204 bytes with no overlap through 3000 updates.

The segment differential test now covers 576 cases, adding all-dead, mixed
protected/dead, protected with live shots and mixed vulnerable/protected parties,
and asserting temporary policy restoration. The 32000-case contact differential,
party routing/frame tests and all 1–4P BC real-menu tests pass. Full speed is
still unachieved. The next isolated spike at update 2975 costs 1567062 ticks;
common actor work, general actor dispatch and drawing account for 261926,
249410 and 217350 attributed ticks respectively.
Evidence: `.local/bc-birth-protection/verified.json` and `next-spike/result.json`.

All 1–4P `qa_multiplayer.py` runs also pass on this ROM, covering real Normal
and Boss Rush menu/modal selection and existing multiplayer flow checks.


### Combined actor-art cache tag

ROM `f2959bef7370d8a24cc6c3ad8b0d8692a92601b383a3eedd3e7f476d96f47649`
combines cache validity and the composite flag into one tag: zero is invalid,
one ordinary, nine composite. Every existing art-selection key remains checked.
This removes one repeated test from the ordinary cached drawing path. Actor
simulation, graphics, clipping, VRAM lookup and submission ordering are unchanged.

Native round-eight 4P improves 1487→1477 video frames per 1000 updates, mean
scene cost 909341.160→907109.959 ticks; the final-round sample improves
1315→1306 frames, mean 851261.579→848313.963 ticks. These comparisons use a
fresh exact baseline ROM. Both sets of 1000 state hashes match and independent
full-RAM replays pass. Long round-eight 4P improves 9699→9688 frames over 5404
updates with both screenshots unchanged. Normal-damage round-four 4P improves
348→345 frames over 300 updates, with matching hashes and replay.

Of 40 BC opening samples, 10 improve, 26 tie and 4 regress slightly, saving
29 frames overall. The actor-cache test passes 1200 mutation/coordinate/slot
reuse updates and 4633 submissions against fresh art selection. Stack sampling
through 3000 4P round-eight updates retains 1204 bytes clearance and no overlap.
The forced six-head final-round regression passes, including its 421-update
clear wait; forced defeats are not natural-campaign evidence. Full speed remains
unachieved: the isolated later round-eight update 2975 costs 1564479 core ticks.
Evidence: `.local/bc-art-cache-tag/verified.json`.

Normal retains all 40040 gameplay hashes; 40 of 40 timings are identical.


### Early round-eight living-segment dispatch

ROM `c9ec8a027638e91e5c24ba03f0aa7fa80f41c34e8c7ac46e825248f2152bf492`
adds the living round-eight segment handler to the existing early round-eight
family path. Segment AI, child births, scroll and common contacts stay in the
same order; relocated bullet aliases retain priority even for custom resource
sets. Other segment rounds and dying segments retain their original dispatch.

This followed two rejected variants. Moving the general fallback behind a
function call again hurt performance despite newer homing fast paths: round-eight
1477→1546 frames per 1000 updates and +456 frames across BC openings. Moving all
segment handlers earlier improved the long route but cost 28 frames across the
openings. Those candidates are archived; neither is in production.

The retained living round-eight path improves 1477→1459 frames per 1000 updates
(mean scene ticks 907109.959→898945.180) and 9688→9524 frames on the 5404-update
bidirectional route. The 1000 gameplay hashes and both route screenshots match;
independent full-RAM replay passes. Opening samples improve in 2, tie in 34 and
regress in 4, costing 4 frames overall. Final-round 4P remains 1306 frames/1000
updates with exactly the same mean scene cost and hashes. Normal-damage round
four remains 345 frames/300 updates with matching hashes. Stack sampling through
3000 round-eight 4P updates leaves 1208 bytes clearance and no observed overlap.

All 16264 complete living-segment updates selected from the original round-eight
capture match the translated actor task. That source file has an incomplete
trailing record; selection explicitly excludes 15952 trailing bytes, retains
only complete paired records, and leaves the original untouched. The formation
capture contains no matching segment records and supplies no segment evidence.
Selection provenance is in `source-round8/selection.json`. Event filtering and
576 segment-birth differential cases also pass. This remains bounded evidence;
full speed is not achieved. Evidence: `.local/bc-segment-dispatch/verified.json`.

Normal retains all 40040 gameplay hashes and 40 identical timings out of 40.
The update-2975 spike now costs 1507835 core ticks; see
`round8/next-spike/result.json` for its profile.


### Rejected compact common-task compiler variants

The common-task instruction profile at round-eight update 2975 shows substantial
register-save, event-clear and coordinate work. An `Os` attribute experiment
shrunk `bc_actor_common_into` from 2110 to 1302 bytes but moved enemy motion into
a separate call: round-eight 4P rose 1459→1584 frames/1000 updates and final 4P
1306→1598. The 40 openings cost 892 extra frames (25 worse, 15 equal).
Forcing motion inline while retaining `Os` produced 1640 bytes, but still cost
1513 and 1403 frames in those samples, with +306 frames across openings
(21 worse, 19 equal). Each candidate preserved all 2000 compared gameplay hashes
and passed independent full-RAM replay. Neither is retained.

The original `O2` common task and motion declarations have been restored, and
the rebuilt ROM matches `c9ec8a027638e91e5c24ba03f0aa7fa80f41c34e8c7ac46e825248f2152bf492`
byte-for-byte. These results favor targeted data-path changes over another
code-size attribute change. Full speed is still unachieved. Profiles and
candidate sources/ROMs are in `.local/bc-common-size`; summary `rejected.json`.


### Rejected collision-coordinate readers

Two native coordinate-reader experiments were rejected. Replacing individual
integer-coordinate shifts throughout the common/contact path with MOVEP/MOVE.B
passed 262144 native reads and the 32000-case contact comparison, but added two
saved address registers and four local-stack bytes. Round-eight 4P rose
1459→1477 frames/1000 updates; normal-damage round four rose 345→359/300;
BC openings cost 76 extra frames. A second variant read X/Y together with one
base pointer only at the three common shot-bound checks. It passed the same
262144-value native probe and restored the original prologue footprint, but
still cost 1468 frames in round eight and +10 across openings. Round four stayed
345. Both preserved all 1300 compared gameplay hashes and independent replays.

All production edits and temporary test options are reverted. The rebuilt ROM
matches `c9ec8a027638e91e5c24ba03f0aa7fa80f41c34e8c7ac46e825248f2152bf492`
byte-for-byte. Candidate sources, native probe variants, disassemblies and
results are archived under `.local/bc-contact-coordinates`; see `rejected.json`.
The renderer's existing coordinate-pair reader remains intact. Full speed is
still unachieved; instruction-level savings cannot substitute for scene timing.


### Current-ROM full protected Home campaigns

Re-ran all four player counts on retained ROM
`c9ec8a027638e91e5c24ba03f0aa7fa80f41c34e8c7ac46e825248f2152bf492`.
Every run launches through the real Home mode menu and player modal, clears
all ten rounds with controller input, completes the ending/credits, and returns
to Home using the last selected controller. Debug protection is enabled after
launch. No boss defeats, deaths, health or weapons are forced/seeded.

| Players | Final simulation tick | Gameplay video frames | Total including ending/return |
|---|---:|---:|---:|
| 1P | 101208 | 103448 | 115674 |
| 2P | 98312 | 105695 | 117921 |
| 3P | 110611 | 141508 | 153735 |
| 4P | 118408 | 175077 | 187304 |

All runs observed consecutive round entries 1–10, no unsupported handler/art
status, ending phases 10/11/8/1/2/9/3/4/5/6/7, exactly 5760 credit updates,
frozen gameplay ticks during the ending, and stable Home return. These are
protected controller-driven diagnostics, not natural playthrough or whole-game
1:1 proof. Prior campaign traces used older builds and can differ in total
simulation updates; their elapsed frame totals are not a controlled speed delta.

`qa_bc_campaign_pilot.py` now records read-only 1000-update timing windows and
separates gameplay frames from ending frames. The windows include intentional
audio waits and transitions; they are not isolated CPU-budget measurements.
Worst windows staying within one round are 1P round 9 (1261 frames), 2P round 9
(1511), 3P round 8 (1983), and 4P round 8 (2055). The latter spans ticks
85018–86018, ending at camera (2304,1792); 4P round 3 also reaches 2034 frames
for 1000 updates. These broad-route measurements confirm a substantial remaining
speed gap and identify late campaign targets beyond fixed-input opening tests.

No production ROM change this turn. Evidence: `.local/bc-campaign-current/verified.json`,
per-count results, `timing-windows.json`, round/ending screenshots, and archived
pilot source/ROM. Natural campaign completion and sustained 60 fps remain
unverified; measured slowdowns contradict full-speed completion.


### Campaign-window attribution and general-family event filtering

Added `bc_campaign_profile.py` and optional `--profile-start`, `--profile-calls`,
`--stop-frame` arguments to the controller pilot. The hash-pinned core hook
attributes complete BC scene calls during a late campaign window. Absolute
video-frame stop permits an independent uninstrumented replay. The baseline
4P Home route records 1000 calls around ticks 85018–86018: mean 1241186.100 core
ticks, maximum 2416253, 997 over the 896040-tick budget. Drawing, general actor
dispatch and common actor work lead the profile. `bc_runtime_actor_events`
accounts for 40206320 attributed ticks, overwhelmingly rejecting empty events.
Full 64 KiB RAM and final pixels match the independent baseline replay.

ROM `f9e9cb2cd26e8439b74005aaca4a9bb9e2c40d82f113b1d5e8fdb977269e200b`
now applies that existing rejection predicate in the general actor-loop caller,
only for the built-in sink with `effects_only` enabled. This avoids marshalling
and calling it for empty events. Extra children, boss defeats, setup sound,
parent/child score and sound still deliver normally; custom/default observers
are unchanged. The sink retains its own guard for other call sites.

Controlled round-eight 4P improves 1459→1443 frames/1000 updates, mean scene
898945.180→892834.138 ticks, with all hashes and independent replay matching.
The long bidirectional route improves 9524→9430 frames/5404 updates with both
screenshots identical. Normal-damage round four improves 345→342 frames/300
updates with matching hashes; final-round 4P remains 1306 frames/1000 updates
with matching hashes. Thirteen BC openings improve, 27 tie, none regress,
saving 86 frames. The 5000-event and 256-complete-loop effect tests pass.
Sampled 4P round-eight stack clearance is 1230 bytes, with no overlap through
3000 updates.

The new ROM's campaign profile averages 1104025.034 ticks over 1000 calls,
with 884 over budget and 1902 elapsed video frames. Its independent replay
matches all 64 KiB RAM and final pixels. This is not a controlled before/after
campaign speed delta: the feedback pilot follows a different route as frame
boundaries and observed positions change. Controlled fixed-input results above
supply the performance comparison. Sustained full speed is not achieved.
Evidence: `.local/bc-campaign-window/` and `.local/bc-general-event-filter/verified.json`.

Normal retains all 40040 state hashes and 40 identical timings out of 40.


### Aligned backward option-trail copy

ROM `12c319a064de09edba5ca7fc8d458ff29d803fae20b8296a45723c7328ec70e1`
replaces the native 14-byte backward trail shift with three aligned longword
copies and two byte copies. The trail starts at odd offset 967 in `BcWeapons`;
its odd-index addresses are therefore word-aligned, as compile-time assertions
require. Copying byte 13 first, then longwords at 9/5/1, then byte 0 preserves
the overlapping source exactly. New X/Y low bytes are stored afterward, keeping
the eight-update option history and source truncation unchanged. Host builds
retain the ordinary byte loop.

`qa_bc_trail_copy.py` extracts the production routine into a scratch native ROM
and compares 147456 updates against a separate byte reference: both word
alignments, nine successive updates, varied full-word coordinates, and eight
sentinel bytes on each side. No release ROM is modified by the probe. The
1–4P party frame/weapon/trail integration test also passes.

Controlled 4P round eight improves 1443→1441 video frames/1000 updates; final
round improves 1306→1298. All 2000 state hashes and independent full-RAM replays
match. The long round-eight route improves 9430→9403 frames/5404 updates with
both screenshots identical. Normal-damage round four improves 342→340 over
300 updates with matching hashes/replay. Ten BC openings improve, 29 tie and
one costs two extra frames, saving 21 overall. Sampled 4P stack clearance is
1226 bytes, four fewer than the prior build, with no overlap through 3000
round-eight updates. These are bounded improvements; full speed is unachieved.
Evidence: `.local/bc-trail-copy/verified.json`.

Normal retains all 40040 gameplay hashes and 40 identical timings out of 40.


### Caller-owned player-frame output

ROM `c5b1b8e0d776753458947ef24cf3e5be04cba01d51a50ebb220bf17def0d70a4`
adds `bc_player_step_into`, allowing party and single-player runtime callers to
write events directly into their result records. The original return-by-value
API remains a wrapper. Control, weapons, recoil and finish still execute in the
same order, and early checkpoint output is fully initialized. The update is
explicitly separate (`noinline`): the initial automatically inlined variant
regressed round-eight 1441→1531 frames and openings by 428 frames, so it is
rejected and archived.

The retained separate-function variant improves round-eight 4P 1441→1440 frames
per 1000 updates, final 4P 1298→1297, and the long bidirectional route
9403→9391 frames/5404 updates. Normal-damage round four regresses 340→341 frames
per 300 updates. All 2300 compared gameplay hashes and independent replays
match; both long-route screenshots match. Twelve openings improve, 24 tie and
four regress, saving 20 frames overall. Sampled stack clearance is 1220 bytes
(six fewer than before), with no overlap through 3000 round-eight 4P updates.

The source player-runtime test now exercises the new output with prefilled
nonzero bytes and compares it to the legacy wrapper. It matches 1680 original
player updates, 2687 common enemy updates, 1677 trail updates, three deaths and
three checkpoint requests from `player-runtime-natural`. The 1–4P party-frame
test also passes. This is a small, route-dependent gain, not sustained full speed.
Evidence: `.local/bc-player-event-output/verified.json` and `noinline/`.

Normal retains all 40040 state hashes and 40 identical timings out of 40.

Compact actor cache build 839603d2: real Normal and Boss Rush menu/modal,
selection and multiplayer flow regression passes all 1/2/3/4-player counts.
BC modal/pause/return checks also pass all counts. Timing remains unfinished.
Evidence: `.local/bc-art-cache-compact/verified.json` and `multiplayer-*p.log`.

BC actor pose extent optimization (2026-10-04), ROM `2185c0767663251edaadbadaf5a69b628a61f7e9364cf10aebcb363256dc2cf5`: 4P R8 long route 9300→9268 frames / 5404 updates; 2000 profile hashes and replays match. BC opening matrix net −38 frames, four small regressions; Normal 40 cases/40040 hashes unchanged. Stack gap1540, no overlap. Evidence `.local/bc-art-half-size/verified.json`; full speed remains unfinished.

### Reject protected Normal body contacts before distances — 2026-10-04

Retained ROM `eae08e12e56c15915c60b43c9c2818279f7c32f0e248cc76ff9462265271896c`. Normal enemy contacts
now reject invulnerable players before distance arithmetic, except for small
pickups, which remain collectible. The later state/protection gates and player
order are retained. No cached protection state is introduced.

The extracted actual contact blocks match across one million cases, including
125,499 pickup dispatches (62,489 while protected), 145,806 kill dispatches,
1–4P, both actor sizes, stale alive flags and wrapped coordinates. This tests
the dispatch boundary; integrated native replay covers resulting game state.
The protected Normal matrix matches 40,040 hashes: three cases improve, 37 tie,
none regress, net 18 fewer frames. 4P section three improves 1,055→1,043 frames
for 1,000 updates; all 1,001 state and ordered-render hashes match.

Added `--vulnerable` to the fixed-update Normal fixture. It allows normal damage
and protection countdowns but still supplies lives/AUTO weapons, so it is not
a natural campaign. On section three it matches all 1,001 state/render hashes
but uses 1,020 frames versus 1,019; this small timing regression is explicit.
BC openings retain 39 timings, with R3 4P costing two more frames (624→626).
The late 4P R8 profile improves 1,831→1,829 with 1,000 matching gameplay hashes
and independent full-RAM replay. Its actor/player function cycle totals are
unchanged; this is not a claim of faster BC logic.

Evidence: `.local/normal-contact-protection/verified.json`. New comparison tool:
`tools/qa_enemy_contact_gate.py --baseline .local/normal-contact-protection/baseline/enemies.c`.
Build and diff checks pass. Sustained all-mode full speed remains unfinished.

### Real Boss Rush modal performance and wheel-cache allocation — 2026-10-04

Added `tools/qa_boss_rush_perf.py`, a stock-core bounded route entering actual
Home → Boss Rush → 1/2/3/4P. It checks cancel behavior and all selected players
joining, selects the already-owned AUTO using normal C releases, and preserves
the default Boss Rush weapon levels. Protection and steering are assisted.
No boss deaths or indices are forced. An initial held-BIT run fired only once
and is explicitly excluded as combat performance evidence.

On unchanged ROM `eae08e12e56c15915c60b43c9c2818279f7c32f0e248cc76ff9462265271896c`, 3,000-video-frame
samples produce these update counts: 1P 2,805 (195 missed), 2P 2,541 (459),
3P 2,788 (212), 4P 2,742 (258). Routes reach two or three bosses, so this is not
an all-boss audit and counts across player counts are not matched workloads.
All have zero submission drops/remaps. The 4P independent uninstrumented replay
matches all RAM, final pixels and timing. The player-count selection works;
sustained full speed fails even in these bounded runs.

The 4P profile attributes 132,620,138 core ticks to `cell_words` and 39,659,802
to `frame_cells`. A read-only heap audit finds no wheel image cache during all
929 wheel-ready video frames. Allocated blocks consume 1,280 and 8,192 bytes,
leaving only 3,948 bytes free. The wheel requests three 4,096-byte plane images
(12,288 total), so allocation fails and background cells are rebuilt per turn.
Even the 11×8-cell rectangle at three frames needs 8,448 bytes. Generated frame
maps have 141–154 distinct full entries (4,512–4,928 bytes of expanded cells),
also above the observed free block. A replacement must address this real memory
constraint; another full-frame allocation cannot solve it.

Evidence: `.local/boss-rush-current/verified.json`. Production ROM is unchanged.
Full port fidelity, all-boss/all-mode speed, and physical adapter tests remain open.

### Rejected low-memory wheel cell caches — 2026-10-04

Tested three alternatives to the failed 12 KiB wheel-plane allocation: a
1,904-byte per-slot unflipped-cell cache with looped flip handling, the same
cache with unrolled flip cases, and a 3,456-byte complete-cell hash cache.
All allocated successfully. Slot/meta tags prevented stale reuse; the complete
cache also keyed flip bits. Actual cached/original C routines matched 172,032
cell outputs covering blanks, all flips, regular/extra templates, cache hits,
slot reuse and untouched destination sentinels.

Nevertheless, all three 4P runs retained exactly 2,742 updates / 3,000 video
frames (258 missed). The unrolled version also retained every 1P–3P update
count: 2,805 / 2,541 / 2,788. Its combined frame_cells/cell_words attribution
fell from 172,279,940 to 128,675,876 core ticks, but did not cross the end-to-end
frame threshold. The hash variant saved little CPU and left just 500 free
heap bytes. These results reject CPU-side cell caching as a sufficient fix.
The full-plane DMA/scheduling path needs direct measurement next; reduced
rendering cost alone is not evidence of fewer missed updates.

Restored exact prior source, symbols and ROM `eae08e12e56c15915c60b43c9c2818279f7c32f0e248cc76ff9462265271896c`.
Candidate sources, ROMs and cell comparisons are archived under
`.local/wheel-cell-cache/rejected.json`. No new production allocation or
cache helper is retained. Full-speed and full-game fidelity remain open.

### Wheel-turn CPU versus DMA scheduler trace — 2026-10-04

Extended `qa_boss_rush_perf.py --scheduler-trace` with read-only opcode-boundary
observations at main input, both scheduler entry variants and DMA queue flush.
The 4P 3,000-frame run records 8,226 observations. An independent uninstrumented
replay matches all 64 KiB RAM, final pixels and 2,742 updates / 258 misses.
Production ROM remains `eae08e12e56c15915c60b43c9c2818279f7c32f0e248cc76ff9462265271896c`.

Libretro's video-frame boundary in this fixture is at scanline 224. Duration
analysis therefore uses `(line-224) mod 262` within each observed video frame;
subtracting raw line numbers gives invalid negative work times. The resulting
bounded scanline measurements show 436 ordinary wheel-ready updates at 139–214
lines (mean163.743), versus 246 wheel turns with >=4KiB queued transfers at
377–419 lines (mean395.171) of input-to-scheduler work. Those turns already
exceed the entire 262-line NTSC frame before waiting/flushing. Their flush-to-
next-input interval is 28–29 lines (mean28.008), including scheduler remainder
and input overhead. This does not justify changing VBlank admission thresholds.

The smaller cache's CPU saving was real but insufficient to bring those turn
updates below one frame. The next optimization must eliminate much more of the
synchronous full-rectangle rendering, preserve output, and fit the actual heap.
Evidence: `.local/boss-rush-scheduler/verified.json`. This is a protected route
through three bosses, not all-mode or complete-campaign speed verification.

### Retain wheel shadow deltas plus bounded metatile cache — 2026-10-04

Retained ROM `77cabae44b56d4889d70fc4ff895eaac70f50a86ef3f2dcd432b41de329f1b22`. When full-plane images
do not fit, an 88-byte slot history for these wheels allows unchanged cells
to be skipped, provided their complete map entry and VRAM slot match. Every
ordinary shadow writer invalidates the prior frame; flush/exit releases it.
A separate optional 1,904-byte unflipped-cell cache avoids repeated template
resolution. Its meta+1 tags handle slot reassignment. Both allocations have
uncached fallbacks and are released by frames_drop. No wheel cadence, physics,
DMA size, or VBlank admission rule changes. Independent full-frame images
never use shadow-delta skips.

Combined 4P wheel-turn CPU work falls from mean 395.171 to 330.614 scanlines
(range 377–419 →309–415, 246 observations each). Delta-only averages 356.163.
The combined saving is retained as progress toward the frame budget, while
explicitly not claiming a visible speed gain yet: the same Boss Rush samples
still miss 195/459/212/258 updates in 1P/2P/3P/4P. All 12,000 completed video frames
match their baseline counterparts exactly; 4P independent full-RAM replay also
matches. The new actual-C comparison passes 40,000 complete-plane comparisons
with blanks, flips, ring wrap, slot changes, shadow invalidation, optional-cache
combinations and separate frame images. Soft reset frees both allocations in
1P (wheel active) and 4P.

Normal 40 cases match all 40,040 gameplay hashes: one timing improves, 37 tie,
two regress, net two extra frames. BC 40 openings: six improve, 33 tie, one
regresses (R9 4P +1), net ten saved frames. Late 4P R8 costs one extra frame
(1829→1830) with 1,000 matching gameplay hashes and independent replay. Its
3,000-update stack test has a 1,546-byte minimum gap and zero overlaps. These
small timing tradeoffs accompany a substantial measured wheel CPU reduction.

Evidence: `.local/wheel-delta/verified.json`; repeat the host comparison with
`tools/qa_wheel_delta.py --baseline .local/wheel-delta/baseline/bg.c`. Boss Rush
QA now supports per-video pixel hashes and an explicit allocation-release test.
Build/diff checks pass. Natural fidelity and sustained all-mode 60 fps remain open.

### Wheel word offsets and native unflipped copy — 2026-10-04

Retained ROM `a70d261ee98f4644fcd9343a5489e4e90362d6e58c6f3b524970fe88130726af`.
The bounded cache and ring addresses now use signed-word byte displacements;
unflipped cached cells use eight native long moves between word-aligned,
disjoint buffers. Host builds retain the C copy. No allocation, frame cadence,
DMA admission, palette or simulation changes.

Across 246 observed 4P wheel turns, input-to-scheduler CPU work falls from
330.614 to 327.650 scanlines on average (range 306–408). The 3,000-frame route
still yields 2,742 updates and 258 misses: this is a small CPU saving, not a
full-speed result. All 3,000 video hashes match the prior ROM. An independent
uninstrumented replay also matches all video hashes and full RAM. Soft reset
releases the caches; the host comparison passes 40,000 whole-plane cases.

All 40 Normal timing cases are unchanged with 40,040 matching state hashes.
All 40 protected BC opening timings are unchanged. Late 4P round 8 retains
1,830 video frames / 1,000 updates with every state hash matching and its own
independent replay verified. Evidence and archived source/ROM/symbols:
`.local/wheel-word-offsets/verified.json`. Full-game fidelity and sustained
60 fps / 100% speed remain unfinished.

### Rejected opaque wheel paired additions — 2026-10-04

Tested an opaque flag in the existing cell-cache tag and native paired-word
flip additions, preserving individual zero handling for transparent cells.
No extra RAM allocation. Candidate `742d06b42a56b3ef24dcbb922ebad046076e7cc3d7a630c08d5550e4c974f264`
passes 40,000 host plane comparisons and matches all 3,000 4P video frames.
The native route still has 2,742 updates / 258 misses and frees caches on reset.
Mean wheel-turn work improves only 327.650→325.882 scanlines, while the maximum
increases 408→458 (246 observations). Rejected this tradeoff; restored exact
prior source, ROM and symbols `a70d261e…`. Evidence and candidate archived in
`.local/wheel-opaque-pairs/rejected.json`. Host coverage exercises the C fallback;
native pixel comparisons exercise the assembly. Full-speed work remains open.

### Current-build all-mode modal audit — 2026-10-04

Rebuilt restored source and confirmed exact retained ROM `a70d261ee98f4644fcd9343a5489e4e90362d6e58c6f3b524970fe88130726af`.
This also refreshes the linked ELF after the rejected opaque-copy experiment;
future restored-build tests that read ELF sizes must rebuild first or restore
the matching ELF too. ROM, ELF and symbols are archived together in
`.local/mode-audit-current/` with hashes and script provenance in `verified.json`.

All twelve mode/count combinations pass: Normal, Before Christ and Boss Rush,
each 1–4P. Actual menu navigation verifies modal cancellation and party launch.
Normal/Boss Rush checks cover joins, injected-wave counts 4/4/6/9, initial boss
HP 20/20/30/45, additional-pair merge, SRAM reload and legacy migration.
BC checks cover physical Start edges, every selected controller's pause/freeze/
resume, inactive-controller exclusion, pause inhibit, forced terminal return,
re-entry and paused soft reset. The terminal fixture explicitly injects the
terminal boundary; this is not proof of natural completion. These results
verify the mode-selection requirement in the current build, while full-game
fidelity and sustained 60 fps / 100% speed remain unfinished.

### Segment coordinate pair reads — 2026-10-04

Retained ROM `84664f8aa3ab55a1bec802dde010c3f53f80708f9b5149d10bd6df469408c9e9`.
The segmented actor's steering and shooting gates now read integer coordinates
with the same MOVEP/MOVE-byte technique used by the renderer, retaining a
portable shift fallback. The helper returns unsigned 16-bit values, preserving
source wrapping and high-byte checks. No fields, allocation or gameplay rules
change. `qa_bc_coordinate_pair.py --segment` extracts the production helper;
262,144 native 68000 cases pass with both word alignments, dirty upper bytes,
fractional bytes and sentinel preservation.

Late round-eight 4P saves three video frames (1830→1827 per 1000 updates), with
all 1000 gameplay hashes matching and independent full-RAM replay verified.
Attributed segment_prepare work decreases 59,360,196→58,986,032 core ticks.
All 40 BC opening timings and all 40 Normal timings remain identical; Normal
also retains all 40,040 state hashes. The 576-case segment-birth differential
passes. Replaying the previously selected complete source pairs gives 16,264
matching living-segment updates (handler $BF27); that fixture contains no child
births or deaths and does not establish whole-game fidelity. Original trace
selection provenance stays in `.local/bc-segment-dispatch/source-round8/`.

Evidence and matching source/ROM/ELF/symbol snapshot:
`.local/bc-segment-coordinates/verified.json`. Full speed remains unachieved.

### Pose-only art selection — 2026-10-04

Retained ROM `4067a22d5c8645cd51cd6749972d1c417bac87185905c72a8ae107e1a6936564`.
Split bc_actor_pose from the positioned bc_actor_sprite wrapper. Actor-cache
refresh uses the former, avoiding coordinate calculations it previously
immediately discarded. The wrapper positions visible art and preserves zero
coordinates for hidden/unhandled art. Gallery/preview callers keep that API.
No sprite ordering, pattern, palette, simulation or cache-layout changes.

Late R8 4P scene mean falls 1009748.873→1006757.780 core ticks; the sampled
peak falls 1640114→1615992. All 1000 gameplay hashes and independent RAM replay
pass. Video timing is mixed: the 1000-update late sample regresses 1827→1832,
while the 5404-update bidirectional route improves 9264→9251 with both PNGs
byte-identical and the same 152 originals / 184 extras / 2253 blocked spawns.
BC openings: 12 improve, 25 tie, three regress, net 17 frames saved. Normal:
all 40 timings unchanged and all 40,040 gameplay hashes match. Retained for
lower CPU cost and broader measured gains while recording the short regression.

The new baseline differential passes 60,192 positioned/pose comparisons;
actor-cache testing passes 1200 updates / 4633 submissions. Native preview
covers 616 art selections with no remaps or drops. The injected 4P completion
fixture passes all 20 portraits, caption/font pixels, fades, audio onset,
5760 credit updates, Home return and gameplay re-entry. This is presentation
coverage, not a natural campaign. A 3000-update stack trace retains 1546 bytes
minimum clearance with no overlap. Evidence, art captures and matching
source/ROM/ELF/symbol snapshot: `.local/bc-pose-selection/verified.json`.
Sustained 60 fps / 100% speed and full-game fidelity remain unfinished.

### Rejected segment-art base table — 2026-10-04

Replaced segment pose-base arithmetic with a six-word ROM table experimentally.
Candidate `5f7b3c2069d0c399e5fcbf8b75eaa62b844576f7abc623054366e16ba0c013ae`
preserves all 1000 late-scene state hashes, independent RAM replay, both
long-route screenshots and spawn totals. Host checks pass 60,192 art cases
and 1200 cache updates / 4633 submissions. But pose-selection attribution
increases 12,500,488→12,838,560 core ticks. Late timing changes 1832→1831,
while the longer route stays 9251 frames. Rejected: no demonstrated sustained
improvement and more CPU work. Restored source, ROM, ELF and symbols exactly
to `4067a22d…`. Evidence: `.local/bc-segment-art-table/rejected.json`.

### Packed pose return — 2026-10-04

Retained ROM `d4d5e170b17d3a22cbfff94801e882e604a12e6ca384a9099f7bb7538ae8952e`.
Art selection returns a register-sized packed key/flags value instead of a
12-byte positioned sprite record. The public positioned wrapper reconstructs
all original fields; cache refresh decodes only its reusable inputs. Packed
bits are documented in bc_actor_art.h. No cache size, simulation, palette,
pattern or submission-order changes.

Late R8 4P improves 1832→1826 video frames per 1000 updates; all gameplay
hashes match and independent full-RAM replay passes. Mean scene ticks fall
1006757.780→1004504.942; sampled maximum falls 1615992→1598926. The long
5404-update route improves 9251→9232 frames with both screenshots byte-identical
and the same spawn/queue totals. BC openings: 12 better, 26 equal, two worse,
net 31 frames saved. All 40 Normal timings remain unchanged with all 40,040
state hashes matching. These samples still do not reach sustained full speed.

Host coverage: 60,192 art comparisons and 1200 cache updates / 4633 submissions.
Native preview: all 52 batches (616 selections) byte-identical to the prior
build, no drops/remaps. The injected 4P completion boundary passes 20 gallery
entries, 5760 credits updates, fades, font/caption pixels, audio, Home return
and gameplay re-entry. Stack: 1546-byte minimum gap, zero overlaps across
3000 updates. Natural full-campaign fidelity remains unverified. Evidence,
captures, scripts and matching source/ROM/ELF/symbols:
`.local/bc-packed-pose/verified.json`.

### Rejected native pose flip table — 2026-10-04

A 256-byte ROM lookup for the big-endian attribute high byte replaces the two
flip shifts in candidate `bf7122496680e2eee035a80ef48bfd385be97281a5bb76a49c8c79593f81f060`.
It passes all 65,536 attribute words in a native probe, 60,192 host art cases,
all 1000 gameplay hashes and independent RAM replay. All 52 native preview
batches and both long-route PNGs match. Nonetheless late timing regresses
1826→1834 and the long route 9232→9258; average scene cost also rises.
Rejected and restored matching source, ROM, ELF and symbols to `d4d5e170…`.
Evidence: `.local/bc-pose-flip-table/rejected.json`. Retained the reusable
`qa_bc_pose_flags_native.py` probe for the packed interface; it compiles the
actual production art selector into a scratch cartridge, leaving release intact.

### Reuse the segment actor pointer — 2026-10-04

Retained ROM `e393961c1175ad5fe157f8b1dd4039d8d847ffed0678a896a51b4c67d5bc04eb`.
segment_prepare receives the actor address already held by its caller instead
of recalculating array+slot on every invocation. Followers read the preceding
actor through that pointer. Only tail firing reconstructs the pool base for
allocation and immediate child processing. Both specialized and general
segment dispatch sites use the same helper; no public ABI/state-layout changes.

Late R8 4P improves 1826→1811 frames per 1000 updates, with all hashes matching
and independent full-RAM replay. Mean scene cost falls 1004504.942→996667.035
core ticks. The longer route improves 9232→9193 frames with both PNGs and
spawn/queue totals unchanged. BC opening timings: one better, 38 identical,
one worse, net zero frames. Normal: all 40 timings identical and all 40,040
state hashes match. Stack retains 1546-byte clearance, zero observed overlap.

Source replay passes 16,264 captured living-segment updates. The existing
576-case stage-birth differential also passes. New qa_bc_segment_pointer.py
compares tail firing against the archived original: 248 cases across parent
slots 1–31 and four aim quadrants, including 124 immediate child updates and
124 full-pool failures. An initial test compared unused extra-event storage;
the corrected comparator follows the documented extra_count validity contract
and compares every valid event, the complete actor pool, player and counter.
It does not suppress differences in consumed data.

Evidence, matching source/ROM/ELF/symbols and tail differential:
`.local/bc-segment-pointer/verified.json`. Sustained full speed and natural
full-game fidelity remain unfinished.

### Reuse the curve actor pointer — 2026-10-04

Retained ROM `8caa2956278c7b9b01e5f30afdff8b5476783f3b67cd04af8c53a59b85f62853`.
curve_common and curve_prepare take the caller's actor pointer, reconstructing
the pool base only for child allocation. The public round-one adapter retains
its existing array/slot API. Parent motion, immediate child order, counters
and firing-latch semantics remain unchanged.

The active-curve R8 4P window (ticks 300–1300) improves 1556→1550 video frames;
mean scene cost decreases 911102.178→907680.508 core ticks. The later early
window (2000–3000) changes 1403→1400 frames, but has essentially unchanged
main simulation attribution and slightly higher mean scene cost, so that
window alone is not CPU-saving evidence. Both windows retain all 2000 state
hashes and independent full-RAM replays. The longer route improves 9193→9188
frames with identical screenshots and spawn/queue totals. BC openings: three
better, 36 equal, one worse, net five saved frames. All 40 Normal timings and
40,040 state hashes match. Stack clearance is 1556 bytes, no overlap observed.

Original round-one curve replay passes 9071 actor updates and seven immediate
child updates, all four phases and all sixteen directions. The extended
qa_bc_segment_pointer.py --curve adds 256 differential cases across all parent
slots: 128 immediate child updates and 128 full-pool failures; every second
attempt stays inhibited, including after allocation failure. Only valid event
entries are compared, following the production extra_count contract.

Evidence, source/ROM/ELF/symbol snapshot and firing fixture:
`.local/bc-curve-pointer/verified.json`. Full-game fidelity and sustained
60 fps / 100% speed remain unfinished.

### Rejected segment animation lookup — 2026-10-04

Replacing the round-dependent segment animation-address conditional with an
8-word ROM table preserved 36,864 preparation comparisons (all round bytes,
16 directions, head/body/tail, wait underflow/expiry/countdown), 16,264 captured
living-segment updates and 248 tail-firing cases. Late R8 4P preserved all 1000
state hashes and independent full-RAM replay. Mean scene ticks fell slightly
996660.917→996241.491, but delivery worsened 1810→1813 video frames per 1000
updates. All 40 BC opening timings stayed identical. The small CPU reduction
has not produced an end-to-end speed benefit, so the candidate is rejected.

Restored source, ROM, ELF and symbols match the baseline; retained ROM is
`8caa2956278c7b9b01e5f30afdff8b5476783f3b67cd04af8c53a59b85f62853`.
Evidence and the complete candidate are in `.local/bc-segment-animation`, with
`rejected.json` recording the decision. Sustained full speed and natural
full-game fidelity remain unfinished.

### Rejected shared actor pose cache — 2026-10-04

A one-entry shared pose cache was tested only after a per-slot art-cache miss.
Its complete key included frame/attributes, source base/reference and composite
flag. Repeated formation poses were correct in the extended renderer fixture:
1200 original updates/4633 submissions plus 256 synchronized updates/6725
submissions, including hidden frames, recolors, composite flags and slot reuse.

Native late R8 4P retained all 1000 state hashes and independent full-RAM replay,
but worsened 1810→1826 frames. Mean scene cost rose 996660.917→1004605.931 ticks.
Pose-selection attribution barely fell (11350304→11297384), while actor drawing
rose 153207082→161110222. BC openings: 1 better, 21 unchanged,
18 worse; net +96 video frames. Rejected the cache and restored
source/ROM/ELF/symbols to `8caa2956278c7b9b01e5f30afdff8b5476783f3b67cd04af8c53a59b85f62853`. Kept the synchronized formation renderer
checks in tools/qa_bc_actor_cache.py and verified them against the restored code.

Evidence: `.local/bc-shared-pose/rejected.json`; candidate and baseline snapshots
are archived beside it. Sustained full speed and full-game fidelity remain open.

### Rejected animation attribute byte update — 2026-10-04

Tested changing only the attribute high byte when enemy animation sets X/Y
flip bits. The native helper and full production bc_enemy_motion each pass
262,144 combinations of all 16-bit attributes and four flip states. The full
routine probe also checks sprite, animation pointer, timer, return value and
limited count. Captured source replay passes 13,755 common-motion updates and
17 HP-exhaustion transitions; 32,000 party-contact comparisons also pass.

Late R8 4P retains 1000 gameplay hashes and independent full-RAM replay but
worsens 1810→1817 frames, with mean scene cost 996660.917→998892.181 ticks.
BC openings: five better, 23 equal, 12 worse; net 31 extra frames. Rejected and
restored source/ROM/ELF/symbols to
`8caa2956278c7b9b01e5f30afdff8b5476783f3b67cd04af8c53a59b85f62853`.

Kept tools/qa_bc_animation_flags.py, which compiles the actual production
routine in a scratch native ROM. It passes on the restored implementation.
The full-routine test needed 3069 video frames (the candidate needed 3057),
so its original 3000-frame observation cap was raised to 20000; the earlier
status=running timeout was not a behavior mismatch. These microbenchmarks
again do not predict whole-scene speed. Evidence and both build snapshots:
`.local/bc-animation-byte/rejected.json`. Full speed and full-game fidelity
remain unfinished.

### Current retained-ROM peak remeasurement — 2026-10-04

Measured exact R8 4P simulation tick 12960 on retained ROM
`8caa2956278c7b9b01e5f30afdff8b5476783f3b67cd04af8c53a59b85f62853` with read-only instruction attribution.
The 1000-update window matches all prior gameplay hashes, the peak row matches
exactly, and the independent uninstrumented full-RAM replay passes. Tick12960
costs 1586144 core ticks, 1.7702 NTSC scene budgets; 801/1000
scene calls exceed 896040 ticks before outer input and VBlank/DMA processing.

Peak attribution: common task304010, actor drawing217924, general actor
loop202818, segment preparation150668, player step146888, scene114996,
pose selection89348. Instruction listings identify recurring dispatcher
round/random-pointer loads, event-envelope stores and argument setup, alongside
motion/contact work and sprite submission. This supports testing a targeted
segment event path; it does not justify another general fallback outline
(previously rejected), broad cache, or relaxing DMA admission. Even removing
all pose-selection cost from this peak would leave it above the frame budget.

No production behavior changed. Evidence, symbol/source snapshots and full
instruction attribution are under `.local/bc-current-peak/verified.json` and
`instructions.json`. The scope remains the protected R8 route, not natural
campaign fidelity or an all-mode speed certification.

### Retained Round 8 segment event fast path — 2026-10-04

ROM `795bac2bc5babeca27fa7172e98f0ef0393108cedf89d28128ac6dc974205448` gives living R8 segments a direct actor-loop path using the existing
segment preparation and common motion/contact routines. It reuses the loop's
empty child envelope, clearing child fields only after a firing attempt.
Scrolling, immediate child order, default/custom observer delivery and the
relocated-bullet precedence guards are preserved. Other families retain the
existing dispatcher. The internal helper requires an initialized empty envelope.

Exact late R8 windows (warmup 12000, 1000 updates): 4P improves 1810→1738 frames,
mean scene ticks 996660.917→970358.991; 3P improves 1559→1493,
mean 919462.922→892097.304. All 2000 gameplay hashes and independent full-RAM
replays match. 4P still has 735/1000 scenes over budget; 3P has 478/1000.
The longer route changes 9188→9055 frames with identical scaled/drained PNGs,
152 original/184 extra enemies, 2253 blocked attempts, no drops/remaps. Its bounded
stop ends at 5405 instead of 5404 updates; this is an approximate route comparison,
not an exact-update timing delta.

New tools/qa_bc_segment_fast.py compares archived and current complete loops:
600 three-pass cases, 36972 ordered valid events, all actor/player/count results
match. It spans first segment slots 0–24, full/free pools, four target quadrants,
and wait expiry/countdown. The initial fixture omitted terrain for the later
child passes and crashed; adding valid empty terrain fixed the test setup.
Existing 5000 event/256 whole-loop sink tests also pass.

All 40 Normal timings and 40040 hashes match. BC openings are mixed:2 better,
30 unchanged, 8 worse, net 10 extra frames. Stack sampling 3000 updates retains 1548 bytes
clearance with 0 overlaps. Real 4PBC modal, cancel, audio, pause/freeze/resume, return,
re-entry and paused reset pass. Build has no warnings; diff check passes.

Evidence and matching source/ROM/ELF/symbol snapshots:
`.local/bc-segment-fast/verified.json`. The change is retained for the larger
measured crowded 3P/4Pgain despite small opening regressions. Sustained 60 fps /
100% speed and natural full-game fidelity remain unfinished.

### Retained Round 8 curve event path — 2026-10-04

ROM `d5a41f8ae089c346f70b89f004dc41de248658628a660a282c34baeb2eedc099` extends the reusable actor-loop event envelope to living Round 8
approach/escape curves. The existing curve preparation/common implementation
is exposed through an internal helper; immediate children, the firing latch,
scrolling, observer order and segment bullet-precedence guards are unchanged.
Child fields are reset after each firing attempt, including allocation failure.

The curve-heavy 4P window (warmup 300, 1000 updates) improves 1555→1507 video
frames, mean scene cost 909815.347→893368.210 ticks. The later segment-heavy
window regresses: 4P 1738→1756, mean 970358.991→975825.494; 3P 1493→1507,
mean 892097.304→898235.443. All 3000 gameplay hashes and independent full-RAM
replays match. These regressions remain explicit; this is not an across-the-board
speedup. The longer 5405-update 4P route improves 9055→9039 frames, both PNGs
match, and counts remain 152 original/184 extra/2253 blocked with no drops/remaps.
BC openings: 11 improve, 28 match, one regresses; net 43 frames saved. Retained
for the curve-window and broader opening/route gains. A next dispatch experiment
should preserve the segment fast path's cost while avoiding these new tests on it.

Extended tools/qa_bc_segment_fast.py with --curve: 600 three-pass cases compare
36,936 ordered valid events, 450 child births and 450 allocation failures against
the archived dispatcher. Segment mode still passes 600 cases/36,972 events,
900 births and 900 failures. Source curve replay passes 9071 actor and seven
child updates; the 256-case firing fixture verifies the latch after success or
failure. Existing effect-filter tests pass. All 40 Normal timings and 40,040
hashes match. Stack sampling retains 1548 bytes, zero overlap; 4P BC menu,
cancel, pause/resume, return/re-entry and paused reset pass.

Evidence and complete build/source snapshots: `.local/bc-curve-fast/verified.json`.
Build warnings and diff checks are clean. Sustained 60 fps / 100% speed and
natural full-game fidelity remain unfinished.

### Rejected separate family dispatch checks — 2026-10-04

Tested separating the Round 8 segment and curve tests, checking segments first
and joining their event delivery at a shared label. The late 4P window improves
only 1756→1753 frames (mean ticks 975825.494→975409.134), while the curve-heavy
window regresses 1507→1523 (893368.210→897552.292). All 2000 state hashes and
independent full-RAM replays match. Complete-loop comparisons pass 600 curve
and 600 segment three-pass cases, including ordered child births/failures.

The 40 BC openings cost 79 extra frames: two better, 27 unchanged, 11 worse.
Rejected this control-flow arrangement. Restored source, ROM, ELF and symbols
to `d5a41f8ae089c346f70b89f004dc41de248658628a660a282c34baeb2eedc099`.
The candidate and all measurements are archived in `.local/bc-family-order/`,
with the retention decision in `rejected.json`. Full speed and full-game
fidelity remain unfinished; this result does not remove the retained curve
path's documented late-window regressions.

### Rejected wheel orientation cache — 2026-10-04

Tested storing each slot's last fully oriented cell, keyed by meta and flip,
in the existing 1904-byte cache. Cache hits then use eight native long copies;
misses rebuild with the original cell_words. This allocates no additional RAM.
The uncached-reference comparison passes 40,000 whole planes, including blank
cells, all flips, slot changes, ring wrap and shadow invalidation. The 4P real
Boss Rush route preserves all 3000 complete video-frame hashes. Both builds
free wheel allocations on soft reset.

It is slower: 246 measured wheel turns rise from 306–408 scanlines (mean
327.6504) to 352–420 (mean 373.5122). Both runs still complete 2742 updates in
3000 frames, missing 258. Thus per-slot orientation rebuilding outweighs the
cheaper copies for this route. Rejected; restored bg.c, ROM, ELF and symbols
to `d5a41f8ae089c346f70b89f004dc41de248658628a660a282c34baeb2eedc099`.

Evidence and complete candidate/baseline snapshots:
`.local/wheel-oriented-cache/rejected.json`. Scheduler timing uses physical
scanline epochs with video-frame origin224. End-RAM hashes are not compared
across builds because cache representations differ. No full-game or all-boss
speed claim follows from this bounded protected route. Full speed remains open.

### Wheel shadow-backed copy-plan feasibility — 2026-10-04

The existing shadow plane can serve as part of a complete oriented-cell cache.
Across the five actual wheel maps, only 88–96 unique cells are absent from a
particular current frame. Storing those cells needs 2816–3072 bytes; one
32-byte scratch cell brings the maximum payload to 3104. The measured 4P heap
currently holds 88+1904 bytes of optional wheel caches followed by 1958 free
bytes. Replacing the optional caches appears feasible, subject to native
allocation/lifecycle and stack checks. This is not a claim that three full
planes fit. Raw key counts are conservative (149/149/141/141/154); no assumption
that distinct keys have distinct pixel contents is needed.

A read-only host prototype assigns missing cells to cache slots for each frame
and resolves parallel copies with a scratch cell for dependency cycles. Across
all five maps, 50,000 random transitions (including repeated frames and reverse
transitions) preserve all live shadow/cache cell words. Plans require 112–163
cell copies for nontrivial transitions and 17,408 ROM bytes total, plus small
initial key lists. Unlike the rejected orientation cache, turns need no cell
reconstruction if native residency and invalidation constraints are satisfied.

This changes the next action to a native copy-plan prototype. Initialization
must prepare a valid state without displaying an intermediate frame; slot
reassignment and any ordinary shadow writer must invalidate/recover safely;
allocation failure must retain the current path. CPU cost, DMA deadlines,
render fidelity, lifecycle and actual end-to-end speed remain unverified.
No production source or ROM changed. Reproducible model and results:
`.local/wheel-residency-study/plan.py`, `plans.json`, `feasibility.json`.

### Native wheel copy-plan prototype — 2026-10-04

Added tools/qa_wheel_copy_plan.py. The scratch ROM uses the five actual wheel
maps and deterministic synthetic 16-word cell contents, then checks the whole
shadow plane, all live cache entries and boundary sentinels after every copy
plan. It covers every old/new frame pair, ring wrapping, dependency cycles,
repeated frames, and all four combinations of word alignment for shadow/cache.
Both eight-MOVE.L and MOVEM implementations pass 3600 native transitions each.
The playable release ROM remains unchanged.

Read-only opcode-boundary timing on the pinned stock-speed core measures only
the copy routine plus return/marker overhead, with interrupts masked and no
DMA. Mean scanline costs by wheel0/0h/1/1h/2:
- Eight long moves: 111.50 / 110.07 / 93.89 / 95.79 / 109.61.
- Multi-register moves: 99.31 / 98.18 / 82.42 / 83.94 / 97.62.
MOVEM is the selected prototype for integration. These costs must still be
combined with the real game's other work; they do not prove a 60 fps frame.

The first timing attempt sampled the frame-budget counter before a completed
emulator frame and produced invalid negative spans. Those numbers are excluded
and labeled invalid-initial-timing.json. The corrected probe waits at a native
start gate for one full frame, asserts the 896040-tick NTSC budget and stock
clock scale, then releases the gate under the read-only observer. It asserts
nonnegative intervals and complete transition/alignment coverage.

The native tests prove the copy mechanism on synthetic cell words, not actual
rendered artwork, initialization, allocation, invalidation, DMA deadlines or
end-to-end Boss Rush timing. Those remain the next integration gates. Evidence:
`.local/wheel-residency-study/native-verified.json`, `.local/wheel-copy-native/`
and `.local/wheel-copy-native-movem/`. Full speed and full-game fidelity remain
unfinished.

### Broader segment direct dispatch experiment — 2026-10-04

Tested one per-pass round-to-handler table to extend the living-segment direct
path from round 8 to rounds 2, 3, 4, 5 and 7. Retained relocated-bullet
precedence and the existing curve/event-envelope behavior. All 3,600 three-pass
pool comparisons match the archived dispatcher, including full pools, child
births and failed allocations. The differential tool now accepts these six
rounds; this additional coverage is retained.

Candidate f5d0e5144bc5082f6e5b4f409731975da805ec56129bd2c08b6085631ede6fe7 preserves all 1,000 late-round-eight
4P gameplay hashes and passes independent full-RAM replay, event filtering and
party callback routing checks. However, it needs 1753 video frames
versus 1,738 for 1,000 updates; mean scene cost rises from 971,190.255 to
973281.869. The 40 BC opening samples improve in 3 cases,
remain equal in 30 and regress in 7, costing 25 frames overall. No measurement
errors or ROM changes occurred. Rejected the production change and restored
source, ROM, ELF and symbols together to 0b1b2c79ddd07089618e9e7e45ce24d9acc987849e488edc4814cd0eddef810f.
Evidence and candidate are in .local/bc-segment-rounds/.
Full speed and whole-game fidelity remain incomplete.

### Word-sized actor missing-art flag — 2026-10-04

Retained a word-sized missing-art count in ActorArtCache's existing padding.
The 68000 cache stays 20 bytes; compile-time assertions protect the stride and
offset. Per-draw byte extension becomes one memory-word addition. No art,
simulation, palette, cache-residency or sprite-order rule changes.

Host comparison passes 1,456 updates / 11,358 submissions, including slot reuse,
empty/composite counts, coordinates and complete simulation bytes. Against
0b1b2c79, native late round-eight 4P retains 1,000 gameplay hashes and independent
full-RAM replay. Mean scene cost drops 971,190.255 to 969,556.651 core ticks, but
frame deadline phasing regresses 1,738 to 1,744 video frames / 1,000 updates.
3P drops 1,502 to 1,495 frames and 892,579.898 to 890,922.284 mean ticks, also with
1,000 matching hashes and independent replay. These timings exclude no
simulation updates; scene CPU costs exclude outer input/VBlank/DMA work.

The long 4P route keeps 5,405 updates, identical scaled/drained screenshots,
152 original / 184 extra births and no missing art/drops/remaps; video frames
drop 9,008 to 9,003. Across 40 BC openings, 9 improve, 29 tie and 2 regress
(round 2 4P and round 8 3P by one frame each), net 30 frames saved.
Retained for these measured improvements with the late 4P tradeoff recorded.

All 40 Normal samples preserve 40,040 gameplay hashes. Against older 41749626,
4P sections 3/5/7 cost one extra frame each; section 5's difference was already
present in 0b1b2c79. Other 37 tie. No measurement errors. Boss Rush 4P retains
2,742 updates / 3,000 frames and all 3,000 video hashes; soft reset releases
wheel allocations. This bounded route still misses full speed.
Real 4P BC modal/pause/return/reentry/reset passes; 3,000-update stack probe
keeps 1,560-byte minimum gap and zero overlap. Build/finalization and diff
checks pass; adding layout assertions produces the identical ROM.

Retained ROM: 8946e57b83cc0a0571136c3cc2a6bb0d6c2e4e2b4daaa36e5a2a1c6aca56d6ce.
Source, ROM, ELF, symbols and verification: .local/bc-missing-word/.
Full campaign fidelity and sustained 60 fps in every mode remain unfinished.

### Rejected protected-party bounds outlining — 2026-10-04

Reused the existing noinline party_shots_far helper for the protected-party
aggregate rejection, replacing its identical inline predicate. This preserves
the wrapped distance arithmetic and passes all 32,000 streamed/reference
contact cases (6,953 ordered events) plus party callback routing checks.
Native normal-damage round-four 4P matches 300 gameplay hashes and independent
full-RAM replay, improving 335 to 333 frames / 300 updates. Late round-eight
4P matches 1,000 gameplay hashes and replay, but changes 1744
to 1763 frames / 1,000 updates; mean scene ticks change
969556.651 to 985424.006.
Across 40 BC openings, zero improve, 23 tie, and 17 regress, costing 153 frames.
No measurement errors or ROM changes occurred. Rejected candidate
b67f2a69b25afe1c1df9750be41df87eb3bd1fb60ec21ab2ba1cdb73e17507c3; restored source, ROM, ELF and symbols together to
8946e57b83cc0a0571136c3cc2a6bb0d6c2e4e2b4daaa36e5a2a1c6aca56d6ce. Evidence: .local/bc-party-bounds-outline/rejected.json.
Keep the protected union rejection inline; outlining only saves in the sampled
vulnerable case and does not satisfy the all-mode speed objective.
Full speed and complete natural-campaign fidelity remain unfinished.

### Unprotected actor-avoidance campaign diagnostic — 2026-10-04

Added optional --dodge to qa_bc_campaign_pilot.py. It predicts nearby actors
linearly and selects ordinary directional pad inputs while retaining the
existing firing/aim policy. It reads actor state but never changes game state
except controller input; no protection, seeded health/lives/weapons/credits,
forced death, defeat or stage jump. Default movement is unchanged.
This heuristic does not model terrain, future births or enemy AI turns.

All four player counts launch through the real Home modal, consume the two
ordinary credits through Start, exhaust lives naturally, and return from game
over to Home. Terminal ticks: 1P 12133, 2P 7687, 3P 7227, 4P 8473.
2P also clears round one and reaches round two.
4P clears round one through combat and enters round two at tick 7164 with
P1/P3 surviving and P2/P4 out. The earlier pilot never left round one.
An independent 4P run matches the complete result, gameplay-end RAM hash and
round-two/game-over/Home screenshots. This is new natural first-round coverage,
not a complete unprotected campaign or source-to-port equivalence proof.

The 3P route exposed a diagnostic snapshot race at its second continue:
simulation ticks increment before rendering republishes per-player debug lives.
The driver previously asserted on the stale 255 lives value. It now waits for
both a resumed tick and the live-player snapshot with the same bounded timeout.
The rerun accepts P3's credit at frame 8298 and observes two lives at frame 8301,
with credits 1 to 0 and only P3's unused-continue rank reduced. No game source
change was needed. Continue failures still time out rather than being ignored.

Evidence: .local/bc-dodge-audit/verified.json and per-player captures/results;
the initial diagnostic failure is preserved in .local/bc-dodge-audit-3p.log.
Retained ROM remains 8946e57b83cc0a0571136c3cc2a6bb0d6c2e4e2b4daaa36e5a2a1c6aca56d6ce.
Full unprotected campaign verification, remaining fidelity and sustained
60 fps / 100% speed remain incomplete.

### Clear player-frame outputs only on checkpoint exit — 2026-10-04

bc_player_step_into previously cleared nine output bytes at entry before
normal control/weapon/finish assignments overwrote all of them. Keep the
control assignment first, and clear only weapon/graphics on the checkpoint
exit where those tasks do not run. Generated 68000 code no longer performs
nine unconditional byte clears per player. All task ordering is preserved.

Source replay matches 1,680 player updates, 2,687 common enemy updates, 1,677
trail updates, three deaths and three checkpoint requests. The verifier now
explicitly requires empty weapon/graphics results on every checkpoint exit,
starting from nonzero prefilled output. The 1–4P party-frame test passes.

Against 8946e57b, late round-eight 4P improves 1,744 to 1,721 video frames /
1,000 updates; mean scene ticks drop 969,556.651 to 965,249.642. 3P improves
1,495 to 1,483 frames and 890,922.284 to 887,712.868 mean ticks. All 2,000
gameplay hashes match and both independent full-RAM replays pass.
The long 4P route keeps 5,405 updates and both screenshots identical, with no
missing artwork/drops/remaps; frames drop 9,003 to 8,941.
Across 40 BC openings: 12 improve, 25 tie, 3 regress, net 44 frames saved.
Regressions are round 5 3P +1, round 5 4P +4, round 9 4P +2.

All 40 Normal timings and 40,040 gameplay hashes are unchanged. Boss Rush 4P
keeps 2,742 updates / 3,000 frames and all 3,000 video hashes unchanged; reset
frees wheel allocations. Real 4P BC modal/pause/return/reentry/reset passes.
The sampled 3,000-update stack route keeps a 1,560-byte minimum gap and zero
overlap. Build/finalization and diff checks pass.

Retained ROM: 938cc6f8a5f4768816d2208099f67b9ce4630a977277af26ccf3d689b58b8e98.
Source, ROM, ELF, symbols and evidence: .local/bc-player-event-clear/verified.json.
These are bounded improvements; sustained 60 fps and full campaign fidelity
remain unfinished.

### Caller-owned party-frame result — 2026-10-05

Added bc_runtime_party_frame_into and switched the native scene to a caller-owned
party result. The return-by-value API remains a compatibility wrapper. All result
fields are initialized on every path; this change removes a result transfer
without changing frame order or inactive-player outputs. The party-frame
verifier exercises prefilled direct output by default and the legacy wrapper
with --legacy. Both pass 1–4P input/weapon/trail updates, shared clocks, individual
and all-party checkpoints, audio waits, wave barriers/overflow and allocation
retry cases.

Against 938cc6f8, late round-eight 4P improves 1,721 to 1,716 frames / 1,000
updates and mean scene cost 965,249.642 to 962,661 core ticks. 3P improves 1,483
to 1,482 frames and 887,712.868 to 885,146.843 ticks. All 2,000 gameplay hashes
match and independent full-RAM replays pass. The long 4P route retains 5,405
updates, 152 original / 184 extra births and both screenshots unchanged, with
no missing art/drops/remaps; frames drop 8,941 to 8,912. Across 40 BC openings,
13 improve, 25 tie and two regress (round 4 3P +3, round 7 3P +1), net 40 saved.

All 40 Normal timings and 40,040 gameplay hashes are unchanged. Boss Rush 4P
keeps 2,742 updates / 3,000 frames and all 3,000 video hashes; reset releases
wheel allocations. Real 4P BC modal/pause/return/reentry/reset passes. The
3,000-update stack route improves minimum clearance 1,560 to 1,584 bytes,
with no overlap. Build/finalization and diff checks pass.

Retained ROM: 5ba3de58a78c84e88a5b52f6b4d54b3d21487211338f30f68d288c1281f2db4d.
Source/header/tool/ROM/ELF/symbol snapshots and evidence: .local/bc-party-output/.
Full-speed every-mode gameplay and complete natural-campaign fidelity remain
unfinished; bounded improvements do not establish completion.

### Rejected selective party-result clearing — 2026-10-05

Tested clearing only absent/waiting player results during ordinary frames and
all player results on pre-player stage waits/errors, relying on player updates
to overwrite active outputs. Direct and legacy party tests pass, including new
explicit zero-output assertions for absent players, latched waiting players,
audio waits, invalid party counts and exhausted event budgets. These stronger
tests are retained against the original whole-result initialization.

All 2,000 late 3P/4P gameplay hashes and both independent full-RAM replays match.
The long 4P route retains 5,405 updates and both identical screenshots with no
missing art/drops/remaps, improving 8,912 to 8,902 frames. However, late 4P
regresses 1,716 to 1,717 frames (mean scene ticks 962,661 to 961,326.548);
late 3P stays 1,482 frames with mean ticks increasing 885,146.843 to 885,329.249.
Forty openings improve in 4, tie in 30 and regress in 6, costing 4 frames overall.
The savings do not justify the added initialization branches for this objective.

Rejected candidate d2d222ac801dfea21a5bd9d94b266a3f44aead3bdf0cd8ab58e363df3e74547a;
restored source/ROM/ELF/symbols to 5ba3de58a78c84e88a5b52f6b4d54b3d21487211338f30f68d288c1281f2db4d.
Evidence: .local/bc-party-clear/rejected.json. Full speed and complete
natural-campaign fidelity remain unfinished.

### Rejected ordinary-shot call specialization — 2026-10-05

Split ordinary weapon slots (kinds 0/1) into a smaller noinline helper that
does not take player-position arguments. Preserve source slot order and option
retirement counts; other kinds retain the existing dispatcher. The source
player-runtime replay passes 1,680 updates, three deaths and checkpoints; the
source-ordered weapon/option fixture passes 1,101 tasks across all three
weapon families and both facings. Late round-eight 4P retains 1,000 gameplay
hashes and independent full-RAM replay.

Timing rejects the split: late 4P changes 1716 to
1732 frames / 1,000 updates and mean scene cost
962661.0 to 971435.857 core ticks. The long route
keeps 5,405 updates and identical scaled/drained screenshots but regresses
8,912 to 8,996 frames. Zero of 40 BC openings improve, 24 tie and 16 regress,
costing 152 frames. No measurement errors or ROM changes occurred.
Restored source/ROM/ELF/symbols together to 5ba3de58a78c84e88a5b52f6b4d54b3d21487211338f30f68d288c1281f2db4d.
Candidate 3b0b77c92a839debb6cd5f83d02caf35dfedaada84af2d996b86818b10775f0f and evidence are archived in
.local/bc-ordinary-shot-call/. Smaller argument lists alone do not reduce the
measured frame cost here. Full speed and full campaign fidelity remain open.

### Caller-owned weapon event output — 2026-10-05

Added bc_weapons_step_into and switched the integrated player task to write the
weapon event directly into its frame output. The original return-by-value API
remains a wrapper. Charge, ordinary fire, option fire, beam launch and ordered
slot updates retain their original order and initialization.

Source replay passes 1,680 player updates (including three deaths/checkpoints)
and 1,101 source-ordered weapon tasks across all three families and options.
The weapon-task verifier now pre-fills direct output with nonzero bytes and
compares all event bytes and the complete weapon state against the wrapper on
each task. All comparisons pass.

Against 5ba3de58, late round-eight 4P improves 1,716 to 1,715 frames / 1,000
updates and mean scene ticks 962,661 to 961,237.732. 3P improves 1,482 to 1,473
frames and 885,146.843 to 884,067.856 mean ticks. All 2,000 gameplay hashes and
independent full-RAM replays match. The long 4P route keeps 5,405 updates and
both screenshots identical, with no missing art/drops/remaps, improving 8,912
to 8,903 frames. Forty BC openings improve in 6, tie in 27 and regress in 7,
net nine frames saved. Each regression is one frame: R3 4P, R5 3P/4P, R7 4P,
R8 2P/3P, R10 4P. This is a small measured improvement with recorded tradeoffs.

All 40 Normal timings and 40,040 state hashes remain unchanged. Boss Rush 4P
retains 2,742 updates / 3,000 frames and every video hash; reset releases wheel
allocations. Real 4P BC modal/pause/return/reentry/reset passes. The stack route
retains 1,584-byte minimum clearance with no overlap. Build/finalization and
diff checks pass.

Retained ROM: e517ad594b25d920b3ca98d407a505c59e2fb3eee17229178979b23d92214ca1.
Source/header/tool/ROM/ELF/symbol snapshots and evidence: .local/bc-weapon-output/.
Full speed in every mode and complete campaign fidelity remain unfinished.

### Rejected filled-wheel-cell paired flips — 2026-10-05

Tested marking fully nonblank cached cells in a spare tag bit, then applying
horizontal/vertical flips with paired word loads, swaps and packed long adds
on 68000. Blank-containing cells retain the original per-word path. This uses
no additional RAM. Expanded the host whole-plane test to include fully filled
metatiles as well as partial/blank cells. All 40,000 comparisons pass against
an independent uncached cell_words reference, including slot reassignment,
all flips, ring wrap and independent frame images.

Real 4P Boss Rush preserves all 3,000 video-frame hashes and 2,742 updates;
soft reset releases wheel allocations. Across 246 ready-wheel turns, mean
input-to-scheduler work improves 327.6138 to 324.7602 scanlines, but the maximum
regresses 408 to 445. Scanlines use physical video-frame origin224 across
wraps. The unchanged update rate and larger worst turn reject this variant
for the sustained-speed objective; no broad native synthetic-kernel proof
or full-speed claim is made.

Restored bg.c, ROM, ELF and symbols to e517ad594b25d920b3ca98d407a505c59e2fb3eee17229178979b23d92214ca1.
Candidate 3655c78e1285cf525b7ab610a86bc22a7fc7ae36c12183872fb5c9d39948c9d0 and results: .local/wheel-filled-pairs/.
The expanded host test remains useful coverage and passes restored production.
Full speed and complete campaign fidelity remain unfinished.

### DMA scratch ownership and lifecycle audit — 2026-10-05

The 8192-byte heap allocation is SGDK's temporary DMA data buffer; the 1280-byte
allocation is its DMA operation queue (80 entries), not party storage. It cannot
be lent to wheel frames while queued copies still reference it. Added read-only
flush-time scratch usage to `qa_boss_rush_perf.py` and a reusable driver wrapper
`tools/qa_dma_buffer.py` to observe boot, menus, gameplay and reset. It observes
successful allocation occupancy, not rejected allocations or unvisited paths.
Nested profiler/scheduler hooks are explicitly rejected by the wrapper.

Retained ROM e517ad594b25d920b3ca98d407a505c59e2fb3eee17229178979b23d92214ca1:
4P Boss Rush measured fights peak at 224 bytes, but the complete driver reaches
5760 bytes during boot. The Normal/Boss Rush 4P modal regression also peaks at
5760. The 4P Before Christ menu/pause/reentry/reset regression peaks at **6496**
in Home state 9, with 352 bytes in BC state 14. Both modal drivers pass. Boss
Rush retains 2742 updates/3000 video frames and all 3000 video hashes; the
lifecycle-watched run also matches final RAM. The speed-test exit 1 continues
to indicate missed frames, not an instrumentation error.

Therefore a global reduction even to 6144 bytes is not justified. The starfield
redraw explicitly copies 32 rows of 128 bytes into scratch, although its on-state
source is already persistent ROM. Next evaluate direct persistent-source DMA
for starfield rows (and stable zero rows), then remeasure transition peaks before
changing buffer capacity or introducing compact wheel-frame storage. No game
source or ROM changed in this audit. Results: `.local/wheel-dma-audit/verified.json`
and its lifecycle, normal-modal, bc-modal, and rush subdirectories. Full speed
and full natural-campaign fidelity remain incomplete.

### Persistent-source starfield DMA — 2026-10-05

Retained ROM 51913d8c701eddef8acedc188f4aa66bc51d275507442537307ae854844d8a87.
`video_stars_draw()` queues each star row directly from persistent ROM, or from
one persistent zero row when clearing. The old version copied all 4096 bytes
through SGDK scratch. Transfer order, row lengths, plane addresses and queued
transfer bytes remain unchanged; scratch capacity is still 8192 bytes. This is
a memory/preparation improvement, not a demonstrated steady-gameplay speedup.

Native lifecycle observations: Normal/Boss Rush 4P modal regression peak drops
5760→1664 bytes; BC modal peak drops 6496→2400 for every player count 1–4.
All BC modal/pause/return/reentry/reset checks pass. Injected 4P ending passes,
including its existing score/fade/audio assertions, with peak scratch 2368.
BC Home/modal/play screenshots are identical. Normal frame-driven bot PNGs
change with timing; fixed-update comparisons below provide stronger simulation
checks, not pixel equivalence for those screenshots.

Normal's 40 fixed-update samples match all 40040 state hashes. Timing changes:
2P section9 +1 video frame, 4P section3 −2, section5 −1, section8 +2; all others
unchanged (net zero). Crowded BC 4P R8 warm12000/1000 retains all 1000 simulation
hashes and independent replay; elapsed frames 1715→1716, effectively unchanged.

Boss Rush's old assumption of at most one frame-counter completion per emulator
sample was invalidated by the faster transition. Added a histogram and explicit
multi-completion sample records; still reject jumps above two. At sampled frame
3120, completions2466/2467 fall in one emulator sample, but their preceding input
boundaries have vtimer3084/3085 and following flushes vtimer3085/3086. This is a
boundary-phase effect, not two updates between VBlanks. The candidate completes
2743/3000 updates, with histogram {0:258,1:2741,2:1}; net shortfall257 is reported
separately from258 zero-completion samples. Full speed remains false. Reset frees
wheel allocations. Repeating under the lifecycle observer matches every video
hash and final RAM. Against the old build only187/3000 video hashes match because
the assisted controller is video-frame driven; this is not a pixel-fidelity claim
for that comparison. Initial assertion failure remains in rush.log.

Evidence: `.local/star-direct/verified.json`, before/candidate source and ROM/ELF/
symbol snapshots, normal matrix, late profile, lifecycle audits and rush traces.
Next evaluate a conservatively smaller scratch buffer with allocation-failure
and additional-transition coverage, then use reclaimed heap for a complete
oriented wheel-cell cache or compact frames. The existing last-orientation-only
cache was previously rejected; a complete cache would be a different design.
Full natural-campaign fidelity and sustained 60 fps remain incomplete.

### Full-orientation wheel cache with 4 KiB DMA scratch — 2026-10-05

Retained ROM 02a98098abc7c4a092e2d0d04f2aa7b76ff09f9d15ead2bb93c74af029fed160.
After the persistent-source starfield change, video_init sets SGDK scratch to
4096 bytes. Wheel fallback cache now holds all four orientations independently
for each of56 VRAM slots (7616 bytes). Each tag still checks the source metatile;
a change in slot contents refreshes the requested orientation. Cache hits use
the existing native eight-longword copy. Allocation failure retains uncached
rendering. Full-plane allocation and frame cadence are unchanged. The measured
wheel heap has88 bytes of slot tracking,7616 cache bytes and342 bytes free.

Against51913d8, 246 ready-wheel turns fall from329.613821 to294.613821 mean
scanlines (10.62% less CPU); range310–408 becomes275–415. Cold misses still
increase the maximum, and even the minimum exceeds one frame's budget. Boss
Rush remains2743 updates/3000 video frames,258 zero-update samples and one
2-completion sample (net shortfall257). All3000 video hashes match. Reset frees
allocations. This is a CPU reduction, not a claimed end-to-end fps improvement.

Host delta/cache oracle passes40000 whole planes with four-orientation storage,
including all flip combinations, blanks, slot reassignment, ring wrap and
independent frame images. Normal40 samples match40040 state hashes; net timing
change zero (2Psection9 −1 frame;4Psection3 +1,section5 +1,section8 −1).
Crowded BC4P R8 warm12000/1000 matches1000 simulation hashes and independent
replay,1716→1715 frames. The3000-update BC stack route has5676-byte minimum
peer/stack gap and zero overlap (previous1584); this is route-scoped evidence.

Added optional `qa_dma_buffer.py --allocation-attempts`: it recognizes linked
MOVE.L Dn/An stores to nextDataBuffer and watches the following instruction,
before an overflow can be rolled back. The pinned native profiler supports64
watch PCs rather than8. Absolute-source queue resets are not allocation sites.
This covers the current inspected compiler layout; it does not prove unvisited
paths. All1/2/3/4P Normal/Boss Rush modal drivers pass under this observation,
as do all four BC modal/pause/return/reentry/reset drivers. BC attempts peak2400
bytes (1696 spare); injected4P ending peaks2368 over888 pointer observations.
No observed request exceeds capacity. Ending score/fade/audio checks pass.
Earlier flush-only observations remain in their output folders; they alone
would not detect requests rejected before a flush.

Evidence `.local/wheel-all-orientations/verified.json`, before/candidate source,
ROM/ELF/symbol snapshots, disassembly, allocation audits and native traces.
Other wheels and full natural campaigns still need broader evidence. Next
reduce cache lookup/copy overhead or evaluate compact frame storage to bring
wheel turns below262 scanlines; BC crowded-scene simulation remains the larger
speed deficit. Full60fps and full natural-campaign fidelity remain incomplete.

### Native round-eight actor-pass specialization — 2026-10-05

Retained ROM c97f64bda699622ae040d30923856f82129af4926c359773b459590676697ee5.
The instruction audit in `.local/bc-native-hotspots/` confirms repeated native
round-family dispatch costs in actor_loop_core. Its source manifest binds the
instruction-cycle data to the prior 02a98098 build. Earlier compact common-task
and coordinate-reader variants were checked and not repeated.

The actor loop body is now an always-inline implementation with an explicit
round argument, instantiated inside separate noinline general and eighth-round
loops. Selection happens once per actor pass. The eighth-round instance receives
constant 7 (zero-based round), allowing GCC to remove unrelated round-family
branches. The general instance uses this pass's resource round; metadata is
stable during production actor passes. The final-round specialization remains.
The ROM contains distinct eighth_actor_loop and general_actor_loop symbols.
A first argument-only attempt did not produce a dedicated clone; that was
replaced before runtime qualification. No CPU interpreter is introduced.

Against 02a98098, protected R8 warm12000/1000 updates:
- 4P: 1715→1673 video frames (~35.0→35.9 fps), mean scene cost
  961234.883→944996.815 core ticks. Actor-loop attributed cost falls
  135144786→113020740 ticks over the sample, approximately16.4%.
- 3P: 1474→1422 frames (~40.7→42.2 fps), mean884078.083→867589.135 ticks.
Both 1000-state traces match and independent full-RAM replays pass.
Long4P R8 retains5405 updates,152 original/184 extra births and2253 blocked
retries, with both PNGs identical and no missing art/drops/remaps. Frames fall
8903→8610. Neither route establishes sustained60fps.

Differential host tests pass600 three-pass segment and600 curve pool cases,
including ordered events, child births and full-pool failures. Party ownership,
index restoration, immediate contacts and callback-driven filter changes pass;
event-filter coverage passes256 full general/final loops. Forty BC opening
samples have9 faster,24 unchanged,7 slower, net38 fewer frames. Regressions:
R1 4P+2, R2 4P+2, R3 4P+1, R4 4P+5, R5 4P+1, R6 3P+1, R10 3P+1
(the exact machine-readable table is authoritative). Normal40 cases match40040
state hashes; 4P section3 and5 save one frame each, section8 costs one more,
section9 costs five more: net four extra frames. The4P BC menu/pause/reentry
check passes. Stack route minimum gap5658 bytes, no overlap.

Boss Rush completes2742 rather than2743 updates/3000 frames. Video hashes differ
under its frame-driven controller, so no exact visual equivalence is claimed for
that comparison. Reset frees wheel allocations. The change is confined to BC
runtime source; that one-update timing difference is recorded, not presented
as a speed improvement. Source/ROM/ELF/symbol snapshots and evidence are in
`.local/bc-round-pass/`; `verified.json` records remaining limitations.
Full natural-campaign fidelity and sustained60fps across modes remain open.

### Native workload counts versus Normal — 2026-10-05

No production change; retained ROM c97f64bda699622ae040d30923856f82129af4926c359773b459590676697ee5.
Added read-only `--workload-trace` to the BC scene profiler and Normal fixed-update
driver, with compiler-derived offsets in `tools/workload_metrics.py`. Counts are
active records after scene work/before scheduling, not capacity. Normal additionally
records CPU ticks from its input boundary to scheduler entry; BC records scene
entry to return. Normal includes a little extra input/scheduler setup work. Neither
interval includes the subsequent VBlank wait and DMA flush. Optional Normal
`--no-fire` changes diagnostic pad policy only, allowing more enemies to survive.

Four-player 1000-update samples:
- BC crowded R8: 1673 video frames; mean24.876 world records,1.640 weapon records,
  29.984 SAT entries; mean944996.815 core ticks.
- Normal section8 with AUTO fire: 1024 frames; mean9.543 world,18.212 weapons,
  27.965 SAT;579046.706 ticks.
- Normal section3 with AUTO fire: 1042 frames; mean10.089 world,18.977 weapons,
  30.289 SAT;591650.395 ticks.
- Normal section8 without fire: 1011 frames; mean18.836 world,0 weapons,
  20.513 SAT;533154.517 ticks, with as many as46 world records.

There are21 exact shared (world,weapon,SAT) count buckets between BC and Normal
without fire. Four buckets have at least five observations in both modes:
(17,0,21), (19,0,23), (21,0,24), (23,0,22). BC uses38.4–40.6% more mean CPU
in those buckets. This supports rejecting object count alone as an explanation;
it does NOT prove equal AI, sprite-pixel area, terrain or simulation complexity.
BC's pool also includes dying actors/options; Normal has separate effect pools.
Counts must not be presented as identical enemy counts. BC does have more world
objects in the default firing routes, but fewer active player weapon records.

BC instrumentation preserves1000 state hashes, exact scene timing and independent
replay. Both firing Normal routes preserve1001 state hashes and elapsed frames.
Initial diagnostic errors were an unnormalized LTO symbol name and checking the
VDP frame-budget variable inside a frame rather than at the emulator boundary;
both were corrected. No game slowdown or gameplay edit was involved. Current
source snapshots, per-update readings and comparison table are in
`.local/bc-load-audit/verified.json` and its sample directories. Next prioritize
native BC data layout/processing cost, rather than assuming inherently heavier
content or emulating the source CPU. Full speed and campaign fidelity remain open.


### Native coordinate layout feasibility (2026-10-05)

`tools/qa_bc_coordinate_layout.py` now tests the native 68000 representation
`[integer-high, integer-low, fraction, zero]` against the current
`[zero, integer-high, integer-low, fraction]`. Both retain precisely the same
16.8 position and modular wrap; this is not extra movement precision.
Scratch ROM only, production remains c97f64bda699622ae040d30923856f82129af4926c359773b459590676697ee5.

The original scratch probe mistakenly placed mutable PRNG seed in ROM (.data at
0x3e2504, with no CRT relocation). Corrected to a local seed, verified 96 random
coordinate changes. The corrected probe passes 128,000 paired move/read checks,
plus 262,144 comparisons covering every signed 16-bit velocity at four wrap
boundaries. Guards and low-byte invariants pass. Disassembly confirms direct
word reads in the candidate and the current MOVEP/byte reads in baseline.

Measured kernel ticks for movement with 0/1/2/4 coordinate-pair consumers:
baseline 32816000/55216000/89264000/155568000; aligned
36736000/45696000/57344000/99904000. Movement alone is 11.95% worse because the
velocity must be shifted; movement plus reads is 17.24/35.76/35.78% cheaper in
these kernels. Repeated reads deliberately have memory barriers to model separate
consumers. These percentages are NOT gameplay speed improvements. Evidence:
`.local/bc-coordinate-layout-v3/result.json`, scratch source/ELF and CPU histogram.

Next implementation should start with enemy/actor coordinates and audit every
position mutation, source-byte access, birth copy, scroll delta, culling and
collision consumer. Player/beam structures do not automatically share the same
coordinate width or semantics. Native state comparisons must normalize the
representation, and reference behavior must remain unchanged. Whole-game
conversion, campaign fidelity and sustained 60 fps remain unproven.


### Enemy coordinate read boundary (2026-10-05)

Centralized 120 integer-coordinate reads in `bc_world.c` through typed,
always-inlined `bc_enemy_x/y(const BcEnemy *)` accessors in `bc_rules.h`.
Player coordinates remain separate. Accessors preserve unsigned-int expression
types and the original shift, including the segment reader's host fallback.
The release rebuild is byte-for-byte identical to c97f64...; this is migration
preparation, not a speed improvement. Host baseline comparisons pass 600
three-pass segment cases (36,972 ordered events) and 600 curve cases (36,936
events), including child births and full-pool failures. `git diff --check` passes.
Before/candidate sources, matching ROM/ELF/symbol files and verification:
`.local/bc-coordinate-accessors/verified.json`.

Remaining conversion audit: approximately 60 actor position writes in world
logic, source integer-byte replacement preserving the other bytes, 24-bit scroll
and separation arithmetic, native MOVEP readers, rules motion/culling, renderer,
stage/wave birth paths, and test/trace normalization. These must all change
together before enabling a different storage representation. Goal remains open.


### Enemy coordinate write boundary (2026-10-05)

Centralized 49 `bc_world.c` coordinate writes: 40 integer-pixel setters retaining
the old slot fraction, seven integer-only copies retaining destination fraction,
and two low-integer-byte replacements retaining high integer and fraction bytes.
Helpers in `bc_rules.h` remain always inline and preserve the current 16.8
representation. Initial 51-site version passed 600 segment and 600 curve host
comparisons, but added eight bytes in `bc_actor_spawn_bullet`; restored those
two bullet copies to their explicit expressions. The final entire cartridge is
byte-identical to c97f64..., which verifies no native behavioral/timing change.
Evidence and matching snapshots: `.local/bc-coordinate-writes/verified.json`.

Still explicit in world: two bullet integer copies; two scroll subtractions;
two terrain-correction subtractions; three boss fractional separation additions;
one high-integer-byte test; native segment MOVEP coordinate extraction. These
need conversion with the layout. Rules, renderers, wave/stage sources and test
normalization still need audit. This is preparation, not a gameplay FPS gain.


### Remaining coordinate consumers centralized (2026-10-05)

Retained ROM aeeabb716a7e41bee044f3022d9eb815ff672737d0d5a7e195c872163c090c4d.
`bc_runtime.c`: 42 ordinary spawn setters and two aim reads use the coordinate
API. `bc_boss_draw.c`: 20 reads; `bc_actor_art.c`: two reads; `bc_rules.c`:
11 enemy-only reads (beam/player/target formats deliberately remain separate).
`bc_gallery.c`: two birth setters and two low-byte setters. Renderer host
fallback and actor preview also use helpers. Preview actor is zero-initialized,
so preserving its fractional byte still produces the original whole position.

Two ternary runtime births and integer-zeroing remain explicit to avoid
unnecessary compiler changes ahead of the layout switch. Release is no longer
byte-identical, but all 40 BC opening timings match the prior production exactly,
with no measurement errors. Heavy R8 4P: 1000 states match, independent full-RAM
replay passes, 1673 video frames and mean 944996.815 scene ticks both unchanged.
Host 600 segment +600 curve comparisons, gallery actors, and renderer cache
checks pass. No speed gain claimed. Matching complete BC source snapshots,
ROM/ELF/symbols and results: `.local/bc-coordinate-consumers/verified.json`.

The remaining storage-sensitive production operations are now concentrated:
- `bc_rules.h`: getter/setter/copy/low-byte masks and shifts.
- `bc_rules.c`: enemy_move_axis and enemy_integer_high.
- `bc_world.c`: two bullet integer copies; two scroll subtractions; two terrain
  correction subtractions; three boss fractional separation additions; one
  high-integer-byte test; segment MOVEP reader.
- `bc_runtime.c`: two integer-zeroing operations, two ternary births, rain
  high-integer-byte test.
- `bc_actor_draw.c`: native MOVEP reader.
- QA: native actor hash uses 50-byte records with x/y in first eight bytes;
  normalize these two longs back to 16.8 when comparing an aligned candidate.
  Host ctypes fixtures still write raw original positions and must transform
  enemy records only (not player/beam coordinates) for candidate comparisons.

Next: atomic representation switch for this audited set, then normalized
cross-layout behavior comparisons and actual native timing. Current layout is
still original 16.8; full-speed and full-campaign fidelity remain incomplete.


### Aligned enemy layout: full native experiment rejected (2026-10-05)

Implemented the complete enemy-only aligned coordinate candidate (integer16,
fraction8, zero8), including unsigned wrapping, scrolling, births, boss offsets,
native rendering and culling. First candidate missed `inc/bc_bullet_turn.h`'s
inline homing read; a continuous trace located the first divergence at record
2095, actor slot4, homing direction/velocity/animation. Fixed the header and
reran; don't use v1 performance as a behavior-preserving comparison.

Corrected candidate c80f7ce0082a1c832bbb7c5d31a32f6037f1317b9ae3cc8183654e124096c747
matches all 13,000 normalized native R8 4P state records, including players,
weapons and stage; low padding bytes remain zero. Independent uninstrumented
candidate replay matches full RAM. 600 segment +600 curve host comparisons pass
with enemy coordinates normalized; other round segment cases passed before the
homing-header correction, so do not treat those as final-v2 full-round proof.

Despite fidelity on this route, candidate takes 20,347 video frames vs20,315
baseline, mean scene ticks914720.022 vs914507.142. Forty opening samples have no
measurement errors but net+2 frames (13 samples change by 1–2 frames). The new
layout is NOT retained as a standalone optimization. Attribution over the13k
route: actor renderer saves60,684,596 ticks; straight-actor common saves31,523,072;
generic actor common costs110,466,426 extra ticks, outweighing other savings.
The velocity scaling in motion is the next issue to solve if this direction is
continued. This evidence replaces microbenchmark-only optimism.

Restored production source/header/ROM/ELF/symbol snapshot
`aeeabb716a7e41bee044f3022d9eb815ff672737d0d5a7e195c872163c090c4d`.
Experiments, original/candidate snapshots, full normalized state streams, native
profiles and verification are in `.local/bc-aligned-enemies/verified.json`.
Kept diagnostic additions: `profile_bc_budget.py --enemy-coordinate-shift 8`
normalizes enemy x/y only and asserts padding; `--state-bytes` saves normalized
records for mismatch localization. `qa_bc_segment_fast.py --aligned` builds
archived original headers/sources separately and normalizes only enemy objects.
Default modes retain original representation semantics. Whole-game speed and
campaign fidelity remain unfinished.


### Aligned enemy layout v3 retained with explicit native word loads (2026-10-05)

Inspection of v2 disassembly found that C shifts still generated long loads,
clear-word/swap sequences and a high-byte shift in hot code. The feasibility
microbenchmark had used actual word loads. V3 uses alias-safe unsigned-short
reads for integer coordinates on big-endian m68k and character reads for the
high integer byte; host fallback remains arithmetic. Enemy-only storage is
source16.8 shifted left8, padding0, same precision/wrap. Player/beam formats
unchanged. The homing-header fix from v2 is included.

Retained production SHA760954da219369ae8c16a067f1f09776ad4666056cc642b8b67d56d08b7e13a8.
Final metadata-only header rebuild preserves that SHA. Evidence/snapshots:
`.local/bc-aligned-enemies/verified-v3.json` and `candidate-v3/`.
- 13,000 normalized native R8 4P states match original exactly; independent
  replay passes. Full route20,315→20,122 video frames, mean914507.142→908210.202
  scene ticks. Heavy warm12000/1000 sample1673→1662 frames (~35.86→36.10fps),
  mean944996.815→938681.296, all1000 hashes and replay match.
- 40 BC openings net38 fewer frames. Regressions: R4 4P+10, R6 4P+6, R8 3P+1
  over600 updates. Other deltas recorded in manifest. Still not sustained60fps.
- Normal40 cases: all40,040 state hashes and elapsed frame counts match prior.
  Boss Rush4P2742updates/3000frames unchanged; reset releases wheel allocations.
- Stack R8 4P3000updates min5662B, zero overlaps. Actual4P BC modal/cancel,
  pause/freeze/resume, return/reentry/reset passes.
- Source-oracle:1748 enemy-motion updates,2676 common-task updates,2663 complete
  actor updates pass against existing reference captures. Initial attempt used
  superseded `enemy-motion`; documented malformed phase pairing there caused
  fixture failure. `enemy-motion-verified` is authoritative and passes.
- Host600 segment pool cases, renderer cache1456updates/11358submissions and
  gallery actors pass. Native full-route hashes supply cross-layout coverage.

QA Enemy ctypes access now translates x/y between logical source16.8 and current
storage, selected by `BC_ENEMY_STORAGE_SHIFT` metadata in bc_rules.h. It asserts
zero padding on reads, retains field names/ABI, and leaves non-enemy structures
untouched. `qa_bc_segment_fast --aligned` selects original/candidate storage per
library and separately compiles archived headers. Raw native RAM readers that
interpret enemy positions must still normalize by8; use
`profile_bc_budget --enemy-coordinate-shift 8 --state-trace` for comparisons
against pre-layout builds. Do not apply enemy conversion to BcBeam or players.

The prior v2 rejection above remains accurate for that candidate; v3 corrects
its native-read implementation and is retained. Work remains on velocity cost,
local timing regressions, full-speed Boss Rush/Normal outliers and natural full
campaign verification. No broad fidelity or sustained-speed completion claim.


### Horizontal motion and paired velocity load experiments rejected (2026-10-05)

Baseline remains760954da219369ae8c16a067f1f09776ad4666056cc642b8b67d56d08b7e13a8.
Trace sampling found roughly89% nonzero horizontal velocities in active,
non-delayed enemies. Tried removing the horizontal zero branch (adding zero is
semantically harmless), then tried a native MOVEM.W load/sign-extension of both
adjacent velocities with horizontal unconditional and vertical conditional adds.
The latter uses d0/d1 clobbers, explicit read/write operands and ABI assertions.

Both heavy R8 4P1000-update native traces match all baseline normalized states
and pass independent replay. Baseline1662frames/938681.296mean scene ticks;
unconditionalX1661/938185.906;paired1662/937324.661. However40 opening samples
regress net16frames forX and8 forpaired, chieflyR4/R9; neither retained. Saved
candidate sources/ROM/ELF/symbols and timing matrices:
`.local/bc-motion-x/verified.json`. Restored prior production files; only a stale
movement comment was corrected afterward. Next consider eliminating repeated
velocity scaling structurally instead of these small instruction changes.

`qa_bc_motion_arithmetic.py` updated to current aligned storage and now extracts
both the scalar primitive and the actual two-axis movement block. Native probe
passes655,360 scalar AND paired position/velocity cases, signed extremes/wrap,
word-aligned offsets0/2, unchanged velocities and guard sentinels. Probe covers
655,360 iterations; do not conflate iterations with independent gameplay cases.
Also made the original coordinate-layout microbenchmark require an explicit
archived `--baseline-source`, rather than incorrectly extracting the now-aligned
production implementation as its old-format baseline. Recheck against archived
original source passes128,000 move/read and262,144 exhaustive velocity checks.
Goal remains incomplete; current heavy4P~36.1fps.


### Pre-scaled velocity layout feasibility (2026-10-05)

New scratch-only `tools/qa_bc_velocity_layout.py` compares current signed16
source velocities (scaled each movement) with signed32 velocities scaled once
when assigned. Both keep the currently aligned position representation. The
candidate costs four extra bytes per enemy (128B for32 actors before any other
copies); no production ABI/source/ROM conversion has been made.

Native results `.local/bc-velocity-layout-v2/result.json`:96,000 paired kernel
updates pass with wrap-edge positions, zero/nonzero axes, changing signed
velocities, low padding invariant and guards. Dedicated noinline setter performs
65,536 actual volatile RAM writes, covering every low16 value with deliberately
nonzero high input bits, and verifies signed16 truncation/scaling. Disassembly
confirms the setter call/store loop remains. The initial v1 setter check was
pure arithmetic and could be optimized; v2 is authoritative.

For velocity writes every1/5/20steps, pre-scaled kernels respectively cost
6.42% more /16.74% less /21.76% less than baseline. Counts include both setter
and motion costs, but exclude game-wide AI getters, actor-loop indexing, changed
record stride and storage pressure. These are NOT game FPS gains. Baseline ROM
SHA remains760954da219369ae8c16a067f1f09776ad4666056cc642b8b67d56d08b7e13a8.

Existing13k R8 protected4P trace has297454 comparable active actor transitions
(grouped by slot and routine/death/base identity);272280(91.54%) retain the same
velocity pair,25174change. This is state equality, NOT a write-frequency count:
redundant writes are invisible, move-delayed actors included and identical slot
reuse can be conflated. Evidence `.local/bc-velocity-layout-v2/gameplay-cadence.json`.
Supports trying an actual candidate, but not predicting whole-game gain.

Next candidate must migrate every BcEnemy velocity read/write with signed16
wrap preserved, including assignments from unsigned source words, per-step
acceleration and negation of-32768. Changing BcEnemy by4B also changes BcActor
stride50→54; audit native traces/workload ABI assertions, debug tools, host
ctypes layouts and all actor indexing. Player/beam velocities remain separate.
Retain only after native behavior/timing, heap/stack and mode regression checks.
Goal remains open; no new game-speed improvement this turn.


### Pre-scaled enemy velocities retained (2026-10-05)

Production fec4cbd9f54bbc290da3bd6858bc17d6d6bf592ec93d09dfc75323643c5b9c98.
Enemy velocity fields are now signed32 `motion_vx/motion_vy`, storing source
signed16 values multiplied by256. AI uses logical getters/setters; setters cast
to signed16 before scaling, preserving source wrapping, including acceleration,
unsigned ROM words and negation of-32768. Native movement directly adds stored
longs. BcActor grows50→54bytes (pool+128B); player/beam formats unchanged.
Evidence and matching full BC sources/headers/ROM/ELF/symbols:
`.local/bc-scaled-velocity/verified.json` and `candidate/`.

Native R8 protected4P:13,000 canonical states match previous production exactly,
independent replay passes; full route20,122→19,918 video frames. Heavy
warm12000/1000:1662→1639frames (~36.10→36.61fps), mean938681.296→932997.177
scene ticks; all1000states and replay match. Forty BC openings net49 fewer
frames; only regression R5 4P+1 over600updates. Still far from sustained60fps.
Normal40 samples preserve all40,040 hashes and all frame counts. Boss Rush
remains2742updates/3000frames with wheel allocation release on reset. R8 4P
stack3000updates:minimum gap5406B, no overlaps. Actual4P BC modal/pause/return/
reentry/reset passes.

Source-reference checks pass:1748 enemy-motion,2676 common,2663 natural actor,
109147 R8 actor and68425 R6 actor updates. Host600 segment+600 curve pool cases
match archived narrow-velocity simulation, including births/full-pool failures.
Renderer-cache and gallery checks pass. Native scalar/two-axis movement probe
passes655360 signed-velocity/wrap/sentinel cases using the actual new struct.

QA updates: Enemy ctypes adapts field width and exposes logical source16 values;
`qa_bc_segment_fast --scaled-velocity` uses separate narrow baseline/wide
candidate actor structures. `profile_bc_budget --enemy-velocity-shift 8`
normalizes54-byte records to the canonical50-byte format; padding/range checks
assert encoding validity. Position/velocity shifts now default from sibling
archived bc_rules.h or current header for release, falling back to original
layout for archives without metadata; explicit flags remain available. ABI
workload offset compilation accepts50/54 and derives actual offsets.
`bc_actor_layout.py` centralizes canonical raw-pool reads; campaign pilot,
round10 promotion checks and wave/progression dumps now use it. This also fixes
the pilot's previous assumption that aligned positions were still raw16.8.
Short100-update unprotected Home4P dodge pilot passes, but is NOT a full campaign
proof. Trace/workload smoke check confirms automatic current layout selection.
Velocity microbenchmark now requires explicit archived narrow baseline source.

Natural campaign fidelity, remaining local performance outliers and all-mode
sustained60fps remain unfinished. Next investigate AI velocity getter/assignment
cost and larger hot paths; do not equate kernel savings with gameplay FPS.


### Exact logical velocity extraction retained (2026-10-05)

Retained ROM b1c929ed923ff28a90d8f6c38e939d04cb9f4086ec9b56b3a0ae658d4ee92bc9.
`bc_enemy_vx/vy` now extract unsigned bits8..23 and cast to signed16, replacing
signed division by256. Stored values are signed16*256 with zero low byte;
therefore the operation is exact for every valid stored value. This removes
signed-division rounding work: boss-six native code loses the negative-path
add255 branch and changes ASR to LSR; function listing256→254 instructions/lines.

Native655360 scalar/two-axis arithmetic/getter checks pass, including every
signed16 velocity. Source2663 natural actor and68425 R6 actor updates pass.
HeavyR8 4P1000 hashes match, replay passes,1639video frames and932997.177mean
scene ticks unchanged. All40 BC opening timings unchanged. No FPS improvement
claimed; this is smaller/faster code for the affected AI getter path. Normal and
Rush were not rerun for this BC getter-only follow-up; prior mode results remain
from fec4... rather than falsely being attributed to this ROM.
Evidence/snapshots/disassembly: `.local/bc-velocity-read/verified.json` and
`candidate/`. Full-speed/full-campaign goal remains unfinished.


### Wrapped enemy source-word decoding retained (2026-10-05)

ROM 98d791e78512c6574922a8843f271e0941af9dd71bb4d5af51b4c2fb006231ec.
The enemy animation jump and velocity-table reader share an inline 68000
high-byte/shift/low-byte decoder. Both byte offsets wrap independently to16 bits.
Native327680 checks cover every word value and every offset at five origins,
including the65535-to0 boundary (cyclic De Bruijn payload). Enemy-motion source
oracle1748 updates passes. Heavy R8 4P1000 normalized states match the prior
ROM and independent replay passes:1639→1638 video frames; mean932997.177→932970.374
scene ticks. BC40 opening cases net−5 frames: R5 4P−2, R6 4P−2, R8 3P+2,
R8 4P−3. This is a small mixed gain, not sustained60fps. Normal/Rush were not
rerun for this BC-only decoder change. Matching full BC source/header and
ROM/ELF/symbol snapshots: .local/bc-animation-word/candidate; evidence manifest:
.local/bc-animation-word/verified.json. Full campaign and full-speed work remains.


### Segment countdown fast path retained (2026-10-05)

ROM84e3d9642d9dabe197c69dac9699f9d0dd7a5ceda30a68fd4e8711709b3f1a8c.
Native profiling identified register save/restore overhead in segment_prepare.
An inline wrapper now decrements the timer and invokes segment_prepare_due only
when a turn is due or the segment is a firing tail (dash_started0x54). Tails
still test firing every update, including frames with no turn. Timer0 wraps
to255 exactly as before. Motion/contact/update ordering is unchanged.

Heavy R8 warm12000/1000:4P1638→1547 video frames (~36.63→38.78fps), mean
scene932970.374→913992.681 ticks;3P1383→1326 (~43.38→45.25fps), mean
856343.754→836566.094. Both1000-state traces match and independent replays pass.
Full R8 4P13000 canonical states match archived scaled-velocity baseline fec4...;
video frames19918→19332 and independent replay passes. This full-run comparison
includes the intervening velocity getter/source-word decoder changes.
BC40 opening tests: R2 4P−1, R4 4P−1, R9 4P+1 frames, others unchanged.
Source R8 actor oracle109147 updates passes. Host6000 three-pass segment pool
cases across rounds2/3/4/5/7/8 match archived sources, with ordered births and
full-pool failures. Expanded wait coverage to0/1/2/7/255. Stack R8 4P3000update
sample: minimum5380B separation (previous5406), zero overlap samples.
Normal and Boss Rush were not rerun for this BC-only change. Evidence and full
matching BC source/header/ROM/ELF/symbol snapshots: .local/bc-segment-countdown/
verified.json and candidate/. Full-speed/full-natural-campaign goal remains open.

Additional validation on preceding98d791... ROM:4P forced final-serpent promotion
and menu return passes (4627updates/4726video frames), but ending presentation
was not tested. Unprotected Home4P dodge pilot consumes both real continues and
returns to Home after game over at tick6829 in round1. This verifies that route's
continue/game-over behavior, not natural campaign completion. Logs/manifests in
.local/bc-animation-word/.


### Current-layout common-task O3 recheck rejected (2026-10-05)

After the aligned coordinates, scaled velocities and segment countdown changes,
remeasured the common task without its O2 attribute. Heavy R8 4P1000update
window worsens1547→1549 video frames and913992.681→915047.399 mean scene ticks.
All1000 canonical states and independent replay match. Generated common body
expands611→728 disassembly lines with the same five saved registers and a larger
local frame (28→36B). Rejected the candidate; restored bc_world.c plus the exact
84e3d964... ROM/ELF/symbols before the next experiment. Keep O2.
Evidence: .local/bc-common-current-o3/rejected.json and candidate/.


### Exact RNG arithmetic simplification retained (2026-10-05)

ROM 03ef47c4e437eb5babd8c201ae917aa84cf6d75db19c3c6056491b44f9a7e859. Source RNG first triples the16-bit seed, then
adds the old low byte into the high byte with discarded carry. This equals
3*seed + (seed<<8) modulo65536. Expressing it directly removes byte extraction
and recombination. Native score entry now saves three registers rather than
four; RNG transition itself uses two adds, one8-bit shift and a final add.

New qa_bc_rng_native.py extracts the production transition into a scratch
68000 ROM and checks all65536 seeds against an independently generated source
byte-algorithm table; passes. Source capture5005 transitions passes too.
Heavy R8 4P1000updates:1547→1542 video frames; mean
913992.681→913112.452 scene ticks. Matching3P:1326→1322 frames,
mean836566.094→835926.364. Both1000-state canonical traces match
and independent full-RAM replays pass.40BC openings net−4frames, with local
regressions retained explicitly in verified.json (R2/R8/R9 4P+1, R5 4P+2).
4P BC real modal/pause/reentry/reset check passes. Build has no warnings; diff
check passes. Normal/Rush were not rerun for this BC-only arithmetic change.

Evidence and matching source/header/ROM/ELF/symbol snapshot:
.local/bc-rng-transition/verified.json and candidate/. No RNG sequence, number
of updates, waves, enemy count or graphics were changed. The optimization is
small; sustained60fps and full natural-campaign fidelity remain unfinished.


### Empty stage-event entry trial rejected (2026-10-05)

Tested returning the no-event result in bc_runtime_stage_event before calling
stage_event_execute. Heavy R8 4P1000updates matches every canonical state and
independent replay, but costs1545 rather than1542 video frames. Mean scene
ticks913077.046 versus913112.452 is only a tiny CPU change, not a throughput
gain. Captured86 round-one stage events pass. Restored runtime source and exact
03ef47c4... ROM/ELF/symbols before the direct-output experiment. The expensive
stage calls in this fixture are primarily actual segment-birth attempts, not
empty-handler entry. Evidence: .local/bc-stage-empty-entry/rejected.json.


### Caller-owned internal stage-event result retained (2026-10-05)

ROM e8d82ad007e9e46ea64697515da796ba9d08267125ed5a25f3598cfebd509bdd. stage_event_execute now fills a result pointer
provided by the two public wrappers. Their return-by-value APIs remain intact.
Every handler, initialization, sentinel, stage advance, audio wait and birth
callback retains its original order and logic. The large dispatch function no
longer builds and copies its entire result locally.

Heavy R8 4P warm12000/1000 improves1542→1531 video frames (~38.91→39.19fps),
mean913112.452→908864.726 scene ticks.3P improves1322→1310 (~45.39→45.80fps),
mean835926.364→833073.710. Both1000 canonical states match and independent
full-RAM replay passes. Forty BC opening tests:14 improve,26 unchanged, none
regress, net−51frames. Exact case changes are recorded in verified.json.
Full R8 4P13000states match archived84e3d964... and replay passes; elapsed
19332→19168frames. This full-run comparison includes the intervening exact RNG
change, so the entire164frame gain is not attributed solely to direct output.
Captured86 round-one and170 round-eight stage events pass, including audio
requests, immediate births and failed allocations, with no unsupported events.
Stack sample4P R8 3000updates has5378B minimum separation and zero overlap
samples (previous5380B). Build is warning-free and diff checks pass.

Matching BC sources, headers, ROM/ELF/symbols and evidence:
.local/bc-stage-direct-output/candidate and verified.json. Normal and Boss Rush
were not rerun for this BC-only internal dispatcher change. Full natural
campaign verification and sustained60fps/100% speed remain incomplete.


### Native wheel orientation decode retained (2026-10-05)

ROM 506622c7babdd1503802f240df8f53b25cb834d00dea68055f462024facec346. cached_frame_cell selects one of four cached
orientations using frame_orientation. On68000, ROL.W#2 followed by AND3
replaces the previous variable14-bit right shift; portable code retains e>>14.
All65536 map words pass the production-helper native test. Host40000 whole-plane
comparisons pass, including all flips, blank cells, slot changes, shadow
invalidation, ring wrap and independent images. No cache layout/size changes.

Assisted4P Boss Rush3000frames:2742 updates unchanged, all3000 video hashes
match. frame_cells attribution decreases83,616,260→80,490,900 core ticks
(3.74%). Reset frees wheel allocations. This is a CPU saving, not an FPS gain.
Normal40cases match all40040 states and all frame counts versus e8d82ad.
BC heavyR8 4P1000states/replay match and1531frames/908864.726mean ticks
remain exactly unchanged. Build/diff checks pass. Evidence and matching source,
ROM/ELF/symbol snapshots: .local/wheel-orientation-rotate/verified.json and
candidate/. Full-speed and full natural-campaign goals remain incomplete.

Baseline follow-up on preceding e8d82ad: Normal40cases preserve40040 states
versus fec4...; 2P section9 costs1frame, 4P section8 costs1 and section9 costs2,
others unchanged.26/40 samples miss at least one frame. Boss Rush remains
2742updates/3000frames, all video hashes match fec4..., reset releases wheel
allocations. This supersedes the earlier note that those modes were not yet
rerun. The new profile highlights projectile terrain checks inside weapons_fire
as another substantial target; no terrain change has been made here.


### Signed-word Normal terrain lookup trials rejected (2026-10-05)

Tested a centered64KiB collision table with signed-word indexing in
terrain_solid. New qa_normal_terrain_native.py extracts the actual production
function into a scratch68000 ROM and checks all16,777,216 valid pixel positions
and184,320 out-of-range probes with a synthetic byte-distinct table. Passes.
This test uses gnu99 to match SGDK's unsigned-byte bool ABI; the compiler's
defaultC23 bool keyword rejects that typedef (initial probe build fixed).

Both candidates preserve all3000 video hashes,2742 game updates and successful
wheel-allocation release on the assisted4P Boss Rush route. However, non-
VDP_waitVBlank instruction attribution increases from1,606,841,434 baseline
ticks to1,621,876,710 for the centered table. The compiler outlines shot_move:
the drop in weapons_fire attribution alone is misleading because work moves
into a new function. Forcing shot_move inline improves that candidate to
1,612,674,127 ticks, still slower than baseline. Rejected both without broadening
tests after the measured regressions. No production terrain or weapon change
is retained. Exact level.c/weapons.c and matching ROM/ELF/symbols restored to
506622c7babdd1503802f240df8f53b25cb834d00dea68055f462024facec346.
Evidence/candidates: .local/normal-terrain-word/rejected.json and candidate-v1/
candidate-v2. The exhaustive native terrain diagnostic is retained. Full-speed
and full natural-campaign goal remain unfinished. Future terrain work needs
to reduce total generated probe cost, not simply change index width.


### Native Normal terrain index byte assembly retained (2026-10-05)

ROM bd6c75b9dc04a447c2cb80397cb09c5154b6568d34cb11eb3d600a86cfc7d719. After the existing4096x4096 bounds guard, terrain_solid
uses LSL.W#4 on a zero-extended Y register and MOVE.B of X>>4 to assemble the
row/column index, retaining the original terrain_cells base. An early-clobber
output prevents column/index register overlap. Portable behavior is unchanged.
No collision map, bounds, player movement or projectile lifetime change.

Production-function native test passes16,777,216 valid pixel coordinates and
184,320 invalid-coordinate probes. Test now accepts --output to preserve each
experiment's scratch evidence and defines u32 alongside the SGDK-sized types.
Assisted4P Boss Rush keeps2742updates/3000frames and all3000 video hashes; reset
releases wheel allocations. Non-VDP_waitVBlank attribution decreases from
1,606,841,434→1,597,693,348ticks (~0.57%). Overall Rush FPS is unchanged.
Normal40samples retain40040 hashes;4P sections3/5 each cost1frame, sections7/8/9
save1/2/5 respectively (net6 saved); other timings unchanged. BC heavyR8 4P
retains1000state hashes and replay,1531→1527frames despite mean scene ticks
908864.726→908923.932; this is not a BC CPU reduction. Build/diff checks pass.
Evidence/snapshot: .local/normal-terrain-byte-index/verified.json and candidate/.

Read-only scheduler input-to-entry spans localize247 over262-line updates to
the active wheel fight. Other measured phases have only four such updates.
See rush/phase-work.json (excludes outside VBlank/DMA processing). Wheel cache
heap has88B slot tracking,7616B oriented cells and72B free; full3*4096B images
do not fit. A next candidate is trading some fixed sprite hash-cache RAM for
the existing full-image wheel path. Full-key validation must preserve hash
collisions, and all-mode timing/render comparisons must decide the tradeoff.
Full natural-campaign fidelity and sustained60fps/100% speed remain unfinished.


### Compact sprite hash enables full wheel images (2026-10-05)

Retained ROM b7dad23fa6dac6455887de4307334039b3f18d712d305b9ef37fb1a11864d72b. Two sprite fast-hash arrays shrink512→128 entries
each, freeing6144B of fixed RAM. Full-key validation and the two-way code index
remain; VRAM slot count, collision behavior, assets and actor scheduling do not
change. Hash now folds key>>8 so all four palette bits enter the seven-bit
bucket. Native byte-offset form uses key<<3 XOR key>>5, masked1016; all65536
keys match the portable hash. Initial128-entry/shift6 trial slowed heavy BC4P
1527→1568frames and was superseded (candidate-v1). The shift8 variant improves
that sample to1505frames with899518.977mean scene ticks.

The existing full-wheel-image allocation now succeeds:12288B for three planes,
1634B free in the sampled live wheel heap. Previously only7616B cell cache and
88B tracking fit.4P Boss Rush improves2742→2989 updates per3000video frames,
~54.84→59.78fps.1P/2P/3P current samples complete2995/2990/2990 updates. Each
launches via the actual modal, has no software sprite drops/remaps, and releases
wheel allocations on reset. Longer4P9000frames covers boss indices0..5 and
completes8971 updates (29misses),1394 full-cache frames, zero fallback frames,
no drops/remaps and successful reset cleanup. This remains assisted/bounded
evidence, not full-speed or whole-campaign proof. Full-image preparation uses
the existing incremental startup path; these tests do not establish identical
background startup timing between the full-image and old fallback paths.

All40 Normal samples preserve40040 gameplay hashes AND40040 ordered sprite
pixel hashes versus the exact bd6c75b9... baseline. Timings:4P section3 saves2,
sections7/8 cost2 each and section9 costs1 (net3 extra); others unchanged.
BC40openings net17 extra frames, exact cases in verified.json. Heavy BC3P
regresses1311→1326frames,837125.387mean ticks; heavy4P improves as above. Both
1000-state traces match and independent replays pass. Full BC4P13000 states
match e8d82ad... with19168→19054frames; that comparison includes intervening
terrain/wheel changes and is not attributed exclusively to this cache change.
Full replay passes. BCstack sample has11508B minimum gap and zero overlaps.
Real4P BC modal/pause/reset/reentry passes. Host40000 wheel plane comparisons
cover all orientations, blanks, reassigned slots, ring wrapping and independent
pre-rendered images. Build/diff checks pass.

Retained for the large Boss Rush gain, with BC3P/opening regressions explicitly
remaining to recover. Exact source/header/ROM/ELF/symbol snapshots and manifests:
.local/sprite-cache-wheel-ram/candidate-v2 and verified.json. Full natural BC
campaign fidelity, background startup timing audit, later Rush bosses and
sustained60fps/100% speed across all modes/player counts remain unfinished.


### Wheel image preparation preserves first-turn timing (2026-10-05)

Retained ROM `1669750473952ea96be03ea472f1f1e22d1a7b57035353b4cd5cdf1145581b3c`.
The full-plane wheel cache previously ignored animation requests until all three
images were prepared. `bg_frames_show` now accepts requests after preparation
starts, uses completed images when available, and draws incomplete requested
poses directly into the shadow. A later direct request cancels an earlier pending
image. Simulation and animation cadence remain unchanged.

Native 4P input-boundary traces show the first displayed/requested pose at relative
update 15, matching the previous uncached/fallback path; the prior full-image path
waited until update 23. This restores the missing first turn. The startup host
verifier passes 8192 whole-plane comparisons across partial preparation, repeated
requests, all heights/orientations/ring positions and allocation failure. Running
that verifier on the previous source fails as expected. The existing 40000-plane
verifier also passes.

Assisted real-modal Boss Rush samples, 3000 video frames each:
- 1P: 2994 updates, 6 missed frames.
- 2P: 2989 updates, 11 missed frames.
- 3P: 2989 updates, 11 missed frames.
- 4P: 2988 updates, 12 missed frames.

All four samples report zero sprite drops/remaps and release wheel allocations
on soft reset. The fidelity fix costs one update in these samples compared with
the previous full-image build. It is retained to preserve visible timing, not
claimed as a speed improvement. The 4P trace has four input-to-scheduler spans
longer than 262 lines: boss loading, wheel setup, wheel teardown and the next boss
load. These CPU spans do not explain every missed presentation deadline; DMA and
scheduler timing remain part of the investigation.

Evidence and matching source/header/ROM/ELF/symbol snapshot:
`.local/wheel-startup-timing/verified.json`, `startup-comparison.json`,
`overruns.json`, and `candidate/`. No release rebuild occurred during native tests.
Build and diff checks pass. Normal/BC simulation paths were not changed or
remeasured for this focused startup fix. Full natural BC campaign fidelity and
sustained 60 fps / 100% speed in every mode/player count remain unfinished.


### Wheel preload collection avoids repeated linear searches (2026-10-05)

Retained ROM `a9d00c3445d3fca74c1b0baa2adc967ec0f8ebbfe6ecd860ecfee9c14587b77c`. `bg_frames_begin` now uses a temporary
512-byte bitset for the complete 12-bit metatile ID space. It preserves first-use
order and the existing 64-entry cap, including IDs repeated with different flips.
The buffer is on the setup call's stack and consumes no persistent heap/static
RAM. The collector stops once the existing output cap is filled.

`qa_wheel_preload_order.py` extracts the production collector and compares its
output with the original independent linear algorithm in 20480 cases: all 4096
starting IDs, flips, repeats, and 63/64/65 distinct-ID boundaries. All pass.
Existing startup/general whole-plane checks also pass (8192/40000 comparisons).
Native 4P wheel setup input-to-scheduler time drops from 338 to 286 scanlines.
It still exceeds 262 lines; this is a measured partial improvement.

Assisted 3000-video-frame Boss Rush results versus wheel-startup-timing:
- 1P: 2994 → 2996 updates.
- 2P: 2989 → 2990 updates.
- 3P: 2989 → 2990 updates.
- 4P: 2988 → 2989 updates.

All samples retain zero sprite drops/remaps and pass reset allocation cleanup.
4P video frames match for the initial 1513 frames; the recovered deadline then
changes video-frame-driven control timing, so later hashes are not a fidelity
comparison. Exact collector order is instead verified directly. Build and diff
checks pass. Source/header/ROM/ELF/symbol snapshots and manifest are under
`.local/wheel-meta-bitset/candidate/` and `verified.json`. Normal/BC were not
remeasured for this focused collector change. Natural full BC campaign fidelity,
later Boss Rush bosses, and sustained 60 fps across all modes remain unfinished.


### BC actor renderer walks parallel arrays directly (2026-10-05)

Retained ROM `12cfaa8946578b8e6cdacf1a90ec696736872a3ef213f193b657e8a890961801`. `bc_actors_draw` now advances actor and
art-cache pointers together instead of reconstructing both addresses from the
slot index. The full pool is still visited in ascending order, including inactive
slots, and composite dispatch, art selection, clipping, cache residency and
simulation updates are unchanged. No structure sizes or persistent RAM change.

Exact release-before/candidate native heavy R8 comparisons, warmup 12000 and
1000 measured updates:
- 3P: 1326 → 1323 video frames; mean scene ticks 837125.387 → 834607.312.
- 4P: 1505 → 1486 video frames; mean scene ticks 899518.977 → 897197.196.

Both comparisons preserve all 1000 canonical gameplay states and pass independent
uninstrumented replay. The production renderer host comparison passes 1456
updates / 11358 submissions, including slot reuse, sprite keys/buckets,
coordinates, composite/empty counts and unchanged simulation bytes.

All 40 protected BC openings were measured before/after, with no measurement
errors. Net video-frame change: -34. Regressions:
- Round 8, 3P: +2 frames.

The change is retained for overall BC CPU/timing improvements; the opening
regression remains explicit. This is not sustained full-speed performance:
heavy 4P is approximately 40.4 simulation updates/second on the 60-frame basis.
Normal/Boss Rush do not call this BC actor renderer and were not remeasured in
this change. Build/diff checks pass. Exact source/header/ROM/ELF/symbol snapshots
and evidence: `.local/bc-render-pointer-walk/candidate/` and `verified.json`.
Natural full BC campaign fidelity and sustained all-mode 60 fps remain unfinished.


### Round-eight-only O2 loop experiment rejected (2026-10-05)

After retaining the BC renderer pointer walk, tested an O2 attribute only on
`eighth_actor_loop`, leaving the shared/general/final loops unchanged. Generated
loop size shrank from 23200 to 22074 bytes, but heavy 4P R8 (12000 warmup,
1000 updates) regressed 1486 → 1493 video frames and mean scene ticks
897197.196 → 898186.793. All 1000 canonical states match; independent replay
passes. Smaller generated code did not reduce the measured execution cost.

Rejected and restored the exact previous source and matching ROM/ELF/symbols:
`12cfaa8946578b8e6cdacf1a90ec696736872a3ef213f193b657e8a890961801`.
Evidence/candidate snapshot: `.local/bc-eighth-loop-o2/rejected.json` and
`candidate/`. No native test was running during restore. No broader timing
matrix was warranted for this regressing candidate. Full-speed and full natural
campaign requirements remain unfinished.


### Frame-cost audit and native pose switch selection (2026-10-05)

Fresh current-layout heavy R8 4P audit: 1000 updates in 1486 video frames,
mean scene 897197.196 core ticks against an 896040-tick frame. 470 scene
calls already exceed the whole frame, before outer input/display work. Scheduler
calls total 465.0365 frame equivalents, including waits AND DMA/processing;
this is not all removable overhead. Peak tick12960 costs1488690 ticks (1.66
frames), with32 post-update actors,4 weapon records and40 SAT entries. Isolated
peak profiling reproduces that exact cost. Largest contributors include common
actor work293370 ticks, drawing202412, eighth loop149912, players146104 and
segment turns123382. Trace states match baseline and independent replay passes.
Evidence: `.local/bc-frame-cost-audit/verified.json`.

The peak instruction profile exposed a variable long shift generated by GCC
bit-test switch lowering in `bc_actor_pose`. Applied native-only
`optimize("no-bit-tests")` to this art selector. No mapping data or algorithm,
actor state, object count or update frequency changes. Retained ROM `b6505f60686ce484076c5eceb27b59feb2fdba16c091c1be470186034081d2af`.
Heavy comparisons (1000 updates,12000 warmup):
- 3P: 1323→1316 video frames; mean scene ticks 834607.312→832491.401.
- 4P: 1486→1486 video frames; mean scene ticks 897197.196→895544.972.

Both retain1000 identical canonical states and pass independent replay.
60192 host pose/position comparisons,65536 native attribute cases and1456
renderer cache updates/11358 submissions pass. An initial actor-art command was
missing its mandatory capture argument; it did not run and is not counted as
validation. The dedicated pose comparison supplies the broad mapping check.

All40 opening measurements completed without errors. Net+3 video frames;
changed cases (round,players,frame delta):
- R4 3P: +2.
- R4 4P: -4.
- R5 4P: +1.
- R6 2P: +1.
- R6 3P: +1.
- R7 3P: +1.
- R7 4P: +2.
- R8 4P: -1.
- R10 3P: +1.
- R10 4P: -1.

Retained for lower CPU cost in both heavy multiplayer scenes, explicitly with
these opening regressions. Build/diff checks pass; no release rebuild occurred
during native measurement. Exact source/header/ROM/ELF/symbol snapshot and
manifest: `.local/bc-pose-no-bit-tests/candidate/`, `verified.json`. Normal and
Boss Rush do not use this BC selector and were not remeasured. Native gallery
pixels and full natural campaign were not rerun. Sustained60fps/100% speed and
full natural BC campaign fidelity remain unfinished.


### Native pose flip extraction uses short rotates (2026-10-05)

Retained ROM `8319bf8c85349f94a6d4c80d76841d39064a0ca5bc67bc21d0fea83152d841c5`. The native `bc_actor_pose` converts attribute
bits11/15 to packed flip bits using ROL.W #5 / ROL.W #2 and masks, replacing
compiler-generated variable shifts by11/14. The portable expression remains
unchanged. Generated instructions use separate registers for both read/write
operands. No ROM lookup table, persistent cache, art data or behavior changes.

All65536 attribute words pass the production native selector probe, including
packed key/visibility/handling and unchanged actor fields. 60192 host positioned
pose comparisons and1456 cache updates/11358 sprite submissions pass. These
are respectively one-family native attribute coverage and broad host art mapping
coverage, not full native gallery video proof.

Heavy R8 with12000 warmup and1000 measured updates:
- 3P: 1316→1314 video frames; mean scene ticks 832491.401→830974.774.
- 4P: 1486→1486 video frames; mean scene ticks 895544.972→894447.127.

Each retains1000 exact canonical states and passes independent replay. All40
opening measurements completed without errors; net5 video frames saved. Changes:
- R2 4P: +1 frames.
- R4 3P: -3 frames.
- R4 4P: +1 frames.
- R5 3P: +1 frames.
- R7 4P: -2 frames.
- R8 4P: -1 frames.
- R10 3P: -2 frames.

Retained with the three one-frame opening regressions explicit. Source/header/
ROM/ELF/symbol snapshot and manifest: `.local/bc-pose-flip-rotate/candidate/`
and `verified.json`. Build/diff checks pass. Normal/Boss Rush do not use this
selector and were not remeasured. Heavy4P remains about40.4 updates/sec; full
natural campaign fidelity and sustained all-mode60fps/100% speed are unfinished.


### Diagnostic campaign pilot uses actual movement speeds/limits (2026-10-05)

QA-only change; playable ROM remains
`8319bf8c85349f94a6d4c80d76841d39064a0ca5bc67bc21d0fea83152d841c5`.
Dodge prediction previously assumed2px on every axis and bounds20..236/20..212.
It now matches production cardinal/diagonal speeds3/2, upgraded4/3, and clamps
X16..240,Y32..200. Speed-pickup state is read from each real player using a
compiler-derived `BcPlayerControl.speed` offset (no simulated state mutation).
All18 chosen direction/speed combinations compare exactly with production
`bc_direction` compiled independently for the host.

Actual unprotected Home4P runs on the identical ROM: old pilot loses at tick6829,
corrected pilot at5814, both in round1. This fixes the diagnostic movement model,
not a claimed survival improvement. Each uses both real credits/continues and
returns from game over to Home; no seeded health/weapons/lives or forced defeat.
The first experimental run was superseded after correcting local velocity-name
shadowing; only `corrected/` is the final run. Broad terrain/AI/birth prediction
is still absent, and no full natural campaign completion is established.

Evidence: `.local/bc-pilot-movement/verified.json`, `baseline/`, `corrected/`.
Build unnecessary (tools only); diff check passes. Next campaign-test work should
account for terrain/camera movement before interpreting pilot deaths as game
faults. Full natural campaign and sustained all-mode60fps remain unfinished.


### Terrain-aware controller pilot extends unprotected campaign coverage (2026-10-05)

QA-only; ROM unchanged at
`8319bf8c85349f94a6d4c80d76841d39064a0ca5bc67bc21d0fea83152d841c5`.
The dodge pilot reads the actual immutable round collision tables through
compiler-derived BcActorStepData offsets and predicts horizontal/vertical probes
in source order. Candidate paths stop at solid cells and use actual speed/clamp
rules. Terrain data is cached by its ROM addresses, with range checks. All test
interactions remain ordinary controller inputs; protection/health/lives/weapons,
enemy defeat and stage completion are never forced.

New independent comparison compiles production `bc_direction`,
`bc_terrain_solid`, `bc_move_step` and matches20000 terrain lookups plus20000
stationary-camera movement cases against the Python prediction, covering wrap,
cell boundaries, cardinal/diagonal movement and both speeds. Scrolling/camera
changes and crushes are explicitly outside this prediction proof.

Unprotected Home/modal runs with actual shared credits:
- 1P: game over at tick26000, round1; both continues accepted, Home return verified.
- 2P: game over at tick18891, round2; both continues accepted, Home return verified.
- 3P: game over at tick14976, round2; both continues accepted, Home return verified.
- 4P: game over at tick11138, round2; both continues accepted, Home return verified.

2P/3P/4P each defeats the first boss and reaches round2 through normal gameplay.
4P previously ended in round1 at5814 ticks with the corrected speed-only pilot;
terrain awareness extends that route to11138 ticks in round2. 1P remains round1.
These are bounded natural-path checks, not complete campaign verification. Enemy
AI/birth prediction and scrolling-aware movement/crush avoidance remain missing.

Evidence, screenshots and tool snapshots:
`.local/bc-pilot-terrain/verified.json`, `run*/`, `prediction.log`, `tools/`.
No game rebuild required; diff check passes. Full natural campaign fidelity and
sustained all-mode60fps/100% speed remain unfinished.


### Optional scrolling/crush prediction in the campaign pilot (2026-10-05)

QA-only, unchanged playable ROM
`8319bf8c85349f94a6d4c80d76841d39064a0ca5bc67bc21d0fea83152d841c5`.
Added `--scroll-prediction` (requires `--dodge`) to read player fractional positions
and current stage position/velocity through compiler-derived offsets. The pilot
predicts terrain motion and crushes in unsigned8.8 source order. Its camera
projection assumes current velocity persists; future stage-script changes and
wave holds can differ, so this remains opt-in and does not replace the default
stationary predictor. The test never writes gameplay health/lives/state.

Independent production-C comparison passes20000 terrain lookups,20000 stationary
steps and20000 scrolling steps, including signed scroll velocities, fractional
positions, wrapped arithmetic and crush returns. Movement tests use synthetic
collision maps and compare against actual `bc_move_step`, not another Python
implementation of the helper.

Unprotected real Home/modal runs with two accepted real continues each:
- 1P ends at tick30449 in round1, then returns Home.
- 4P ends at tick11042 in round2, then returns Home.
This adds no new round coverage over the terrain-only pilot (1P26000/R1,
4P11138/R2). Retain as a checked diagnostic option, not a survival improvement
or campaign completion claim. AI/birth prediction remains approximate.

Evidence and tool snapshots: `.local/bc-pilot-scroll/verified.json`, `run-1p/`,
`run-4p/`, `prediction.log`, `current-tools/`. Diff check passes. No game rebuild
was necessary. Full natural campaign and sustained all-mode60fps remain open.


### Predecode immutable segment animation/velocity tables (2026-10-05)

Retained ROM `a2b8b882c59a0311279be1eea6d2a9aacd7ef84d4e4f8be047026d3b4546d75b`. Scene entry explicitly binds the six rounds
with segmented enemies after assigning actor_data round, source data and
relocation. The binder decodes16 animation words and both source speed variants
into native values, with velocities in the current scaled storage format.
`segment_prepare_due` uses these for the explicitly bound data object, valid
directions and supported speeds. Other callers/speeds retain direct source reads.
NULL or unsupported-round binding disables the cache. Binding requires immutable
round tables/identity fields until the next bind; the live scene satisfies this.
Turning/aiming, waits, firing order and all source AI updates remain unchanged.

New --bind-segments coverage in qa_bc_segment_fast compares both cached speeds
against the old dispatcher:6000 three-pass pool cases across rounds2/3/4/5/7/8,
including countdowns0/1/2/7/255, immediate child births and allocation failure.
Another1000 unbound round8 cases verify fallback. Complete actors/player/counts
and ordered events match. The initial host command encountered duplicate archived
headers; using a source-only baseline directory resolved it before these checks.

Heavy R8 (12000 warmup,1000 measured updates):
- 3P: 1314→1299 video frames; mean scene ticks 830974.774→825763.365.
- 4P: 1486→1465 video frames; mean scene ticks 894447.127→889400.435.

Each has1000 matching canonical states and independent replay. Forty BC opening
samples finish without measurement errors, net3 frames saved; changed cases:
- R2 4P: -1 frames.
- R4 4P: +1 frames.
- R6 2P: -1 frames.
- R6 4P: -2 frames.
- R7 4P: +1 frames.
- R8 3P: -1 frames.
- R8 4P: +1 frames.
- R10 4P: -1 frames.

Long4P R8 trace retains all13000 canonical states versus the older sprite-cache
baseline,19054→18764 video frames, replay passes. That timing comparison includes
intervening renderer/pose changes and is not attributed solely to this cache.
4P Boss Rush remains2989/3000updates,746full-wheel-cache frames,zero fallback,
drops or remaps; reset releases allocations. Its remaining free heap is1364B.
BCstack sampling3000updates has11238B minimum gap and zero overlaps. The real4P
menu/cancel/launch/all-controller pause/reset/re-entry test passes.

Exact source/header/ROM/ELF/symbol snapshot and evidence:
`.local/bc-segment-native-tables/candidate/`, `verified.json`. Build/diff pass;
no release rebuild during native measurements. Heavy4P is about41updates/sec,
not sustained60. Normal full timing was not rerun. Full natural campaign and
universal full-speed/whole-game stack requirements remain unfinished.


### Current Normal traces and all-mode player modals revalidated (2026-10-05)

ROM `a2b8b882c59a0311279be1eea6d2a9aacd7ef84d4e4f8be047026d3b4546d75b` unchanged throughout. After the recent BC table/static-RAM
changes, all40 Normal fixed-update samples preserve40040 canonical gameplay
hashes and40040 ordered SAT sprite-pixel hashes versus b7dad23f.... Zero software
sprite drops or runtime remaps in these samples. Timing changes:2P sections2/9
save1frame each;4P section8 costs1 and section9 saves1 (sections zero-based).
Other36 timings unchanged.15/40 samples meet1000updates in1000video frames;
25 miss at least one deadline. Worst is4P section3 at1041frames (about57.64
updates/sec on60Hz basis), unchanged versus baseline. These tests include
protected fixed routes and do not prove whole-game speed/background fidelity.

Real Home/menu regression passes for each1/2/3/4P:
- BC modal cancel/launch, real audio, every selected controller's pause/freeze/
  resume, terminal return, re-entry and paused soft reset.
- Normal modal selection/cancel, selected-player join and unselected exclusion,
  real wave timeline, controlled four-record spawn scaling4/4/6/9, P3/P4 merge.
- Boss Rush modal selection/cancel and20/20/30/45 boss-hit scaling, selected-party
  start, saved count reload and version3 settings migration.

Additional-pad input is supplied by the logical pad hook; this does not verify
physical adapters. Controlled spawn/merge probes are explicit debug operations,
not natural campaign claims. Normal/multiplayer/Rush scratch-offset consumers
ran serially; independent BC menu checks used their own paths. No rebuild during
any native tests. Diff check passes.

Evidence: `.local/normal-after-bc-tables/verified.json`, `normal/results.json`,
`bc-menu-*p.log`, `multiplayer-*p.log`. Player-option modals are verified on the
current build, but sustained all-mode60fps and full natural BC campaign remain
unfinished. No new runtime optimization was retained in this validation turn.


### Compact per-player multiplayer HUD cache (2026-10-05)

Retained ROM `77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94`. The3P/4P HUD's cached fields now sit together
per player, with one pointer walk instead of repeatedly addressing separate
arrays. The cache is invalidated whenever the panel opens; score/lives/energy,
messages/names, weapon/speed and boss-bar conditions/commands remain unchanged.
The cache adds56bytes staticRAM; solo/two-player HUD paths remain unchanged.

A production-function differential compares every draw command across4000
frames, including3P/4P resets, unchanged frames, all messages, names, scores,
lives/energy, weapons/speed and boss bars. Commands match exactly. Normal4P
section3:1041→1039frames, panel attributed ticks36581468→28399168 (about22%
less); total measured non-VDP-wait ticks725779028→717576839. This checks total
active attribution as well as the function, avoiding an outlining-only claim.

All40 Normal samples preserve40040 gameplay AND40040 ordered sprite-pixel hashes,
zero measurement errors. Changes (sections zero-based):4Psection3 saves2,
section5 saves1,section7 saves3,section8 saves1,section9 costs3; net4saved.
All other timings unchanged. Only15/40 samples meet1000updates/1000frames.
Heavy BC4P remains1465frames and889400.435mean scene ticks, all1000 states
match and independent replay passes.4P BossRush improves2989→2990updates in
3000video frames; full wheel images still allocate, zero fallback/drops/remaps,
1308B free heap, reset cleanup passes. Real3P/4P Normal/Rush menu/join/merge/
spawn/health/settings regressions pass after the timing tests ran serially.

Build/diff checks pass. Exact source/header/ROM/ELF/symbol snapshot and evidence:
`.local/hud-multi-cache/candidate/`, `verified.json`. HUD command comparison is
host-side; sprite hashes are not whole-background pixel proof. Section9 timing
regression remains explicit. Full natural BC campaign and sustained all-mode
60fps/100% speed remain unfinished.

### Segment velocity record experiment — rejected

Paired cached X/Y velocities into one record to share the table address.
The native round-eight 4P sample (12,000 warmup updates, 1,000 measured)
preserved all 1,000 simulation hashes and passed independent replay. Mean
scene CPU ticks fell slightly, 889400.435 to 889151.081, but elapsed video
frames rose from 1465 to 1469. Rejected the change: frame pacing is the
objective, and the CPU change does not establish a speed improvement.
Restored source and matching ROM/ELF/symbol snapshot, SHA256
`77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94`.
Evidence: `.local/bc-segment-packed-record/rejected.json`, candidate and
before snapshots, and `after/result.json`. No gameplay reduction made.
Sustained all-mode 60fps and complete natural BC campaign remain unverified.

### BC actor-renderer O2 experiment — no machine-code change

Applied a native-only O2 attribute to bc_actors_draw and rebuilt (compiler
and linker invocations recorded). Final ROM remained byte-identical to
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
The round-eight 4P 12,000-warmup/1,000-update native profile therefore
remained 1465 video frames, 889400.435 mean scene ticks, with all 1,000
state hashes matching and independent replay passing. Removed the redundant
attribute and restored matching source/ROM/ELF/symbol files. Evidence:
`.local/bc-render-o2/rejected.json`, build.log, candidate/, after/.
Renderer cost remains the largest attributed routine (143491040 ticks);
this compiler-setting experiment supplies no speed improvement. Full-speed
and natural full-campaign requirements remain open.

### SAT register-allocation experiment — rejected

Replaced the fixed d0–d3 MOVEM.W sprite entry write with four MOVE.W stores
using compiler-selected data registers. Native 4P round-eight benchmark
(12,000 warmup / 1,000 measured updates) worsened from 1465 to 1489 video
frames, and mean scene ticks from 889400.435 to 893059.398. All 1,000
simulation states match; independent replay passes. No sprite-pixel proof
is claimed for this rejected candidate. The candidate includes the condition
code clobber required by MOVE.W; adding that clobber and rebuilding produced
the identical measured ROM (8537f69127c439843384a86cfcef25ebf9b50798150f7f5bc73c7697def2cd83).
Restored sprites.c and matching baseline ROM/ELF/symbol snapshot
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/sprite-sat-free-registers/rejected.json`, candidate/, after/.
This rules out relaxing the four-register SAT write as a speed improvement
in the heavy fixture. Full-speed and full natural campaign remain open.

### Outlined actor-art refresh — rejected

Moved pose decoding/cache refresh to a noinline helper while preserving
all keys and the draw order. Host cache comparison passed 1,456 updates
and 11,358 submissions. Heavy native 4P round eight improved 1465→1460
video frames, but mean scene ticks rose 889400.435→891019.150. Heavy 3P
regressed 1299→1304 and 825763.365→828617.377 ticks (3P reference is the
pre-HUD segment-table build). Both compare all 1,000 state hashes and pass
independent replay. Forty BC opening samples cost four extra frames net
against the segment-table matrix; mixed individual gains/regressions remain
in the raw results. This does not support retaining the helper.
Restored exact prior source/ROM/ELF/symbol snapshot, SHA
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-art-refresh-helper/rejected.json`, cache.log, after/,
3p/, matrix/, candidate/. Host submission comparison is not native pixel
proof, and bounded protected fixtures do not establish full-campaign fidelity.
Full-speed and full natural campaign requirements remain unfinished.

### Four-slot shot-index scan — rejected

Inspection confirms multiplayer runs the shared enemy loop once after all
player updates. Tested changing the collision-index scan from two to four
consecutive shot slots per loop iteration, preserving eligibility and source
slot order. Host comparisons pass 32,000 scans (5,336 contacts / 2,070
damaging hits); native probe passes 4,096 complete index comparisons with
dirty top bytes, fractions, flags, half sizes and sentinel preservation.
Heavy native 4P round eight (12,000 warmup / 1,000 measured) nevertheless
regresses 1465→1485 video frames, 889400.435→892593.842 mean scene ticks.
All 1,000 simulation states match; independent replay passes. Rejected and
restored bc_rules.c plus the matching ROM/ELF/symbol snapshot, SHA
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-shot-index-four/rejected.json`, host.log, native.log,
after/ and candidate/. No enemy/player updates removed. Full-speed and
full natural campaign requirements remain unfinished.

### Animation high-byte flip update — rejected

Tested a native big-endian high-byte assignment for the two animation flip
bits, leaving the low attribute byte untouched and retaining the portable
word expression on host builds. The full-scene native 4P round-eight test
(12,000 warmup / 1,000 measured updates) regresses 1465→1482 video frames
and 889400.435→891692.494 mean scene ticks. All 1,000 simulation hashes
match; independent replay passes. This bounded state trace does not claim
exhaustive attribute validation. Rejected, with source and matching baseline
ROM/ELF/symbol restored to SHA
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-animation-byte-flips/rejected.json`, after/, candidate/.
Full-speed and full natural campaign requirements remain unfinished.

### Controller-only rapid-fire campaign diagnostic — retained

Added optional --rapid-fire to qa_bc_campaign_pilot.py: three simulation
updates held / three released, using ordinary pad bits and press edges.
Default charge behavior is unchanged. No cartridge/source gameplay change.
On current ROM 77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94,
all runs launch through Home/modal, use normal damage, and accept the two
real continues through Start, without health/weapon seeding or forced defeat.
Fresh 1P default baseline ends at tick26000 in round1. Rapid-fire 1P defeats
the first boss and enters round2 at tick6768 with two lives, eventually ends
at tick32170 in round2. Rapid-fire 4P enters round2 at tick6743 and ends at
tick14995. Every run returns to Home after normal game over, and both
continue offers are accepted. No later round or complete natural campaign
is verified; these input patterns are diagnostic, not a gameplay fix or
proof of universal speed. Evidence: `.local/bc-pilot-rapid-fire/verified.json`,
baseline-1p/, 1p/, 4p/, and before/after pilot snapshots.

### Optional pickup-seeking campaign pilot

Added --seek-pickups to the controller-only diagnostic. It selects the
nearest live weapon/option/life pickup inside player bounds and within112px;
existing hazard/terrain steering remains active with --dodge. Reports
pickup_target_updates (steering decisions, NOT confirmed collections).
Default behavior is unchanged; ROM remains
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Natural Home runs with rapid fire and normal damage:1P reaches round2 at
tick6604 (prior6768), ends tick37253 (prior32170);4P reaches round2 at6797
(prior6743), ends14515 (prior14995).855/1321 player-update decisions target
pickups respectively. Both use exactly two real accepted continues and
return to Home after game over; no seeded weapons/health or forced defeats.
No additional rounds were verified. Retained as an optional input pattern
with the multiplayer regression explicit, not a game optimization.
Evidence: `.local/bc-pilot-pickups/verified.json`, 1p/, 4p/, before/after
pilot snapshots. Full natural campaign and full-speed requirements stay open.

### Read-only natural-death trace and immediate avoidance

Added --death-trace to the campaign pilot, using compiler-derived world
state/invulnerability offsets. Logs consecutive alive→dying snapshots with
player/camera positions, previous held buttons, and five nearest actor
records. It records evidence, not an asserted cause of death. Exact baseline
end RAM, video frame, tick, round transitions and continue records match
the prior uninstrumented pickup run. Nine observed deaths all occur in R2.

Inspection found dodge scoring omitted the first upcoming update (it scored
2,4,8,12). Added optional --immediate-safety: score update1 too and prefer
candidates without a predicted immediate contact before comparing total
future risk. Default steering is unchanged. Natural 1P Home/rapid/pickup
run survives38844 updates versus37253, but still ends in round2 after nine
deaths. Both real continues accepted, normal gameover returns Home. No
protection, seeded health/weapons, forced defeat, or gameplay-code changes.
The next coverage obstacle remains R2 contacts; prediction does not yet
model AI turns, new births or future camera changes. These bounded runs do
not prove full campaign or full speed. ROM unchanged at
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-pilot-death-trace/verified.json`, 1p/, immediate-1p/,
and current-tools/.

### Pilot boss-charge strategy — rejected

Verified R2 boss representation: core and four parts use ref36c4; core
flags29 during movement and28 during its opening cycle. The existing
composite-flag target detection correctly finds it after spawning. Null
targets in earlier progress logs are before the encounter, not a confirmed
port bug. Tested long charges only while a boss is visible, retaining rapid
fire elsewhere plus pickup/immediate-safety steering. Natural1P ends39073
updates in R2 (prior38844);4P ends14544 in R2. Both accept two real continues
and return Home; no forced defeat, protection or weapon/health seeding.
Repeated late1P deaths occur at x21 near the arena's left edge with nearby
projectiles, so firing mode alone does not solve the pilot movement limit.
No additional round coverage gained; removed this option and restored the
prior pilot. ROM unchanged at
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-pilot-boss-charge/rejected.json`, pilot-candidate.py,
1p/,4p/. Full natural campaign and full-speed requirements remain open.

### Genesis-core snapshot determinism gate for controller search

Added host-only PilotSnapshot and qa_bc_pilot_snapshot.py. The helper saves
core state plus Runner frame count, input mask and last display, and restores
them without modifying ROM gameplay rules. The pinned Genesis core test
starts a4P R8 diagnostic without protection, explores all nine movement
directions for120video frames each, restores, repeats each branch and then
replays the same baseline input sequence. Every branch repeat and baseline
replay matches exact work RAM, VRAM, rendered pixels, frame count and
simulation tick. Restoring also matches the original fingerprint each time.

This enables actual-core controller lookahead instead of assuming constant
projectile velocity. It is only a harness gate: the campaign pilot does not
yet use it, save/restore exploration is not an uninterrupted natural run,
and any selected campaign route must receive an independent no-restore
replay before natural coverage is claimed. SRAM persistence and audio
sample identity are not covered by this gate. ROM unchanged at
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-pilot-snapshot/verified.json` and saved tool sources.
Full-campaign and sustained full-speed requirements remain open.

### Experimental controller lookahead and strict replay gate

Connected optional --lookahead to the1P Home pilot, evaluating nine movement
inputs against four updates of the actual core when hazards/bosses are near.
Speculative states are restored; selected movement alone enters the route.
Added per-video-frame recording (--record-inputs also works without search)
and qa_bc_controller_replay.py, which replays from boot with controller
inputs only and requires the exact final gameplay RAM hash.

The1,000-update record-only run passes strict independent replay. Lookahead
smoke does NOT: RAM differs at one byte, logical offset0xfd28 (recorded3,
replay2), while every other RAM byte matches. This address is near the stack,
but inactive-stack residue has NOT been proven, so no normalization or
weaker passing gate was introduced. The longer lookahead process was
explicitly terminated after this failed gate, not restarted or counted as
campaign evidence. Need compare native SP/PC, active stack, pixels and
transient state before accepting search-route verification.

Evidence: `.local/bc-pilot-lookahead/diagnostic.json`, record-only/,
smoke-ram/ (both raw RAM snapshots), replay logs and tools/. Options remain
experimental and off by default. No cartridge gameplay changes; ROM remains
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Full-campaign and sustained60fps requirements remain unfinished.

### Isolated controller predictor resolves replay mismatch

Endpoint diagnostics identify the earlier difference: original search ended
at PC0x67a36 and plain replay at0x67a30, both inside VDP_waitVBlank, with
SP0xfffd3c. D1/SR also differed; pixels and VRAM matched. This establishes
a VBlank CPU-phase difference, so merely ignoring the stack byte would
not be an exact machine-state replay. No ignored ranges were introduced.

PilotSnapshot now accepts a destination runner. Controller speculation uses
a separately loaded copy of the pinned core with distinct RAM. The live
run is serialized read-only and NEVER restored; only the shadow is restored.
Strict replay now passes the1,000-update smoke and a31,293-video-frame full
gameover route: exact full RAM, all18checked CPU registers including PC/SP,
VRAM and rendered pixels. The greedy four-update movement policy ends in
R1 at tick28478, a regression, despite two accepted normal continues.

Revised the optional policy to retain the heuristic move whenever it survives
the prediction horizon, searching alternatives only for a predicted death.
Its10,000-update natural Home route enters R2 at tick6973, but consumes one
continue at8432. Independent12,804-frame no-restore replay passes every
strict endpoint check. Conservative policy remains experimental/off by
default; neither its survival nor extra campaign coverage is established.
No cartridge gameplay changes or CPU-speed adjustments. Evidence:
`.local/bc-pilot-lookahead/isolated-verified.json`, isolated/,
isolated-campaign/, conservative-10k/, isolated-tools/. Full campaign and
sustained60fps remain unverified. ROM remains
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.

### Final-address-only enemy animation write — rejected

Kept the local animation address after a source jump and wrote only its
final advanced address, replacing the intermediate jump store and later
read/modify/write. Native heavy4P R8 fixture (12000warmup/1000measured)
preserves all1000simulation states and passes independent replay, but
regresses1465→1468video frames and889400.435→889810.075mean scene ticks.
Rejected; restored bc_rules.c and matching ROM/ELF/symbol snapshot SHA
77d1983a55a3f27c54bca184228ea25f2cf812c8a4ed65e59624a9ee1f6a4e94.
Evidence: `.local/bc-animation-final-address/rejected.json`, after/,
candidate/. No claim of exhaustive animation validation for this rejected
variant. Full natural campaign and sustained60fps remain unverified.

### Retained tiny-queue late-VBlank window

finish_frame now admits NTSC V-counter235..240 only for <=256queued bytes
and <=1transfer, with the existing new-VBlank-epoch guard. Earlier caps
(2048/8 through228,1024/4 through234) and PAL fallback are unchanged.
These counter values correspond to physical241..246 before call overhead.
An initial512-byte/two-transfer candidate saved55frames in the heavy4P
fixture; tightened to256/1 for more DMA headroom before retention.

Retained ROM64eddbcb52f4f9c545dacf3fb5f3e5f0dcc6ef0c153887e404304093936f1275:
- HeavyR8 4P1465→1437 and3P1299→1288 frames/1000updates.
- Charged4P R10 remains1203frames/1000updates. All3000simulation states
  match their baselines; each instrumented run passes independent full-RAM replay.
- Three native scheduler samples:263/174/52 early submissions, including
  63/19/6 in the new physical241+ window. Every early submission completes
  in the same VBlank epoch, latest scanline258. Completion epochs strictly
  increase between updates. These are measured fixtures, not exhaustive
  DMA/callback combinations or physical-hardware certification.
- All40BC openings save66frames net,11improve29tie,none slower vs segment-table
  matrix. All40Normal samples preserve40040gameplay and40040ordered sprite
  hashes with identical timing and zero measurement errors.
- 4P BossRush remains2990updates/3000video frames, full wheel cache, zero
  drops/remaps/fallbacks, reset releases allocations. No new late flushes
  observed in its scheduler trace. Sprite-pixel comparison covers Normal;
  no baseline whole-video comparison is claimed for Rush.
- Real4P BC modal, pause/every-controller resume, return/reentry/reset pass.

Evidence: `.local/vblank-tiny-queue/verified.json`, candidate/ complete source
and include snapshots plus matching ROM/ELF/symbols, native profiles, matrices
and menu/rush logs. Full natural campaign and sustained all-mode60fps remain
unfinished. No actors, ticks, waves, graphics or game rules reduced.

### Retained288-byte single-transfer late window

Raised only the newest V-counter235..240 byte cap256→288; one-transfer cap,
new-epoch guard, earlier caps and PAL fallback remain unchanged. Actual
prior traces include264–288byte single transfers finishing in blank.
Retained ROM: f05ae788ece11ccc17f29603486a94f557553a968c36ac78e5a36975b4d758f3.

HeavyR8 4P1437→1410frames/1000updates,3P1288→1271; charged4P R10
1203→1196. All3000states match and native replay passes. LongR8 4P
13,000-update comparison against immediately preceding64eddbcb build:
18493→18232video frames, all13000states identical and
independent full-RAM replay passes. Long route includes2621early scheduler
submissions: all finish in the same VBlank, latest physical scanline258;
completion epochs strictly increase. This is bounded emulator evidence,
not physical-hardware or exhaustive callback/DMA certification.

Important trace interpretation: entries observed at physical241+ can include
a call selected slightly earlier under the1024-byte cap. `late_entry_calls`
is therefore not a count of decisions made by the new288-byte branch. The
prior tiny-window manifest's similarly named counts should be read as late
entry observations, not exact branch selection. No deadline filtering hides
these larger earlier-window transfers; every early call is checked.

FortyBC openings save27frames net:7improve,32tie,R10 2P costs1frame. All40
Normal cases retain identical timing and40040gameplay/40040ordered-sprite
hashes.4P Rush retains2990updates/3000frames and every video hash, with no
drops/remaps/fallback and successful reset cleanup. Real4P BC modal/pause/
return/reentry/reset passes. Evidence: `.local/vblank-288/verified.json`,
complete candidate source/include/ROM/ELF/symbol snapshot, profiles/matrices
and menu/rush logs. Full natural campaign and sustained all-mode60fps remain
unverified; no actors, waves, updates or graphics were removed.

### Outlined common enemy motion — rejected

Forced bc_enemy_motion to remain a separate native function, preserving its
C rules. This tests whether smaller actor callers offset call overhead.
Heavy4P R8(12000warmup/1000measured) regresses1410→1567video frames,
889517.405→934009.706mean scene ticks. All1000simulation states match
and independent replay passes. Restored inlining and matching source/ROM/
ELF/symbol snapshot f05ae788ece11ccc17f29603486a94f557553a968c36ac78e5a36975b4d758f3.
Evidence: `.local/bc-motion-leaf/rejected.json`, after/, candidate/. This
rejects outlining the whole motion task as a performance improvement; no
whole-game fidelity claim comes from the bounded fixture. Full natural
campaign and sustained60fps remain unfinished.

### Native enemy timer decrement — retained

The common BC enemy animation timer now decrements its byte directly in memory
and branches on zero with native 68000 SUBQ.B/BEQ. The portable C path remains
unchanged. Native probe coverage exhausts all 256 input values at both even and
odd addresses (512 cases), checking wrap, the zero branch and adjacent sentinels.
The m68k compiler does not support asm-goto outputs; the memory clobber covers
the write to the addressed input operand. Original-reference checks pass for
1748 motion updates, 321 death-animation updates and 9 retirements.

Against f05ae788, heavy R8 4P saves 1410→1407 video frames per1000 updates;
3P saves1271→1265. Mean scene ticks fall889517.405→887656.665 and
825875.918→823910.871 respectively. The longer protected R8 4P fixture saves
18232→18160 frames for13000 updates. All15000 compared simulation states
match and independent full-RAM replays pass. Sampled early scheduler calls
complete in the same VBlank, latest physical line258 (280/192/2654 calls).
This is sampled emulator evidence, not exhaustive or hardware deadline proof.

Forty BC openings save18 frames net:8 improve,28 tie,4 regress (R1 4P+1,
R5 4P+1,R10 3P+1,R10 4P+3). All40 Normal cases retain identical timing,
40040 gameplay hashes and40040 ordered-sprite pixel hashes. Boss Rush4P
retains2990 updates/3000 frames and every video hash, with zero sprite drops,
runtime remaps or wheel fallbacks; soft reset cleanup passes. Actual4P BC
modal/pause/return/reentry/reset passes. No actors, waves or updates removed.

Retained ROM:1183302482de8acc18338dfc35c6972a2f9a4834d4a89ac94c1d1f8c36c943db.
Evidence:`.local/bc-timer-memory/verified.json`, matching full candidate source,
headers, ROM, ELF and symbols; `tools/qa_bc_timer_native.py` native probe.
Full natural campaign and sustained60fps across all modes remain unfinished.

### Omit discarded peer score RNG work — retained

Multiplayer BC previously advanced a temporary seed for each peer's score task,
then discarded the result. The score API now permits a null seed to omit that
work; the leader still advances the authoritative shared seed once per update.
Queue consumption, decimal score arithmetic, high-score refresh, extend policy,
lives and sounds remain identical. The 32768-case baseline comparison exercises
both leader and peer paths with score/high/queue changes, all command bytes,
threshold counts, extend cursors and life wrap; score state/events/lives match,
and the leader seed retains the original advance.

Against11833024, heavy R8 4P saves1407→1406 video frames per1000updates and
mean scene ticks887656.665→886053.259. Heavy3P saves1265→1261 and
823910.871→822867.045 ticks. Long protected4P R8 saves18160→18101 frames
for13000 updates, mean871567.9957692308→870018.9334615385 ticks. All15000
compared simulation states match and independent full-RAM replay passes.
The sampled early scheduler calls (280/190/2670) finish within the same VBlank,
latest physical line258; this remains bounded emulator evidence.

Forty BC openings save16frames net:11 improve,27 tie,2 regress by one frame
(R3 4P and R7 4P). All40 Normal timings and40040 gameplay/40040 ordered-sprite
hashes match. Boss Rush4P retains2990updates/3000frames and all video hashes,
with no sprite drops/remaps/wheel fallback and successful reset cleanup.
Actual4P BC modal/pause/return/reentry/reset passes. No enemies, waves, graphics
or updates removed. The source timer optimization from the previous step stays.

Retained ROM:02e89b0f329eaf6a4b255ac6985a7bb4b54eaac5ba28129c7c9e3a5a599e522a.
Evidence:`.local/bc-peer-score-rng/verified.json`, complete candidate source/
headers/ROM/ELF/symbol snapshot and `tools/qa_bc_peer_score.py`.
Sustained all-mode60fps and full natural campaign verification remain unfinished.

### Natural pilot reaches round three; profile from strict input replay

ROM and all game source/include files remain exactly02e89b0f. Extended the
isolated conservative-lookahead pilot to100000updates on the current build.
Rapid fire stalls at R2 (103765 total video frames,3 deaths,1 real continue);
a charged-shot variant also stalls at R2 (105204frames,2 deaths,no continue).
Both full input records replay without snapshots/restores to identical64KiB
RAM, CPU registers, VRAM and displayed pixels. Removed the unsuccessful
boss-charge option again; its exact candidate script and inputs are archived.

Endpoint inspection finds the rapid-fire pilot using returning weapon2/power2
at x54 while the core is x208. That weapon travels straight for16updates before
homing back. This suggested testing a closer controller aiming target, rather
than modifying enemy rules. Retained optional `--boss-standoff 96`: the pilot
clears R2 and reaches R3 at tick15909; its40000-update bounded run ends alive
at the R3 boss, after3 deaths and1 real continue. The complete47209-video-frame
input replay matches full RAM/CPU/VRAM/pixels exactly. No health, weapons,
credits, player deaths or boss defeats were seeded/forced.

Added optional read-only profiling to `qa_bc_controller_replay.py`, initialized
only after boot/target tick because the core's video budget is not set before
its first frames. R3 ticks32000..33000 measure1000 scene calls over1335video
frames; mean scene871343.074coreticks, peak1507079,369 calls over896040budget.
Largest attribution:general actor loop128436532ticks, contacts111646514,
common actor88823546, projectile drawing87979108, weapon stepping84093058,
boss-three preparation75373340. Scene attribution excludes outer input and
VBlank/DMA. The complete profiled replay matches the recorded endpoint; the
profile's own separate stop-point replay flag remains false (not separately
verified at that intermediate stop).

Evidence:`.local/bc-pilot-lookahead/current-evidence/verified.json`, three
*-current/ input/RAM/CPU/video records, range-current/replay-profile/, and
archived pilot/replay tools. This advances natural coverage only through the
start of R3 and identifies a natural1P performance failure; it does not prove
full campaign completion or sustained60fps. All-mode1/2/3/4P/full-speed goal
remains active.

### Scene-paced natural replay and solo body rejection — retained

Added `qa_bc_scene_replay.py` to capture controller bytes at native scene entry
and compare canonical gameplay after every completed scene. The source1P Home
route has40013 gameplay calls. Capture leaves its original47209-frame fullRAM,
CPU, VRAM and pixel checkpoint identical. Replaying those inputs at scene entry
matches every canonical state and takes47215frames. This paced baseline is used
for speed comparisons; it is not compared directly to video-scheduled inputs.
The first harness attempt also paced menu calls and failed before initialization;
preserving original boot/modal input until simulation tick1 fixes that error.

The comparator covers actors, stage, player state excluding transient pointers,
score, RNG seed, credits and continue ranks. This is a defined gameplay subset,
not a full64KiB comparison across ROMs. No actor, health, weapon, score or RNG
writes and no emulator-state restores are used. Capture requires the original
ROM; replay permits changed ROMs and fails on the first differing scene. Output
records are cleared before running so failed retries cannot retain stale passes.
Evidence/tool snapshot:`.local/bc-scene-input/verified.json`.

Solo common contacts now use the existing exact body-distance predicate when
shots cannot hit, before constructing contact records. Cooldown, damage-lock,
motion, retirement and contact ordering remain intact. The old broader experiment
also changed party handling and was slower; this trial changes only solo gating
and is measured against the new natural vulnerability-heavy fixture.

Retained ROM214b5e8b69510988de38571742b8b7b3372909849d093a54b0691d992e2fcd46.
All40013 natural-route scene hashes match02e89b0f; total paced video frames
47215→45734. R3 ticks32000..33000 need1333→1240video frames for1000scene
calls (frame-index spans), about7% fewer. Heavy4P R8 stays1406frames/1000updates,
all1000 state hashes and independent fullRAM replay pass; mean scene ticks
886053.259→886056.171 (effectively unchanged, not a CPU gain claim for4P).

32000 host contact comparisons pass, including indexed/unindexed shots,
wrapped bounds, damage, pickups, options, fractional boss health and ordered
events. Forty BC openings have no regressions and save2frames total (R4 3P,
R8 2P each1). Forty Normal cases preserve all40040 gameplay/40040 sprite hashes
and timings.4P Rush retains2990updates/3000frames, identical video hashes,
zero drops/remaps/wheel fallback and successful reset cleanup.1P BC actual
modal/pause/return/reentry/reset passes. Evidence:
`.local/bc-solo-body-gate/verified.json`, before/candidate matching source,
headers, ROM, ELF and symbols; natural/,4p/,matrix/,normal/,rush/ and logs.
No enemies, updates or graphics removed. Full natural campaign and sustained
all-mode60fps remain incomplete.

### Boss-three homing velocity tables in native ROM format — retained

The BC data generator now decodes all five even speeds0..8 and sixteen headings
for the R3/R9 boss-three homing shot into native signed32 velocity containers.
Two1292-byte-total ROM records retain their exact source pointer/origin.
Existing scene binding validates that identity once; eight bytes of static
pointers select the table. The hot task still updates phase, speed, aim,
heading, animation and timer in source order. It replaces only the final three
little-endian reads/scaling with native vector loads. Odd/out-of-range speed,
out-of-range direction, unbound or other data objects retain original reads.

`qa_bc_boss3_vectors_native.py` checks all320 native ROM components directly
against source bytes, then compares actual production preparation to the prior
source-read function on the pinned68000 core. All32076 cases pass: both rounds,
bound/unbound/other-object fallback, speeds0..10, directions0..17, phase/wait
0..2 and three player aim heights. The probe alters only a scratch cartridge.

Against214b5e8b, the natural1P scene-paced route saves45734→45457 video frames,
with all40013 canonical gameplay states matching. R3 ticks32000..33000 save
1240→1209frame-index span per1000scene calls. Heavy4P R8 saves1406→1404frames,
all1000 states and independent fullRAM replay match; mean886056.171→886050.823
scene ticks is effectively unchanged. BC40 openings net unchanged: R8 2P+1,
R10 2P−1,38ties. All40 Normal timings and40040gameplay/40040sprite hashes match.
4P Rush retains2990updates/3000frames and every video hash, no drops/remaps/
wheel fallback, reset cleanup passes, and wheel allocation leaves1300B free.
Actual4P BC modal/pause/return/reentry/reset passes. No actors, waves, updates
or art are removed.

Retained ROM:bddb5e2a686a5d8468c39d4b431155de5a80052eaa2cd330dd1596018812c7d9.
Evidence:`.local/bc-boss3-native-vectors/verified.json`, native.log and
`.local/bc-boss3-vector-probe/`, natural/4p/matrix/normal/rush/menu records,
complete matching candidate source/includes/generated data/ROM/ELF/symbols,
and generator/native-probe tool snapshots. Full natural campaign and sustained
all-mode60fps remain incomplete.

### Isolated round-three homing dispatch (2026-10-05)

Retained native ROM cb6a64bf187dd14f28db4eef86c808415c1ae364cada1c30ae33a9a3e0f73262.
`boss_three_homing_prepare` shares the exact existing steering logic between
full dispatch and a compact round-three actor loop. The compact loop reuses
its empty child-event envelope, preserves scrolling/contact/event order and
uses the existing uncommon-family fallback. Other rounds retain their original
per-actor loop. No actors, updates, waves or graphics are removed.

The preceding direct/integrated/leaf experiments sped up R3 but cost 15–16
frames in the R6 4P opening. A separate R3 loop removes that regression. Its
first variant incurred four frames in the R3 opening; restoring ordinary
bullet fast paths reduces that to one. All variants and matching sources /
ROM / ELF / symbols are archived under `.local/bc-boss3-direct/`.

Against retained bddb5e2a, the final scene-paced natural route improves
45457 to 43994 video frames with all 40013 canonical gameplay states matching.
The R3 tick32000..33000 sample improves 1209 to 1070 frame-index span for 1000
scene calls (about 56.1 updates per 60 video frames); mean scene cost is
758742.152 core ticks, with 91 calls over the 896040-tick budget. This is not
sustained full speed, nor full-campaign proof. The optional new profiling in
`qa_bc_scene_replay.py` first reproduced baseline scene states AND exact frame
spans before measuring candidates. It excludes outer input and VBlank/DMA.

Validation: 800 three-pass mixed R3/R9 pools, 41558 ordered events; 320 native
ROM components and 32076 native steering comparisons; original `round3-route`
6006 complete loops / 148005 actor updates / 76 children / 88 retirements,
zero unsupported loops. Heavy R8 4P stays 1404 frames per1000 updates, with
all1000 states and independent fullRAM replay matching. BC40 openings have
zero net frame change: R3 4P611→612, R7 4P666→664, R9 4P616→617, all others
unchanged. Normal40 preserves all40040 gameplay and40040 sprite hashes;
2P sections2/9 each cost one frame (1001→1002 and1000→1001), others unchanged.
These small timing regressions are recorded, not represented as ties.

4P Rush remains2990 updates/3000 frames with every video hash matching, no
sprite drops/remaps/wheel fallback, reset cleanup passes,1296B free wheel heap.
Actual4P BC modal/cancel/launch/controller pause/resume/return/reentry/reset
passes. The instrumented R3 4P3000-update stack route has zero overlap samples
and minimum11160B gap; that route alone does not prove whole-game stack safety.
Evidence: `.local/bc-boss3-direct/verified.json`, `isolated-bullets/`, matching
`candidate/` sources/includes/generated assets/ROM/ELF/symbols and QA tools.
Full natural campaign and sustained all-mode60fps remain incomplete.

### Conservative per-shot X rejection (2026-10-05)

Retained ROM `96e3dc2993b2736f9a0e882631bca9157bec2dc2360998a0ddc1793b7faabf3d`. The indexed collision scan now rejects a shot's X
coordinate using the maximum indexed half-width before calculating its weapon
address. The widened sum conservatively bounds the original byte-wrapped
radius. Possible contacts retain exact live-state, individual hitbox, shot
consumption, damage and slot-order tests. No index layout or RAM allocation
changes. This removes work for distant shots; it does not remove shots.

Against cb6a64bf, the recorded natural scene-paced route saves43994→43869
video frames, all40013 canonical gameplay states matching. R3's1000-call
window saves1070→1065 frame-index span; mean758742.152→755728.582 scene ticks,
91→74 calls over896040 budget. Heavy4P R8 takes1404→1403 frames but mean cost
rises886073.937→886130.056, effectively unchanged; all1000 gameplay states and
independent fullRAM replay pass. BC40 openings cost five net frames:
R3 4P+2, R4 4P+1, R6 4P+1, R8 3P−1, R10 2P+1, R10 3P+1. The small cross-round
regressions are retained as a measured tradeoff for the longer natural-route
improvement, not described as universal acceleration.

32000 indexed/uncached sequential scans and32000 1P–4P contact comparisons
pass. Normal40 timings and40040 gameplay/40040 sprite hashes are unchanged.
4P Rush stays2990updates/3000frames, every video hash matches, no software
sprite drops/remaps/wheel fallback and reset cleanup passes. Actual4P BC
modal/cancel/launch/pause/return/reentry/reset passes. The peak32670 scene is
still1378853ticks, with378658 attributed to actor_contacts. That remaining
spike and full natural campaign coverage remain open work.

Evidence: `.local/bc-shot-x-prefilter/verified.json`, natural/4p/matrix/normal/
rush/peak outputs, host/menu logs, matching candidate sources/includes/assets/
ROM/ELF/symbols. Full campaign and sustained all-mode60fps remain unverified.

### Vertical shot rejection and natural round-four coverage (2026-10-05)

Retained ROM a994d13214f2128dbea93d5d3c9c311469bdd41a1ec558bda90165a1f47f0bf6.
The indexed scan now applies the conservative Y bound after the existing X
bound, before calculating a shot's weapon address. Possible contacts retain
exact live-state, individual byte-wrapped hitbox, consumption/damage and slot
order. No RAM/index layout changes, no removed shots or updates.

Against96e3dc29: scene-paced route43869→43813video frames, all40013canonical
states match. R3 sample1065→1057frames/1000calls, mean755728.582→754468.806
core ticks, over-budget74→71. HeavyR8 4P regresses1403→1405frames, mean
886130.056→886180.932; all1000states and independent fullRAM replay match.
BC40 openings net two fewer frames: R3 4P−2, R6 3P+1/4P−1, R7 4P+2,
R9 4P−1, R10 2P−1/3P−1/4P+1. These are mixed measured improvements, not a
claim of universal acceleration. Host32000shot scans and32000contact cases
pass. Normal40 timings and40040gameplay/40040sprite hashes remain identical.
4P Rush2990/3000 and every video hash match; no drops/remaps/wheel fallback,
reset cleanup passes. Actual4P BC modal/pause/return/reset check passes.

A fresh normal-damage 1P Home pilot with real controls, conservative isolated
lookahead, pickups, rapid fire and96px boss standoff ran100000updates. It
cleared rounds1–3, enteringR2tick6888, R3tick28017 andR4tick35142. It used zero
continues and finished alive at the round-four boss at the update limit.
This extends natural progression beyond the previous R3-only recording.
The boss remains at10HP/8bars in the late logs; the run does not establish why
its controller strategy stopped making damage progress. Do not infer a port
bug from that result alone.

Independent controller-input replay runs103334absolute video frames without
snapshot restoration and matches full64KiBRAM plus CPU/VRAM/pixel checkpoint.
No health/weapons/actors/RNG or forced boss defeat edits. Pilot wall-clock
lookahead uses a separate core, never restores authoritative live state.
Evidence: `.local/bc-shot-xy-prefilter/verified.json`, campaign/ result/input/
RAM/checkpoint/replay, full candidate source/includes/generated assets/ROM/
ELF/symbols and pilot tools. Sustained all-mode60fps and full campaign clear
remain incomplete. R4 boss aiming and remaining heavy4P costs are next work.

### Round-four pilot aiming diagnosis (2026-10-05)

ROM remains a994d13214f2128dbea93d5d3c9c311469bdd41a1ec558bda90165a1f47f0bf6;
no production changes. Read-only inspection of the preceding natural endpoint
finds player(134,74), core(232,142), returning weapon2/power5, no solid terrain
in the visible boss arena, and unobstructed cardinal/diagonal movement from
that position. Terrain does not explain the stalled aiming there.

Two controller-only trials each run70000updates, clear rounds1–3 at the same
ticks as the prior run, use zero continues, and finish alive inR4. Trialone
uses64px standoff only at the R4boss; trialtwo keeps96px and targets the nearest
vertically aligned composite part whose shot-immunity bit is clear. Neither
reduces core10HP/8bars. Both independently replay exactly (fullRAM and machine
checkpoint), with no save-state restoration into the authoritative core.

The second strategy used an insufficient vulnerability predicate: side parts
have flags0x28 but cooldown255, so cannot take damage. Core cooldown/damage
lock are zero at the endpoints but its flag alternates0x29/0x28 through the
source attack/open cycle. Thus aim selection must consider cooldown and the
core's vulnerability window, not flags alone. These trials do not establish a
port bug. Next controller trial should evaluate charged fire timed/aligned to
the core opening. Failed options were removed, restoring the pilot byte-for-
byte to its prior source. Candidate scripts and complete runs are retained in
`.local/bc-r4-pilot/`; summary `rejected.json`. Full campaign and sustained
all-mode60fps remain unfinished.

### R4 charged-fire trial and measured aiming failure (2026-10-05)

Production remains a994d13214f2128dbea93d5d3c9c311469bdd41a1ec558bda90165a1f47f0bf6.
A controller-only80-held/20-released firing rule, enabled only at the R4boss,
runs80000updates alive atR4 with zero continues, but does not damage the core.
The earlier route still reachesR2tick6888/R3tick28017/R4tick35142. The failed
pilot option is archived and removed; original pilot is restored byte-for-byte.

New `qa_bc_boss_window.py` replays recorded input from boot without restoring
snapshots or altering game outcomes, and checks fullRAM plus CPU/VRAM/pixel
endpoint equality. Its video-boundary snapshots (once per observed newtick)
are explicitly not a trace of collision execution. Among34711boss snapshots,
8294have core shot immunity clear, cooldown0 and damage_lock0. None has player
vertical alignment within8pixels; minimum gap55pixels. No eligible shot
rectangle overlaps the open core in those snapshots. CoreHP/bars stay10/8.
Thus periodic charging alone cannot fix the pilot's demonstrated aiming
failure. Next trial: direct core tracking with real-core4-step safety retained,
bypassing the overly conservative12-step heuristic only at this boss. This
finding is not proof that the whole boss implementation is correct.

Fresh current-ROM protectedR3 4P profile (warm300, measured1000) takes1190
video frames, mean754919.543scene ticks,191over896040budget, maximum1442329.
Independent fullRAM replay passes. Largest attribution: actor drawing105592508,
scene103855220, player step98747180, common actor98078176ticks. Enemy rendering
is a concrete next optimization target; these timings remain below60fps.
Evidence: `.local/bc-r4-charge/rejected.json`, campaign/input/checkpoint,
window/result.json, round3-4p/result.json and archived diagnostic scripts.
Full campaign and sustained all-mode60fps remain unfinished.

### Natural campaign reaches round eight; direct core tracking (2026-10-05)

Production ROM remains a994d13214f2128dbea93d5d3c9c311469bdd41a1ec558bda90165a1f47f0bf6.
Retained optional pilot `--boss-four-direct-aim` requires actual-core lookahead.
Only while a round-four boss is visible, it bypasses the conservative12-step
linear hazard heuristic and feeds direct target movement into the existing
real-core4-step safety selection. All inputs remain ordinary pad controls;
no health/actor/weapon/RNG changes or snapshot restores into the live core.
The core now takes damage and dies, confirming the prior stall was caused by
that pilot strategy, not evidence of an unkillable native R4boss.

The80000-update run clears rounds1–6 and ends alive inR7, using one real
continue inR5. Independent input replay matches fullRAM and CPU/VRAM/pixel
endpoint at87153absolute video frames. A160000-update bounded extension
preserves that entire input prefix, clearsR7, entersR8 at tick93347 and reaches
theR8boss. It uses the final available continue inR8 at tick101212, then exhausts
lives at tick111546/status7 and returns toHome. Independent replay of its
122454-frame gameplay recording exactly matches fullRAM/machine checkpoint.
The Home return is observed by the pilot after that gameplay endpoint.
Round transitions: R2tick6888, R3 28017, R4 35142, R5 47070, R6 60425,
R7 79245, R8 93347. Natural full-campaign clear is still not established.

Captured80031complete scene states from the80k run with original endpoint
matching. Scene-paced replay matches every canonical state at87159frames
(six more than original video-paced input). R6ticks76000..77000 are a new
reproducible slow workload: capture1961frame span, mean1043280.210scene ticks;
paced1963, mean1043277.676. Capture969/1000calls exceed896040budget. Main
attribution: common actor203715848, actor drawing159169836, general actor
loop123944562, weapon update102186574, projectile drawing99111656ticks.
This is ~30.6updates/s in the original sample, not sustained60fps. Preserve
this longer canonical route when evaluating future optimizations.

Evidence: `.local/bc-r4-direct-aim/verified.json`, campaign/extended inputs,
RAM/checkpoints/replays; scene-capture/scene-replay; verified-tools snapshots.
Read-only actor-render assembly inspection is also saved as actor-draw.s.
Next work: optimize the verified R6boss load and extend natural coverage
pastR8. Full campaign and sustained all-mode60fps remain incomplete.

### Native unsigned-distance helper (2026-10-05)

Retained ROM16f46cd9b632c0f934e48435ea4c8817d9e6802ef48bac31eba552d506aaa8e2.
`bc_unsigned_distance` in bc_rules.h uses68000SUB.W/carry/NEG.W to calculate
exact unsigned16-bit absolute distance. It avoids a separate compare while
preserving far distances across0x8000/0xffff. The portable C fallback is
unchanged. Used by body_near, player-body contacts, indexed/unindexed shot
bounds and returning-weapon distance; no hitbox, collision-order, actor,
update, wave, art or RAM layout changes.

`qa_bc_distance_native.py` compiles the actual header helper into a scratch
cartridge and checks655360cases: all65536X values against10Y boundaries.
32000shot scans and32000contact comparisons pass. Returning-weapon source
fixture matches2089active updates,61launches/catches and35blocked launches.
The first body-only trial saved87159→87144routeframes and1963→1960R6sample
frames; broader reuse is retained because it improves both recorded routes.

Against a994d132, the80k natural scene-paced route saves87159→87040frames,
all80031canonical states matching. R6ticks76000..77000 save1963→1950frames;
mean1043277.676→1028186.201ticks, over-budget969→958/1000. Earlier R3route
saves43813→43522frames, all40013states match; sample1057→1037frames,
mean754468.806→741173.230ticks, over-budget71→46. Neither is sustained60fps.

HeavyR8 4P costs1405→1406frames despite mean886180.932→886066.804ticks;
all1000states and independent fullRAM replay match. BC40 openings net one
fewer frame with explicit mixed one/two-frame changes in verified.json.
Normal40 timings and40040gameplay/40040sprite hashes remain identical.
4P Rush2990/3000 and every video hash match; no drops/remaps/wheel fallback,
reset cleanup passes,1296Bfree wheel heap. Actual4P BC modal/pause/return/
reentry/reset passes. Build/finalization/diff checks pass.
Evidence: `.local/bc-body-distance/verified.json`, reproducible verifier,
body-only-candidate/shared outputs, native probe `.local/bc-body-distance-native`,
and complete matching candidate sources/includes/generated data/ROM/ELF/
symbols/native QA script. Full natural campaign and sustained all-mode60fps
remain unfinished; the reproducible R6boss is still a major performance gap.

### Inline solo body-distance predicate (2026-10-05)

Retained ROM 8266df976ff16c76983a63025fe843b535f3a2d78c6e1f528e50c35cf7754208. Instruction attribution on the naturalR6boss
showed common-task register saves/restores, event clearing and repeated body
predicate calls costing more than animation decoding. `body_near_inline`
shares the same exact unsigned predicate with the existing noinline party
wrapper; only the solo common-task branch inlines it. This eliminates repeated
call/argument/result handling in1P without expanding each multiplayer body
scan. No animation cache or additional RAM, and no actor/update/art changes.

32000 streamed-contact comparisons pass. All80031canonical states of the
long natural route match; frames87040→86633. R6sample1950→1899frames per1000
calls; mean1028186.201→997253.495ticks; over-budget958→908. Earlier R3route
preserves40013states and saves43522→43401frames, sample1037→1036, mean
741173.230→732032.581ticks, over-budget46→38. Neither proves sustained60fps.

HeavyR8 4P stays1406frames (mean886066.804→886103.960 effectively unchanged),
all1000states and independent fullRAM replay pass. All40BC opening timings
are unchanged. All40Normal timings and40040gameplay/40040sprite hashes match.
4P Rush retains2990/3000, every video hash, zero drops/remaps/wheel fallback
and reset cleanup. Actual4P BC modal/pause/return/reentry/reset passes.
Build/finalization/diff checks pass. Evidence: `.local/bc-solo-near-inline/`
verified.json, reproducible verifier, candidate source/includes/generated
assets/ROM/ELF/symbols and all route/matrix/profile logs. Assembly attribution
is `.local/bc-r6-common-inspect/common.s`. Full natural campaign clear and
sustained all-mode60fps remain incomplete.

### Separate composite fallback from ordinary actor cache (2026-10-05)

Retained ROM ca88e4b7f2aa74dc66b34df8656021f481abe263b9f51f6ebb36336d2da0454e. Composite actors already use bc_boss_draw;
unsupported composites now preserve the ordinary mapper's exact hidden-frame
and missing-art counts directly. Ordinary actors no longer compare/store a
redundant composite tag on each draw. The cache remains20native bytes per
slot (the removed byte becomes alignment padding); no RAM increase, removed
art, changed sprite priority, altered clipping or skipped gameplay updates.
The all-zero cache key is a valid hidden sprite0. Added a directed first-use
test for live zero-frame ordinary/composite actors before cache population.

Host comparison passes1456cache updates /11358ordered sprite submissions,
slot reuse, flips, coordinates, empty/composite cases and simulation-byte
immutability. All80031states of the long natural route match, frames86633→
86571. R6sample1899→1888frames/1000calls, mean997253.495→990003.819ticks,
over-budget908→899. Earlier R3route preserves40013states,43401→43359frames;
sample1036→1032, mean732032.581→729864.093, over-budget38 unchanged.

HeavyR8 4P improves1406→1376frames, mean886103.960→880451.929ticks; all1000
states and independent fullRAM replay match. BC40 openings save48frames net:
14improve,25tie, R8 2P alone costs603→604. All40Normal timings and40040gameplay/
40040sprite hashes match. 4P Rush retains2990/3000, all video hashes, no
software drops/remaps/wheel fallback and reset cleanup. Actual4P BC modal/
pause/return/reentry/reset passes. Build/finalization/diff checks pass.

Evidence: `.local/bc-render-composite-gate/verified.json`, reproducible verifier,
cache/menu logs and route/matrix/profile outputs; full candidate source,
includes/generated assets/ROM/ELF/symbols and updated renderer comparison.
Sustained all-mode60fps and natural full-campaign clear remain incomplete.

### Cache hardware flip bits for BC actors (2026-10-05)

Retained ROM 2b84480dd129ceacbfbc27948f746aec16b76e88ef9d577e3f1e9fc622df9c77. Ordinary actor art caches now keep the
hardware0x0800/0x1000 flip bits in the former byte/padding pair, preserving the
20-byte cache size. New BC submission paths pass those bits directly to SAT
emission. Logical-flag callers retain their conversion;32px fallback converts
back before its four ordinary16px submissions. Clipping, cache residency,
sprite order, diagnostics and artwork remain unchanged. No extra RAM.

Host renderer comparison passes1456updates/11358ordered submissions, including
first-use zero frames. Native SAT probe passes20480emissions across every
flag byte/slot, wrapping coordinates and table guards. Long natural route
preserves80031canonical states,86571→86492frames; R6sample1888→1871,
mean990003.819→981490.034ticks, over-budget899→880. Earlier R3route preserves
40013states,43359→43315frames; sample1032→1031, mean729864.093→727148.863,
over-budget38→35. These remain bounded samples below sustained60fps.

HeavyR8 4P saves1376→1352frames, mean880451.929→873422.270ticks; all1000states
and independent fullRAM replay match. Paired3P saves1246→1233frames,
mean816684.561→809348.757; both independent replays and1000cross-build states
match. The initial archived3Pbaseline lacked its matching bc_rules.h and was
incorrectly decoded as the older actor layout, causing false hash mismatches.
That result is preserved as3p-before-invalid-layout and not used as evidence.
After verifying the archived ROM hash and supplying matching headers, rerun
hashes match. `profile_bc_budget.py` now rejects missing archived layout info
unless both coordinate/velocity shifts are explicit; a negative CLI check
confirms rejection before execution.

BC40 openings save38frames net: nine improve,29tie, R3 4P andR4 3P each cost
twoframes. Normal40 timings and40040gameplay/40040sprite hashes are unchanged.
4P Rush retains2990/3000, every video hash, no drops/remaps/wheel fallback,
and reset cleanup. Actual4P BC modal/pause/return/reentry/reset passes.
Build/finalization/diff checks pass. Evidence: `.local/bc-render-flip-bits/`
verified.json, matching candidate sources/includes/generated assets/ROM/ELF/
symbols/tools, native/cache/route/matrix logs and paired3P profiles. Full
natural campaign clear and sustained all-mode60fps remain incomplete.

### Small-actor bucket revisit rejected on current renderer (2026-10-05)

Tested using the existing art-cache bucket pointer for16px actors after the
composite-tag removal and hardware-flip caching. The repeated-key shortcut
and full-key residency check remained intact; no extra RAM. This revisits the
older rejected variant against the new natural R6boss route and new renderer
allocation, rather than assuming the old timing result still applies.

Host1456cache updates/11358submissions pass. All80031canonical natural states
and1000heavy4P states match; independent fullRAM replay passes. Timing rejects
the candidate: long route86492→86540frames, R6sample1871→1872,
mean981490.034→987925.750ticks. HeavyR8 4P improves only1352→1350frames;
BC40 openings cost27extra frames overall. This does not justify retention.

Archived candidate a6bb21a3d0c93a0d7bd3cbc95375839b25f959fd1072aed340fb6684638ee5c3,
all changed source/header/test files, ROM/ELF/symbols and matching layout
headers under `.local/bc-small-bucket-current/`. Restored all four edited
files and rebuilt/finalized; release is byte-identical to retained
2b84480dd129ceacbfbc27948f746aec16b76e88ef9d577e3f1e9fc622df9c77.
Summary: rejected.json. No production or QA change retained from this trial.
Full campaign and sustained all-mode60fps remain incomplete.

### Seven-life natural campaign and round-eight diagnosis (2026-10-05)

Retained production ROM 2b84480dd129ceacbfbc27948f746aec16b76e88ef9d577e3f1e9fc622df9c77 unchanged.
Added optional `--home-lives 1..7` to the controller pilot; it selects the
setting through the actual Home Options UI and verifies the saved value.
This run used seven total starting lives, normal damage, one player, both
real continues, and the previously verified R4 direct-aim policy. It cleared
rounds1–7, reached R8 at tick102661, then exhausted its lives at tick142060.
Both continues were spent in R8;15 of23 observed deaths occurred there.
The Home game-over return passed. This is explicitly a nondefault-lives
coverage run, not a default-settings or full-campaign clear.

Independent input replay reproduced151729 absolute gameplay video frames
with identical full64KiB RAM, CPU registers, VRAM, pixels and frame/tick
checkpoint. No state restores or forced outcomes were used in that replay.
The later Home return was observed separately after the captured endpoint.

Extended `qa_bc_boss_window.py` with an optional round selector (default4
preserves the previous R4/x232 filter). Read-only R8 slot-zero boss sampling
also reproduced the exact endpoint:15771 snapshots,8731 open with no cooldown
or damage lock,2148 aligned within8 vertical pixels,62 open shot-overlap
snapshots. Health reached6bars from12 across the observed attempts. These
are video-boundary observations, not collision-execution traces. Unlike the
previous R4 stall, zero alignment is not the explanation; improve pilot
survival next before claiming coverage of rounds9–10.

Evidence: `.local/bc-natural-seven-lives/verified.json`, input recording,
replays, boss-window report and archived tools. Matching production build
archive remains `.local/bc-render-flip-bits/candidate`. Syntax/diff checks
pass. Full natural campaign and sustained all-mode60fps remain incomplete.

### Round-six loop specialization rejected (2026-10-05)

Tested a dedicated round-six dispatcher to remove unrelated per-actor branches.
A direct constant-round copy exceeded the4MiB cartridge window (4325376bytes
padded) and was never tested as a valid cartridge. A compact loop handling
common/rain updates and using the existing family fallback fit, but increased
the80031-state natural route from86492 to86687frames. It preserved every state.
Restoring ordinary straight/homing bullet fast paths improved the total to86486,
but the round-six portion alone still cost35extra frames; unrelated compiler
layout improvements masked that regression in the total.

Both fitting candidates pass4773original-source loops/68425actor updates.
The revised candidate preserves all80031natural states and1000heavy4Pstates;
independent4P fullRAM replay passes. R6boss sample improves1871→1863frames,
mean981490.034→977220.895ticks,880→871over budget. HeavyR8 4P improves1352→1335.
However, the40opening cases cost80extra frames overall, including R6 4P889→983.
Rejected this tradeoff. Candidate hashes, source/ROM/ELF/symbol/layout snapshots
and results are under `.local/bc-sixth-loop/`; summary `rejected.json`.

Restored bc_runtime.c and rebuilt/finalized: release is byte-identical to
2b84480dd129ceacbfbc27948f746aec16b76e88ef9d577e3f1e9fc622df9c77. No production
change retained. Full natural campaign and sustained all-mode60fps remain open.

### Natural round-eight clear exposes round-nine shot handler (2026-10-05)

Added an optional `--boss-eight-lookahead 4..16` controller-pilot setting;
default4 preserves prior behavior. Twelve-update prediction only at the visible
R8boss, with the existing seven-life Home setup and normal damage, naturally
clears rounds1–8. One real continue was spent. R9 begins at tick123074;
the run stops at tick124871/status2 while four reserve lives remain.
Independent replay reproduces133510absolute frames with fullRAM/CPU/VRAM/pixel
checkpoint equality. Evidence: `.local/bc-r8-lookahead/verified.json` and
recorded inputs/replay. This is nondefault-lives coverage, not a full clear.

The stop is an actual port omission: a radial projectile enters state0x40
with death handler$A7EB in R9. The debug handler shows its living routine$9EB1,
so diagnosis used the stopped actor pool rather than that debug word alone.
Original R9 bytes at$A7EB are `A9 80 9D 08 2E 4C B1 9E`: restore state0x80,
then jump to common$9EB1. This is the existing R1$B5C2 revival translated by
-$DD7. Added$A7EB to R9's BOSS_SHOT_REVIVE mapping beside$AFB6.

New `qa_bc_boss9_shot_revive.py` checks the source bytes and compares1024cases
against explicit source state restoration plus the common task, including
scrolling, motion, retirement, player contacts and event outputs. It fails
before the fix at case0 and passes after. Original R9 opening retains5008loops,
112104actor updates and339child updates. Build/finalization/diff checks pass.
Candidate ROM fed523b91b9ae08cc5beb18633b131a2548fbb05d29fc33239a429be6d7b1d74
and matching source/ELF/symbol/layout headers are archived under
`.local/bc-r9-shot-revive/candidate`. A fresh natural campaign and BC40 matrix
are running; native passage beyond the former stop and timing remain pending.
Full campaign completion and sustained all-mode60fps are still unproven.

R9 revival fix BC40 matrix completed without measurement errors: 0 changed timings, 0 net extra video frames. Full speed remains false; natural continuation is still running.

R9 revival fix modal regression: new `qa_home_player_modal.py` verifies all12
Normal/BC/Rush ×1/2/3/4P combinations from fresh boot through real pad input.
Each case checks dialog, cancel without saved-count changes, selected count,
Home settings/player_limit and the correct mode entry. Rush also checks all
selected joined slots; BC checks native player count/status. This is menu/entry
coverage, not full gameplay or physical multitap coverage. All12pass onfed523...
with screenshots and per-case results under `.local/bc-r9-shot-revive/home-modals`.
The BC4P modal was visually inspected. Campaign continuation remains in progress.

### R9 revival fix passes natural continuation (2026-10-05)

On retained fed523b91b9ae08cc5beb18633b131a2548fbb05d29fc33239a429be6d7b1d74,
the seven-life/normal-damage pilot clears rounds1–8, passes the former
R9$A7EB failure, and clears R9's first three encounters. It reaches the
220000-update limit alive at the repeated fourth boss, with three reserve
lives and four boss bars remaining. One real continue was spent in R8.
Independent replay of231126absolute video frames matches full64KiB RAM,
CPU registers, VRAM, pixels and frame/tick checkpoint. No further unsupported
handlers were seen within this route. This validates the fix in native play,
not full-campaign completion. Summary: `.local/bc-r9-shot-revive/verified.json`.

Added optional `--boss-nine-four-direct-aim` to the controller pilot. It selects
the same direct-aim policy used for R4 only in R9 with boss sprite reference
$36BE, retaining real-core safety lookahead. Default behavior is unchanged.
A fresh natural run is live under `.local/bc-r9-direct-aim/`; its outcome and
independent replay are pending. Production ROM remains fed523... . Full-speed
and full-campaign requirements remain open.

Retained R9-fix heavy-party checks also complete: R8 warmup12000/measured1000
preserves1000canonical states each for3P/4P and both independent fullRAM
replays pass.3P uses1233frames (unchanged), mean809331.887coreticks;4P uses
1349frames (previous1352), mean873448.534. These bounded samples remain below
full speed, approximately49/44updates per nominal60Hz second, respectively.
Evidence: `.local/bc-r9-shot-revive/3p`, `4p`, and updated verified.json.

### R9 direct-aim pilot reaches eighth encounter (2026-10-05)

Retained optional R9 fourth-boss direct-aim pilot policy. On unchangedfed523...
ROM, seven-life1P Home with normal damage clears rounds1–8 and the first seven
R9encounters. It spends its final continue at the eighth encounter, tick154703,
then reaches the220000-update limit alive at the third encounter of the retry.
Full replay of231635absolute video frames matches fullRAM, CPU registers,
VRAM, pixels and frame/tick checkpoint. Inputs match the preceding pilot for
140465video frames before the new R9aim rule acts. No new unsupported handler
occurred. Evidence: `.local/bc-r9-direct-aim/verified.json` and recording/replay.
This remains nondefault-lives natural coverage, not a full campaign clear.

A new optional `--boss-nine-eight-lookahead 4..16` keeps the default4 and
selects a longer controller prediction only in R9 with boss reference$36C0.
A12-update run (matching the successful R8 policy) is live with a300000-update
limit under `.local/bc-r9-eight-lookahead/`; outcome/replay remain pending.
The production ROM is unchanged. All-mode sustained60fps remains unachieved.

### Twelve-step R9 eighth-boss pilot remains insufficient (2026-10-05)

On unchangedfed523... ROM, the R9 eighth-boss12-update prediction run ends
at tick294782 with game over in that encounter. Both real continues were used;
the retry cleared the first seven R9encounters again but exhausted six reserve
lives at the eighth. No new unsupported handler or art stop occurred. Independent
replay reproduces310693absolute gameplay frames with fullRAM/CPU/VRAM/pixel
checkpoint equality. Home return passes separately after the captured endpoint.
Evidence: `.local/bc-r9-eight-lookahead/verified.json`. This policy does not
establish any additional completed encounter beyond the earlier run.

Inspection of `choose_move` identifies a controller-search weakness: if every
constant-direction branch predicts death, it previously chose solely by aim
distance. Added optional survival tie-breaking to prefer the latest predicted
death, then aim distance; safe choices still outrank dying ones and the default
policy is unchanged. `--boss-nine-eight-survival` applies it only to R9$36C0 and
records calls, all-directions-die decisions, and changed choices. A new natural
seven-life run with12-update prediction and350000-update limit is live under
`.local/bc-r9-survival/`; its outcome and independent replay remain pending.
No production ROM change. Full campaign and sustained60fps remain unfinished.

### First independently verified natural full campaign clear (2026-10-05)

Unchanged native ROM fed523b91b9ae08cc5beb18633b131a2548fbb05d29fc33239a429be6d7b1d74
now has a complete natural1P Home clear through all ten rounds, normal damage,
seven configured lives and one real continue. R10 entry tick158174; final clear
tick160119. No forced deaths/defeats, seeded health/weapons, protection or
snapshot restores in the authoritative run. Independent replay reproduces all
170392recorded gameplay video frames and exact full64KiB RAM, CPU registers,
VRAM, pixels and frame/tick checkpoint.

The R9 eighth-boss survival tie-break made one changed decision among2617search
calls: one call predicted death for every constant-direction branch. Its input
prefix matches the unsuccessful12-step policy for163627video frames. The new
choice retained enough survival to clear the eighth and ninth encounters and
R10. This is a controller-policy improvement, not altered ROM/game rules.

The pilot observed ending phases10,11,8,1,2,9,3,4,5,6,7 over12110frames,
5760credit updates with gameplay frozen, then Home return. Added optional
`qa_bc_controller_replay.py --verify-ending`: after exact gameplay replay it
repeats that ending input sequence and verifies phase/duration equality,
credits, frozen gameplay and final Home pixels. Passes. Original post-ending
fullRAM was not recorded, so only the stated ending checks are claimed.
Congratulations/ending screens were visually inspected.

Evidence: `.local/bc-r9-survival/verified.json`, recording, checkpoints,
controller-replay.json, ending screenshots and archived tools. Matching native
build archive: `.local/bc-r9-shot-revive/candidate`. One complete natural1P
campaign at nondefault lives is now verified; default-settings and all-player-
count campaign coverage are not implied. All12Home modal combinations remain
verified. Sustained all-mode60fps is still unachieved; preserve this successful
recording as a complete-route regression for further native optimizations.

### Full-clear route baseline and rejected common-motion split (2026-10-05)

Captured160172completed simulation states from the verified natural ten-round
clear onfed523... . Capture reproduces the original full checkpoint at170392
video frames. Scene-paced replay matches every canonical actor/stage/player/
score/RNG/credit/continue state, taking170383frames; the different video phase
is recorded, not treated as a cross-build fullRAM equality. R6tick76000 sample
uses1870frames/1000calls, mean980484.785coreticks. This full-route comparison
corpus is under `.local/bc-full-route-baseline/verified.json` and will detect
late-round regressions that the earlier truncated route could not exercise.

Tested separating the complete multiplayer motion/contact path from the solo
common task, revisiting an older split after the coordinate/velocity changes.
Host32000contact cases and party-routing tests pass. The candidate preserves
all160172full-route states and1000heavy4Pstates; independent4P RAM replay passes.
Performance rejects it: full route170383→170706frames, R6sample1870→1871,
mean980484.785→984321.506; heavyR8 4P1349→1692, mean873448.534→969348.296.
Native code explains the multiplayer loss: the extracted party function calls
motion separately and saves ten registers, versus five in the shared handler.
The solo entry saves only three registers but still does not improve the route.

Candidate bf2b4ea9543ccb74504b058b6f1411b275bbb3f635c2fd77471ac0517e8ab274,
source/ROM/ELF/symbol/layout snapshots and all checks are archived under
`.local/bc-common-motion-split/`; summary rejected.json. Restored bc_world.c
and rebuilt/finalized; release is byte-identical to retainedfed523... . No
production change retained. The verified natural1P clear remains valid;
sustained all-mode60fps remains unfinished.

### Rejected player coordinate cache — 2026-10-05

Cached player integer coordinates in each temporary shot index during the actor
pass, retaining an uncached fallback for other callers. Host contact tests
(32,000 cases), shot-index/routing tests and the native index probe passed.
All 160,172 canonical full-route states and all 1,000 heavy 4P states match
the retained build; independent 4P replay also passes. These canonical hashes
cover the subset stated in scene-record.json, not cross-build full RAM.

Performance regressed: full route 170,383 → 170,816 frames; R6 profile
1,870 → 1,886 frames per 1,000 calls (mean 980,484.785 → 987,588.518
core ticks); heavy 4P 1,349 → 1,366 frames. The 40 opening measurements
had no measurement errors; their aggregate frame change was 30.
Restored all eight experimental source/test files and rebuilt; release is
byte-identical to fed523b91b9ae08cc5beb18633b131a2548fbb05d29fc33239a429be6d7b1d74.
Evidence and archived candidate: `.local/bc-player-pixel-cache/rejected.json`.
No performance regression retained. Sustained all-mode 60 fps remains unverified
and is contradicted by the heavy multiplayer measurements.

### SAT write memory-range experiment — 2026-10-05

Replaced the MOVEM.W sprite writer's global memory clobber with an explicit
eight-byte output operand, preserving its four fixed registers and instructions.
The native SAT test passed all 20,480 cases and sentinels. All 160,172 canonical
full-route states and 1,000 heavy 4P states match; independent 4P replay passes.
Heavy 4P is exactly unchanged at 1,349 frames and mean 873,448.534 core ticks.
Full route improves slightly, 170,383 → 170,377 frames; the slow R6 sample
stays at 1,870 frames, mean 980,484.785 → 980,453.215 ticks. This negligible
route gain does not address the measured heavy slowdown. Restored sprites.c
and rebuilt the byte-identical fed523b9 release rather than retain a global
renderer change without meaningful measured benefit. Normal/Rush performance
was not tested for this rejected candidate.

Candidate 8382d8f3aea7d205a1068e086ff1464f7bfd99c68e0d55c2af2fef23cbfac46c
and matching source/ROM/ELF/header archives, native logs, route/profile evidence
and actor-renderer instruction cost ranking: `.local/bc-sat-store-range/`.
Decision manifest: `rejected.json`. Sustained all-mode 60 fps remains unfinished.

### Reuse collision scan bounds — 2026-10-05

Retained ROM 7a26d323b166c619d39bec2474db46f33f7ed24b2a1e2021669e93b021e8328c.
Compute the conservative target/index half-width sums once per shot scan
instead of once per candidate shot. Exact byte-wrapped per-shot hitboxes,
live-state checks, consumption, damage and source slot order remain intact.
No actors, shots, updates, artwork or waves were removed.

Compared with fed523b9, the full scene-paced natural-route replay takes
170,289 rather than 170,383 frames; all 160,172 canonical states match.
R6's 1,000-call sample improves 1,870 → 1,866 frames, mean
980,484.785 → 977,821.404 core ticks. Heavy R8 4P regresses
1,349 → 1,353 frames despite a small mean reduction 873,448.534 →
873,398.547. This is a retained tradeoff, not universal acceleration.
Heavy 3P stays at 1,233 frames; vulnerable R4 4P stays at 483 per 300 calls.
All 2,300 compared profile states match and independent replays pass.
The 40 BC openings save one frame overall with no measurement errors.

Host 32,000 shot scans, 32,000 multiplayer contact cases and party routing pass.
All 40 Normal timings, 40,040 gameplay hashes and 40,040 sprite hashes match
the prior renderer baseline. Rush remains 2,990 updates in 3,000 frames; all
video hashes match, no drops/remaps/wheel fallback, reset cleanup passes.
All 12 Home mode/player dialog, cancel and launch combinations pass.
Evidence, matching source/include/ROM/ELF/symbol archives, and per-window route
changes are in `.local/bc-shot-radius-hoist/verified.json` and adjacent files.
The full-route comparison uses the documented canonical subset, not cross-ROM
full-RAM equality. The prior natural 1P clear evidence remains on fed523b9;
all-player-count natural campaign coverage and sustained all-mode 60 fps
remain unfinished.

### Rejected shot-distance reuse — 2026-10-05

Carried the indexed shot scan's already computed X/Y distances into its exact
per-shot hitbox tests. Host 32,000 shot scans and 32,000 contact comparisons
pass. All 160,172 canonical full-route states and 1,000 heavy 4P states match;
independent 4P replay passes. Native actor_contacts shrinks by six bytes.

Against 7a26d323, the full route improves 170,289 → 170,276 frames and the
R6 profile improves 1,866 → 1,865 frames, mean 977,821.404 → 977,743.935
core ticks. Heavy 4P regresses 1,353 → 1,354 frames, mean
873,398.547 → 873,332.831. All 40 opening timings are unchanged with no
measurement errors. Rejected: the tiny route gain does not justify another
heavy-4P frame regression. Normal and Boss Rush were not tested for this
rejected candidate. No behavior difference found in the tested scopes.

Candidate 33ee724e530e7147f7d15fc721c03350abaf72cf7e15cf26be859396768a047f,
matching source/ROM/ELF/header snapshots and results are archived under
`.local/bc-shot-distance-reuse/`; decision `rejected.json`. Restored bc_rules.c
and rebuilt byte-identical 7a26d323b166c619d39bec2474db46f33f7ed24b2a1e2021669e93b021e8328c.
The earlier bounds-hoisting optimization remains retained. Sustained all-mode
60 fps and all-player-count campaign verification remain unfinished.

### ROM input translation table — 2026-10-05

Retained ROM 30280571cb8cad635d94430f31295bc96ba658b2b34544e41f6bc88974ae2293.
BC's logical held/pressed input conversion now uses a 256-byte constant ROM
table instead of eight repeated bit tests per byte. There is no added RAM.
Static assertions pin the logical input bit assignments. New
`tools/qa_bc_buttons.py` compiles the production mapper and checks all 256
combinations against the independent per-bit contract, including opposing
and simultaneous inputs. Mapping, controller order and input cadence stay intact.

Against 7a26d323: heavy R8 4P improves 1,353 → 1,306 frames per 1,000
updates, mean 873,398.547 → 859,037.347 core ticks. Heavy 3P improves
1,233 → 1,214, mean 809,323.270 → 798,460.852. Vulnerable R4 4P improves
483 → 466 frames per 300 updates. All 2,300 compared gameplay states match
and each independent full-RAM replay passes. The 40 BC opening measurements
save 119 frames overall: 15 improve, 25 tie, none regress, no measurement errors.

Full scene-paced natural-route replay improves 170,289 → 170,044 frames; all
160,172 canonical states match. R6 sample improves 1,866 → 1,859 frames,
mean 977,821.404 → 974,705.690 ticks. Canonical comparisons retain their
documented subset scope; they are not cross-build full-RAM equality.

All 40 Normal timings, 40,040 gameplay hashes and 40,040 sprite hashes match.
4P Rush retains 2,990 updates/3,000 frames, identical video hashes, zero
drops/remaps/wheel fallback and passing reset cleanup. All 12 Home mode/player
dialog/cancel/launch combinations pass. The BC 4P menu test also verifies each
controller's pause/freeze/resume, return, re-entry and paused reset.
Evidence and matching source/ROM/ELF/header/test snapshots:
`.local/bc-input-table/verified.json` and `candidate/`.

This is a measurable multiplayer gain, not completion: heavy 4P is about
45.9 updates/sec at nominal 60Hz and 3P about 49.4. Sustained all-mode 60 fps
and all-player-count natural campaign verification remain unfinished.

### Rejected scene player-pointer table — 2026-10-05

Tested replacing scene member(i) address reconstruction with the existing
party_control.players table. begin() still constructs its binding from the
primary player/allocated peers before runtime lookups; no added RAM.
All 160,172 full-route canonical states and 1,000 heavy 4P states match.
Independent heavy 4P replay and real 4P menu/cancel/launch/controller pause,
return/re-entry and paused reset pass.

Performance rejects the change: full route 170,044 → 170,087 frames;
R6 sample 1,859 → 1,861 frames, mean 974,705.690 → 975,267.216 ticks.
Heavy 4P stays at 1,306 frames with mean 859,037.347 → 858,093.859.
The 40 openings save four net frames, but have mixed regressions; no
measurement errors. Normal/Rush were not tested for the rejected candidate.

Candidate e6e40296615570189aedac28719864bbe03acecf612e38794e39cfe9584cdc66
and matching source/include/ROM/ELF/header snapshots and measurements:
`.local/bc-member-table/rejected.json` and adjacent files. Restored bc_scene.c
and rebuilt byte-identical 30280571cb8cad635d94430f31295bc96ba658b2b34544e41f6bc88974ae2293.
The input-table optimization remains retained. Sustained all-mode 60 fps and
all-player-count natural campaign verification remain unfinished.

### Rejected shared player terrain probe — 2026-10-05

Tested skipping the vertical terrain lookup when the horizontal probe was
empty and both probes addressed the same 16-pixel subcell. Horizontal
collisions retain the original second lookup because scrolling can change X.
200,000 old/new C movement comparisons pass with all direction nibbles,
full-word positions/camera/scroll, wrapping and crushes. The existing 20,000
terrain/stationary/scrolling predictor comparisons also pass.

All 160,172 full-route canonical states and 1,000 heavy 4P states match;
independent 4P replay passes. Heavy 4P improves 1,306 → 1,297 frames, mean
859,037.347 → 855,922.984 ticks. Forty opening samples save 11 frames overall
but include small regressions; no measurement errors. Natural-route timing
rejects this version: 170,044 → 170,077 frames, R6 sample 1,859 → 1,862,
mean 974,705.690 → 975,151.254. Normal/Rush were not tested for this rejected
candidate. No claim of universal speedup follows from the favorable 4P fixture.

Candidate 41a76068ab2c39fe1eec7aadd7aa5cdae14bfd55497d8e48dfc673c6eeb97359
and matching source/include/ROM/ELF/header snapshots, comparison counts and
measurements are archived under `.local/bc-player-terrain-reuse/`; decision
`rejected.json`. Restored bc_rules.c and rebuilt byte-identical
30280571cb8cad635d94430f31295bc96ba658b2b34544e41f6bc88974ae2293.
The input-table optimization remains retained. All-mode sustained 60 fps and
all-player-count natural campaign verification remain unfinished.

### Rejected zero-velocity projectile addition gate — 2026-10-05

Tested skipping beam_axis's signed 24-bit addition when velocity is zero,
retaining the existing position mask and carry-dependent offscreen predicate.
Source beam-flight and fractional-beam captures pass (266 active updates and
six launches each); returning-weapon capture passes 2,089 updates, 61 launches
and 61 catches. All 160,172 full-route canonical states and 2,000 native
profile states match; independent ordinary/charged 4P replays pass.

Ordinary heavy 4P is exactly unchanged at 1,306 frames and mean 859,037.347
ticks. Charged 4P is exactly unchanged at 1,253 frames and mean 781,102.532.
All 40 opening timings are unchanged with no measurement errors. Full route
regresses 170,044 → 170,080 frames; R6 sample 1,859 → 1,860, mean
974,705.690 → 974,750.119. Rejected: no measured multiplayer gain and a
long-route loss. Normal/Rush were not tested for the rejected candidate.

Candidate 2d13fa19063917f3f6def7895cc94299af80c1e2c75e5137b39f9b4ac5044363
and matching source/include/ROM/ELF/header snapshots and evidence are under
`.local/bc-projectile-zero-axis/rejected.json` and adjacent files. Restored
bc_rules.c and rebuilt byte-identical
30280571cb8cad635d94430f31295bc96ba658b2b34544e41f6bc88974ae2293.
The input-table improvement remains retained. All-mode sustained 60 fps and
all-player-count natural campaign verification remain unfinished.

### Replay scope clarification and round-six 4P baseline — 2026-10-05

Clarified qa_bc_scene_replay.py's ambiguous comparison_scope wording and added
explicit canonical byte-layout metadata. The hash algorithm is unchanged:
32 canonical 50-byte actors, 24-byte stage, player bytes 0..999 and 1008..1023,
2-byte RNG seed, 35-byte score, 1-byte credits, and 4 unused-continue counts.
That is 2,682 bytes; only the player's two transient pointer fields are omitted
from its record. Score/RNG/credits/continue counts were already included in
prior hashes. Earlier shorthand must not be read as excluding those fields.
This is still not a whole-RAM or video comparison.

Replayed all 160,172 natural-route scenes on retained 30280571; all hashes
match the prior recording, and timing is exactly unchanged: 170,044 route
frames and 1,859 R6 profile frames, mean 974,705.690 ticks. No production
source or ROM change. The clarified report is under
`.local/bc-replay-scope-audit/verified.json` and `replay/`.

Added a fresh read-only diagnostic for R6 4P after 12,000 warmup updates.
It needs 1,469 video frames for 1,000 updates (about 40.84 updates/sec at
nominal 60Hz), mean 896,975.212 core ticks before outer input/VBlank/DMA.
Independent full-RAM replay passes. Mean workload: 30.957 active world records,
1.901 player-weapon records, 38.308 submitted SAT entries. World records
include shots, pickups and dying actors, not only living enemy ships. Largest
attributed routines: common actors 180,400,822 ticks, actor drawing 143,797,920,
general dispatch 124,282,158, player updates 99,326,570, scene 88,365,200.
Evidence: `round6-4p/result.json`; source/layout matching archive remains
`.local/bc-input-table/candidate/`. These results identify common actor work
as the next measured target and confirm that the round-eight sample does not
establish a whole-game lower bound. Sustained all-mode 60 fps and all-player-
count natural campaign verification remain unfinished.

### Detailed party contact scan outlined behind rejection gates — 2026-10-05

Retained ROM ce51fa8743caf099924becd454e20a948bd3bad15d682be922797c7c3cda2177.
Moved the detailed ordered multiplayer contact scan into an O2 noinline helper,
keeping motion, event initialization and whole-party quick rejection in the
common entry. Vulnerable-party body/shot union rejection also precedes the
helper, so distant contacts do not pay its register-save cost. Potential contacts
retain the original per-member order, callbacks, exact hitboxes, counters and
damage behavior. No actors, waves, graphics or updates are removed.

The first version improved protected samples but regressed the normal-damage
R4 4P sample from 466 to 488 frames. It was superseded by v2 with vulnerable
union rejection moved before the helper. Both variants and their evidence are
preserved; only v2 is retained.

Against input-table ROM 30280571, v2 improves heavy R6 4P 1,469 → 1,461
frames per 1,000 updates, mean 896,975.212 → 894,894.742 ticks. Heavy R8
4P improves 1,306 → 1,298, mean 859,037.347 → 855,981.525; R8 3P improves
1,214 → 1,204. Normal-damage R4 4P improves 466 → 465 frames per 300
updates, mean 908,630.520 → 903,253.797. All 3,300 native profile states
match and all four independent replays pass.

Full-route scene replay improves 170,044 → 169,879 frames; all 160,172
canonical state hashes match, including score/RNG/credits/continue counts.
The R6 solo profile improves 1,859 → 1,853, mean 974,705.690 → 971,584.103.
Forty BC openings save 20 net frames with no measurement errors; small
regressions remain: R6 3P +5 and three other cases +1. This is a measured
aggregate improvement, not universal full-speed behavior.

Host 32,000 contact comparisons and party routing pass. Event-filter checks
pass 5,000 events and 256 complete loops, preserving score/audio/defeat and
observer order. All 40 Normal timings, 40,040 gameplay hashes and 40,040 sprite
hashes match. Rush retains 2,990 updates/3,000 frames with identical video
hashes, no drops/remaps/wheel fallback and passing reset cleanup. All 12
Home mode/player dialog/cancel/launch cases pass. R8 4P 3,000-update stack
probe has no overlap and 11,180-byte minimum gap; that is route-specific.

Evidence: `.local/bc-party-scan-outline/verified.json`; retained matching
source/include/ROM/ELF/header archive and results under `v2/`. Initial variant
is in `candidate/` with `v1-superseded.json`. Build is warning-free and diff
checks pass. Sustained all-mode 60 fps and all-player-count natural campaign
verification remain unfinished: heavy R6 4P is still roughly 41 updates/sec.


### Party body-distance result reuse (2026-10-05)

Retained ROM `6dc0e1f63dad5757db3f9cdcb53d1190eb338c088ab04e990f368e98a01ede49`
reuses the body-union distance predicate across the rejection gate and detailed
party contact helper. No actor, contact, animation, or update is removed.
Against ce51fa87, heavy R6 4P improves 1,461 to 1,453 video frames per
1,000 updates; heavy R8 4P improves 1,298 to 1,290. The R8 3P sample
regresses 1,204 to 1,205 frames despite slightly lower mean CPU time.
Normal-damage R4 4P stays at 465 frames per 300 updates, with mean CPU
903,253.797 to 904,351.863 ticks. All 3,300 profile states match and all
four independent replays pass. This is a small measured tradeoff.

The complete route matches all 160,172 canonical state hashes and stays at
169,879 frames. R6 solo remains 1,853 frames and 971,584.103 mean ticks.
The 40 BC openings cost one net frame, with no measurement errors.
All 40 Normal timings, 40,040 gameplay hashes and 40,040 sprite hashes
are unchanged. Rush video hashes match exactly: 2,990 updates in 3,000
frames, zero sprite drops/remaps/wheel fallback, successful reset cleanup.
All 12 Home mode/player modal cases pass. The R8 4P 3,000-update stack
probe reports no overlap and 11,180 bytes minimum gap on that route.
Host tests pass 32,000 contacts, party routing, 5,000 filtered events and
256 complete event loops. Evidence and matching candidate source/ROM/ELF
are in `.local/bc-party-body-result/`, with `verified.json` recording scope.
Sustained 60 fps remains unverified and contradicted by the heavy samples;
no whole-game or all-player-count completion claim is made.


### Rejected party motion early return (2026-10-05)

Tested an explicit nonzero-motion return after retirement handling, eliminating
repeated motion guards in party contact dispatch. Host 32,000 contact cases and
party routing pass; native heavy R8 4P matches 1,000 state hashes and its
independent replay. All 160,172 full-route hashes match and route timing stays
at 169,879 frames, with the R6 solo profile unchanged. However, heavy R8 4P
regresses 1,290 to 1,295 frames per 1,000 updates and mean CPU rises from
855,395.317 to 856,037.126 ticks. Rejected candidate 462b5dd2; restored
6dc0e1f6 source. Evidence: `.local/bc-party-motion-exit/rejected.json`,
matching candidate archive and measurement results. No speed claim.


### Sprite-cache signed-word address formation retained (2026-10-05)

Retained ROM `1cc53615d083f1208623e1b166c901505c87bc12ff9bce4afa744c54e82d0f74`
uses a signed-word displacement for the native sprite-cache bucket. The largest
offset is 1,016 bytes; a compile-time assertion pins the range. An empty register
constraint preserves word address formation through GCC range propagation,
producing AND.W / MOVEA.W instead of AND.L / MOVEA.L. Bucket selection, cache
keys, eviction, pinning, RAM/layout, uploads and sprite submissions are unchanged.
The production-extracting `tools/qa_sprite_hash_native.py` checks all 65,536 keys
at three origins on the 68000: 196,608 exact address comparisons pass.

Against 6dc0e1f6, heavy R8 4P improves 1,290 to 1,286 video frames per 1,000
updates, mean 855,395.317 to 853,861.330 ticks. R8 3P improves 1,205 to 1,203,
mean 794,846.479 to 793,059.197. R6 4P improves 1,453 to 1,452, mean
894,133.296 to 892,936.044. Normal-damage R4 4P stays at 465 per 300 updates,
mean 904,351.863 to 903,711.877. All 3,300 profile state hashes match and
all four independent replays pass.

Full-route replay matches all 160,172 canonical states and improves 169,879 to
169,822 video frames. R6 solo CPU improves 971,584.103 to 970,091.857 mean
ticks, but its sample takes 1,854 rather than 1,853 frames. Forty BC openings
save 16 frames: seven improve, 33 tie, none regress, no measurement errors.
Forty Normal cases preserve all 40,040 gameplay and sprite hashes and save
two net frames: 2P sections 2/9 and 4P section 9 save one each, while 4P
section 7 costs one. These are aggregate gains with disclosed local regressions.

Rush retains identical video hashes, 2,990 updates / 3,000 frames, zero
sprite drops/remaps/wheel fallback, and passing reset cleanup. All 12 Home
mode/player modal combinations pass. The R8 4P 3,000-update stack probe has
no overlap; its measurements are route-specific. Final rebuild matches the
measured ROM byte-for-byte. Evidence, candidate source/include/ROM/ELF and
native probe are archived in `.local/sprite-hash-word-address/verified.json`
and its sibling files. Sustained all-mode 60 fps and all-count natural campaign
completion remain unachieved; no reductions to content or updates were made.


### Native projectile flip rotations retained (2026-10-05)

Retained ROM `62a21a4b313d1b26084fa86dc17a8a1c44be2aeed5fcf62fe00d5d753d2ce39e`
replaces expensive shift-based projectile flip extraction with native word
rotations by five and two, as already used by the actor pose selector. Source
attribute bits, returning-shot facing overrides, art selection and coordinates
are unchanged. Production-native tests cover every attribute word across four
frame categories: 262,144 cases. Host draw tests preserve 37,177 ordered sprites
and 600 packed strips across 2,400 pools. No enemies, shots or updates are removed.

Compared with 1cc53615, the recorded full route saves 223 video frames
(169,822 to 169,599), matching all 160,172 canonical gameplay state hashes.
The R6 solo sample improves 1,854 to 1,838 frames per 1,000 updates and
970,091.857 to 965,624.940 mean CPU ticks. Projectile drawing falls from
98,619,192 to 94,165,764 attributed ticks across that window (~4.5%).
The worst sliding 1,000-update window in this route now spans 1,882 video
frames (~31.88 updates/sec at 60 Hz), compared with 1,895 before this change.
This is a bounded 1P recording, not exhaustive worst-case coverage.

Heavy R8 4P improves 1,286 to 1,279 frames; R6 4P improves 1,452 to 1,445;
normal-damage R4 4P improves 465 to 464 per 300 updates. R8 3P costs one
frame (1,203 to 1,204) despite mean CPU falling 793,059.197 to 792,336.412.
All 3,300 native profile state comparisons and four independent replays pass.
Forty BC openings save seven net frames, with four one-frame regressions:
R4 4P, R7 3P/4P and R9 4P. No measurement errors or ROM changes occurred.

All 40 Normal timings and 40,040 gameplay/sprite hashes remain identical.
Rush video hashes match exactly: 2,990 updates / 3,000 frames, no software
drops/remaps/wheel fallback, successful reset cleanup. All 12 Home mode/player
modal cases pass. R8 4P stack probe: 3,000 updates, no overlap, 11,180-byte
minimum gap on this route. Build/diff checks pass. Matching source/ROM/ELF,
results and scoped manifest: `.local/bc-projectile-flip-rotate/verified.json`.
Sustained 60 fps and natural campaign coverage at every player count remain
unfinished; the retained change improves measured costs without claiming completion.


### Rejected beam carry branch (2026-10-05)

Tested conditional increment of the beam offscreen bound when bit 24 of its
24-bit position-plus-velocity sum is set. Native exhaustive velocity checks at
ten fractional/boundary positions pass 655,360 cases. Both beam source captures
pass 266 active updates and six launches each. Full route matches all 160,172
canonical states and improves 169,599 to 169,552 frames; R6 solo improves
1,838 to 1,831 frames, mean 965,624.940 to 963,138.260 CPU ticks.

However heavy R8 4P regresses 1,279 to 1,288 frames per 1,000 updates despite
mean CPU decreasing 852,994.023 to 852,615.351. A separately measured archived
baseline and candidate charged-fire 4P sample tie at 1,242 frames; its CPU falls
776,853.210 to 776,229.202. Both profiles match all 1,000 gameplay states and
independent replays. Forty BC openings save nine net frames, with no measurement
errors. Rejected this mixed change in favor of the retained heavy 4P timing.
Restored 62a21a4b source. Candidate 823be4d3 and evidence remain archived at
`.local/bc-beam-carry-branch/rejected.json`. No completion or full-speed claim.


### Rejected direct charged-beam stepping (2026-10-05)

Tried routing live kind-3 shots directly to bc_beam_step from the weapon pool
loop, bypassing the general dispatcher and preserving option retirement counts
and exact slot order. Differential tests match 60,000 complete pool updates and
6,000 randomized launch/occupied/fractional cases. Both native 4P samples match
1,000 gameplay hashes and pass independent replay; full route matches all
160,172 canonical states.

Timing rejects the split: ordinary R8 4P regresses 1,279 to 1,328 frames and
852,994.023 to 866,255.432 mean CPU ticks; charged 4P regresses 1,242 to 1,268
and 776,853.210 to 786,435.650. Full route changes 169,599 to
170,278 frames; R6 sample changes 1,838 to
1,870, mean 965624.940 to 981051.071.
The generated player routine grows 6,372 to 6,562 bytes and its stack frame
192 to 204 bytes, despite a smaller dispatcher. Restored 62a21a4b source.
Candidate aa232ae2, assembly, matching snapshots and evidence are archived in
`.local/bc-beam-direct-step/rejected.json`. Full speed remains unfinished.


### Rejected O2 weapon dispatcher (2026-10-05)

Tested native-only optimize("O2") on the existing noinline weapon_live_step,
with no source algorithm, pool ordering or ABI change. The dispatcher shrinks
2,430 to 270 bytes and stops saving four registers, but delegates more work to
helper calls. Both 4P profiles match 1,000 gameplay states and pass independent
replay. Full route matches all 160,172 canonical states.

Ordinary R8 4P regresses 1,279 to 1,295 frames / 1,000 updates and mean CPU
852,994.023 to 855,060.122. Charged 4P regresses 1,242 to 1,248, mean
776,853.210 to 779,020.403. Full route changes 169,599 to
170,354 frames; R6 solo changes 1,838 to
1,870, mean 965624.940 to 983462.543.
Rejected e2a6ebcd and restored 62a21a4b source. Evidence and matching
source/ROM/ELF/assembly are in `.local/bc-weapon-dispatch-o2/rejected.json`.
These results reject local code size as a proxy for speed; the full objective
remains active and sustained 60 fps remains unfinished.


### Multiplayer natural-campaign predictor support (2026-10-05)

ROM remains 62a21a4b byte-for-byte. The basic controller-driven 4P Home run
(with seven configured lives and real continues, no protection/forced defeats/
seeded health or weapons) clears round one but loses at the round-two boss.
It ends at tick 17,733 / absolute video frame 29,953 after two real continues,
and returns Home from game over. Independent replay without save-state restores
matches full endpoint RAM, CPU registers, VRAM and pixels. This is a bounded
failed pilot route, not evidence of a port bug or campaign completion.

Extended host-only choose_move with a selected player index and proposed peer
controller inputs. Forecasting reads that player's state/coordinates, retains
peer held inputs, and emits peer press edges only at the first forecast update.
All speculative steps remain on the separate shadow core. Campaign pilot now
constructs all controller proposals before forecasting each player, so no peer
is inadvertently held idle during another player's prediction. The natural
Home-only, no-protection guard remains; 1P is no longer the only supported count.

New qa_bc_pilot_party synthetic fixture exercises all four selected players,
inactive-peer handling and retained peer inputs, checking unchanged authoritative
RAM/CPU/VRAM/pixels after every prediction. A separate 36-case comparison against
the prior default player-zero predictor produces identical choices and no live
machine changes. Evidence and tool snapshots:
`.local/bc-natural4p-current/predictor-verified.json` and `verified-tools/`.
A fresh 4P lookahead campaign is running separately; no outcome is claimed here.
Full natural campaigns at all counts and sustained 60 fps remain unfinished.


### Natural 4P round-two slowdown measured (2026-10-05)

The completed basic 4P Home pilot provides a new vulnerable-party profiling
corpus on retained 62a21a4b. The 1,000-update window at ticks 10,019–11,019
spans 2,186 video frames: approximately 27.45 gameplay updates/sec at 60 Hz.
It precedes the route's first player death at tick 12,642. This supersedes the
previous ~31.9-fps worst-known sustained sample; neither is exhaustive coverage.
Independent input replay with profiling still matches the recorded full endpoint
RAM, CPU registers, VRAM and pixels. No protection, forced defeat, health or
weapon injection is used in this natural seven-life Home run.

Every measured complete scene exceeds the 896,040-tick frame budget. Mean is
1,542,318.309 ticks; maximum 2,259,089. Scene profiling excludes outer input,
VBlank and DMA work. Leading attributed totals across 1,000 calls: general actor
loop 207,896,234; common actor task 160,541,332; detailed party contacts
153,424,012; projectile drawing 135,643,004; player task 133,023,744; weapon
stepping 132,233,458. Body-union rejection adds 39,184,376 and per-player body
proximity 33,332,936. This vulnerable 4P route exposes substantially more contact
work than the protected R8 fixtures and should accompany future optimization
comparisons. Evidence: `.local/bc-natural4p-current/round2-profile-verified.json`,
`r2-hot-instructions.json`, and `basic-campaign/replay-profile/`.
The improved multiplayer lookahead pilot remains live separately; at its latest
checkpoint it has reached round four. No full campaign or speed completion claim.


### First multiplayer-lookahead campaign attempt replayed (2026-10-05)

The host predictor's natural 4P Home attempt on unchanged 62a21a4b reaches
round four. R2 entry is tick 6,658 and R3 entry 14,364 with all four players'
starting lives intact. R4 entry is tick 21,870 with remaining-life counters
[5,6,4,6]. The party eventually loses at the R4 boss, after two real continues;
game over is tick 33,508 / absolute frame 56,689 and Start returns Home.
Seven lives were selected through Home Options. No protection, forced enemies,
health/weapons injection, or restores into the authoritative core are used.

Independent replay of the full input record, without prediction or restores,
reproduces the exact endpoint work RAM, CPU registers, VRAM and pixels.
This establishes one natural 4P path through rounds 1–3 and a replayable R4
boss failure, not a complete 4P campaign or a demonstrated game bug. Tool and
route evidence: `.local/bc-natural4p-current/lookahead-attempt-verified.json`.
The attempt and replay are terminal; no campaign process remains live.
Sustained 60 fps remains contradicted by the verified natural R2 sample (~27.45
updates/sec); further optimization must include this vulnerable-party workload.


### Complete peer coverage in scene-paced comparisons (2026-10-05)

Extended qa_bc_scene_replay from solo-only recordings to 1–4P Home recordings.
The established solo hash byte sequence stays unchanged. Multiplayer appends
every selected peer's 1,016 canonical player bytes, its 35-byte score, all twelve
continue-prompt bytes, and pending/shown flags. Transient shot-index/party
pointers at player offsets 1,000–1,007 remain excluded for every member; actor
coordinates/velocities retain their canonical normalization. Four-player scenes
hash 5,849 bytes. Native compiler assertions pin player stride/pointer offsets,
stage, score and continue layouts rather than silently accepting ABI drift.

The coverage test passes 964 mutations across 1–4P, checking included fields,
excluded pointers/unselected peers, and the exact legacy solo prefix. On
62a21a4b, 4P capture reproduces the original full RAM/CPU/VRAM/pixel checkpoint,
then scene-paced replay matches all 17,736 complete states. Its natural R2
baseline is 2,186 frames and 1,542,301.376 mean ticks for 1,000 complete calls;
the complete partial route uses 29,957 frames. Capture/video-paced recording
uses 29,953 frames; this input-boundary difference is why candidate comparisons
use the scene-paced baseline. The full solo corpus still matches all 160,172
states and unchanged timing. Capture is original-build-only; cross-build replay
is canonical gameplay comparison, not full RAM or video comparison.

Evidence and tool snapshots: `.local/bc-natural4p-scene-corpus/verified.json`.
This QA change enables vulnerable 4P optimization checks without weakening the
solo record or claiming campaign/speed completion.

### Party body predicate inlining retained (2026-10-05)

ROM `3fe12cc6f6d4bea621c6c2ef3070f780963badc3be86150fff29b4340f5986dd` replaces `62a21a4b313d1b26084fa86dc17a8a1c44be2aeed5fcf62fe00d5d753d2ce39e`. The private party contact scan now inlines the existing body-distance predicate. Collision formulas, ordering, enemy counts, artwork, and solo code are unchanged. Evidence: `.local/bc-party-body-inline/verified.json`.

The natural 4P partial route matches all 17,736 canonical states including every selected peer and takes 29,804 frames instead of 29,957. Its round-two 1,000-call profile drops from 2,186 to 2,129 video frames. The worst contiguous 1,000 advancing updates improve from 2,191 frames (27.385 updates/sec at 60Hz) to 2,132 (28.143). This is useful progress but still far below 60fps.

Tradeoffs: protected round-eight 4P takes 1,284 versus 1,279 frames; round-six 4P improves 1,445 to 1,438; 3P stays 1,204; vulnerable round-four improves 464 to 463. All 3,300 states and independent replays match. The 40 BC opening samples cost four extra frames in total. The full solo route matches all 160,172 states and remains 169,599 frames, with its round-six profile unchanged. Normal's 40 timing samples and 40,040 state/sprite hashes match. Boss Rush remains 2,990 updates in 3,000 frames with identical video hashes, no sprite drops/remaps/wheel fallbacks, and reset cleanup passing. All 12 Home mode/player modal cases pass. The bounded 4P stack route has 11,180 bytes minimum gap and no overlap samples. Build has no warnings; diff whitespace check passes.

Retained for the natural vulnerable-party gain despite the small protected-fixture regressions. Full 4P campaign completion and sustained 60fps in every mode remain unproven and unfinished.

### Isolated party contact scan O3 retained (2026-10-05)

After body predicate inlining, compiling only the isolated `party_contact_scan` with O3 improves the new natural 4P workload. ROM `c5a5e53f2fd8a18f8acbedf4860397857ddba9bdcc03b6b554b6b6b7d6e77fe9` replaces `3fe12cc6f6d4bea621c6c2ef3070f780963badc3be86150fff29b4340f5986dd`. Source collision logic is unchanged. Evidence: `.local/bc-party-scan-o3/verified.json`.

All 17,736 natural 4P scene states match; the partial route improves 29,804 to 29,755 frames. Round-two 1,000-call timing improves 2,129 to 2,119 frames, mean 1,517,432.448 to 1,507,905.112 core ticks. The worst sliding 1,000 advancing updates take 2,124 frames, or 28.249 updates/sec at 60Hz (previously 2,132 / 28.143). The scan grows from 954 to 1,222 bytes.

All 3,300 multiplayer fixture states and independent replays match. Round-eight 4P improves 1,284 to 1,283 frames; 3P improves 1,204 to 1,203; vulnerable round-four ties at 463. Round-six 4P regresses 1,438 to 1,442 frames despite lower average scene CPU ticks. The 40 BC openings save two frames net. The full solo route matches 160,172 states and stays 169,599 frames; its round-six profile remains 1,838 frames and 965,624.940 mean ticks. Normal's 40 timings and 40,040 state/sprite hashes are identical. Boss Rush video hashes match, with the existing 2,990/3,000 update rate, no sprite drops/remaps/fallbacks, and successful reset cleanup. All 12 Home modal cases pass. Bounded stack minimum gap is 11,162 bytes, zero overlaps. Build warnings and diff whitespace checks are clean.

Retained for the measured natural 4P benefit with the round-six tradeoff recorded. Full 4P campaign completion and sustained 60fps remain unfinished; no actors, sprites, or gameplay updates were removed.

### Natural scene-entry workload trace (2026-10-05)

Added optional `--workload-trace` to the scene-paced replay tool and native-ABI-derived actor-family occupancy to `WorkloadMetrics`. Counts are read at scene entry only during the selected profile window. They do not count immediate births or every executed actor update. On retained ROM `c5a5e53f2fd8a18f8acbedf4860397857ddba9bdcc03b6b554b6b6b7d6e77fe9`, all 17,736 scene records, all 1,000 timing rows, and function-attributed totals exactly match the untraced run. Evidence: `.local/bc-natural4p-workload/verified.json`.

Round-two 4P profile occupancy averages 22.586 active world records (maximum 31), 18.188 weapon records (maximum 29), and 43.864 submitted SAT entries (maximum 57). Segment handler `bb7e`, active state `80`, flags `00`, accounts for 12,276 of 22,586 scene-entry actor observations. This identifies round-two segment dispatch as the next optimization target; the raw counts alone do not prove equal cost per family or source fidelity. The QA-only trace does not change the ROM.

### Round-two segment direct dispatch retained (2026-10-05)

ROM `12d29a4bbd4008e8202705e8af6936fef390fb743158039e78d10152525e0bc1` replaces `c5a5e53f2fd8a18f8acbedf4860397857ddba9bdcc03b6b554b6b6b7d6e77fe9`. The general loop routes live round-two `bb7e` segment trains through the existing segment/common helper with the reusable empty child envelope, as round eight already does. Relocated bullet precedence, ordered children, motion, collision, and event delivery remain unchanged. Evidence: `.local/bc-round2-segment-direct/verified.json`.

The focused differential passes 1,000 three-pass segment cases, 61,620 ordered events, 1,500 births, and 1,500 allocation failures. All 17,736 natural 4P scene states match. That partial route saves 83 frames (29,755 to 29,672); the round-two profile improves 2,119 to 2,053 frames and mean 1,507,905.112 to 1,440,449.010 core ticks (about 4.5%). General-loop attribution falls 65,943,290 ticks across 1,000 updates. The worst contiguous 1,000 advancing updates now take 2,087 frames, approximately 28.749 updates/sec at 60Hz; this remains far below the requested speed.

Other timing is mixed: protected round-eight 4P 1,283 to 1,284; 3P 1,203 unchanged; round-six 4P 1,442 to 1,440; vulnerable round-four 463 to 464. All 3,300 fixture states and independent replays match. BC's 40 openings cost five extra frames net. Solo's 160,172 states match and its whole route improves 169,599 to 169,589 frames, while round-six profiling costs two frames (1,838 to 1,840). Normal's 40 timings and 40,040 state/sprite hashes match exactly. Boss Rush's video hashes remain identical at 2,990 updates/3,000 frames with no sprite drops/remaps/wheel fallbacks and reset cleanup passing. All 12 modal cases pass. Bounded stack gap remains 11,162 bytes with no overlap. Build warnings and diff whitespace checks are clean.

Retained for the substantial natural round-two CPU reduction and route improvement, with regressions documented. No enemy, sprite, shot, or update was removed. Sustained 60fps and natural full 4P campaign completion remain unfinished.

### Animation flip lookup rejected (2026-10-05)

Tested a native 256-word (512-byte) table replacing animation frame-bit expansion in `bc_enemy_motion`; host code retained the arithmetic reference. Candidate `59dd4af9c2e8cd0776784c3b3f9b0c632f25e822c212f9887208cc9d8cf7908d` passes all 262,144 native animation-attribute cases. All 17,736 natural 4P scene states and 1,000 protected 4P states match, and the protected replay passes. Evidence: `.local/bc-animation-flip-lookup/rejected.json`.

The natural route regresses 29,672 to 29,675 frames. Its slow round-two 1,000-call span remains 2,053 frames, with only a tiny mean CPU reduction (1,440,449.010 to 1,440,132.526 ticks). Protected R8 4P improves 1,284 to 1,281 frames. Rejected the mixed, negligible improvement; source restored and rebuilt ROM verified exactly `12d29a4bbd4008e8202705e8af6936fef390fb743158039e78d10152525e0bc1`. No production change retained. The measured result rules out this table conversion as a material solution to the remaining slowdown. Sustained 60fps and full natural 4P completion remain unfinished.

### Party body-union predicate inlining retained (2026-10-05)

ROM `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7` replaces `12d29a4bbd4008e8202705e8af6936fef390fb743158039e78d10152525e0bc1`. Inlined `party_bodies_far` into the common dispatcher. Its widened arithmetic, byte-wrapped hitbox radii, and conservative rejection are unchanged. Removing the 114-byte helper grows common code by only 78 bytes. Evidence: `.local/bc-body-union-inline/verified.json`.

All 32,000 contact-stream cases / 6,953 ordered events pass. All 17,736 natural 4P scene states match, while that partial route improves 29,672 to 29,465 frames (207 saved). Round-two 1,000-call profiling improves 2,053 to 2,039 frames and mean 1,440,449.010 to 1,418,520.789 core ticks. Worst contiguous 1,000 advancing updates improve 2,087 to 2,068 frames, about 29.014 updates/sec at 60Hz. Vulnerable round-four 4P improves 464 to 449 frames.

Protected round-eight 4P, round-eight 3P, and round-six 4P fixture timing is unchanged; all 3,300 profile states and independent replays match. All 40 BC opening timings are unchanged. Solo's 160,172 states match and its route stays 169,589 frames, with round-six profiling unchanged at 1,840 frames / 966,251.454 mean ticks. Normal's 40 timings and 40,040 state/sprite hashes match exactly. Boss Rush video hashes match, with the existing 2,990/3,000 rate, no sprite drops/remaps/wheel fallbacks, and reset cleanup passing. All 12 Home modal cases pass. Bounded stack gap remains 11,162 bytes with no overlaps. Build warnings and diff whitespace checks are clean.

Retained: measured vulnerable-party gains with no timing regressions in these comparison routes. These bounded checks do not prove whole-game 60fps or natural full 4P completion; both remain unfinished.

### Longer round-four controller prediction (2026-10-05; campaign running)

Added optional `--boss-four-lookahead` (4..16, default 4) to the host campaign pilot. It applies only at a visible round-four boss and requires real-core lookahead. No production ROM change: `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7`. The default retains prior policy; the new attempt selects 12 updates to address the prior 4P pilot's round-four loss.

Expanded the synthetic multiplayer predictor test to both four- and twelve-update horizons for each selected peer, active and inactive. It verifies unchanged authoritative RAM/CPU/VRAM/pixels and preserved other-player inputs. Eight active-peer cases pass; `.local/bc-natural4p-boss4-horizon/predictor-verified.json`. The fresh natural 4P run launches through Home with seven starting lives and real continues, recording all inputs. It uses no protection, forced defeats, health/weapon injection, or live-core snapshot restoration. Campaign evidence is pending in `campaign/`; reaching round two with all starting lives intact is not full campaign proof. Do not rebuild the release ROM while this pilot is running.

### Current round-two instruction hotspots (2026-10-05)

Generated `.local/bc-body-union-inline/current-hot-instructions.json` by mapping the retained natural 4P profile's per-PC core-tick histogram to its matching archived ELF disassembly. This is read-only analysis of ROM `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7`. The report covers the top 30 instructions in each of six hot functions. Party-contact save/restore alone attributes 5,769,120 + 6,057,576 ticks; common-task save/restore attributes 6,371,120 + 3,806,880. Projectile drawing's two leading long shifts each attribute 3,056,088 ticks, while active-shot testing/branching costs 4,044,180 + 3,624,824. These are instruction-attributed totals across the 1,000-call window, not separate frame-rate measurements. They identify remaining register-pressure and coordinate-extraction costs; no new optimization has been validated from them.

### Projectile packing eligibility rewrite rejected (2026-10-05)

Moved neighboring X extraction after triple-pack eligibility in source. Host checks match 2,400 pools, 37,177 ordered sprites, and 600 packed strips. An isolated SGDK output build (explicit `.local/.../build/rom.bin` target with `OUT_DIR` and `OUT_DIR_LIB`, omitting the release/padROM target) leaves the live campaign's release ROM untouched. Candidate `810a4d686b2e25c337b000e43f3af0b2c32f462f1c8d4253806e01057b558b7b` matches 1,000 protected 4P scene states and its independent replay.

The draw function stays 2,574 bytes. Disassembly shows that GCC already gated neighboring reads; only same-cost current-shot loads and shifts are reordered. The sample changes 1,284 to 1,283 frames with essentially equal mean ticks (852,782.021 to 852,780.712). The isolated ROM was finalized at raw 4,177,084 bytes rather than padded to release 4,194,304, so this tiny timing difference is not a retained-gain claim. Rejected the rewrite based on generated code; restored source. Release ROM remains exactly `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7`; the campaign was never rebuilt or restarted. Evidence: `.local/bc-projectile-pack-gate/rejected.json`.

### Longer-prediction 4P attempt terminal and replay verified (2026-10-05)

The run previously marked running in `.local/bc-natural4p-boss4-horizon/` is now terminal. It naturally cleared rounds one through six and lost in round seven at tick 72,512 / video frame 115,960, then returned Home after game over. Selected 4P with seven starting lives through Home; accepted two real continues (P3 at tick 33,380 and P4 at 34,544). P1/P2 exhausted in R4; P3/P4 carried the selected 4P session through R6. This does not mean four living players completed those rounds together.

The 12-update R4 prediction attempt cleared the boss that defeated the prior four-update attempt. The ROM also differs from that older run, so this is not an isolated causal measurement of prediction horizon. Entry ticks: R2 6,655; R3 14,251; R4 22,714; R5 40,056; R6 50,271; R7 60,749. Deaths: R2 one, R3 three, R4 thirty-four, R7 eight. The last loss is in the dense late-R7 enemy-shot section. No protection, forced defeats/deaths, health/weapon injection, or authoritative-core snapshot restoration.

Independent replay of all 115,960 recorded frame inputs uses zero save-state restores and exactly matches full endpoint RAM, CPU registers, VRAM and pixels. RAM SHA-256 `ac48865bb1dae309695874addaff3bef60bc9e3c86784560c0becd718f1346bf`. Evidence: `.local/bc-natural4p-boss4-horizon/verified.json`, `campaign/controller-replay.json`, both machine checkpoints, and logs. Retained ROM unchanged at `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7`. No pilot/replay process remains live. This extends natural selected-4P coverage through R6 but does not prove full campaign completion or sustained 60fps.

### Expanded natural 4P scene corpus and new slow windows (2026-10-05)

Captured the terminal R1-R6-clear / R7-game-over controller route on retained ROM `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7`. Capture exactly matches the original full RAM/CPU/VRAM/pixel checkpoint. The scene-paced replay matches all 72,529 canonical states, 5,849 bytes each including all selected peers and scores/continues. Capture uses 115,960 video frames; scene-paced replay uses 115,948, reflecting its different input-delivery timing. Future cross-ROM comparisons must use the scene-paced baseline. Evidence: `.local/bc-natural4p-six-round-corpus/verified.json`.

Expanded coverage finds a slower sustained window than the earlier 29.014 result: round three takes 2,166 video frames for 1,000 contiguous advancing updates, approximately 27.701 updates/sec at 60Hz (capture starts tick18,503; scene replay tick18,513). This changes the worst measured current-ROM result through broader coverage, not through a code regression. At tick19,019 the scene-paced 1,000-call profile takes 2,111 frames, mean 1,397,565.379 core ticks, with 993 calls above the 896,040-tick frame budget. Its biggest attributed costs are projectile drawing, weapon updates, player updates, and the general-family fallback. Active `b6c3` segment trains account for 5,518 scene-entry observations in the capture workload trace; direct dispatch is a concrete next candidate.

A separate original-input replay profiles late round four at tick26,019: 1,000 updates / 2,106 frames, mean 1,468,408.543 ticks, maximum 2,335,032, all 1,000 over budget. That complete replay again matches the original full machine endpoint. Both slow regions need to accompany the older R2 and protected fixtures when assessing future changes. No ROM changes in this work; full 4P campaign completion and sustained 60fps remain unfinished.

### Round-three segment direct dispatch retained (2026-10-05)

ROM `c91f17b50cb9c07ec654dcf80921c5b37aac50acbf2cdc1a9721e575ecb873f6` replaces `09a6f66699c3516aa20094bcdec3ef649fb1d9bb47b1d56762371824db8165a7`. Live round-three `b6c3` trains now use the existing segment/common helper and reusable child envelope in `third_actor_loop`, preserving relocated bullet precedence and ordered firing events. The loop grows 586 bytes; the fallback remains for other families. Evidence: `.local/bc-round3-segment-direct/verified.json`.

Focused differential: 1,000 three-pass pools, 61,620 ordered events, 1,500 births and 1,500 allocation failures match. The expanded natural 4P corpus matches all 72,529 gameplay states and saves 79 frames (115,948 to 115,869). Round-three 1,000-call profiling improves 2,111 to 2,056 video frames, mean 1,397,565.379 to 1,331,830.017 ticks (about 4.7%). The worst contiguous 1,000-update window now shifts to late R4 (ticks25,507–26,507): 2,146 frames / 27.959 updates/sec, versus prior R3 2,166 / 27.701.

Solo's 160,172 states match and the route saves 40 frames (169,589 to 169,549). Its R6 profile remains 1,840 frames with a tiny mean increase (966,251.454 to 966,272.055). R3 protected 2P at warm3500 saves 1,005 to 1,004 frames; 3P saves 1,038 to 1,030. Both 1,000-state comparisons and both baseline/candidate independent replays pass. Earlier R3 fixture attempts at warm12000 and warm4500 failed their expected-gameplay status assertion on both ROMs and are not counted as measurements; the valid warm3500 windows replace them.

Protected R8 4P matches 1,000 states and timing exactly (1,284 frames / 852,782.021 mean ticks), independent replay passes. All 40 BC opening timings and all 40 Normal timings are unchanged; Normal's 40,040 state/sprite hashes match. Boss Rush retains identical video hashes, 2,990/3,000 updates, no sprite drops/remaps/wheel fallbacks and successful reset cleanup. All 12 Home modal cases pass. Bounded stack minimum gap 11,162 bytes, zero overlap. Build warning and diff whitespace checks pass.

Retained for the measured R3 gains without removing actors, shots, sprites or updates. Full natural 4P campaign completion and sustained 60fps remain unfinished.

### Round-four segment direct dispatch retained (2026-10-05)

Profiled the retained R4 worst window at tick25,507 before editing: 2,145 video-frame span for 1,000 calls, 1,470,757.778 mean ticks, 988 over budget. `b7f8` trains contribute 7,263 scene-entry actor observations and the general actor loop is the largest attributed function. Full scene replay matches the established 72,529 states. Baseline evidence: `.local/bc-round4-current-profile/`.

ROM `43adf500a899169e7fc54beff63de5f13766408ea0203c7a25e56e4f60e7201a` replaces `c91f17b50cb9c07ec654dcf80921c5b37aac50acbf2cdc1a9721e575ecb873f6`. Round-four trains use the existing segment/common helper and reusable child event envelope in the general loop, extending the R2/R8 path. No actors, shots, sprites or updates are removed. Evidence: `.local/bc-round4-segment-direct/verified.json`.

The focused host differential matches 1,000 three-pass pools, 61,620 events, 1,500 births and 1,500 allocation failures. Natural 4P matches all 72,529 states and saves 182 frames (115,869 to 115,687). R4 profiling improves 2,145 to 2,093 frames and mean 1,470,757.778 to 1,432,963.259 ticks. The worst sliding 1,000 advancing updates shift back to R3 at ticks18,423–19,423: 2,097 frames / 28.612 updates/sec, versus preceding worst 2,146 / 27.959. Solo matches 160,172 states and saves 126 frames (169,549 to 169,423); R6 profile improves 1,840 to 1,838 frames with a small mean decrease.

At R4 warm3000, protected 2P improves 1,084 to 1,041 frames; 3P 1,496 to 1,277. Both 1,000-state comparisons and both before/after independent replays pass. Protected R8 4P matches all 1,000 states and timing exactly at 1,284 frames / 852,782.021 mean ticks. BC openings save five frames net across 40 cases. All 40 Normal timings and 40,040 state/sprite hashes match. Boss Rush video hashes match at its existing 2,990/3,000 rate, no drops/remaps/wheel fallbacks, reset cleanup passes. All 12 Home modal cases pass. Bounded stack gap 11,162 bytes, zero overlaps. Build warning and diff whitespace checks pass.

Retained. Full natural 4P campaign completion and sustained 60fps remain unfinished; these bounded improvements do not establish whole-game speed.

### Weapon-kind workload trace (2026-10-05)

Added native-ABI-derived shot-kind offsets and read-only per-player weapon-family occupancy to the optional scene workload trace. On ROM `43adf500a899169e7fc54beff63de5f13766408ea0203c7a25e56e4f60e7201a`, the entire 72,529-scene record, including all gameplay hashes and start/end video frames, exactly matches the untraced R4-direct baseline. Each sample's family totals equal the independently counted active records per player. Evidence: `.local/bc-weapon-workload/verified.json` and `replay/`. No ROM changes.

The current R3 worst window at tick18,423 has 24,651 scene-entry weapon observations: 7,251 live expanding shots, 6,193 dying expanding shots, 3,356 live straight shots, 2,506 dying straight shots, 3,345 live returning shots, and 2,000 options. No beams occur. Dying straight/expanding records account for 8,699 / 24,651 (35.3%); these are occupancy counts, not executed task counts, and dying status alone does not prove that velocity has already been zeroed. The 1,000 complete scene calls span 2,096 video frames (the inclusive sliding-window convention is 2,097), average 1,403,431.435 ticks, 991 over budget. This points the next weapon optimization toward impact/stationary ordinary-shot work rather than beam dispatch. Existing animation, motion bounds and slot-retirement order must be preserved. Full natural 4P completion and sustained 60fps remain unfinished.

### Stationary ordinary-shot motion branch rejected (2026-10-05)

Tested a zero-X/Y-velocity branch in `bc_shot_step` that calls `beam_axis` with constant zero, preserving masking, old high-byte carry in bounds, and X-before-Y retirement. Candidate `b46bb8076137e9e08240d7346d203ec3c663237265aa13895fbe5ce7a07ebc51` passes 60,000 complete weapon-pool updates, 6,000 charge/launch edge cases and 20,000 stationary boundary cases (including 32-bit padding and wrapped coordinates). All 72,529 natural 4P gameplay states match, as do 1,000 protected R8 states and independent replay.

Rejected on timing: natural route worsens 115,687 to 116,127 frames (+440). R3 tick18,423 profile worsens 2,096 to 2,099 frames and mean 1,403,431.435 to 1,409,749.579 ticks. Protected R8 saves one video frame (1,284 to 1,283) but mean CPU also increases, 852,782.021 to 853,318.970. Explicitly branching for zero velocities does not pay for itself in this implementation. Source restored and rebuilt ROM verified exactly `43adf500a899169e7fc54beff63de5f13766408ea0203c7a25e56e4f60e7201a`. Evidence: `.local/bc-stationary-shot-motion/rejected.json`, differential script/log, before/candidate archives and timing outputs. No production change retained; full campaign and 60fps goals remain unfinished.

### Unowned ordinary-shot tail dispatch rejected (2026-10-05)

Candidate `2772b4ba7178d1652e585a7e28c1b1780185285016843e57acd28a054ab0d3fe` outlined ordinary-shot updates and tried an early return for unowned shots to avoid retaining the weapon pool for ownership retirement. Host differential passes 60,000 full-pool updates, 6,000 charge edges and 20,000 stationary boundary cases. All 72,529 natural 4P states and 1,000 protected R8 states match; independent protected replay passes.

Rejected: natural route worsens 115,687 to 117,838 frames (+2,151). Same R3 window worsens 2,096 to 2,126 frames, mean 1,403,431.435 to 1,445,984.309 ticks. Protected R8 worsens 1,284 to 1,300 frames, mean 852,782.021 to 856,226.182. Restored source and rebuilt ROM verified exactly `43adf500a899169e7fc54beff63de5f13766408ea0203c7a25e56e4f60e7201a`. Evidence: `.local/bc-unowned-shot-tail/rejected.json`. All candidate processes terminal before rebuilding. No production change retained. Worst retained sustained measured window remains 28.612 updates/sec; full natural 4P completion and 60fps remain unfinished.

### Live weapon dispatcher inlining retained with measured tradeoffs (2026-10-05)

ROM `0af22385e2f59d0973cb34c498927320f70af0ef4146902f7390d6885f8dc45b` replaces `43adf500a899169e7fc54beff63de5f13766408ea0203c7a25e56e4f60e7201a`. The existing live-slot dispatcher is always-inline, keeping repeated frame arguments in its caller. Task semantics, source slot order, actors, shots, drawing and update scheduling remain unchanged. This removes the 2,430-byte outlined dispatcher and grows integrated player code from 6,372 to 8,606 bytes. Evidence: `.local/bc-weapon-dispatch-inline/verified.json` and full before/candidate archives.

Host differential passes 60,000 full-pool updates, 6,000 charge edges and 20,000 stationary boundary cases. Expanded natural 4P replay preserves all 72,529 states and improves 115,687 to 114,244 frames (1,443 saved). Its R3 profile at tick18,423 improves 2,096 to 2,066 frames, mean 1,403,431.435 to 1,367,360.001 ticks. The worst inclusive sliding 1,000-update window is now 2,069 frames / 28.9995 updates/sec at ticks18,522–19,522, compared with prior 2,097 / 28.6123. Solo preserves all 160,172 states and improves 169,423 to 168,508 frames; R6 profile 1,838 to 1,760 frames, mean 966,057.89 to 941,433.899.

Explicit regressions: protected R8 4P worsens 1,284 to 1,313 frames / 1,000 updates, mean 852,782.021 to 862,274.385 ticks, with all states matching and independent replay passing. Of 40 BC opening samples, 14 regress and 26 tie, costing 85 frames net; all ten 4P openings regress. These remain follow-up workloads. Retained for the longer natural-route and worst-window gains, not as a universal speed improvement.

All 40 Normal timings and 40,040 state/sprite hashes match. Boss Rush retains identical 3,000 video hashes and 2,990 updates, zero drops/remaps/wheel fallbacks, successful reset cleanup. All 12 modal cases pass. Protected R8 4P 3,000-update stack check has 11,162-byte minimum gap and zero overlaps. Final comment-only rebuild reproduces the tested ROM exactly; warning and diff checks pass. All test processes terminal. Full natural 4P completion and sustained 60fps / 100% speed remain unfinished.

### Projectile hardware flip submission retained (2026-10-05)

ROM `f7eec400df4bdf1c8a903d4507fd23a58612c1961ae89f0caa2d6afc06d8ba88` replaces `0af22385e2f59d0973cb34c498927320f70af0ef4146902f7390d6885f8dc45b`. Single projectiles submit prepared Genesis SAT flip bits through the existing sprite backend, avoiding conversion to logical flags and back. Source horizontal bit 0x0800 stays at SAT bit 11; source vertical bit 0x8000 moves to SAT bit 12. All three directional beam art frames suppress flips. The packed-triple path and public art mapper are unchanged. Evidence: `.local/bc-projectile-hardware-flips/verified.json`.

Expanded natural 4P replay matches all 72,529 gameplay states and improves 114,244 to 113,772 frames (472 saved). R3 tick18,423 profile improves 2,066 to 2,056 frames, mean 1,367,360.001 to 1,357,915.097 ticks. Projectile drawing attribution falls 181,269,564 to 172,021,332 ticks (about 5.1% of this renderer). The worst sliding 1,000-update window takes 2,060 frames / 29.1262 updates/sec at ticks18,522–19,522, versus prior 2,069 / 28.9995. Solo matches all 160,172 states and improves 168,508 to 168,301 frames; its R6 profile improves 1,760 to 1,744 frames, mean 941,433.899 to 935,480.455.

Protected R8 4P matches 1,000 states and independent replay, improving 1,313 to 1,308 frames, although mean scene CPU slightly increases 862,274.385 to 862,340.059 ticks. Across 40 BC openings, nine improve, 29 tie and two regress by one frame each, saving 13 frames net. All 40 Normal timings and 40,040 state/sprite hashes remain identical; Boss Rush retains identical 3,000 video hashes, 2,990 updates, zero drops/remaps/wheel fallbacks and reset cleanup. All 12 Home modal cases pass; bounded stack gap 11,162 bytes, zero overlaps. Build warning and diff checks pass.

Updated the host renderer fixture to model SAT bit positions and reject unrelated bits: 2,400 pools / 37,177 ordered sprites / 600 strips pass. New `qa_bc_projectile_bits_native.py` compiles the production renderer in a scratch 68000 cartridge with a submission-capture backend. All 65,536 attributes across nine frame choices pass (589,824 cases), covering all three beam frames, facing changes, missing art, exact flip submissions and unchanged attributes/coordinates. This checks renderer submissions, not framebuffer pixels or hardware scanline visibility. Its initial scratch counter variables were incorrectly linked into ROM; they were moved to explicit RAM before the passing run.

A preliminary candidate incorrectly passed source vertical bit 0x8000 through unchanged. It was caught in code review, its natural replay deliberately terminated, and all outputs moved to `incorrect-preliminary/` with an INVALID marker. None of those outputs count as verification. The corrected source and host backend were rebuilt before the valid measurements above. All processes are terminal. Full natural 4P campaign completion and sustained 60fps / 100% speed remain unfinished.

### Vulnerable-party shot union inlining retained (2026-10-05)

ROM `ff9fa32ec251e96d9ebe7ecaeeb4260ed6103ffd37bc84cc7caf4ef8441ae9b8` replaces `f7eec400df4bdf1c8a903d4507fd23a58612c1961ae89f0caa2d6afc06d8ba88`. `party_shots_far` is now always-inline at its existing call sites. Bounds arithmetic, cached-index rules, player order and collision behavior are unchanged. The removed helper is 104 bytes; common entry grows 62 bytes and detailed contact scan grows 42 bytes. Evidence: `.local/bc-shot-union-inline/verified.json`.

The host comparison passes 32,000 cached/uncached 1P/2P/3P/4P cases with 6,953 ordered events, including bounds, empty/protected parties, clocks, boss health, deaths, pickups and options. Natural 4P replay preserves 72,529 states and improves 113,772 to 113,247 frames (525 saved). R3 tick18,423 profile improves 2,056 to 2,043 frames, mean 1,357,915.097 to 1,341,663.848 ticks. Worst sliding 1,000 advancing updates now take 2,048 frames / 29.296875 updates/sec at ticks18,522–19,522, versus prior 2,060 / 29.1262.

Tradeoffs remain explicit: solo's 160,172 states match but total frames worsen 168,301 to 168,355 (+54); R6 profile remains 1,744 frames, mean 935,480.455 to 936,392.233. Protected R8 4P preserves 1,000 states and independent replay but costs one frame, 1,308 to 1,309, mean 862,340.059 to 862,597.841. Forty BC openings have one improvement, 31 ties and eight regressions, costing 16 frames net. Retained for the larger natural 4P and worst-window gains; this is not an across-the-board speed improvement.

All 40 Normal timings and 40,040 state/sprite hashes match. Boss Rush retains identical 3,000 video hashes / 2,990 updates, zero drops/remaps/wheel fallbacks and reset cleanup. All 12 Home modal cases pass. Protected 4P stack gap remains 11,162 bytes with zero overlaps. Build warnings and diff checks pass; all processes terminal. Full natural 4P completion and sustained 60fps / 100% speed remain unfinished.

Read-only follow-up evidence `player-cost-baseline.json` maps the previous matching ROM/ELF and R3 instruction histogram. The inlined weapon traversal's group-end compare accounts for 5,105,898 ticks, stack-based group-end addition 4,480,000, live-slot test 3,685,248; separate coordinate shifts are also high. This identifies loop bookkeeping and motion arithmetic as next targets; no such transformation is included in this retained change.

### Occupied weapon-group counter retained (2026-10-05)

ROM `23a6fad30fc92fcc6ce72d53254c313bc5d62cae0104cbe0c3601103a6857c1f` replaces `ff9fa32ec251e96d9ebe7ecaeeb4260ed6103ffd37bc84cc7caf4ef8441ae9b8`. Occupied six-slot groups use a local unsigned countdown rather than a source-level end pointer. Each slot is still re-read and updated in source order; empty groups, births and retirement behavior are unchanged. GCC converts the countdown back to a pointer comparison, but keeps the inner bound in D0 rather than repeatedly loading it from the stack. Integrated player code grows from 8,606 to 9,194 bytes; its local frame shrinks 212 to 208 bytes. Evidence: `.local/bc-weapon-group-counter/verified.json`.

Differential tests pass 60,000 complete weapon-pool updates/events, 6,000 charge edges and 20,000 stationary boundary cases. Natural 4P matches all 72,529 gameplay states and improves 113,247 to 113,187 frames (60 saved). The profiled R3 window costs one additional frame (2,043 to 2,044) while mean CPU falls slightly, 1,341,663.848 to 1,341,432.463. The worst inclusive sliding window also costs one frame, 2,048 to 2,049 at ticks18,522–19,522: 29.2826 updates/sec instead of 29.296875. No worst-case speed improvement is claimed.

Solo matches 160,172 states and improves 168,355 to 168,344 total frames; its R6 profile costs one frame, 1,744 to 1,745, with essentially unchanged CPU. Protected R8 4P improves 1,309 to 1,305 frames, mean 862,597.841 to 860,819.169, with 1,000 states and independent replay matching. BC openings improve in ten cases, tie in 29 and regress by one frame in one, saving 25 frames net. Retained as a small overall route/opening/R8 gain, with profiled-window regressions explicitly preserved.

All 40 Normal timings and 40,040 state/sprite hashes match. Boss Rush retains identical 3,000 video hashes and 2,990 updates, zero drops/remaps/wheel fallbacks, reset cleanup. All 12 Home modal cases pass. Bounded stack gap 11,162 bytes, zero overlaps. Build warning and diff checks pass; all processes terminal. Full natural 4P completion and sustained 60fps / 100% speed remain unfinished.

### Native projectile bound extraction retained (2026-10-05)

ROM `c5e38c42c448a0300d03673e72ec464ed13316090f375090168c4de984e991f7` replaces `23a6fad30fc92fcc6ce72d53254c313bc5d62cae0104cbe0c3601103a6857c1f`. The native `beam_axis` offscreen bound uses one longword rotate followed by word extraction/addition instead of separate shifts for integer position and carry. The complete carry/padding byte, 24-bit stored position, 16-bit bound wrap and X-before-Y task behavior remain unchanged. Non-68000 callers retain the original C expression. Evidence: `.local/bc-motion-bound-rotate/verified.json`.

Added reusable `tools/qa_bc_motion_bound_native.py`, which extracts the production helper into a scratch 68000 cartridge and compares it against the original arithmetic. All 65,536 signed velocities at 20 fractional/boundary/padded positions pass: 1,310,720 native cases, including full 32-bit addition wrap. The initial expanded scratch array caused GCC to request unavailable memcpy; making that immutable array static const fixed the standalone harness before its passing run. Host checks also pass 60,000 full-pool updates, 6,000 charge edges and 20,000 stationary boundary cases.

Natural 4P preserves all 72,529 states and improves 113,187 to 112,953 frames (234 saved). R3 tick18,423 profile improves 2,044 to 2,038 frames, mean 1,341,432.463 to 1,336,997.865 ticks. The worst inclusive sliding 1,000-update window takes 2,044 frames at ticks18,522–19,522, approximately 29.3542 updates/sec versus 29.2826. Solo preserves all 160,172 states and improves 168,344 to 168,237 frames; R6 profile improves 1,745 to 1,734, mean 936,392.534 to 933,455.334.

Charged R8 4P was measured on both archived baseline and candidate: 1,253 to 1,251 frames, mean 779,215.136 to 778,485.288, all 1,000 states match and both independent replays pass. Ordinary protected R8 matches 1,000 states and independent replay; it costs one display frame (1,305 to 1,306) despite slightly lower mean CPU (860,819.169 to 860,480.502). Forty BC openings have six improvements and 34 ties, saving nine frames with no regressions.

All 40 Normal timings and 40,040 state/sprite hashes match. Boss Rush retains identical 3,000 video hashes / 2,990 updates, zero drops/remaps/wheel fallbacks and reset cleanup. All 12 Home modal cases pass. Bounded stack gap remains 11,162 bytes, zero overlaps. Build warning and diff checks pass; all processes terminal. Full natural 4P completion and sustained 60fps / 100% speed remain unfinished.

### Word-aligned projectile layout prototype (2026-10-05; not integrated)

Investigated a larger representation change after the incremental instruction work. The isolated native prototype rotates the complete 32-bit projectile position left eight bits: integer pixels become the aligned high word, fraction occupies bits8–15, and the original high padding byte remains in bits0–7. This is invertible even for dirty padding and avoids discarding behavior relevant to source bounds. Production code/ROM remain exactly `c5e38c42c448a0300d03673e72ec464ed13316090f375090168c4de984e991f7`.

Compiled and executed `.local/bc-shot-layout-prototype/probe.py` on the hash-pinned 68000 core. All 1,310,720 cases compare the current production helper, two aligned alternatives and the original arithmetic; every signed velocity at 20 fractional/boundary/padded positions matches final position and offscreen result. Integer-coordinate reads match too. Instruction counters confirm 1,310,720 calls to each of the five measured functions. Evidence: `result.json`, generated C/ELF/ROM, and log in that directory.

The first ADDX version needs a third data register and its saved-register cost makes it slower: 1,322.273 versus 1,252.273 mean attributed core ticks per helper call. A two-register branch version folds the carry into the retained padding byte before clearing it and averages 1,174.838 (about 6.18% lower). Aligned integer reads average 280 versus 476 ticks (41.18% lower). These are noinline callee costs, including their own prologues/returns and excluding caller setup, conversion overhead and game integration. They are not whole-game speed evidence and do not establish that the integrated layout will win. The first prototype and results are preserved separately.

Source audit identifies production consumers in `bc_rules.c`, both projectile render files, and `bc_robot_preview.c`. Packed-triple Y comparison is a critical constraint: its existing `y >> 8` equality includes the old padding byte, so replacing it with only a 16-bit integer getter would alter grouping. The equivalent rotated mask is 0xffff00ff. Births, option low-X masking, index eligibility and all canonical QA readers also need exact transformations. `result.json` records the integration contracts. Native record strides can stay unchanged; canonical readers must inverse-rotate every shot coordinate using each ROM's matching archived header and independently validate that normalization before cross-ROM state comparison.

This prototype makes a larger optimization concrete and testable; it is not yet a production change. Current worst measured production 4P window remains 29.3542 updates/sec. Full natural 4P completion and sustained 60fps / 100% speed remain unfinished.

### Word-aligned projectile layout retained (2026-10-05)

ROM `ae81fbb69601df7c3e1397335c643a8f32dc818ba6af893de872f742dad6cbdc` replaces `c5e38c42c448a0300d03673e72ec464ed13316090f375090168c4de984e991f7`. Native BcBeam positions rotate the entire original 32-bit container left eight bits, providing aligned integer-word reads while retaining fraction and dirty padding. Robot and enemy coordinates do not change. Shot/player strides remain 32/1024 bytes. The two-register carry branch preserves full source arithmetic, including padding carry, bound wrap and X-before-Y retirement. Packed-triple Y equality retains the padding byte. Host reference layout remains original unless explicitly compiled with BC_TEST_ALIGNED_BEAMS.

Evidence: `.local/bc-shot-layout-integrated/verified.json`, archived source/headers/tools/ELF/ROM and individual test logs. Canonical replay readers independently inverse-rotate all 30 projectile coordinate pairs; no additional bytes are excluded. Archived profiles require matching headers or explicit layouts. Decoder validation passes 2,000 random complete records and 8,192 single-bit mutations; scene coverage passes 964 mutations. Differential checks pass 60,000 pool updates/events, 6,000 charge edges and 20,000 stationary boundary cases. Native tests pass 1,310,720 motion cases, 4,096 complete shot indices and 589,824 renderer flip/pixel cases. Independent old/new renderer comparison passes 2,400 pools, 37,527 ordered sprites and 600 packed strips with dirty padding; default host reference tests also pass. All 11 native robot/projectile preview images match pixels (bounded preview evidence, not full campaign video).

Natural selected-4P replay matches all 72,529 canonical states and improves 112,953 to 111,480 display frames. R3 profile improves 2,038 to 2,022 frames, mean 1,336,997.865 to 1,310,769.950 core ticks. Worst inclusive 1,000-update window shifts to R2 ticks11,305–12,305: 2,033 display frames, 29.5130 updates/sec. Solo matches all 160,172 states and improves 168,237 to 167,687 frames; R6 profile 1,734 to 1,664. Protected R8 4P improves 1,306 to 1,292 frames, charged R8 1,251 to 1,242; both match 1,000 states and independent replays. BC40 openings save 40 frames net: 11 improvements, 26 ties, three regressions (R4 3P +1, R5 4P +1, R8 3P +3).

All 40 Normal timings and state/sprite hash sequences match. Boss Rush retains identical video hashes, 2,990 updates/3,000 frames, no drops/remaps/wheel fallbacks and reset cleanup. All 12 Home mode/player modal cases pass. Bounded stack gap is 11,184 bytes with no overlaps. Build warnings and diff checks pass. Full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished. The next profile targets the newly slowest R2 window.

### Current worst-window R2 attribution (2026-10-05)

Read-only profile of retained ROM `ae81fbb69601df7c3e1397335c643a8f32dc818ba6af893de872f742dad6cbdc`: `.local/bc-aligned-r2-profile/verified.json`, `profile.json`, `hot-instructions.json`, matching ROM/ELF/headers. The process completed successfully; its entire 72,529-state / 111,480-frame scene record is identical to the retained integration record. Production code/ROM did not change.

Ticks11,305–12,305 take 2,033 inclusive display frames (29.5130 updates/sec). Mean complete-scene cost is 1,393,045.269 core ticks against an 896,040 frame budget; all 1,000 calls exceed budget, maximum 2,073,309. These costs exclude outer input/VBlank/DMA work. Attributed instruction time: actor common 15.60%, player/weapon update 15.50%, general actor loop 13.60%, actor drawing 9.33%, party contact scan 8.93%, projectile drawing 8.08%. Function costs include inlined callees.

Scene-entry means are 25.507 world records and 15.808 weapon records. Dominant actor occupancies include live segment bb7e (7,837), turret b9d2 (4,854), canonical projectile 884a (4,270) and ceiling be24 (3,398). These are occupancy sums, not executed-task counts. The general loop repeatedly dispatches using dynamic data->round, unlike the existing constant-round eighth loop. A measured round-two specialization is the next candidate; it must preserve every task, birth, contact and event order. No performance improvement is claimed by this profiling-only follow-up. Sustained full speed and a full natural 4P campaign remain incomplete.

### Round-two constant-loop trial rejected (2026-10-05)

Measured the R2 profiling candidate in `.local/bc-round2-constant-loop/rejected.json`. A direct constant-round clone and then a separately outlined fallback exceeded the 4 MiB cartridge window; neither oversized variant was used for timing. A shared no-clone fallback fit, preserving the general loop's effect filtering and the existing R3/R10 unconditional sink contract via an explicit flag. Candidate ROM was `f5c6e3073bfaa9d8fefb7086cc14684201816e8088e396fabb0f6c355e38911a`. The host compiler ignored the native-only noclone attribute with a warning; native build itself was warning-free. No candidate changes remain.

Host differential passed 1,000 three-pass segment cases, 61,620 ordered events, 1,500 child births and 1,500 allocation failures. Both full canonical corpora matched (72,529 selected-4P states and 160,172 solo states). Nevertheless, natural 4P worsened 111,480 to 111,680 frames, solo 167,687 to 167,881. The targeted R2 profile worsened 2,032 to 2,046 frame span and mean 1,393,045.269 to 1,433,310.480 core ticks. Its inclusive worst window becomes 2,047 frames / 29.3112 updates/sec versus retained 2,033 / 29.5130. These route and worst-window regressions reject the approach despite R8 4P improving 1,292 to 1,279 with matching 1,000 states and independent replay; solo R6 profile also improved 1,664 to 1,638.

BC40 openings save 11 frames net (7 improvements, 28 ties, 5 regressions), including +8 at R2 4P. Normal40 timings/state/sprite hashes match; Rush video hashes match with 2,990/3,000 updates, no drops/remaps/fallbacks and reset cleanup. Home12 passes; bounded stack gap 11,082, no overlaps. All processes terminal before restoration. Rebuilt retained source and verified exact restored ROM `ae81fbb69601df7c3e1397335c643a8f32dc818ba6af893de872f742dad6cbdc`.

The next candidate is a targeted R2 turret common path (b9d2; 4,854 scene-entry occupancies in the slow window) rather than cloning the whole dispatcher. It must retain the RNG cadence, three-shot birth order, immediate child updates, count increments and complete event/sink contract. This trial provides no retained speed gain; full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Direct R2 turret path retained (2026-10-05)

ROM `d366fc75703fc507e16465a4b913f97331d3a77b929111a23f814a6596c324ed` replaces `ae81fbb69601df7c3e1397335c643a8f32dc818ba6af893de872f742dad6cbdc`. The actor loop dispatches live R2 b9d2 turrets directly to the shared turret preparation/common task after scrolling. The direct path requires the actual resource relocation -535 and non-null RNG; custom layouts retain general-dispatch precedence. The original turret branch uses the same extracted preparation code. The new helper initializes the complete valid event envelope, preserves RNG cadence, one limit check for the whole three-shot burst, allocation order, immediate child updates and count increments. Source changes are confined to bc_world.c, bc_runtime.c and bc_world.h; sprites, waves and actor counts are unchanged.

Evidence: `.local/bc-round2-turret-direct/verified.json`, archived before/candidate source and headers, ROM/ELF/symbols, local independent baseline differential harnesses and native traces. Standard host comparison passes 1,000 three-pass turret pools, 62,501 ordered events, 1,494 child births and 1,812 failed allocations. Additional boundary/near-limit comparison passes 1,500 three-pass pools, 90,465 events, 294 births and 912 failed allocations, covering X outside the visible byte and Y15/16/223/224/65535 with initial limited count7. Complete actor/player/count/RNG states and valid event fields match independently compiled pre-change dispatch.

Natural selected-4P preserves all 72,529 canonical states and improves 111,480 to 111,417 frames (63 saved). R2 ticks11,305–12,305 improve 2,032 to 2,028 non-inclusive frame span (2,033 to 2,029 inclusive); mean complete-scene cost falls 1,393,045.269 to 1,369,311.167 core ticks. The worst inclusive 1,000-update window moves to R4 ticks25,998–26,998, still 2,033 frames / 29.5130 updates/sec. No overall worst-rate gain is claimed. Solo preserves all 160,172 states but regresses by three total frames, 167,687 to 167,690; R6 profile improves 1,664 to 1,661, mean 919,439.066 to 919,299.451.

Protected R8 4P improves 1,292 to 1,289 frames despite slightly higher mean CPU (854,524.111 to 854,584.766). Charged R8 improves 1,242 to 1,241, mean 771,264.515 to 771,236.900. Both preserve 1,000 states and pass independent replay. BC40 openings save seven frames net: three improvements, 35 ties, two regressions (R6 3P +2; R9 4P +1). Retained for the targeted R2 and 4P route gains with these small tradeoffs recorded.

All 40 Normal state/sprite hash sequences match. Normal 2P section5 saves one frame (1,003 to 1,002); 4P section3 costs one (1,039 to 1,040); remaining timings match. Rush video hashes remain identical, 2,990/3,000 updates, zero drops/remaps/wheel fallbacks and reset cleanup. All Home12 modal cases pass. Bounded stack gap 11,180 bytes, zero overlaps. Native builds are warning-free; formatting-only rebuild is byte-identical; diff check passes; all jobs terminal. The next profile should target the new R4 window at tick25,998. Full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Current worst R4 profile and aligned zero-velocity trial (2026-10-05)

Read-only `.local/bc-turret-r4-profile/verified.json` profiles retained ROM d366fc75 at ticks25,998–26,998. The complete scene record matches the prior 72,529-state / 111,417-frame record exactly. All 1,000 measured calls exceed the 896,040 core-tick budget; mean 1,335,322.989 and maximum 2,169,580. Inclusive span is 2,033 display frames / 29.5130 updates/sec. Attributed instruction shares: player/weapon update 19.07%, actor common 13.81%, projectile draw 11.44%, general actor loop 10.52%, actor draw 8.79%, party contact scan 8.00%. Function attribution includes inlined callees and excludes outer input/VBlank/DMA. Dominant actor occupancy is the already-direct R4 b7f8 segment train (10,271 scene-entry samples). Weapon occupancies include 6,607 live and 4,451 dying expanding shots, 4,819 returning shots and 3,433 live straight shots; these counts are not executed tasks or zero-velocity measurements.

Revisited zero-velocity motion specifically for the new rotated projectile layout, not the older original-storage experiment. The native branch clears retained padding and computes the exact source bound even when velocity is zero; it bypasses only the shift/add/carry work. Candidate `1d4b1ed9bda5ad2d9fc0a1096ce5bed528b0de43ccf6e57fc16f05793baa5611` passes 1,310,720 native boundary/velocity/padding comparisons. Evidence, source/ROM archive and copied scratch probe: `.local/bc-aligned-stationary-motion/rejected.json`.

All 72,529 selected-4P and 160,172 solo canonical states match, but natural 4P worsens 111,417 to 111,540 frames and solo 167,690 to 167,747. R4 mean CPU increases 1,335,322.989 to 1,337,260.939 with unchanged 2,032 non-inclusive span; worst inclusive window remains 2,033. Solo R6 profile worsens 1,661 to 1,680 frames. Protected R8 4P remains 1,289 frames while mean rises 854,584.766 to 854,790.419, matching 1,000 states and independent replay. BC40 saves one frame net (three improvements, 36 ties, one +2 regression). Rejected on the longer route/CPU evidence; no additional Normal/Rush/Home gates were needed to reject it.

All jobs completed before restoring the prior source. Rebuild verifies exact retained ROM `d366fc75703fc507e16465a4b913f97331d3a77b929111a23f814a6596c324ed`; no production change remains from this experiment. A next candidate is per-slot projectile artwork selection caching: unlike the previously rejected mapping tables, it would reuse a validated unchanged pose between animation updates, while refreshing positions and preserving grouping/submission order. This is only a candidate, not an implemented or measured gain. Full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Projectile pose cache and native bound-register trials rejected (2026-10-05)

A four-pool, 30-slot artwork cache retained source frame/facing, mapped tile key and visibility/beam flags, while reading positions/attributes live and retaining strip grouping and ordered submissions. Cache hits did not imply VRAM residency. `.local/bc-projectile-pose-cache/rejected.json` archives ROM `90e6671b34da58d9fc5d02232156f8bda7cafdb4096925dc1de8ba23e091effc`, source and probes. It passed 2,400 randomized pools / 37,527 ordered sprites / 600 strips, plus 1,200 persistent-pool draws covering live position/flip changes, beam facing, unknown/inactive slots and seven-owner replacement. All 589,824 native renderer flip/pixel cases passed. Both canonical corpora matched (72,529 selected-4P and 160,172 solo states).

Nevertheless, cache timing regressed: natural 4P 111,417 to 112,792 frames; solo 167,690 to 167,742; R4 span 2,032 to 2,033, mean 1,335,322.989 to 1,348,256.896. R8 4P worsened 1,289 to 1,316 frames, mean 854,584.766 to 864,495.744 with matching state/replay. BC40 cost 79 extra frames. The cache is removed; no caching benefit is claimed.

A subsequent bound-register trial initially had an invalid build comparison: Python copy2 restored the renderer source's old modification time, so make reused the rejected cache object. The linked symbols still contained pool_poses/next_pool. That mixed ROM `4ccc20d6db42d82d8d9d5d0850def82e32c97ff6dc1fbb79b640d79a2221a5d3` and its measurements are isolated in `.local/bc-beam-word-bound-mixed/invalid-comparison.json`, not used to attribute bound-only performance. Its archived renderer source was corrected to the actually linked cache source; the intended restored source is saved separately. Touching the restored renderer forced recompilation, and symbol absence was verified before all fresh bound-only measurements. Future restoration must force the affected object rebuild or verify an exact baseline ROM hash.

The valid bound-only ROM `b0506ec86fb34b807e79a5844178daba5cd55e26e7d981f114135e26a592fe66` uses swap/add.w/swap to add integer position into the existing carry register, avoiding C's extra coordinate temporary. All 1,310,720 native velocity/bound/padding cases pass. `.local/bc-beam-word-bound/rejected.json` records fresh measurements and archives. Both corpora match. Natural 4P worsens 111,417 to 111,457 frames despite R4 span improving 2,032 to 2,031; mean R4 CPU rises to 1,336,160.896. Solo improves eight frames, 167,690 to 167,682. R8 costs three frames (1,289 to 1,292), with essentially unchanged mean CPU. BC40 has 39 ties and one +1 regression. All Normal40 timings/state/sprite hashes, Rush video hashes/2,990 updates, Home12 and bounded stack (11,180-byte gap, no overlaps) pass. Rejected because the longer multiplayer route regresses.

After all processes completed, rebuilding the restored sources verified exact retained ROM `d366fc75703fc507e16465a4b913f97331d3a77b929111a23f814a6596c324ed` and absence of cache symbols. Diff check passes. No production change remains from either trial.

### Position-only returning-shot prototype (2026-10-05; not integrated)

Inspection found bc_return_step discards both beam_axis boundary results. An isolated helper computes `(stored + ((unsigned int)velocity << 8)) & 0xffffff00` in the rotated layout. This equals the rotated low 24-bit source sum: old source padding cannot affect those low 24 bits, and no boundary carry is needed when its result is unused. `.local/bc-unbounded-beam-prototype/verified.json` and scratch C/ELF/ROM preserve 1,310,720 passing native position comparisons, every signed velocity at 20 full-container edge/padding positions, against original arithmetic and the bounded helper. Initial harness launch lacked the tools import path; adding it allowed the complete native run.

This prototype provides correctness evidence for a targeted returning-shot optimization, not integrated performance evidence. Other weapon families must keep full bounds and X-before-Y retirement. It is the next integration candidate. Worst retained measured window remains 29.5130 updates/sec; full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Returning-shot position-only motion retained (2026-10-05)

ROM `8e6e72bc8aa62537269576260975bd5463613acc3eb63232189d4bfd3d73cabf` replaces `d366fc75703fc507e16465a4b913f97331d3a77b929111a23f814a6596c324ed`. Only bc_return_step's two discarded-boundary calls change to beam_move. The helper preserves the full low-24-bit position result and padding clearing, using addition/mask in the rotated native representation and original host representation. All other families retain beam_axis and their ordered X/Y retirement checks. No new RAM, record layout, artwork or wave changes. Evidence: `.local/bc-return-position-only/verified.json`, before/candidate source/ROM/ELF/headers and native scratch probe.

Extended reusable tools/qa_bc_motion_bound_native.py to detect and check the production position-only helper when present, alongside the original bound comparison. All 1,310,720 cases match both motion paths: every signed velocity at 20 full-container fractional/boundary/padding positions. Independent archived-source host comparison passes 60,000 complete weapon-pool updates/events, 6,000 charge edges and 20,000 stationary boundary cases, with canonical layout conversion preserving every byte. The artifact archive includes the updated QA source.

Natural selected-4P matches all 72,529 states and saves 38 display frames, 111,417 to 111,379. Solo matches all 160,172 states and saves 37, 167,690 to 167,653. R4 ticks25,998–26,998 mean CPU falls 1,335,322.989 to 1,334,104.093, but non-inclusive span costs one frame (2,032 to 2,033). Worst inclusive window remains at the same ticks and costs 2,034 rather than 2,033 display frames: 29.4985 rather than 29.5130 updates/sec. Solo R6 profile also costs two frames (1,661 to 1,663) with mean essentially unchanged (919,299.451 to 919,311.708). Retained as a small improvement in both full recorded routes, with the bounded-window regressions explicit; no worst-rate improvement is claimed.

Protected R8 4P remains exactly 1,289 frames / mean854,584.766; charged remains 1,241 / mean771,236.900. Both preserve 1,000 states and independent replay. All BC40 opening timings tie. Normal40 timings/state/sprite hash sequences match; Rush video hashes match, 2,990/3,000 updates, no drops/remaps/wheel fallbacks and reset cleanup. Home12 passes. Bounded stack gap remains 11,180 bytes with no overlaps. Native build is warning-free, no rejected pose-cache symbols are present, diff check passes and all jobs are terminal.

A next candidate is the option task's explicit flags&2 case: its boundary results cannot retire the option, so the verified position-only helper may avoid that unused work while retaining the ordinary bounded path for other flags. This has not been implemented or measured. Full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Option position-only motion retained (2026-10-05)

ROM `6cfe3b95ba6be4146fe1ce9e6be85c400c748e5b72c9e31b2f36324001626f7b` replaces `8e6e72bc8aa62537269576260975bd5463613acc3eb63232189d4bfd3d73cabf`. After its normal state/animation/trail work, bc_option_step uses the already-native-validated beam_move for both axes only when flags&2 makes both offscreen results irrelevant. Other flag values retain the bounded X-before-Y path. Both branches preserve position wrapping and padding clearing. This removes unused computation, not updates, contacts or actors. Only production bc_rules.c changes. Evidence: `.local/bc-option-position-only/verified.json`, archived source/ROM/ELF/headers and differential harnesses.

The archived-source comparison passes 60,000 complete weapon-pool updates/events, 6,000 charge edges and 20,000 stationary cases. A focused additional 32,768 records, each stepped three times, compares complete option bytes with canonical layout conversion: every flag byte crossed with all four tested states and all four phases, timer/tier edges, dirty positions and signed velocities. The first version correlated low flag bits with state; the final passing test removes that correlation. Logs and both evidence versions are retained. The shared beam_move arithmetic remains exactly the previously validated 1,310,720-case implementation.

Natural selected-4P preserves all 72,529 states and improves 111,379 to 111,335 display frames (44 saved). R4 span improves 2,033 to 2,032; mean complete-scene cost 1,334,104.093 to 1,332,618.791. Worst inclusive window remains ticks25,998–26,998, improving 2,034 to 2,033 frames / 29.5130 updates/sec. Solo preserves all 160,172 states and improves 167,653 to 167,631; R6 span 1,663 to 1,658, mean 919,311.708 to 918,456.714.

Protected R8 4P regresses four display frames (1,289 to 1,293) despite slightly lower mean CPU (854,584.766 to 854,520.317). Charged R8 costs two frames (1,241 to 1,243), mean 771,236.900 to 771,246.294. Both preserve 1,000 states and independent replay. BC40 has 39 ties and a three-frame R4 4P regression. Retained for both longer routes and the worst-window gain, with bounded fixture regressions explicit.

Normal40 timings/state/sprite hashes and Rush video hashes match. Rush remains 2,990/3,000 updates, zero drops/remaps/wheel fallbacks and reset cleanup. All Home12 cases pass. Bounded stack gap 11,180 bytes, no overlaps. Build warning and diff checks pass; all jobs terminal. Current R4 instruction histogram is available with the retained natural4p profile for the next examination of the player/weapon update cost. Full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Forward weapon-pool scan retained (2026-10-05)

ROM `9285a04fdea6e7c372ccbc7e6fb3d0aa33ee84f8d6669a00b274fecb249a8942` replaces `6cfe3b95ba6be4146fe1ce9e6be85c400c748e5b72c9e31b2f36324001626f7b`. Read-only prior-profile analysis in `.local/bc-option-position-only/player-hot-instructions.json` found repeated grouped state reads and nested traversal bookkeeping among the largest player instructions. The weapon loop now walks forward once: live slots run immediately; an empty slot may skip a confirmed six-record empty span, bounded by the pool end. Every task remains in source order and reads current state. Launches still precede traversal; no occupancy metadata, update removal or allocation policy changes.

Evidence: `.local/bc-weapon-forward-scan/verified.json`, before/candidate sources, ROM/ELF/headers and harness. Compiled player code grows 120 bytes (9,060 to 9,180), illustrating why source simplification alone was not considered proof of speed. Independent comparisons pass 60,000 complete pool updates/events, 6,000 charge edges, 20,000 stationary boundary cases and 32,768 three-update option records across flag/state/phase combinations. Both native canonical corpora match: 72,529 selected-4P states and 160,172 solo states.

Natural 4P improves 111,335 to 110,993 display frames (342 saved). R4 span 2,032 to 2,031; mean complete-scene cost 1,332,618.791 to 1,324,386.049. Worst inclusive 1,000-update window stays at ticks25,998–26,998, 2,032 frames / 29.5276 updates/sec. Solo improves 167,631 to 167,384 (247 saved), R6 span 1,658 to 1,629 and mean 918,456.714 to 911,739.003.

Shorter fixtures regress: protected R8 4P 1,293 to 1,300 frames, mean 854,520.317 to 857,470.124; charged R8 1,243 to 1,244, mean 771,246.294 to 774,614.827. Both preserve 1,000 states and independent replay. BC40 costs 13 frames net (three improvements, 32 ties, five regressions), including +10 at R6 4P. Retained for both longer-route and worst-window gains, with these workload-dependent costs explicit.

All Normal40 timings/state/sprite hash sequences match. Rush video hashes match, 2,990/3,000 updates, no drops/remaps/wheel fallbacks and reset cleanup. Home12 passes; bounded stack gap 11,180 bytes with no overlaps. Build warning and diff checks pass; all jobs terminal. Only production bc_rules.c changes. Full natural 4P completion and sustained 60 FPS / 100% speed remain unfinished.

### Projectile-row masks rejected at both placements (2026-10-05)

Retained ROM remains `9285a04fdea6e7c372ccbc7e6fb3d0aa33ee84f8d6669a00b274fecb249a8942`; exact SHA verified after rebuilding restored sources with fresh timestamps. No production or shared QA changes from these trials remain. The previous status-only answer made no implementation progress; this continuation revalidated the baseline and completed two evidence-producing experiments. All trial jobs are terminal.

The first candidate (`40fe697a0892a92433fe633454b4de61438b298c6a81c4a9efca95bf9364c952`, `.local/bc-shot-row-mask/rejected.json`) adds a 16-bit occupied-row mask to each transient shot index and rejects disjoint Y intervals in indexed collision. It preserves source slot order, exact byte-wrapped radii, live-state rechecks and consumed-shot behavior. The second (`ac2e32d00ad8978727f4814ce6817fedd4ad4c7f6eb907e26a0054399e122796`, `.local/bc-shot-row-early/rejected.json`) moves the mask rejection into single/multiplayer actor scans before contact materialization; direct shot collision remains unchanged there.

Both preserve all 72,529 selected-4P and 160,172 solo canonical states. Both regress the long routes: baseline 110,993/167,384 display frames becomes 111,837/167,812 for the first, and 111,785/167,770 for the earlier rejection. R4 mean complete-scene ticks rise from 1,324,386.049 to 1,340,624.320 and 1,338,337.210; spans rise 2,031 to 2,034 in both. Worst inclusive 1,000-update windows are 2,036 frames (29.4695 FPS, R3) and 2,035 (29.4840 FPS, R4), compared with retained 2,032 (29.5276 FPS). Solo R6 spans worsen 1,629 to 1,677/1,672. Short protected R8 windows take 1,297/1,299 versus 1,300 frames, but mean CPU costs rise to 858,950.883/859,022.416 versus 857,470.124; independent replay passes. Short-window display improvement is insufficient evidence to retain either regression.

Validation includes 32,000 indexed/unindexed shot comparisons, 32,000 streamed contact comparisons (6,953 ordered events), 576 segment births (786 contacts, 6,648 consumed shots, 48 allocation failures), 1,438,976 directed row/radius-boundary comparisons, and 4,096 native complete-index records with sentinels/unaltered weapon bytes. The early helper additionally passes 43,727 in-contract native row queries from a deterministic 65,536-input sweep; out-of-contract positions are skipped, as recorded in `native-coverage.json`. Its first scratch-probe link failed for missing libgcc; the harness was corrected to link the compiler's matching library before the successful probe. Both builds and diff checks are clean. Broader Normal/Rush/Home gates were not rerun for rejected candidates; exact baseline restoration preserves the previously verified release.

First-candidate profile attribution shows +8,227,744 ticks in index construction and +7,220,598 in actor contacts over the R4 window; bookkeeping outweighed scan rejection. Read-only retained-ROM instruction analysis is saved as `.local/bc-weapon-forward-scan/retained-hot-instructions.json`, using its matching ELF and cycle histogram. State scans/branches remain prominent in player/projectile loops; contact register saves and event initialization also remain measurable. No additional row-mask variant is justified by these results. Sustained 60 FPS / 100% speed and full natural 4P campaign verification remain unfinished.

### Empty-run projectile scan and explicit mapper inlining rejected (2026-10-05)

Previous goal turn made progress by ruling out both row-mask placements; this turn tested a different measured cost: projectile empty-slot traversal. Retained ROM stays exactly `9285a04fdea6e7c372ccbc7e6fb3d0aa33ee84f8d6669a00b274fecb249a8942`, verified after rebuilding both restored source files with fresh timestamps. No production change remains; all jobs are terminal.

First trial uses a compact inner while-loop for empty records, retaining the existing six-slot skip, end bounds, packed triples, sprite order and mapper behavior. ROM `ff602eaee8c796d734f14956ff98aabe572902118b1143b52bbb6e481b856dd3` and full evidence are in `.local/bc-projectile-empty-runs/rejected.json`. It preserves 72,529 selected-4P and 160,172 solo canonical states but costs 116,066/169,621 display frames versus retained 110,993/167,384. R4 mean rises 1,324,386.049 to 1,412,912.417; span 2,031 to 2,054. Worst inclusive 1,000-update window becomes 2,094 frames / 28.6533 FPS. Protected R8 ordinary/charged rises 1,300/1,244 to 1,317/1,266, both independently replayed. All twelve Home mode/player-count cases pass.

Disassembly/profile explains a major compiler side effect: the mapper stopped inlining. A separate `bc_projectile_sprite` now consumes 76,586,832 attributed ticks in the R4 window, while projectile draw itself also increases 10,172,708. The first loop variant therefore cannot be judged as a pure traversal-cost experiment. The second explicitly forces native GNU inlining of the mapper while retaining a public definition, and verifies zero mapper calls in the resulting draw routine. ROM `9ecc9964f44b999470e4d9b2da46196cf42fc7fc30bfd79330280b4485faaad7`, source, assembly and results are in `.local/bc-projectile-empty-runs-inline/rejected.json`.

The explicitly inlined version still regresses both long routes: 111,769/167,781 frames (776/397 extra), with all canonical states identical. R4 mean is 1,341,091.661, span 2,032. Worst window becomes 2,037 frames / 29.4551 FPS. Short fixtures misleadingly improve: R8 ordinary 1,293 frames, mean 855,339.870; charged 1,243, mean 775,041.827; BC40 saves eighteen frames net, with two small regressions. These gains do not outweigh the long-route and worst-window regressions. Home12 passes; stack gap 11,180 bytes with no overlap in the bounded fixture. The Normal matrix was deliberately terminated with its current child after candidate rejection; it is incomplete, not a passing gate. Exact process identities and reason are saved in `normal-stopped.json`. Rush was not run for a discarded candidate.

Host renderer comparison passes 2,400 pools / 37,527 ordered sprites / 600 packed strips, including dirty coordinate padding and unchanged simulation bytes. Its initial invocation used a source-directory argument where an archive root was required; corrected invocation passes and the initial error is archived. Both native variants pass 589,824 exact submission cases across all attributes and nine frames. Builds and diff checks pass. Renderer loop shape changes require checking inliner decisions and full-route CPU work; fewer source-level loop operations are not sufficient evidence of speed. Sustained 60 FPS / 100% speed and full natural 4P campaign verification remain unfinished.

### Word-distance party body bounds retained (2026-10-05)

ROM `54725a07426ca43c73716db83f3c4c290aac9b51e3a3c5589aedcf7370a15599` replaces `9285a04fdea6e7c372ccbc7e6fb3d0aa33ee84f8d6669a00b274fecb249a8942`. The preceding goal turn made progress by identifying and rejecting renderer/inlining regressions. Current disassembly of the common enemy path exposed 32-bit sum expansion, zero-extension and stack traffic in the whole-party body-bounds test. This change uses ordered 16-bit subtraction: `p+r<=lo` becomes `p<=lo && lo-p>=r`; `p>=hi+r` becomes `p>=hi && p-hi>=r`. Ordering prevents subtraction wrap. The predicates remain exactly equivalent for every unsigned 16-bit coordinate, byte radius, zero radius, and even unordered endpoints. Existing byte-wrapped actor half-sizes and contact order are untouched. Only production bc_world.c changes; no layout, actor, projectile, update or rendering reduction.

Evidence is `.local/bc-body-union-word-distance/verified.json`, matching archived source/headers/ROM/ELF/symbols, native probe and disassembly. Native 68000 checks compare 524,288 cases spanning every coordinate and byte radius, with extreme/inverted endpoints, against an independent widened-sum reference (not the complete Cartesian product). Host contact tests pass 32,000 1–4P comparisons and 6,953 ordered events. Both canonical corpora match: 72,529 selected-4P states and 160,172 solo states.

Natural 4P improves 110,993 to 110,573 display frames (420 saved). R4 mean complete-scene cost falls 1,324,386.049 to 1,314,928.559; span falls 2,031 to 2,030. The worst inclusive 1,000-update window falls 2,032 to 2,031 display frames: 29.5276 to 29.5421 updates/sec. Profile attribution removes 9,291,324 ticks from the common actor routine over that R4 window. Solo is exactly unchanged at 167,384 display frames, R6 span 1,629 and mean 911,739.003.

Protected R8 ordinary fire is effectively unchanged in CPU cost (857,470.124 to 857,469.704), taking 1,299 versus 1,300 frames; charged remains 1,244 frames with mean 774,614.827 to 774,624.900. Both preserve 1,000 states and independent replay. The body test is bypassed for protected players, so these are not claimed as meaningful body-test speed gains. BC40 saves one frame at R6 4P, all other samples tie. Normal40 timing, state and ordered sprite hashes all match. Rush's 3,000 video hashes match, 2,990 updates, no drops/remaps/wheel fallbacks, and reset cleanup passes. Home12 passes; bounded stack gap remains 11,180 bytes with no overlap. Build warning and diff checks pass; all jobs are terminal.

This is a measured reduction in multiplayer body-bound CPU work, not a full-speed result. Sustained 60 FPS / 100% speed and full natural 4P campaign verification remain unfinished.

### Native borrow-based body bounds retained (2026-10-05)

ROM `b4cfbb74b4811d0dd80cb8898a4a5190a4f8e30ec649aaf511028613760434d5` replaces `54725a07426ca43c73716db83f3c4c290aac9b51e3a3c5589aedcf7370a15599`. The preceding goal turn made progress by retaining ordered word-distance body bounds. This continuation tests combining its ordering and distance operations with the 68000 borrow flag. Only production bc_world.c changes; the host ordered-subtraction predicate remains intact.

First, `__builtin_sub_overflow` was tried in ROM `80b5610120cb4c5f98f075ddb422c72169d530726d397675b4ecb9c64bb2885d`. It passes 32,000 host contacts and 524,288 native reference cases, but the compiler emits extra compares, stack flag stores and reloads instead of the intended carry branch. Rejected on generated code before a long route test; no FPS claim. Source, assembly and result are in `.local/bc-body-union-borrow/rejected.json`.

The retained implementation uses native SUB.W/BCS to exclude a wrapped distance before comparing the exact byte radius. An asm-goto block has an explicit D0 scratch/condition-code clobber and read-only input operands; no memory is written. Each interval half remains exactly equivalent to the original widened-sum test, including zero radii, full-range coordinates and reversed endpoints. `tools/qa_bc_body_bounds_native.py` now makes the independent 524,288-case native predicate check reusable. The sweep spans all coordinate and radius values but is not their complete Cartesian product. The archived prototype and the permanent tool both pass. Current host contacts also pass 32,000 comparisons / 6,953 ordered events.

Evidence: `.local/bc-body-union-native-borrow/verified.json`, source/headers/ROM/ELF/symbols, compiled common-task assembly and function attribution. All 72,529 selected-4P and 160,172 solo canonical states match the prior retained build. Natural 4P improves 110,573 to 110,280 display frames (293 saved). R4 mean falls 1,314,928.559 to 1,309,374.262; common-routine attribution falls by 5,418,938 ticks over the 1,000-call window. R4 span stays 2,030; worst inclusive window stays 2,031 frames / 29.5421 updates/sec. Solo improves 167,384 to 167,340 (44 saved), R6 span 1,629 to 1,625 and mean 911,739.003 to 910,832.629.

Protected R8 ordinary remains 1,299 frames, mean 857,469.704 to 857,427.354; charged improves 1,244 to 1,242, mean 774,624.900 to 774,186.910. Both preserve 1,000 simulation hashes and independent replay. BC40 regresses three frames net (two improvements, three regressions, 35 ties), explicitly retained for the longer-route CPU gains. Normal40 timings and all state/ordered-sprite hashes match. Rush's 3,000 video hashes match, 2,990 updates, no drops/remaps/wheel fallbacks and successful reset cleanup. Home12 passes; bounded stack gap remains 11,180 bytes, no overlap. Build warning, Python syntax and diff checks pass. All jobs terminal; release SHA matches the archived candidate.

Full natural 4P campaign verification and sustained 60 FPS / 100% speed remain unfinished. The worst measured sustained rate did not improve in this trial despite less total route CPU work.

### Combined enemy interior-byte test retained (2026-10-05)

ROM `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1` replaces `b4cfbb74b4811d0dd80cb8898a4a5190a4f8e30ec649aaf511028613760434d5`. The prior goal turn made progress by retaining native borrow-based body bounds. This continuation replaces the common motion gate's logical OR of two pure coordinate-byte reads with bitwise OR. Both predicates are true exactly when at least one high byte is nonzero; the flags gate, full wrapped edge checks, animation, motion and retirement remain unchanged. Generated 68000 code combines the two bytes and branches once for the frequent interior-screen case. A source comment explains the intentional bitwise form. The comment-only rebuild reproduces the exact tested ROM hash. Only production bc_rules.c changes.

Evidence: `.local/bc-enemy-interior-or/verified.json`, matching source/ROM/ELF/headers, common-task assembly and function attribution. Three original-source fixtures pass 34,477 motion updates, 313 retirements, 1,037 death-animation updates, 3,074 composite updates and 25 HP-exhaustion transitions. These are common-task fixtures, not a full-game source-equivalence claim. Both native corpora match: 72,529 selected-4P and 160,172 solo canonical states.

Natural 4P improves 110,280 to 110,212 display frames (68 saved). R4 mean complete-scene cost falls 1,309,374.262 to 1,308,391.105; common-routine attribution falls by 934,276 ticks in the 1,000-call window. R4 span remains 2,030; worst inclusive window remains 2,031 frames / 29.5421 updates/sec. Solo improves 167,340 to 167,306 (34 saved), R6 span 1,625 to 1,612 and mean 910,832.629 to 909,214.124.

Protected R8 ordinary improves 1,299 to 1,298 frames, mean 857,427.354 to 856,112.257. Charged costs one extra frame (1,242 to 1,243) despite lower mean CPU (774,186.910 to 773,454.920); this short-window regression is explicit. Both preserve 1,000 states and independent replay. BC40 saves nine frames net (eight improvements, 29 ties, three regressions), without measurement errors. Normal40 timings and all state/ordered-sprite comparisons match. Rush's 3,000 video hashes match, 2,990 updates, no drops/remaps/wheel fallbacks and successful reset cleanup. Home12 passes; bounded stack gap remains 11,180 bytes with no overlap. Builds and diff checks are clean; all jobs terminal.

The improvement is small and does not raise the worst sustained frame rate. Full natural 4P campaign verification and sustained 60 FPS / 100% speed remain unfinished.

### Constant-kind ordinary-shot specialization rejected (2026-10-05)

The prior goal turn made progress by retaining the combined enemy interior-byte test. This continuation investigated the largest remaining attributed routine, player/weapon updates. Candidate `b534904f90597f8079aa556750379106ee971f2ee05e8f7659b708a83abd46c0` extracts an always-inlined ordinary-shot implementation with an explicit kind argument. The ordered weapon dispatcher supplies constant zero/one for straight/expanding slots; the public entry passes the actual kind, preserving its generic behavior. This differs from the older rejected noinline ordinary-shot argument split: no new per-shot call is introduced. Slot order, animation, terrain checks, X-before-Y motion/retirement and option ownership accounting stay unchanged.

Evidence: `.local/bc-shot-kind-specialization/rejected.json`, before/candidate sources, ROM/ELF/headers, differential harness and full native route results. Host comparisons pass 60,000 complete weapon-pool updates/events, 6,000 charge edges, 20,000 stationary-shot boundary cases and 32,768 three-update option cases. Both native corpora match all canonical gameplay states: 72,529 selected-4P and 160,172 solo.

The player routine grows 9,180 to 9,594 bytes (+414) and fits the ROM, but native performance rejects it. 4P route rises 110,212 to 111,059 display frames (+847); R4 mean 1,308,391.105 to 1,323,421.022 and span 2,030 to 2,031. Worst inclusive 1,000-update window rises 2,031 to 2,032 frames (29.5421 to 29.5276 FPS). Player routine attribution increases 14,698,964 ticks over the R4 window. Solo rises 167,306 to 167,564 (+258), R6 span 1,612 to 1,650 and mean 909,214.124 to 916,316.912. Removing source-level kind decisions does not reduce total native work in these routes.

All trial jobs finished before restoration. Rebuilt restored bc_rules.c with a fresh timestamp and verified exact retained SHA `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`; no production change from this experiment remains. Builds and diff checks are clean. Broader Normal/Rush/Home gates were not repeated for the discarded candidate; the exact previously verified release is restored. Full natural 4P campaign verification and sustained 60 FPS / 100% speed remain unfinished.

### Player partial-redundancy-elimination experiment rejected (2026-10-05)

The preceding goal turn made progress by measuring and rejecting constant-kind shot specialization. This continuation mapped the retained R4 instruction histogram to its matching ELF and found 39,491,004 ticks in player-routine instructions with SP/FP stack operands, out of 238,895,944 attributed player ticks. The frame pointer is established by LINK; counting only SP operands would miss most accesses. These are complete instruction costs, not an isolated memory-stall estimate.

Tested a native-only `optimize("no-tree-pre")` attribute on bc_player_step_into, disabling only partial redundancy elimination while retaining O3 and existing inlining. This is distinct from the old broad O2 experiment on the former struct-return player entry. Local compiler option inspection confirms PRE enabled by default. No C gameplay rules, record layouts or scheduling were changed. Candidate `85207e5c68639a0d5058a66bc1bf6853600ae137a42f43d181ad01485e2f6cf0`, source/headers/ROM/ELF, disassembly and both profiles are archived in `.local/bc-player-no-pre/rejected.json` and adjacent files.

The player function shrinks 9,180 to 8,732 bytes, but its local frame grows 204 to 212 bytes. Measured SP/FP-operand instruction cost rises 39,491,004 to 56,692,524 ticks; complete player attribution rises 238,895,944 to 248,527,230. Thus the specific register-pressure hypothesis is contradicted by the native workload despite smaller code.

All 72,529 selected-4P and 160,172 solo canonical states match. Both routes regress: 4P 110,212 to 110,826 display frames (+614), R4 mean 1,308,391.105 to 1,318,278.773 and span 2,030 to 2,031; worst inclusive 1,000-update window 2,031 to 2,032 frames (29.5421 to 29.5276 FPS). Solo 167,306 to 167,407 (+101), R6 span 1,612 to 1,622 and mean 909,214.124 to 911,465.877. Rejected; broader Normal/Rush/Home checks were unnecessary for this discarded compiler setting.

Both route jobs completed before restoring bc_player.c with a fresh timestamp. Rebuild/finalization verifies exact retained SHA `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`. No production change remains, all jobs terminal, builds/diff checks clean. Full natural 4P campaign verification and sustained 60 FPS / 100% speed remain unfinished.

### Earlier Round 4 walker dispatch rejected — 2026-10-05

Moved the existing b26e/b32d/b33e family branch ahead of unrelated boss-family
checks in bc_actor_step_into, preserving canonical straight/homing bullet and
bullet-death precedence for custom relocations. No handler body, scrolling,
RNG, child allocation, collision, or event ordering changed.

Candidate ROM: `93630028d18a5ab6aca30a21e74019a5a2883cc8e78efb611ea5895732528931`.
Baseline: `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.
The mixed walker differential passed 1,000 three-pass pools and 60,277 ordered
events. The original Round 4 later-loop fixture passed 4,987 loops, 108,412
actor updates, 165 child updates, and 237 retirements with no unsupported loops.

Both scene-paced long replays matched all canonical states (72,529 selected-4P
and 160,172 solo), but selected-4P increased 110,212 to 110,420 video frames
and solo increased 167,306 to 167,378. The sampled R4 mean decreased slightly
from 1,308,391.105 to 1,305,461.409 core ticks; its noninclusive span remained
2,030 frames. The worst inclusive 1,000-update window remained 2,031 frames,
29.54209749 FPS, earliest candidate tie at ticks 25997–26997. Solo R6 mean
increased to 909,893.068 and span to 1,621. Round-entry-bounded span analysis
attributes 182 of the 208 additional selected-4P frames to Round 7; these
spans include entry-transition boundaries and are not isolated per-round CPU
measurements.

Rejected on long-route timing. Reverted bc_world.c; no new production code
is retained. No broader mode gates were run for this rejected candidate.
Evidence: `.local/bc-r4-walker-dispatch/rejected.json`. All replay and source
checks terminated before rebuilding. Full-speed completion and a complete
natural four-player campaign remain unproven.

Restoration verified: release ROM exactly matches baseline SHA-256 `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.

### Separate charge/fire phase rejected — 2026-10-05

The previous goal turn produced evidence against earlier R4 walker dispatch.
This continuation tested a different player/weapon boundary: extracted the
existing alive-only charge, main/option firing and reserved beam launch block
into noinline weapon_fire_phase. The ordered existing-shot loop remains
inlined. This is distinct from the older whole-weapon outlining and beam-only
launch-helper experiments. No source task, slot iteration, retirement, RNG,
launch, charge or collision rules changed.

Candidate ROM `3e2011633e54cd80b701b61ccf1225e56db4ca9d456be85f3c1f7123dba68354`
compared with baseline `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.
The player function shrank from 9,180 to 4,634 bytes, with a separate 4,116-byte
fire helper. Its local frame shrank from 204 to 52 bytes; the helper has a
188-byte local frame. These are local prologue allocations, not total stack
high-water measurements.

The differential passed 60,000 complete weapon updates, 6,000 charge edge
cases, 20,000 stationary-boundary records and 32,768 three-update option
records. The continuous PCE source fixture passed 1,101 weapon updates, 872
main launches, 198 option launches, 4,088 native contact scans and 1,101 trail
updates. That fixture covers no beam launches; charge/beam launch boundaries
are exercised by the separate differential.

All 72,529 selected-4P canonical states and 160,172 solo states match, but
selected-4P grows 110,212 to 110,769 frames, and solo grows 167,306 to 167,445.
R4 sampled mean grows 1,308,391.105 to 1,315,752.697 core ticks; its 2,030-frame
noninclusive span is unchanged. Worst inclusive 1,000-update window remains
2,031 frames / 29.54209749 FPS at ticks 25998–26998. Solo R6 mean rises to
913,105.018 ticks and span to 1,635 frames (previously 1,612).

Instruction attribution explains why the smaller frame is insufficient:
player cost falls from 238,895,944 to 224,369,082 ticks, but the fire helper
adds 21,684,418, increasing the combined cost by 7,157,556 ticks. Instructions
with SP/FP operands cost 39,491,004 before and 50,461,894 across both candidate
functions. These count whole instruction costs, not isolated memory penalties.

Rejected and restored bc_rules.c byte-for-byte. No broader mode gates were
run for this rejected candidate. All replay/check jobs terminated before the
restore build. Evidence: `.local/bc-fire-phase-outline/rejected.json`, with
source/ROM archives and instruction-cost report. Full-speed and complete
natural 4P campaign requirements remain unmet.

Restoration verified: release ROM exactly matches baseline SHA-256 `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.

### Three-slot empty weapon skips rejected — 2026-10-05

Previous goal turn tested and rejected separating charge/fire work. Current
instruction attribution again places weapon traversal among the highest
player costs. Tested changing only the forward loop's empty-span skip from
six slots to three, with corresponding end guard and two-neighbor OR. This
allows skipping shorter empty stretches before live slots, retaining original
slot order, all updates, allocation and ownership accounting.

Candidate `42e7a882dda31b3eb93e42770f9c46fe8c20e6dc10efa83199790ae65669f35b`
compared to `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.
Host differential passes 60,000 complete weapon updates, 6,000 charge-edge
cases, 20,000 stationary boundary records and 32,768 three-update option
records. Both long scene-paced replays match all canonical states: 72,529
selected-4P and 160,172 solo.

Selected-4P costs 110,610 video frames versus 110,212; solo costs 167,316
versus 167,306. Sampled R4 mean increases 1,308,391.105 to 1,312,880.751
core ticks; integrated player instruction cost increases 238,895,944 to
243,248,642. The noninclusive R4 span remains 2,030 frames. Worst inclusive
1,000-update window remains 2,031 frames / 29.54209749 FPS at 25998–26998.
Solo R6 increases 909,214.124 to 909,417.502 mean ticks and 1,612 to 1,613
frames. Extra traversal overhead outweighs shorter empty-span opportunities.

Rejected; restored bc_rules.c byte-for-byte after all checks terminated.
No broader mode gates run for this rejected candidate. Evidence and archives:
`.local/bc-weapon-three-skip/rejected.json`; measured baseline hot instructions
are saved alongside. The retained six-slot forward traversal remains in place.
No production improvement or full-speed claim follows from this experiment.

Restoration verified: release ROM exactly matches baseline SHA-256 `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.

### Precomputed shot rejection intervals rejected — 2026-10-05

Prior turn produced timing evidence against three-slot weapon skips. This
continuation examined collision calculations. Existing earlier prechecked
contact and distance-reuse experiments were reviewed before choosing a new
change: replace only indexed per-point coarse absolute-distance rejection
with precomputed circular intervals. For positive radius r <= 510,
(unsigned short)(enemy + r - 1 - shot) < 2*r - 1 contains every exact
unsigned-distance hit. Any wraparound false positive still encounters the
unchanged exact per-shot unsigned-distance and byte-radius checks. Zero
aggregate radii return no hits. Aggregate rectangles, live-state rechecks,
shot order, consumption and damage logic remain unchanged.

Candidate `905a12f080cc045792675adb0be8652e8946fc4ca3b5d25e3d59a413c382cdcb`
against baseline `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.
Indexed/unindexed differential passes 32,000 scans / 5,336 contacts / 2,070
damaging hits. Additional boundary differential passes 65,536 scans / 2,241
contacts / 901 damaging hits, including zero and maximum half-radii, high
word coordinates and wrapping edges. Streamed party contacts pass 32,000
comparisons / 6,953 ordered events.

Both native long routes match canonical states: 72,529 selected-4P and
160,172 solo. However, 4P costs 110,291 frames versus 110,212; solo costs
167,346 versus 167,306. R4 mean rises 1,308,391.105 to 1,310,853.614 core
ticks, with span unchanged at 2,030 noninclusive frames. Worst inclusive
1,000-update window remains 2,031 frames / 29.54209749 FPS at 25998–26998.
Solo R6 mean rises to 909,941.704 and span to 1,615 (previously 1,612).

Rejected: the extra per-query setup does not produce a measured speed gain.
Restored bc_rules.c after all jobs terminated. No broader mode gates were
run for the rejected candidate. Evidence and full source/ROM archives:
`.local/bc-shot-coarse-interval/rejected.json`. Sustained full speed and full
natural four-player campaign completion remain unproven.

Restoration verified: release ROM exactly matches baseline SHA-256 `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.

### Two-register packed SAT emission rejected — 2026-10-05

Previous goal turn measured and rejected shot coarse intervals. This turn
examined renderer register pressure after reviewing earlier rejected mapping
tables, pose caches, small-bucket hints and four-MOVE.W emitter variants.
Tested a distinct writer: pack y/size-link into d0 and attribute/x into d1,
then MOVEM.L those two registers. Existing retained writer uses four word
registers d0–d3 and MOVEM.W. Count, clipping, lookup, ordering and all eight
output bytes remain unchanged; no graphics or update reduction.

Candidate `d7e72688950738835e4e265f036fd49202636edd81e5599d2ef48142f820a1b4`
against baseline `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.
The scratch native 68000 emitter probe passes 20,480 flag/slot combinations,
wrapping coordinates, exact count/size/link/attribute/position and complete
table sentinels in 4,382 probe frames. Its copied harness only adds the u32
typedef needed by the new extracted writer; it never overwrites release ROM.

Long replays match all 72,529 selected-4P and 160,172 solo canonical states.
They nevertheless take 111,280 and 167,708 frames instead of 110,212 and
167,306. R4 mean rises 1,308,391.105 to 1,322,164.711 ticks; noninclusive
span rises 2,030 to 2,032. Worst inclusive 1,000-update window rises 2,031
to 2,033 frames, 29.51303492 FPS at 25998–26998. Solo R6 mean increases
to 918,617.014 and span to 1,664 (previously 1,612).

Rejected: packing overhead outweighs fixed-register reduction in the tested
build. Restored sprites.c byte-for-byte after every test job terminated.
Broader Normal/Rush/Home gates were not run for the rejected candidate.
Evidence and complete source/ROM archives: `.local/bc-sat-two-registers/rejected.json`.
The retained four-word MOVEM emitter remains. Full-speed completion and full
natural four-player campaign coverage remain unproven.

Restoration verified: release ROM exactly matches baseline SHA-256 `6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1`.

### Natural selected-4P turret-lane campaign started — 2026-10-05

Previous turn measured and rejected two-register SAT writes, then restored
exact retained ROM 6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
This continuation addresses missing natural full-campaign coverage. Started
the existing controller pilot with --turret-lanes, splitting late R7 aiming
between upper/lower turrets. Home selects four players and seven starting
lives; real continues remain enabled. The previously tested R4 horizon12,
R8/R9 horizon12, direct boss aiming, pickup seeking and actual-core safety
lookahead remain. No protection, injected health/weapons/lives, forced deaths,
forced boss kills or authoritative-core restores. Prediction uses a separate
host core; the cartridge continues to run native Genesis code.

The run uses unchanged release ROM and writes controller recording/death
traces on completion. Evidence: `.local/bc-natural4p-turret-lanes/run.json`,
`campaign.log`, and archived baseline source/ROM/pilot helpers. Live execution
handle 23297, observed PID3321. Round1 cleared at tick6646; tick8000 reports
Round2 with life counters [6,6,6,6]. These are initial progress observations,
not full-campaign or performance proof. Keep release ROM fixed while this
pilot is live. Previous selected-4P corpus remains the R1–R6 clear/R7 loss;
60 FPS and complete natural4P coverage remain unproven.

### Live natural4P follow-up and menu-evidence audit — 2026-10-05

Re-polled live execution handle23297 and PID3321; no restart or ROM rebuild.
The current native run entered R2 at tick6646 and R3 at tick14198. R4 entry is tick21674/frame36594, with all
four life counters [6,6,6,6]. Tick22000 remains R4. These are live diagnostic
observations and await independent recorded-input replay after termination.
The turret-lane option is only active late in R7, so earlier survival must not
be attributed to it. Unchanged release ROM hash is confirmed.

Audited the existing Home modal evidence against the exact current ROM: all
12 combinations (normal/bc/rush ×1/2/3/4P) pass dialog, cancel preservation
and launch. Initial audit used display labels instead of the tool's short
mode keys; source inspection corrected the assertion before marking the
audit passed. `.local/bc-natural4p-turret-lanes/menu-evidence-audit.json`
records this narrowly scoped proof. It does not establish gameplay speed.
Pilot remains live; keep release fixed. Full natural4P campaign and sustained
60 FPS /100% speed remain unverified.

Live campaign follow-up: execution23297 remains live and release hash unchanged. Latest logged observation: {"tick": 28000, "frame": 48081, "round": 4, "status": 0, "camera": [2304, 768], "lives": [4, 6, 6, 7], "boss": [232, 126, 10, 8, 0]}. 3 alive-to-dying transitions observed so far; diagnostics do not infer exact death causes. No restart, protection, gameplay mutation or new completion claim. Evidence remains `.local/bc-natural4p-turret-lanes/`.

### Current-ROM CPU budget audit during live campaign — 2026-10-05

Revalidated live session23297/PID3321 and unchanged release. The latest
observation is R4 tick30000, frame50475, life counters [3,5,5,6], visible
boss [232,101,9,6,0]; seven deaths logged. The test remains live.

Read-only audit of the matching retained R4 profile (1000 complete scenes,
start25998): budget896040 core ticks, mean1308391.105, maximum2128098.
Reaching the frame budget requires at least31.5159% mean reduction and
57.8948% reduction of this measured maximum, before outer input/VBlank/DMA
work. These are necessary CPU-budget reductions, not proof of whole-game
requirements or a claim that reducing only the mean would suffice.
Player updates18.259%, common enemy12.615%, projectile drawing11.440%,
general actor loop10.522%, actor drawing8.793%, detailed party scan8.002%
of measured scene mean. Attribution is exclusive per-instruction function
assignment; callees are separate. This supports targeting several major
paths, with measured long-route gates, rather than expecting one small
rewrite to close the gap. Evidence: `performance-budget-audit.json` in
`.local/bc-natural4p-turret-lanes/`. No production edits or rebuild occurred.

### Optional rapid-fire rhythm in controller lookahead — 2026-10-05

Current live campaign remains on unchanged release and its already-loaded
original pilot code; it has reached R4 tick34000 and used a real continue
for P1 at tick33572. The snapshot is still running (session23297/PID3321).
No current-run forecast behavior was altered.

Read-only source review found default prediction holds the present fire
button throughout its horizon, whereas --rapid-fire live input uses three
updates held/three released. Added opt-in --predict-rapid-fire, requiring
--rapid-fire and --lookahead. Shadow branches preserve exact first-update
inputs/edges, then predict that known global-tick rhythm for all peers.
Movement and firing side remain held approximations; future reactive
controller decisions are not claimed exact. Default forecast remains intact.
Only QA/controller tools changed; no cartridge source or ROM changed.

New qa_bc_pilot_fire.py exercises actual shadow-core pad writes for all
four selected controllers and all six starting phases (24 cases), checks
burst/release edges and peer movement, and verifies authoritative RAM/CPU/
VRAM/pixels unchanged. Its setup explicitly uses synthetic player states
and invulnerability solely in a separate QA process, never the campaign.
Existing default multiplayer predictor fixture passes eight active/inactive
controller/horizon cases with live state unchanged. Invalid option guard
is checked before a game starts. Syntax checks pass.

Evidence/tool snapshots: `.local/bc-natural4p-turret-lanes/rapid-forecast/verified.json`.
This is forecast-tool verification, not a survival, campaign, or speed gain.
Use only in a subsequent independent pilot trial after the current run ends.

### Turret-lane campaign terminal verification; firing-forecast trial started — 2026-10-05

Confirmed session23297 terminal. Current-ROM natural selected4P run ended
in R4 at tick39929, gameplay frame60900, after44 deaths and two real
continues (P1/P2); game-over Start returned Home. It cleared R1–R3. Since
R7 was not reached, this run did not exercise or validate turret lanes.
The previous R1–R6 clear/R7 loss remains the broader natural4P coverage.

Independent controller replay completed all60900 recorded video frames
with zero authoritative save-state restores. Endpoint complete workRAM,
CPU registers, VRAM and rendered pixels match exactly. This is endpoint
checkpoint equality after replay, not a per-frame full-state/pixel audit.
Evidence: `.local/bc-natural4p-turret-lanes/verified.json`. Neither natural
full-campaign nor full-speed completion follows.

Started the next trial on the exact same release hash6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1
with only --predict-rapid-fire enabled. Same Home4P/seven lives, real
continues, horizons, boss aiming, pickups and turret-lane option. No game
source or ROM changes. Live execution handle75875; new evidence/source
archive `.local/bc-natural4p-rapid-forecast/`. Keep release fixed until
this trial and its independent replay terminate.

### Boolean terrain bitmap probe while campaign runs — 2026-10-05

Rapid-fire forecast campaign remains live (session75875/PID65949), on exact
retained release6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
It reached R4 with more early losses than the preceding trial; survival
improvement is not established. No release rebuild occurred.

Read-only map analysis found byte-row deduplication needs332800 bytes for
ten per-round maps, or331008 bytes with a global row dictionary/pointer
tables. That does not fit the current 4MiB cartridge. See
`.local/bc-terrain-row-probe/sizes.json`.

A separate scratch 68000 ROM benchmarks one-bit solid/empty maps (8192
bytes/round,81920 for all ten). Native byte-memory BTST followed by SNE
replaces variable shifting; exact pointer-identity guards retain a generic
fallback. All655360 subcell queries across ten source maps match boolean
solidity, plus12288 mismatched/disabled-resource fallback checks. This
representation intentionally does not preserve the original nonzero nibble
value; any integration must use it only where that value is interpreted as
a Boolean and preserve the generic API's numeric return contract.

Measured reference lookup1688207360 core ticks; bitmap1450462650
(14.0827% less); full-byte direct table1192755200. These are isolated
noinline lookup costs, not integrated scene/route FPS. Existing R8/R10
full-byte maps are faster than bitmap lookup, so replacing them trades
performance for space. All-round bitmap storage would be smaller than
those two maps combined but could regress their current fast paths.
Current raw ROM ends at4177216, leaving17088 bytes before4MiB.

Evidence/source/native probe/profile: `.local/bc-terrain-bitmap-probe/verified.json`.
Release/source gameplay remains unchanged. This identifies a promising
primitive for an integration experiment, not retained game optimization or
full-speed proof.

### Exact-value bitmap variants rejected in native microbenchmarks — 2026-10-05

Confirmed the ongoing rapid-fire predictor campaign/session75875 remains
live; no release or cartridge source mutation. Audited all source terrain
values: most rounds include multiple nonzero nibbles, so a Boolean bitmap
cannot silently replace bc_terrain_solid's numeric contract. Distribution
is saved in `.local/bc-terrain-bitmap-probe/value-distribution.json`.

Tested a bitmap-only empty-cell rejection followed by the exact original
lookup on occupied cells. Both variants pass655360 exact numeric queries
and12288 fallback cases. The first inlines the original fallback and costs
2289288750 core ticks versus1688207360 reference (+35.6047%). The second
uses a separate noinline/no_icf fallback: bitmap body1662991330 plus
fallback148364720 =1811356050 (+7.2946%). Count the fallback instructions;
using only the bitmap-body attribution would give a misleading comparison.
Both are rejected as generic numeric-lookup replacements. Evidence in
`.local/bc-terrain-exact-bitmap/rejected.json` and
`.local/bc-terrain-exact-bitmap-call/rejected.json`, with native scratch
ROMs, extracted source and profiles. Release remains exactly6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.

The prior14.0827% Boolean-only lookup improvement is still only a primitive
benchmark. Integration would need a separate Boolean-query path and tests
that preserve the generic numeric API; these failed wrappers provide no
gameplay improvement. Sustained60FPS and full natural4P completion remain
unverified.

### Rapid-fire forecast campaign replay and compact terrain probes — 2026-10-05

The preceding user-answer turn only restated existing timing evidence and
is classified as no progress. This continuation established that campaign
PID65949 had terminated and read its completed result; it did not restart
an unobserved live run. The selected Home 4P rapid-fire-forecast campaign
cleared Rounds1–5, then lost Round6 at tick52786. There were46 deaths
(P1=15, P2=8, P3=15, P4=8), two real continues and a successful game-over
return to Home. No debug protection, forced deaths/boss defeats or seeded
health/weapons. Round7 turret-lane policy was not reached. The previous
best natural selected4P route still covers more rounds (R1–R6).

Independent replay consumed all77632 recorded controller/video frames,
with zero authoritative save-state restores. Endpoint full RAM, CPU,
VRAM and pixels match the recorded checkpoint; this is not a per-frame
checkpoint audit. Endpoint RAM SHA256:
dc70fe876a72efccd1e99148f4714e682cdedacf8707c1493298b87105759289.
Evidence: `.local/bc-natural4p-rapid-forecast/verified.json` and
`campaign/controller-replay.json`. Both pilot and replay are terminal.
This improves coverage versus the immediately preceding R4-loss trial,
but proves neither a full4P clear nor a general pilot survival advantage.

Two additional native scratch-ROM terrain representations were measured
without changing the production cartridge or source. Each passed655360
Boolean collision queries spanning all ten rounds plus12288 disabled or
mismatched-source fallback queries. A256-byte per-round cell occupancy
mask uses2560bytes total but costs2505592250 attributed core ticks versus
1688207360 reference (+48.4173%); rejected. Deduplicated32-byte Boolean
rows use44160bytes across ten rounds (global dedup41920, versus17088 free)
and cost1872514490 ticks (+10.9173%); rejected. Their Boolean contract is
not a replacement for the generic numeric collision-nibble API. Evidence:
`.local/bc-terrain-cell-mask/rejected.json`,
`.local/bc-terrain-boolean-row-probe/rejected.json`, and
`.local/bc-terrain-boolean-rows/sizes.json`. All scratch jobs are terminal.

Production ROM remains6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
No integrated performance gain retained this turn. Worst measured sustained
4P window remains29.54209749FPS (1000updates/2031video frames). The flat
8192-byte Boolean bitmap's earlier primitive gain remains a possible
single-round integration experiment, not proven game improvement.
Full natural4P completion and sustained60FPS/100% speed remain incomplete.

### Round4 Boolean bitmap integration rejected — 2026-10-05

Previous turn classified as progress: independent natural4P controller
replay completed and two scratch terrain representations were rejected.
Confirmed no campaign/profile processes remained before changing release.

Tested the previously promising flat Boolean bitmap inside actual game
terrain callers. Generated8192bytes for Round4; a private Boolean helper
checks both original source pointers, then uses BTST on the bitmap, falling
back to the original lookup for other sources. Generic numeric
bc_terrain_solid API and BcTerrain ABI were unchanged. Player movement,
beam terrain checks and enemy terrain checks used the helper. No actors,
updates, waves, contacts or shots were omitted.

Candidatebeccdd5feb590f5fe781560ce5f6702b6ac55b96a3176e55703b43c72005b5ec
passed33554432 generic numeric queries,655360 extracted native Boolean
queries across ten rounds, and12288 modified-source/control queries.
The native harness reference attribution includes candidate fallback calls;
do not read its raw per-function totals as a speed comparison.

Full scene-paced4P replay matched72529 canonical states, but total video
frames regressed110212→111388. Round4 1000-scene mean worsened
1308391.105→1315184.276 core ticks, with noninclusive video span2030
unchanged. Worst sustained1000-update window became2033frames at
ticks18522–19522 (29.51303492FPS). Full solo scene-paced replay matched
160172 states, but frames regressed167306→167731; Round6 profile span
1612→1666 and mean909214.124→919239.034. These are canonical gameplay
state comparisons, not original-controller-phase full machine comparisons.

Rejected the integration. All replay and scratch jobs completed before
restoring the three changed files with fresh modification times and
rebuilding. Exact baseline ROM SHA restored and verified:
6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
Evidence, baseline/candidate sources and ROMs, profiles and restoration:
`.local/bc-round4-bitmap-integrated/rejected.json`.
The isolated bitmap primitive gain does not translate through per-query
source guards and changed compiler output; do not retry this same wrapper
as a proven improvement. Retained worst sustained4P rate stays29.54209749FPS.
Full natural4P completion and sustained60FPS/100% speed remain incomplete.

### Projectile draw O2 compiler variant rejected — 2026-10-05

Previous turn classified as progress (integrated terrain trial measured,
rejected and exact baseline restored). Confirmed no prior test processes
were live before this new build. Applied native-only optimize("O2") to
bc_projectiles_draw; retained the mapper, traversal, grouping, source order
and all submissions. Candidatea0254ee76d7c9b778446d87d4effeb0e863bca68bfdb38ef7e68219c953a651b
passed2400 host pools,37527 ordered submissions,600 packed strips and
589824 native renderer cases. The draw routine shrank2654→1380bytes,
but smaller code did not mean lower execution cost.

Four-player canonical replay matched72529 states and regressed
110212→110350video frames. Round4 mean1308391.105→1311013.249,
span2030→2031; projectile exclusive ticks149686166→152205662.
Worst1000-update window2032frames at25998–26998 (29.52755906FPS).
Solo matched160172 states but regressed167306→167340frames;
Round6 mean909214.124→910619.654 and span1612→1622.
These scene-paced canonical comparisons do not claim original-phase full
machine equivalence. Evidence/source/ROM archives and profiles:
`.local/bc-projectile-draw-o2/rejected.json`.

Rejected; all tests terminal before source restore and rebuild. Verified
exact restored release6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
No production change retained. Worst retained sustained4P remains
29.54209749FPS. The full natural4P campaign and sustained60FPS/100% speed
remain incomplete; menu12 evidence for the unchanged baseline still applies.

### Option known-free-slot allocation trial rejected — 2026-10-05

Previous turn classified as progress (projectile compiler experiment measured
and rejected). No prior test jobs remained before building. Option launch
already scans for a free slot, then called its ordinary/returning launcher
from pool start. Candidate started the one-shot launch at the known free
slot. Both families launch exactly one shot with these fixed power arguments;
allocation, untouched bytes and source ordering remain unchanged.

Candidatebef47f5128d595919b64ccc8820ffa28f7a90bf4a24902662028388c361fb9a9
passed60000 weapon updates,6000 randomized charge releases,20000 stationary
cases,32768 option records and1566 dense pool cases covering every first-free
boundary, full pool, either/both options, wrapped kinds and facing values.
Source task trace passes1101 updates,872 main/198 option launches,
4088 native contact scans and1101 trails. No beams in that source fixture.

Full4P scene-paced replay matches72529 canonical states but takes
110216video frames versus110212 baseline. Round4 mean improves slightly
1308391.105→1308104.448; profile span2030 and worst inclusive2031/29.54209749FPS
are unchanged. Solo matches160172 states, improves167306→167292 total
frames and mean909214.124→908806.444, but Round6 span worsens1612→1614.
The mixed marginal result supplies no sustained4P gain; rejected rather
than retaining another tradeoff while the primary performance deficit remains.
These replay comparisons cover canonical scene state, not full RAM/video.

All jobs completed; source restored with fresh modification time and rebuilt.
Exact restored release SHA verified:
6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
Source/ROM archives, tests, profiles and aggregate evidence:
`.local/bc-option-known-free/rejected.json`.
No production change retained. Full natural4P completion and sustained
60FPS/100% speed remain incomplete.

### Retained paired native body bounds — 2026-10-05

Previous turn classified as progress (known-free option allocation measured
and rejected). Current baseline instruction audit is archived in
`.local/bc-current-hot-instructions/hot.json`: the actor common path spills
X/Y and both radii to stack before separate native axis predicates. The
new party_bodies_far native block reads each coordinate/radius when needed,
uses D0/D1/D2 scratch registers, and branches out on the same ordered word
subtractions and unsigned radius comparisons. Y is read only after X passes.
Byte-sized hitbox additions, zero radii, unordered endpoints and wrapped
coordinates retain their original semantics. No task, actor, shot, collision,
wave or submission is removed. Generic portable code remains the reference.
The toolchain does not support asm-goto outputs; the compiled implementation
uses explicit scratch-register clobbers and read-only memory operands.

Retained ROM:
af83c64b4b8e4b46521304e3fdf3492d8b0aec8ddb9521239d9f99949e0b6f42
replaces6df234bb1363443e4dbdff493239e00560f427968679b42913ef1a1c1af003c1.
The common routine shrinks1368→1320bytes; its exclusive ticks in the R4
window fall165057270→150663030. Whole-scene mean falls1308391.105→1293741.799.

Native widened-arithmetic comparison passes1048576 cases across both axes,
all16-bit positions, byte radii, zero/extreme/inverted boundaries; half of
cases force X near to independently exercise Y. Permanent reproducible
probe: `tools/qa_bc_party_bounds_native.py`; it uses a scratch cartridge.
Host contact stream also passes32000 comparisons/6953 ordered events.
Full scene-paced4P replay matches72529 canonical states, improves
110212→109365video frames; solo matches160172 states,167306→167235frames.
The solo R6 mean909214.124→907292.841 and span1612→1604 improve.
These compare canonical state at completed scenes, not full original-phase
RAM/video checkpoints and not a new natural4P campaign clear.

Worst inclusive1000-update4P window improves2031→2024video frames at
ticks25998–26998:29.54209749→29.64426877FPS. R8 ordinary improves1298→1292,
mean856112.257→855513.148; charged1243→1242,mean773454.920→772938.208.
Both protected1000-update fixtures match baseline simulation hashes and
pass independent replay. BC40 opening timings total unchanged:5 improve,
30 tie,5 regress by1–2frames. This is not a universal full-speed improvement.

All12 Home modal/cancel/launch mode/player cases pass on the retained ROM.
Normal40 timing and state/render hashes match baseline. Boss Rush matches
all3000 video hashes, with the same2990updates/3000frames, zero drops,
remaps or wheel fallback, and successful reset release. Stack probe retains
11180-byte minimum gap, zero overlap in83676400 sampled boundaries.
Normal/BC/Rush speed gates still report the known incomplete full-speed
requirement; those exits are not hidden as passing60FPS checks.

All test jobs terminal. Sources/ROMs/profiles/results and aggregate evidence:
`.local/bc-body-paired-native/verified.json`.
Remaining measured scene-only CPU budget deficit is30.7404% on average and
57.4797% at the peak, before outer input/VBlank/DMA work. Full natural4P
completion and sustained60FPS/100% speed remain incomplete; goal active.

### Paired shot-bound native trial rejected — 2026-10-05

Previous turn classified as progress: native paired body bounds retained
with full regression evidence. This turn tested the nearby party_shots_far
predicate as a two-register native block, streaming X then Y, preserving
word-sized radius sums, byte bounds and16-bit position-plus-radius wrap.
No caller gates, collision order or tasks changed. No prior jobs live before
building candidate31a5cd3b65283d916b422faf381bb0b1e6b438d974e7f5a68087fbc78549dc24.

Native original-formula comparison passes1571840 queries:1048576 across
both axes/all16-bit positions with half forcing X near, plus523264 dense
queries over positions0–1023 and every radius sum0–510, including dirty
coordinate fractional bytes. Full4P replay matches72529 canonical states;
solo matches160172. Selected4P route marginally improves109365→109326frames
and R4 mean1293741.799→1293337.423, but profile span2023→2024 and worst
inclusive window2024→2025 (29.62962963FPS) regress. Solo remains exactly
167235frames, R6 mean907292.841/span1604. Canonical scene comparison is not
full original-phase machine equivalence.

Rejected this mixed marginal change; it does not improve the primary worst
window. All scratch/replay jobs terminal before restoring source and
rebuilding. Exact retained body-bounds ROM SHA verified:
af83c64b4b8e4b46521304e3fdf3492d8b0aec8ddb9521239d9f99949e0b6f42.
Evidence/source/ROM archives/native probe/profiles:
`.local/bc-shot-paired-native/rejected.json`.
Retained worst sustained4P remains29.64426877FPS. Previously verified
12 Home combinations and Normal/Rush regressions still apply to this exact
ROM. No new production change retained. Full natural4P completion and
sustained60FPS/100% speed remain incomplete.

### Projectile scan cost and lifetime audit — 2026-10-05

Previous turn classified as progress: paired shot predicate measured and
rejected, retained body-bounds ROM restored. This turn performed a read-only
instruction/mutation audit before attempting shared traversal metadata.
Matching current ELF and R4 instruction histogram confirm selected weapon
state/empty-span/traversal blocks cost30631034 core ticks across1000scenes
(2.3676% of whole scene), and corresponding draw blocks30823366 (2.3825%).
These totals exclude live task dispatch, mapping, simulation and sprite
emission. Even deleting the entire draw traversal at zero replacement cost
would leave mean1262918.433 ticks versus896040 budget; a real implementation
still needs live-state checks, list maintenance and traversal. This bounds
the possible benefit and rules out treating scan sharing as the60FPS solution
by itself. Evidence and exact annotated instruction ranges:
`.local/bc-projectile-scan-budget/audit.json` and matching disassembly.

Source lifetime audit identifies a correctness constraint for a possible
render list. Ordinary/returning/charged/option projectile births occur before
the weapon traversal, but actor-pass pickups can create option bodies in
slots28/29 afterward. Contacts can also change states after traversal.
A candidate ordered list for slots0–27 would need live-state rechecks and
separate live handling for slots28/29. Entering/checkpoint/waiting/continue
and stage early-return paths need explicit validity or fallback. Existing
BcShotIndex cannot simply be retained: it excludes dying records, resides
on actor-loop stack, and its pointer is restored before rendering.
A new list is only a candidate; no production implementation or performance
gain is claimed. No current test jobs were running and no ROM rebuild occurred.

Release remains exactlyaf83c64b4b8e4b46521304e3fdf3492d8b0aec8ddb9521239d9f99949e0b6f42.
Worst verified sustained4P remains29.64426877FPS. Full natural4P completion
and sustained60FPS/100% speed remain incomplete.

### Shared weapon/draw traversal prototype rejected — 2026-10-05

Previous turn classified as progress: instruction cost and mutation lifetime
audit established a specific next experiment. Built a per-scene four-owner
ordered draw-list prototype, collecting ordinary slots0–27 during the existing
weapon walk and appending live-read slots28/29 plus a sentinel. Renderer
rechecks state, retains triple grouping/submission order, and falls back to
its normal scan without a current list. Scene entry invalidates lists, so
checkpoint/entry/waiting/early-return paths cannot reuse prior-frame lists.
Repeated owners replace their list; metadata is512bytes outside gameplay state.
Standalone rules use an optional weak collector binding.

Candidatef9bb83547ccd408cd283f84e7c2304e9e1614a651b699b19882d927ef6480b8f
passes2400 host draw pools/37527 ordered sprites/600 strips, and2400 further
post-collection mutation/reset/eviction pools/33722sprites/343strips.
589824 native cached-renderer cases pass exact flip bits/coordinates,
unknown-art handling and unchanged inputs. Full canonical scene replays
match72529 selected4P states and160172 solo states. These checks do not
claim full cross-build original-phase RAM/video identity.

Rendering exclusive ticks improve149686166→145775168, but player-step
cost rises238895944→294313698; stack-operand instructions specifically
rise39491004→93600626. This compiler/register cost outweighs the saved
scan.4P route regresses109365→112950video frames; R4 mean
1293741.799→1347249.386 and span2023→2032. Worst inclusive window becomes
2044frames at18522–19522 (29.35420744FPS). Solo167235→168611frames;
R6 mean907292.841→944571.607/span1604→1778. Rejected.

A follow-up restrict qualifier explicitly declaring disjoint collector storage
produces a byte-identical ROM to the rejected variant. No duplicate replay
was run for identical machine code. Both variants are archived under
`.local/bc-projectile-draw-list/rejected.json` and
`.local/bc-projectile-draw-list-restrict/rejected.json`; stack-cost evidence
is in the former folder's `player-stack-cost.json`.

All test jobs completed before each restoration. Restored all four game
files with fresh modification times and rebuilt; exact retained ROM SHA:
af83c64b4b8e4b46521304e3fdf3492d8b0aec8ddb9521239d9f99949e0b6f42.
No draw-list metadata/API/source remains in production. Retained paired body
bounds and its12-menu/Normal/Rush evidence remain applicable. Worst retained
sustained4P stays29.64426877FPS. Full natural4P completion and sustained
60FPS/100% speed remain incomplete.

### Returning-weapon-only outlining rejected — 2026-10-05

Previous turn classified as progress (shared draw-list trial measured and
rejected). Prior evidence ruled out repeating whole live-dispatcher and
ordinary-shot outlining. Tested only native noinline on bc_return_step;
source task semantics/ordering and ABI remained unchanged. Candidate
651722b12a14cc04f40b521fd5629b302949372fe4f315d1071338c59b871035
adds a520-byte helper while player code grows9180→9196bytes.

Host comparisons pass60000 weapon updates,6000 charge edges,20000 stationary
cases and32768 option records. Those host checks exercise unchanged portable
code; actual native evidence is the full scene-paced replays, matching72529
selected4P and160172 solo canonical states.4P regresses109365→110465frames,
R4 mean1293741.799→1315675.368/span2023→2032. Player exclusive ticks decrease
238895944→236548270, but separate return helper adds23855860: include both
rather than mistaking the player-only attribution for an improvement.
Worst window2033frames/29.51303492FPS at25998–26998. Solo167235→167480,
R6 mean907292.841→912061.962/span1604→1630. No full machine/video cross-build
claim follows from the canonical scene comparison.

Rejected; all replay jobs terminal before restoring source and rebuilding.
Exact retained SHA verified:
af83c64b4b8e4b46521304e3fdf3492d8b0aec8ddb9521239d9f99949e0b6f42.
Evidence and matching before/candidate sources/ROMs/profiles:
`.local/bc-return-step-outline/rejected.json`.
No new production change retained. Worst retained sustained4P stays
29.64426877FPS; full natural4P completion and sustained60FPS/100% speed
remain incomplete.

### Recorded Round6 death cause and scrolling-aware natural4P trial — 2026-10-05

Previous turn classified as progress (returning-step outlining measured and
rejected). Investigated the last Player3 death in the completed rapid-fire
forecast campaign using its exact archived6df234 ROM and all77632 recorded
controller frames. A hash-pinned read-only opcode watch enabled at tick52620
observed state128→64 at PC0x5bf0, tick52626/video frame77470, after67181
sampled instructions. Archived disassembly identifies the player control
terrain-crush write, followed by control sound3; this was not an enemy-contact
state write. Watch removed, the remaining recorded inputs replayed to matching
full endpoint RAM/CPU/VRAM/pixels. Evidence, watch source, instruction excerpt
and screenshot: `.local/bc-r6-death-audit/verified.json`. This establishes the
recorded death path, not a blanket full-port fidelity verdict.

That campaign used stationary-camera terrain prediction. The existing
scrolling predictor passes20000 current production-C lookup/stationary/scroll
comparisons including fractions, wrap and crush. Started a natural selected
Home4P campaign on retainedaf83c64b4b8e4b46521304e3fdf3492d8b0aec8ddb9521239d9f99949e0b6f42
with --scroll-prediction enabled, plus existing rapid-fire forecast,12-update
R4/R8/R9 boss horizons, direct boss aiming, pickup seeking and turret lanes.
Seven starting lives selected through the real Options menu; real continues
allowed; no protection, seeded health/weapons, forced kills or authoritative
save-state restoration. No pilot or cartridge source changed this turn.

LIVE campaign session78881/PID72348 confirmed by process inspection and same
session poll. It entered Round1 at tick19/frame3051, lives[6,6,6,6]. Source,
ROM and pilot archived in `.local/bc-natural4p-scroll-aware/baseline`;
metadata/run arguments evidence in `run.json` and `campaign.log`.
Do not rebuild release while this campaign or its eventual independent
controller replay is live. At terminal, inspect result and replay recorded
inputs independently; verify ending only if actual final_clear occurs.
No new survival advantage or full4P completion claimed while running.
Worst verified sustained4P remains29.64426877FPS;60FPS/100% speed and full
natural4P completion remain unfinished.

### Isolated performance build validated (2026-10-05)

The preceding answer-only turn restated timing; it made no optimization
progress. Revalidated the live campaign by PID72348 (CPU time advancing),
now at Round4 tick30000 with lives[5,3,3,6]. Production remains af83c64b.
A clean build in `.local/bc-isolated-build` is byte-identical to production.
Its copied QA tools use that workspace's sources/ELF and the absolute pinned
SIDEARMS_CORE path. The independent scene-paced replay produces byte-identical
scene-record.json, scene-cycles.npy and profile.json:72529 canonical states,
109365 display frames, R4 mean1293741.799 ticks/span2023. Evidence:
`.local/bc-isolated-build/verified.json`. This validates isolated candidate
testing while the natural campaign keeps the production ROM fixed.

Started an actor-render candidate that computes the 16/32px sprite origin
offsets once per draw pass rather than subtracting the extent for every
actor. Host cache differential passes1200updates/4633submissions and
256synchronized updates/6725submissions. Native full-route replay is running
under session38004; no speed gain or retention is claimed yet. Candidate
sources/ROM are archived in `.local/bc-actor-origin-offsets`.
60FPS/100% speed and natural full4P completion remain unverified.

### Actor origin-offset candidate: native route gains (2026-10-05)

Isolated candidate fecc853fbce3e8e63e34b829e485a11c14ab798269ac1d939969dddd281519a0
moves sprite extent subtraction into the two per-pass origin offsets. The
production af83c64b ROM/source remains fixed for the live natural campaign.
Candidate full scene-paced replays match72529 multiplayer and160172 solo
canonical states. Four-player route109365→109254 display frames; R4 mean
1293741.799→1292047.337 ticks, actor-draw attribution115043390→113373610.
Worst inclusive1000-update window remains2024frames at25998..26998,
29.64426877FPS. Solo167235→167121frames; R6 mean907292.841→904944.446,
span1604→1589. Protected R8 ordinary1292→1291 and charged1242→1238;
both match1000 simulation states and pass independent replay.

Extended tools/qa_bc_actor_cache.py with4608 submissions at signed-word
coordinate/origin boundaries. Baseline and candidate pass these plus the
existing1200updates/4633submissions and256synchronized updates/6725submissions.
Home12 dialog/cancel/launch combinations pass. BC40 openings save18frames
net:8 improve,29 tie,3 regress one frame; exit1 reflects missed speed targets,
not measurement errors. Stack sample:11180byte minimum gap,zero overlaps,
83221686 sampled boundaries. Normal40 comparison still running(session89611);
Boss Rush must run after it finishes because they share scratch files.
Candidate is archived but not promoted; `.local/bc-actor-origin-offsets/run.json`
tracks evidence and pending checks. Do not rebuild either production or the
isolated ROM while its respective live tests are using it.

Natural scrolling-aware4P campaign PID72348 is confirmed live at Round4
boss tick34000, lives[2,2,0,3]; no full-clear claim. The full60FPS/native port
objective remains incomplete. This turn made progress through isolated-build
validation, measured candidate gains and stronger renderer boundary coverage.

Actor-origin candidate regression checks are now terminal. Normal40 timings,
40040 state hashes and ordered sprite-render hashes match baseline. Boss Rush
has identical3000 video hashes,2990updates/3000frames,zero drops/remaps/wheel
fallbacks, and releases wheel allocations on reset. Its exit1 remains the
known speed shortfall. All candidate jobs are terminal; evidence aggregated
in `.local/bc-actor-origin-offsets/verified-candidate.json`. Candidate is
validated for promotion after the unchanged production campaign and its
independent controller replay finish. It is not yet the retained release.
Current production SHA remains af83c64b; worst sustained4P remains29.6443FPS.

### Combined native shot-index eligibility trial (2026-10-05)

Previous turn made progress: isolated actor-origin candidate validated across
canonical routes, R8 replay, renderer boundaries and mode regressions. It
remains staged, not promoted, while production campaign PID72348 is live.
This turn layers one native-only change on that candidate: bitwise OR of the
shot flag bit and two coordinate high bytes replaces three short-circuit
eligibility gates. All reads address valid nonvolatile shot bytes; eligibility,
ordered slots and index bounds are unchanged. GCC additionally removes an
index temporary stack spill/reload from shot_index_live. Production stays
af83c64b. Trial ROM54111af465ed0a3419b70b6bc1a35684c88711abf7ebbd2295fd181473b8328d;
baseline candidate fecc853f. Sources, ROM, disassembly and metadata are in
`.local/bc-shot-index-or`. Native4096 complete-index comparisons pass with
weapon bytes and sentinels intact, including dirty padding, coordinate high
bytes and state/flag/radius variation. Multiplayer and solo canonical route
timing are running (sessions20179/40000). No speed gain is claimed yet.

Combined shot-index trial matches72529 multiplayer states, with route frames
109254→108952 versus the staged origin-offset baseline; R4 mean1292047.337→
1287704.061, worst inclusive window2024→2022frames (29.6735905FPS), maximum
scene2105278→2098460ticks. The indexed helper attribution41521396→37255372.
Solo160172states match,167121→166979frames; R6 mean904944.446→901468.183,
span1589→1574. R8 ordinary1291→1289 and charged1238→1235, each with1000
matching simulation hashes and independent replay. Home12 passes. BC40
saves13frames net:10 improve,29 tie,one regresses2frames; no measurement error.
Stack gap11154bytes,zero overlaps over83129274 sampled boundaries. Native
probe and route/R8/BC40/Home/stack sessions are terminal. Normal40 session49671
remains live; run Boss Rush after it finishes. Production remains unchanged.
Natural4P campaign PID72348 passed Round4 and is alive inRound5 tick42000,
lives[4,1,3,255]; the fourth player is out. No full natural4P clear is claimed.

Shot-index candidate checks are all terminal. Normal40 matches timings and
all40040 state/render hashes. Boss Rush matches all3000 video hashes, remains
2990updates/3000frames with zero drops/remaps/fallbacks and successful reset
allocation release. Exit1 reports its known speed shortfall. Evidence aggregated
in `.local/bc-shot-index-or/verified-candidate.json`; the selected isolated
candidate is54111af4, including BOTH origin-offset and eligibility changes.
`.local/bc-isolated-build/selected-candidate.json` points to its full source,
header and ROM/ELF archive. No further candidate tests are pending. Promotion
must follow completion of the live production campaign and its independent
controller replay. Production remains af83c64b. No full-speed or full natural
four-player completion claim is made. This turn made measured optimization
progress: candidate worst sustained4P29.6736FPS, retained production29.6443FPS.

### Returning velocity-pair trial (2026-10-05)

Previous turn made measured optimization progress: validated native shot-index
eligibility candidate54111af4 (including staged actor-origin offsets). It remains
selected for later production promotion. Production campaign PID72348 is still
live; it has cleared R1–R6 and reached R7 tick74000, lives[3,255,2,255]. No full
natural4P clear claimed. Production af83c64b remains fixed through campaign
and eventual independent controller replay.

Native disassembly shows returning-shot steering calculating two table element
addresses and writing adjacent signed16-bit velocities separately. A new
isolated trial reads/writes them as one alias-safe, word-aligned32-bit value,
with static assertions for width and contiguous vx/vy. The portable path is
unchanged. Full native returning-shot differential compares16384 complete
records and active counts, covering target offsets, wrapped source origins,
launch delays, animation/timer and dirty record bytes; all pass in1098 video
frames. Probe extracts both actual before/after functions, compiled O3 for
68000, and runs on the pinned core. Candidate ROMc1aacc6118ae92a5e3102b67712e1de01f01a54a6e2adc843d3a8566ebb0dbae.
Evidence `.local/bc-return-vector-pair`; canonical multiplayer/solo timing
sessions74082/76985 are still running. No speed or retention claim yet.

Returning velocity-pair trial rejected:72529 multiplayer and160172solo canonical
states match, but4P108952→109327frames,mean1287704.061→1291911.404,worst2022→
2023frames; solo166979→167129frames,R6mean901468.183→905136.575,span1574→1594.
Both jobs terminal. Exact selected isolated54111af4 restored by rebuilding;
production unchanged af83c64b. Evidence `.local/bc-return-vector-pair/rejected.json`.
No broad regression rerun for rejected source.

The natural scrolling-aware4P campaign is now terminal, confirmed by missing
PID72348 and successful completion poll of session78881. It cleared R1–R7,
lost inR8 at tick87825, recorded133249gameplay frames and returned toHome.
Full campaign remains unverified. Independent controller replay has started;
keep production unchanged through its completion. This run's endpoint must
not be confused with a full-campaign clear or all-four-player survival.

Terminal campaign independent replay session48927 is running. Also capturing
its larger native canonical route before replacing production (session97265,
`.local/bc-natural4p-seven-round-corpus/capture`). This newly reached R7/R8
route should be replayed on selected candidate54111af4 before promotion.
Release remains frozen through these production-ROM jobs.

Natural4P run independent controller replay now passes136264total input frames
with zero authoritative save-state restores. Full endpoint RAM/CPU/VRAM/pixel
checkpoint matches; this is endpoint verification, not every-frame pixel audit.
Run losesR8 at87825ticks with48deaths, real continuesP3tick34418/P1tick35768,
and observed Home return. Aggregated `.local/bc-natural4p-scroll-aware/verified.json`.
Canonical capture terminal:87845 states at136264frames. A NEW slower sustained
window is2091inclusive frames for1000updates,ticks11224..12224=28.69440459FPS
in retained af83c64b. This supersedes29.6443FPS as worst observed retained
performance; differing natural controller inputs reach a different workload.

Comparative scene-paced replays on that same new corpus are running: baseline
production session72921 and selected isolated54111af4 session31647, each with
1000call profile at11224 and workload trace. Outputs are baseline/ and candidate/
in `.local/bc-natural4p-seven-round-corpus`; run.json records both handles.
Keep BOTH builds fixed until these jobs terminate. Inspect all87845 canonical
states, total frames, worst windows and profile before promoting the two staged
optimizations. No selected-candidate speed number for this new workload yet.
Goal remains active: full natural4P clear and sustained60FPS still unproven.

### Promote actor origins and combined shot-index eligibility (2026-10-05)

Both longer-route comparative jobs72921/31647 finished successfully. All87845
canonical states match. Scene-paced baseline136290frames→candidate135424
(866saved). This differs from original video-paced capture136264 because
scene-paced input follows completed native updates. R2profile11224..12224
mean1471367.863→1463046.515ticks,maximum2245971→2231138;span2090→2086.
Worst inclusive1000-update window2091→2087frames,28.69440459→28.74940105FPS.
This is the new retained worst measured sustained workload, not an instantaneous
minimum or60FPS claim. Comparisons include R7 and earlyR8 newly reached by the
natural run. Both builds stayed fixed until all jobs completed.

Copied only staged src/bc_actor_draw.c and src/bc_rules.c into production and
rebuilt/finalized. Exact SHA54111af465ed0a3419b70b6bc1a35684c88711abf7ebbd2295fd181473b8328d
matches the already-tested isolated cartridge. The paired returning-velocity
trial remains rejected and is absent. Retained changes are per-pass16/32px
sprite origin offsets and bitwise-combined native shot-index eligibility.
Existing tests for this exact cartridge cover older72529-state4P and160172-state
solo routes, R8 ordinary/charged1000state+independent replay samples, all12
Home modal/cancel/launch combinations, BC40 timings, Normal40 state/render
comparisons, Boss Rush3000video hashes and reset release, native4096 complete
indices, actor coordinate-boundary submissions, and bounded stack samples.
These are regression evidence, not full-game60FPS proof.

Production before/candidate sources, ELF/ROM/symbols/headers and aggregated
verification: `.local/bc-native-index-render-retained/verified.json`.
New-corpus comparison: `.local/bc-natural4p-seven-round-corpus/verified.json`.
Selected isolated pointer updated to promoted; all campaign/replay/build jobs
are terminal. Previous turn made progress through rejected-trial evidence,
independent natural replay, new coverage and slower-workload identification;
this turn completes actual production promotion.

New R2workload audit is saved as r2-workload.json. In1000scene-entry samples,
ordinary live straight shots12560 and expanding9076 dominate weapon occupancy;
no returning shots occur. Dying ordinary records total4776 and options1000.
These are occupancy, not task counts. Player/weapon task costs287353430ticks
in this profile. Even excluding outer input/VBlank/DMA, mean scene cost needs
38.7552% reduction and peak59.8393% to fit896040ticks. Optimization should
focus on ordinary player-shot work in this newly verified worst route.
Full natural4P campaign clear and sustained all-mode60FPS/100% speed remain
unfinished; the active goal is not complete or blocked.

### Two-register ADDX projectile carry trial (2026-10-05)

Previous turn made progress by promoting exact54111af4 after expanded-route
validation. New retained R2instruction profile identifies ordinary shot motion
among the repeated player-task costs. In rotated beam storage, shifted velocity
has low byte zero. After ADD.L setsX/C, ADDX.B value,step computes the old
padding byte plus carry in step's low byte, modulo256. It replaces the existing
BCC/conditional ADDQ.B/MOVE.B sequence using the same two data registers.
Masking, position write, bound wrap and X-before-Y retirement remain unchanged.
This differs from the old rejected three-register ADDX prototype.

Isolated trial db2edad48f204c660147fca173a393ccf938a018fa423939c88db598d32abab3
passes1310720 native motion/boundary cases, every signed velocity at20source
fraction/boundary/padded positions; position-only reference also matches.
Disassembly confirms two-register ADDX.B. Evidence `.local/bc-beam-two-register-addx`.
Production stays54111af4. Three native canonical replays running: newR2route
session96623, oldR4route81096, solo46004. No speed/retention claim yet.

### Retained two-register beam carry (2026-10-05)

Production rebuilt and finalized to exact tested db2edad48f204c660147fca173a393ccf938a018fa423939c88db598d32abab3,
replacing54111af4. Only the native beam_axis carry sequence changes, using
ADDX.B with the shifted velocity's known-zero low byte. No CPU emulation,
wave/weapon/hitbox reductions, skipped updates or rendering omissions added.
Native1310720cases pass. All320546 canonical scene comparisons across the
three routes match (87845new4P,72529old4P,160172solo). These routes overlap;
the count is comparisons, not distinct gameplay coverage.

New4P route135424→135113frames,R2mean1463046.515→1458966.544ticks;
profile span2086→2085,maximum2231138→2229843. Worst inclusive window2087→2086,
now ticks11218..12218,28.76318313FPS. Old4P108952→108769frames,R4mean1287704.061→
1285381.580,span2021→2020,worst2022→2021 at25997..26997. Solo166979→166924frames,
R6mean901468.183→899465.476,span1574→1565.

Short workload results are mixed and are not hidden: protected R8ordinary
1289→1292frames (mean852908.056→852620.853) and charged1235→1236(mean770233.660→
769715.506), with1000states matching each and independent replay passing.
BC40 openings net5frames worse:one improves1,four regress1–2,35tie. Retained
because all three long routes and both worst sustained sections improve,
with lower CPU means across every profiled workload. This does not satisfy
all-workload60FPS; the short timing regressions remain a limitation.

Home12 modal/cancel/launch pass. Normal40 timings and40040 state/render hashes
match. Boss Rush all3000video hashes match,2990updates/3000frames,zero
sprite drops/remaps/wheel fallbacks and successful reset allocation release.
Stack minimum gap11154bytes,zero overlaps across83057540 sampled boundaries.
All jobs terminal before production build; exact SHA match makes the isolated
verification applicable to release. Full before/candidate source/ROM/ELF and
aggregate `.local/bc-beam-two-register-addx/verified.json`. Current worst observed
sustained4P28.7632FPS. Goal remains active;60FPS and full natural4P clear not proven.

### Coordinate-contribution terrain tables rejected (2026-10-05)

Previous turn made progress by retaining two-register ADDX after native and
campaign checks. This turn investigated replacing terrain coordinate masks
and shifts with ROM lookup tables, preserving numeric low-nibble collision
values and original cells/attributes pointers. No game source or ROM changed.

First prototype: two256-word tables combine cell-index bits and subcell bits,
1024bytes total. All655360native queries across10 source rounds and12288
additional pointer/flag cases match. Isolated candidate cost1734082560ticks
versus reference1688207360,2.7173913% slower. Second prototype: two128-word
tables contribute only cell-index bits, with existing subcell arithmetic,
512bytes total. Same coverage passes;2101084160ticks,24.4565217% slower.
Both are rejected before gameplay integration. Reference/direct control costs
match prior terrain probes. Probes use noinline/noclone O2 lookup functions;
these are callee costs, not whole-game speed measurements. No claimed speed
benefit from the extra tables. The compact existing coordinate bit arithmetic
remains in production.

Evidence `.local/bc-terrain-coordinate-lut/rejected.json` and
`.local/bc-terrain-coordinate-lut128/rejected.json`, with generated C, native
ELF/ROM, disassembly/profile and original source map data. Both jobs terminal.
Retained ROM verified unchanged db2edad48f204c660147fca173a393ccf938a018fa423939c88db598d32abab3.
Worst measured sustained4P remains28.7632FPS. The turn adds evidence ruling
out these table arrangements; full60FPS/100% speed and natural4P clear remain
unfinished, with meaningful optimization work still available.

### Word-only beam bound trial (2026-10-05)

Previous turn made progress by ruling out two slower coordinate-table terrain
prototypes with native numeric-query evidence. Retained production remains
db2edad4. Current isolated trial27cd786328a3e7e4ad4f8803fb79717dbd685792eb34f272ec43a84cc56fe65a
moves the position write and SWAP/word-add bound extraction into the existing
native carry asm. It preserves full stored position before reusing the register
for its integer word and carry-byte sum. The source boundary comparison still
wraps to16bits. All1310720 native motion/boundary/padding/velocity comparisons
pass. Disassembly removes CLR.W before SWAP, but introduces MOVE.W in some
paths; no net CPU gain is presumed from instruction inspection alone.

NewR2route and solo replays are running(sessions63879/91302). Evidence/source,
ROM/ELF/headers/native probe and player disassembly in `.local/bc-beam-word-bound`.
Production unchanged; no retention/full-speed claim pending measurements.

Word-bound fusion trial rejected. New4P87845canonical states match but route
135113→136312frames,R2mean1458966.544→1472010.995ticks,span2085→2088,worst
inclusive2086→2089 at11224. Solo160172states match,166924→167138frames,
R6mean899465.476→904350.657,span1565→1590. Moving the position output into
asm did not yield a measured benefit; the native equality probe alone was
insufficient performance evidence. No wider mode regressions run for this
rejected cartridge. Both route jobs terminal. Restored isolated source with
fresh timestamp, rebuilt/finalized to exactdb2edad4, matching unchanged
production. Evidence `.local/bc-beam-word-bound/rejected.json` and source/ROM/
ELF/native probe/player assembly. Current retained worst sustained4P28.7632FPS.
This turn made progress by testing and rejecting the fusion; full-speed and
full natural4P completion remain unfinished, with no external blocker.

### Player output alias contract trial (2026-10-05)

Previous turn made measured progress rejecting the slower word-bound fusion
and restoring exactdb2edad4. Current trial adds __restrict__ only to the
bc_player_step_into event output parameter. Production callers were inspected:
party output is its separate result.players[i], the single-player runtime
uses a local BcPlayResult, and the wrapper uses a local frame event. Player
state, terrain and animation data do not overlap these caller-owned outputs.
No task, state-machine or order changes are intended. The compiler emits a
new ROM0c8bf507486cc3f90270f3c7452f4a8dccec7572600ad60c287632ac0203b826;
source/ROM/ELF/header/player-assembly evidence is `.local/bc-player-output-restrict`.
Canonical native routes are running: newR2 session48643,oldR4 session21223,
solo88415. Retained production remainsdb2edad4; no speed/retention claim yet.

Player output-only restrict trial rejected: all320546 canonical comparisons
match, but new4P135113→135795frames,R2mean1458966.544→1467609.213,span2085→2086;
old4P108769→109120,R4mean1285381.580→1290677.878,span2020→2022; solo166924→167094,
R6mean899465.476→902949.530,span1565→1585. Host original task fixture also passes
1680player/2687common-enemy/1677trail updates with3deaths/checkpoints. Evidence
`.local/bc-player-output-restrict/rejected.json`; all its jobs are terminal.

Follow-up adds restrict to both event and player inputs. Actual production
player storage is distinct from event, terrain and animation data; no ABI
layout change. Native ROM65959ee1d381119e3fec8b5b6c6eac9f382aa1977ce8fb54149fef58cc244930
differs from output-only, so it requires its own measurement. Canonical route
sessions newR270026,oldR471216,solo47677 running; evidence/metadata in
`.local/bc-player-both-restrict`. Production remainsdb2edad4. Isolated source
currently contains this experimental annotation; do not promote or rebuild
while the three tests are live. No gain/full-speed claim for this follow-up.

Both-pointer restrict follow-up also rejected. All320546 canonical comparisons
match, but new4P135113→135584frames,R2mean1458966.544→1465597.007,span2085→2087;
old4P108769→109033,R4mean1285381.580→1288721.637,span2020→2022; solo166924→167049,
R6mean899465.476→902483.281,span1565→1578. Original host task fixture passes
1680player/2687common-enemy/1677trail updates and3deaths/checkpoints. No claimed
performance gain from the alias annotation. No wider mode reruns for either
rejected cartridge. All jobs terminal; restored isolated bc_player.c with fresh
timestamp and rebuilt to exactdb2edad4 matching unchanged production.

Evidence `.local/bc-player-output-restrict/rejected.json` and
`.local/bc-player-both-restrict/rejected.json`. Neither annotation remains in
production or selected isolated source. The turn made measured progress by
ruling out both compiler-contract variants; this is not full-speed completion.
Retained worst sustained4P28.7632FPS; full60FPS and natural4P clear remain open.

### Two-entry BC small-sprite repeat trial (2026-10-05)

Previous turn made measured progress rejecting both player restrict annotations
and restoringdb2edad4. Current work examines projectile rendering. Existing
BC lookup_repeat remembers one successful small-sprite key/attribute and
invalidates it at spr_bc_begin; lookup pins the referenced slot for the frame.
Trial adds one prior successful key/attribute (4bytes), also invalidated at
BC frame begin. A second-key hit returns its already-pinned attribute without
changing order or submission data. Successful uncached lookup shifts the prior
entry; failed lookup leaves both untouched. Normal's ordinary lookup path and
large-sprite cache are unchanged in source. No resident art, entity or drawing
work is removed.

Isolated ROM69e73856967af16af7c6e98d0aecbb5a6a56ee8fc9ec2929082a53e6f7e421f9,
source/ROM/ELF/headers at `.local/bc-small-repeat-two`. Native canonical routes
running:newR2session14524,oldR499195,solo80434. These compare simulation and
timing; independent pixel/cache regression checks are still required if the
candidate earns retention. Production remainsdb2edad4. No speed claim yet.

Two-entry small-sprite shortcut rejected for worsened sustained4P workloads.
All320546 canonical simulation comparisons match; pixel equivalence was not
claimed or separately audited for this rejected candidate. Results are MIXED:
new4P total135113→134360frames improves, but R2profilemean1458966.544→1468013.841
and span2085→2092 worsen. Old4P108769→109200frames,R4mean1285381.580→1296297.457,
span2020→2024 worsen. Solo166924→166741frames improves,R6mean899465.476→885621.548,
span1565→1492 improves. The cache benefits some workloads but misses the
multiplayer bottleneck priority; do not summarize it as uniformly slower.
OldR4projectile draw attribution149686166→155203454 and actor draw116691806→
118441120 show added renderer cost. No broad mode/pixel reruns for rejection.

All three jobs terminal. Restored sprites.c with fresh timestamp and rebuilt
to exactdb2edad4 in isolated workspace; production remained unchanged.
Evidence `.local/bc-small-repeat-two/rejected.json`. Previous turn made
progress rejecting two compiler annotations; this turn adds measured cache
tradeoff evidence. A separate potential next experiment is selecting constant
solo/multiplayer projectile loops once per draw call, eliminating the dynamic
packing branch per slot; it has not been implemented or measured here.
Retained worst sustained4P28.7632FPS. Full60FPS/100% speed and natural full4P
completion remain open; no external blocker or completion claim.

### Constant solo/multiplayer projectile loops trial (2026-10-05)

Previous turn made measured progress identifying mixed two-entry-cache gains
but rejecting its worse sustained4P performance. Current isolated change keeps
all sprite mapping/grouping/submission logic in one always-inline core and
selects a noinline solo(pack0) or multiplayer(pack1) wrapper once per draw.
The existing public entry remains noinline and dispatches using the same
player-limit condition. This removes a dynamic packing condition from each
slot; no artwork, order, empty-slot scan or packed-triple criteria change.

Host differential passes2400pools/37527ordered sprites/600packed strips,
including positions, flips, fallbacks, end slots, dirty padding and unchanged
simulation bytes. Native symbols confirm separate constant loops. Trial ROM
0f93ad0cf58d73a2bcf1c019bcb2d4ed76a3371f150aa217a03df48024a03b4f;
archive/metadata `.local/bc-projectile-fixed-pack`. Three canonical native
replays running:newR2session57105,oldR454254,solo24749. Production unchanged
db2edad4. No speed or retention claim yet; full60FPS goal remains unfinished.

### Constant projectile loops retained (2026-10-05)

The intervening user-answer turn was a status-only no-progress turn. Resumed
Normal40 session47868 and confirmed terminal; subsequently completed Boss Rush
session50581 before any rebuild. All40 Normal cases match baseline timing and
state/render hashes. Rush matches all3000 video hashes,2990 updates/3000frames,
zero sprite drops/remaps/wheel fallbacks, and released allocations on reset.
These are equivalence checks, not proof that either mode is universally60FPS.

Retained the constant solo/multiplayer projectile loops: longer4P87845 states
match,135113->134748 frames; worst1000 updates2086->2083 display frames,
28.76318313->28.80460874FPS at tick11218. Older4P72529 states match,
108769->108561 frames; worst2021->2020. Solo160172 states match,
166924->166900 frames. Native renderer checks exercise1P and4P with589824
cases each; host differential2400 pools/37527 ordered sprites/600 strips.
These renderer probes verify submissions/coordinates, not full campaign pixels.

Short-fixture tradeoff: R8 ordinary1292->1285 frames; charged1236->1237,
both1000-state matches and independent replay verified. BC40 is net5 frames
worse (one case improves1, five regress1-2,34tie), with known speed failures.
Home all12 modal combinations pass. Stack gap11154 bytes,zero overlaps over
83024926 sampled boundaries. No simulation or rendering work was removed.

Production rebuilt exactly to tested0f93ad0cf58d73a2bcf1c019bcb2d4ed76a3371f150aa217a03df48024a03b4f,
within4MiB. Evidence `.local/bc-projectile-fixed-pack/verified.json`; before and
candidate sources/ROM archived there. Extended native renderer QA with optional
--players and --output; default remains1P. Goal remains active: worst measured
sustained4P is28.80FPS, not60; natural full4P completion remains unverified.

### Shot-index coordinate order trial (2026-10-05)

Previous goal turn made progress retaining constant projectile loops. Current
turn first tested restrict index/body annotations; entire finalized ROM was
byte-identical to0f93, so removed them (evidence
`.local/bc-shot-index-restrict/rejected.json`). All production callers build a
separate stack index from weapon storage; no source/index overlap is required.

Next isolated trial stores X and updates X bounds before loading/storing Y
and its bounds. Native disassembly removes D2 push/pop from shot_index_live,
keeping the same rejection, slot order, count, bounds and half-size operations.
Native differential passes4096 complete indices including dirty coordinate
bytes, fractions, high-byte rejection, state/flag/radius variation, unchanged
weapons and index sentinels (6869 probe video frames). This is correctness
evidence, not a whole-game speed claim.

Candidate d09b0770a92c6d1e913651c0215649b4b65c57fc0edb5b01142fa57d01a1ea1d
is archived under `.local/bc-shot-index-coordinate-order/candidate`.
Long R2 four-player replay session55525 and full solo session82099 both
confirmed live by polling; do not rebuild isolated ROM while these run.
Results/logs/run.json under same evidence directory. Production remains0f93;
retention awaits measured route timing and canonical-state comparison. Goal
still incomplete at retained worst sustained4P28.8046FPS.

### Shot-index coordinate order replay evidence (2026-10-05)

Previous turn made progress implementing and native-checking the candidate.
All three canonical routes now terminal and matching:87845-state R2 route
134748->134499 frames, mean1453433.072->1449691.964, profile span2081->2074;
worst1000-update window2083->2075 at tick11218,28.8046->28.9157FPS.
72529-state R4 route108561->108390,mean1280829.606->1278223.240,
profile span2019 unchanged/worst2020 unchanged. Solo160172 states,
166900->166838,mean898826.663->897126.342,span1564->1559.
Host index/contact differential32000 scans/5336 contacts/2070 damaging hits
passes, including slot order. R8ordinary1285->1281 and charged1237->1236;
both1000-state matches and independent replays pass. BC40 net5 frames saved:
two improvements4/2,one regression1,37ties; no measurement errors but existing
speed failures remain. All12 Home combinations pass. Stack gap11154 bytes,
zero overlaps83027368 sampled boundaries. Normal40 session7947 still live;
Boss Rush must run after it finishes. Production unchanged0f93 pending those
mode checks. Evidence `.local/bc-shot-index-coordinate-order/run.json`.

### Shot-index coordinate order retained (2026-10-05)

Normal40 subsequently finished: all40 exact timing and state/render-hash
matches. Boss Rush session32130 then completed: all3000 video hashes match,
2990 updates/3000 frames,zero sprite drops/remaps/wheel fallback,reset releases
allocations. All candidate probes/replays/matrices are terminal. Promoted only
bc_rules.c and rebuilt production exactly to tested
 d09b0770a92c6d1e913651c0215649b4b65c57fc0edb5b01142fa57d01a1ea1d
within4MiB. Before/candidate full source and ROM/ELF/symbol archives saved.
Final evidence `.local/bc-shot-index-coordinate-order/verified.json`.
Retained worst sustained4P now28.91566265FPS; full60FPS/100% speed remains
unachieved, and natural full4P campaign completion still requires work.

### Native shot-index count load trial (2026-10-05)

Previous goal turn made progress retaining coordinate-order optimization.
First trial delaying triple-sprite X coordinate reads produced byte-identical
ROM; restored source, evidence `.local/bc-triple-late-coordinates/rejected.json`.
Next isolated change zero-extends index count using MOVEQ/MOVE.B rather than
compiler MOVE.B/ANDI.L. Resulting shot_index_live is four bytes shorter with
no additional register save; early-clobber output protects memory addressing.
Count increment, rejection, bounds and ordered index remain identical.
Native differential passes4096 complete indices including dirty bytes,
state/flags/radii, unchanged weapons and index sentinels.

Candidate80bfed25c8bef0e87a7a2174f69f5fad683db69b3123e48f0ba93cb3b084d034
archived under `.local/bc-index-count-moveq/candidate`; metadata run.json.
R2 four-player route session53728 and solo full route92218 are running.
Do not rebuild isolated ROM until both terminal. Production remainsd09b0770;
retained worst4P28.9157FPS. No candidate speed claim or goal completion.

### Count-load replay tradeoffs (2026-10-05)

Previous turn made progress implementing and native-checking MOVEQ count load.
All three long routes terminal with matching canonical states. R2four-player:
87845 states,134499->134360 frames,mean1449691.964->1448216.581,
profile span2074->2072,worst2075->2073 at11218=28.94356006FPS.
R4four-player:72529 states,108390->108317 frames,
mean1278223.240->1277248.518,profile2019/worst2020 unchanged.
Solo160172 states:166838->166846 (8frames worse),mean897126.342->896415.345,
profile1559 unchanged. CPU means improve, but frame scheduling gains are mixed.
R8ordinary1281->1293 and charged1236->1238; both1000 states match and
independent replay verifies. BC40net4 worse (two1-frame improvements,two
regressions4/2,36ties),no measurement errors; existing speed failures remain.
Host shot-index32000 scans pass; Home12pass; stackgap11154,no overlaps over
82960024 boundaries. All these jobs terminal. Normal40session43412 confirmed
live; run Boss Rush only after Normal terminal. Do not rebuild isolated ROM
while Normal runs. Metadata `.local/bc-index-count-moveq/run.json` includes
all results; retention undecided, production remainsd09b0770 at28.9157FPS.
Saved baseline100hottest instruction PCs to baseline-hot-instructions.json
for follow-up profiling; repeated weapon motion shifts and actor-common
register saves remain measurable. No claim of full60FPS or full4P clear.

### Native count load retained (2026-10-05)

Previous turn made progress collecting mixed route evidence. Normal40session
43412 now terminal: all40 timing/state/render-hash comparisons match exactly.
Then Boss Rush83665 completed:3000 video hashes match,2990 updates/3000frames,
zero drops/remaps/wheel fallback, allocations released on reset. All candidate
jobs terminal. Promoted only native count load and rebuilt production exactly
80bfed25c8bef0e87a7a2174f69f5fad683db69b3123e48f0ba93cb3b084d034,
within4MiB. Full evidence `.local/bc-index-count-moveq/verified.json` and
before/candidate source/ROM/ELF/symbol archives.

Decision prioritizes both long4P routes and R2 worst-window improvement;
all three long-route and bothR8 CPU averages fall. Tradeoffs explicitly
accepted: solo+8 display frames, R8ordinary+12/charged+2, BC40net4 worse.
This is not a universal frame-rate improvement. Retained worst sustained4P
28.94356006FPS. Full60FPS/100% speed and natural full4P clear remain unfinished.

### Party dispatch boundary trial and contact QA repair (2026-10-05)

Previous goal turn made progress retaining native count load. Current isolated
trial keeps party_common_dispatch out of line at O2 while retaining common
motion in bc_actor_common_into. Old common-entry work rejected a separate
party helper; this trial evaluates the current enlarged dispatch and caches.
The intended reduction in common register saves did not materialize: entry
still savesD2/A2-A4. Do not infer a benefit without route measurements.
Candidate33753f0b50c28ecf55afc19212582a6eac90201d1df29b4a2ce61d36b2fbcac1,
archive/metadata `.local/bc-party-dispatch-outline`.
R2route61871 and solo1191 confirmed live; do not rebuild their isolated ROM.

qa_bc_party_contacts.py initially failed its obsolete sizeof(Actor)==52
assertion, after preceding contact checks had passed. Replaced hardcoded size
with sizeof(BcActor) and offsetof(health_fraction) exported by a tiny compiled
C layout probe; checks actual ctypes/C ABI and keeps all gameplay assertions.
Updated tool passes against both retained production and isolated candidate:
exact1/1/1.5/2.25 bosshealth, fractional bars, protection/reuse, ordered damage,
single clocks, death ownership, pickups/options/retirement. This QA fix is
independently useful even if the gameplay experiment is rejected. Production
ROM remains80bfed25; worst sustained4P28.94356FPS,goal unfinished.

### Party dispatch outline rejected (2026-10-05)

Previous turn improved contact QA and started candidate routes. Both replays
now terminal and canonical states match: R2four-player87845 states but
134360->141027 frames,mean1448216.581->1495050.816,span2072->2111;
solo160172 states166846->166866,mean896415.345->897467.858,span1559->1565.
No register-save reduction occurred, and the additional dispatch boundary
increased cost. Rejected without broad mode QA; restored isolated source with
fresh mtime and rebuilt exact80bfed25c8bef0e87a7a2174f69f5fad683db69b3123e48f0ba93cb3b084d034.
Production unchanged. Evidence `.local/bc-party-dispatch-outline/rejected.json`.
The independently passing C/ctypes layout check in qa_bc_party_contacts.py is
retained. All jobs terminal; no pending ROM readers. Retained worst4P28.94356FPS;
60FPS/100% speed and full natural4P campaign clear remain unfinished.

### Paired player-body proximity trial (2026-10-05)

Previous turn made progress rejecting the slower party dispatcher and
restoring80bfed25 exactly. New isolated body_near_inline native predicate uses
D0/D1 for each ordered unsigned distance, preserving high-word actor pixels,
shifted player pixels, byte-wrapped radii (half+5/8), and X-before-Y rejection.
Host fallback unchanged. Unlike paired body-union bounds, this tests individual
player/actor proximity at existing call sites. No eligibility/order changes.
New tools/qa_bc_body_near_native.py passes1048576 native comparisons spanning
every16-bit coordinate and byte radius, close/far/extreme endpoints, fractions
and upper padding. This deterministic sweep is not full Cartesian coverage.
Probe elapsed8393frames; this is correctness evidence, not game speed evidence.

Candidate0999a7c52f5424e5f4c679069d4057a0b81a086fc12152820aa498da10d6acd7
archived under `.local/bc-body-near-paired/candidate`; run.json contains handles.
R2route67681 and solo11065 running; do not rebuild isolated ROM while live.
Production remains80bfed25 at worst sustained4P28.94356FPS. Goal unfinished.

### Paired proximity mixed route evidence (2026-10-05)

Previous turn made progress with candidate implementation and native boundary
probe. Baseline probe also passes1048576 cases (7677frames vs candidate8393);
these total harness times are not isolated predicate cost measurements.
R2 and solo canonical replays now terminal. R2matches87845states,
134360->134398 display frames (38worse),mean1448216.581->1447649.644,
profile2072/worst2073 unchanged (28.94356FPS). Solo matches160172states,
166846->166746 frames (100saved),mean896415.345->893932.788,
profile1559->1543. No retention decision yet: second4Proute83703 and
ordinary R8probe47472 running. Keep isolated ROM0999a7c5 fixed while live.
Production80bfed25 unchanged. If4P does not benefit, evaluate native proximity
only in solo common entry while retaining original party predicate. That is
an optimization possibility, not a completed or measured change. Full goal
remains60FPS/100% speed in all modes/1-4P and remains unfinished.

### Proximity solo-only alternative (2026-10-05)

Previous turn made progress obtaining mixed paired-proximity timings. Remaining
shared candidate0999a7c5 tests terminal: R4matches72529states,108317->108297
frames,mean1277248.518->1276633.295,span2019 unchanged. R8ordinary matches1000
states with independent replay,1293->1286 frames,mean852253.689. Shared change
therefore gains solo/R4 but regresses the longer R2route38frames; no retention.

After all shared candidate readers finished, built solo-only native proximity
variant6773a86d4bb067a3aca76b4d5d1f7222fd59acc0ec0d5f85603b31b4b8042589.
Original C body_near_inline stays at both party call sites; body_near_solo uses
paired native predicate only in solo common entry. New QA --helper option
selects the intended native function;1048576 boundary comparisons pass.
R2route24951 and solo38847 running; source/ROM archive and handles recorded in
`.local/bc-body-near-solo/run.json`. Keep isolated ROM fixed while they run.
This is testing a candidate implementation choice, not narrowing the goal:
all modes/1-4P still require60FPS/100% speed. Production80bfed25 unchanged,
worst sustained4P28.94356FPS. No completion claim.

### Solo proximity alternative route results (2026-10-05)

Previous turn made progress implementing solo-only native predicate and passing
1048576 native cases. All three long route jobs now terminal and canonical
states match. R2four-player87845 states:134360frames,mean1448216.581,span2072,
exact baseline timing. R4four-player72529states:108317frames,mean1277248.518,
span2019,also exact baseline timing. Solo160172states166846->166746,
mean896415.345->893932.788,profile1559->1543. Thus solo-only variant keeps the
shared variant's solo gain without its observed R2regression. Favor solo-only
variant pending remaining checks; production remains80bfed25.

Normal40session93017,BC40session36868,Home12session8862,stack4P/R8session30873
running. Initial stack1P invocation was rejected by CLI: this probe measures
stack/peer-allocation separation and supports2-4P; no1P stack coverage claimed.
Boss Rush must wait for Normal40terminal because of shared scratch files.
Keep isolated6773a86dROM unchanged while these tests run. Evidence and pending
handles `.local/bc-body-near-solo/run.json`. Full60FPS goal remains incomplete.
Read-only follow-up investigated prior bitmap terrain work: R4integration
already rejected; any R2experiment must address per-query pointer-check cost
rather than repeat that implementation unchanged. No terrain source change.

### Solo proximity retained (2026-10-05)

Previous turn made progress with three matching canonical routes and opening
matrix/Home/stack checks. Normal40 now terminal and all timing/state/render
hashes match. Boss Rush22247 then completed with3000matching video hashes,
2990updates/3000frames,zero drops/remaps/wheel fallback and reset cleanup.
All candidate jobs terminal. BC40 all40timings unchanged (existing speed
failures remain). Home12pass,4P/R8 stackgap11154/zero overlaps82960024boundaries.

Promoted only bc_world.c solo predicate. Production rebuilt exactly
6773a86d4bb067a3aca76b4d5d1f7222fd59acc0ec0d5f85603b31b4b8042589,
within4MiB. Evidence `.local/bc-body-near-solo/verified.json`, before/candidate
source/ROM/ELF/symbol archives. Shared variant0999a7c5 rejected in favor of
solo-only: same100-frame solo gain, exact baseline timing on both long4P
routes. New native boundary test remains, with --helper selecting solo code.
Retained4P worst28.94356006FPS unchanged; solo route166746frames. Full60FPS/
100% speed across all modes and full natural4Pclear remain unfinished.

### Prevalidated terrain lookup prototypes (2026-10-05)

Previous turn made progress retaining solo proximity. Archived guarded
per-metatile masks were already rejected, so this turn specifically removed
per-query resource guards from independent scratch probes. These primitives
require callers to validate resource identity outside the query batch; no
production API/source/resource changes made. Each passes655360 queries across
all ten source maps, including4096px wrapping/fraction positions. Boolean
candidate matches solidity only; direct byte reference retains numeric flags.
No mismatch/disabled-source fallback coverage is claimed for these unguarded
primitives (fallback checks0). Production ROM remained6773a86d exactly.

Flat bitmap: reference1688207360ticks,bitmap936660410 (44.51745%less),direct
byte642252800. Flat bitmap8192bytes/round. Evidence
`.local/bc-terrain-bitmap-prevalidated/verified.json`. Per-metatile256-byte
mask costs1698188730 (0.59124%more),rejected even without guards; evidence
`.local/bc-terrain-cell-prevalidated/rejected.json`. Both native sessions
3918/5480 terminal. These are isolated noinline primitive costs, not FPS.

Next integration candidate: Round2bitmap only, validating both immutable
source pointers once in weapon update, passing selected map into ordinary
shot task. Preserve generic numeric bc_terrain_solid and fallback for other
rounds; avoid the rejected R4per-query guarded integration. This plan is not
yet implemented or verified in gameplay. Full60FPS/100% speed remains open;
retained4P worst28.94356FPS,solo route166746frames.

### Round2 weapon-batch bitmap integration trial (2026-10-05)

Previous turn verified prevalidated flat lookup44.5% primitive savings.
New isolated variant validates both immutable Round2terrain pointers once per
weapon update, selects8192-byte bitmap, and passes it into ordinary shot core.
Direct bc_shot_step remains a wrapper with generic terrain, and the public
numeric bc_terrain_solid contract is unchanged. Other rounds use original
lookup. Actor terrain and player movement are unchanged. Source task ordering,
retirement and collision behavior are not intentionally altered.

Updated isolated build_bc_data.py generates map alongside immutable Round2
code. Regenerated assets, restoring original reference manifest afterward;
independently compared all65536generated subcells to numeric source flags.
Built within4MiB; candidate9dbc7e2f42402466035a68a82457bb9d18828add5c849f0d4f4d88d690d0a3ee.
Archive `.local/bc-r2-weapon-bitmap/candidate` includes source,headers,ROM,ELF,
symbols and generator. Production unchanged6773a86d.

Extracted native selector/lookup probe passes655360 Boolean queries across10
rounds plus12288 changed-source/fallback queries. Initial harness compile
needed reference function renaming; repaired without ROM changes. Its
reference attribution includes fallback calls, so do not interpret raw totals
as integration speed evidence. Source bitmap itself independently verified.
R2route96289 and solo45260 running; keep isolatedROM fixed. Metadata run.json.
No FPS gain established yet; retained4P28.94356FPS and goal unfinished.

### Round2 bitmap loop split trial (2026-10-05)

Previous turn integrated and checked bitmap selector/lookup. Shared-loop route
jobs now terminal with all canonical states matching: R2four-player87845,
134360->135102frames despite focus mean1448216.581->1430568.433 and span
2072->2063. Solo160172states166746->166866,mean893932.788->897942.892,
span1543->1561. Shared-loop form regresses overall; no retention.

After terminal checks, isolated follow-up splits the existing ordered pool
loop into two always-inline copies selected once per weapon batch. Generic
copy receives constant-null map; specialized copy is entered only with the
validated Round2bitmap. Intended to remove bitmap checks from generic shot
queries without changing pool order/empty scans/task behavior. Helper/map are
byte-identical source to already-native-verified shared candidate. Original
weapon-task fixture passes1101updates/872main launches/198option launches/
4088contacts/1101trail updates. Build fits4MiB (_etext0x3fd5d8).
Source/ROM/generator archive and metadata `.local/bc-r2-weapon-bitmap-split`.
R2route14812 and solo88085 running; do not rebuild while live. Production
remains6773a86d; no integration frame-rate gain retained,goal incomplete.

### Round2 weapon bitmap integrations rejected (2026-10-05)

Previous turn made progress measuring shared-loop regression and testing a
constant-path loop split. Split route jobs now terminal and canonical states
match: R2four-player87845 states134360->136350 frames,
mean1448216.581->1446344.690,span2072->2071. Solo160172states166746->166991,
mean893932.788->898251.438,span1543->1565. Disassembly verifies a specialized
bitmap branch but also temporary stack stores around bit/index calculation.
Both shared-loop and split-loop integration forms regress full routes despite
isolated primitive gains; rejected without unnecessary broader mode checks.

All readers finished before restoring bc_rules.c, generated bc_data.c and
build_bc_data.py with fresh mtimes. Rebuilt scratch exactly to retained
6773a86d4bb067a3aca76b4d5d1f7222fd59acc0ec0d5f85603b31b4b8042589;
production unchanged. Rejection evidence under `.local/bc-r2-weapon-bitmap`
and `.local/bc-r2-weapon-bitmap-split`, including candidate archives and profiles.
A future bitmap attempt must address integrated register/stack costs, not
rely only on primitive speed. No pending jobs. Retained worst4P28.94356FPS;
full60FPS/100% speed and natural full4Pclear still incomplete.

### Paired projectile velocity clear trial (2026-10-05)

Previous turn made progress rejecting both bitmap integrations and restoring
exact6773a86d. Current isolated trial uses one native CLR.L for adjacent VX/VY
word clears at four existing simultaneous-zero assignments (launch, impact,
expanding transition, option collection). Compile-time offset assertion checks
adjacency; asm declares both memory outputs and condition codes. Host fallback
retains original assignments. No motion arithmetic or task order change.
Native65536 comparisons verify every velocity value and all other beam bytes
unchanged. Original weapon-task host fixture passes1101updates,872main/
198option launches,4088contacts,1101trails. Evidence/archive
`.local/bc-beam-stop-long`; run.json records candidate SHA and handles.
R2route72965 and solo29638 running; keep isolated ROM fixed while live.
Production6773a86d unchanged; retained worst4P28.94356FPS. No speed gain claimed
until routes finish; full60FPS/100% speed goal remains incomplete.

### Paired velocity-clear validation follow-up (2026-10-05)

Previous turn made progress implementing native clear and65536byte-preserving
probe comparisons. Current turn verified disassembly emits CLR.L over velocity
pair at relevant player-task sites. Started second4Proute52208 and R8probe48063.
R8probe now terminal:1000canonical simulation states match older retained
80bfed25 R8reference and independent replay passes;1293->1285displayframes,
mean854754.236ticks vs852161.947,so mixed timing. Subsequent6773a86d baseline
only changes solo proximity, but no new exact-baseline R8measurement is claimed.
All three long route handles72965/29638/52208 confirmed live via polling and
CPU-active processes. Do not rebuild isolatedd43964f0 while they run.
Metadata `.local/bc-beam-stop-long/run.json`; production6773a86d unchanged.
Retained worst4P28.94356FPS,full60FPS/100% speed objective remains incomplete.

### Paired velocity clear rejected (2026-10-05)

All three long routes terminal and canonical states match, but all regress:
R2four-player134360->135108frames,mean1448216.581->1456125.475,span2072->2081;
R4four-player108317->108733,mean1283466.268,span2020;solo166746->166846,
mean897648.843,span1559. Counts87845/72529/160172states. Rejected paired CLR.L
integration despite native correctness: smaller local instruction sequence
changed integrated code costs adversely. No broad mode checks needed.
After all readers terminal restored isolated bc_rules.c with fresh mtime and
rebuilt exact6773a86d4bb067a3aca76b4d5d1f7222fd59acc0ec0d5f85603b31b4b8042589.
Production unchanged. `.local/bc-beam-stop-long/rejected.json` records results,
archives and restoration; native probe is experiment-only. No jobs pending.
Retained worst4P28.94356FPS; full objective remains incomplete.

### Animation source-offset reuse trial (2026-10-05)

Previous turn made progress rejecting paired clear and restoring6773a86d.
Current isolated change computes animation source offset once for duration
and frame reads, recomputing after a jump. All offset increments retain
unsigned16wrap, including origin subtraction and offset65535to0. No record,
duration, retirement, composite handling or attribute rules changed.
Native262144 animation-attribute cases pass. Host differential131072 motion
calls spans every animation address, varying origins, duration/redirect/
retire/composite cases and full enemy bytes/limited counters. Candidate
9dae21b34998a03e7f6bdc3497a0102f4c700011b5b97a48780cc9ccdc11f72b
archived `.local/bc-animation-offset-reuse/candidate`; probes and metadata
in same evidence folder. R2route3306 and solo68448 running; keep isolatedROM
fixed. Production6773a86d unchanged; no speed claim yet. Full60FPS remains
unfinished,retained worst4P28.94356FPS.

### Animation-offset candidate broader checks (2026-10-05)

Previous turn made progress implementing offset reuse and native/host checks.
Started second4Proute88263 and R8probe2551; R8now terminal. Its1000states
match prior80bfed25R8reference (before solo-only proximity optimization),
independent replay passes,1293->1287displayframes,mean852353.082vs852161.947.
This is near-flat CPU with display-phase variation, not conclusive route gain.
Saved before/after common-task assembly: register-save count stays four but
allocation changes; offset reuse introduces different spills around decoding.
All long route handles3306/68448/88263 confirmed live; keep9dae21b3isolatedROM
fixed. `.local/bc-animation-offset-reuse/run.json` records pending readers.
Production6773a86d unchanged; worst sustained4P28.94356FPS,goal incomplete.

### Animation-offset reuse rejected (2026-10-05)

All three routes subsequently terminal,all canonical states match. R2four-player
87845states134360->134401frames,mean1448216.581->1447665.968,span2072ties;
solo160172states166746->166846,mean893932.788->896572.061,span1543->1558;
R4four-player72529states108317->108306,mean1276723.833,span2019ties.
Rejected mixed result: smallR4gain does not offset longerR2/solo regressions.
Previous live-handle note superseded; all readers terminal before restoration.
Restored isolatedbc_rules.c with freshmtime and rebuilt exact6773a86d4bb067a3aca76b4d5d1f7222fd59acc0ec0d5f85603b31b4b8042589.
Production unchanged. `.local/bc-animation-offset-reuse/rejected.json` contains
full evidence. No jobs pending; retained4P28.94356FPS,fullgoal incomplete.

### Actor artwork key mask trial (2026-10-05)

Previous turn made progress rejecting animation-offset reuse and restoring
6773a86d. Current isolated renderer masks frame_attributes key to0xffff880f,
retaining full sprite word, two flip bits and palette nibble. Audit of
bc_actor_pose shows no other attribute bits used; state/composite handling
still happens before key lookup, base/ref remain separate key components.
Potential gain is fewer needless refreshes; extra mask may outweigh it.
Host cached-renderer differential passes normal randomized/synchronized and
signed-origin cases. Added experiment-specific persistent ignored-bit sweep
across ordinary art references, comparing every ordered submitted sprite and
all simulation bytes. Evidence/logs/source/ROM archive `.local/bc-actor-key-mask`.
R2route7480 and solo67217 running; do not rebuild isolated ROM while live.
Production6773a86d unchanged; no speed claim. Full60FPS/100% speed unfinished,
retained4P worst28.94356FPS.

### Actor cache key mask rejected — 2026-10-05
Previous response was no progress (status only). Revalidated both replay handles as terminal. Masked artwork keys preserve 87,845 four-player and 160,172 solo canonical states, but R2 requires 134,567 versus 134,360 display frames, and solo 166,807 versus 166,746. Profile means worsen to 1,449,505.855 and 895,531.833 ticks. Reject candidate df1f5090; restore retained actor source. Production stays 6773a86d. Evidence: `.local/bc-actor-key-mask/rejected.json`. Goal remains incomplete.

### Direct straight-shot submission trial — 2026-10-05
Scratch-only fast path handles source frame 0x1b8 after the existing triple-group check. It submits the same 0x4016 artwork key, coordinates and flip bits without constructing the general mapper result. Native 4P probe passed 589,824 cases, strengthened to verify artwork keys as well as coordinates, flip bits, missing-art handling and unchanged beam input. Candidate archived under `.local/bc-projectile-straight-direct/candidate`; long R2 four-player replay session 87941 and full solo session 7145 launched. No performance gain claimed before results. Retained production remains 6773a86d; scratch restored that exact SHA before this trial. This turn makes progress by rejecting a slower candidate and testing the next optimization.

Direct straight-shot trial follow-up: previous goal turn classified progress. Both replay handles revalidated live. Native 1P additionally passes 589,824 cases. Independent retained-source host comparison passes 2,400 pools, 37,527 ordered sprite submissions and 600 packed strips with dirty coordinate padding. Includes artwork keys, grouping fallbacks, end slots and unchanged simulation bytes. Performance results still pending; production unchanged.

Direct straight-shot trial: previous turn classified progress (added 1P native and independent host equivalence evidence). Revalidated R2 session 87941 and solo session 7145 live, additionally confirmed both operating-system processes accruing CPU. Started BC40 session 7191 and second natural 4P route session 73389 to broaden timing coverage. These jobs share an immutable candidate ROM; no rebuild is permitted while readers run. No result or speed gain inferred from live status.

Direct straight-shot timing evidence: R2 and solo jobs are terminal and canonical states match (87,845 / 160,172). R2 improves from 134,360 to 134,072 display frames, mean 1,448,216.581 to 1,443,745.590 ticks; worst 1,000-update window 2,073 to 2,069 frames (28.99951667 FPS). Solo regresses 166,746 to 166,850 frames and mean 893,932.788 to 900,078.305 ticks. BC40 terminal exit 1 is the existing speed failure, with no measurement errors or ROM changes; net 9 frames saved across 40 samples. R4 session 73389 remains confirmed live. Candidate is not promoted. Next test: confine direct path to the compile-time multiplayer renderer after R4 finishes, then revalidate long routes. This turn is progress: timing evidence changes implementation decision.

### Multiplayer-only straight-shot path — 2026-10-05
Previous turn classified progress. Shared variant R4 replay finished with 72,529 matching canonical states and 108,131 versus 108,317 display frames, mean 1,275,358.259 versus 1,277,248.518 ticks; profile span unchanged at 2,019. All shared-variant readers terminal before rebuilding. New candidate 82543322 uses the direct 0x1b8 path only when the compile-time pack flag is true, retaining original solo renderer source. Long R2 (38744), solo (75800), R4 (77543), and BC40 (49516) now running. Source, ELF, symbols and ROM archived in `.local/bc-projectile-straight-multi/candidate`. Production remains 6773a86d.

Multiplayer-only candidate renderer validation passed: 589,824 native 4P cases with artwork-key checks, plus 2,400 independent retained-source pool comparisons (37,527 ordered sprites, 600 packed strips). Timing remains pending.

Multiplayer-only direct drawing validation: previous turn classified progress. R2 (38744), solo (75800), R4 (77543) replay handles revalidated live. BC40 is terminal with no measurement errors or ROM changes; 40 samples save 3 display frames net (two +1 regressions, improvements -1/-2/-1/-1, remaining ties). Full speed remains false. Started Normal timing/render comparison (15829), all 12 mode/player modal cases (80141), and 4P/R8 stack audit (15516). Boss Rush must wait until Normal completes because their probes share scratch resources. No production promotion yet.

Candidate 82543322 passes all 12 Home mode/player dialog, cancel, and launch cases. 4P/R8 stack audit over 3,000 updates reports 11,154-byte minimum gap and zero overlaps across 82,999,184 instruction boundaries. These are bounded checks, not full-game performance or stack guarantees.

Multiplayer-only long replay results contradict promotion: R2 matches 87,845 canonical states but takes 134,427 versus 134,360 frames; worst 1,000-update window is 2,074 versus 2,073 frames (28.92960463 FPS). R4 matches 72,529 states but takes 108,363 versus 108,317 frames; mean 1,279,350.240 versus 1,277,248.518 ticks. This candidate loses the shared variant gains and will not be promoted. Solo (75800) and Normal (15829) remain live; do not rebuild until terminal. Boss Rush need not run for a rejected candidate. Production stays 6773a86d. This turn is progress because measured regressions decide rejection.

### Separate projectile renderer cores trial — 2026-10-05
Previous turn classified progress. Normal40 reader finished: all timing, state and render hashes match retained baseline; no measurement errors. Rejected multiplayer-only 82543322 and rebuilt exact retained 6773a86d before next trial. Disassembly reveals multiplayer frame grows from 32 bytes (shared direct variant) to 48 bytes (pack-guard variant), with additional spills; identical-looking source specialization does not retain identical assembly. New scratch trial gives solo and multiplayer separate always-inline core bodies: original solo body and direct-draw multiplayer body, preserving constant pack selection and submission order. Goal remains incomplete; no gain assumed until timing.

Separate-core candidate 41f17243 builds successfully and restores the multiplayer renderer to a 32-byte local stack frame. Independent retained-source host comparison passes 2,400 projectile pools / 37,527 ordered sprites / 600 packed strips. R2 replay session10727 and full solo session69387 launched; no speed improvement claimed before measurement.

Separate-core native 4P renderer probe also passes 589,824 cases including artwork keys, SAT flips, pixel coordinates, missing-art handling and unchanged beam data. Replay timing still pending.

Separate-core trial continuation: previous turn classified progress; current R2 session10727 and solo69387 revalidated live. Added second 4P route15361, BC40 matrix84003, Normal timing/state/render comparison34421, and Home12 modal checks1927 against unchanged candidate41f17243. Boss Rush waits for Normal terminal due shared probe scratch. No production changes or performance claim.

Separate-core candidate41f17243: all12 Home dialog/cancel/launch cases pass. 4P/R8 stack audit passes with minimum gap 11154 bytes and 0 overlaps across 82928152 sampled instruction boundaries. Long replay timings still pending.

Separate-core BC40 suite terminal with no measurement errors or ROM changes: net9 display frames saved; three +1 regressions, improvements -1/-2/-2/-2/-2/-2/-1, remaining ties. This reproduces the shared-direct variant short-sample timing while retaining original solo core source, but long-route and cross-mode checks remain live and no promotion is warranted yet. Current turn adds completed evidence and is progress.

Separate-core long-route timing confirms the intended gain: R2 matches87,845 canonical states, 134,072 versus134,360 display frames, mean1,443,745.590 ticks, worst1,000-update window2,069 versus2,073 frames (28.99951667FPS). Solo matches160,172 states and exact baseline timing166,746 frames / mean893,932.788 / span1543. R4 matches72,529 states, 108131 frames / mean1275358.259 / span2019. Normal34421 still live; R8 ordinary70008 and charged1814 launched. Previous turn classified progress; current results support continuing promotion checks but do not prove60FPS.

### Retained separate projectile cores — 2026-10-05
Promoted41f1724335fd847c3d4ef3eda1267b887a5767e2a807ed206eb76022640e4bd3; production rebuild matches candidate exactly. Native direct straight-shot submission is confined to the multiplayer core; original solo core remains separate to preserve register allocation. R2 route saves288 frames (134,360→134,072) with87,845 matching canonical states; worst1,000-update window2,073→2,069 frames (28.94356006→28.99951667FPS). R4 saves186 frames (108,317→108,131),72,529 matching states. Full solo160,172 states and timing unchanged166,746 frames / mean893,932.788. BC40 net9 frames saved with three+1 regressions; no measurement errors. Normal40 exact timing and state/render hashes. Boss Rush3000 video hashes match,2990updates/3000frames, zero sprite drops/remaps/wheel fallbacks, reset cleanup passes. Home12 passes; 4P/R8 stack gap11,154bytes with zero overlaps. Native renderer589,824 cases plus host2,400 pools/37,527 submissions/600 packed strips pass; native QA now additionally verifies artwork keys. R8 ordinary1,288 and charged1,235frames with matching simulation hashes and verified replay versus older80bfed25 reference (1,293/1,238), explicitly not a fresh6773 comparison. Evidence `.local/bc-projectile-straight-separated/verified.json`. All jobs terminal. Goal remains incomplete: native4P worst sustained rate still about29FPS, not60; full natural4P clear unproven. This turn is progress through verified production promotion.

### Direct expanding-flight artwork trial — 2026-10-05
Previous turn classified progress (verified promotion). Production and scratch baseline both revalidated as41f17243 before edits. R2 profile attributes156,422,280ticks to multiplayer projectile drawing per1,000updates. New scratch candidate8dd77d6f directly submits source sprite0x1ae as key0x4083 in the multiplayer renderer, with unchanged coordinates, flips, order and fallback. Solo remains original. Expanded native test adds the new source sprite/key and passes655,360 cases. Independent retained-source host comparison passes2,400 pools /37,527 ordered sprites /600 packed strips. Full candidate source, headers, ROM, ELF and symbols archived in `.local/bc-projectile-expanding-direct/candidate`. R2 session89632 and solo69073 now running. No speed improvement assumed; retained production remains41f17243 (~29FPS worst sustained4P). Goal incomplete.

Direct expanding-flight continuation: previous turn classified progress. Revalidated R2 session89632 and solo69073 live. Added BC40 suite38414 and second long4P route62554 against immutable candidate8dd77d6f. Retained production41f17243 unchanged.

Retained R2 instruction profile inspected while candidate replays run: player/weapon function283,389,470ticks; individual velocity-shift instructions account for4,605,216 and4,438,560ticks, alongside high-frequency state scans, movement loads/stores and terrain work. Saved60 hottest player instructions and disassembly in `.local/bc-projectile-expanding-direct/baseline-player-hotspots.json` and `player-baseline.asm`. This identifies remaining work without changing active-reader ROM or claiming a speed gain.

Expanding-direct BC40 terminal: no measurement errors or ROM changes; deltas versus retained41f17243 [0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 0, 0, 0, -1, 1, 0, 0, 0, 1, 0, 0, -1, 2, 0, 0, 0, 0, 0, 0, 2, 2, 0, 0, 0, 0, 0, 0, 2, 1], net-8 frames saved. Existing full-speed failure persists. Long replay handles89632/69073/62554 still live. No promotion based on short samples. Current turn completes bounded timing evidence and hotspot analysis (progress).

Expanding-flight direct path rejected: all three replay readers terminal, canonical states match. R2 134,072→134,287 frames despite mean1,443,745.590→1,442,914.452; R4 108,131→108,305 with mean1,275,358.259→1,276,379.748; solo exact166,746 frames. BC40 net8 frames worse. Revert trial; production41f17243 unchanged. Previous turn classified progress; current timing results determine rejection. Old whole-weapon outlining, ordinary-shot specialization and charge/fire outlining already failed prior timings, so those are not repeated.

### Direct hardware artwork key table trial — 2026-10-05
Restored scratch to exact41f17243 after rejecting expanding-only path. Prior mapper table experiments at docs6520/9782 failed, so this trial targets a different boundary: multiplayer loop submits packed hardware artwork keys directly instead of returning a BcProjectileSprite. Retained straight3 and straight-shot fast paths remain; solo mapper remains unchanged. Candidate 7b0b163d90be1fd638262fc614ad2058849293d3bfd17b9873fba1c035d8b314 archived with fullsrc/inc/ROM/ELF/symbols. Native differential compares all65,536 source frame IDs ×4flip combinations ×2facings against original bc_projectile_sprite, totaling524,288 passing cases including invalid IDs, exact artwork key, pixels, flips, unmapped counts and unchanged inputs. Host independent comparison passes2,400 pools/37,527 ordered sprites/600 packed strips. Long R2 session12537 and full solo16716 running. No speed gain claimed. Production remains41f17243; goal incomplete.

Direct key-table continuation: previous turn classified progress (rejected expanding-only path, built and verified new renderer). Revalidated R2 session12537 and solo16716 live; added R4 replay53714 and BC40 suite93015. Candidate7b0b163d remains isolated and immutable during tests; production41f17243 unchanged.

Direct key-table BC40 completed: no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, -2, 0, 0, 0, -2, 0, 0, 2, 1, 0, 0, 0, 0, 0, 0, 1, -2] versus41f17243, net1 frames saved. Full-speed goal still fails these bounded samples. Long-route jobs12537/16716/53714 remain pending; no promotion yet. This turn adds completed timing evidence (progress).

Direct hardware key table rejected after all replay readers terminated. Canonical states match R2/solo/R4 (87,845/160,172/72,529). R2 total134,072→134,064 but mean1,443,745.590→1,445,732.288 and focused span2068→2071 worsen; R4 108,131→108,190 and mean1,275,358.259→1,277,011.953; solo exact166,746frames. Restoring retained41f17243. Previous turn classified progress; this turn changes next action based on complete timing evidence.

### Native shot-index memory increment trial — 2026-10-05
Restored exact41f17243 scratch after table rejection. New native count sequence captures old count with MOVEQ/MOVE.B, then ADDQ.B directly to index count, replacing C increment temporary. Same slot index, byte wrapping, ordered writes and bounds. Candidate 5a76a66f5000d84a06ee4211cbb41a5abb5ec1986edc1788f055328eb9ef406c archived with full source/headers/ROM/ELF/symbols. Native4,096 complete index comparisons pass with dirty coordinate padding, high-byte rejection, state/flag/radius variations and sentinels. Host32,000 scans preserve5,336 contacts,2,070 damaging hits and slot order. R2 session76358 and solo17412 running. Production41f17243 unchanged; no speed claim before long timing. Current turn advances through rejection evidence and new verified experiment.

Shot-index memory increment continuation: previous turn classified progress. R2 session76358 and solo17412 revalidated live; added R4 replay89176 and BC40 suite94254 against immutable candidate. Saved bounded disassembly `index.asm` to verify instruction selection independently of the source edit. Production41f17243 unchanged.

Shot-index memory increment BC40 terminal: no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0] versus retained41f17243, net-1 frames saved. Disassembly confirms ADDQ.B #1,count directly and no temporary count increment/store. Long replay handles76358/17412/89176 confirmed live through30-second bounded waits. Current turn adds completed timing and instruction evidence (progress); full-speed goal remains unproven.

Shot-index increment long results: previous turn classified progress. All three canonical replay traces match. R2 134,072→134,041frames, mean1,443,745.590→1,443,248.779; worst1,000-update window2069→2068frames (29.01353965FPS). R4 108,131→108,108frames, mean1,275,358.259→1,275,025.290; worst2020frames unchanged. Solo166,746→166,761frames (+15), mean893,932.788→893,656.750, profile span1543→1544. Candidate is a measured tradeoff, not a universal gain. Running Normal98365, Home12 session5457, stack54046 and R8 ordinary/charged probes before promotion decision; Boss Rush serialized after Normal. Production41f17243 unchanged.

Index memory increment Home12 checks pass (dialog, cancel preservation, launch). 4P/R8 stack audit: minimum gap11154 bytes, 0 overlaps across82918462 instruction boundaries. Normal98365 and R8 probes35725/60220 remain live. No promotion yet. Current turn records long-route tradeoff and completed correctness gates (progress).

Index memory increment continuation: previous turn classified progress. R8 ordinary and charged probes terminal with matching1,000 simulation hashes each and verified independent replays against retained41f17243. Ordinary1288frames unchanged, mean851,748.359→851,736.095; charged1235→1237frames, mean768,219.571→768,141.241. Normal session98365 still confirmed live. Candidate is a small CPU/long4P gain with display-timing regressions in solo and charged sample; no universal-speed claim.

Normal40 comparison terminal: all timings and state/render hashes exactly match retained41f17243, no measurement errors. Boss Rush4P 3,000-frame video/reset comparison started after Normal finished (session51821).

### Retained native shot-index memory increment — 2026-10-05
Promoted5a76a66f5000d84a06ee4211cbb41a5abb5ec1986edc1788f055328eb9ef406c; production rebuild exactly matches tested candidate. Native ADDQ.B updates count in memory while old count retains ordered slot offset. Both long4P routes improve: R2 134,072→134,041frames and R4 108,131→108,108; canonical87,845/72,529states match. Worst R2 inclusive1,000-update window2069→2068frames (28.99951667→29.01353965FPS). Solo160,172states match but166,746→166,761frames; charged R8 1235→1237, ordinary1288unchanged. All sampled CPU means decrease. BC40 has39ties and one+1 regression. This is a documented tradeoff prioritizing long4P and worst-window gains, not a universal speedup. Native4096index cases and host32000scans pass. Home12 and bounded4P/R8 stack audit pass. Normal40 timings/state/render hashes and Boss Rush3000video hashes match; Rush2990updates, zero drops/remaps/wheel fallback, reset cleanup passes. All jobs terminal. Evidence `.local/bc-index-memory-increment/verified.json`. Current turn is progress via verified promotion. Full60FPS/100% speed and full natural4P campaign remain incomplete.

### Early shot-index flag gate trial — 2026-10-05
Previous goal turn classified progress (retained native memory count increment). Revalidated production/scratch5a76a66f. Candidate 73dd6ee17f08e9b0b4c08a7ca2b5c4020cb4c373c1b92e6db92ea66da845cc10 moves flags&1 exclusion from noinline shot_index_live into each of the existing two ordered state gates in bc_shot_index. Integer-coordinate checks remain in helper. All accepted slots, eligibility, bounds and collision order are unchanged. Native4096 complete indices and host32000 scans/5336contacts/2070damaging hits pass. Full candidate and native probe archived in `.local/bc-index-early-flag`. R2 session35107 and solo64638 started; no performance claim yet. Production5a76a66f remains unchanged and full-speed objective incomplete.

Early shot-index flag continuation: previous turn classified progress. R2 session35107 and solo64638 revalidated live. Added second4P replay67314 and BC40 suite69922 using the same immutable candidate; retained production5a76a66f unchanged.

Early flag gate BC40 terminal, no measurement errors or ROM changes: deltas [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 3, 0, 0, 0, 27, 0, 0, 0, 1, 0, 1, 4, 30, 0, 0, 1, 5, 0, 0, 2, 18, 0, 0, 0, 3, 0, 2, 0, 6] versus retained5a76a66f, net-103 frames saved. Native helper disassembly confirms flag instructions removed from callee (`index.asm`). Long R2/solo handles35107/64638 confirmed live in30-second bounded waits; R4 remains pending67314. This turn adds completed timing evidence (progress). No promotion or full-speed claim.

Early index flag gate rejected with complete canonical state matches. R2 134,041→136,499frames, mean1,443,248.779→1,453,651.773; R4 108,108→109,383frames, mean1,275,025.290→1,286,549.775. Solo166,761→166,732frames improves but does not offset multiplayer regression. BC40+103frames. All readers terminal; exact5a76a66f restored. Previous turn classified progress; current rejection determines next action. Next isolated trial annotates non-overlap of local collision target, weapon pool and temporary shot index in bc_enemy_shots_indexed; production callers use separate storage. No collision logic or order changed.

Collision-input restrict annotations produce a finalized ROM byte-identical to retained5a76a66f, so no timing run is warranted. Rejected and removed annotations; no behavior or performance change claimed. Evidence `.local/bc-contact-storage-restrict/rejected.json`. Production remains5a76a66f with29.01353965FPS worst sustained4P. This turn makes progress by rejecting a measured regression and ruling out a no-code-change candidate; full goal remains incomplete.

### Precise timer memory operand trial — 2026-10-05
Previous turn classified progress (rejected early flag gate and no-op restrict annotations). Prior distance reuse rejection reviewed; not repeated. Scratch candidate fd978d3b59b960f54971c8f99bbcd273d8bccc610c13f1a18cc8fbf6f8bb076f changes native enemy_timer_due from SUBQ.B/asm-goto BEQ plus global memory clobber to SUBQ.B/SEQ with explicit read/write timer operand and normalized boolean result. Same256-value decrement/wrap/zero behavior, no animation or motion rules changed. This tests reduced compiler reload barriers against extra zero-result instruction cost. Native512 even/odd timer cases pass, including neighbors; archived probe and candidate source/ROM/ELF/headers/symbols under `.local/bc-timer-precise-memory`. Long R2 session67421 and full solo22739 running. Production5a76a66f unchanged, no speed gain claimed. Goal remains incomplete.

Precise timer operand continuation: previous turn classified progress. Long R2 session67421 and solo22739 confirmed live. Added R4 route33442 and BC40 suite10407 against immutable candidate. Production5a76a66f unchanged; no performance claim yet.

Precise timer operand results so far: native262,144 integrated animation cases pass (all attribute words, flips, sprite/timer/animation pointer/count/return outputs). BC40 terminal with no measurement errors or ROM changes, net14frames worse. R2 terminal with87,845 matching states but134,041→134,209frames, mean1,443,248.779→1,444,545.893, profile span2067→2069. This is unfavorable timing despite correct behavior. Solo22739 and R433442 still pending; no promotion. Current turn adds integrated correctness and timing evidence (progress).

Final precise-timer results: remaining readers terminal. Solo160,172 states match but166,761→166,815frames, mean893,656.750→895,832.511; R472,529states match but108,108→108,171frames, mean1,275,025.290→1,276,377.480. Rejected all-route regression, restored source and rebuilt exact5a76a66f. Evidence `.local/bc-timer-precise-memory/rejected.json`. All jobs terminal; production unchanged; full60FPS/100% objective incomplete.

### Cooldown range predicate — no-code-change rejection, 2026-10-05
Previous turn classified progress (timer regression rejected and retained build restored). Replaced9 world cooldown predicates `cooldown && cooldown!=255` with `(unsigned char)(cooldown-1)<254`, preserving zero/255 sentinels. Finalized ROM exactly equals baseline5a76a66f, so no runtime gain is possible and long replay reruns are unnecessary. Native512 byte-value/even-odd checks pass; party/contact-stream behavior checks also pass. Removed experimental rewrite. Evidence `.local/bc-cooldown-range/rejected.json`. Current turn rules out a candidate with authoritative binary evidence (progress). Production unchanged; goal remains incomplete.

### Live-member collision index trial — 2026-10-05
Previous turn classified progress (byte-identical cooldown rewrite rejected). Candidate 5498d3a0b4301b4c20fa13213e913c654daa0548176c52b6401c69e027c6c4b4 limits derived shot-index construction inside party_actor_loop to state0x80 members. Non-live members get a temporary null index (existing uncached fallback), previous pointers restored on all exits. Weapon simulation, drawing, actors, contacts and their ordering are not removed. Other index builders remain unchanged. Cached party union already includes only state0x80 members. Routing fixture passes P3 ownership, P2 immediate boss-child contact, four pointer restores, early exit and callback filtering; event tests pass5000events and256general/final loops. Initial fixture-path failures were resolved by linking existing original round10 code into scratch fixture path; reruns pass. Candidate fullsrc/inc/ROM/ELF/symbols archived. Long R2 session34689 and solo6785 running to check deaths, continues, state progression and timing. Production5a76a66f unchanged; no speed claim.

Live-member index continuation: previous turn classified progress (implemented derived-index optimization and passed routing/event tests). R2 session34689 and solo6785 revalidated live. Second4P route3610 and BC40 suite8863 launched using unchanged candidate. Production5a76a66f remains untouched.

Live-member indices: strengthened routing probe passes32 combinations of live/dead/dying peers, occupied non-live weapon pools and normal/early actor-loop exits. Same probe passes against saved pre-change runtime source; P3 kill ownership and full non-live weapon bytes unchanged, all four index pointers restored. BC40 terminal with no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, 1, 0, 0, 0, -5, 0, 0, 0, 1, 0, 0, 0, -1, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, -2], net7 frames saved. Long handles34689/6785 still confirmed live; R4 pending3610. Current turn adds targeted fidelity and timing evidence (progress), no promotion yet.

### Consolidated live-member index block trial — 2026-10-05
Previous turn classified progress. Initial live-only index variant all readers terminal: R2 matches87,845states and134,041→132,349frames, but mean1,443,248.779→1,443,817.368 and worst2068→2070frames regress; R4 matches72,529states and108,108→107,377frames, mean1,275,025.290→1,274,252.196, span2019→2018. Solo160,172states and166,761frames exactly unchanged. Initial variant not yet promoted. New candidate ac8ee60d55e6d932dc496141b46d0f9c26078e637b5747e6518dcb93f11776b1 consolidates repeated state0x80 tests into one block covering policy/body bounds, index build, shot union and pointer assignment; null fallback remains for non-live members. Mixed32-case routing and5000-event/256-loop checks pass. Archived source/headers/ROM/ELF/symbols under `.local/bc-party-live-index-block/candidate`. Long R2 session46596 and solo75207 running. Production5a76a66f unchanged; goal remains incomplete.

Consolidated live-index block continuation: previous turn classified progress (long-route savings established, state checks consolidated, targeted routing/events passed). R2 session46596 and solo75207 confirmed live. Added R4 replay78095, BC40 suite12339, Normal timing/state/render comparison28787, Home12 check11170 and4P/R8 stack audit16528 using the immutable candidate. Boss Rush must wait for Normal terminal due shared probe scratch. Production5a76a66f unchanged.

Consolidated live-index BC40 complete: no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, -2, 0, 0, 0, 0, 0, 0, -1, -3, 0, 0, 0, 0, 0, 0, 0, -5, 0, 0, 0, -1, 0, 0, 1, -1, 0, 0, 0, -1, 0, 0, 0, -3], net16 frames saved versus5a76a66f. Home12 dialog/cancel/launch checks pass. Stack4P/R8 gap11158bytes, zero overlaps across82810368instruction boundaries. R2/solo live through30-second waits; R4 and Normal pending. Current turn adds completed timing and correctness evidence (progress). No promotion yet.

Consolidated index long replay evidence: previous turn classified progress. R2 matches87,845states and improves134,041→132,102frames, mean1,443,248.779→1,441,562.395, but inclusive worst1,000-update window2068→2069frames (28.99951667FPS). This is a substantial total-route saving with one-frame worst-window regression, not a universal gain. Solo and R4 readers also terminal; exact metrics saved in run.json. Normal28787 remains live; R8 ordinary70526/charged98500 launched. No production promotion yet.

Consolidated live-index checks: R4 matches72,529states and108,108→107,233frames, mean1,275,025.290→1,272,204.787, span2019→2017. Solo160,172states and all timing metrics exactly match5a76a66f. Normal40 timing/state/render hashes all match. R8 ordinary1288→1281frames and charged1237→1241; both1,000-state traces match and independent replays verify, both CPU means decrease. Boss Rush session42704 started after Normal terminal. Broad timing tradeoff remains documented, not claimed as uniform improvement.

### Retained consolidated live-member indexes — 2026-10-05
Promotedac8ee60d55e6d932dc496141b46d0f9c26078e637b5747e6518dcb93f11776b1; production rebuild matches tested candidate exactly. Actor-pass shot acceleration indexes are constructed only for state0x80 members, with body policy and union updates inside the same state block; non-live peers get temporary null fallback and original pointers restore after normal/early exit. Their weapons still simulate and render. R2 saves1,939frames (134,041→132,102) with87,845matching canonical states; R4 saves875frames (108,108→107,233) with72,529matching states. Solo160,172states and166,761frames exactly unchanged. R2 worst inclusive1,000-update window regresses2068→2069frames (29.01353965→28.99951667FPS); do not quote29.01FPS as current retained worst. BC40 net16frames saved, one+1regression. R8 ordinary1288→1281, charged1237→1241, matching states and independent replays. Normal40 exact timings/state/render hashes; Boss Rush3000video hashes match,2990updates, zero drops/remaps/wheel fallback and reset cleanup pass. Home12 passes, bounded4P/R8 stack gap11,158bytes and zero overlaps. Expanded32-case live/dead/dying/occupied-weapon/early-exit routing check retained in qa_bc_party_routing.py;5000event/256loop comparisons pass. Evidence `.local/bc-party-live-index-block/verified.json`. All jobs terminal. Previous turn classified progress; current verified promotion is progress. Full60FPS/100% speed and full natural4P campaign remain unproven.

### Live-only indexes in remaining actor passes — 2026-10-05
Previous goal turn classified no progress: performance status only. Revalidated retained production ac8ee60d55e6d932dc496141b46d0f9c26078e637b5747e6518dcb93f11776b1 and isolated candidate c48b8e8fd916e027b1e2fdf4b9a08e1a3c3f0af20a8b1528247dca6be0c89b9f. Candidate applies live-state-only derived shot-index construction to segment births and solo actor passes, retaining temporary null fallback and original pointer restoration. No weapon simulation, rendering, actor tasks or ordered contacts removed. Tests pass: 576 segment births, 786 ordered party contacts, 6648 consumed shots, 48 allocation failures across six rounds/both variants/1–4P; 32 live/dead/dying routing cases; 5000 events and 256 general/final loops. Missing original fixture paths were linked to existing local reference code, then the segment test reran successfully. Long canonical replays launched: R2 session74748, solo40090, R4 83488; BC40 session16146. Source/ROM archive and run manifest under `.local/bc-live-indices-all-passes`. Production unchanged; no performance gain or 60FPS claim. Current turn adds completed fidelity evidence and starts measured comparison (progress).

Remaining-pass index trial follow-up: added independent retained-versus-candidate solo differential probe covering all256 player states with occupied weapon pools, normal/unsupported early exits, exact player/actor/event bytes and restored sentinel pointer. All512 cases pass. BC40 completed with no measurement errors or ROM changes and all40 frame counts exactly equal retained ac8ee60d. This bounded protected-opening matrix cannot establish benefits for dead-player paths; long natural R2/solo/R4 replays remain pending. No promotion or full-speed claim.

Remaining-pass live-index continuation: previous turn classified progress (512 solo differential cases and complete BC40 equality). Revalidated long R2 session74748, solo40090 and R4 83488 live with tool polls and matching process records; no restart. Started independent Home12 modal and bounded4P/R8 stack checks against unchanged c48b8e8f candidate while awaiting timing. Production ac8ee60d remains unchanged; full-speed and natural full4P campaign remain incomplete.

Remaining-pass trial results: Home12 dialog/cancel/launch checks all pass. Bounded4P/R8 stack minimum gap11,162bytes with zero overlaps across82,810,350 sampled instruction boundaries. R4 long replay completed72,529 matching canonical states and107,233frames, exactly equal retained total; mean1,272,204.787→1,272,200.825 core ticks and profile span2017 unchanged. R2 session74748 and solo40090 still confirmed live. Current turn adds completed modal, stack and long-route evidence (progress), but no material speed gain established and no promotion.

Remaining-pass live-only indexes rejected after all replays completed. R2 matches87,845states but132,102→132,113frames; worst inclusive1,000-update window2069→2070frames (28.99951667→28.98550725FPS). R4 matches72,529states with107,233frames unchanged. Solo matches160,172states and improves166,761→166,757frames, but mean893,656.750→894,228.496 ticks; profile span1544→1543. Four-player worst-window regression and no R4 gain outweigh four saved solo frames. All readers terminal; restored source with fresh mtime, rebuilt/finalized and verified isolated ROM exactly equals production ac8ee60d55e6d932dc496141b46d0f9c26078e637b5747e6518dcb93f11776b1. Evidence `.local/bc-live-indices-all-passes/rejected.json`; exhaustive solo probe remains archived. Current turn adds authoritative rejection and restoration (progress). Retained worst4P remains28.99951667FPS. Full60FPS/100% speed, full natural4P clear, and overall goal remain incomplete.

### Outline collision-index builder trial — 2026-10-05
Previous goal turn classified progress (remaining-pass live-index regression rejected; exact ac8ee60d restored). Revalidated isolated and production ROM hashes, reviewed prior sparse/two-slot/four-slot index experiments. New isolated candidate ee3028d3e154f37f7e452f1a855c62806b341b4bc715285b59b79487c022feb2 marks bc_shot_index noinline, leaving its sparse ordered scan and live helper unchanged. Tests whether a separate native scan reduces caller register pressure. Native4096 complete indices pass with dirty padding and index sentinels; host32000 scans/5336contacts/2070damaging hits and32 live/dead/dying routing cases pass. Full candidate archive and bounded disassembly under `.local/bc-index-outline`; native probe archived. Long R2 and solo replays plus BC40 timing launched against immutable candidate. Production ac8ee60d unchanged; no speed claim. Current turn advances with a distinct compiled candidate and native fidelity evidence; goal incomplete.

Outline-index continuation: previous turn classified progress (new compiled candidate and4096native/32000host/32routing cases passed). Revalidated R2 session62808 and solo2158 live; started second4P route52601 without rebuilding. BC40 completed with no measurement errors or ROM changes; frame deltas versus retained recorded in run.json. Bounded disassembly confirms noinline scan is separately emitted; party loop stack allocation/register save mask remains unchanged, so register-pressure hypothesis is not yet established. Long timing remains decisive. Production ac8ee60d unchanged; full goal incomplete.
BC40 frame deltas: [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 3, 0, 0, 0, 0, 0, 0, 0, 16, 0, 0, 0, 1, 0, 0, 0, 7, 0, 0, 0, 4, 0, 1, 2, 6]; net frames saved -41.

Outline-index timing continuation: previous turn classified progress (BC40 regression measured). R2 session62808, solo2158 and R4 52601 confirmed live via bounded tool polls and matching processes; no restart or rebuild. Current evidence does not justify promotion. Production ac8ee60d unchanged. Awaiting long canonical state/timing results before restoring scratch; this interval is a verified wait.

Outline-index trial rejected: R2 matches87,845states but132,102→132,516frames, mean1,441,562.395→1,445,019.387 and worst2069→2070frames. R4 matches72,529states but107,233→107,469frames, mean1,272,204.787→1,275,597.491 and span2017→2020. Solo matches160,172states and improves166,761→166,629frames, mean893,656.750→891,070.670 and span1544→1528. BC40 costs41extraframes. All jobs terminal; reverted global noinline annotation and rebuilt exact retained ac8ee60d. Evidence `.local/bc-index-outline/rejected.json`. Current turn adds decisive long-route evidence (progress). Solo gain motivates a separate solo-only wrapper, leaving multiplayer inlining intact; not a reason to retain the slower global change. Full60FPS/100% speed goal incomplete.

### Solo-only outlined shot-index trial — 2026-10-05
Following global-outline rejection, restored baseline then added static noinline solo_shot_index wrapper only for bc_runtime_actor_loop's solo branch. Multiplayer and segment-birth calls retain prior inlining. Candidate b4c08c5c1506e00c7e2c36335ea239dccd6fc333eeb5a0323fed7dcfe8e54b59 archived under `.local/bc-index-outline-solo/candidate`. Independent retained-versus-candidate comparison passes512solo passes/all256state bytes/occupied pools/normal and early exits/full actor-player-event bytes/index restoration;32party routing cases pass. Long R2 session80690, solo59036 and BC40 73234 launched. Production ac8ee60d remains unchanged; no speed gain claimed before timing. Current turn includes measured rejection, exact restoration and targeted follow-up candidate (progress). Goal remains incomplete.

Solo-only outlined index continuation: previous turn classified progress (global variant rejected, targeted candidate built and512solo/32party checks passed). R2 session80690 and solo59036 revalidated live. BC40 completed with no measurement errors or ROM changes; deltas [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,-1,0,0,0,0,0,0,0,-1,0,0,0,0,0,0,0,1,0,0,0,0,0,0,0,0], net1frame saved. Started R4 route92761, Normal40 timing/state/render21920, Home12 67283 and stack4P/R8 2231 against immutable b4c08c5c. Rush must wait for Normal terminal due shared probe scratch. No production promotion yet; current turn adds completed timing evidence (progress), goal incomplete.

Solo-only outline verification: Home12 dialog/cancel/launch cases all pass. Bounded4P/R8 stack check has11,158bytes minimum gap, zero overlaps across82,830,170 instruction boundaries. R2/solo/R4 and Normal timing/state/render jobs confirmed live; no rebuild or restart. Production unchanged. These completed checks add verification evidence, but no long-route gain established yet.

Solo-only outline long results: all160,172solo states match;166,761→166,629frames, mean893,656.750→891,180.465, profile span1544→1524. R2 matches87,845states,132,102→132,103frames, mean1,441,562.395→1,441,539.316, worst inclusive1,000-update window2069→2068frames (29.01353965FPS). R4 matches72,529states,107,233→107,238frames, mean1,272,204.787→1,272,145.196, span2017unchanged. This is a solo gain and tiny4P total regression with improved worst-window, not a universal speedup. Normal40 terminal: identical timing/state/render hashes and no measurement errors. Started Rush4081 only after Normal terminal; heavyR8 ordinary64709 and charged15328 compare retained1000-state traces/independent replays. No promotion yet; production ac8ee60d unchanged. Current turn completes long timing and mode checks (progress); full60FPS/100% speed goal incomplete.

### Retained solo-only outlined shot index — 2026-10-05
Promoted b4c08c5c1506e00c7e2c36335ea239dccd6fc333eeb5a0323fed7dcfe8e54b59; production rebuild matches tested candidate exactly. Static noinline solo_shot_index wrapper changes only solo actor-pass call boundary; shared index algorithm and multiplayer inlining remain unchanged. Full solo160,172states match and166,761→166,629frames (132saved); mean893,656.750→891,180.465, profile span1544→1524. R2 four-player87,845states match with132,102→132,103frames; worst inclusive1,000-update window2069→2068frames, now29.01353965FPS. R4 four-player72,529states match,107,233→107,238frames; mean decreases slightly. BC40 net1frame saved with one+1regression. R8 ordinary1281→1279, charged1241→1242; both1000state traces match and independent replays verify, CPU means decrease. Normal40 exact timings/state/render hashes; Rush3000video hashes match,2990updates, zero drops/remaps/wheel fallback and reset cleanup pass. Home12 pass; bounded4P/R8 stack gap11,158bytes with zero overlaps. Independent512solo/all256states and32party routing cases pass. Evidence `.local/bc-index-outline-solo/verified.json`. This is a documented timing tradeoff, not a universal improvement. All jobs terminal; current turn makes progress through verified retention. Sustained all-mode60FPS/100% speed and full natural4P campaign clear remain incomplete.

### Register live-state comparison trial — 2026-10-05
Previous goal turn classified progress (solo-only outlined index retained as b4c08c5c). Revalidated production and isolated baseline hashes and no live readers before build. Candidate b205dee18eef162ecf2044fad2c51f5f94aff267088fd272acaaf63907f1bed9 uses native CMP.B against data-register -128 plus asm-goto for each existing sparse index state test. Host expression remains state==0x80; slot order, source states, eligibility and contacts unchanged. Native8192 complete-index comparisons pass: original4096cases plus4096covering all256statebytes, dirty padding/fractions, gates, radii, unchanged weapons and index sentinels. Host32000scans/5336contacts/2070damaging hits pass. Disassembly confirms register compare but compiler now emits a compact loop with six saved registers rather than prior unrolling; instruction-level gain may be outweighed by loop overhead, so no speed claim. Archived full source/ROM/ELF/headers/symbols and native probe under `.local/bc-index-register-state`. R2 session41480, solo55715 and BC40 85142 running against immutable candidate. Production b4c08c5c unchanged. Current turn implements/tests distinct native candidate (progress); full60FPS/100% speed goal incomplete.

Register-state BC40 complete: no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 3, 0, 0, 1, 28, 0, 0, 0, 1, 0, 1, 3, 34, 0, 0, 1, 9, 0, 0, 1, 14, 0, 0, 0, 3, 0, 2, 0, 9]; net frames saved -112. Long R2/solo remain pending. No promotion.

Register-state continuation: previous turn classified progress (8192native checks and measured BC40 regression). R2 session41480 and solo55715 revalidated live, no restart or rebuild. Disassembly indicates native asm-goto prevents previous unrolling; prepared a separate explicit28-slot ordered source variant under `.local/bc-index-register-state-unrolled/candidate.c` to isolate comparison cost from added loop bookkeeping. Prepared source is not installed/built and has no runtime evidence yet. Current playable production b4c08c5c remains unchanged; current reader candidate b205dee1 remains immutable. Full goal incomplete.

Register-state loop variant rejected: all87,845R2states match, but132,103→133,887frames, mean1,441,539.316→1,456,935.788; worst2068→2085frames (28.77697842FPS). Solo160,172states match but166,629→166,791frames, mean891,180.465→894,983.551, span1524→1552. All readers terminal; rebuilt exact baseline b4c08c5c before next trial. Evidence `.local/bc-index-register-state/rejected.json`.

Built explicit28-slot state-check variant ee168cca9b7582e4517c1181e988d34c86c46ddde72e5fef5a674afc71a6ded0 to preserve ordered unrolling around the native register comparison. Complete8192native indices/allstatebytes and32000hostscans pass. Full source/ROM/ELF/headers/symbols and native probe archived `.local/bc-index-register-state-unrolled`; disassembly saved. R2 session8273, solo31706 and BC40 34704 running, no production promotion or gain claim. Production b4c08c5c unchanged, retained worst29.01353965FPS. Current turn adds authoritative rejection, exact restoration and distinct verified candidate (progress); full60FPS/100% goal incomplete.

Explicit state-scan continuation: previous turn classified progress (loop regression rejected and new native candidate checked). R2 session8273 and solo31706 confirmed live. BC40 completed with no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 2, 17, 0, 0, 0, 0, 0, 1, 2, 32, 0, 0, 0, 2, 0, 0, 2, 12, 0, 0, 0, 3, 0, 1, 0, 8]; net frames saved -84. Current turn adds completed timing evidence; production b4c08c5c unchanged, full goal incomplete.

Explicit register-state scan rejected: R2 matches87,845states but132,103→133,244frames, mean1,441,539.316→1,450,641.605; worst2068→2076frames (28.90173410FPS). Solo matches160,172states but166,629→166,693frames, mean891,180.465→892,467.198, span1524→1535. BC40 adds84frames. Both loop and explicit-slot versions of register equality regress; this approach is exhausted without a new compiler-level rationale. All readers terminal; restored bc_rules.c with fresh mtime and rebuilt exact retained b4c08c5c1506e00c7e2c36335ea239dccd6fc333eeb5a0323fed7dcfe8e54b59. Evidence `.local/bc-index-register-state-unrolled/rejected.json`. Previous turn classified progress; current turn yields decisive rejection/restoration (progress). Retained worst29.01353965FPS, full60FPS/100% goal incomplete. Read-only next-target review identifies repeated projectile velocity scaling in player hot path; enemy velocities already use wider pre-scaled native storage, while beams still use signed16 source velocities. Any beam-layout trial must first prove source arithmetic/padding/carry and canonical-reader conversion, then measure added RAM/stride/birth costs; no such change is yet implemented.

### Pre-scaled projectile velocity prototype — 2026-10-05
Previous turn classified progress (register-state candidates rejected and exact b4c08c5c restored). New isolated68000 motion prototype passes1,310,720cases: every signed16velocity at20full-container/fraction/boundary/dirty-padding origins. Both retained beam_axis and pre-scaled signed32 axis match independently calculated original positions/bounds including carry. Measured noinline helper cost1098.27268→930.27268coreticks/call, 15.29675% decrease, code46→42bytes. This excludes velocity production, wider stride, RAM, callers and whole-scene work; no gameplay speed claim. Initial generated-C quote typo fixed before successful execution; playable ROM unchanged.
Native compile-only ABI probe confirms BcBeam26→30bytes, BcShot32→36, BcWeapons984→1104, BcPlayerControl1024→1144; four-player extra480bytes. Shot-index/party pointers move1000/1004→1120/1124. Independent prototype decoder roundtrips4096random complete players exactly (including padding/pointers) and rejects240invalid velocity encodings. No production readers/layout changed yet. Integration contracts and evidence `.local/bc-beam-scaled-velocity-prototype/verified.json`, `layout-roundtrip.json`, native C/ELF/ROM/hook, layout assembly and scripts. Current turn adds native arithmetic/cost and lossless-layout evidence (progress). Next integrate in isolated source with header-validated canonical readers, then measure whole-scene/stride/birth/stack costs. Production b4c08c5c retained;29.01353965FPS worst4P and overall60FPS/100% goal incomplete.

### Integrated pre-scaled projectile velocities — 2026-10-05
Previous goal turn classified progress (native arithmetic prototype and lossless1144→1024byte decoder proved). Isolated candidate0cfec8a0fdb977d15e277cb074d599c78fdf7782f9dbcc6dfe38775a26e91c57 widens only native BcBeam velocities to signed32 at position scale; all nonzero birth/turn/acceleration producers convert through signed16 first, zero stores remain zero. Beam axis/position-only movement consume pre-scaled values. Portable source fixtures retain signed16. Native shot/player strides36/1144, extra480bytes across4P. Canonical player/scene/budget/workload readers use matching-header layout, validate velocity range/low8zero and normalize to original1024bytes; original pointer exclusion remains after normalization. Candidate source/headers/tools/ROM/ELF archived, production b4c08c5c unchanged.
Decoder checks pass4096randomplayers in both position layouts,8192single-bit mutations,240invalid velocity encodings rejected, plus existing2000random/8192position checks. Scene coverage964mutations across1–4P passes. Native index4096cases, host32000scans and source weapon fixture pass; independent host renderer matches. Native integrated beam_axis+bc_beam_velocity matches1,310,720original arithmetic cases. Stack4P/R8 gap10,678bytes (480less than retained), zero overlaps across82,776,792boundaries. BC40 terminal with no measurement errors or ROM changes; frame deltas [0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 1, 2, 0, 0, 0, 1, 0, 0, -1, 12, 0, 0, 0, 0, 0, 0, 0, 4, 0, 0, 0, 3, 0, 0, 2, 6], net31extra frames. Isolated primitive gain does not prove whole-game improvement. Long R2 session98953 and solo83543 running; second4P route started separately. No production promotion; current turn implements full native integration and validated cross-layout readers (progress), goal incomplete.

Pre-scaled beam integration follow-up: native projectile renderers pass589,824cases each for1P and4P, preserving artwork keys/SATflipbits/pixelcoordinates/allbeamframes/missingart/unchanged inputs under36byte stride. Host source weapon fixture passes1101updates/872main launches/198option launches/4088contact scans/1101trail updates; host renderer2400pools/37527ordered submissions/600strips passes. R2/solo/R4 handles98953/83543/99251 confirmed live; all reading immutable0cfec8a0. Profile-budget independent replay now forwards all explicit layout overrides, including beam velocity shift. No promotion or game-level speed claim.

Pre-scaled beam long evidence: R2 matches87,845canonical states and132,103→131,663frames (440saved), mean1,441,539.316→1,433,795.398; worst inclusive1000updatewindow2068frames unchanged at29.01353965FPS. Solo matches160,172states and166,629→166,501frames (128saved), mean891,180.465→886,666.613, profile span1524→1499. Native baseline and expanded encodings compare via validated lossless normalization. Started Normal40 timing/state/render4732, Home12 61924, heavyR8 ordinary30633 and charged95750. Rush remains pending until Normal terminal. R4 completion recorded in run.json when available. Current turn adds long-route gains with exact canonical gameplay matches; no promotion yet and full60FPS goal incomplete.

Pre-scaled beam additional results: R4 matches72,529states and107,238→107,038frames (200saved), mean1,272,145.196→1,267,982.723, span2017→2014. Home12 all pass. HeavyR8 ordinary1279→1284frames/mean850,359.839→852,492.424; charged1242→1237frames/mean766,727.479→768,438.461. Both1000canonical state traces match retained and independent replays verify. These mixed bounded costs are documented against gains on both long4P routes and fullsolo; worst4P window unchanged. Normal4732 remains live; Rush must follow it. No promotion yet.

### Retained pre-scaled projectile velocities — 2026-10-05
Promoted0cfec8a0fdb977d15e277cb074d599c78fdf7782f9dbcc6dfe38775a26e91c57; production rebuild matches tested candidate exactly. Native signed32 projectile velocities now share position scale, removing repeated motion shifts; all producers preserve signed16 source conversion, host reference layout remains signed16. Native shot/player stride36/1144, four-player RAM+480bytes. Matching-header readers losslessly normalize to original1024byte canonical player; range/padding validation and exact pointer exclusion retained. Eight promoted source/header/tool files listed in verified.json. Native1,310,720motion cases,4096indices,1P/4P589,824renderer cases each pass. Host source fixture and renderer pass; decoder/layout mutation tests and archived old-ROM reader replay pass.
Both long4P routes improve with exact canonical state matches: R2 132,103→131,663frames (440saved/87,845states), R4 107,238→107,038 (200saved/72,529states). Fullsolo166,629→166,501 (128saved/160,172states). Worst inclusive4P1000updatewindow stays2068frames,29.01353965FPS. BC40 adds31frames; heavyR8 ordinary1279→1284 and charged1242→1237, both state traces and independent replays pass. These tradeoffs remain documented. Normal40 exact timings/state/render hashes; Rush3000video hashes match,2990updates, zero sprite drops/remaps/wheel fallback and reset cleanup pass. Home12 passes; bounded4P/R8 stack gap10,678bytes/zero overlaps. All test jobs terminal. Evidence `.local/bc-beam-scaled-velocity/verified.json`. Current turn achieves verified native-layout integration/retention (progress); full60FPS/100% speed and natural complete4P campaign remain incomplete.

### Native projectile timer memory decrement — 2026-10-05
Previous goal turn classified progress (pre-scaled velocities retained with bothlong4P/solo gains). Revalidated production/scratch0cfec8a0. Retained R2 profile delta shows player cost283,389,470→275,696,414ticks, while actor-contact address cost increases only134,190; unchanged othermajor functions. Saved current80hottest player instructions/disassembly under `.local/bc-wide-velocity-hotspots`. Timer load/subtract/store remains a measured hotspot, motivating a targeted native decrement rather than a wider stride.
Candidate97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997 replaces four projectile-family C timer predicates with SUBQ.B/SEQ using explicit read/write byte memory and a register result; no global memory clobber. Enemy timer path unchanged. Native512 cases cover all256timerbytes/evenoddaddresses/wrap/zero result/neighbor sentinels and pass. Source weapon fixture passes1101updates. Full source/headers/tools/ROM/ELF and native probe archived `.local/bc-projectile-timer-memory`. R2 session70755, solo55411 and BC40 7168 running. Production0cfec8a0 unchanged; no performance gain claim. Current turn creates/tests a new native optimization informed by retained profile (progress); full60FPS/100% goal incomplete.

Projectile timer BC40 complete: no measurement errors or ROM changes; deltas [0, 0, 0, 0, 0, 0, 0, -1, 0, 0, 0, -1, 0, 0, -1, 0, 0, 0, 0, -2, 0, 0, 1, -8, 0, 0, 0, -1, 1, 0, -1, -6, 0, 0, 0, -4, 0, 0, -2, -4]; net frames saved 29. LongR2/solo remain pending, no promotion.

Projectile timer continuation: previous turn classified progress (native512timer cases, source fixture andBC40net29frames saved). R2 session70755 and solo55411 revalidated live, unchanged candidate97e94941 verified. Started R4 route49192, Normal40 timing/state/render71023, Home12 36514 and4P/R8stack97336. Rush must follow Normal terminal due shared scratch. Production0cfec8a0 unchanged; no whole-game speed claim. Goal remains incomplete.


### Projectile timer continuation: long replay results

Previous goal turn classified progress: launched additional mode and long-route checks; all six pending handles now confirmed terminal. Candidate `97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997` preserves all 87845 / 72529 / 160172 canonical states in the R2 four-player, R4 four-player, and solo corpora, saving 849 / 394 / 114 display frames respectively. Normal 40 samples preserve hashes and timing; all 12 modal selections pass; stack probe has no overlap and minimum gap 10704 bytes. Evidence: `.local/bc-projectile-timer-memory/run.json`. Heavy R8 ordinary/charged and Boss Rush checks launched before any promotion; full-speed goal remains unproven.


### Retained native projectile timer decrement

Retained `97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997`: four projectile timer updates use native SUBQ.B/SEQ with a precise byte memory operand; portable source semantics remain unchanged. The production rebuild matches the tested candidate exactly. Native 512-case byte/alignment/wrap/sentinel checks and the 1101-update original weapon fixture pass. Both long four-player corpora and solo preserve all canonical states (not a full-RAM/video equivalence claim), saving 849, 394, and 114 frames. Worst measured inclusive 1000-update four-player window improves from 2068 to 2060 display frames: 29.01354 to 29.12621 FPS. BC40 saves 29 frames net. Heavy R8 ordinary improves 1284 to 1270 frames, charged stays 1237, with lower attributed CPU costs and matching 1000-state traces plus independent replay. Normal40 timing/hashes unchanged; all twelve Home mode/player launches pass. Boss Rush 3000 video hashes match, 2990 updates, zero drops/remaps/fallback, reset cleanup passes. Stack gap 10704 bytes with no overlap in this route. Evidence `.local/bc-projectile-timer-memory/verified.json`. All experiment handles terminal. Full 60 FPS and natural four-player campaign completion remain unverified; goal remains active.


### Projectile timer direct-branch candidate

Previous goal turn classified progress: retained native timer memory decrement and verified exact production build. Revalidated production `97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997`. Current R2 profile still attributes 265980064 ticks to player update, the largest function. Candidate `3ab5dad12d6c434be6cbe6e803ed3926735599c9fb7ad7d77e602b6e50a9bbc0` replaces projectile SUBQ.B/SEQ Boolean production with SUBQ.B/BEQ asm-goto, matching existing enemy timer technique; memory clobber is required for writes through the input operand. Native 512 timer values/alignment/wrap/neighbor cases and original 1101-update weapon fixture pass. Full source/headers/tools/ROM/ELF/native probe archived in `.local/bc-projectile-timer-branch`. R2 long replay71925, solo58803, BC40 timing26873 launched; no performance or retention claim yet. Production unchanged, goal incomplete. Current turn implements and validates a distinct candidate (progress).


Projectile timer branch continuation: previous goal turn classified progress (distinct candidate and native/source checks). R2 handle71925 and solo58803 confirmed live again. BC40 terminal with no measurement errors/ROM changes; 35 ties, three one-frame wins and two one-frame losses, net one frame saved. Started R4 replay45647 and Normal regression17925. Read-only retained-profile instruction breakdown for top eight functions saved in `.local/bc-projectile-timer-branch/retained-hotspots.json`; no additional ROM edits while probes run. Long results are required before retention. Current turn adds measured evidence and new regression coverage; goal incomplete.


Projectile direct-branch audit: previous turn classified progress (BC40 result, extra route and Normal launches, read-only hotspot analysis). All three long canonical replays now pass: R2 87845 states/130736 frames (78 saved), solo160172/166361 (26 saved), R4 72529/106584 (60 saved). Mean scene costs 1422970.521 / 882159.117 / 1262423.106. R2 worst inclusive1000-update window regresses2060 to2061 display frames (29.11208 FPS); solo worst improves1542 to1535. Normal40 hashes/timing unchanged, no errors. Final R8 ordinary25668, charged24204, Home1243819, stack16318 and Rush62369 checks started; production unchanged. These completed comparisons change the retention decision evidence; full-speed goal remains incomplete.


Rejected native projectile timer direct branch `3ab5dad12d6c434be6cbe6e803ed3926735599c9fb7ad7d77e602b6e50a9bbc0`. Despite aggregate R2/R4/solo savings78/60/26 frames and matching canonical states, the worst R2 1000-update window costs one extra frame (2061 vs2060), and heavy ordinary R8 costs four extra (1274 vs1270); charged improves1237 to1236. Both heavy traces match and independent replay passes. All12 modal selections pass; Normal40 timings/hashes unchanged; Rush3000 video hashes match with2990 updates and zero drops/remaps/fallback/reset cleanup passes. Stack has10678-byte gap/no overlap. Tiny aggregate gains do not justify regressions in target slowdowns. Full evidence `.local/bc-projectile-timer-branch/rejected.json`. All probes terminal; scratch source restored with fresh mtime and rebuilt exactly to retained97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997. Production unchanged. Retained worst sustained measured4P remains2060 frames/29.12621FPS, not an instantaneous minimum. Goal remains incomplete.


### Solo common-contact outline experiment

Previous goal turn classified progress: completed timer-branch comparisons, rejected heavy-scene regressions, restored exact baseline. Retained R2 profile attributes153756876 ticks to common actor path, including6462400/4865168 save/restore ticks. Candidate2642db8a8b5435fea544517c55a7efe9b674efc28ef46e02cb0ae13b34e7dd93 outlines only the solo post-motion/contact dispatch at O2, preserving motion, event initialization, party selection, clocks and ordered contacts. Host32000contact comparisons/6953events, mixed live/dead routing and party boss-health tests pass. Disassembly unexpectedly adds one saved register and eight stack bytes to common entry; no performance claim until complete-route timing. Full source/header/tool/ROM/ELF archive `.local/bc-solo-common-outline/candidate`. R2 replay8872, solo84209, BC4014959 running against immutable candidate. Production97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997 unchanged. Current turn creates and validates a distinct optimization candidate (progress); full-speed goal incomplete.

Solo common outline BC40 finished: no measurement errors or ROM changes; total frame delta 111 vs retained baseline. R2/solo handles8872/84209 confirmed live. No retention decision yet.


Solo common outline rejected: both corpora preserve states but R2 adds2137 frames (130814→132951), mean1438250.289, worst2072frames/28.95753FPS; solo adds3123 (166387→169510), mean942383.701, worst1833. BC40 adds111. All handles terminal. Restored source with fresh mtime and rebuilt exact retained97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997. Evidence `.local/bc-solo-common-outline/rejected.json`. Previous goal turn classified progress (new candidate, fidelity checks and BC40); current rejection and restoration add decisive evidence. Read-only next-target audit `.local/bc-solo-common-outline/address-cost.json` measures indexed projectile address sequence at 337512 ticks across1000 scenes (0.0237 percent); any offset-index gain would be smaller and pay added build work. No new speed claim; full60FPS and native full4P campaign completion remain unproven.


### BC small-sprite vertical-first clipping candidate

Previous goal turn classified progress: completed rejection/restoration of solo actor outline and quantified projectile-address calculation as only0.0237% of sampled scene ticks, ruling it out as useful priority. Current renderer audit shows projectile drawing156422280 ticks (~11% of busy R2 window). Candidate346b1c635b3eac2b2b4cff43a2a1583c4497458a51c7bd09806fa55e6d96c4a2 reorders only BC repeat-enabled16px clipping to Y then X. Predicates remain pure with identical u16 bounds; both precede all count/cache/drop/emission effects. Normal nonrepeat path and32px/triple paths unchanged. Expected benefit depends on clipping frequency and generated register allocation, not yet measured. Archived fullsrc/inc/tools/ROM/ELF/headers and projectile assembly `.local/bc-vertical-clip-first`. R2 replay66983, solo49904, BC4079276 running; production97e949 retained unchanged. Goal incomplete, no new FPS claim.


Vertical clipping continuation: previous goal turn classified progress (new BC-only predicate-order candidate, compiled Y-first path confirmed, replay jobs started). BC40 now terminal: no measurement errors or ROM changes; net9 extra frames vs97e949. Added extracted actual before/after cached_key16 differential harness:15,728,640cases sweep all65536values on each axis against10edge coordinates, repeat/nonrepeat, count79/80, cache hit/miss/failure; exact cache-call/miss/emission trace, values, count and dropped diagnostics match. Host proof does not establish native timing. R2/solo handles66983/49904 remain live; no source/ROM mutations. Evidence `.local/bc-vertical-clip-first/run.json` andclipping.log. Current turn yields behavior and timing evidence; full-speed goal incomplete.


BC vertical-first16px clipping rejected: R2 preserves87845 canonical states but130814→130993 frames (+179), mean1425420.836 vs1423845.640. Worst1000-update window improves2060→2059frames, insufficient to offset route regression. Solo preserves160172 states and saves5frames (166387→166382), mean882859.964 slightly worse, worst1542→1540. BC40 adds9frames;15,728,640host boundary/cache/drop/emission cases match. No broad mode tests needed for rejected renderer change. All probes terminal; source restored with fresh mtime and scratch rebuilt exactly to retained97e9494141f3eed38fb78fe80ae5224549d4da8350a9072674649ed2cb2cd997. Evidence `.local/bc-vertical-clip-first/rejected.json`. Retained worst measured sustained4P29.12621FPS; full60FPS/100% speed and full natural4P campaign remain incomplete.


### Rain effect predicate ordering

Previous goal turn classified progress: completed clipping side-effect and timing checks, rejected route regression, restored97e949 exactly. Scene bookkeeping audit found prior player-pointer table experiment already rejected, so not repeated. Native general actor loop loads actor_data.random_state for every live actor before testing rain rounds5/8. New candidate9de5c0ce60c647ed33c9f197f6214e1abab1daa3ab1fca1757aac563b749865f tests exact round/handler first, then live state/RNG pointer; same pure predicate and unchanged rain reversal/common-task order. General-loop disassembly confirms pointer-load avoidance outside rain paths, but round now spills to stack: whole-route timing required. Party routing and5000event/256loop checks pass. Fullsrc/inc/tools/ROM/ELF/header archive `.local/bc-rain-gate-order/candidate`. R2 replay13704, solo59962, BC4060442 launched; production unchanged. Current turn implements a distinct evidence-based candidate (progress); no full-speed claim.


Rain gate continuation: previous goal turn classified progress (predicate-order candidate built, routing/events passed, BC40 net33frames saved with33ties/seven wins and no regressions or measurement errors). R2/solo13704/59962 confirmed live now. Started second4P route11388, Normal4036855, Home1268748, stack75222, ordinaryR844860 and chargedR86603. Source matches archived candidate. Rush remains serialized after Normal terminal. Production unchanged; no speed/retention decision before full evidence. Current turn adds verification coverage; goal remains incomplete.


Rain gate long results: R2 87845states match,130814→129810frames (1004saved), mean1416311.085, worst2060→2055inclusive1000-updateframes (29.19708FPS). Solo160172states match,166387→166140 (247saved), mean875028.868,worst1542→1507. R4 72529states match,106644→106281 (363saved),mean1257095.840/profile2013. Normal40 exact hashes/timing; Home12pass; stack10708-byte gap/zero overlaps. HeavyR8 ordinary1270→1273,charged1237→1234; both1000-state traces match/independent replay and CPU means decrease slightly. Rush72015 launched after Normal terminal. Production unchanged pending final gate. Evidence `.local/bc-rain-gate-order/run.json`; full-speed goal incomplete.


Retained rain predicate ordering as9de5c0ce60c647ed33c9f197f6214e1abab1daa3ab1fca1757aac563b749865f. Production rebuilt exactly to tested candidate; only src/bc_runtime.c promoted. Rain round/handler tests precede actor-state/RNG-pointer tests; gameplay predicate and subsequent task order unchanged. All three long canonical corpora match; R2/R4/solo save1004/363/247displayframes. Worst measured4P1000-updatewindow2055frames=29.19708FPS (not instantaneous minimum). BC40 saves33net with33ties/seven wins. R8ordinary+3/charged−3frames documented; Normal40 exact timing/hashes, Rush3000video hashes/2990updates/zero drops/remaps/fallback/resetcleanup, Home12 and bounded stack pass. All handles terminal. Evidence `.local/bc-rain-gate-order/verified.json`. Current turn completes verified promotion (progress); sustained60FPS/100% speed and full natural4P campaign remain unproven, goal active.


### Rain handler selection once per actor pass

Previous goal turn classified progress: retained9de5c0ce with matched production hash, long-route gains and all gates. New candidatea2dfe654e84a3fb329ad33e374c4845f8c5442a23a932ba48f1a223ee56202bb selects rain handler once from immutable pass round (5→b17c,8→abf6,others0). Per-actor predicate requires nonzero selector, matching handler, live state and current RNG pointer. No stale pointer/state caching; dynamic actor births/order/rain reversal unchanged. Native assembly confirms selection before loop and word comparison inside. Routing/event-filter host checks pass. Fullsrc/inc/tools/ROM/ELF/header archive `.local/bc-rain-handler-select/candidate`. R2 replay76961, solo64230, BC4034191 running. Production unchanged9de5c0ce; no speed claim before timing. Current turn creates a distinct measured follow-up candidate (progress); full60FPS and natural full4P campaign remain unproven.

Rain-handler selection BC40 terminal: no errors/ROMchanges; net frames saved -12. Long R2/solo76961/64230 confirmed live; no retention decision yet.


Rain-handler continuation: previous goal turn classified progress (candidate, host checks and BC40 evidence). R2/solo readers now terminal with87845/160172matching canonical states. R2 saves197frames (129810→129613),mean1410437.070,worst2055unchanged; solo adds49 (166140→166189),mean874920.557/profile1427. BC40+12 remains a mixed result. Started R4 replay10382, Normal41591, ordinaryR823619/chargedR88953; keep candidate immutable until terminal. Production9de5c0ce unchanged.

Independent native movement prototype `.local/bc-beam-memory-add/rejected.json` tests ADD.L directly into position memory plus preserved padding/ADDX carry and word bound extraction. All1310720velocity/origin/padding/wrap/bound cases match independent source arithmetic and retained helper; isolated candidate1014.27268 vs930.27268coreticks/call (+84/~9.03%), both42bytes. Rejected before gameplay integration. Probe used its own cartridge, never changed playable ROM. Scope excludes caller allocation, no whole-game speed claim. Current turn adds decisive native rejection and long-route evidence (progress); full-speed goal incomplete.


Rain-handler selection follow-up: previous turn classified progress (long R2/solo evidence and rejected native memory-add prototype). R4/Normal/chargedR8 handles10382/41591/8953 confirmed live; ordinaryR823619terminal and exact1273frames/849828.273mean/matching1000states/independent replay. Home1286942 and stack24128 launched. Candidate a2dfe654 remains immutable; production9de5c0ce unchanged. No retention decision yet; overall60FPS/100% speed objective incomplete.


Rain-handler final comparisons: R4 preserves72529states and106281→106039frames (242saved), mean1252300.133/profile2014 vs2013. R2 saves197/worst2055unchanged; solo+49frames documented. Normal40 exact hashes/timing, no errors; heavyR8 ordinary1273/charged1234 and CPU means exactly unchanged, both traces/replays pass. Home12pass; stack10708/no overlaps. Rush24431 started after Normal terminal. Read-only retained-budget-audit.json finds busy R2 mean requires at least36.73% scene cost reduction merely to fit frame budget, excluding outer work; current gains do not establish60FPS. Current turn adds decisive route/gate evidence (progress), goal remains incomplete.


Retained rain-handler selection a2dfe654e84a3fb329ad33e374c4845f8c5442a23a932ba48f1a223ee56202bb; production rebuild exactly matches tested candidate. Onlysrc/bc_runtime.c changed: select nonzero rain handler once per immutable pass round; still check current actor state/RNGpointer and preserve task order. Both long4P routes save197/242frames; worst measured4P1000-updatewindow remains2055frames/29.19708FPS. Solo adds49frames and BC40 adds12; R4focus span2013→2014 despite lowermean documented tradeoffs. All canonical states match. Normal40 unchanged, Rush3000video hashes/2990updates/zero drops/remaps/fallback/resetcleanup, heavyR8both traces/replays/timings, Home12 and stack10708/nooverlap pass. All handles terminal. Evidence `.local/bc-rain-handler-select/verified.json`. Current turn completes verified promotion (progress). Goal active: sustained60FPS/100% speed and full natural4P campaign remain unproven.


### Segment handler selection once per pass

Previous goal turn classified progress: completed rain-handler gates/promotion and matched production SHAa2dfe654. Revalidated production/scratch exact hash. Candidate8243615dc816074a2b96ed34168c4799e27c925ff1fced2e248e61751f20b66a selects round1bb7e/round3b7f8 segment handler once per actor pass, with zero disabled selector. Retains round7curve/segment relocation guards and earlier bullet precedence. Shared branch chooses segment vs curve using selected handler rather than comparing both fixed train IDs again. No actor/task/birth/contact/order changes intended. Routing,5000event/256loop and six-round/both-variant/1–4P segment-birth index checks pass. Fullsrc/inc/tools/ROM/ELF/headers archived `.local/bc-segment-handler-select/candidate`. R2 replay5701,solo23567,BC4024558 launched. Production unchanged; current turn implements/checks distinct follow-up candidate (progress); no new FPS claim, full-speed goal incomplete.

Segment-handler BC40terminal: no measurement errors/ROMchanges; net frames saved 21. Long handles5701/23567confirmed live. No promotion decision yet.


Segment-handler continuation: previous goal turn classified progress (candidate implementation, routing/event/birth checks, BC40net21frames saved). R2/solo5701/23567confirmed live. Added R4 route45241, Normal61262, Home1274741, stack87499, ordinaryR866339 and chargedR896605. Rush must follow Normal terminal. Immutable candidate8243615d remains isolated; productiona2dfe654 unchanged. Goal incomplete, no new speed claim.


Segment-handler route comparisons: all87845/72529/160172states match. R2 129613→129417 (196saved), mean1413397.272 slightly worse than1410437.070, worst2055unchanged. R4 106039→105829 (210saved),mean1250712.652/span2011. Solo166189→166142 (47saved),mean873005.266,worst1492. Normal40hashes/timing exact; Home12pass; stack10708/no overlaps. HeavyR8ordinary1273/charged1234 exacttiming/means/states and independent replay. Rush75124 launched after Normalterminal. Evidence `.local/bc-segment-handler-select/run.json`. Current turn adds completed route/gate evidence (progress); overall60FPS goal incomplete.


Retained segment-handler selection8243615dc816074a2b96ed34168c4799e27c925ff1fced2e248e61751f20b66a. Production rebuild exactly matches tested candidate; onlysrc/bc_runtime.c promoted. R2/R4/solo save196/210/47displayframes with complete canonical traces matching; BC40net21saved; worst measured4P remains2055frames/29.19708FPS. R2profilemean slightly higher remains documented. Native code keeps actor/task/birth/contact order and round7 relocation guard; host routing/event/birth checks pass. Normal40 unchanged, Rush3000video hashes/2990updates/zero drops/remaps/fallback/resetcleanup, heavyR8both state/replays/timings unchanged, Home12 and stack10708/nooverlap pass. All handles terminal. Evidence `.local/bc-segment-handler-select/verified.json`. Current turn completes verified promotion (progress); full60FPS/100% speed and full natural4P campaign remain unproven, goal active.


### Common handler before rain selector

Previous goal turn classified progress: retained segment selector8243615d with matched production build/all gates. Candidate d9babb0793f15068ffc6d68d393acd4535eea2c15d0501a3f96358fb49408d0a initializes rainfalse and evaluates its predicate only after handler9eb1fails. The only rain selectors areb17c/abf6, so9eb1always had rainfalse; reversal/common-task/sink order unchanged. Native disassembly confirms common comparison before selector tests for live actors; current register allocation must be measured. Routing and event-filter checks pass. Fullsrc/inc/tools/ROM/ELF/headers archived `.local/bc-common-handler-first/candidate`. R2 replay31905,solo29482,BC4049196running. Production8243615d unchanged, no new speed claim; current turn implements/tests distinct dispatch candidate (progress), goal incomplete.

Common-handler-first BC40terminal: no measurement errors/ROMchanges; net frames saved -20. Long handles31905/29482confirmed live. No promotion decision yet.


Common-handler-first rejected: both long corpora match87845/160172states but R2 adds562frames (129417→129979),mean1417181.227,worst2056vs2055; solo adds115 (166142→166257),mean876601.404,worst1515vs1492. BC40adds20. Native branch priority alone does not improve full-loop register allocation/work. All readers terminal; restored source with freshmtime and rebuilt exact8243615dc816074a2b96ed34168c4799e27c925ff1fced2e248e61751f20b66a. Evidence `.local/bc-common-handler-first/rejected.json`. Previous goal turn classified progress (candidate, hostchecks, BC40); current turn resolves long comparisons/rejection/restoration (progress). Existing ordered draw-list/row-mask trials also reviewed before repeating occupancy metadata changes; no new changes from that review. Retained worst measured sustained4P29.19708FPS; full60FPS/100% speed and natural full4P campaign remain unproven, goal active.


### Normal AUTO fixed-range update candidate

Previous goal turn classified progress: rejected common-handler-first regression and restored8243615d. Fresh retained Normal4Psection3 profile reproduces1040frames/1000updates (57.6923FPS), matching prior1001state/render hashes, zero drops/remaps. Evidence `.local/normal4p-section3-current/verified.json`; whole-run CPU profile includes setup and VBlank waiting, so percentages are not pure worst-frame costs. Native weapons_fire hotspot includes variableMULU#22 for AUTO8/9slot endpoint. Candidate8c0e57e8cdcf56555e3396a00fe786152bc6a42ecf2effb3f5f892833105dbd3 branches once to constant8/9slot upd_linear calls; same firing, simulation order/ranges, collisions and rendering. Native disassembly no longer containsMULU#22 in weapons_fire. Fullsrc/inc/tools/ROM/ELF archive `.local/normal-auto-fixed-count/candidate`. Normal40state/render comparison47415running; Rush must wait for Normalterminal. Production unchanged. Current turn adds current-mode profiling and a compiled optimization (progress); all-mode60FPS and BCfull4P campaign goal remains incomplete.


Normal AUTO candidate follow-up: previous goal turn classified progress (profile, native candidate, comparison launched). The intervening FPS answer verified retained measurements but made no optimization progress. Normal matrix47415 is terminal: 40/40 state/render comparisons match, no measurement errors; saved frames by1/2/3/4P =0/-1/0/8. Four-player combined10000updates/10106frames (~59.37067FPS), worst section3unchanged1040frames. Rush38124terminal: all3000video hashes match,2990updates, zero sprite drops/remaps/wheel fallbacks, exit cleanup true. BC40handle52058running. Added optional AUTO pickup16/17 selection to fixed-update QA (default17unchanged) to cover both constant loop lengths; retained AUTO16section3comparison launched before candidate run, serialized with Rush. Evidence `.local/normal-auto-fixed-count/interim.json`. Production8243615d unchanged; candidate not yet approved/promoted. Goal remains incomplete.

AUTO16 follow-up terminal: {"state_hashes": true, "render_hashes": true, "baseline_frames": 1002, "candidate_frames": 1002}. BC40terminal: all40frame counts unchanged, no measurement errors or ROMchanges. Long BC4P replay84824and Home12modal48110launched on immutable8c0e57candidate; no production promotion yet.

Previous goal turn classified progress: completed Normal40/Rush/AUTO16/BC40 comparisons and added both AUTO levels to QA. Current follow-up: Home12terminal/pass, stackterminal10708-byte minimum gap and zero overlaps. R2replay84824confirmed live; solo59359and protected R8/replay34501launched. No ROM/source rebuild while readers are active. Read-only review found the proposed Normal last-shot-key cache had already been rejected (`normal-shot-repeat`,1144vs1139frames); no duplicate candidate was introduced. Evidence `.local/normal-auto-fixed-count/interim.json`; production unchanged, full-speed/full4P completion remains unproven.

Protected R8/replay34501terminal: {"states_match": true, "replay_verified": true, "before_frames": 1273, "after_frames": 1273, "before_mean": 849828.273, "after_mean": 849828.273}. Long R2/solo84824/59359last polls confirmed live.

Previous goal turn classified progress: Home12/stack/R8 verified and long solo started. R2replay84824terminal:87845canonical states match,129417frames and mean1413397.272ticks unchanged. Solo59359still active. Added optional host-only measurement phase gating to profile_genesis and Normal QA; profile-measurement excludes intro/warp without changing guest memory/instructions/cycles. Production baseline measurement63577launched with state/render hashes to verify instrumentation. Candidate not promoted; all-speed goal remains open.

AUTO fixed-count retained: solo59359terminal matches160172states,166142frames, mean873005.266unchanged. All readers terminal before production build81319; final production SHA8c0e57e8cdcf56555e3396a00fe786152bc6a42ecf2effb3f5f892833105dbd3matches tested cartridge. Normal4P10000/10106 (~59.37067FPS), worst1040/1000unchanged;2Pcosts one frame in one bounded sample. Full evidence `.local/normal-auto-fixed-count/verified.json`. Measurement-only profiler preserves1001state/render hashes and1040frames; attribution includes VBlank waits but excludes intro/warp, revealing player update13.15%,shot draw8.67%,weapon fire6.26%of all measured cycles. Scope is bounded, not full-game proof. Current turn progress: completed replay gates, retained source/ROM optimization, added verified scoped profiling. Goal remains active and incomplete.


### Normal multiplayer target wrap candidate

Previous goal turn classified progress: retained AUTO fixed-count8c0e57with replay gates and verified measurement-only profiling. Correction to previous attribution: native symbol inspection shows update_all.lto_priv.0 is enemy processing (en_dbg_spawn/choose_target/collect_shots), not player processing; its measured13.15%must not be labeled player update. Candidateb6f6c7c0a9d4257338a70486957c576c1dc12f44a69739f826e520bfc8eb96bd replaces per-candidate signed general modulo in3/4Pchoose_target with a32-byte3Pstart table/4Pmask and increment/wrap. Tick cadence, complete cyclic scan order, living-player test, coordinates and no-live fallback are preserved;1/2Pbranch unchanged. Exhaustive6144tick/count/live-mask combinations verify identical ordered candidates and selections (`selection-proof.json`); this arithmetic proof is complemented by actual cartridge state/render comparisons, not treated as whole-game proof. Fullsrc/inc/tools/ROM/ELF archived `.local/normal-target-wrap/candidate`. Normal40comparison49727running; do not run Rush/qa_soak concurrently or rebuild its ROM. Production8c0e57unchanged. Current turn creates/tests a new candidate, goal remains incomplete.

Target-wrap follow-up: previous goal turn classified progress (compiled candidate, arithmetic proof, Normal40launched). Added independently compiled actual before/after choose_target and weapon_weight functions:663552cases covering1–4P,256tick bytes,81OFF/ALIVE/DYINGcombinations and8coordinate/loadout/orientation scenarios. All target coordinates and resulting tick bytes match (`host-selection.json`, reproducible `check_target.py`); host proof is not native timing. Native disassembly has no __modsi3/__divsi3 reference in enemy update. Normal49727confirmed live; completed1/2P and partial3Pcomparisons match. BC4033234launched on immutablecandidate. Production8c0e57unchanged; no new speed claim.

BC40target-wrap terminal: all40timings unchanged, no measurement errors or ROMchange. Normal49727still live at last poll.

Target-wrap rejected: Normal40terminal, all state/render hashes match and no errors, but aggregate timing unchanged in every player count.4Psection7saves1frame and section8costs1; worst section3unchanged. BC40unchanged. All readers terminal, restored original enemies.c with freshmtime and rebuilt exact retained8c0e57. Evidence `.local/normal-target-wrap/rejected.json`. Current turn progress: exhaustive actual-source fixture, completed comparisons, rejected neutral candidate and verified restoration. No active jobs. Full-speed and natural full4Pport completion remain incomplete.


### BC packed triple spacing candidate

Previous goal turn classified progress: rejected timing-neutral Normaltarget-wrap and verified restoration. Retained BC R2profile attributes156422280/1413397272ticks (~11.07%)to projectile_draw_multi. Candidate1b7bbcd6bc4598ef50e03a56d0895e6c687081e37086de3b54c32336eeb234e3reuses signed full-width bx-x spacing for the +/-8 test and compares cx-bx to it, replacing separate forward/reverse arithmetic. No narrowing/wrap assumption, slot order, triple eligibility, art, grouping or fallback change. Solo core unchanged. Host renderer passes2400pools/37527ordered sprites/600packed strips including dirty padding. Archivedfullsrc/inc/tools/ROM/ELF/headers, native assembly. Long R2replay43513and BC4082175running; native4Part/coordinate probe also launched. Production8c0e57unchanged. Current turn builds/tests a distinct rendering arithmetic candidate; goal remains incomplete.

Native4Pprobe56819terminal/pass589824cases: artwork keys, SATflips, coordinates, missing-art handling and unchanged inputs. LongR2/BC40timing remains pending.

Triple-spacing follow-up: previous goal turn classified progress (candidate, host2400/native589824renderer checks, replay and matrix launched). BC4082175terminal:40timings unchanged, no measurement errors. R243513confirmed live. Added retained per-instruction player histogram/assembly (`retained-player-hotspots.json`), showing the30-slot weapon dispatch and beam motion as the largest repeated instructions. Existing docs identify earlier weapon-outline and PRE trials; no duplicate source candidate applied. Solo replay started on the same immutable ROM to verify compiler spill/layout effects despite unchanged solo renderer source. Production unchanged; all-speed goal incomplete.

Triple-spacing long4P43513terminal:87845canonical states match;129417→129411displayframes (6saved),mean1413397.272→1413362.412ticks. Worst inclusive1000updatewindow2055→2054frames,29.211295FPS; this is not instantaneous minimum/fullcampaign proof. Previous goal turn classified progress (BC40result, mapped current weapon hotspot, solo launched). Current turn resolves4Pcomparison and launches ordinary/chargedR8checks64861/10290plus Normal40/Home12compatibility. Solo51935still live at last poll. Production8c0e57unchanged; small gain requires remaining gates, goal remains incomplete.

R8ordinary/charged terminal: {"r8": {"states_match": true, "replay_verified": true, "before_frames": 1273, "after_frames": 1273, "before_mean": 849828.273, "after_mean": 849828.273}, "r8-charge": {"states_match": true, "replay_verified": true, "before_frames": 1234, "after_frames": 1234, "before_mean": 766300.542, "after_mean": 766300.542}}. Solo51935confirmed live; Normal56328and Home1270758pending.

Triple-spacing continuation: previous goal turn classified progress (long4Presult and R8ordinary/charged verified). Home1270758terminal/all12pass. Solo51935and Normal56328confirmed live by tool handles; completed1/2P Normalcomparisons match timing/state/render. Started distinct older4P/R4route to check mixed-weapon heavy scenes and bounded4P/R8stack safety. Production and reader ROMs unchanged. Goal incomplete; no new full-speed claim.

Solo51935terminal:160172canonical states match,166142frames and mean873005.266unchanged. Stack98271terminal:10708-byte minimum gap, zero overlaps. Read-only compiler investigation confirms -fomit-frame-pointer already enabled in actual build flags; do not repeat that as a new optimization. Native player LINK therefore is not evidence that flag is absent. Pending Normal56328and older4P/R4replay77314; Rush must wait for Normalterminal. Production unchanged.

Normal56328terminal: {"all_hashes_match": true, "saved_frames": 0, "errors": []}. Rush3000-framecomparison launched after terminal Normal.

Triple-spacing final-gate follow-up: previous goal turn classified progress (solo/Home12/stack/Normal40resolved, Rushstarted). Rush99500terminal: all3000video hashes match,2990updates, no sprite drops/runtime remaps/wheel fallbacks, reset cleanup true. Older4P/R4replay77314confirmed live. All other candidate gates terminal; do not rebuild while that reader runs. Production remains8c0e57. Read-only review of actual SGDK flags identifies disabled-web register allocation as an untested future player-routine hypothesis; no compiler/source changes made during live replay. Goal remains incomplete.

Triple-spacing retained: older4P/R4replay77314terminal72529states match,105829→105830frames(+1),mean1250712.652→1250648.287ticks, span2011unchanged. This one-frame route cost is accepted against R2saving6frames and worst inclusivewindow2055→2054, with unchanged solo/BC40/Normal/R8/Rush and all rendering/Home/stack gates passed. All readers terminal before productionbuild45988. Production rebuilt exact tested1b7bbcd6bc4598ef50e03a56d0895e6c687081e37086de3b54c32336eeb234e3. Evidence `.local/bc-triple-spacing/verified.json`; active selection updated. Current turn progress: completed final gates and retained verified renderer change. Full-speed and natural full4Pcampaign remain incomplete; current worst measured BC4P29.211295FPS, Normal4P59.37067average/worst57.6923.


### BC player web register allocation candidate

Previous goal turn classified progress: retained triple-spacing1b7bbcd6after final gates and exact production build. Native-only optimize("web") on existing noinline bc_player_step_into re-enables GCC register-web construction disabled by actual SGDK -fno-web. No source gameplay rules/order/ABI changes. Candidatea3c4f2d9babd38147cb1c1d3445316db925302ea4e7682ec0894252f0b80c394is not byte-identical: native player9040→9124bytes, local frame224bytesunchanged; build has no warnings/errors. Fullsrc/inc/tools/ROM/ELF/flatheaders and native player assembly archived `.local/bc-player-web/candidate`. Long R2replay80937and solo54488running; BC40also launched. Production1b7bbcd6unchanged; no speed claim and do not rebuild while readers run. Current turn creates/measures a distinct compiler-register-allocation candidate. Fullspeed/full4Pcompletion remain incomplete.

Player-web continuation: previous goal turn classified progress (compiled distinct candidate/archived/dispatched three gates). BC4095297terminal:all40timings unchanged, no measurement errors/ROMchanges. Long R280937and solo54488confirmed live; no reader restart/rebuild. Read-only incomplete natural4Pdeath audit archived `natural4p-last-deaths.json`: final losses inR8scrolling section before boss, so boss-eight-only lookahead changes would not address this route endpoint. This is controller-test diagnosis, not evidence of a port behavior bug. Production1b7bbcd6unchanged and full objective incomplete.

Player-web rejected: long80937/54488terminal,87845/160172canonical states match but exact timing unchanged:129411/166142frames, R2mean1413362.412,solo873005.266. BC40alsounchanged. All readers terminal before restoring/rebuilding exact1b7bbcd6(87870). Evidence `.local/bc-player-web/rejected.json`. Previous goal turn classified progress (BC40resolved and natural4Pdeath diagnosis); current turn completes rejection/restoration.

New native-only optimize("gcse") candidatead5fc450d085f6f0cd0e5f92ec7571c1549861f88143e71234ac62cba987ba1fre-enables common-subexpression elimination disabled by actual SGDK-fno-gcse; web remains baseline-disabled. Only existing noinline bc_player_step_into marked; no gameplay/ordering/ABI change. Native player9040→8998bytes,224-bytelocalframeunchanged. Fullsrc/inc/tools/ROM/ELF/flatheaders+assembly archived `.local/bc-player-gcse/candidate`. LongR293473,solo65631andBC4099748running. Production1b7bbcd6unchanged; no speed claim. Goal remains incomplete.

GCSEcontinuation: previous goal turn classified progress (rejectedweb/restored exactbaseline/newgcsecandidate). BC4099748terminal:net2additional frames across40samples, deltas archivedrun.json; no measurement errors. LongR293473/solo65631confirmed live. Native before/after instruction comparison archived `changed-instructions.json`; many differences are stack offsets, so summed baseline costs of altered instructions are not predicted savings. Await long measured results before retention. Production1b7bbcd6unchanged, full goal incomplete.

GCSEfollow-up: previous goal turn classified progress (BC40resolved and instruction comparison). R293473terminal:87845canonical states match,129411→129440frames(+29),mean1413362.412→1413759.102; worstinclusive1000window2054→2055(29.19708FPS). Reject for regression. Solo65631confirmed live; leave immutablecandidateuntil terminal before restoration. Production stillverified1b7bbcd6, so current public worst remains29.211295FPS. Goal incomplete.

GCSErejection finalized: solo65631terminal160172statesmatch,166142→166148frames(+6),mean873005.266→873194.392ticks. All candidate readers terminal. Originalbc_player.c restored withfreshmtime, rebuild14765verifiesexact1b7bbcd6. Evidence `.local/bc-player-gcse/rejected.json`. Native-onlywebandgcsechangesbothremoved; no active jobs. Current turn progress completes regression audit/restoration. Reviewed prior beam-launch-outline trials before considering stack refactoring; do not duplicate the already-rejected approach without new evidence. Current retained speed unchanged and full objective incomplete.


### Turret handler once per actor pass

Previous goal turn classified progress: rejectedgcse after both route regressions and exactbaseline restoration. Candidate5efaee159d28eca17d1678d53a7503815b10831d87688333263a14f285f0817eselects turret handlerb9d2 once when round1/relocation-535, then retains per-actor live-state and current random-state-pointer checks. The selected round resource relocation is initialized in bc_scene round-load; no actor task mutates it. All earlier bullet/segment/common precedence remains unchanged. This follows retained rain/train handler selection, with no C gameplay/task/ordering/ABI change. Hostrouting32combinations and eventfilter5000events/256loops pass. Fullsrc/inc/tools/ROM/ELF/headers archive `.local/bc-turret-handler-select/candidate`. LongR241260,solo30469,BC4079531running on immutableROM. Production1b7bbcd6unchanged. Current turn creates/tests a distinct native dispatch candidate; fullspeed/full4Pcompletion remain incomplete.

Turret-selector continuation: previous goal turn classified progress (candidate+hostrouting/events+long comparisons). BC4079531terminal:net3additionaldisplayframes across40samples, no measurement errors/ROMchanges; exactdeltasrun.json. LongR241260/solo30469confirmed live. Added original-PCEcompleteactor-loop verification against round2-walker-late capture/code002160 to strengthen direct turret/fallback behavior evidence beyond synthetic observer/routing fixtures. Production1b7bbcd6unchanged; no new speed claim. Goal incomplete.

OriginalR2capture20076terminal/pass:2401complete loops,29805actor updates,69child updates including36later-slot updates,113retirements, zero unsupportedloops. Fullworld/player/task comparison is bounded to this capture; not whole-game proof.

Turret-selector rejected: both long readers terminal,87845/160172statesmatch but R2129411→129450frames(+39),mean1413799.919,worst2055; solo166142→166149(+7),mean873184.368,worst1498. BC40adds3. Restoredbc_runtime.c/rebuilt85551exact1b7bbcd6before next candidate. Evidence `.local/bc-turret-handler-select/rejected.json`. Previous goal turn classified progress (BC40andoriginal2401loopfixture); current turn resolves rejection/restoration.

### Direct round-two ceiling task
Candidatebf3b57cd8d48c5572da277d80e44377a64fde4130ff6021f40855ecd4c015200adds bc_actor_ceiling_common_into: existingceiling_prepare thenexistingcommon, aftercallerscroll. Actorloopdirectpathguardedround1/relocation-535, alivebdad/be08/be24or nonlivebe4e; earliercommon/bullet/segmentprecedence untouched, customrelocationfallsback. Usesexistingempty simpleenvelope; ceilingtaskdoesnotemit separatechild/events. Later-slot sibling changes and common contact/event order retained. OriginalR2fixture passes2401loops/29805updates/69children/36later-slotupdates/113retirements; routing32and eventfilter5000/256pass. Fullsrc/inc/tools/ROM/ELF/flatheaders archived `.local/bc-ceiling-direct/candidate`. LongR271606,solo69035andBC4087363running. Production1b7bbcd6unchanged; no speedclaim. Goalfullspeed/full4Pcompletion remains incomplete.

Ceiling-direct continuation: previous goal turn classified progress (turretreject/restoration/directceilingcandidate+original/routing/events). BC4087363terminal:net1displayframe saved across40samples,no errors/ROMchange; exactdeltasrun.json. LongR271606/solo69035confirmed live. Originalfixtureoccupancy audit confirms bdad290/be0857/be24434, no be4e. Additional originalcaptures lack familycoverage. Added independent hostbaseline/candidate complete-loop fixture specifically for death/revival:480cases across3nonlive states,16speeds,5waits,standard/customrelocation; all fullactors/player/counters/eventfields match, everyloophandled. Evidence `death-fixture.json` and reproducible `death_fixture.py`. This closes a specific testing gap, not fullgameproof. Productionunchanged; objectiveincomplete.

Direct-ceiling long71606/69035terminal:87845/160172statesmatch. R2mean1413362.412→1378568.947andworst2054→2037(29.45508FPS)improve, but fullroute129411→129491(+80); solo166142→166177(+35),mean873628.679,worst1503. Not retained. Fullmeasurements `.local/bc-ceiling-direct/measured.json`. All readers terminal before refinement.

Handler-firstrefinementf8bc24cbdb12053734a21b2844bb0e958fd1a7b2ebec1cc3194872e9d520ec3frejects unrelatedhandlers before checking round/resource, then separatesdeathbe4estatefromthree livehandlers. Same direct-ceilinghelper/header remain; production baseline still1b7bbcd6. Native build/archive `.local/bc-ceiling-handler-first/candidate`; actualbaseline/candidate480deathfixture rerunpasses. LongR216648/solo29972running. To restore production later use allthree beforefiles in `.local/bc-ceiling-direct`, not onlyrefinementbefore.c. Currentturnprogress:closeddeathcoveragegap,completedrouteevidence,implementedmeasured-rationale refinement. Goalremainsincomplete.

Ceilinghandler-first continuation: previous goal turn classified progress (deathfixture/longfirstvariantresults/refinement). R216648/solo29972confirmed live. OriginalR2fixture20527terminal/pass2401loops/29805updates/69children/113retirements. BC4096862launched. Added read-only per-reference-round tick-bin analysis of firstvariant in `.local/bc-ceiling-direct/route-round-spans.json`: addedframesR1..R8=[4,12,0,3,9,40,11,1]. MajorityregressionoutsideR2despiteheavyR2windowgain; bins are reference transition ranges, not per-frameFPS. This supports testing unrelatedhandlerrejectcost, not a claim that refinedcandidatewins. Production1b7bbcd6unchanged; goal remainsincomplete.

RefinedBC4096862terminal:net78addedframes,no measurementerrors/ROMchanges. LongR2/solo remainpending.

Ceilingrefinementfollow-up: previous goal turn classifiedprogress (originalfixture/BC40resolved/per-roundfirstvariantanalysis). R216648terminal87845statesmatch but route129411→130256(+845),mean1380469.727,worst2041vsretained2054. HeavywindowgaincannotjustifybroadroutecostandBC40+78. Rejectbothceilingvariants. Solo29972confirmedlive; keepcandidateimmutableuntilterminal, thenrestoreallthreeoriginalfilesfrombc-ceiling-direct. Productionunchanged,fullgoalincomplete.

Bothceilingvariantsrejected/restored: solo29972terminal160172statesmatch but166142→166453(+311),mean878694.677. Allreadersterminal; restoredsrc/bc_runtime.c,src/bc_world.c,inc/bc_world.hfromoriginalbeforefiles withfreshmtime. Build62786exactretained1b7bbcd6verified; bothvariantrejected.jsonfilesrecordrestoration. Noceilinghelperremainsinproductionorscratch, noactivejobs. Currentturnprogresscompletesfullroutecomparisonsandrevertsregression. RetainedBCworst29.211295FPS,Normal4P59.37067average remainunchanged; fullspeed/full4Pobjectiveincomplete.


### First eligible projectile initializes index bounds

Previous goal turn classified progress: rejected bothceilingvariants/fullrestorationexact1b7bbcd6. Candidateb0d8d250483d999f035cb2a3c40dab9c969213834cb54f503e713f685e4731fainitializes min/max/radii directly when previousindexcountzero; lateritems use min/elsemax because initialized bounds satisfymin<=max. Emptyindexinitialization/eligiblegates/slotorder/coordinates/countincrement remainunchanged. NoABI/simulation/renderingchange. Native4096completeindices passincludingdirtypadding/fractions/state/flags/radii/sentinels/unalteredweapons; host32000scans/5336contacts/2070damaginghitspass. Fullsrc/inc/tools/ROM/ELF/flatheaders archive `.local/bc-index-first-bounds/candidate`. LongR214645,solo87012,BC4071037running. Production1b7bbcd6unchanged; no speedclaim. Currentturnbuildsandvalidatesdistinctindexbuildercandidate; fullspeed/full4Pgoalremainsincomplete.

Indexfirstboundscontinuation: previousgoalturnclassifiedprogress (candidate+native4096/host32000checks+replays). BC4071037terminal net1frame saved,no measurementerrors/ROMchange. LongR214645/solo87012confirmedlive. Foundqa_bc_shot_index_native.pyignored--output andalwayswrotefixedscratchfolder; fixedCLIargparse(defaultunchanged), archivedpriorprobe/native-initial, reran27259terminal4096pass/7557framesintocandidate/native. VerifiedprobeROM/sourcechecksumsnative/verified.json;toolschangeisalow-riskQAevidencefixanddoesnotchangeplayableROM. Production1b7bbcd6unchanged,fullgoalstillincomplete.

Indexfirstboundsrejected: longR214645/solo87012terminal87845/160172statesmatch. R2route129411→129364(47saved),butmean1413362.412→1415023.981andworst2054→2055regress; solo166142→166183(+41),mean873005.266→874399.463,worst1507. Restoredoriginalbc_rules.cafterallreadersterminal,rebuild7599exact1b7bbcd6. Evidence `.local/bc-index-first-bounds/rejected.json`. NativeQA--outputfixretained; no gameplaycandidate remains. Currentturnprogressresolvescandidateandfixesevidencearchiving. Full60FPS/full4Pgoalremainsincomplete.


### Native index append register call

Previousgoalturnclassifiedprogress (indexfirstboundsrejected/restored,QAoutputfixretained). Candidate6c8e0f4a22942ebb3ac0e54aa7481ce138c5f6590f0ef99e959f14e294770b83addsprivate68000leafABI a0=index,a1=beam,d0.b=slot; appenderpreservesa0/a1andclobbersd0/d1/CCRonly. Inlinecallconstraintsdeclaretheseplusmemory. Nativeeligibility/append/bounds/radii/orderexact; hostkeepsoriginalChelper. Removesper-eligible-shotstackargumentmarshalling; empty-slotgatesand28slotsunchanged. Firstlinkfailure(localassemblysymbolacrossLTOpartitions)fixedwithhidden global symbol; finalbuildpasses. QAextractoracceptsadditionalhelperattributes. Native4096completeindicespass,probe7513framesvsprior7557(notgameplaytiming);host32000scanspass. Fullarchive `.local/bc-index-regcall/candidate`,nativeprobe/ELF/ROMandassemblyretained. LongR277449,solo46962,BC4056866running. Production1b7bbcd6unchanged. Currentturnimplementsandverifiesdistinctnativecall-costoptimization; goal remainsincomplete.

Indexregcallcontinuation: previousgoalturnclassifiedprogress(newnativeleaf+4096indices/32000scans+replays). BC4056866terminalnet3frames saved, noerrors/ROMchanges. LongR277449/solo46962confirmedlive. IndependentnativeABIprobe(check_abi.py/abi_runner.py)executeseligibleandrejectedcallswithD2-D7/A0-A6sentinels;allpreserved,SPexact,eligibleindexslot/x/ycorrect. OnlydeclaredD0/D1/CCRareunconstrained. ProbehasownROManddoesnotmodifyplayablecandidate. Evidenceabi.logandabi/;production1b7bbcd6unchanged,goalstillincomplete.

Regcalllongreplays77449/46962terminal:87845/160172statesmatch. R2129411→128513(898saved),mean1413362.412→1400600.95,worst2054→2052(29.239766FPS). Solo166142→165953(189saved),mean873005.266→867729.072,worst1492→1457. Bothroute/CPU/worstimprovementsjustifybroadergates. LaunchedR456909,Normal405968,R8ordinary55912/charged13628. RushmustwaitforNormalterminal(sharedoffsetscratch). Candidateimmutable,production1b7bbcd6unchanged;notpromotedyet. Currentturnprogress:nativeABIcheckandlongresults;goalstillincomplete.

Regcallcontinuation: previousgoalturnclassifiedprogress(nativeABI+longR2/soloimprovements+remaininggates). R8ordinary55912/charged13628terminal:1000statesmatchandindependentreplaysverified. Ordinary1273→1268frames,mean849828.273→848486.331;charged1234→1233,mean766300.542→763750.995. LongR456909/Normal5968confirmedlive. Home1295521andstack72857launched;RushmustwaitforNormalterminal. Production1b7bbcd6unchanged;candidate6c8e0f4aimmutable. Objectivefullspeed/full4Pstillincomplete.

Home1295521terminalall12pass. Stack72857terminal: {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2280, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2280, "overlap_samples": 0, "sampled_boundaries": 82627348}. No additional claimbeyondboundedroute.

Normal5968terminal: {"all_hashes_match": true, "saved_frames": -2, "errors": []}. RushlaunchedafterNormalterminal;R4remaining.

Regcallretained: previousgoalturnclassifiedprogress(R8/Home/stack/Normalresolved,Rushlaunched). R456909terminal72529statesmatch:105830→105292frames(538saved),mean1250648.287→1241578.254,span2011→2007. Rush40536terminal3000video hashesmatch,2990updates,zero drops/remaps/wheelfallback,resetcleanuptrue. Allgates/readers terminal beforeproductionbuild2407. Added compile-timeassertsforeveryhardcodedindex/beamoffset; productionandscratch94590rebuildexacttested6c8e0f4a22942ebb3ac0e54aa7481ce138c5f6590f0ef99e959f14e294770b83. NativeABItestsand4096indicespass; BC40net3saved;Normal39ties/4Psection9costs2withallstate/renderhashesmatching;Home12pass,stackgap10682/nooverlap. Evidence `.local/bc-index-regcall/verified.json`;selectedmanifestupdated. ProductionBCworst1000update4Pwindow2052frames=29.239766FPS,Normal4Paggregate59.358923624851606FPS,worst57.6923. Full60FPS/100%speed and naturalfull4Pcampaignremainincomplete. Currentturnprogressretainsverifiednativeimprovement;noactivejobs.


### Native whole-index scan candidate

Previous turn classified no progress toward implementation: it answered the regular-mode FPS question from existing measurements. Revalidated retained production SHA 6c8e0f4a and selected manifest before taking the next optimization action. Candidate ab085ddf411b023e92e7ff67405d3ebdf30a34c8eeb99e9772e0c657f842dfed moves the 28 ascending state gates and index initialization into a private native 68000 scan, retaining the existing append helper and every eligibility/collision-order rule. Fixed a0/a2 inputs are preserved; a1/d0/d1/CCR/memory clobbers declared. Compile-time offsets and sizes checked. Production is unchanged; scratch candidate archived with sources, headers, tools, ROM, ELF and symbols in `.local/bc-index-whole-scan/candidate`.

Native 4096 full-index comparisons pass, including dirty padding, fractions, flags/states, radii, unchanged weapon bytes and index sentinels. Native ABI probe passes eligible/rejected cases preserving D2-D7/A0/A2-A6/SP. Host 32000 scans, 5336 contacts, 2070 damaging hits pass. Isolated probe 7489 frames versus retained 7513; this is not gameplay performance. BC40 completes without measurement errors or ROM changes: net one frame saved; three samples each cost one frame. Long natural 4P R2 replay session 67322 and solo session 50208 confirmed live; do not rebuild scratch while they read it. Evidence `.local/bc-index-whole-scan/pending.json`. Candidate is not promoted. Full 60 FPS/100% speed and natural full 4P campaign remain incomplete.


Whole-index scan continuation: previous goal turn classified progress (new native implementation, native/host correctness and ABI checks, BC40, long replay launch). Re-polled live sessions 67322 (natural 4P R2) and 50208 (solo); both remain running, without terminal output. No restart or build performed. Saved read-only retained-build player instruction attribution to `.local/bc-index-whole-scan/retained-player-hotspots.json`: hot instructions include shot state scan, phase/acceleration tests, and native beam movement inside bc_player_step_into. This identifies the next investigation after current candidate resolves; it is not a speed result or source change. Current turn is a verified wait with read-only profiling evidence. Production remains retained 6c8e0f4a; scratch ab085ddf remains immutable. Full goal incomplete.


Correction to preceding wait entry: the final poll returned terminal exit 0 for both 67322 and 50208. Inspected completed artifacts: 87845/160172 gameplay states match. R2 128513→128312 display frames (201 saved), mean scene ticks 1398442.087, worst inclusive 1000-update window 2046 frames = 29.325513 FPS (previous 2052). Solo 165953→165899 (54 saved), mean 866692.925, worst 1450 (previous 1457). Evidence long-results.json. These improvements justify broader gates: R4 session18607, Normal40 session78108, R8 ordinary35641 and charged77410 launched. Rush must wait for Normal terminal because of shared offset scratch. Current turn classified progress from completed long results and next gates, superseding the earlier verified-wait classification. Production unchanged; candidate not promoted; full goal incomplete.


Whole-scan continuation: previous goal turn classified progress (long replay improvements, broader gates launched). R8 ordinary35641 and charged77410 terminal: all 1000 state hashes match retained baseline and independent replays verify. Ordinary 1268→1267 frames, mean scene ticks 848486.331→848373.778; charged 1233 frames unchanged, mean 763750.995→763369.677. Home12 session90745 terminal: every mode/player dialog, cancel and launch combination passes. Stack session91635 terminal: minimum gap10682 bytes, zero overlap across82675356 sampled boundaries, bounded 4P/R8 route only. Long R4 session18607 and Normal40 session78108 remain confirmed live; scratch candidate unchanged. Rush remains queued until Normal finishes due to shared offset scratch. pending.json updated with evidence. Current turn progress resolves four gates; production6c8e0f4a unchanged and full goal incomplete.


Whole-scan retained: previous goal turn classified progress (R8/Home/stack gates). R4 session18607 terminal, 72529 states match:105292→105223 display frames, mean1241578.254→1240120.441, profile span2007→2004. Normal40 session78108 terminal: all40 state/render hashes and frame totals match, errors empty. Exit1 reflects existing full-speed misses. Boss Rush session45983 terminal after Normal:3000 video hashes match,2990 updates, zero sprite drops/runtime remaps/wheel fallbacks, reset cleanup true; speed remains short of target. All readers terminal before production build60751. Promoted src/bc_rules.c; production build/finalization terminal and exact SHA ab085ddf411b023e92e7ff67405d3ebdf30a34c8eeb99e9772e0c657f842dfed matches tested candidate. Evidence `.local/bc-index-whole-scan/verified.json`; selected manifest updated. No active jobs. Retained improvement preserves native eligibility and 28-slot order; worst measured BC4P1000-update window2046 display frames=29.325513FPS, Normal4P59.358924 aggregate/worst section57.692308 unchanged. Natural full4P campaign and sustained60FPS/100% goal remain incomplete. Current turn progress: remaining results resolved and verified optimization promoted.


### Projectile occupied-path layout candidate

Previous goal turn classified progress: whole native index scan ab085ddf promoted after all gates and exact production build. Revalidated selected manifest. Current candidate98bfb11ae11c568fb92c4ab3815774f90140e2820793998065fd6c781e404df6 adds __builtin_expect(state!=0,1) to the existing weapon traversal. This changes compiled branch layout only; every live state read, six-empty-slot skip, task order and update is retained. Investigates the instruction-profile hotspot in bc_player_step_into without removing work or changing native representation. Original weapon fixture passes1101updates/872main launches/198option launches/4088collision scans/1101trail updates (fixture does not cover charged segments). Full archive and before/after native disassembly `.local/bc-weapon-live-layout/candidate` and parent. Long R2 session35523, solo33677, BC40 session52280 launched against immutable scratch candidate. Production ab085ddf unchanged; no speed claim or promotion yet. Current turn progress builds and verifies a distinct candidate; full60FPS/100%speed and natural full4P campaign remain incomplete.


Projectile live-layout continuation: previous goal turn classified progress (candidate plus original weapon fixture and replay launch). BC40 session52280 terminal: no measurement errors/ROM changes; candidate adds36 display frames across40samples. Native player disassembly grows2579→2600 instructions and moves the empty branch farther (0x780→0xa82 displacement); the live path was already fall-through before the hint. Thus the hint is not producing the intended layout benefit, and whole-function allocation/layout changes appear counterproductive. Long R2 session35523 and solo33677 confirmed live; neither restarted or rebuilt. Production ab085ddf unchanged, candidate immutable until readers terminal. pending.json includes matrix deltas. Current turn progress yields evidence against retention; full-speed goal remains incomplete.


Live-layout rejected: previous goal turn classified progress (BC40regression and compiled-layout evidence). Long R2 session35523 and solo33677 terminal with all87845/160172states matching. R2 128312→129413 display frames (+1101), mean1398442.087→1410909.143, worst2046→2054. Solo165899→166049 (+150), mean866692.925→871038.875. Both long routes confirm the BC40regression. All readers terminal before restoring bc_rules.c from before.c with fresh mtime. Scratch rebuild60757 terminal; scratch and production both exact retained ab085ddf411b023e92e7ff67405d3ebdf30a34c8eeb99e9772e0c657f842dfed. Rejection evidence `.local/bc-weapon-live-layout/rejected.json`. No active jobs. Current turn progress decisively rejects and restores; full60FPS/100%speed and natural full4Pcampaign remain incomplete.


### Ordinary projectile retirement-flag motion split

Previous turn classified progress (branch-hint regression rejected, exact retained ab085ddf restored). Candidate d02ba4b9d051c35d6ecf5e8f91d3ba945dcf3c57b2779fd6d80037edcbebff07 checks flags&2 once after animation in bc_shot_step: when set, existing beam_move updates both positions without unused bounds; otherwise exact X-before-Y beam_axis retirement remains. No task/order/state/flags change. Source audit shows ordinary launches clear this bit; benefit on real routes is uncertain, and the new branch may cost more. Host differential passes60000 complete weapon updates,6000charge/launch edges,20000varied-velocity boundary cases with dirty padding/flags/phases/timers. Initial inherited log label said stationary although velocities had been changed; corrected label and reran same tests before R2 launch. Fullsrc/inc/tools/ROM/ELF/flatheaders archive `.local/bc-shot-flag-motion/candidate`; repro differential.py retained. R2 session72866,solo91879,BC40session51105 running against immutable scratch. Production ab085ddf unchanged. Current turn progress creates and checks a distinct motion-cost experiment; no native speed/fidelity claim until replays. Full goal remains incomplete.


Shot flag-motion continuation: previous goal turn classified progress(new candidate,host differential and replay launch). BC40session51105terminal:6extra display frames overall,no measurement errors/ROMchange. Long R2session72866 and solosession91879 confirmed live. Audited native motion probe and found stale raw signed-short arguments despite current pre-scaled velocity ABI. Updated production/scratch qa_bc_motion_bound_native.py to call bc_beam_velocity on inputs and honor --output (default unchanged). Probe33294terminal:1310720native bounds cases pass,every signed source velocity at20fractional/boundary/padded positions;1310720position-only results also match original arithmetic. Native probe3576frames is not gameplay timing. Evidence native-motion.log/native-motion ROM/ELF/source;updatedQA archived. Playable production ab085ddf unchanged; scratch d02ba4b9 immutable. Current turn progress resolves short matrix and repairs/verifies native arithmetic QA. Full goal incomplete.


Shot flag-motion rejected: previous goal turn classified progress (BC40result and native motion QA repair). Long R2session72866 and solo91879 now terminal; all87845/160172states match. R2 128312→128837frames(+525),mean1398442.087→1406440.455,worst2046→2053. Solo165899→166052(+153),mean866692.925→871040.870,worst1450→1483. Both routes regress, consistent with6extra frames in BC40. All readers terminal before source restoration and scratch rebuild70553; exact production/scratch ab085ddf verified. Evidence `.local/bc-shot-flag-motion/rejected.json`. Native motion test ABI conversion/--output fixes retained in tools and scratch, with1310720nativecases passed. No active jobs. Current turn progress resolves rejection/restoration; full-speed/full4Pgoal remains incomplete.


### Native distance operand flexibility

Previous goal turn classified progress (flag-motion regression rejected/restored, QA fix retained). Inspected party collision path and prior native proximity/clear trials to avoid repeating rejected approaches. New candidate b6fbcd3fbee40eaa540c98b458a493c17d4dbdf58ab6f581b4494cafaf563305 changes only native bc_unsigned_distance second input constraint from d to g, allowing legal word memory/immediate operands instead of forcing another data register. Same SUB.W/BCC/NEG.W and unsigned endpoint semantics, host fallback unchanged. Output read/write constraint and CCR declaration preserved. Native655360distance comparisons pass(all65536 X against10boundary Ys,bothdirections); native probe archive in `.local/bc-distance-operand/native`. Header rebuild produced distinct ROM; fullsrc/inc/tools/ROM/ELF/flatheaders archived. LongR2session18211,solo86212,BC40session90844 launched against immutable scratch;productionab085ddf unchanged. Current turn progress creates and checks a distinct register-pressure candidate; no speed claim, full60FPS/full4Pgoal incomplete.


Distance operand continuation: previous goal turn classified progress(candidate/native655360checks/replay launch). BC40session90844terminal:net1extra display frame,no errors or ROM changes. Saved before/after party_contact_scan assembly and party-subtractions.json: all4distance SUB.W instructions in this function remain register-to-register, so intended operand benefit does not occur at these sites. Long R2session18211 and solo86212 confirmed live with bounded30second waits;no restart/build. Productionab085ddf unchanged,scratchb6fbcd3f immutable. Current turn progress resolves timing matrix and validates compiler output; full goal incomplete.


Distance operand rejected: previous goal turn classified progress(BC40resolved/nativepartyassembly inspected). LongR2session18211 and solo86212 terminal with all87845/160172states matching. R2 128312→128395frames(+83),mean1398442.087→1399918.254,worst2046→2049. Solo165899→165917(+18),mean866692.925→867326.579,worst1450→1453. No retention: both totals and worst windows regress. Restored scratch inc/bc_rules.h after all readers terminal;rebuild52404terminal;bothproduction/scratch exactab085ddf verified. Evidence `.local/bc-distance-operand/rejected.json`. No activejobs. Currentturnprogress resolves experiment and restores;full60FPS/100%speed and naturalfull4Pcampaign still incomplete.


Actor renderer alias audit: previous goal turn classified progress(distance operand rejected/restored). Saved retained R2 bc_actors_draw instruction attribution in `.local/bc-actor-draw-review/hotspots.json` with matching disassembly. Dominant instructions include sprite SAT write, frame-key compare, live/composite gates, repeated small-sprite cache operations. Reviewed earlier cache-refresh outlining rejection; did not repeat it. Tested restrict on bc_actors_draw actor input and private art-cache pointer. Host checks pass1200cacheupdates/4633submissions,256synchronized updates/6725submissions,4608signed-word boundary submissions. Build21988 is byte-identical retainedab085ddf: alias hint gives no native code benefit. Rejected and restored source;rebuild92842terminal exactab085ddf. Evidence `.local/bc-actor-draw-restrict/rejected.json`. No activejobs. Currentturnprogress profiles target and eliminates a no-op candidate without redundant long replays. Full60FPS/100%speed/full4Pcampaign goal remains incomplete.


### Repeated small-sprite cache pair layout

Previous goal turn classified progress(actor alias candidate byte-identical and restored). Profile shows repeated absolute accesses to repeat_small key/attribute in actor/projectile submissions. Candidate79dca11bbc28949d3f0bba8d49bb9309c234917354a8a458d0b83db9da012727 groups the two u16 globals into one {key,attr}record. Replaces all accesses mechanically; same4byte storage,invalidation,one-entry policy,lookup/pinning/miss and emission order. No count/stamp or debugger symbol changes. Distinct ROM built; fullsrc/inc/tools/ROM/ELF/flatheaders and before/afteractor assembly archived `.local/bc-repeat-pair`. LongR2session84543,solo9273,BC40session17099 running; source grouping alone is not performance evidence. Broader rendering hashes still required before any promotion. Productionab085ddf unchanged,scratchimmutable. Currentturnprogress builds a distinct cache-addressing candidate;goal remains incomplete.


Repeat-pair continuation: previous goal turn classified progress(candidate/build/replays). BC40session17099terminal:19extra display frames,no measurement errors/ROMchange. Assembly confirms new paired longword cache store versus2word stores, but accesses remain absolute and packing/register allocation add work. Added actual-before/after extracted lookup_repeat C differential:393216cases(all65536keys,matching/nonmatching prior key,zero/one/65535 lookup results) preserve returnattribute,lookupcallcount and both cachefields. Evidence check_cache.py/cache.log. LongR2session84543 and solo9273 confirmed live through30second bounded waits; no restart or rebuild. Productionab085ddf unchanged,scratch79dca11b immutable. Currentturnprogress resolves short timings and cache-transition proof; fullgoal incomplete.


Repeat-pair rejected: previous goal turn classified progress(shortmatrixregression plus393216cachetransitionchecks). LongR2session84543 and solo9273 terminal,all87845/160172states match. R2 128312→128452frames(+140),mean1398442.087→1399270.376,worst2046unchanged. Solo165899→165940(+41),mean866692.925→867425.811,worst1450→1457. Candidate regressesbothroutes/BC40;rejected. Allreadersterminal before restoringsprites.c and scratchbuild76177;exactproduction/scratchab085ddf verified. Evidence `.local/bc-repeat-pair/rejected.json`. Noactivejobs. Currentturnprogress closesexperiment/restores;full60FPS/100%speed/full4Pcampaign goal remains incomplete.


### Normal body-contact byte distance

Previous goal turn classified progress(repeat-pair rejected/restored). Revisited Normal4Pslowsection:enemy update remains hotspot; source absdiff is used only twice in body contacts,both withu8arcade coordinates. Candidate5ccbd7131839a1f70f9ece4958522e79ed89ddf3b69f1103c1414638a0fe38ec specializes private absdiff parameters to u8 and nativeSUB.B/BCC/NEG.B with zero-extendedu16output. Preserves unsigned0..255distance and prior coordinate wrapping; no changes to eligibility,order,damage or spawning. Native all65536coordinatepairs pass independent reference. Full archive `.local/normal-body-byte-distance/candidate`;probe.py/native includes reproducibleROM/ELF/source. Normal40state/render matrixsession41280running. These fixtures use protectedplayers; vulnerable route and remainingallmodegates required before retention, even if compiler layout changes protectedtiming. Serialize other Normal/Rush tooling after matrixterminal(sharedoffsetscratch). Productionab085ddf unchanged. Currentturnprogress implements/verifiesdistinctNormalcandidate;full60FPS/full4Pgoal incomplete.


Normal byte-distance continuation: previous goal turn classified progress(candidate/nativeall65536pairs/matrixlaunch). Normal40session41280terminal:all40state/renderhashesmatch,errorsnone,net6displayframes saved. Four-player samples save5 total:section3 1040→1038,section5 1014→1013,section7 1017→1015;othersunchanged. Worstsectioneffective57.803468FPS,notlocked60. These protectedfixtures do not establish vulnerable contact behavior. Started productionab085ddf vulnerable4Psection3/3000updates/rendertrace baseline session29658;run candidate equivalent only after it finishes(sharedoffsetscratch). BC40session28200also running against candidate5ccbd713;noROM/sourcechanges. Currentturnprogress resolves protectedmatrix and launches broader comparisons. Productionunchanged;candidate notpromoted;fullgoal incomplete.


Normal byte-distance continuation: previous goal turn classified progress(Normal40improves,baseline vulnerable run launched). BC40session28200terminal all40timings unchanged,noerrors/ROMchange. Vulnerable baseline29658 and candidate30732terminal:3000updates4Psection3with ordinarydamage/protection timers,allstate/renderhashes match;3058→3052displayframes(6saved),nodrops/remaps. These remain assistedlives/loadout bounded tests. LongR2session1391 and solo27277 launched;BossRush1130 after vulnerableterminal;Home1229942/stack5878also running. pending.json records allhandles/evidence. Scratch5ccbd713immutable,productionab085ddf unchanged. Currentturnprogress verifies vulnerablecontacts and launches remaininggates;full60FPS/100%speed/full4Pgoal incomplete.


Normal byte-distance gate continuation: previous goal turn classified progress(vulnerable state/render comparison improves,BC40unchanged,remaininggates launched). Rush1130terminal:3000videohashesmatch,2990updates,zero drops/remaps/wheelfallbacks,resetcleanuptrue. Home1229942terminal all12dialog/cancel/launchcasespass. Stack5878terminal minimumgap10682bytes/nooverlap across82675356boundaries,bounded4P/R8only. R2session1391 and solo27277 confirmedlive through30second boundedpolls;no restart/build. pending.json updated. Candidate5ccbd713 remainsimmutable and unpromoted;productionab085ddf unchanged. Currentturnprogress resolves3gates;full60FPS/100%speed/full4Pgoal incomplete.


Normal byte-distance retained: previous goal turn classified progress(Rush/Home/stackresolved). LongR2session1391 and solo27277 terminal:all87845/160172statesmatch and exactprior timings128312/165899frames,mean1398442.087/866692.925. BC40unchanged;Rush3000videohashes/2990updatesunchanged;Home12pass;stack10682/nooverlap. Allreadersterminal before productionbuild41998. Promotedonlysrc/enemies.c;productionfinalizedROM exacttested5ccbd7131839a1f70f9ece4958522e79ed89ddf3b69f1103c1414638a0fe38ec. Nativeall65536bytepairs pass;Normal40allstate/renderhashesmatch/net6framessaved;4P10000updates/10103frames=59.3883005FPS,worstsection3 1038frames=57.8034682FPS. Vulnerable4P3000updates/renderexact,3058→3052frames. Evidence `.local/normal-body-byte-distance/verified.json`;selectedmanifestupdated. Noactivejobs. Currentturnprogress retainsverifiedNormalimprovement. BCworst29.325513FPSunchanged;full60FPS/100%speed and naturalfull4Pcampaignremainincomplete.


### Normal collision frame parity

Previous goal turn classified progress(byte-distance improvement promotedexact5ccbd713). Fresh measurement-only4Psection3profile23625terminal reproduces1038frames and all1001state/renderhashes. Evidence `.local/normal4p-byte-distance-profile`:enemy update13.07%,shotdraw8.69%,weaponfire6.12%ofmeasuredcycles(includes32.76%VBlankwait),enemy-hotspots.json identifies peractorabsoluteBTSTframe. Candidatef7513bd214bda94499c544c023906d1f07c97c247ab8f4966a1b8ce019d20987 computes odd frame once after collect_shots and passes it into inline update/collide. game_update incrementsframe beforeflow_update;framefixedwithinpass. Combined exception remains readpercollision since death canchangeit. Every actorupdate/order/eligibility remains;onlyparityreuse. Sourcecomment corrected before finalbuild62764/archive. Normal40state/rendermatrix78561running;vulnerable/Rushandremaininggates requiredifimproves. Fullarchive `.local/normal-collision-parity/candidate`. Production5ccbd713 unchanged. Currentturnprogress refreshesprofileandbuildsnexttargetedcandidate;fullgoal incomplete.


Normal parity continuation: previous goal turn classified progress(freshprofile/candidate). Normal40session78561confirmedlive through30secondboundedwait;completedrowsstate/renderhashesmatch. Archived native update_all before/afterassembly and frame-accesses.json:some peractorBTSTframe reads disappear,but compiler introduces frame-word stack stores for retained parity;netgainunproven. BC40session86440launched independently againstsame immutablecandidate. No rebuild/restart. Production5ccbd713 unchanged. Currentturnprogress verifiescodegeneration and starts cross-mode regression;fullgoal incomplete.


Normal parity comparison: previous goal turn classified progress(codegenerationaudit/BC40launch). Normal40session78561terminal allstate/renderhashesmatch,errorsnone;net1displayframe saved:4Psection7/8eachsave1,2Psection9costs1;worst4Psection3unchanged1038. BC40session86440terminal alltimingsunchanged/noerrors. Vulnerable4Psection3session76175terminal3000updates:allstate/renderhashesmatch,3052→3049displayframes(3saved). Smallmeasuredgain merits remaininggates despite documented2Pcost. LongR2session18714,solo66729,Rush91461launched aftervulnerableterminal. Candidatef7513bd2immutable,production5ccbd713unchanged. Currentturnprogress resolvescomparisons and advancescandidate;fullgoal incomplete.


Normal parity gate continuation: previous goal turn classified progress(smallNormalgains/vulnerablematches/remaininglaunch). Rush91461terminal2990updates/3000frames,zero drops/remaps/fallback/resetcleanuptrue,but video hashes differ at onlyindex102. Reproduced with serial110frame baseline45875/candidate71117 captures (bothterminal):all110hashes reproduce prior respective runs;frames101/103match;frame102 differs exactly4pixels atx9/74/116/244,y24,previous nonblack becomesblack. Captures and pixel-differences.json archived. Scheduler entries/flush/input observations atframes3033–3035 are identical,including scanlines/DMA sizes. Cause not established;do not claim renderingequivalence or promote yet. Home1295647 and stack37333terminal:all12pass,stack10,682gap/nooverlap. LongR218714 and solo66729terminal:all87845/160172states match,exactprior128312/165899frames and1398442.087/866692.925means. Alljobsnowterminal,pending.jsonstatus marks renderinginvestigation. Production5ccbd713 unchanged;candidatef7513bd2 retainedonlyinscratch. Currentturnprogress isolates/reproduces mismatch and resolvesothergates;fullgoal incomplete.


Parity raster investigation/restoration: previous goal turn classified progress(reproduced4pixelmismatch and resolvedlonggates). Serial memorycapture62266/50460terminal:VRAM65536bytes,CRAM128,VSRAM128,andSAT640allidentical atframes101/102/103 despite4differingstar pixels ony24frame102. memory-comparison.json andcaptures retained. HUD general H-int path computes(win_mask>>row)&1 via variable32bitshift before VDPwindowwrite; source row-boundary behavior supports raster-latency suspicion,but no instruction-timedVDPwriteproof yet. Do notclaim establishedcause or render equivalence. Smallparitygainnotretained givenvisiblemismatch;restored enemies.c afteralljobs terminal,rebuild69997 exactproduction/scratch5ccbd713. Evidence rejected.json. Next useful target is removing expensive per-row HUD mask shifts while preserving VBlank mask publication and window boundaries, with native/display verification. Currentturnprogress narrowsmismatch to timing/state distinction and restoresverifiedbuild. Noactivejobs;fullgoal incomplete.


### HUD native window-row bit test

Previous goal turn classified progress(parityrastermemory investigation and exactrestoration). Candidate444d8c8def7dbf85f0c19b569a1c59e366f46e19aea3e40cd3d3eae82c9d593b addswindow_row_value:BTST(mask,row)/SNE/ANDI#128 replaces variable32bitshift/move/ANDI#1/LSL#7 in generalhud_hint. Rowcalculation/clamp,split-simplepath,VBlankpublication,VDPwindowregistervalues unchanged. NoadditionalRAM. Native2097152mask/rowcases pass(all32rows/all6553616bitpatternsineachhalf;notall2^32masks). Disassemblyconfirms intendedsequence. Fullarchive `.local/hud-window-bit-test/candidate`,nativeprobe, before/afterassembly. BossRushcapture53762terminalfirst110videohashesexactretained;frame102nodifferentpixels;VRAM/CRAM/VSRAM/SATat101/102/103allmatch. Thisdoesnotproveentiregame/rendering. Normal40session13801running againstimmutablescratch;production5ccbd713unchanged. Currentturnprogress implements/verifiesmoretargetedinterruptoptimization;full60FPS/100%speed/full4Pgoal incomplete.


HUD bit-test continuation: previous goal turn classified progress(native2097152checks/first110Rushrenderproof/build). Normal40session13801confirmedlive through30secondboundedwait;completedrowsstate/renderhashesmatch. StartedBC40session27570 and longR2session64363/solo87350 againstsameimmutable444d8c8d. No source/ROMchanges orrestarts;production5ccbd713 unchanged. FullRush/vulnerable/modeentry/stackgates stillrequired beforepromotion;Normal/Rushfixtures mustremainserialized. pending.json recordshandles. Currentturnprogress advancescrossmode/fullroutevalidation;full60FPS/full4Pgoal incomplete.


HUD bit-test full results: previous goal turn classified progress(broaderreplayslaunched). Normal13801/BC4027570terminal:Normalall40state/renderhashesmatch,2frames savedonly4Psection7;BC40net1savedwithmixedindividualdeltas,noerrors. FullRush32431terminal:2989vs2990updates in3000frames;baseline2updatevideo-frame3120 disappears,candidateallnonzero intervals1update. Videohashes divergefrom187 with cadence shift,so notalignedrenderproof;no drops/remaps/fallback,resetcleanuptrue. Vulnerable1367terminal3000states/renderhashesmatch,3052framesunchanged. Home1224724/stack30194terminalpass. LongR264363/solo87350terminalall87845/160172statesmatch;R2 128312→128342(+30),mean1398442.087→1398443.865;solo165899→165892(7saved),mean866692.925→866690.027. Alljobs terminal. Mixedtiming andunresolvedupdate-alignedRushcomparison mean candidate444d8c8dnotpromoted. pending.jsoncontainsresults;production5ccbd713unchanged. Currentturnprogress resolvesgates and exposescadencecomparisonlimitation;fullgoal incomplete.


### Update-aligned Boss Rush comparison and HUD candidate decision

Previous goal turn: no progress toward implementation (reported existing Normal 4P FPS only). Revalidated retained production SHA 5ccbd713 and candidate 444d8c8d. Added `--mode rush` to tools/qa_normal_fixed_updates.py: enter the real Home modal, apply controls/protection at input-update boundaries, select owned AUTO through C, and measure fixed completed updates. No Normal warp, RNG reset, life refill, or weapon injection in Rush. Hash scope includes existing players/enemies/RNG/selected level fields plus Rush state/timer/counters and boss HUD; private boss internals remain outside the state hash. Render hashes cover ordered SAT/patterns, not background/HUD raster timing. This is bounded assisted evidence, not full-game fidelity or natural completion.

Terminal runs 63542/77513: retained/candidate each complete 3000 updates; all 3001 state and sprite hashes match across boss indices 0–2. Display frames 3011 -> 3010. Evidence `.local/hud-window-bit-test/aligned-comparison.json`. Normal regression run31560: 4P section3/1000 updates exactly preserves all state/render hashes and1038 frames. Metadata now reports section/AUTO injection level as null for Rush. HUD candidate rejected because mixed gains do not outweigh long BC R2 regression128312->128342; rejection recorded in rejected.json. All readers terminal before scratch HUD restored. Restore build66082 terminal; production and scratch ROM SHA exactly5ccbd7131839a1f70f9ece4958522e79ed89ddf3b69f1103c1414638a0fe38ec. No active jobs.

Current turn: progress (new update-aligned comparison resolves cadence ambiguity; regression check passes; candidate decision and exact restoration completed). Full 60FPS/100% speed goal remains incomplete. Retained Normal4P ten-section average59.3883FPS, slowest tested1000-update section57.8035FPS; retained BC4P worst measured1000-update window29.3255FPS. Next optimization must improve native runtime without changing updates, waves, contacts, or rendering; this harness is now available to check Rush despite timing shifts.


### Native shot-index append expansion candidate

Previous goal turn classified progress: update-aligned Rush comparison, Normal harness regression, HUD candidate rejection, and exact restoration completed. Current authoritative retained profile shows index append/scan consume about70.6million attributed ticks in the1000-scene R2 window. New isolated ROM9361be77ea13797ae8a0ff603ef5ce642859326dfd7af164cd46929723760247 expands the existing native append instructions inside each of28 ascending scan slots, eliminating nested JSR/RTS. Every state/flag/coordinate test, index byte store, bounds update and slot order is retained; a0/a2 preservation and scratch registers unchanged. Source ABI assertions retained. Larger code trades ROM space for per-live-shot call overhead; no gameplay/render reduction.

Build19400 terminal; fullcandidate archive and disassembly at `.local/bc-index-inline-native`. Native probe99957 terminal passes4096completeindices including dirty position padding, fractions, state/flags, radii, sentinel/weapon preservation. BC40session16634 terminal: no measurement errors/ROM changes, net2displayframes saved across40samples, with mixed individual deltas (bc40-comparison.json). This is not full-speed proof. Long R2session75062 and solosession64541 verified live by handle polling; no rebuild while readers run. pending.json recordshandles. Production5ccbd713 remains unchanged/unpromoted. Currentturnprogress creates and verifies a distinct native candidate and starts full-route gates. Full60FPS/100%speed and natural4Pfullclear remain incomplete.


### Native index expansion long replay results

Previous goal turn classified progress (candidate9361be77, native4096case proof, BC40 net2frames saved, long replays started). Current turn re-polled original handles; R275062 and solo64541 now terminal success. Compared every stored canonical state hash directly against retained5ccbd713: all87845multiplayer and160172solo states match. R2frames128312->128047 (265saved), profiled mean1398442.087->1393693.826ticks, worst inclusive1000-update window2046->2043frames. Solo165899->165817 (82saved), mean866692.925->864624.208ticks, worst1450->1439frames. These are canonical scene comparisons, not full-RAM/video proof or a natural4Pfullclear.

Home12session89178 and stack62463 terminalpass. Normal40session97450 verifiedlive, completed rows so far state/render/timing unchanged. R8ordinary75573 and charged16038 started against immutable candidate; stilllive on polling. pending.json records results/handles. Boss Rush aligned state/render and legacy video/exit gates remain to run serially after Normal (shared offsets). Production5ccbd713 unchanged; no promotion yet. Currentturnprogress resolves long-route improvement and advances cross-mode gates. Full60FPS/100%speed objective incomplete; no completion claim.


### Retained native shot-index expansion

Previous goal turn classified progress: long R2/solo replay gains and canonical-state equivalence established; cross-mode gates started. Currentturn all original handles terminal: Normal97450 all40 state/render hashes and framecounts unchanged, noerrors; R8ordinary75573 and charge16038 both replayverified/all1000statehashesmatch retained BC baseline,1267->1266 and1233->1232frames, mean848074.451/762617.814ticks. Aligned Rush3949 all3001state/renderhashes and3011displayframes match retained. Legacy Rush37641 all3000videohashes match,2990updates,zero sprite drops/remaps/wheel fallback,resetcleanuptrue. Home12 and stack gates alreadypass;stack minimumgap10682/nooverlap.

Promoted only src/bc_rules.c after all readers terminal. Productionbuild63917 terminal; production/scratch/testedROMexact SHA9361be77ea13797ae8a0ff603ef5ce642859326dfd7af164cd46929723760247. Evidence `.local/bc-index-inline-native/verified.json`; selected-candidate.json updated. Retained gains: long4P87845states128047frames(265saved), solo160172states165817frames(82saved), BC40net2saved. Worst measured4P inclusive1000-update window2043frames(~29.37FPS), improvedfrom2046 but farbelow60. Normal4P unchanged59.3883FPS ten-sectionaverage/worst testedsection57.8035FPS. Noactivejobs. Currentturnprogress finishes gates and retains measured native improvement. Full60FPS/100%speed/full4Pnaturalclear goal still incomplete; these scoped tests do not establish whole-game fidelity or speed.


### Short native shot-index slot gates

Previous goal turn classified progress: retained9361be77 after completing native, BC, Normal, Rush, modal and stack gates. Revalidated production/scratch exact9361be77 before work. Isolated candidate53f388998d6015df3bbda67c068e58f682254ed038bf5da55933078fe7bfe806 changes only the28 unrolled scan state-gate branches from word displacement to short displacement. Assembler accepts every displacement; disassembly confirms all28word gates removed. No state tests/order/stores or register ABI change. Candidatebuild86026 terminal; fullarchive/scan.asm under `.local/bc-index-short-gates`. Nativeprobe51644 terminal passes4096completeindices with dirty position padding, fractional bytes, varied flags/states/radii, unchanged weapon bytes and index sentinels. Probe7473frames is not gameplay performance.

Long4P R2session50508, solo45765, BC40session22946 launched against immutable candidate; pending.json recordshandles. Production9361be77 remains retained. No promotion or speed claim yet. Currentturnprogress implements/verifies a distinct native encoding improvement and starts runtime gates. Full60FPS/100%speed and natural4Pclear remain incomplete.


### Short-gate results and register-held index bounds

Previous goal turn classified progress(short-gate candidate53f38899/native4096tests/runtimechecks started). Original handles50508/45765/22946 allterminal. Versus retained9361be77, short-gate R2 all87845statesmatch128047->127977frames(70saved), mean1393053.109ticks; solo all160172statesmatch165817->165811(6saved), mean864335.15. BC40 noerrors/ROMchanges, net3frames savedonlyR5/4P. Shortgate candidate remains archived/unpromoted pending broadergates; no completion claim.

Prepared a distinct register-bound scan outside the live scratch build while readers ran. Bounds min/maxX/Y and halfX/Y held in d2-d7 throughout the ordered scan, then stored once before return; MOVEM saves/restores d2-d7 (24stackbytes), existing a0/a2preservation and a1/d0/d1scratch remain. No callbacks/consumers read partial bounds during scan; state/flag/coordinate filters and slots remain unchanged. Includes shorter slot gates. Nativeprobe36567 terminal passes4096completeindices/dirtypadding/fractions/stateflags/radii/sentinels/unchangedweaponbytes. Source/independentprobe under `.local/bc-index-register-bounds`.

Only after all old readers terminal, installed proposed source in scratch and built86875 terminal. Candidate55c98bbc17146088e8c6afef2004219f9d0078b64fe2e95c3df1ebbf3abd1300 archived fullsrc/inc/tools/ROM/symbols. LongR2session46331, solo31137, BC40session74018 launched; pending.json tracks handles. Production9361be77 unchanged. Currentturnprogress resolves short-gate gains and builds/verifies a larger native optimization. Full60FPS/100%speed/full4Pnaturalclear objective incomplete.


### Register bounds runtime gates and register-count follow-up

Previous goal turn classified progress(shortgate gains resolved/registerbounds candidate built/nativeequivalence/runtimegates launched). Currentturn revalidated live longR246331 and solo31137 by originalhandles. BC40session74018 terminal: noerrors/ROMchanges, but candidate55c98bbc adds26displayframes across40samples versus retained9361be77 (mixed deltas, largest+10); notpromoted. Started Normal40session32033 againstimmutable55c98bbc; completedrows state/render/timing unchanged,stilllive. Home12session10514 and stack93756 terminalpass; pending.json stores stack/resultscope and activehandles.

Prepared register-count follow-up only in `.local/bc-index-register-count/proposed.c`, outside live build. Keeps ordered accepted-shot count in d1, uses d0 for eligibility and immediate slot stores, increments count once peracceptedshot, publishes count/bounds atreturn. Removes peracceptedshot count load/memoryincrement. Existing d2-d7save/restore retained. Nativeprobe17669 terminalpasses4096completeindices/sentinels/weaponpreservation with dirtypadding/fractions/flags/states/radii; 7459probeframes isnotgameplay. No fullcandidateROM built yet; mustwait for all currentscratchreaders tofinish before rebuilding. Production9361be77 unchanged. Currentturnprogress resolves BC40regression and verifies a follow-up source candidate; full60FPS/100%speed/full4Pnaturalclear goal remains incomplete.

Same-turn final polling resolved R246331 and solo31137 as terminal (supersedes live wording above). Direct canonical hashes match all87845/160172states. Results: {"natural4p-r2": {"states_match": true, "before_frames": 128047, "after_frames": 127771, "mean_scene_ticks": 1388691.045}, "solo": {"states_match": true, "before_frames": 165817, "after_frames": 165713, "mean_scene_ticks": 861409.787}}. Only Normal32033 remains pending; no rebuild performed.


### Register-held index count gameplay candidate

Previous goal turn classified progress(registerbounds longroute results resolved, BC40regression identified, registercount nativeprobe passed). Re-polled Normal32033 terminal: registerbounds55c98bbc all40 Normalstate/renderhashes andframecounts unchanged/noerrors. All registerbounds readers nowterminal before any rebuild; sourcecandidate remainsunpromoted with mixed BCtiming.

Installed the already native-verified registercount proposal into scratch only. Build9718 terminal; candidate731838196d8dcb9f5cb15f08d113841ca38756a500874e7a4638722ce1fc7915 archived fullsrc/inc/tools/ROM/symbols in `.local/bc-index-register-count/candidate`. Keeps count and sixbounds in native registers while preserving28slotorder/exactfiltering, then publishes final count/bounds. Native4096equivalence proof previouslyterminal17669. New longR2session75338, solo91899, BC40session54114 started against immutable73183819; pending.json recordshandles. Production9361be77 remainsunchanged. Currentturnprogress completes previousNormalgate and builds/launchesruntimevalidation of follow-up. Full60FPS/100%speed/full4Pnaturalclear goal remainsincomplete.

Registercount BC40session54114 nowterminal: noerrors/ROMchanges; deltas againstretained9361be77 [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, -1, 8, 0, 0, 0, 0, 0, 0, 2, 10, 0, 0, 0, 1, 0, 0, 0, 3, 0, 0, 0, 1, 0, 1, 1, 2]; net 28 addeddisplayframes. Notpromoted; longR275338/solo91899 stillpending.


### Sparse index regression isolated; adaptive native scan candidate

Previous goal turn classified progress(registercount73183819 built/launched/BC40regression measured). Re-polled longR275338/solo91899 toterminal. Direct canonical hashes match all87845/160172states; R2frames128047->127478(569saved), mean1385166.671; solo165817->165634(183saved), mean859632.032. Candidateunpromoted because BC40 adds28frames. Independent Round6/4P600scene profiles32948/76303 terminal: matchingstatehashes840->850frames; mean872671.695->875161.443. Indexscan alone adds1515080attributedticks; other gameplayfunctions unchanged. Mean0.40583liveweaponrecords/player,59.4167%player sampleszero. Evidence `.local/bc-index-register-count/r6-comparison.json` supports sparse-scan fixed-overhead diagnosis (workloadrecords are not identical to indexed count).

Prepared adaptive scan outside livebuild: if previous index count<3, branch to equivalent short-gate sparse implementation; otherwise use registercount/registerbounds scan. Both implementations visitall28slots inascendingorder and recompute completeindex; cachedcountselects implementation only,nevereligibility/workload. Saves/restoresd2-d7ondensepath. Nativeprobe initiallyrequired unavailableumodsi3forQAcountselection; replacedtestselectionwithboard&31, no cartridgeworkaround. Probe57251 terminalpasses4096completeindices with previouscount0..31(includingbothpaths),dirtypadding/fractions/stateflags/radii/unchangedweaponbytes/sentinels. No claimofexhaustivecrossproductcoverage.

After all oldreaders terminal, scratchbuild94527 terminalcandidate726aa4d5168ce5708e35548ef2e1e7de8c6da64c1400224ed45017050e76a350. Fullarchive/probe/source under `.local/bc-index-adaptive`. LongR2session6991, solo78395, BC40session89546 started; pending.json trackshandles. Production9361be77unchanged. Currentturnprogress resolveslonggains, isolatesregressioncause, andbuildsverifiedadaptivecandidate. Full60FPS/100%speed/full4Pnaturalclear goal remains incomplete.


### Adaptive scan regression checks; count-only native alternative

Previous goal turn classified progress(registercountlonggains resolved/sparsecauseisolated/adaptivecandidatebuilt). Original adaptiveBC40handle89546 terminal: noerrors/ROMchanges, net16addedframes versus retained9361be77 (improvedfromregistercount+28, stillregression). LongR26991 and solo78395 verifiedlive. Started Normal40session62447 againstimmutable726aa4d; completedrows matching,stilllive. Home12session82086 and stack99846 terminalpass. R6adaptiveprofile59292 terminal all600statehashes match retained,840->848frames, mean872671.695->874294.587; combined indexfunctions16620786 vs15654968attributedticks. Hence sparsepathdispatch stillhasmeasurablepenalty; no promotion.

Prepared `.local/bc-index-count-only/proposed.c` outside livebuild: startfromshortgatevariant, retainboundsinmemory butholdonlycountind1; eligibilityusesd0,immediateslotstore,acceptedcountincrements once afterradiuschecks,finalcountpublishedatreturn. Usesonlyexistinga1/d0/d1scratch,noadditionalregistersave/restore/noadaptivebranch. Nativeprobe34039 terminalpasses4096completeindices/dirtypadding/fractions/stateflags/radii/unchangedweaponbytes/sentinels. No fullgameROMforcount-onlyyet; waitforallcurrentreaderstoendbeforebuilding. Production9361be77unchanged. pending.jsonfiles tracksource/testscope/livehandles. Currentturnprogress measuresadaptivepenaltyandverifiesdistinctlower-overheadcandidate. Full60FPS/100%speed/full4Pnaturalclear remains incomplete.


### Count-only scan gameplay build

Previous goal turn classified progress(adaptivepenaltymeasured/count-onlynativecandidateverified). Re-polled original adaptive6991/78395/62447; allterminal. Directcanonicalstatehashes match87845/160172states: adaptiveR2128047->127789frames,mean1388920.022; solo165817->165636,mean859885.929. Normal40allstate/renderhashesandframecountsunchanged/noerrors. Adaptive remainsunpromotedwithBC40+16frames; results recordedpending.json.

After allreaders terminal, installed count-only proposal in scratch; build87430 terminal. Candidate79bd2ae31eccc4a532e82bc12b0b5bc315caabb9d5c982dfc9a8ac62a616936e archived fullsrc/inc/tools/ROM/symbols under `.local/bc-index-count-only/candidate`. Retainsboundsmemory/shortbranches;countinexistingd1scratch,eligibilityd0,immediateslotwrite,finalcountpublication. No additionalregistersaves/adaptivedispatch. Native4096proofpreviouslypassed34039. LongR2session9392, solo9208, BC40session48998 launchedagainstimmutablecandidate; pending.json trackshandles. Production9361be77 unchanged. Currentturnprogress resolvesadaptivegates/builds/startsmeasurementoflower-overheadcandidate. Full60FPS/100%speed/full4Pnaturalclear goal remainsincomplete.

Same-turn count-only BC40session48998 nowterminal: noerrors/ROMchanges; deltas [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 2, 0, 0, 0, 1, 0, 0, 0, 2]; net 6 addedframes versusretained9361be77. Long9392/9208 pending.

Started serialized Normal40state/render regression gate15830 against count-only79bd2ae3; pending.json records actual returnedhandle15830. No source/ROMchange while readersrun.


### Count-only broader verification

Previous goal turn classified progress(count-only79bd2ae3built/BC40+6framesmeasured/longandNormalgatesstarted). Re-polled existing9392/9208/15830handles, allconfirmedlive; no restart/rebuild. Home12session51500 and stack35217 nowterminalpass;stack resultrecordedpending.json (testedrouteonly). Launched independentR8ordinary7816 and charged60819 state-trace/replayverification againstsameimmutable79bd2ae3; bothconfirmedlive. Normalcompletedrows preserveallstate/renderhashesandframecounts. pending.jsonupdatedwithactualhandles. Production9361be77unchanged. Currentturnprogress extendsmodeentry/stack/R8verification; full60FPS/100%speed/full4Pnaturalclear objective incomplete. BossRushaligned/video/reset checks remain serializedafterNormal.


### Retained count-only native shot-index scan

Same-turn bounded polling resolved long9392/9208, Normal15830, R87816/60819 as terminal. All87845/160172canonicalstatehashes directlymatchretained9361be77. R2frames128047->127741(306saved),mean1389582.901ticks,worstinclusive1000window2043->2041frames. Solo165817->165724(93saved),mean862508.346,worst1439->1415frames. Normal40allstate/renderhashesandtimingunchanged/noerrors. R8ordinary1266->1264,mean847795.410;charge1232->1229,mean761858.762;allstatehashesmatch/replayverified. AlignedRush29365terminalall3001state/renderhashesand3011framesexact. LegacyRush69500terminalall3000videohashesexact,2990updates,zero drops/remaps/fallback/resetcleanuptrue.

Retained count-only79bd2ae3 afterallreaders terminal. Decision explicitlyaccepts BC40net6addedframes (R6/3P+1,R8/4P+2,R9/4P+1,R10/4P+2) in exchangeforlongroute/R8focusedimprovements; notuniformimprovementandnotfullspeed. No gameplaywork omitted. Onlysrc/bc_rules.cpromoted. Productionbuild24165terminal; exacttestedproduction/scratch SHA79bd2ae31eccc4a532e82bc12b0b5bc315caabb9d5c982dfc9a8ac62a616936e verified; evidence `.local/bc-index-count-only/verified.json`, selected-candidateupdated. Alljobs terminal. Earlierregisterbounds/registercount/adaptive alternatives remainunpromotedarchives.

Currentturnprogress completesgatesandretainsmeasurednativeimprovement. Normal4Punchanged59.3883FPSaverageten-sectionfixture/worstsection57.8035FPS. BC4Pworstmeasured1000window60000/2041=29.3974FPS,stillfarbelowtarget. Full60FPS/100%speed/full4Pnaturalclear remainsincomplete; scopedcanonicalstate/renderchecksarenotwhole-gameproof.


### Packed-projectile combined Y equality candidate

Previous goal turn classified progress(retainedcount-only79bd2ae3afterfullgates). Revalidatedretainedsource and reviewed prior delayed-coordinate/mapping/cache/loop experiments; not repeated. New scratchonly841917768fddfe90786d436dcdc583d4e3b7da7c1770ebfc2ca7d3f6271bf576 combines multiplayerpacked-triple Y equality into ((a.y^b.y)|(a.y^c.y)) masked once. Native/alignedmask0xffff00ff preservesoriginalpadding; sourcehost>>8 equality preserved. Every tripleeligibilityfilter,fullwidthXspacing,submissionorder,art,clipping/cache behavior unchanged. Solo coreunchanged. Build42062terminaldistinctROM; fullarchiveandboundedbefore/afterassembly under `.local/bc-triple-y-union`.

Host54574terminal: bothsource/alignedlayouts pass2400pools/37527ordered sprites/600packedstrips,dirtypadding/fallback/end-slots/inputpreservation. Native33125terminal589824artwork/flip/coordinatecasespass; thisnativeprobe doesnotclaimexhaustivetriplegrouping. LongR2session82035, solo43706, BC40session69803 launchedagainstimmutablecandidate; pending.jsontrackshandles. Production79bd2ae3unchanged. Currentturnprogress createsandverifiesdistinctrendererarithmeticcandidate and startsruntimegates. No speedclaimyet; full60FPS/100%speed/full4Pnaturalclear remainsincomplete.


### Combined Y check rejected; projectile switch-lowering candidate

Previous goal turn classified progress(rendererYunion84191776built/nativehostchecks/runtimegateslaunched). OriginalR282035/solo43706/BC4069803terminal: all87845/160172canonicalstatesmatch; R2127741->127793frames(+52), mean1389582.901->1390505.802; solotimingunchanged165724/862508.346. BC40allframecountsunchanged/noerrors. Normal59804terminalall40state/renderhashesandtimingunchanged;Home1278463/stack6197terminalpass. Rejected84191776; rejected.jsonarchivesresults. Allreaders terminal before source replacement.

Fresh retainedrendererPCattribution in `.local/bc-triple-y-union/retained-projectile-hotspots.json` confirms156409540attributedticks; disassemblyshows variableLSL.Lbit-test lowering insideinlinedprojectileartselection. Earlierbc_actor_pose no-bit-tests optimization wasreviewed; thiscandidate applies native-onlyoptimize("no-bit-tests") to projectile_draw_multi only. Sourceart rules,grouping,solo core untouched. Build47671terminal distinctcd2005396dcbcf876a396d2066198e164a4efe3d0eadf1a7c3a9d46e8139739d. after.asm confirmsvariablebit-test shifts removed andmapperremainsinlined(no newbc_projectile_spritecall). Fullarchive under `.local/bc-projectile-no-bit-tests`. Native52648terminal589824rendererart/flip/coordinate/inputcasespass. No speedclaimbasedoncodegenalone.

LongR2session69539, solo86740, BC40session61583 launchedagainstimmutablecandidate; pending.json trackshandles. Production79bd2ae3unchanged. Currentturnprogress resolvesrejecteddeltaandbuilds/verifiesdistinctbackendoptimization. Full60FPS/100%speed/full4Pnaturalclear remainsincomplete.


### Retained multiplayer projectile no-bit-tests lowering

Previous goal turn classified progress(Yunionregressionrejected/no-bit-tests candidatebuilt/nativecheckspassed). Originallong69539/86740/BC4061583handlespolledtoterminal. BC40noerrors/ROMchanges,net14displayframes saved,nosampleregresses. Directcanonicalhashesmatchall87845/160172states: R2127741->127173frames(568saved),mean1389582.901->1384165.783,worstinclusive1000window2041->2039. Soloexact165724frames/862508.346mean/worst1415. Normal2464terminalall40state/renderhashesandtimingexact. Home122174/stack6805terminalpass. R827142/charge81872terminalallstatehashesmatchandreplayverified:1264->1262/mean847171.458;1229->1223/mean759421.705.

AlignedRush82131terminalall3001state/renderhashesand3011framesexact. LegacyRush63165terminalall3000videohashesexact,2990updates,zero drops/remaps/wheelfallback/resetcleanuptrue. Onlysrc/bc_projectile_draw.cpromotedafterallreadersterminal. Productionbuild85580terminalexacttestedSHAcd2005396dcbcf876a396d2066198e164a4efe3d0eadf1a7c3a9d46e8139739d; production/scratchsourceexact. Evidence `.local/bc-projectile-no-bit-tests/verified.json`; selected-candidateupdated. Alljobs terminal. Native-onlyfunction compilerflag changes switchlowering,notart/grouping/simulationrules.

Currentturnprogress completesgatesandretainsverifiedrendererimprovement. Normal4Pstill59.3883FPSfixtureaverage/worsttestedsection57.8035; BC4Pworstmeasured1000window60000/2039(~29.4262FPS),farbelowtarget. These scopedchecksarenotwhole-gameproof. Full60FPS/100%speed/full4Pnaturalclear objective remainsincomplete.


### Native projectile facing-to-flip mask

Previous goal turn classified progress(retainedcd200539rendererbackendimprovementaftergates). Revalidatedproduction/scratchcd200539. Playerupdate disassembly shows5variableLSL.Wby11 sequences from facing-to-sprite-bit conversion (not switch lowering). Scratchcandidate5138f92e4e4e423e5802999e697bec8b6747bcfbbb5bb547bd3aa4f38d79d399 addsprivateprojectile_left_flip: TST.Bfacing/SEQ/EXT.W/ANDI.W#2048. Replaceszero-facing ternaryatbeam/ordinaryshot/optionattributeupdates; existingkind/phase/spriteconditions and0x77ffmask retained. Hostfallbacksamezero/nonzero result. No layout/ruleschange. Nativeall256facingbytecases exactzero/0x800/inputpreservationpass; before/afterplayerassemblyconfirmsfivevariable shiftsremoved.

Build8863terminaldistinctROM/fullarchive `.local/bc-facing-mask/candidate`. Initialqa_bc_weapons invocation lackedrequiredcapture/code anddidnotrun; corrected originaloption-weapons taskcomparison supplied `.local/pce-reference/option-weapons-tasks/code-002160.bin`, completed successfully (weapons-capture.log), scopedoriginalfixture notwholegame. Probe source/ROM/log andassemblyarchived. LongR2session20198, solo53157, BC40session31524 launchedagainstimmutablecandidate; pending.jsontrackshandles. Productioncd200539unchanged. Currentturnprogress implements/verifiesnativeflagconversion andstartsperformancegates. No speedclaimfromassemblyalone; full60FPS/100%speed/full4Pnaturalclear remainsincomplete.


### Retained native facing mask

Previous goal turn classified progress(native5138f92efacingmask built/exhaustive256bytecheck/sourceweaponfixturepass/runtimegatesstarted). Original20198/53157/31524polledtoterminal. BC40allframecountsunchanged/noerrors. All87845/160172canonicalstatehashesmatchretainedcd200539: R2127173->127142frames(31saved),mean1384165.783->1383435.991,worstinclusive1000window2039->2037. Solo165724->165725(+1),mean862508.346->862175.090,worst1415->1413. Decisionacceptsoneframeinfullsolorouteforimproved4P/worstwindows; notuniformspeedgain. Normal88799all40state/renderhashesandframecountsexact. Home1281658/stack33269pass. R810387/charge8471statehashesmatch/replayverified/framecountsunchanged1262/1223;means847171.458/759540.257(chargedmean+118.552ticks).

AlignedRush64606terminalall3001state/renderhashesand3011framesexact. LegacyRush82017terminalall3000videohashesexact,2990updates,zero drops/remaps/wheelfallback/resetcleanuptrue. Afterallreaders terminal promotedonlysrc/bc_rules.c;productionbuild57399terminalmatchesexacttestedSHA5138f92e4e4e423e5802999e697bec8b6747bcfbbb5bb547bd3aa4f38d79d399. Evidence `.local/bc-facing-mask/verified.json`; selected-candidateupdated. Alljobs terminal. Read-onlyreviewofpriorrow-maskexperiments confirmed bookkeepingregressions; none repeated.

Currentturnprogress completesgatesandretainsmeasurednativeflagconversion. Normal4Pstill59.3883FPSaverage/worsttestedsection57.8035. BC4Pworstmeasured1000window60000/2037(~29.4551FPS),farbelow60. Full60FPS/100%speed/full4Pnaturalclear remainsincomplete; scopedtestsarenotwhole-gameproof.


### Direct ordinary-shot retirement result

Previous goal turn classified progress(retainednativefacingmask5138f92eaftergates). Read-onlyretainedplayerPCprofile saved `.local/bc-player-hot-review/{retained.asm,hotspots.json}`; commonpost-updateTST.Bshotstate attributed2303280ticks in R2window, separatefromrequiredpre-updateeligibility. Newcandidate8aa0400ae89304a66d4785e8e2cc5764ec91ab50fbd4aa7bfcf1ca7099e00f6b introducesprivatealways-inlineshot_step_live returning1onlyatretirementbranches. Publicbc_shot_stepremainsvoid/guardsinactiveinputanddelegates; weaponsloopcallsprivatehelperonlyafterlivecheck,usesreturnedretirementforoptioncounterdecrement. Otherweaponfamiliesretainpoststatecheck. Movement/terrain/animation/timer/phase/flags/statechanges/X-before-Yearlyreturn preserved; no updateomission.

Build/hostsession56437terminal:60000fullweaponupdates/events,6000charge/launchcases,20000variedvelocity/dirtypositionpadding/boundary/timer/flagcases matchindependentlycompiledretainedsource. Originalweapon-taskcapture1101updates/872mainlaunches/198optionlaunches/4088collision scans/1101trails passes(nochargedsegmentsinthatfixture). Fullsrc/inc/tools/ROM/ELF/headers, nativeplayerassemblyanddifferential.py archived `.local/bc-shot-retired-result`. LongR2session22660, solo72978, BC40session73349 startedagainstimmutablecandidate; pending.jsontrackshandles. Production5138f92eunchanged. Currentturnprogress implementsandchecksretirement-resultrefactorandstartsCPUmeasurements. No gainclaimyet; full60FPS/100%speed/full4Pnaturalclear remainsincomplete.


### Retained direct shot retirement result

Previous goal turn classified progress(retirementrefactor8aa0400abuilt/86000hostcases+sourcefixturepass/runtimegatesstarted). OriginalR222660/solo72978/BC4073349polledtoterminal. All87845/160172canonicalstatehashesdirectlymatchretained5138f92e: R2127142->126783frames(359saved),mean1379131.285,worstinclusive1000window2037->2036. Solo165725->165648(77saved),mean859984.678,worst1413->1399. BC40noerrors/ROMchanges,net1addedframe(mixedindividual +/-1); acceptedwithlargerlongroute/R8gains,notuniformimprovement. Normal20545all40state/renderhashesandframecountsexact. Home1260614/stack59557pass. R833570/charge71067statehashesmatch/replayverified:1262->1259/mean846952.498;1223->1221/mean759353.833.

AlignedRush19180terminalall3001state/renderhashesand3011framesexact. LegacyRush6932terminalall3000videohashesexact,2990updates,zero drops/remaps/wheelfallback/resetcleanuptrue. Afterallreaders terminal promotedonlysrc/bc_rules.c; productionbuild48065terminalmatchesexacttestedSHA8aa0400ae89304a66d4785e8e2cc5764ec91ab50fbd4aa7bfcf1ca7099e00f6b. Production/scratchsourceexact. Evidence `.local/bc-shot-retired-result/verified.json`; selected-candidateupdated. Alljobs terminal.

Currentturnprogress completesgatesandretainsverifiednativeplayerupdateimprovement. Normal4Punchanged59.3883FPSfixtureaverage/worsttestedsection57.8035FPS; BC4Pworstmeasured1000window60000/2036(~29.4695FPS),stillfarbelow60. Full60FPS/100%speed/full4Pnaturalclear objective remainsincomplete. Scopedcanonicalstate/rendercomparisonsarenotwhole-gameproof.

Previous status-only turn classified no progress; revalidated current retained 8aa0400a and identical scratch source. Current turn starts isolated returning-shot direct-retirement result candidate, preserving public inactive guard, catch counter, aim, animation and motion order. Production unchanged; full goal remains incomplete.

Returning-shot candidate 0fba493a05df0984223051792479235191ae0e502ffac270dd98f580c4a29ec2: private always-inline return_step_live returns retirement at the catch branch; public bc_return_step retains inactive guard. Dispatcher uses direct result for kind2. Host60000 complete weapon updates,6000charge edges,20000ordinary boundaries and20000direct returning steps all match. Build16520terminal. Archived candidate in .local/bc-return-retired-result/candidate. R2 replay54687 and BC40timing13117 launched, candidate held immutable. Currentturn progress adds verified behavior evidence and native runtime experiment; production8aa0400a unchanged. Full60FPS/100%speed goal incomplete.

BC40 session13117terminal(exit1 speed misses, not measurement failure): all40 framecounts exactly retained8aa0400a; measurement_errors false,rom_changed false. R2 session54687 re-polled and confirmedlive; preserve candidate while reader runs. No speed improvement claimed yet.

Previous goal turn classified progress(candidate build/host comparisons/BC40resolved). Current turn re-polled R2 session54687 and confirmedlive. Improved direct-return differential to vary state independently from launch delay and explicitly cover catch boundary deltas0/15/16/65535 with counter0..255; all106000combinedcases pass (session98827terminal). Solo canonical replay81649 launched against same immutable0fba493a. Baselineprofile confirms playerstep largest individual attribution261031848ticks/1000calls, supporting current focus. Production unchanged; full goal incomplete.

R2 session54687terminal: {"states_match": true, "scenes": 87845, "before_frames": 126783, "after_frames": 126788, "before_ticks": 1379131.285, "after_ticks": 1379131.285}. Sourceweaponfixturepass1101updates/872main/198option/4088collision/1101trail. Solo81649confirmedlive; candidate immutable until terminal.

Previous goal turn classified progress(long R2 comparison completed; returning candidate lacks benefit). Currentturn verified solo81649live, process80699CPU98.7%; scratch remains immutable. Independently prepared option-only retirement candidate from retained production in .local/bc-option-retired-result/candidate.c (no returning change). Public inactive guard and phase/tier/trail/timer/X-before-Y paths retained; direct result feeds ownership count. Host126000comparisons pass, including20000direct option states. This is preparation/behavior evidence, not native speed proof; wait for reader terminal before scratch build. Fullgoal incomplete.

Solo81649terminal: {"states_match": true, "before_frames": 165648, "after_frames": 165648, "decision": "rejected: no measured 4P gain"}. Returning candidate rejected. All readers terminal before loading separate option-only candidate into scratch. Production8aa0400a remains unchanged.

Option-only candidate build39912terminal, SHA168fc095b91c928d718d8db5754ced5fec7419c0a79ff71b67ea82062793a708, fullarchive .local/bc-option-retired-result/candidate. Native longR2 and BC40 launched; hold scratch immutable. Currentturnprogress rejects nonbeneficial returning candidate and advances independently behavior-checked option candidate. Full60FPS/100%speed goal incomplete.

Previous goal turn classified progress(returning candidate rejection, option candidate build/behavior checks). Currentturn verified both R2 replay93689 and BC40matrix45479 live; immutable scratch168fc095. Saved generated native player disassembly for inspection. Production8aa0400a unchanged. Full60FPS/100%speed goal remains incomplete.

Option candidate BC40session45479terminal: all40framecounts unchanged, no measurement errors/ROMchange. Original sourceweaponfixturepass. Solo66392/Home1220758/stack98858 launched alongside liveR293689. Native disassembly confirms option retirement jumps directly to ownership logic; baseline-player-hotspots.json shows state/empty branches remain dominant overhead (4.81m/4.42m ticks). Existing six-empty-slot skip must be preserved or independently remeasured; no new loop change made. Currentturnprogress resolves matrix and expands regressions; production unchanged/fullgoal incomplete.

Home20758 and stack98858terminal/pass: all12Normal/BC/Rush1–4P modal/cancel/launch combinations; boundedR8stack3000updates gap10682/nooverlap. R293689 and solo66392re-polledconfirmedlive. Candidate notpromoted; fullperformance/fidelity goal remains incomplete.

Previous goal turn classified progress(BC40/Home/stack/sourcefixture resolved). CurrentturnR293689terminal: all87845canonicalstatesmatch,126783→126771frames(12saved),mean1379131.285→1379019.579; worstinclusive1000window2034. Solo66392stilllive. Normal45152/R8ordinary51297/R8charge68904launched; Rush serialized afterNormal. Candidate168fc095 remains immutable; production8aa0400a unchanged. Currentturnprogress identifies small native improvement and advances regression gates; fullgoal incomplete.

Option runtime sessions66392/51297/68904terminal. {"solo": {"states_match": true, "before_frames": 165648, "after_frames": 165639}, "r8": {"states_match": true, "before_frames": 1259, "after_frames": 1259, "replay_verified": true, "mean_ticks": 846957.041}, "r8-charge": {"states_match": true, "before_frames": 1221, "after_frames": 1222, "replay_verified": true, "mean_ticks": 759330.803}}. Normal45152stillpending beforeRush. Candidate notpromoted; fullgoal incomplete.

Retention assessment pending Normal/Rush gates: option-only change saves12long4Pframes and9solo, improvesworst1000window2036→2034, BC40unchanged; chargedR8costs1frame despite lower mean759353.833→759330.803. All scopedstatesmatch. Normal45152re-polledlive, completedcases state/render/timingexact so far. No source/ROM changes while readerlive. Next run alignedRush thenlegacyRush afterNormalterminal.

Previous goal turn classified progress(longR2/solo/R8 comparisons resolved). Normal45152confirmedlive on this turn, currently4Pcases, all completedstate/render/timingexact. Saved option-candidate profile attribution comparison. No build/sourcechanges while readers run; fullgoal incomplete.

Normal45152terminal(exit1speedmiss): all40state/renderhashes and framecounts exact, errors[]. R2 attribution confirms playerstep261031848→260892408ticks(139440saved), other materialgameplay functionsunchanged. Started alignedRush77454 afterNormalterminal; legacyRushnext. Candidate168fc095immutable; productionunchanged. Currentturnprogress completesNormalgate; full60FPSgoal incomplete.

Option retirement retained: alignedRush77454terminal with3001state/renderhashes/3011framesexact; legacyRush82397terminal all3000videohashesexact/2990updates/0drops/remaps/fallback/resetcleanuptrue. All readers terminal before promoting onlysrc/bc_rules.c. Productionbuild79774terminal; finalizedproduction/scratch/testedROMexact168fc095b91c928d718d8db5754ced5fec7419c0a79ff71b67ea82062793a708. Evidence .local/bc-option-retired-result/verified.json; selectedmanifestupdated. Gains12long4Pframes(126783→126771),9solo(165648→165639), worstinclusive1000window2036→2034(29.498525FPS). BC40unchanged; chargedR8+1frame disclosed. Normal4P unchanged59.3883FPSaverage/worsttestedsection57.8035. Home12pass; boundedstackgap10682/nooverlap. Currentturnprogress completesgatesandretainsverifiednativeimprovement. Noactivejobs. Full60FPS/100%speed/nativefull4Pclear goal remainsincomplete; scopedchecksare notwhole-gameproof.

Previous goal turn classified progress(option-only168fc095retained after all gates). Currentturn revalidated production/scratch source identity; isolated empty-span candidate replaces five-neighbor bitwiseOR with logicalOR. Reads are pure/nonvolatile; all mustbezero to skip, same endguard/sixslotspan/order/liveupdates. Tests assess branch cost against avoided reads; no speedclaim yet. Production unchanged/fullgoal incomplete.

Empty-neighbor short-circuit candidate442bab5f0e36cbf922c09cc57f318c4fc955dc9d15014487b971744eed3d758e built19178terminal; host49183terminal126000comparisons pass. Native player disassembly confirms fiveTST.B/conditional early exits replacing MOVE.B/fourOR.B/onebranch, so all-empty path adds branches while occupied-neighbor paths avoid laterreads. Fullarchive .local/bc-empty-short-circuit/candidate. R2replay1469 andBC40matrix85031 launched, immutablecandidate untilterminal. Production168fc095unchanged. Currentturnprogress tests distinct scan-costtradeoff; full60FPS/100%speed/full4Pclear objective incomplete.

BC40session85031terminal: {"changes": [{"round": 4, "players": 3, "delta": -1}, {"round": 4, "players": 4, "delta": 10}, {"round": 5, "players": 4, "delta": 1}, {"round": 6, "players": 3, "delta": 1}, {"round": 6, "players": 4, "delta": 18}, {"round": 7, "players": 4, "delta": 3}, {"round": 8, "players": 3, "delta": 1}, {"round": 8, "players": 4, "delta": 8}, {"round": 9, "players": 4, "delta": -1}, {"round": 10, "players": 3, "delta": -1}, {"round": 10, "players": 4, "delta": 5}], "total_added_frames": 44, "measurement_errors": false, "rom_changed": false}. R2session1469confirmedlive; noROM/sourcechange untilterminal.

Previous goal turn classified progress(short-circuit candidate behavior/native build/BC40regression). Currentturn replay1469re-polledlive, process6139CPU98.5%, no scratchmutation. Prepared distinct shot-volley allocation cursor from retained168fc095 in .local/bc-shot-allocation-cursor/candidate.c: move slotinitialization outside memberloop, retaining first-free search and descending volleyorder; priorselectedslot is reread occupied on nextiteration. Pure launch setters cannot free earlier records. Host146000cases pass(session58216terminal): existing126000weapon/edge cases plus20000direct volleys with random holes/full/empty pools, alltiers/facing/dirtybytes and option-slot sentinels. Candidate not yet nativebuilt; wait readerterminal. Currentturnprogress produces checked nextcandidate; fullgoal incomplete.

Short-circuit replay1469terminal: {"states_match": true, "before_frames": 126771, "after_frames": 127301, "mean_ticks": 1382170.202, "decision": "rejected"}. Reject afterBC40+44frames and longresult; allreaders terminal before replacing scratch with separate retained-based allocationcursorcandidate. Production168fc095unchanged.

Allocationcursorbuild44983terminal, candidate493753e4c503fc102a2a48f7e1af501b8bcb8d4b96ddd2a7e62d5b69cd765efc archivedfullsrc/inc/tools/ROM/ELF/symbols. R260003/BC4091012launched; immutablecandidate. Currentturnprogress rejects slower empty-scan and advances behavior-checked independent allocation optimization. Production168fc095unchanged; fullgoal incomplete.

Previous goal turn classified progress(rejected empty-scan, built/behavior-tested allocationcursor). R260003confirmedlive; BC4091012terminal: {"changes": [{"round": 5, "players": 4, "delta": -1}, {"round": 6, "players": 3, "delta": -1}, {"round": 8, "players": 3, "delta": -1}, {"round": 8, "players": 4, "delta": 1}], "total_added_frames": -2, "measurement_errors": false, "rom_changed": false}. Originalsourceweaponfixture passes1101updates/872main/198option/4088collisions/1101trails. Production168fc095unchanged, scratch493753e4immutable. Currentturnprogress resolves matrix/sourcebehavior; fullgoal incomplete.

Allocationcursor continuation: original weapon fixture passes, BC40net2frames saved withR8/4P+1mixed. LongR260003re-polledlive; solo72636/Normal65201 launched. R8ordinary11945/charge28761/Home43689/stack77837 started. bc_shot_fire fullyinlined; saved player.asm (standalone disassembly empty), no newnative sourcechange. Candidate493753e4immutable; production168fc095unchanged. Currentturnprogress expands actualgameplay/regression evidence; fullgoal incomplete.

Previous goal turn classified progress(BC40/referenceweapon evidence, broaderreplayslaunched). Currentturn R260003/solo72636/Normal65201confirmedlive. R811945/charge28761/Home43689/stack77837terminal: {"r8": {"states_match": true, "before_frames": 1259, "after_frames": 1259, "mean_ticks": 846929.692, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1222, "after_frames": 1223, "mean_ticks": 759302.166, "replay_verified": true}, "stack": {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2984, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2984, "overlap_samples": 0, "sampled_boundaries": 82262672}, "home12_pass": true}. Scratch493753e4immutable, production168fc095unchanged; fullgoal incomplete.

R260003terminal: all87845statesmatch,126771→126850frames(+79),mean1379019.579→1379061.796,worst1000window2034→2036. Cursorcandidate will notbe retained; shorterBC40net2saved insufficient. Solo72636/Normal65201stillconfirmedlive; no scratchchange. Generatedplayer.asm shows MULU.W#36 inside repeatedvolley path. Prepared distinct pointer-cursor variant from retained168fc095, .local/bc-shot-allocation-pointer/candidate.c, carrying recordpointer/end instead of slotnumber (no change to first-free/order/fullpoolguard). Host146000comparisons pass. Notyetnativebuilt untilallreaders terminal. Currentturnprogress rules out countercursor and checks nextvariant; fullgoal incomplete.

Previous goal turn classified progress(R2countercursorregression and pointervariant146000hostchecks). Solo72636/Normal65201nowterminal: {"solo_states_match": true, "solo_before_frames": 165639, "solo_after_frames": 165615, "normal_errors": [], "normal_hashes_match": true, "normal_saved_frames": 0, "decision": "rejected: 4P long replay regression"}. Allreaders terminal before loading separatepointercandidate into scratch. Production168fc095unchanged; fullgoal incomplete.

Pointer allocation candidate9bffed65d7bace8da761287c3a47fe4ed19f173127ff2c37cbf257053748b54e: build99471terminal, originalweaponfixturepass1101updates/872main/198option/4088collision/1101trail. Fullarchive .local/bc-shot-allocation-pointer/candidate; player.asm saved. BC4032564/R255562/solo80762launched against immutablecandidate. PublicallocationAPI and28slotbound unchanged; first-freerecordcursor retains originalvolleyorder. Production168fc095unchanged. Currentturnprogress closes rejectedcountercandidate and builds/tests distinctnativepointerversion; fullgoal incomplete.

PointerBC4032564terminal: {"changes": [{"round": 5, "players": 4, "delta": -1}, {"round": 8, "players": 3, "delta": -1}, {"round": 8, "players": 4, "delta": 1}], "total_added_frames": -1, "measurement_errors": false, "rom_changed": false}. Nativeplayer.asm confirms allocationloop CMPA/TST.B/LEA36 and no MULU.W#36 remains inplayerfunction. R255562/solo80762pending; no speed claim frominstructioncountalone.

Previous goal turn classified progress(countercandidate rejected, pointerbuild/referencefixture/BC40resolved). Currentturn confirmedR255562/solo80762live (process7605/7606~99%CPU). Read-only retainedactorprofile saved .local/bc-shot-allocation-pointer/baseline-actor-hotspots.json: register save/restore6.46m/4.87m, MOVEPeventclear6.89m combined, supporting costreview. Prior eventalignment and runtimealignmentguard explicitly rejected in docs5763/8419; no repetition/sourcechange. Scratch9bffed65immutable, production168fc095unchanged.

PointerR255562terminal: {"states_match": true, "before_frames": 126771, "after_frames": 126714, "mean_ticks": 1377393.829}. Solo80762pending; noROM/sourcechange. Long4Pdecision depends on realframe evidence, not removedmultiply alone.

Solo80762terminal all160172statesmatch,165639→165581frames(58saved). TogetherwithR2saving57frames supportsremaininggates. Normal88608/R8ordinary38440/R8charge54038 launched; Home/stackalso launched. Keepcandidate9bffed65immutable. Currentturnprogress establishes actualnative longroutegains; production168fc095unchanged/fullgoal incomplete.

Previous goal turn classified progress(pointerlong4P/solo gains verified and remaininggateslaunched). Currentturn Normal88608confirmedlive; R838440/charge54038/Home45634/stack50692terminal: {"r8": {"states_match": true, "before_frames": 1259, "after_frames": 1257, "mean_ticks": 846825.483, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1222, "after_frames": 1222, "mean_ticks": 759227.469, "replay_verified": true}, "home12_pass": true, "stack": {"lowest_sp": 16775328, "lowest_pc": 151318, "lowest_tick": 2080, "minimum_gap": 10708, "gap_sp": 16775328, "gap_end": 16764620, "gap_pc": 151318, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82189290}, "natural4p-r2_worst_1000_frames": 2031, "solo_worst_1000_frames": 1388}. Candidate9bffed65immutable; production168fc095unchanged/fullgoal incomplete.

Pointer profile-review.json: playerstep260892408→259298634ticks(-1593774) inR2window; commonactor/projectilerender/generalactor/actorrenderattributions unchanged. Biggest remaining player18.83%,common11.16%,projectilerender10.97%,generalactor10.23%,actorrender8.47%of measuredcomplete-scene time. Normal88608re-polledlive, completedcasesexact. AwaitNormalterminal then alignedRush/legacyRush; candidateimmutable. Currentturnprogress resolvesR8/Home/stack andquantifiesgain; full60FPSgoal incomplete.

Normal88608terminal all40state/render/timingexact,errors[]. AlignedRush21100terminal all3001state/renderhashes and3011framesexact; no sprite/SATregression. LegacyRush27965launched afteralignedterminal; finalvideocadence/resetgatepending. Production168fc095unchanged, candidate9bffed65immutable.

Pointer allocation retained: legacyRush27965terminal all3000videohashesexact/2990updates/0drops/remaps/fallback/resetcleanuptrue. Allreadersterminal before promotingonlysrc/bc_rules.c. Productionbuild14583terminal, finalizedproduction/scratch/testedROMexact9bffed65d7bace8da761287c3a47fe4ed19f173127ff2c37cbf257053748b54e. Evidence .local/bc-shot-allocation-pointer/verified.json; selectedmanifestupdated. Long4P126771→126714(57saved),solo165639→165581(58saved),all87845/160172statesmatch. Worst4Pinclusive1000window2031(~29.5421FPS),solo1388. BC40net1savedwithR8/4P+1; longR8ordinary1259→1257,charge1222unchanged/replayverified. Normal40exact; Home12pass; boundedstackgap10708/nooverlap. Currentturnprogress completesgatesandretainsmeasurednativeimprovement. Noactivejobs. Full60FPS/100%speed/full4Pnaturalclear goal incomplete; scopedchecksnotwhole-gameproof.

Previous goal turn classified progress(pointerallocation9bffed65retained afterallgates). Revalidated scratch/productionsourceidentity. Newisolatedbeam-retirement candidate preserves publicinactiveguard and exact delay/acceleration/timer/attributes/X-beforeYmotion, returnsretirement directly to dispatcher. No gameplay/task/render removal. Production unchanged/fullgoal incomplete.

Beamretirementcandidate44d8c859c7f498fa9e1bebbbfb66b806197418253ca1ebd898a3a4797c685300: host99935terminal166000comparisonsmatch (60000fullweapon updates,106000direct/edgecases including20000beams), build47313terminal. Fullarchive .local/bc-beam-retired-result/candidate. BC4095544/R270352/R8charge47817launched; candidateimmutable. Production9bffed65unchanged. Currentturnprogress builds/checks distinctnativebeam optimization; no speedclaim untiltests/fullgoal incomplete.

BC4095544/R8charge47817terminal: {"bc40_changes": [{"round": 2, "players": 4, "delta": -1}, {"round": 5, "players": 4, "delta": 1}], "bc40_added_frames": 0, "measurement_errors": false, "rom_changed": false, "charge": {"states_match": true, "before_frames": 1222, "after_frames": 1222, "mean_ticks": 758851.016, "replay_verified": true}}. Originalweaponfixturepass (doesnotcoverchargedsegments); directbeamhost andchargednativecheckscoverbeamchange. R270352stillpending; candidateimmutable/productionunchanged.

Previous goal turn classified progress(beamretirementcandidate build/166000hostchecks/BC40andchargedR8resolved). Currentturn R270352confirmedlive, solo35317launched. Source/profilingreview preserves existingterrain behavior: prior empty-pagecache explicitlyregressed; no newcache/state-layoutchange. Prior beamwordbound/fusedswap attempts also rejected inarchivedruntimeevidence, avoidrepeating. Scratch44d8c859immutable/production9bffed65unchanged; fullgoal incomplete.

BeamretirementR270352terminal: {"states_match": true, "before_frames": 126714, "after_frames": 126711, "mean_ticks": 1377343.415}. Solo35317pending, candidate notpromoted.

Beamcontinuation: R2saves3frames/all87845statesmatch,mean1377393.829→1377343.415. Solo35317stillpending. RemaininggatesNormal29651/R8ordinary72289/Home52276/stack79497launched; RushwillserializeafterNormal. Candidate44d8c859immutable; production9bffed65unchanged. Currentturnprogress completeslong4Pcomparison and advanceschecks; fullgoal incomplete.

Previous goal turn classified progress(beamlong4P3frames saved, remaininggateslaunched). Currentturn solo35317/Normal29651confirmedlive; ordinaryR872289/Home52276/stack79497terminal: {"r8": {"states_match": true, "before_frames": 1257, "after_frames": 1260, "mean_ticks": 846830.579, "replay_verified": true}, "home12_pass": true, "stack": {"lowest_sp": 16775328, "lowest_pc": 151186, "lowest_tick": 2080, "minimum_gap": 10708, "gap_sp": 16775328, "gap_end": 16764620, "gap_pc": 151186, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82187604}, "worst_4p_1000_frames": 2034}. Candidate44d8c859immutable, production9bffed65unchanged; fullgoal incomplete.

BeamSolo35317terminal: {"states_match": true, "before_frames": 165581, "after_frames": 165596}. Beamcandidate notfavored: worst4Pwindow2031→2034 and ordinaryR8+3offset longR2-3; Normal29651stilllive, defer scratchrestore untilterminal. Independently prepared source-only optionownership branch variant from retained9bffed65, replaces dynamicindex with same twofixedcounter branches; testsrunning, no native speedclaim.

BeamNormal29651terminal: {"decision": "rejected: solo+15, ordinaryR8+3 and worst4Pwindow+3 outweigh long4P-3", "normal_hashes_match": true, "normal_saved_frames": 0, "normal_errors": []}. Allreaders terminal before scratchreplaced with independentretained-based option-owner-branch candidate. Host21614terminal166000comparisonsmatch. Production9bffed65unchanged. Currentturnprogress rejects nonbeneficialbeamvariant and advancesnewownershipcodegenexperiment; fullgoal incomplete.

Optionownerbranchbuild89713terminal, candidate57690f187fbf83ab152b4013552d043c90bb64d326683a76eac48a71e0badf4d fullarchive .local/bc-option-owner-branch/candidate. BC4093918/R217715launched; candidateimmutable. Same retired/flags12 eligibility and flags8 sidepriority/counterwrap, explicit fixedcounterbranches replace computedindex. Production9bffed65unchanged/fullgoal incomplete.

Previous goal turn classified progress(beamrejected and optionownerbranchbuilt/hosttested). BC4093918terminal: {"changes": [], "total_added_frames": 0, "measurement_errors": false, "rom_changed": false}. R217715confirmedlive. Originalweaponfixturepass1101updates/872main/198option/4088collisions/1101trail. Production9bffed65unchanged; candidate57690f18immutable; fullgoal incomplete.

Native ownerbranch player.asm confirms BTST#3/branch and fixedSUBQ.Bcounteraddresses1093/1094 replacing shift/mask/invert/indexarithmetic. BC40timingunchanged is notspeedproof. Solo31406launched alongside R217715; immutable57690f18. Currentturnprogress verifiesreferencefixture/codegeneration and launcheslongregression. Production9bffed65unchanged/fullgoal incomplete.

Previous goal turn classified progress(ownerbranch referencefixture/BC40/nativecodegenconfirmed, sololaunched). Currentturn longR217715/solo31406confirmedlive (~100%CPU, process33551/33795); no rebuild/restart. Started Normal andR8ordinary/charge regressiongates against sameimmutable57690f18. Production9bffed65unchanged; fullgoal incomplete.

OwnerbranchR217715terminal all87845statesmatch,126714→126666frames(48saved),mean1377393.829→1377366.382,worst1000window2031unchanged. R88714/charge24581terminal: {"r8": {"states_match": true, "before_frames": 1257, "after_frames": 1257, "mean_ticks": 846825.483, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1222, "after_frames": 1222, "mean_ticks": 759227.469, "replay_verified": true}}. Normal58577/solo31406pending; Home76481/stack6748launched. Currentturnprogress resolves long4P/R8 and advancesremaininggates; production9bffed65unchanged/fullgoal incomplete.

Previous goal turn classified progress(ownerbranch long4P48frames saved/R8exact). Currentturn solo31406/Home76481/stack6748terminal: {"solo": {"states_match": true, "before_frames": 165581, "after_frames": 165591}, "home12_pass": true, "stack": {"lowest_sp": 16775328, "lowest_pc": 151326, "lowest_tick": 2080, "minimum_gap": 10708, "gap_sp": 16775328, "gap_end": 16764620, "gap_pc": 151326, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82189290}}. Normal58577confirmedlive; remainingRushserializedafterNormal. Candidate57690f18immutable,production9bffed65unchanged/fullgoal incomplete.

Normal58577terminal all40state/render/timingexact/errors[]. Ownerbranch profilemeans slightlylower bothR2(1377393.829→1377366.382) andsolo(858699.492→858666.200), butsolo fullroute+10frames/worst1388→1389 versus4P-48/worst2031unchanged. Explicitmixedtradeoff, notuniformgain. StartedalignedRush54598 afterNormalterminal. Candidateimmutable; fullgoal incomplete.

Ownerbranchretained afterallgates: alignedRush54598exact3001state/renderhashes/3011frames; legacy33574exact3000videohashes/2990updates/0drops/remaps/fallback/resetcleanuptrue. Allreadersterminal before promotingonlysrc/bc_rules.c; productionbuild36697terminal; production/scratch/testedROMexact57690f187fbf83ab152b4013552d043c90bb64d326683a76eac48a71e0badf4d. Evidence .local/bc-option-owner-branch/verified.json; selectedmanifestupdated. Long4P126714→126666(-48),solo165581→165591(+10),allstatesmatch. Acceptsmallsolotradeofffor4Pgain; notuniformimprovement. Worst4P1000window2031unchanged(~29.5421FPS),solo1389(+1). BC40/Normal40/R8ordinary/chargeunchanged. Home12pass/stack10708nooverlap. Currentturnprogress completesgatesandretainsnativeimprovement. Noactivejobs. Full60FPS/100%speed/full4Pnaturalclear goal incomplete.

Previous goal turn classified progress(ownerbranch57690f18retainedaftergates). Rendererreview baseline .local/bc-projectile-large-direct/before.asm: large0x1ba mappercase0ticks inR2window, ruledoutaddingfastpath; impactcase0x3fee244048ticks indicatesusedpath. Newisolated .local/bc-projectile-impact-direct directlysubmits0x1d4/1d6 afterexistingstraightpath in multicoreonly, samekey0x281c/0x281d/coords/flips; solo/grouping/fallbackunchanged. Production57690f18unchanged, no speedclaim/fullgoal incomplete.

Impactdirect candidate6c4278516b5df6f6fb8b9bdb40a3a822e35a175e210c158651586a9ce5cdf92c: build3070terminal, host50597terminal bothsource/aligneddirtypadding2400pools/37527orderedsprites/600stripsexact. Expanded reusable nativeQA adds0x1d6 expected0x281d; production/scratchscriptssynced. Native3909terminal655360art/flip/coords/missing/inputpreservationcasespass. Fullarchive .local/bc-projectile-impact-direct/candidate. BC4028249/R254770launched againstimmutablecandidate. ProductionROM57690f18unchanged. Currentturnprogress profiles/selectsusedrenderpath and checks distinct nativeoptimization; fullgoal incomplete.

Previous goal turn classified progress(impactdirectcandidatebuilt/host/native655360casesverified). BC4028249terminal: {"changes": [{"round": 2, "players": 4, "delta": -1}, {"round": 6, "players": 4, "delta": -1}, {"round": 7, "players": 4, "delta": -1}, {"round": 8, "players": 4, "delta": -1}], "total_added_frames": -4, "measurement_errors": false, "rom_changed": false}. R254770confirmedlive. Candidate6c427851immutable/production57690f18unchanged; fullgoal incomplete.

Impactdirectcontinuation: BC40four4Psampleseachsave1frame,remaining36ties/noerrors. Solo20038/Normal37150/R8ordinary15214/charge30365launched alongside R254770. NativeQA wording corrected from allbeamframes to sampledprojectileframes: test covers10sourceframeIDs includingbothimpacts×65536attributes, notall16bitIDs. Thislabelonlyedit syncedproduction/scratch/archive; testedROMunchanged. Currentturnprogress resolvesmatrix and expandsregressions, production57690f18unchanged/fullgoal incomplete.

ImpactR815214/charge30365terminal: {"r8": {"states_match": true, "before_frames": 1257, "after_frames": 1261, "mean_ticks": 846702.633, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1222, "after_frames": 1221, "mean_ticks": 760140.01, "replay_verified": true}}. R254770/solo20038/Normal37150pending; no source/ROMchanges.

Previous goal turn classified progress(impactBC40/R8comparisons resolved andbroadercheckslaunched). Currentturn longR254770/solo20038/Normal37150allconfirmedlive; Home7234/stack5612launched. Saved nativeprojectiledisassembly/codegen-comparison.json torelate eventualtiming toactualcode. Scratch6c427851immutable, production57690f18unchanged/fullgoal incomplete.

ImpactR254770terminal: {"states_match": true, "before_frames": 126666, "after_frames": 126477, "mean_ticks": 1375797.738, "worst_1000_frames": 2032, "before_projectile_ticks": 151118184, "after_projectile_ticks": 149595670}. Multirenderinstructions903→938; extrafastpath haswholefunctioncost. Solo/Normalpending; no promotiondecision untilterminal.

ImpactHome7234/stack5612terminal: {"home12_pass": true, "stack": {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2282, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2282, "overlap_samples": 0, "sampled_boundaries": 82239254}}. Solo20038/Normal37150re-polledlive. Currentturnprogress verifies189framelong4Pgain andrenderer151118184→149595670ticks, whiledocumentingworst2031→2032. Candidate6c427851notpromoted; fullgoal incomplete.

Previous goal turn classified progress(impactlong4P189frames saved/Home/stackresolved). Currentturn solo20038confirmedlive; Normal37150terminal: {"rows": 40, "errors": [], "all_hashes_match": true, "saved_frames": 0}. StartserializedRushgates; candidate6c427851immutable,production57690f18unchanged/fullgoal incomplete.

Impactsolo20038terminal: {"states_match": true, "before_frames": 165591, "after_frames": 165591}. AlignedRush60112terminal {"state_hashes": true, "render_hashes": true, "emulated_frames": true} (3001hashes/3011frames). Legacyvideo/resetnext; all priorreadersterminal.

Impactdirectretained: legacyRush80159terminal all3000videohashesexact/2990updates/0drops/remaps/fallback/resetcleanuptrue. Allreadersterminal beforepromoting src/bc_projectile_draw.c; productionbuild87814terminal and production/scratch/testedROMexact6c4278516b5df6f6fb8b9bdb40a3a822e35a175e210c158651586a9ce5cdf92c. ExpandednativeQAtool retainsbothimpactIDs655360cases and accurate sampledframes label. Evidence .local/bc-projectile-impact-direct/verified.json; selectedmanifestupdated. Long4P126666→126477(-189),solo165591exact/allstatesmatch; renderer151118184→149595670ticks. Worst4P1000window2031→2032(~29.5276FPS),ordinaryR81257→1261(+4),charge1222→1221(-1): documentednonuniformtradeoff. BC40net4saved; Normal40exact; Home12pass/stack10682nooverlap. Currentturnprogress completesgatesandretainsnative rendererimprovement. Noactivejobs. Full60FPS/100%speed/full4Pnaturalclear goal incomplete; scopedchecksnotwhole-gameproof.

Previous goal turn classified progress(impactdirect6c427851retained). Currentrenderer inspection confirms impactIDpair already compilerfolded toANDI/CMP, no redundanttwoIDcheck. Remaining mapperusesrangecheck/zeroextend/doubleindex/tableload/indirectjump. Priorpaired/twoentryrepeatcachesregressed, avoidrepeating. Newisolatednative-only optimize no-jump-tables added to existing no-bit-tests on projectile_draw_multi; mapping/source/allsubmissions/grouping/solo unchanged. Testcomparison-tree againstcurrenttable, notassumedfaster. Productionunchanged/fullgoal incomplete.

Nojumptablecandidateff8140a26053a3b0b713958a148672dd317215fbb0c55a317a3bc464a4127c7b built43050terminal; native62025terminal655360renderer casespass. Disassemblyconfirmscomparison-tree replacesindexedjump; no mapping/renderpolicychange. Fullarchive .local/bc-projectile-no-jump-tables/candidate. BC4091931/R249133launched; candidateimmutable. Currentturnprogress tests distinctcompilerdispatchoptimization; production6c427851unchanged/fullgoal incomplete.

Previous goal turn classified progress(nojumptablecandidate built/native655360rendercasespass). BC4091931terminal: {"changes": [{"round": 4, "players": 4, "delta": -3}, {"round": 5, "players": 4, "delta": -1}, {"round": 7, "players": 4, "delta": 4}, {"round": 8, "players": 4, "delta": -3}, {"round": 9, "players": 4, "delta": -1}, {"round": 10, "players": 4, "delta": 1}], "total_added_frames": -3, "measurement_errors": false, "rom_changed": false}. R249133confirmedlive. Candidateff8140a2immutable,production6c427851unchanged/fullgoal incomplete.

Nojumptablecontinuation: BC40net3saved but4P/R7+4/R10+1, othersimprove/tie. Solo25573/Normal68285/R8ordinary26116/charge70303started withsameimmutableff8140a2. LongR249133pending; no speedconclusion fromshortaggregate. Currentturnprogress resolvesmatrix and expandswhole-mode/runtimechecks; production6c427851unchanged/fullgoal incomplete.

Previous goal turn classified progress(nojumptableBC40net3saved/broadercheckslaunched). Currentturn R249133/solo25573/Normal68285confirmedlive; R826116/charge70303terminal: {"r8": {"states_match": true, "before_frames": 1261, "after_frames": 1254, "mean_ticks": 846057.212, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1221, "after_frames": 1217, "mean_ticks": 759311.882, "replay_verified": true}}. Candidateff8140a2immutable,production6c427851unchanged/fullgoal incomplete.

NojumptableHome77240/stack80943launched. Codegenaddressrows938→1036, caveatbaselineincludes jump-tabledata decodedasinstructions; this isnotdynamicinstructioncount. RealR8ordinary1261→1254/charge1221→1217improvementswithmatchingstates supportcontinuinggates. LongR249133/solo25573/Normal68285pending; production6c427851unchanged/fullgoal incomplete.

NojumptableR249133terminal: {"states_match": true, "before_frames": 126477, "after_frames": 126679, "mean_ticks": 1379214.34, "worst_1000_frames": 2031, "before_projectile_ticks": 149595670, "after_projectile_ticks": 152892446}. Currentturnprogress establishes long4P regression (+202frames, renderer+3296776ticks) despite R8 gains; solo/Normal/Home/stackpending, candidate notfavored forretention/fullgoal incomplete.

Previous goal turn classified progress(nojumptablelong4Pregression/R8resultsresolved). Solo25573/Normal68285/Home77240/stack80943allterminal: {"solo_states_match": true, "solo_before_frames": 165591, "solo_after_frames": 165591, "normal_errors": [], "normal_hashes_match": true, "normal_saved_frames": 0, "home12_pass": true, "stack": {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2984, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2984, "overlap_samples": 0, "sampled_boundaries": 82226044}, "decision": "rejected: long4P +202 outweigh scoped R8 gains"}. Allreadersterminal before restoringrenderer toretained6c427851source. Currentturnprogress rejects slowerdispatch andrestores; fullgoal incomplete.

Restorebuild89759terminal; scratch/productionexactretained6c427851. Noactivejobs. Read-onlyNormalshotprofile uses matching5ccbd713ELFandcapturedPCarray; saved .local/normal-shot-hot-review/{shot.asm,hotspots.json}. Largestindividualinstruction LSL.Wregistercount at0x656c4 contributes3608556ticks, usedforcolour<<11. Nextcandidatecan use16bitROR#5 ofalready-masked0..15colour foridenticalpalettebits, avoidingvariable11bitshift; mustverifyallcolourvalues/nativekeybits andNormal/Rushrenderstates beforepromotion. Currentturnprogress closesrejection/restores and identifiesnewNormalhotspot; fullgoal incomplete.

Previous goal turn classified progress(rejectednojumptables/restoredexact6c427851/profiledNormalpalettehotspot). NewisolatedNormalshot_palette_bits rotatesalready-masked0..15colour right5 on68000, same bits11–14 as left11; portablefallbackunchanged. Onlyspr_shots keyconstructionchanged, samecolour/code/cache/emissionorder. Nativekeyexhaustiveprobe prepared. Productionunchanged/fullgoal incomplete.

Normalpaletterotatebuild48251terminal, SHA369393a197055e53d46be5d5ea6b3504a25717f0b99c5ffdbe3f3ef7d33b5406. Nativeprobeall256colourbytes×2048codes=524288identicalkeys; disassemblyshowsROR.W#5 instead ofvariableLSL.W#11. Fullarchive .local/normal-shot-palette-rotate/candidate. Normal40state/render29173running; BC40also launched. Scratchimmutable,production6c427851unchanged. Currentturnprogress implements/nativeverifiesNormalhotspotoptimization; speedandfullgoalnotyetproved.

Previous goal turn classified progress(Normalpaletterotatebuilt/native524288keysverified). BC4048446terminal: {"changes": [], "total_added_frames": 0, "measurement_errors": false, "rom_changed": false}. Normal29173confirmedlive, completedstate/renderchecks match. Candidate369393a1immutable/production6c427851unchanged/fullgoal incomplete.

Palettecontinuation: BC40unchanged; Normal29173ongoing. LongBC4P69300/solo99002/Home44979/stack85154launched, immutable369393a1. RushandvulnerableNormal serializeaftermatrix. Currentturnprogress resolvesBCmatrix andexpandsregressions; production6c427851unchanged/fullgoal incomplete.

PaletteNormal29173terminal: {"errors": [], "all_hashes_match": true, "saved_frames": 3, "changes": [{"players": 4, "section": 7, "frames": 1014, "baseline_frames": 1015, "saved_frames": 1}, {"players": 4, "section": 8, "frames": 1021, "baseline_frames": 1022, "saved_frames": 1}, {"players": 4, "section": 9, "frames": 1005, "baseline_frames": 1006, "saved_frames": 1}], "four_player_frames": 10100, "four_player_fps": 59.40594059405941, "four_player_worst_frames": 1038}. Currentturnprogress resolvesNormalperformance/rendergate; broaderchecks stillpending/nopromotion.

Previous goal turn classified progress(Normal40allhashesmatch/3framessaved/BC40exact). Currentturn alignedRush55806terminal {"state_hashes": true, "render_hashes": true, "emulated_frames": true} frames3011; Home44979/stack85154terminal {"home12_pass": true, "stack": {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2282, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2282, "overlap_samples": 0, "sampled_boundaries": 82239254}}. LongBC4P69300/solo99002confirmedlive. Candidate369393a1immutable/production6c427851unchanged; fullgoal incomplete.

PalettelegacyRush2097terminal:2990updates/0drops/remaps/fallback/resetcleanuptrue, but1of3000videohashes differs at102. Captures6678/60800terminal: {"101": {"pixels": 0, "bounds": null}, "102": {"pixels": 4, "bounds": [9, 24, 244, 24]}, "103": {"pixels": 0, "bounds": null}}. Sameframe102top-rowphenomenon as earlierparitycandidate; cannotclaimrasterfidelity frommathkeyproof. VulnerableNormal85539terminal comparison against retainedbyte-distancefixture {"state_hashes": true, "render_hashes": true, "before_frames": 3052, "after_frames": 3045}. Candidateunpromoted pendingdisplaydecision; fullgoal incomplete.

Previous goal turn classified no progress toward implementation (reported verified regular 4P FPS). Current turn revalidated terminal jobs and completed palette long comparisons: 87845 BC 4P states and 160172 solo states match; video totals unchanged at126477/165591. Palette memory captures27386/90078 terminal: VRAM/CRAM/VSRAM/SAT identical at101/102/103. Four differing pixels at y24 are colored background stars in baseline, black in candidate. HUD window callback timing is being traced at native instruction boundaries; cause not yet established. Production6c427851 unchanged; candidate369393a1 unpromoted; full goal incomplete.

Palette HUD instruction trace24818/65946 terminal and video-identical to uninstrumented104-frame captures. At frame102 baseline window-off write starts cycle211204 (line23); candidate starts212044, four ticks after line24 boundary212040. Both write0x9200 with identical mask0x0c000005. This establishes a late window switch, not differing sprite keys. New isolated combined candidate retains palette rotation and uses word-sized counter row calculation plus native BTST window-mask selection. Production unchanged. Currentturnprogress diagnoses the raster failure and prepares a targeted fix; fullgoal incomplete.

Combinedpalette/HUD build86172 terminal SHA387bbc495fef300a19b4c38ae7ae54b4aaf664c35a839139a44a9565a39a3b51; full archive .local/normal-shot-palette-hud/candidate. Native probe verifies256 V-counter mappings and2097152 row-mask cases. Trace49168 terminal: frame102 window-off begins210771 on line23, before boundary212040. Raw104 video hashes all differ, so fixed-video captures no longer establish matching gameplay alignment; do notclaim raster equivalence. Earlier probe missingCORE and trace126-byte hard bound failures were corrected (COREexplicit, callback bound from nextsymbol), both terminal. Normal40state/render99676 andBC4075491 launched against immutable scratch; production6c427851 unchanged. Currentturnprogress diagnoses late-HUD artifact, implements targeted combined candidate, and begins broader gates. Full60FPS/100%speed and natural4Pclear remain incomplete.

Previous goal turn classified progress (instruction-timed late HUD switch identified, combined candidate387bbc49 built/native checked). Currentturn Normal99676 confirmedlive with matching simulation states but early sprite-hash differences; first1P samples differ at44 of1001 boundaries, onlythrough77/entryblink. BC4075491terminal, no measurementerrors/ROMchange: R2/4P+1,R4/4P+2,R5/4P+1,R6/4P+1,R10/2P-1,R10/3P-1. Long4P95546/solo18873/Home94539 launched. Independent sprite diagnostics use private offsets-before/offsets-after directories, avoiding sharedqa_soak scratch while matrix runs; no ROM edits. Production6c427851 unchanged/fullgoal incomplete.

Normal99676 terminal exit2: all40 simulation traces match; every raw sprite-hash mismatch matches one independently captured offscreen empty SAT (x=y=-32,size1x1,tile0); other sprite hashes exact. Do NOT dismiss as fidelity pass: candidate tile0 has byte28=2 versus baseline0, although both ROM star_tiles firsttile are zero. Native per-video-frame boot trace isolates persistent corruption atframe633 (baseline remainszero). Private opcode watch over632–634 reports0 sampledCPUcycles, so it did not identify writer; no cause claimed. Evidence sprite-detail-comparison.json,offscreen-sentinel-comparison.json,tile-before/after/tile-events.json. Normal4P total10102 vs10103, worstsection3 worsens1038→1039. Home94539 terminal all12pass. Long4P95546/solo18873 still monitored; candidate remains unpromoted, production6c427851 unchanged/fullgoal incomplete. Currentturnprogress locates independent VRAM corruption instead of suppressing rawrenderfailure.

Finalpoll confirms long4P95546/solo18873 terminal (supersedes pending wording): {"natural4p-r2": {"states_match": true, "before": 126477, "after": 126484, "mean_ticks": 1375803.982}, "solo": {"states_match": true, "before": 165591, "after": 165588, "mean_ticks": 858663.953}}. All candidate reader jobs terminal; no ROM restoration or promotion yet. VRAM tile0 corruption still unresolved, candidate unpromoted/fullgoal incomplete.

Previous goal turn classified progress (startup tile corruption isolated, all gates terminal). Currentturn native trace establishes root cause: startup queue contains valid nonzero lengths, then HUD H-int interrupts flushQueue between0x6c0/0x6c2, savedPC0x6c2; window write consumes pendingDMAcommand and subsequent transfer has length0 (65536words), stallingCPU631–641 and overwritingtile0. No opcode samples632–634 becauseCPUhaltedbyDMA, confirmed by DMA_length snapshots. Candidate387bbc49 rejected, isolatedhud/sprites restoredretained6c427851 sources. New src/dma_queue.s supplies project-local flushQueue with savedSR/interruptmask only around pairedwordcommand, preservesmemorywordtrigger/queueorder. No externalSGDKfiles changed; productionunchanged/fullgoal incomplete.

AtomicDMA build18660 terminal SHA1d015b8bf8733669a38a6ea0601fe86082f97f86deccd429d093db92d0f8936a; fullcandidate archive .local/dma-command-atomic/candidate. Isolated renderer/hud backto6c427851; only native queue protection new. Startup620–655 no remainingDMA observed atframeboundaries,tile0blank. Normalentry80update diagnostic77967terminaltile0alwaysblank. Privatepatched known-failing387bbc49 boots620–750 withblanktile0, maximumremainingDMA27words vs prior65536wordrun; regression.py/patch.elf/result retained. This is bounded startup evidence, not all DMA phases. Normal40/BC40/Home12 launched against immutable scratch. Currentturnprogress proves interrupt split-command race and implements/testsfixednativequeue; production6c427851 remains unchanged/fullgoal incomplete.

Previous goal turn classified progress (DMA command race proven, atomic native queue implemented/startup regression passes). BC4054007 andHome62204 terminal: all12modalpaths pass; BCmatrix {"measurement_errors": false, "rom_changed": false, "changes": [{"round": 2, "players": 4, "before": 606, "after": 607}, {"round": 5, "players": 4, "before": 625, "after": 627}, {"round": 6, "players": 4, "before": 834, "after": 838}, {"round": 8, "players": 3, "before": 612, "after": 614}, {"round": 8, "players": 4, "before": 742, "after": 741}, {"round": 10, "players": 3, "before": 621, "after": 620}]}. Normal67790 confirmedlive, completedstate/rendercomparisons match. LongBC4P/solo launched on immutable1d015b8b. Production6c427851 unchanged/fullgoal incomplete.

AtomicDMA Normal67790terminal all40state/renderhashes match: {"errors": [], "all_hashes_match": true, "changes": [{"players": 2, "section": 5, "before": 1002, "after": 1003}, {"players": 2, "section": 9, "before": 1000, "after": 1001}, {"players": 4, "section": 3, "before": 1038, "after": 1040}, {"players": 4, "section": 7, "before": 1015, "after": 1013}, {"players": 4, "section": 8, "before": 1022, "after": 1023}], "four_player_frames": 10104}. New tools/qa_dma_command_atomic.py read-only nativeaudit750bootframes verifies186transfer commandpairs, descriptorVDPregs, priority7duringbothwords andsavedpriority3restored; maxqueued2752words,nozero-lengthdescriptors. Tool copiedto scratch/archive, ROMimmutable. AlignedRush nowlaunched; long4P52471/solo45034 pending. Currentturnprogress adds reproducible nativeatomicityaudit andresolvesNormalgate; fullgoal incomplete.

AtomicDMA long4P52471/solo45034 re-polled andconfirmedlive; alignedRush45566 andstack29700 running. pending.json storeshandles/remaininggates. Normal4P10104frames for10000updates (prior10103), worstsection3=1040frames (prior1038). Correctnessfix timingcost explicitly retained for evaluation, not describedasspeedgain. Productionunchanged; fullgoal incomplete.

Previous goal turn classified progress (Normal40resolved/nativeDMAauditadded). Long4P52471/solo45034/alignedRush45566/stack29700 allterminal: {"natural4p-r2": {"states_match": true, "before_frames": 126477, "after_frames": 126555, "mean_ticks": 1375770.655, "worst_1000_frames": 2031}, "solo": {"states_match": true, "before_frames": 165591, "after_frames": 165604, "mean_ticks": 858706.485, "worst_1000_frames": 1389}, "rush_aligned": {"state_hashes": true, "render_hashes": true, "before_frames": 3011, "after_frames": 3011}, "stack": {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2984, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2984, "overlap_samples": 0, "sampled_boundaries": 82213812}}. DMA correctness protection adds78frames over87845updates and13frames oversolo160172updates; gameplay states preserved, disclosed as cost notspeedgain. AlignedRush3011frames andbothhashstreams exact. LegacyRush88376 andR8ordinary/charged launched againstimmutable1d015b8b; production6c427851 unchanged/fullgoal incomplete.

AtomicDMA legacyRush88376 terminal all3000videohashes identical,2990updates/0drops/remaps/wheelfallback/resetcleanuptrue. R8ordinary94984/charged71273terminal: {"r8": {"states_match": true, "before_frames": 1261, "after_frames": 1261, "mean_ticks": 846745.991, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1221, "after_frames": 1224, "mean_ticks": 760116.966, "replay_verified": true}}. Allreaderjobs terminal. Retaining correctnessfix despite small timingcost; copiedonlynew src/dma_queue.s toproduction, nativeaudittoolalready present. Productionrebuild started, nofullgoalcompleteclaim.

AtomicDMA productionbuild92866terminal; production/scratch exact1d015b8b. verified.json andselected-candidate.json updated; noactivejobs. Retainednativeatomiccommandfix plusQAaudit. Regular4Pboundedmean600000/10104=59.3824FPS,worstsection3=60000/1040=57.6923FPS. BC4Pboundedworst1000updates2031frames=29.5421FPS. No60FPS/100%speed claim. Currentturnprogress resolvesallgates/promotescorrectnessfix; fullgoal andnatural4Pclear remain incomplete.

Previous goal turn classified progress (atomicDMA fullyverified/promoted1d015b8b). Noactive readers. New combined candidate reapplies prior nativepaletteROR and word-sized HUDcounter/BTST helpers on corrected atomicDMA foundation; old387bbc49 was blockedbyprovenDMAcommandrace, now independentlyfixed. Production1d015b8b unchanged. Mustremeasureallgates, noassumptionofgain/fidelity. Currentturnprogress starts evidence-based retest with changedfoundation; fullgoal incomplete.

Combined palette/HUD/atomicDMA build26856terminal SHA531d406ff622e15337104efc228d6fa443c92db14e28324b632fe5b62f25770d; fullarchive .local/normal-palette-hud-atomic/candidate. NativeDMAaudit186transfers pass; tile91466terminalblankthroughboot/Normalentry80updates, priorcorruptionabsent. BC406704terminal {"errors": false, "changes": [{"round": 4, "players": 4, "before": 871, "after": 872}, {"round": 5, "players": 4, "before": 627, "after": 626}, {"round": 6, "players": 4, "before": 838, "after": 837}, {"round": 8, "players": 4, "before": 741, "after": 740}, {"round": 10, "players": 3, "before": 620, "after": 622}]}. Normal40654 ongoingmatchingstate/render; long4P5134/solo67784launched. CurrentretainedBCplayer instructionprofile saved .local/bc-player-current-review/{player.asm,hotspots.json} againstmatching1d015b8bELF: taskslotstate/dispatch andmovement dominate; no untestedBCcodeedits. Currentturnprogress buildsnewcombinedcandidate onverifiedDMAfoundation andresolvesinitialgates. Productionunchanged/fullgoal incomplete.

Previous goal turn classified progress (531d406f built/startup andDMAaudits passed/BC40resolved). Currentturn Normal40654,long4P5134,solo67784 allre-polledconfirmedlive; Normalthrough4Psection6 matchesstate/renderhashes. Home12/stackgateslaunched onimmutablecandidate. NoROM/source mutation; production1d015b8bunchanged/fullgoal incomplete.

Combined Normal40654terminal: {"errors": [], "all_hashes_match": true, "changes": [{"players": 4, "section": 3, "before": 1040, "after": 1038}, {"players": 4, "section": 7, "before": 1013, "after": 1014}, {"players": 4, "section": 8, "before": 1023, "after": 1022}], "four_player_frames": 10102, "four_player_worst": 1038}. Allrawspritehashesnowmatch, unlikepre-DMA-fixcandidate. AlignedRush launched aftermatrixterminal; noqa_soakoffsetconcurrency. PriorMOVEM.Wvelocityexperiment reviewed: was actor motion before widenedprojectilevelocities, not currentfour-longwordshotpair; no newnativeprototypeorROMchangesyet. Currentturnprogress resolvesNormalgate/continuesremainingtests; fullgoal incomplete.

CombinedHome55686/stack29007terminal: all12modalpaths pass; stack {"lowest_sp": 16775302, "lowest_pc": 712, "lowest_tick": 2984, "minimum_gap": 10682, "gap_sp": 16775302, "gap_end": 16764620, "gap_pc": 712, "gap_tick": 2984, "overlap_samples": 0, "sampled_boundaries": 82235766}. R8ordinary54107/charged28756 launched. Candidate531d406f remainsimmutable andunpromoted; fullgoal incomplete.

Combinedlong4P5134terminal: {"states_match": true, "before_frames": 126555, "after_frames": 126541, "mean_ticks": 1375778.67, "worst_1000_frames": 2032}. AlignedRush12974terminal: {"state_hashes": true, "render_hashes": true, "before_frames": 3011, "after_frames": 3010}. Solo67784re-polledlive. LegacyRushlaunched afteralignedfixtureterminal. Currentturnprogress resolveslong4P/alignedRush evidence; production1d015b8bunchanged/fullgoal incomplete.

Previous goal turn classified progress (Normal40/long4P/alignedRushresolved). Remaining solo67784/R854107/charged28756/legacyRush83699 allterminal: {"r8": {"states_match": true, "before_frames": 1261, "after_frames": 1259, "mean_ticks": 846715.114, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1224, "after_frames": 1228, "mean_ticks": 760085.403, "replay_verified": true}, "solo": {"states_match": true, "before_frames": 165604, "after_frames": 165600}, "rush": {"different_video_count": 0, "first_differences": [], "updates": 2990, "sprite_drops": 0, "runtime_remaps": 0, "wheel_fallback_frames": 0, "soft_reset_released_wheel_allocations": true}}. Legacy3000video hashesexact despitealignedRushsaving1video frame in differentinputschedule. Retaincombined531d406f forNormal-2/R2-14/solo-4/alignedRush-1, disclose4Pworst+1 andchargedR8+4. Allreaders terminal; copiedonlyhud.c/sprites.c toproduction, DMAprotectionretained; productionbuildstarting. Currentturnprogress resolvesremaininggates/promotescheckedcandidate; fullgoal incomplete.

Combinedproduction54856terminal exact531d406f matchesisolatedtestedROM. verified.json/selected-candidate updated; noactivejobs. Regular4P10000updates/10102frames=59.394179FPS,worstsection3=57.803468FPS. BC4Pworst1000window2032frames=29.527559FPS; long4P126541 andsolo165600. Full60FPS/100%speed andnatural4Pclear remainunmet. Currentturnprogress completespromotion/evidence; nextwork targetsBCweapon/contactcosts with matchingretainedprofile, no fullgoalcompleteclaim.

Previous goal turn classified progress (combined531d406f verified/promoted). Currentturn read retainedBCweapon/contactsource and priorMOVEM.Wactortrial; separate32-bit projectileload prototype .local/bc-shot-motion-pair loads x/y/vx/vy withMOVEM.L but commitsXbeforeY and preservesXretirement. Privateprobe compareswholeBcBeam andretirement vsretainednativeaxis across20padded/boundaryorigins×65536velocities; not integratedintoplayableROM. Firstcompile lackedmodulohelper, replaced boundedindexmodulo withconditional; firstprobe98652terminalhit30000framebudgetwithstatus1 (notmismatch), rerun2206 uses100000 limit. Production/scratch531d406f unchanged. Currentturnprogress implements independenttargetedprototype; no speedclaim/fullgoal incomplete.

Pairprototype2206terminal:1310720whole-BcBeam/retirementcomparisons pass; reference1714.795840 vsMOVEM1988.977603 coreticks/call (~16%slower),108vs114bytes. Rejectbeforegameplayintegration; noROMsourcechanges/rebuild needed. Evidence .local/bc-shot-motion-pair/rejected.json andnativeprobeELF/source. Nolivejobs; production/scratch531d406f retained. Currentturnprogress rulesout a specificmovementbatchingapproach withnativecost/equivalenceevidence. Full60FPS/100%speed andnatural4Pclear remain incomplete.

Previous goal turn classified progress (nativepaired-motionprototype rejected after1310720matchingcases/slowercost). New isolatedcontactcandidate730ba9012ad23bb4c248e1e38de31762cc00a91d7c1e94e4f412f67b4244b0b9 carries partyshotbounds result intoactor_contacts: gate0unchangedsolo/unknown,gate1uses sharedindexedhelper withoutduplicatedouterrectangle,gate2skipsproven-impossibleshots while retainingbodycontacts. Sameindex/target tested immediatelybeforecall; individualslotstate/radius/order/consumption/damageunchanged. Allpublicnormalshot APIs retain originalgates. Hostpartyfixtures pass; contactstream32000 cached/uncachedcomparisons/6953orderedevents/3002emptyvulnerableunions/904ordinaryvulnerableunions pass. Build84218terminal/fullarchive .local/bc-contact-prechecked/candidate. Long4P/BC40launched; no nativeperformanceclaimyet. Production531d406funchanged/fullgoal incomplete.

Previous goal turn classified progress (precheckedcontactcandidate built/32000hostcomparisons passed). BC4022968terminal: {"measurement_errors": false, "rom_changed": false, "changes": [{"round": 2, "players": 4, "before": 607, "after": 606}, {"round": 3, "players": 4, "before": 604, "after": 603}, {"round": 5, "players": 4, "before": 626, "after": 625}, {"round": 6, "players": 4, "before": 837, "after": 838}, {"round": 7, "players": 4, "before": 633, "after": 635}, {"round": 8, "players": 1, "before": 602, "after": 601}, {"round": 8, "players": 4, "before": 740, "after": 739}, {"round": 9, "players": 4, "before": 603, "after": 602}]}. Long4P10573 re-polledconfirmedlive; longsololaunched againstimmutable730ba901. Production531d406funchanged/fullgoal incomplete.

Precheckedcontactadditionalgates launched: solo40509/Normal20886/Home23388/R864514/chargedR8. Codegen saved before/afteractor_contacts assembly:2560→3136bytes; two wrapper calls inline into a larger helper, so larger code/extra gate cost may offset removedbounds. Awaitnativeprofilingratherthanassumebenefit. Candidateimmutable; production531d406funchanged. Currentturnprogress resolvesBCmatrix andchecks actualgeneratedcode/expandsregressioncoverage; fullgoal incomplete.

Previous goal turn classified progress (BC40resolved/nativecodegenreview/gateslaunched). Currentturn Home23388/R864514/charged57039terminal: all12Homepaths pass; {"r8": {"states_match": true, "before_frames": 1259, "after_frames": 1262, "mean_ticks": 846692.938, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1228, "after_frames": 1225, "mean_ticks": 760129.314, "replay_verified": true}}. Long4P10573/solo40509/Normal20886re-polledconfirmedlive. Candidate730ba901immutable; production531d406funchanged/fullgoal incomplete.

Precheckedcontactlong4P10573/Normal20886/stack10509 terminal. R2 {"states_match": true, "before_frames": 126541, "after_frames": 126446, "mean_ticks": 1374272.571, "before_mean_ticks": 1375778.67, "worst_1000_frames": 2030, "before_contacts_ticks": 158545282, "after_contacts_ticks": 157045028}. Normal {"errors": [], "all_hashes_match": true, "saved_frames": 0}. Stack {"lowest_sp": 16775336, "lowest_pc": 151466, "lowest_tick": 2080, "minimum_gap": 10716, "gap_sp": 16775336, "gap_end": 16764620, "gap_pc": 151466, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82431342}. Solo40509re-polledlive. AlignedRushstarted afterNormalterminal; immutable730ba901/production531d406funchanged. Currentturnprogress confirms long4P improvement withcanonicalstates, Normalunaffected andstackpass; fullgoal incomplete.

Solo40509finalpollterminal: {"states_match": true, "before_frames": 165600, "after_frames": 165635}. Supersedespendingwording. OnlyalignedRush57595running; legacyRushremainsnextserialgate. Candidateunpromoted/fullgoal incomplete.

Previous goal turn classified progress (long4P-95/worst-2, solo+35, Normalunchanged resolved). AlignedRush57595terminal: {"state_hashes": true, "render_hashes": true, "emulated_frames": true, "frames": 3010}. LegacyRushnextserialgate, production531d406funchanged/candidate730ba901immutable/fullgoal incomplete.

PrecheckedcontactlegacyRush54318terminal: {"video_hashes_match": true, "updates": 2990, "sprite_drops": 0, "runtime_remaps": 0, "wheel_fallback_frames": 0, "soft_reset_released_wheel_allocations": true}. Allreaders terminal. Retaining4P95-framegain/worstwindow2-framegain whiledisclosing solo35-framecost (~0.021%) andordinaryR8+3/chargedR8-3; comparedgameplay/render/video remainexact. Copiedbc_rules.c/bc_world.c/bc_rules.h toproduction andbuilding; nofullspeedclaim. Currentturnprogress resolveslastgate/promotesverifiedcandidate; fullgoal incomplete.

Precheckedcontactproduction85263terminal exact730ba901 matchestestedcandidate. verified.json/selectedmanifestupdated; noactivejobs. CurrentBC4Plong126446frames/87845updates, worst1000window2030frames=29.556650FPS; solo165635frames. Normal4P remains59.394179FPS boundedaverage. Full60FPS/100%speed/fullnatural4Pclear notachieved. Currentturnprogress completescheckedpromotion; goalactive.

Previous goal turn classified progress (precheckedcontact730ba901verified/promoted). New isolatedsingle-core variant passes near flag through one shared call instead of selecting two separatelyinlinedwrappers; unchanged bounds/individualtests/shotgate semantics. Intended to avoid measured576byteactor_contacts expansion and reducebranch/codecost; nativebenefit unproven. Allreaderspreviouslyterminal, production730ba901unchanged. Currentturnprogress prepares focuseddeduplicationvariant; fullgoal incomplete.

Single-corebuild26040terminal SHA900c982dd8397ff15558a5557749489efc98260e1e2043de3c186d7c09fbf789; fullarchive .local/bc-contact-single-core/candidate. Host32000contactcomparisons/6953orderedevents pass. Nativeactor_contacts3136→2562bytes (-574), proving intendeddeduplication without yetprovingruntimegain. Long4P55413/solo68400/BC4058394 launched onimmutablecandidate; production730ba901unchanged/fullgoal incomplete. Currentturnprogress buildsandchecks distinctcompactcontactvariant.

Previous goal turn classified progress (single-core900c982d built/host32000pass/nativecode574bytessmaller). BC4058394terminal {"measurement_errors": false, "rom_changed": false, "changes": [{"round": 6, "players": 4, "before": 838, "after": 837}, {"round": 7, "players": 4, "before": 635, "after": 633}, {"round": 8, "players": 3, "before": 614, "after": 613}, {"round": 10, "players": 3, "before": 622, "after": 620}]}. Long4P55413/solo68400re-polledconfirmedlive. Production730ba901unchanged/candidateimmutable/fullgoal incomplete.

Single-coreBC40net6framessaved/no slowercases; Normal43319/R898461/charged21095/Home12/stack launched, withlong4P55413/solo68400pending. NoROMedits; candidate900c982dimmutable/production730ba901unchanged. Currentturnprogress resolvesBCmatrix andexpandsnativefidelity/performancegates; full60FPS/100%speed/fullnatural4Pgoal remains incomplete.

Previous goal turn classified progress (single-coreBC40net6saved/no regressions, broadergateslaunched). R898461/charged21095/Home26364/stack5983terminal; all12Homepaths pass; {"r8": {"states_match": true, "before_frames": 1262, "after_frames": 1264, "mean_ticks": 846669.999, "replay_verified": true}, "r8-charge": {"states_match": true, "before_frames": 1225, "after_frames": 1227, "mean_ticks": 760020.17, "replay_verified": true}, "stack": {"lowest_sp": 16775332, "lowest_pc": 151466, "lowest_tick": 2080, "minimum_gap": 10712, "gap_sp": 16775332, "gap_end": 16764620, "gap_pc": 151466, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82319878}}. Long4P55413/solo68400/Normal43319re-polledconfirmedlive. Candidate900c982dimmutable/production730ba901unchanged. Currentturnprogress resolvesstress/modal/stackgates; fullgoal incomplete.

Natural4Pclear work resumed independently: archivedretained730ba901 to .local/bc-natural4p-scroll-horizon8/build, noROMchanges. Privatepilotonly changesR8nonboss horizon4→8/threatradius64→96, addressingpreviousscrolling deaths beforeboss. RealHome4P/7lives/continues, nohealth/weapon/protection/enemydefeatinjections; recordedcontrollers forlaterindependentreplay. Session45424running; run.json retainsfullscope. Archiveis separatefromproduction/scratch, so unrelatedcandidatebuilds safe while thisreader runs, but nevermodifyitsbuild. Single-corelong55413/68400/Normal43319pending; productionunchanged. Currentturnprogress resolvesstressgates andstartsconcretefullcampaignverification attempt; fullgoal incomplete.

Previous goal turn classified progress (stress/modal/stackresolved andnatural4Ptriallaunched). Single-corelong55413/68400/Normal43319terminal: {"natural4p-r2": {"states_match": true, "before_frames": 126446, "after_frames": 126415, "mean_ticks": 1373738.205, "worst_1000_frames": 2032}, "solo": {"states_match": true, "before_frames": 165635, "after_frames": 165644, "mean_ticks": 859394.55, "worst_1000_frames": 1394}, "normal": {"errors": [], "all_hashes_match": true, "saved_frames": 0}}. Natural4P45424re-polledlive, tick6000R1firstboss/allfouralive, buildarchiveindependent. Production730ba901unchanged; fullgoal incomplete.

Single-corealignedRush4491launched afterNormalterminal; currentlong4P31framesbetter butworstwindow+2/solo+9 explicit. OnlythiscandidateROMreader remains; separate naturaltrial45424 remainslive onitsownarchived730ba901ROM. Productionunchanged/fullgoal incomplete.


Goal continuation 2026-10-06: previous turn classified no progress toward implementation (answered the Regular 4P FPS question from existing evidence). Revalidated next action: aligned Boss Rush candidate 900c982d finished, 3001 state/render hashes equal retained 730ba901 and 3010 video frames unchanged. Launched final legacy Rush video/cleanup gate session 96637, serialized after aligned run. Natural campaign session 45424 authoritatively polled live; reached round 4, tick 28122. Full natural 4P clear remains unverified. Production unchanged; goal incomplete.

Single shared contact core 900c982d rejected after final gate: legacy Rush session 96637 terminal, all 3000 video hashes match, 2990 updates, zero sprite drops/remaps/wheel fallbacks, reset releases allocations. Aligned state/render hashes also exact. Long 4P saves only 31 frames while worst 1000-update window grows 2030 to 2032, solo +9, R8 ordinary/charge +2 each. Smaller code alone does not satisfy sustained-speed objective. Rejection archived in .local/bc-contact-single-core/rejected.json; production SHA verified unchanged 730ba901. All candidate readers terminal; separate natural campaign 45424 remains live. This turn produced completed fidelity evidence and a candidate disposition (progress); goal still incomplete.


Goal continuation 2026-10-06: previous turn progress (single shared core rejected after completed gates). Natural campaign 45424 polled live. New isolated candidate 69f1eeebf39b53a2fd7aec61c8776b357695f614ec5baa2b9f5b398203b6f480 restores retained source then specializes the near wrapper using indexed = near || index != 0. Near already requires an immediately passed non-null index rectangle; original unindexed public path remains available. This removes nullable-index branches only in the proven indexed path, preserving slot order/live checks/hitbox semantics. Host stream 32000 comparisons and 6953 ordered events pass. Build38836 terminal; native actor_contacts 3136 to 3032 bytes. Full archive .local/bc-contact-index-specialized/candidate. Long4P85273 and BC4098703 launched on immutable scratch ROM; performance unproven, production unchanged, full goal incomplete.


Goal continuation 2026-10-06: previous goal turn progress (indexed-path specialization built and host-verified). Long4P85273 and natural campaign45424 both authoritatively polled live; campaign reaches R4 tick30965. BC40 session98703 terminal: no measurement errors or ROM changes, no slower cases; R7/4P635->633, R8/3P614->613, R10/3P622->620, net five video frames saved. Comparison archived. Launched solo18026 and Normal4015721 against unchanged candidate69f1eeeb, plus Home modal and R8 replay gates. Production730ba901 unchanged; full-speed/fullclear objectives incomplete.


Goal continuation 2026-10-06: previous turn progress (BC40 completed comparison and further gates launched). Long4P85273, solo18026, Normal4015721 and separate natural campaign45424 confirmed live through session polls. Home52963 terminal: all12 mode/player modal, cancel, launch cases pass. R8ordinary38223 terminal: all1000 state traces equal retained730ba901 and independent replay verified, but1262->1264frames (+2), mean846672.127ticks. This regression will count against retention. Launched chargedR866841 and boundedstack79325; immutablecandidate69f1eeeb remains unpromoted. Evidence .local/bc-contact-index-specialized/runtime-comparison.json. Fullspeed/fullnatural4Pclear still incomplete.

Long4P85273 now terminal: all87845canonical states match;126446->126494(+48) video frames, worst1000window unchanged2030. Profile mean1377328.274ticks versus retained1374272.571. Candidate69f1eeeb rejected for performance. Normal15721 intentionally interrupted, terminal130; chargedR866841 and stack79325 terminal0. Solo18026 interrupt requested and terminal confirmation pending. Production untouched; naturalcampaign45424 independent and still running. No more gates needed for rejected variant.


Goal continuation 2026-10-06: previous turn progress (long4P exact-state timing proves specialization slower; rejection). Last solo18026 terminal0: completed160172states all match,165635->165640(+5). ChargedR8 states/replay match1225->1224(-1). Stack10712byte minimum gap/no overlaps in bounded sample. Normal was intentionally stopped after rejection. All candidate readers terminal. Restored scratch retained sources and build71216 terminal exact SHA730ba9012ad23bb4c248e1e38de31762cc00a91d7c1e94e4f412f67b4244b0b9. Remaining evidence archived in remaining-comparison.json/rejected.json. Weapon hotspot review identified prior failed timer asm-goto, stationary-motion, known-free option allocation, fire outlining and terrain-table trials; did not repeat them. Earlier indexed-address attribution only0.0237percent makes that a low-value target. Separate natural campaign45424 authoritatively live, nowR4tick35256 with both continues consumed. Production unchanged, full objective incomplete.


Goal continuation 2026-10-06: previous turn progress (remaining rejection evidence/restoration exact). Separate naturalcampaign45424 polled live. New isolated candidate319384fe8b363aefdab8493ba59cf5b809e37ea2c06f0a8f2ff16e8a1c459288 replaces the two party-contact seven-field OR chains with contact_event_pending. Native MOVEP.L reads even/odd bytes at either alignment; maskFF00FFFF removes only score_id from even bytes, combines all other event bytes. Static layout assertions preserve eight-byte record. Portable fallback retains original predicate. No callback order or payload changes. Host32000contact comparisons/6953ordered events pass; native4096single-field/value/alignment cases verify predicate, score-ID exclusion and input/sentinel preservation. Probe56199/build58100 terminal. Full archive .local/bc-contact-event-predicate/candidate; long4P19871 and BC4021780 launched on immutable scratch ROM. Production730ba901 unchanged. Performance unproven and full goal incomplete.


Goal continuation 2026-10-06: previous goal turn progress (MOVEP event predicate candidate built/host/nativechecked). Long4P19871 and naturalcampaign45424 authoritatively polled live; naturalrun reachesR4tick38000, lives6/2/6/0, no credits after both continues. BC4021780 terminal: no errors or ROM mutation; R3/4P603->604 and R10/4P652->654, other38cases unchanged, net3frames worse. Native predicate coverage extended to all256 field-presence masks crossed with all256 repeated byte values and both alignments, plus4096singlefield cases:135168pass with source/sentinel preservation. Not all2^64 payloads; tests support intended bitwise predicate. New solo94639 launched; candidate immutable/unpromoted, production unchanged. Full objective remains incomplete.


Goal continuation 2026-10-06: previous turn progress (native combined-field coverage and BC40 comparison). Long4P19871/solo94639/naturalcampaign45424 all authoritatively polled live. Read-only matching retained ELF/cycle histogram saved in retained-party-hotspots.json/retained-party-contact.asm. Important correction: compiler already folds logical source chain into six OR.B loads after retired byte, not seven separate branches. MOVEP variant therefore saves less than source appearance suggests. Existing temporary contacts are stack-resident even addresses; potential next variant can explicitly align only local records and use masked longword reads, without changing public ABI or global event layout (prior global alignment attempt rejected). No ROM mutation or second candidate while current readers live. Production unchanged; performance/fidelity goal incomplete.

Long4P19871 terminal: all87845 canonical states match;126446->126434(-12) total frames, worst1000window2030->2028(-2), profiled mean1374285.598ticks versus1374272.571 (slightly higher CPU mean despite video improvement). Archived long-comparison.json; solo94639 remains pending. Small mixed gain warrants remaining evidence; no promotion or fullspeed claim.


Goal continuation 2026-10-06: previous turn progress (long4P completed, exact states and small video gain; source/codegen audit). Solo94639 terminal: all160172canonicalstates match, total165635frames unchanged, mean859497.191ticks. Independent naturalcampaign45424 authoritatively live and nowR6tick56000; lives[5,3,6,255], three active players, no fullclear yet. Candidate319384fe regressions launched: Normal401371, ordinaryR856225, chargedR838576, Home1261845, stack97299. Same immutable scratchROM, no promotion; production730ba901 unchanged. Long+solo comparisons are scene-state evidence, not wholecampaign video/hardware proof. Full objective remains incomplete.


Goal continuation 2026-10-06: previous turn progress (solo exact and regression launches). Naturalcampaign45424 polled live. Candidate319384fe R8ordinary56225/charge38576/Home61845/stack97299 terminal: state/replay matches, frames1262->1264 and1225->1226 respectively, all12modal paths pass, stack10716minimum gap/nooverlap bounded sample. Normal1371 terminal: all40state/renderhashes and timing exact,4P10102frames/errors[]. Started alignedRush76143 serially afterNormal. Read-only source-derived prototype .local/bc-contact-event-aligned-prototype tests two native longword reads with maskFFFF00FF under explicit even-address precondition;135168singlefield/combined-presence/value/even-address cases pass, sentinel/input preserved. Prototype does not change playableROM; any integration must explicitly align only private local records and retain public ABI. Current scratch319384fe immutable, production730ba901 unchanged, full objective incomplete.


Goal continuation 2026-10-06: previous turn progress (Normal40 exact, runtime comparisons, native aligned prototype). AlignedRush76143 terminal: all3001state/render hashes match retained730ba901,3010video frames unchanged. Launched legacyRush92493 serially as final MOVEPcandidate reader. Naturalcampaign45424 authoritatively polled live. Production unchanged; fullgoal incomplete.

Retained319384fe after all gates terminal. LegacyRush92493 matches all3000video hashes,2990updates,zero drops/remaps/wheelfallback,resetcleanuptrue. Production91239 terminal and exactcandidateSHA319384fe8b363aefdab8493ba59cf5b809e37ea2c06f0a8f2ff16e8a1c459288 verified. Onlysrc/bc_world.c promoted. Long4P12frames saved and worst2030->2028; solo total unchanged. Mixed costs explicitly retained: BC40+3frames, R8ordinary+2/charge+1, mean4Pprofile slightly higher. This is a small worst-window/video gain, not sustained fullspeed. All evidence consolidated verified.json; selected-candidate updated. Separate naturalcampaign atR7tick70000 lives3/1/5/255 remains running on itsown730ba901archive. Aligned-longword prototype remains private/unintegrated. Full objective incomplete.


Goal continuation 2026-10-06: previous turn progress (MOVEPcandidate319384fe fullyverified/promoted). Allpreviouscandidate readers terminal; independentnaturalcampaign45424 polled live. Newcandidate8eb5b2a15c5d7e13af4deb1e6bfebc3575e603b798c35cb876867d421935e2c9 explicitly aligns only the two private local contact records to2bytes, replaces MOVEP predicate loads with MOVE.L0/4 andFFFF00FF mask. Public BcActorEvent ABI/other records unchanged. Host32000contactcomparisons/6953orderedevents pass. Integrated helper passes135168nativefield/value/evenaddresscases with scoreIDexclusion andinput/sentinelpreservation. Build29206 terminal; fullarchive/nativeprobe/disassembly .local/bc-contact-event-aligned/candidate andparent. Long4P3131 andBC4032190 launched onimmutablecandidate. Production319384fe unchanged, performanceunproven, fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (alignedpredicate8eb5b2a1 built/host/nativeverified). Long4P3131 and naturalcampaign45424 confirmed live. BC4032190 terminal: noerrors/ROMchange, six improvements/no regressions against319384fe: R3/4P604->603,R6/4P838->837,R7/4P635->633,R8/3P614->613,R10/3P622->621,R10/4P654->652; net8frames saved. Solo11208/Normal4020168 launched plus R8/Home/stack gates. NaturalcampaignnowR8tick78000camera1757/1792,lives2/1/5/255, threeactiveplayers beyond priortrialR8scroll failures nearcamera1404; no clear claimed. Production319384fe unchanged; fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (BC40gain and regression launches). Naturalcampaign45424 authoritatively live, R8tick80000camera2080/1792 with lives2/1/5/255. Home95793/stack4611 terminal pass: all12paths,10716minimumgap/nooverlaps boundedroute. Long4P3131 completed after boundedwait: all87845statesmatch;126434->126412(-22)totalframes but worst1000window2028->2031(+3),mean1373780.31. Reject alignedvariant8eb5b2a1: small total gain does not justify worse slowest window for sustainedspeed objective. Requested interruption of remainingcandidate readers11208/20168/53183/61434; confirmterminal before restoring scratch. Production319384fe unchanged. Fullgoal incomplete.

Alignedvariant cleanup: remaining readers all terminal (solo11208 exit1 after interrupt, Normal20168 exit130; ordinary/chargedR8 terminal0). Restore7756 terminal exact retained319384fe SHA verified. No candidate readers remain; separate naturalcampaign continues.


Goal continuation 2026-10-06: previous turn progress (alignedpredicate rejected, exact319384fe restored). Separate naturalcampaign45424 polled live. New isolatedcandidate7da385023138023033c8f257bc774f5bd9e9ff4f79a41bfaafe9c9eb297f4d46 splits existing party_contact_scan immune/general bodies into separate noinline routines, selected by alwaysinline wrapper. Original flag decision,playerorder,contacts,clock increments/decrements,early exits andeventdelivery unchanged. Host32000comparisons/6953events pass. Native immune prologue saves8registers versus9prior, general saves10 (tradeoff; not assumed gain). Build36265 terminal; fullarchive/disassemblies .local/bc-contact-immune-split/candidate andparent. Long4P26949/BC4078753 launched againstimmutablescratch. Production319384fe untouched; sustained60FPS/fullnatural4Pclear remains incomplete.


Goal continuation 2026-10-06: previous turn progress (immune/general split candidate built/hostverified). Long4P26949 and independentnaturalcampaign45424 authoritatively live. Campaign nowR9tick88000 camera926/2048 lives0/0/3/255, confirming pilot passedR8 (not yet independent-replayverified orfullclear). Reviewed qa_bc_controller_replay endpoint/endingcontract and saved verification-plan.json undercampaign trial; wait terminalresult, useimmutable730ba901archive, no speculative restores in independentreplay. BC4078753 terminal: noerrors/ROMchange,net7frames saved withR4/3P+1,R8/4P+2 regressions, siximprovements. Solo62545 andNormal4074830 launched; performanceunproven,production319384fe unchanged, fullobjective incomplete.


Goal continuation 2026-10-06: previous turn progress (BC40 comparison and naturalR9 advance). Immune-split long26949/solo62545/Normal74830 confirmed live; R8ordinary66526/charged24142 launched. Natural45424 terminal0: status7 loss inR9tick96066,143643recorded gameplayvideo frames, no cheats/protection/forcedoutcomes. LasttwoP3deaths95469/95906 both near125,84 atcamera1536/2048, repeatedfourthboss bulletpattern. Launched independentcontroller replay97125 usingimmutable730ba901archive, no ending flag (notclear). Newnaturaltrial .local/bc-natural4p-r9-four-horizon12/build copiedsameimmutableROM; onlycontrollerR9boss4 horizon4->12 (template36be), R8scroll8/radius96 unchanged. RealHome4P7lives/continues andallpreviouspilotoptions retained; recordinginputs. Session12005running. This iscontrollersearch, noROMgameplaychange. Fullnaturalclear andfullspeed stillunverified.


Goal continuation 2026-10-06: previous turn progress (naturalR9failure analyzed, independentreplay97125 andnewpilot12005 launched). Bothnatural-related sessionsconfirmedlive. Immune-split long26949/solo62545/Normal74830/R866526/charge24142 terminal. All87845/160172canonicalstates match;4P126434->126526(+92),worst2028->2026(-2),mean1370796.672 improved;solo165635 andworst1402 unchanged. R8ordinary1264->1259,charge1226->1224,state/replayexact. Normal40allstate/render/timingexact. Mixed longgain/worseoverall requires investigation: savedroute-timing-blocks shows 60k-70kcost+96frames,earlierblocksmostlybetter. Started matchednewprofilestick60000/1000calls baseline62205 onarchived319384fe,candidate67241 onscratch7da38502. These are newproblem-windowprofiles, notduplicategates. StartedHome38404/stack94709/alignedRush95987;candidateunpromoted/immutable. Fullobjective incomplete.


Goal continuation 2026-10-06: previous turn progress (longmixedtiming analyzed,newproblemwindowprofiles). Baseline62205/candidate67241 andnewpilot12005 confirmedlive. Independentcontrollerreplay97125 terminal0:143643video-frame inputs replayed, zero save-state restores, endpointRAM157107a827774c79a59356e7222035b06ac0230eee1f2ac06d670aa67c702fca andrecordedCPU/video checkpoint match. VerifiednaturalR1-R8clear/R9loss, notfullclear/perframeRAM/video proof. Launched scene capture12239 onimmutable730ba901 archive toextend canonical regressioncorpus throughR8/R9. Immune-splitHome38404/stack94709/alignedRush95987 terminal: all12paths,10716gap/nooverlap,all3001state/renderhashesexact3010frames. LegacyRush82293 launchedserially. Production319384fe unchanged; candidate7da38502 undecided pendinglocalizedprofiles; fullgoal incomplete.

LegacyRush82293 terminal: all3000video hashes match retained,2990updates,zero sprite drops/remaps/wheelfallbacks,resetcleanuptrue. Onlymatchedtick60000profile readers remain forimmune-split decision.


Goal continuation 2026-10-06: previous turn progress (independentnaturalreplay verified, gates completed). Profile62205/67241 nowterminal afterboundedwait: tick60000baseline1561frames/904547.952mean vs split1571/905607.031, exactstates. Combinedcontactcallees8051358->7652624ticks improve398734 butbc_actor_common_into222473160->223949474(+1476314), outweighing savings. Prior split7da38502 rejected;allreadersterminal. Newvariant0ddf8e5ba15a550aac5b466217aa59963425aa5b8fc5ea3130c7ae71c38e1e0c marks only dispatchwrapper noinline, retainingtwo specializedscans andtheirsemantics; nativewrapper tailbranches butreloads/re-stores arguments. Host32000contactcomparisons pass;build56473terminal/fullarchive .local/bc-contact-split-dispatch/candidate. Tick60000replay36791 andBC4029819 running onimmutablecandidate, no speedclaim. Expandedcapture12239 andnewnaturalpilot12005 polledlive; independentarchivedbuilds unaffected. Production319384fe unchanged;fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (localizedprofile regression identified, noinline-dispatchvariantbuilt). Dispatchlong36791 andnewpilot12005confirmedlive;pilotR4tick28000matchespriorroutebeforeR9controllerchange. BC4029819 terminal: noerrors/ROMchange,net1frameworse vs319384fe;three regressions/twoimprovements archived. Expandedcapture12239 terminal:96088completedscenes/143643videoframes on730ba901;canonical record throughR8clear/R9loss ready. Started retained319384fe archived-build replay of newcorpus withR8tick80000profile. This expandsfidelityscope beyondolderR7clear route; no claimfullclear/fullRAM/perframevideo. Productionunchanged, fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (expandedcorpuscomplete/retainedreplaylaunched,dispatchBC40compared). Retainedexpanded2414 andnaturalpilot12005 authoritativelylive. Read-only matchedcallerhistograms saved .local/bc-contact-immune-split/caller-hotspots-tick60000.json andcaller-instruction-deltas.json: save/restoreticksidentical; branchform/layout shifts dominate callerregression. Dispatch36791 terminal:all87845statesmatch,126434->126613(+179),worst2028->2032(+4). Tick60000span1561->1566,mean904547.952->904840.391. Reject0ddf8e5b;allcandidate readers terminal. Restore59207 terminal exact319384fe SHA verified. Productionunchanged. Avoidassuming outlineddispatch fixes branchlayoutcost; full60FPS/fullnatural4Pclear incomplete.


Goal continuation 2026-10-06: previous turn progress (dispatchregressionrejected/exactrestore, branch-costevidence). Expandedretained2414 andnaturalpilot12005 confirmedlive. New native-only commonactor compilerlayout candidate414f841b0c94ea4d49dd1b4260557fe8a68b1432127e680215206e4c5648a5a9 changes existingO2 attribute toO2,reorder-blocks-algorithm=simple. SameClogic/contacts/motion/order; tests branchlayout evidence directly withoutsplittingcalls. Native common size1310->1240bytes(-70), runtimebenefitunproven. Build42728terminal;host27369terminal32000contactcomparisons pass. Fullarchive/commonassembly .local/bc-common-simple-layout/candidate andparent. Tick60000replay84655 andBC4015789 running onimmutablescratch; production319384fe unchanged. Fullobjective incomplete.


Goal continuation 2026-10-06: previous turn progress (simple-layoutcandidatebuilt/hostchecked). Simple-layout84655 andnaturalpilot12005 confirmedlive;84655 remainslive afterbounded45secondwait. BC4015789 terminal: noerrors/ROMchange,net19frames worse vs319384fe with7regressions/2improvements; longresultpending beforedisposition. Expandedretained2414 terminal:all96088canonicalstates match730ba901capture throughR8clear/R9loss;143647frames,newrouteworst1000window2023frames at81606..82606 (29.6589FPS), separateolderrouteworst2028 remainsvalid. R8profile80000mean1268513.715ticks/span1968;largestcosts player186188912/common172515616/partycontact149096444 ticks. Evidence eight-round-route/verification.json added toretainedverified.json. This expandsbehaviorcoverage, notfullclearorfullRAM/video proof. Production319384fe unchanged;goal incomplete.


Goal continuation 2026-10-06: previous turn progress (retainedexpanded96088statesverified,layoutBC40regressionmeasured). Simplelayout84655 terminal:all87845statesmatch but126434->126892(+458),worst2028->2031(+3),tick60000mean907378.178/span1584 vs904547.952/1561. Reject414f841b/allreadersterminal. Restore18372terminal exact319384feSHAverified. Naturalpilot12005 confirmedlive. NewR8matchingretainedinstructionaudit saved .local/bc-r8-current-review/party-hotspots.json andassembly toguide nexttarget. Reviewed priorplayercoordinatecache rejection (14801),do not repeat it. Productionunchanged; sustainedspeed/fullnatural4Pclear stillincomplete.


Goal continuation 2026-10-06: previous turn progress (simplelayoutrejected/restored andR8audit). Natural12005 confirmedlive. Reviewed pairedbodypredicate priorR2regression/solo-onlyretention17034..17075; not repeated. Distinctcandidate56fa4ad54cbd6e5b9c9afee60bdb6be0a268f2e79d8d859ee23c54f58a2a84db carries existing per-member body-impossibility intoactor_contacts bit2 ofprivatecontact_gate. Low2bits retain prior shotgate; general partycaller passes !body derivedfromexistingactor/partybodybounds/protection gates. Ifbodypossible, originalexactcontactcheck unchanged; unindexed/solo/immune callsites pass0 asbefore. Prevents redundantbodywork afterpossible shot contacts whenparty alreadyprovedbodyfar. Host32000cached/uncachedcomparisons/6953orderedevents pass,includingstate/clocks/pickups/death/bosshealth. Build30765terminal/fullarchive .local/bc-contact-body-prechecked/candidate. Long4P33786/BC407557 running immutablecandidate;production319384fe unchanged,fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (body-impossibility forwarding candidate built/hostchecked). Long4P33786 andnatural12005 authoritativelylive;naturalatR4tick36000lives6/2/6/0. BC407557 terminal:noerrors/ROMchange,5improvements/noregressions net7frames saved vs319384fe:R3/4P604->603,R7/4P635->633,R8/3P614->613,R10/3P622->621,R10/4P654->652. Launchedsolo60212 andexpandedR1-R8clear/R9loss replay72051 withR8tick80000profile, plusNormalmatrix. Thiscandidate must preserve new96088statecorpus aswellasolder87845route. Immutable56fa4ad5scratch/production319384fe unchanged;fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (BC40noregressiongain and expanded/solo/Normalreplays launched). Original long33786,solo60212,expanded72051,Normal21137,naturalpilot12005 all authoritatively polled live. Started remainingindependentHome19117,stack63864,ordinaryR861333,chargedR843713 againstsameimmutable56fa4ad5candidate. NoROMedits while readersrun; production319384fe unchanged. Currentturn advances requiredregressioncoverage whileverifiedlongrunscontinue;fullgoal incomplete.

Long33786 terminal:all87845canonicalstatesmatch,126434->126136(-298)frames,worst2028->2022(-6),mean1370321.351ticks (exact inlong-comparison.json). Both total and worst-window improve; pendingexpanded/solo/regression results stillrequired. This doesnotestablishfullspeed.


Goal continuation 2026-10-06: previous turn progress (long4P56fa4ad5 saves298frames/worst-6). Natural12005 polledlive. Home19117/stack63864/R861333/charge43713 terminal: all12modal paths pass,10700minimumgap/nooverlap, ordinary1264->1262 andcharge1226->1225 exactstates/replayverified. Solo60212/expanded72051/Normal21137 terminalafterboundedwait: all160172/96088statesmatch;solo165635->165664(+29),worst1402->1400,mean860172.033;expanded143647->143330(-317),worst2023->2021,mean1265282.431. Normal40state/render/timingallunchanged/errors[]. Solo+0.0175percenttotalcostexplicit;two4Pcorpora improve totalandworst. LaunchedalignedRush81458 serially afterNormal;legacyfollows. Production319384fe unchanged, candidateunpromoted,fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (expanded/solo/Normal/R8gates resolved;4Pgainswithsmallsologression). AlignedRush81458terminal:all3001state/renderhashesand3010framesexactretained319384fe. LegacyRush89693launchedserially asfinalcandidate reader. Naturalpilot12005authoritativelylive. Candidate56fa4ad5unpromoteduntilfinalvideo/cleanupgate;fullgoal incomplete.

Retained56fa4ad54cbd6e5b9c9afee60bdb6be0a268f2e79d8d859ee23c54f58a2a84db afterlegacyRush89693terminal:all3000video hashesexact,2990updates,zerodrops/remaps/wheelfallback/resetcleanuptrue. Onlysrc/bc_world.cpromoted;production32196terminal exactcandidateSHAverified. Allcandidate readersclosed/evidenceverified.json/selectedcandidateupdated. Two4Proutes save298/317frames,worst2028->2022/2023->2021;solo+29totalframesexplicit,worst1402->1400;Normal40unchanged. BC40net7savednoregressions;R8ordinary/charge-2/-1. Full60FPS/100%speed stillnotmet;naturalfull4Pclear remainsunverified. Independentpilot12005 currentlyR6tick58000 runsown730ba901archiveunmodified.


Goal continuation 2026-10-06: previous turn progress (bodyfarprecheck56fa4ad5fullyverified/promoted). Naturalpilot12005confirmedlive. Newcandidatee10cbf28ba2e7890ed8a40354c03c833be2e0e2a3ae0bd22cf4d3c3bf53f6418 extendsprivatecontact_gate bit3 for exactbody-near predicate already passed immediately. Immune party branch passes8 afterbody_near_inline; general branch passes8 only!shots&&body aftersamepredicate. Newshared enemy_player helper retainseligibility/options/pickup/death/cooldownrules; onlyduplicate exactdistance skippedwhennear, originalpublicAPI passes0. No changes to actualbounds,sourceorder,shots/motion/rendering. Host32000comparisons/6953orderedevents pass. Build39165terminal/fullarchive .local/bc-contact-body-near/candidate. Long4P79884/BC4078967 launchedimmutable;production56fa4ad5 unchanged. Full60FPS/fullnatural4Pclear remainsincomplete.


Goal continuation 2026-10-06: previous turn progress (body-near forwarding candidate built/hostverified). Long79884 andnaturalpilot12005 authoritativelylive. BC4078967terminal:noerrors/ROMmutation,all40timings unchanged vs56fa4ad5. NaturaltrialatR7tick74000camera2816/1536lives3/1/5/255. Launchedsolo76739 andexpandedroute63935 withR8tick80000profile onimmutablee10cbf28; latercontactheavyroute neededbeyondopeningmatrix. Production56fa4ad5 unchanged;fullgoal incomplete.


Goal continuation 2026-10-06: previous turn progress (BC40unchanged andsolo/expandedreplayslaunched). Solo76739/expanded63935/natural12005 authoritativelylive;naturalnowR8tick76000camera1154/1792lives2/1/5/255. StartedNormal54117 andR88062 immutablee10cbf28. Long79884terminalafterboundedwait:all87845statesmatch,126136->126138(+2),worst2022unchanged,mean1370995.85 vs1370321.351. No usefulgain in this route; pendingexpandedcorpus mattersbeforedecision. Production56fa4ad5unchanged;fullgoal incomplete.


Goal continuation 2026-10-06: preceding user-answer turn classified no progress toward implementation (read-only confirmation of known Normal4P timing). Revalidated scratch restore session35844 terminal success; scratch and production SHA both56fa4ad54cbd6e5b9c9afee60bdb6be0a268f2e79d8d859ee23c54f58a2a84db. Closed body-near forwarding e10cbf28 experiment: older4P +2frames; expanded +26/worst+2; solo+25/worst+2; R8+2; all compared canonical states preserved, BC40/Normal40 unchanged. Candidate rejected, all its readers terminal, original sources restored. Natural campaign12005 authoritatively polled live, nowR9 tick98000, last player has1life; horizon12 has extended beyond prior96066 loss but fullclear remains unproven. Next isolated experiment limits already-native solo body predicate to immune-party branch only; prior all-party substitution failed, so full-route gates remain mandatory.

Immune-party-only native body predicate candidate6a0cc4f68317439584688b9a5a6bee8e9b36c947d0a2057057692840b059e223 built successfully (70966 terminal). Only the immune branch body_near_inline call changes to existing native body_near_solo; general party/solo logic unchanged. Host contact stream83683 terminal pass. Full candidate archive in.local/bc-immune-native-near/candidate. Launched old4P65030 and BC4020815 against immutable scratch; production56fa4ad5 unchanged. Native helper itself is unchanged from previously verified endpoint/wrapped-radius routine. No speed improvement claimed before results.

Naturalpilot12005 now terminal exit0. Result reasonstatus_7 at tick99846/round9, gameplay endpoint147588video frames, RAMSHA83e34987c05e93b71515df07eba0143e766dd7a172f9a268069849daee7fc148; returned Home after gameover. Horizon12 extends survival3780updates pastprior96066loss but does not prove fullcampaign. Started independent controller replay on its immutable730ba901build without --verify-ending because run ended in loss. Fullgoal remains active/incomplete.


Goal continuation 2026-10-06: preceding turn progress (immune-only native body candidate built/hostverified, natural trial completed R9loss and independent replay launched). Long65030/replay82185 authoritatively live. BC4020815 terminal exit1 from speed misses, no measurement errors or ROM mutation. Comparison: {"changed": [], "net_frames_added": 0, "measurement_errors": false, "rom_changed": false}. Long route remains needed before acceptance/rejection; production56fa4ad5 unchanged.

Launched expanded R1-R8clear/R9loss canonical replay99210 (96088states) and full solo40092 (160172states) on immutable6a0cc4f6 candidate. Existing old4P65030 and independent natural replay82185 remain active. No ROM rebuild with readers active; no performance gain claimed.


Goal continuation 2026-10-06: preceding turn progress (BC40 candidate no-change result, solo/expanded replay launches). Long65030/expanded99210/solo40092 confirmed live. Natural independent replay82185 terminal exit0:147588frames, zero save-state restores, endpointRAM83e34987c05e93b71515df07eba0143e766dd7a172f9a268069849daee7fc148 and recorded machine checkpoint verified. This validates extended R9loss input route, not fullclear or per-frame video. Candidate6a0cc4f6 remains unpromoted; started Normal state/render matrix and R8 ordinary profile against immutable scratch. Fullgoal incomplete.

Read-only natural loss follow-up: final three deaths at ticks97383/98534/99685 recur at position64,195 with matching local actor arrangements. R9 repeated fourth-boss horizon12 currently lacks longest-survival tie-break (enabled only at repeated eighth boss). Saved next-controller-review.json as a concrete follow-up hypothesis, not a proven cause or implemented fix.


Goal continuation 2026-10-06: preceding turn progress (independent R9loss replay verified, Normal/R8 gates launched). Long65030 and R876653 terminal exit0; solo40092/expanded99210/Normal91125 authoritatively live. Candidate6a0cc4f6 older4P comparison {"states_match": true, "before_frames": 126136, "after_frames": 126107, "before_worst": 2022, "after_worst": 2022}; R8 {"states_match": true, "before_frames": 1262, "after_frames": 1262, "replay_verified": true}. Long gain29frames/worst unchanged supports continuing full regression checks, not promotion yet. Production56fa4ad5 unchanged; fullgoal incomplete.

Started Home12 gate19316 and stack94186 on immutable candidate. New natural4P trial61556 uses separate copied730ba901build at.local/bc-natural4p-r9-four-survival; sole controller change enables existing longest-survival tie-break for repeated fourth boss0x36be as well as eighth0x36c0 in R9. Retains horizon12/R8scroll8 and prior inputs elsewhere, real Home4P7lives/continues, no game-state seeding or ROM edits. This tests repeated death-pattern hypothesis; requires independent replay when terminal.


Goal continuation 2026-10-06: preceding turn progress (old4P/R8 resolved, Home/stack and natural trial launched). Expanded99210/solo40092/Normal91125/Home19316/stack94186 all terminal; natural61556 polled live. Expanded all96088states match143330->143312(-18) but worst2021->2024(+3). Solo all160172states exact165664frames/worst1400; Normal40state/render/timing exact/errors[]; Home12 allpass; stack10700gap/nooverlap. Reject6a0cc4f6 due worse slowest expandedwindow despite total gains; no Rushneeded after rejection. Allcandidate readers closed, restoring originalsrc/bc_world.c fromproduction56fa4ad5 and rebuilding scratch. Natural61556 independentimmutable730ba901 unaffected. Fullgoal incomplete.

Restore68613 terminal success; scratch ROM exact retained56fa4ad54cbd6e5b9c9afee60bdb6be0a268f2e79d8d859ee23c54f58a2a84db verified by SHA256. Candidate rejection closed; production unchanged.


Goal continuation 2026-10-06: preceding turn progress (immune-only candidate rejected on expanded worst-window regression; exact retained restore verified). Natural61556 authoritatively live. Reviewed current heavy R8 profile: indexscan45million attributed ticks/1000calls. New isolated scan predicate combines flags bit0 and coordinate-high bytes into one OR rejection; all28ascending state gates/index contents/count/bounds/radii unchanged, no extra registers. Prior registerbounds/adaptive/first-bounds proposals reviewed, not repeated. Native differential probe and build started; production56fa4ad5 unchanged.

Nativeprobe16832 terminal passes4096 completeindices, dirtypadding/fractions/highbytes/stateflags/radii, unchanged weapon bytes and sentinels. Build46867 terminal; candidate669f6c447417754341cad0af5995427510b8d4422109abc8c9f9d8042e6e536a archived fullsource/headers/tools/ROM/ELF. Long4P85934 and BC4057082 launched against immutable scratch. Probe7467frames is test-runtime only, not gameplay speed. Production56fa4ad5 unchanged; fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (combined index filter669f6c44 built/native4096 verified, long4P/BC40 launched). Long85934 and natural61556 authoritatively live, natural R3tick22000/lives6,5,5,7. BC4057082 terminal speed-miss exit1, no measurement errors or ROM change; changes versus56fa4ad5:R6/4P838->837,R8/3P613->614,R10/3P621->620, net1frame saved with mixed results. Started full solo and expanded4P canonical replays on immutable candidate to resolve workload-dependent performance and correctness. Production56fa4ad5 unchanged; fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (BC40 mixednet1saved resolved and fullsolo/expanded launched). Long85934/expanded98163/solo68926/natural61556 authoritatively polled live. Started Normal55883 and R8ordinary20952 on immutable669f6c44. Saved exact before/after bc_index_scan_regs disassembly/assembly-review.json to check native predicate emission; no ROM/source changes with active readers. Production56fa4ad5 unchanged, fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (native disassembly audited; Normal/R8 checks launched). Long85934/R820952 terminal; expanded98163/solo68926/Normal55883/natural61556 confirmed live. Results {"long": {"states_match": true, "before_frames": 126136, "after_frames": 126083, "before_worst": 2022, "after_worst": 2022}, "r8": {"states_match": true, "before_frames": 1262, "after_frames": 1260, "replay_verified": true, "scene_ticks": {"mean": 846663.104, "median": 837420.5, "p90": 968974.3, "p99": 1111030.76, "maximum": 1355662, "over_frame_budget": 256}}}. Fullgoal incomplete; production56fa4ad5 unchanged, candidate pending remaining results.

Started Home12 modal72978, stack78117 and charged R8 profile74033 against immutable669f6c44. Normal55883 remains prerequisite before serial Rush tests. Candidate unpromoted pending all relevant results; no fullspeed claim.


Goal continuation 2026-10-06: preceding turn progress (long4P53frame gain/R8twoframe gain resolved, remaining gates launched). Expanded98163/Normal55883/natural61556 confirmed live. Solo68926 terminal all160172states match but165664->165675(+11), worst1400 unchanged. Home72978 terminal all12pass; stack78117 terminal10700gap/nooverlap. ChargedR874033 terminal {"states_match": true, "before_frames": 1225, "after_frames": 1228, "replay_verified": true}. Candidate669f6c44 pending expanded results; small solo/charge costs explicit, production56fa4ad5 unchanged, fullgoal incomplete.

Expanded98163/Normal55883 terminal: expanded all96088states match143330->143310(-20),worst2021 unchanged; Normal40state/render/timing exact/errors[]. Both4P routes improve totals without worst-window regression, solo+11/charge+3 explicit. Started alignedRush serially afterNormal terminal; legacyvideo check follows. Natural61556 R4tick28000; fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (expanded4P20frame gain, solo+11/charge+3 and Normal40resolved, alignedRush launched). AlignedRush40637 terminal exit1 existing speed misses; all3001state/renderhashes exactly retained56fa4ad5,3010frames same. Natural61556 authoritatively live. Started legacyBossRush3000videoframe/cleanup check serially afteraligned terminal. Candidate669f6c44 unpromoted untilfinalgate;fullgoal incomplete.

LegacyRush6638 terminal:all3000videohashes exact,2990updates,zero sprite drops/remaps/wheelfallback,resetcleanup true. Allcandidate readers terminal beforepromotion. Promoted onlysrc/bc_rules.c union filter; production57356 terminal exact669f6c447417754341cad0af5995427510b8d4422109abc8c9f9d8042e6e536a verified. Retained both4P total gains53/20frames with worst2022/2021unchanged; solo+11/chargedR8+3 accepted explicit small costs,ordinaryR8-2,BC40net1savedmixed. Normal40exact,Home12pass,stack10700gap. verified.json/selectedmanifest updated. Natural61556 remains independent730ba901trial; full60FPS/fullnatural4Pclear incomplete.


Goal continuation 2026-10-06: preceding turn progress (union index669f6c44 promoted after allgates/exact production build). Natural61556 authoritatively live. Saved current retained R8player histogram/disassembly to.local/bc-player-retained-review; state/empty-span reads remain major player instructions. New isolated weapon traversal tests three-empty-slot span instead of six, preserving end guard, source order and reread of every live task; rendering unchanged. Prior logical-shortcircuit/sixspan/layout attempts reviewed and not repeated. Host differential/build started; production669f6c44 unchanged, fullgoal incomplete.

Host69639/build69051 terminal success; full differential166000cases pass. Candidate231f9918145a874698ce36e9470aa3f0ab606ba3b980a632dd04d3d9ac3b82df fullarchive retained. Started long4P67201 and BC4067646 on immutable scratch; production669f6c44 unchanged. No performance gain claimed before timings.


Goal continuation 2026-10-06: preceding turn progress (three-empty-span candidate built/166000hostcases passed and timing launched). Long67201/natural61556 authoritatively live; BC4067646 terminal noerrors/ROMchange but11regressions/zeroimprovements/net69extra frames (R4/4P+13,R6/4P+21,R8/4P+15). Rejected231f9918 without furthergates. SentSIGINT only verified candidate replayPID86275; session67201 terminal exit1, no completed longroute claim. Allcandidate readers closed before restoring src/bc_rules.c fromretained669f6c44 and rebuilding scratch. Natural61556 remainslive independent730ba901R4tick32000. Fullgoal incomplete.

Restore91297 terminal success; scratch exact retained669f6c447417754341cad0af5995427510b8d4422109abc8c9f9d8042e6e536a SHA verified. Three-slot trial closed; production unchanged.


Goal continuation 2026-10-06: preceding turn progress (three-slot scan rejected on11opening regressions, readerterminated and retained669f6c44 restoredexact). Natural61556 authoritatively live. Shifted current investigation to Normal4P slowest bounded section3 (1000updates/1038frames), within all-mode60FPSgoal. Started measured-update instruction profile with scheduler/workload/render tracing on retained immutable scratch; no source changes. This targets remaining regular-mode missedframes without reducing updates or rendering. Fullgoal incomplete.

Normalprofile55354 terminal exit1 existing speed miss: {"rom_sha256": "669f6c447417754341cad0af5995427510b8d4422109abc8c9f9d8042e6e536a", "frames": 1038, "updates": 1000, "work_over_budget": 17, "maximum_work_ticks": 1075795, "scope": "bounded protected section3, measured updates only; host hooks add no guest instructions"}. Saved matching retained native disassemblies and instruction attribution for enemy update_all.lto_priv.0, spr_shots and weapons_fire. VBlankwait298975488ticks is idlewait, not optimization workload; active top costs enemyupdate118991054,shotrender77534310,weapons55682620. No code/ROM change; this identifies measured regular4P workload for next candidate.


Goal continuation 2026-10-06: preceding turn progress (Normal4Psection3 measurement/profile completed,17overbudget updates identified). Natural61556 authoritativelylive. New scratch-only Normal spr_shots capacity candidate keeps remaining capacity locally, decremented only after successful original emit; count is still updated by emit and clipping precedes drop accounting. Reviewed lookup/lookup_slow/small_miss: no count changes, only cache/budget/upload operations. Original active/coordinate/key/miss/emission order unchanged; zero capacity clamps count>=MAX_SPR. Build and measured section3 comparison next; production669f6c44 unchanged/fullgoal incomplete.

Build1764 terminal, candidate9054b552efb6b7695a979dc040d400e672c24641ded7fa7c93b29b247e4eab23 fullarchive saved. Section3 measured profile/render/state replay35891 launched on immutable scratch; baseline.local/normal-section3-retained-profile. No speed claim before comparison.

Section3 35891 terminal: all1001state/render hashes match, but1038->1039frames and shotrenderer77534310->79797914ticks(+2.92%). Reject9054b552 without broadergates; allreaders terminal before source restore/rebuild.

Restore51772 terminal; scratch SHA exact retained669f6c44 verified. Production unchanged; candidate closed.


Goal continuation 2026-10-06: preceding turn progress (localcapacity candidate rejected after exact state/render comparison and restored669f6c44). Natural61556 authoritatively polledlive. New isolated spr_shots usesu16 for already-maskedcolour0..15 instead ofu8, to test removal of redundant byteextension before key rotation; actual value/range/API and allrenderlogic unchanged. Build/disassembly/section3 gate next, production669f6c44 unchanged. Fullgoal incomplete.

Colourword build29629 terminal byte-identical retained669f6c44. Rejected no-op without redundant gameplay tests; original source restored.

Read-only follow-up mapped retained Normal weapons_fire hotspot to upd_linear active-state loop (MOVE.B2.605m,empty BEQ2.467m,loopBNE1.926m,CMP1.737m ticks in sample). Prior AUTO8/9fixedendpoint optimization already retained; not repeated. Saved weapon-loop-review.json for next distinct loop-layout test. No source/ROM changes remain this turn.


Goal continuation 2026-10-06: preceding turn progress (colourword compiled to identical ROM and rejected; mapped Normalweaponloop hotspot). Natural61556 authoritativelylive. New isolated upd_linear branchhint active==1 likely, affecting native layout only: allslotranges/motion/explosion/sourceorder unchanged. Prior BCweaponloop layout differs and is not repeated here. Building candidate forsection3state/render/measuredCPU gate; production669f6c44 unchanged/fullgoal incomplete.

Build43900 terminal candidate80b3a865 fullarchive/assembly. Section3 37107 terminal: all1001state/renderhashes exact and1038frames unchanged, weapons_fire55682620->57479240ticks(+3.23%). Rejected branchhint without broadergates; allreaders closed before restoring weapons.c/rebuilding. Production669f6c44 unchanged.

Restore79038 terminal; scratch SHA exact669f6c44 retained verified. Candidate closed; fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (Normalweaponbranchhint rejected/restoredexact669f6c44). Natural61556 authoritativelylive. Reviewed earlier paritycache rejectionf7513bd2: small Normalgains, but frame102 fourpixel HUD/star mismatch, identicalVRAM/CRAM/SAT. Since then retained nativeHUDrowmask/timing and atomicDMAfix changed the relevant display path. Re-testing same narrowly scoped paritypass oncurrent669f6c44, explicitly because premisechanged; diffagainstcurrentenemies.c contains onlyodd parameter/once-per-pass snapshot, combined stillreadpercollision. Originalframe/collisionorder unchanged. Firstgate is previouslyfailing3000frameRushvideo, then broaderchecks ifpasses. Productionunchanged/fullgoal incomplete.

Build58564 terminal candidatec4e0cb99a454d619f3f1c03ac4560ec4dfaa82d01e9b25e8d493eac799e2c1d2 archived. Rush31359 terminal:all3000videohashes match currentretained669f6c44,2990updates,zero drops/remaps/wheelfallback,resetcleanup true. Earlier frame102 mismatch doesnotrecur oncurrentHUD/DMA baseline; no inference that oldcause conclusivelyproved. Started Normal40state/render44314 serially afterRush and BC4020718 independently. Candidateunpromotedpendingtiming/fidelitygates;productionunchanged/fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (retested paritycache now passes previouslyfailingRush3000video gate; Normal/BC matrices launched). Normal44314/natural61556 authoritativelylive; naturalR7tick64000lives5/2/6/255. BC4020718 terminal:noerrors/ROMchange,all40timings unchanged vs669f6c44. Launched long4P1207/solo73052/Home1279098 on immutablec4e0cb99; NormalmustfinishbeforealignedRush/vulnerableNormal sharedoffsetgates. Production669f6c44 unchanged; fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (BC40unchanged, long/solo/Homegates launched). Normal44314/long1207/solo73052/natural61556 confirmedlive; Home79098terminal all12modal/cancel/launchpaths pass. NaturalR7tick68000lives5/2/6/255. Started expanded4P canonicalreplay and boundedstack onimmutablec4e0cb99. Independentread-only BC/Normal hotspotreviews delegated now that proactive delegation is enabled; reviewers forbidden source/ROM mutations/sharedQA launches. Production669f6c44 unchanged, fullgoal incomplete.

Normal44314 nowterminal:all40state/render comparisonsmatch/errors[], no timingregressions;4Psection7 1014->1012,section8 1022->1021,total10102->10099,worstsection3still1038. Started serial currentretained/candidate vulnerable4Psection3 3000update comparison before alignedRush (sharedoffsettools serialized). SmallmeasuredNormalgainmerits remaininggates; no fullspeed claim.

Vulnerable59397 serialpair terminal:all3001state/renderhashes match,3050->3049frames. Stack64286 terminal10700gap/nooverlap. Old4P1207/solo73052 terminal: {"natural4p-r2": {"states_match": true, "before_frames": 126083, "after_frames": 126083, "before_worst": 2022, "after_worst": 2022}, "solo": {"states_match": true, "before_frames": 165675, "after_frames": 165675, "before_worst": 1400, "after_worst": 1400}}. Started alignedRush aftersharedoffsetvulnerablejobs closed; expanded77359stillpending. Candidateunpromoted/fullgoal incomplete.

AlignedRush35602 terminal: {"state_hashes_match": true, "render_hashes_match": true, "before_frames": 3010, "after_frames": 3010, "hash_count": 3001}. Expanded77359 confirmedlive; scratch remainsimmutable. IndependentNormalreview identified branchless en_y_from_arcade mapping as next nonduplicate arithmetic candidate; exhaustive proof preparation is isolated from production/scratch.


Goal continuation 2026-10-06: preceding turn progress (Normalmatrix/vulnerable gains resolved, allothergatesexceptexpanded complete). Expanded77359 terminal all96088canonicalstatesexact143310frames/worst2021 unchanged; allcandidate readers nowclosed. Natural61556 authoritativelyliveR8tick78000. Paritycachec4e0cb99 passes previouslyfailingRushvideo withcurrentHUD/DMAfix, Normal40noregression4Ptotal10099(-3),vulnerable3049(-1),allBCroute/framecountsunchanged,Home12/stackpass. Promoted onlysrc/enemies.c and startedproductionbuild; exactROMhashverificationrequired before retainedmanifest update. Fullgoal incomplete.

Production60924 terminal exact testedc4e0cb99a454d619f3f1c03ac4560ec4dfaa82d01e9b25e8d493eac799e2c1d2 verified; retainedmanifest updated. Normal4P10000updates/10099frames=59.411823FPS aggregate; slowestsection3 remains57.803468FPS/1000update sample. BCworstwindows2022/2021 unchanged. This completes paritycache optimization, not fullgoal.

IndependentNormal review isolatedproof passes all256Yinputs×64repeats; exact branchlessmapping(s16)(u8)(ay+8)-24 equivalent to original piecewise mapping. Noinline helper26->16bytes/433.5625->336mean coreticks, notcaller/game speed. New scratchcandidate changes onlysrc/enemy_int.h helper after allpreviousreaders terminal; basedonretainedc4e0cb99. Productionunchanged; section3/render/state/nativecallsite inspection gates next.

Ywrapbuild13308 terminal49abd4dd0cd3133a7934d92e305d272bce98094efa601df5cdcc1c3c00426b27 fullarchive saved. Candidate section351467 terminal all1001state/renderhashes exact,1038frames unchanged. Started matched retainedc4e0cb99section3CPUprofile using immutablearchive aftercandidateprofile terminal; current669fprofile predatesparity so notusedfornetCPUclaim. Fullgoal incomplete.

Matchedbaseline73408 terminal: enemyupdate118627628->117573652ticks(-1053976,~0.89% of enemyupdate),weapons55682620/shotrenderer77534310exact. Both1038frames/allstate-renderhashesmatch. Native arithmetic proofplusactualCPUgain justify Normal40/BC40 matrices nowlaunched; candidateunpromoted untilbroadergates.


Goal continuation 2026-10-06: preceding turn progress (parityc4e promoted exact, branchlessY49abd built/nativeproof/section3CPUgain verified and matrices launched). Normal70207/natural61556 authoritativelylive; naturalR9tick90000lives0/0/3/255 (zero lives still active). BC4080347 terminal:noerrors/ROMchange,all40timings unchanged. Started long4P/solo replaygates on immutable49abd. IndependentNormalagent inspecting native small/bigmovement folds with matching49abd/c4earchives; BCagentquantifies structural ABIopportunity. Productionc4e unchanged/fullgoal incomplete.

Normal70207 terminal:noerrors,all40state/renderhashesexactandalltimingsunchanged,total4P10099. Independent nativecallsite review found small/item move path losesproved-rangefold underglobalYrewrite: localnormalizationcosts307720vs175840ticks(+131880),whilebiglocalblocks save953456ticks. Prepare explicit oldsmallconversion/newbigmapping follow-up aftercurrentreaders close; no extra globalYgates launchedwhilebettervariantprepared. Currentcandidateunpromoted,productionc4e unchanged.


Goal continuation 2026-10-06: preceding turn progress (Normal49abd matrixexact, smallpathmissedfoldidentified). Long20613/solo44689terminal:all87845/160172states match and exact126083/165675frames; globalYcandidate superseded bysamebranchlesshelperplus explicitsmallnormalization, allreaders closedbeforeedit. New scratchonlyenemies.c keepssmall ry-16 afterretirementprovesry<241, biguseshelper; nobehavior change. Natural61556 terminalR9loss tick99915/video147658, RAMcbeeb1508ab6dea90eb4564df4b3e19299ff4cae3fce618e96b9a58288c930c5,returnedHome. Tie-break66changes/72alldirectionsdie/7058calls gains69updatesoverpriortrial, nofullclear. Independentcontrollerreplay81988 started immutablearchived730ba901 withoutendingflag. Controllerstrategyreviewdelegatedread-only. Productionc4eunchanged/fullgoal incomplete.

Small-specializedbuild32098 terminal7f75d931cf54a735810d9ea9b322ade3e38e7549ab02309a6aeb1d9e71a0657b archived. Section316322 terminal all1001state/renderhashesexact1038frames; enemyupdate118627628->117188260ticks(-1439368/~1.21%). Betterthan globalY117573652,still nosection3framegain. StartedNormal40/BC40 onimmutablecandidate. BCcontactdescriptorprototype authorizedonlyisolated.local directory, hostbehaviorproof first; no production/scratch changes byagent. Fullgoal incomplete.

Natural independentreplay81988 terminal exit0:147658videoframes,zero save-state restores, endpointRAMcbeeb1508ab6dea90eb4564df4b3e19299ff4cae3fce618e96b9a58288c930c5 and machinecheckpointverified. Validates R9loss, notfullclear/per-framevideo. Controllerreview found suspected alternate-move rapidfire-phase return mismatch; isolatedregressionproof beingpreparedbeforefix, no change to gameROM.


Goal continuation 2026-10-06: preceding turn progress (globalYsuperseded; specialized7f75section3CPUgain verified/matrices launched; naturalR9loss independentlyreplayed). Normal44282 authoritativelylive; BC4098516terminal all40timingsunchanged/noerrors/ROMchange. Controllerproof216cases identifies46originalfiremismatches; all108rapid-disabledcases identical, direction/shadowsequence/statistics/liveRAMunchanged. Fixedroottools/bc_pilot_lookahead.py finalselectedreturn to preserve proposedfirstfirebits; addedtools/qa_bc_pilot_selection.py contractregression216cases(pass), strengthenedactualcoreqa_bc_pilot_fire.py selectedfireassertion. Actualcoreteststarted againstunchangedproductionc4e. No gameROM or previousarchivedtrialmodified. BCdescriptorprototype remains isolatedagentwork. Fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (first-action controller fix passed synthetic216/native24 cases; specialized Y matrices completed and three long replays launched). Current production ROM SHA verified exact c4e0cb99. Regular 4P measured10000 updates over10099 video frames =59.411823FPS; slowest tested1000-update section is section3,1038 frames =57.803468FPS. These are bounded sample rates, not instantaneous minima or full-game full-speed proof. Natural72375 authoritatively live, R3/tick16000. Long72088/solo55610/expanded85456 terminal with results {"natural4p-r2": {"states_match": true, "states": 87845, "before_frames": 126083, "after_frames": 126083, "before_worst": 2022, "after_worst": 2022}, "solo": {"states_match": true, "states": 160172, "before_frames": 165675, "after_frames": 165675, "before_worst": 1400, "after_worst": 1400}, "eight-round-route": {"states_match": true, "states": 96088, "before_frames": 143310, "after_frames": 143310, "before_worst": 2021, "after_worst": 2021}}. Remaining candidate fidelity gates next; production unchanged/full goal incomplete.

Started remaining candidate gates on immutable7f75d931: alignedRush57185, Home12 72157, stack48375. Shared-offset legacyRush/vulnerableNormal must wait for alignedRush to terminate. No new frame-rate gain is claimed; productionc4e0cb99 remains selected.


Goal continuation 2026-10-06: preceding turn progress (three long canonical replays completed unchanged, remaining Home/stack/alignedRush launched and current regular4P figures verified). AlignedRush57185,Home72157,stack48375 now terminal. Results {"rush_aligned": {"state_hashes_match": true, "render_hashes_match": true, "before_frames": 3010, "after_frames": 3010, "hash_count": 3001}, "home12": {"cases": 12, "all_pass": true}, "stack": {"lowest_sp": 16775320, "lowest_pc": 151466, "lowest_tick": 2080, "minimum_gap": 10700, "gap_sp": 16775320, "gap_end": 16764620, "gap_pc": 151466, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82328420}}. Natural72375 authoritatively live. Legacy video Rush and vulnerable Normal checks remain before candidate promotion; productionc4e unchanged/fullgoal incomplete.

Specialized Y remaining gates terminal: legacyRush87295 all3000 video hashes exact/2990updates/zero drops-remaps-fallback/resetcleanup true; vulnerableNormal22425 all3001state/render hashes exact and3049->3044 video frames. All candidate readers closed. Retaining the native enemy mapping CPU gain plus five-frame vulnerable-sample gain; promoted onlysrc/enemies.c andsrc/enemy_int.h, production build next. Normal40/BC40 totals and all BC long rates remain unchanged; no sustained60FPS claim.

Productionbuild80760 terminal: exact tested7f75d931cf54a735810d9ea9b322ade3e38e7549ab02309a6aeb1d9e71a0657b SHA verified. Specialized Y conversion now retained; manifest updated. BC descriptor prototype host differential now passes author tests, pending independent review/native build and full timing gates. Natural trial remains independent on archived730ba901. Full goal incomplete.

BCcontactdescriptor prototype staged only in scratch after all Normal7f75 readers closed and production SHA confirmed. Author host proof:32000prepared+32000fallback contacts,2012frozen-pass sequences/32024actor updates,576six-round segment births,party-frame/routing/early-exit checks. Independent read-only review found no actionable mismatch. Compact source-ordered contact records retain living count and immediately clear body eligibility on option absorption or tombstone deaths; original fallback remains outside actor pass. Native build/layout/stack/replay/timing unverified. Production7f75 unchanged/fullgoal incomplete.

NativeBCdescriptor build51547 terminal SHAe66dd6c66dfdb695770a5db987d6bed470caeb0dda342831ab63aa7e77e045a3/4MiB archived. BC40 40590 terminal:noerrors/ROMchange,net63 additional frames,12 regressions/1improvement, largestR6/4P837->854,R8/4P739->751,R4/4P872->883. Stack29208 terminal10616bytegap/nooverlap. Natural-route30339 still authoritativelylive; its vulnerable workload must resolve before disposition. Expanded4P and solo canonical comparisons also launched. Production7f75 unchanged; candidateunpromoted/fullgoal incomplete.

Descriptor long4P30339 terminal: all87845canonical states exact but126083->127591video frames(+1508),worst1000window2022->2030; R2scene mean1370065.536->1380388.926ticks. Rejecte66dd6c6 for performance; expanded3734/solo73157 stilllive before restore. Native inspection identifies preparation inlined/unrolled (party_actor_loop744->1832bytes/frame380->444),more saved registers, and mutation guard overhead even after no-touch body checks. Host equality did not predict CPU benefit. Next independent Normal candidate retains actual SAT count/cursor locally per shotbatch;122576sanitized extracted-loop cases pass and native object removes repeated global count/address work, actualgame timing still untested. Production7f75 unchanged.

All descriptor readers now terminal. Additional route results {"natural4p-r2": {"states_match": true, "states": 87845, "before_frames": 126083, "after_frames": 127591, "before_worst": 2022, "after_worst": 2030}, "eight-round-route": {"states_match": true, "states": 96088, "before_frames": 143310, "after_frames": 144466, "before_worst": 2021, "after_worst": 2022}, "solo": {"states_match": true, "states": 160172, "before_frames": 165675, "after_frames": 165634, "before_worst": 1400, "after_worst": 1400}}. Candidate rejected; restored only staged source/header/test copies from current production7f75, removed isolated new-test copy, restoring native build next. Production remainsunchanged.

Descriptor restore86883 terminal; scratch ROM exactretained7f75 verified. New isolated Normal shot-batch cursor candidate changes onlysrc/sprites.c: local actualsubmitted count and SAT destination, original clipping/cache/miss/drop/emission order, globalcount published onreturn. Unlike rejectedremainingcapacity experiment, genericemit bookkeeping is removed. Read-only callgraph/interruptaudit supports countvisibility;122576sanitizedhostcases compare SAT/count/drops/helperorder; nativeobject removes repeatedmemorycount andSATrescale. Nativegamebuild/section3LTOmeasurement next; noFPSclaim. Natural72375 authoritativelylive onitsownarchive.

Shotbatchcursor build66237 terminal candidate14feadb1f7fc2883be04179e7f69fedbc48b5cb58829fccfae6280358dca0c41/fullarchive. Section328424 terminal: all1001state/renderhashes exact,1038->1034frames; shotrender77534310->73745294ticks(-3789016/~4.89%). ActualLTO disassembly preserves count in d5/SATcursor in a3 withoneentryload/oneexitstore, no repeatedin-loop globalcount/addressreconstruction. Launched Normal40state/render and BC40 plus long4P/solo gates onimmutablecandidate. Production7f75 unchanged pendingbroadvalidation; fullgoal incomplete.


Goal continuation 2026-10-06: preceding turn progress (specializedY7f75 retained afterallgates; BCdescriptore66 rejectedonactualroute slowdown/restored; Normalshotcursor14fe section3improves4frames/~4.89%shotCPU with exact hashes andbroadgates launched). Normal8969/long47783/solo29201/natural72375 authoritativelylive. BC4089734 terminal: {"errors": false, "rom_changed": false, "changes": []}. Launching expanded4P/Home12/stack onimmutable14fe candidate; Normalmatrix mustfinishbefore sharedoffsetRush/vulnerablechecks. Production7f75 unchanged/fullgoal incomplete.

Normal8969 terminal: all40state/render hashesexact/noerrors/noregressions,4Ptotal10099->10088,mean59.476606FPS,worstsection31034frames. Improved4Psections3(-4),5(-1),6(-1),7(-1),8(-3),9(-1). Othercompletedgates {"natural4p-r2": {"states_match": true, "states": 87845, "before_frames": 126083, "after_frames": 126083, "before_worst": 2022, "after_worst": 2022}, "solo": {"states_match": true, "states": 160172, "before_frames": 165675, "after_frames": 165675, "before_worst": 1400, "after_worst": 1400}, "home12": {"cases": 12, "all_pass": true}, "stack": {"lowest_sp": 16775320, "lowest_pc": 151466, "lowest_tick": 2080, "minimum_gap": 10700, "gap_sp": 16775320, "gap_end": 16764620, "gap_pc": 151466, "gap_tick": 2080, "overlap_samples": 0, "sampled_boundaries": 82328420}}. LegacyRush8846 startedafterNormalmatrixclosed; expanded39727 remainslive. Production7f75 unchanged untilremaininggatescomplete.

Shotbatch finalgates terminal: expanded39727 all96088states exact143310frames/worst2021; legacyRush8846 all3000videohashes exact2990updates/zeroissues/resetcleanuptrue; alignedRush56884 all3001state/render exact3010->3011frames(+1); vulnerable62924 {"state_hashes_match": true, "render_hashes_match": true, "before_frames": 3044, "after_frames": 3039, "hash_count": 3001}. Retain measuredNormal4Pgain10099->10088 andshotCPUgain, accepting explicitone-frame alignedRushcost; legacyvideorate unchanged. Allcandidate readersclosed beforepromoting onlysrc/sprites.c. Productionbuildnext/exacthashrequired; no sustained60FPSclaim. Natural72375 authoritativelyliveR7tick72000 withtwoactiveplayers.

Production34095 terminal/exact tested14feadb1 SHA verified; shot-batch count/cursor now retained andselectedmanifestupdated. CurrentNormal4P boundedmean59.476606FPS/worst58.027079FPS. New scratch-only BCno-contact-return candidate adds earlyreturn0 afterbc_enemy_player confirms no bodytouch; allfourprivatecallers supply zeroevent, shots alreadyprocessed, depletion returnsbeforebranch andcallers retaindamagelocktick. 55264 independenthostcomparisons pass; exactoldsourcehashcheckedbeforestaging. Nativebuild/realLTOtimingnext, notdescriptorarchitecture. Production14feunchanged/fullgoal incomplete.

BCno-contact native build81769 terminal SHA1d3dead522da86c39fc447f20d6cd72db137becfd611bb79ec54008f0d88f505 archived. Long4P16463 and BC408857 running onimmutablecandidate. Next separate Normalcandidate is preparedonlyunder.local/normal-independent-review/after-shot-count: dynamic spr_32 palette rotate, constantfoldingpreserved; object/hostproof passed butactualLTO timing untested. Production14fe remainsselected.

BCno-contact BC408857 terminal:noerrors/ROMmutation,all40timingsunchanged. Long16463 confirmedlive. Expanded4P andsolo canonical replays launched onimmutable1d3dead5 to resolve actualroute/worst-window effects; production14fe unchanged.


Goal continuation 2026-10-06: preceding turn progress (shotcursor14fe passedbroadgates andretainedexact; BCno-contactreturn1d3dead5 built/BC40unchanged andlongreplays launched). Long16463 terminal {"states_match": true, "states": 87845, "before_frames": 126083, "after_frames": 126091, "before_worst": 2022, "after_worst": 2022, "before_profile": 1370065.536, "after_profile": 1368882.172}. Expanded75696/solo84143/natural72375 authoritativelylive. Candidateunpromoted untilremainingresultsresolve; production14fe unchanged/fullgoal incomplete.

BCno-contact remainingroutes terminal: {"natural4p-r2": {"states_match": true, "states": 87845, "before_frames": 126083, "after_frames": 126091, "before_worst": 2022, "after_worst": 2022}, "eight-round-route": {"states_match": true, "states": 96088, "before_frames": 143310, "after_frames": 143302, "before_worst": 2021, "after_worst": 2021}, "solo": {"states_match": true, "states": 160172, "before_frames": 165675, "after_frames": 165621, "before_worst": 1400, "after_worst": 1394}}. Combined4Proute totals balance(+8older/-8expanded), bothworstwindows unchanged; solo saves54frames andworst1000window1400->1394. Allcanonicalstatesexact. Continuefinalgates forsolo/nativeCPUimprovement, explicitlynot a4Pframerate gain. Naturaltrial stillrunning butR7camera2384 appearsstalled; read-onlycontroller/progressiondiagnosis delegated, no restart/livearchiveedits.

Natural72375 nowterminal:update_limit220000/R7, endpoint263948videoframes/RAMc673f9aa1238c6c64db412b6df762188d721fbdc371a6466c74de9f810175f70. Independentcontrollerreplay4458 startedwithoutendingflag; read-onlyendpointdiagnosis delegated beforeanynewtrial. Nofullclear/returnclaim. BCno-contact Normal38366terminal all40state/renderhashesexactandalltimingsunchanged,total4P10088. Home63465all12pass; stack85432gap10700/nooverlap; matchedR8charge64515/62765 allstatehashesexact/replayverified/1228frames and760007.367meancoreticks unchanged. LegacyRush80417runningseriallyaftermatrix.

BCno-contact finalgates complete: legacyRush80417all3000videohashesexact2990updates/zeroissues/resetcleanup; aligned38626all3001state/renderexact3011framesunchanged; vulnerable1062all3001state/renderexact3039framesunchanged. Allcandidate readersclosed. Retaining3lineearlyreturn forsolo54frames/worst1400->1394 andmeasuredR2CPUgain; explicit4Polder+8/expanded-8tradeoff,worstunchanged. Promotedonlysrc/bc_world.c; productionbuild/exacthashnext. Naturalindependentreplay4458 terminal263948frames/0restores/endpointRAM+machinecheckpointverified; verifiesR7stall, notclear/perframevideo.


### 2026-10-06 — Shared-engine requirement; prior candidate disposition

The preceding no-contact early-return candidate is retained as a verified baseline, not a 4P performance solution. Production build session 37319 completed and its ROM SHA-256 is `1d3dead522da86c39fc447f20d6cd72db137becfd611bb79ec54008f0d88f505`, exactly matching the tested candidate. The old 4P route adds eight video frames; the expanded route saves eight; their worst 1,000-update windows remain 2,022 and 2,021 frames. Solo saves 54 frames and improves its worst window from 1,400 to 1,394. Normal's 4P matrix remains 10,088 video frames for 10,000 updates (59.48 FPS aggregate; worst sampled section 58.03 FPS). Canonical state, render, Home modal, stack, and Boss Rush checks are recorded in `.local/bc-no-contact-return-native/verified.json`. The 60 FPS goal remains unmet.

The user's architecture correction now takes priority: BC must be a mode of the regular engine, with matching existing graphics reused and genuinely new tiles/enemies remastered. Inspection confirms the current implementation is native but separate: `main.c` intercepts BC before `game_update`/`game_draw`; BC owns separate players, actors, waves, and contact processing. Sharing the low-level sprite/background backend alone does not satisfy this requirement. Further isolated BC microoptimizations are paused in favor of real shared engine integration, while preserving BC behavior with the existing canonical replay oracles.

The latest natural 4P trial's R7 endpoint is a controller-navigation limitation: an independently replayed, input-only 29-update detour reaches the release position, releases the stalled groups, and resumes the script/camera. This proves reachability, not survival or a completed 4P campaign. Evidence remains isolated in `.local/bc-natural4p-first-action-review/`; original recordings are unchanged.


### 2026-10-06 — First shared enemy-engine subsystem retained

Classification: architectural integration, not a completed same-engine port or FPS optimization. The regular enemy engine now owns one typed 2,880-byte arena used by both Normal and BC, replacing BC's separate 1,728-byte actor allocation. Normal's 40-byte and BC's 54-byte records retain their layouts and slot order. Both modes use the same free-slot allocator. Normal boss/effect/pool state is cleared before BC adopts the arena; Normal pool metadata and records are reset on exit. The separate BC update/collision/player/weapon loops remain to be migrated; `docs/bc-shared-engine.md` records the remaining work.

Production build 9837 completed with SHA-256 `7a115b005e06b0646113335e2c6581cd44ef4c3cc5cd75b4413d954425a1d527`, exactly matching the immutable tested candidate. Evidence: `.local/bc-shared-enemy-engine/verified.json`. Independent review found no introduced ownership/ordering/type blocker and verified all native debugger aliases. Sanitized host allocation tests passed 360,000 cases. Native tests passed 12 entry/exit/reentry cases and populated Normal → BC → Rush → BC → Normal handoffs. The handoff test initially assumed the Home cursor reset; fixing that test assumption made the real menu-driven restart check pass without a ROM change.

All 344,105 canonical BC states across the retained three routes match: 87,845 old 4P states, 96,088 expanded 4P states and 160,172 solo states. Timing tradeoffs are recorded rather than hidden: old 4P 126,091→126,163 video frames (worst 1,000-update window unchanged at 2,022); expanded 4P 143,302→143,304 (worst 2,021→2,023); solo 165,621→165,627 (worst 1,394→1,397). This slice is retained for genuine storage/allocator integration, not a speed gain. Normal's 40 samples have identical state/render hashes; aggregate 4P improves by one video frame (10,088→10,087). Vulnerable Normal retains all 3,001 state/render hashes with 3,039→3,042 frames. Both Rush gates match (3,000 raster frames in the video gate; 3,001 state/render hashes in the aligned gate), with unchanged timing and clean reset. Home's 12 modal/launch paths pass. R8 charge's 1,000 state hashes match with 1,228→1,224 frames; stack/heap minimum gap is 12,556 bytes with no overlaps. The 60 FPS / 100% speed requirement remains unmet.

Asset matching is now grounded in a ten-round inventory, not assumed from old manual mappings: `.local/bc-asset-matching-review/match-inventory.json` covers 689 source background IDs with 50 original/Normal/current-BC atlas pages; `enemies/manifest.json` covers 45 source sprite-base IDs. Round-1 cells 0x21 and 0x3A have demonstrated rock-shape/orientation substitutions. No nearest-neighbor result has been falsely promoted to a verified match. Existing boss drafts also need silhouette/pose review; nine banks currently derive from only three Normal shapes. Remastering must use the actual Genesis palette allocation, not an assumed expanded simultaneous palette.


### 2026-10-06 — Shared-pass migration continuation

Previous goal turn classification: **progress**. It changed authoritative source state by sharing the enemy arena and allocator, and verified gameplay-state/render parity, mode transitions and native memory savings. Current production ROM revalidated as `7a115b005e06b0646113335e2c6581cd44ef4c3cc5cd75b4413d954425a1d527`; the prior native QA/build jobs are terminal. The next step is replacing duplicate actor scans with a common engine iteration primitive, followed by collision and frame ownership migration. The full objective, source fidelity, matching/remastering requirement and sustained 60 FPS remain unchanged and incomplete.


Shared-pass first prototype rejected: native SHA `7c4e5834e655d380d84b519a2953c1c6a0a1926ad12fbf929334a7de74a0d581` preserves 87,845 old 4P and 160,172 solo canonical states and all Normal40 state/render hashes, but slows the real cartridge. Normal4P rises 10,087→10,106 frames; BC40 adds160 frames; old4P rises126,163→128,683 (worst2,022→2,032); solo165,627→166,503 (worst1,397→1,485). All candidate jobs are terminal. The selected production and scratch ROM/ELF remain/restored to7a115b00. Matching full-LTO disassembly and instruction histograms attribute96.1% of R2's extra17,761.289 ticks/scene to the opaque cursor: extra scanner work plus lost compiler proof that actor equals actors[slot], causing repeated address calculation/state/handler dispatch. A typed shared traversal policy is being prepared, preserving the migration goal while correcting this implementation cost.

The same state-equivalent R2 workload trace counts13–31 world objects (mean22.916),9–46 active weapon records including options/dying shots (mean27.412), and29–74 SAT entries (mean54.328). Thus BC's larger slot capacity alone does not explain its measured slowdown. Counts are scene-entry snapshots, not executed-task or pixel counts, and the Normal comparison uses different content/record definitions. `.local/bc-shared-actor-pass/workload-diagnosis.json` records these limits and the selected baseline's expensive functions for subsequent engine integration.


### 2026-10-06 — Typed shared actor traversal retained

Previous goal turn classification: **progress**. The first opaque iterator was rejected on measured native regressions, and an alternative was prepared without changing the selected ROM. The alternative now centralizes Normal and all three BC actor passes in `inc/enemy_pass.h`, retaining typed induction, fresh Normal pool tails, BC slot/address equivalence, immediate births and early exits. Its two complete non-LTO objects match the originals byte-for-byte. The full LTO cartridge build also matches the verified baseline byte-for-byte: SHA-256 `7a115b005e06b0646113335e2c6581cd44ef4c3cc5cd75b4413d954425a1d527`. Thus all existing native state/render/timing measurements remain applicable without another identical replay run.

Fresh source-level validation passed 2,203,453 sanitizer comparisons, 19,497 actual-runtime source-recorded loops (407,913 actor updates), and the complete 1–4P party fixture. Evidence is `.local/bc-shared-typed-pass-native/verified.json` and `.local/bc-shared-engine-review/pass-prototype/typed-alternative/`. This is source traversal consolidation, not a speed improvement or completed engine migration. Player/weapon/collision and frame lifecycle integration remain outstanding. The 60 FPS goal is unchanged and unmet.


### 2026-10-06 — Split lifecycle and verified launcher candidate, not retained

Isolated SHA `0139c0352ecc439e03e8e20ea686ab287637649652c93afb93d18819bea0861a` genuinely splits BC simulation and drawing and routes both through the existing game/flow lifecycle, with one shared main frame completion path. It also corrects seven launcher poses to reviewed Normal artwork, preserving source XOR flips. The asset extension retains all 2,793 existing small and 811 large patterns and palette choices exactly, with all 194 unrelated generated outputs unchanged. Durable source-pose evidence is prepared in `tools/bc_sprite_matches.json`; two additional composites and eight cells require 2,048 pattern bytes.

All 87,845 old four-player canonical states remain exact, as do all Normal40 state/render samples and all 3,001 aligned Rush state/render hashes. Home12, launcher28 native SAT/VRAM checks, each-controller four-player pause/freeze/resume, populated mode handoff, and the complete four-player ending presentation pass. Stack gap is 12,508 bytes with no overlap. The Normal test originally rejected the compiler's MOVE.B-to-stack input boundary; accepting that observed opcode form fixes instrumentation without cartridge changes. Shared-scene profiling also now handles the linked flow_draw return after game_draw inlining.

The candidate is not promoted because timing regresses: BC40 adds104 video frames; old4P126,163→128,742, worst1,000-update window2,022→2,030; R2 mean1,368,899.315→1,381,883.874 core ticks. Normal4P10,087→10,090, alignedRush remains3,011. Dominant BC simulation kernels and their matched R2 instruction tallies remain unchanged. Investigation is confined to lifecycle/draw orchestration and pose selection, without reverting the shared-engine objective. Full source/ROM archive and terminal test results: `.local/bc-engine-lifecycle-native/`. Production remains the verified `7a115b00` ROM. No 60 FPS claim.


### 2026-10-06 — Lifecycle overhead isolation continues

Previous goal turn classification: **progress**. It retained byte-identical typed actor traversal and rejected the first split-lifecycle implementation on measured overhead, while preparing a verified Normal-art launcher correction. Production remains `7a115b005e06b0646113335e2c6581cd44ef4c3cc5cd75b4413d954425a1d527`; architecture integration and 60 FPS are incomplete.

The next isolated candidate, `308306c980048519ec65dc6f53ec56d4419aca37c17ffe3e0a572298103684ed`, keeps drawing out of the shared flow dispatcher and packs the corrected launcher pose result without duplicating flip packing. All 12,500 states of the explicitly bounded four-player replay match, and all 28 native launcher pose/flip SAT/VRAM checks pass. This is a partial route, not another full campaign verification. R2 mean cost improves from 1,381,883.874 to 1,376,672.990 ticks, but remains 7,773.675 above production; BC40 still adds 73 video frames. It is archived, not promoted, under `.local/bc-engine-lifecycle-native/revised/`. Restoring the previous BC diagnostic sampling contract is the next isolated test; no simulation, rendering, wave or collision work is omitted. The parallel shared shot-query and source-grounded background reuse tasks remain underway.


Lifecycle follow-up disposition: all four bounded variants retain 12,500 exact canonical states, with no complete-route claim. Restoring BC's original debug sampling reduces R2 mean to 1,375,467.331 ticks and BC40 overhead to 63 video frames. Separating ending presentation gives 1,375,415.902 ticks, still 6,516.587 above production; explicitly retaining one typed player-draw loop produces the same measured timing. These variants are archived and not retained (`.local/bc-engine-lifecycle-native/variant-results.json`). No gameplay or render work was skipped. The split lifecycle remains prepared but outstanding. Scratch is now restored to the selected lifecycle while the actual shared shot-query pipeline and verified launcher artwork undergo independent linked gates. The query has 800,000 Normal and 4,555,158 BC sanitizer comparisons; its builders and outer body/party collision systems remain separate, so it is explicitly partial integration.


### 2026-10-06 — Shared projectile queries and matched launcher artwork retained

Production build52701 completed with SHA-256 `950214fe69568db0f45c2f858794dd6127162ee41189d9418197f6f7577b53ba`, exactly matching the tested cartridge. The new engine query owns traversal, live rechecks, geometry, ordered consumption/protection/damage and stop handling for Normal flat/row queries and BC indexed/fallback queries. Per-mode compact storage, hit arithmetic, cadence and hit order are preserved. Builders, outer party/body contacts and player/weapon/lifecycle ownership are still separate. This is genuine partial query integration, not a complete same-engine port or speed solution. The slower lifecycle variants remain archived, not retained.

The launcher's seven poses now use reviewed existing Normal graphics, with the source horizontal flip applied to standing/airborne poses. Durable provenance is `tools/bc_sprite_matches.json`. All28 pose/flip combinations match native SAT entries and exact uploaded VRAM with zero remaps, drops or composite fallback. The asset extension preserves all2,793 old small patterns,811 old large patterns and all palette assignments; two composites/eight cells add2,048 pattern bytes. The five poses lacking live sequencing captures remain identified as resident-source-bank evidence rather than live animation proof.

All344,105 canonical BC states match. Old4P126,163→126,176 video frames, worst1,000-update window2,022→2,023; expanded4P143,304→143,312, worst2,023→2,022; solo165,627→165,632, worst1,397 unchanged. R2 mean1,368,899.315→1,368,866.464 core ticks; BC40 adds11 video frames. Normal40 state/render hashes are all exact; aggregate4P10,087→10,094 frames (59.44FPS), with worst sampled1,000-update section1,035 frames (57.97FPS). The actual selected7a Normal report has a1,033-frame worst4P section; the earlier58.03FPS prose referred to an older1,034-frame sample. These are bounded section/window averages, not a proven whole-game minimum or instantaneous FPS.

Aligned Rush preserves3,001 state/render hashes and3,011frames; legacy Rush preserves all3,000 video hashes,2,990updates and clean reset with zero render issues. Vulnerable Normal preserves3,001 state/render hashes at3,042→3,047frames. Home12, populated arena handoff, all1–4P ordered-contact fixtures,32,000 contact-stream comparisons and native stack checks pass (minimum gap12,556bytes, no overlap). Independent sanitizer proofs cover800,000 Normal and4,555,158 BC queries. All candidate readers are terminal. Evidence: `.local/bc-shared-query-native/verified.json`. The small timing tradeoffs are accepted for architectural/art correctness; sustained60FPS and the broader graphics remaster remain unfinished.


### 2026-10-06 — First authored BC background family retained

Production build63018 exactly matches tested SHA-256 `7c70e62cd1a811c42da7e64ee431d4aee562a70c36145b234ba19adb7e6aac90`. R1 cells20/21/22/3A/3B now use newly authored contours with existing Normal stone/rock materials. These are adapted artworks, not falsely claimed whole-cell identity matches. Exact source composition is preserved in the generated pixels:3A=20.right+21.left,3B=21.right+22.left,and22.right=20.left. Completing22 avoids cutting off the warm rock formation beside21. Stone relief was softened after visual review in the actual source-map neighborhood. Durable contour/provenance files live under `tools/data/bc_background_r1_*`; generation is reproducible through `tools/build_bc_background.py`.

All58 other R1 images, all palette/template words, source collision data, scrolling code and generated R2–R10 files remain unchanged. Unique R1 blocks51→54 add1,632 raw resource bytes. Native checks cover103 camera positions and115,360 nametable/VRAM subtiles with no cache failure and a clean menu return. Actual rendered camera1280/0 was visually reviewed. The bounded12,500-scene replay is exact and spans17,550video frames both before and after; R2 mean1,368,873.996ticks (a7.532-tick phase-level difference from9502, not a claimed gain). Normal4P's ten state/render samples and all timings remain unchanged at10,094frames. This is a five-cell art correction, not the complete level remaster or a whole-campaign speed verification. Evidence: `.local/bc-background-reuse-native/verified.json`.


Shared native collector follow-up: isolated candidate67e071e93459d77bd524d7e680260cb7c7fb0322909495daf6b90ddc51d8c195 replaces both actual builders with the same typed algorithm, including the real BC68000 implementation. Independent native correctness passes8,192boards/16,384 full-byte comparisons; all source bytes and sentinels remain intact. However, matched public-call microbenchmarks are0.78–3.38% slower, and linked gates confirm overhead:12,500states exact, R2 mean1,372,929.194ticks (+4,055.198vsretained7c70),BC40+35frames,Normal40state/renderexact with4P10,094→10,098frames. The candidate is archived, not retained, pending a measured calling-convention improvement. Evidence is `.local/bc-shared-collector-native/disposition.json` and `.local/bc-shared-collector-prototype/native-probe/`. Current production remains7c70.

A separate lifecycle variant is now staged only in scratch: the genuine shared game/flow update/draw split plus a native compiler register-allocation constraint, based on measured spill overhead rather than an algorithm change. It retains the verified query and artwork. Build/native results remain pending; no main-ROM lifecycle or collector integration claim is made yet.


Lifecycle register-allocation trialae00665480b5ae39cb11b3a341b19c345ba3c1db629c9485c9828d41ab4a0b7a is rejected on linked code shape before replay. The non-LTO object improvement does not survive full LTO: update13,712→13,824bytes, frame-local accesses286→304 and saved registers7→8. One spilled argument source is removed per player call, but a new save/reload adds eight accesses across four calls, and all deferred-wave spills remain. No FPS measurement is claimed for this unrun variant. Source/ELF/ROM are archived under `.local/bc-shared-lifecycle-review/remaining-overhead/linked-trial`; scratch sources and outputs are restored to retained7c70. The remaining lifecycle integration is still unfinished.


### 2026-10-06 — Shared-engine follow-up and bounded collector ABI measurement

Previous goal turn classification: **progress**. It retained the actual shared projectile query and corrected launcher artwork, then the five-cell R1 contour/material correction; it also measured and archived the slower split-lifecycle and plain shared-collector alternatives. Current retained production remains `7c70e62cd1a811c42da7e64ee431d4aee562a70c36145b234ba19adb7e6aac90`. Same-engine ownership, the full graphics remaster and sustained 60 FPS are not complete.

The shared collector register-entry candidate first failed the actual game link because a static assembler target could not resolve across LTO partitions. A two-line linkage-only fix reproduces the original failure in a four-partition test and resolves the helper as GLOBAL HIDDEN. The actual game link now passes the fail-closed native-body check: 3,398 bytes, SHA-256 `a402e59025426d1a85334e57ae2e860fb371b63dba6d2a03246118aff50ec3bd`; candidate ROM `f716070fae95a561d575c9f298f3e8839f676763dedfa515121c9d7104e9d46f`. Its explicitly bounded 12,500-state replay is exact. R2 mean cost is 1,370,838.525 core ticks, versus retained 1,368,873.996 and plain shared C 1,372,929.194. BC40 adds 18 video frames versus the retained query timing matrix (the art-only follow-up leaves those opening cells outside scope). This is a measured reduction of the earlier collector overhead, not a speed improvement over production or a full-route proof. Normal40 remains in progress. Evidence: `.local/bc-shared-collector-native/register-abi/`.

The existing-party-frame noinline experiment was stopped at object review: combined code shrank only 24 bytes, nested local stack increased 56 bytes and new aggregate-result stores/sound tests appeared. No game build or timing claim is made for that experiment. A shared fused lifecycle is now being designed to move session/transition ownership into the regular engine without requiring the costly update/draw split.


Collector ABI follow-up disposition: all40 Normal state/render samples match, with no measurement errors. The ten4P sections take10,098frames versus10,094 retained (section3 adds3, section7 adds1). Candidatef716 remains archived, not retained; all native readers are terminal and shared scratch sources/outputs are restored to retained7c70. The compiler-ABI experiment reduced the plain collector overhead but did not improve production speed. Main runtime timing and artwork are unchanged. `.local/bc-shared-collector-native/register-abi/disposition.json` records the exact result.

## October 9 controller protocol follow-up

The current `45e7faf9` cartridge guards SGDK's nullable Team Player event
callback in a build-local SDK adaptation. This fixes the first-button crash and
the earlier startup crash when buttons are held and the other port is empty.
`tools/qa_multitap.py` covers both Team Player ports and EA 4-Way Play with three-
and six-button pads through emulator controller protocols, without the logical
pad hook. All six configurations pass 228 isolated button/release checks plus
held-Up startup and reset. See `.local/multitap-startup/` and the current
`docs/expansion-acceptance.md` for evidence and limits. The old physical-adapter
validation gap is narrowed by protocol emulation, not replaced by a hardware claim.


### Precise MOVEP event-clear memory operand rejected — October 9, 2026

Retained build remains b7d8519de191b3b944498ecc74c901750f8cbe6a58d01d5879ce14b3fd98c672. Current instruction attribution is saved under `.local/b7-performance-review/`; the profiled 6123 executable regions were verified byte-identical to b7 before using that histogram. The common actor entry still spends substantial time saving/restoring registers and clearing event records.

Candidate a71c5332a37c8bb86420d8414623dcd4e0b37806d587649b6c6384c8e4814355 replaces the MOVEP clear's global memory clobber with an explicit eight-byte output operand. It changes no alignment contract or gameplay rules. Native O2/O3 probes pass 1,024 cases across both byte alignments and all initial byte values, preserving preceding reads and surrounding sentinels. Main common/curve routines remain byte-identical; the straight helper shrinks from 218 to 204 bytes.

The 600-update four-player HuCard samples preserve every simulation hash and workload. R2 changes 735→734 video frames, mean664649.3→664636.828 core ticks. R8 worsens1005→1009 frames, mean886474.19→888510.933. Rejected for the heavier-scene regression and absence of improvement in the intended common path. Original source restored, touched and rebuilt; exact b7 hash verified. All jobs terminal. Evidence: `.local/bc-event-clear-operand/rejected.json`, comparison.json, native/ and before/candidate archives. No speed improvement is retained or claimed.

### Scheduler policy decoding corrected — October 9, 2026

The preceding goal turn made progress by rejecting the precise audio-copy
operand trial after a longer control. Its mixed timing prompted this read-only
scheduler investigation. Retained ROM remains b7d8519d.

`profile_bc_budget.py` previously exposed `process_time_stack` for every
SYS_doVBlankProcessEx entry. The current GCC constant-propagated clone has no
incoming argument: it pushes TRUE directly into VDP_waitVBlank. The raw stack
word (for example 2772) is therefore not a policy for that clone. Existing
frame counts, scanline observations and measured durations are unaffected.
Do not interpret that historical raw field as a mode without checking the ABI.

New `scheduler_policy.py` checks exact native entry instruction prefixes and
the specialized clone's VDP_waitVBlank target. It reports process_time=2 for
that verified ON_VBLANK_START clone, reads SP+4 only for the verified generic
entry, and reports unknown for unsupported machine-code layouts. The profiler
retains raw stack evidence and adds decoded policy plus its source.

Fresh retained R8 4P HuCard 600-update measurement reproduces 1005 frames,
every state/workload/scene-time row and every prior scheduler row exactly;
596 calls select next-start and 3 select current-blank. Evidence is
`.local/scheduler-policy-audit/verification.json`.

Applied to the two archived 3000-update R8 ROMs, with hashes and entry bytes
checked independently: retained b7 has 2995 next-start / 4 current-blank calls;
rejected d2 has 2992 / 7. Scene ticks fall 3,032,849,771 to 3,024,979,853,
but scheduler ticks rise 1,992,012,940 to 2,005,720,349. Video frames rise
5660 to 5667. Current-blank calls finish their video writes within the same
blank (latest physical lines252/251). Late entries mostly cluster at physical
lines254–261; they do not establish room for safe additional DMA. This
explains why lower isolated scene cost did not yield faster gameplay; it
is not evidence that relaxing the scheduler limits is safe. No runtime or
cartridge change retained. Full expansion completion remains unproven.
