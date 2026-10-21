# Side Arms expansion acceptance — October 9, 2026

## Integrated 5f6aa68a — October 10

The main clean rebuild reproduces the tested cartridge exactly:
`5f6aa68ad8c9fce146ae952f0885957fb063436257f1f144f9c4c9b70e184cab`.
It remains 4 MiB, with the existing sound-bank alignment, all content, and the
v1.4 compatibility fixes. General dispatch is bypassed for official R3 curves
and idle pickups, R5 divers and walkers, and R5/R7 segmented trains. Walker
bursts retain ordered three-shot creation. Normal's sprite upload allowance is
8 KiB; BC retains 6 KiB and both keep the existing cache-churn scheduling hint.

The full protected four-player BC campaign completes every round, 5,760 credits
updates, and Home return. All 114,250 eligible rolling five-second gameplay
windows exceed 50 updates/sec; the minimum is 50.9343 in R9. There are no HuCard
underruns, software sprite drops/remaps, or unmapped art. This controller pilot
uses protection but does not force boss defeats or seed weapons/health. It does
not prove 50 newly displayed frames/sec. Captured R3 and R5 routes preserve
21,200 and 46,999 gameplay states, with minima 51.5336 and 50.5348 respectively.

All 21 HuCard tracks pass native NTSC/PAL Sound Test, including stop and Arcade
resumption. All 12 native Team Player launch/save/reset cases pass across
3P/4P, Normal/BC/Rush and both regions, without controller-input overrides.
The Normal 4P section-eight HuCard fixture has zero sprite misses; 3,319 flushes
are guarded and the maximum queue occupancy is 29 of 80. BC's catch-up/flush
guard check also passes. The three-player campaign also completes, with a 56.5271 minimum update rate.
Current-ROM imported boss/attack, serpent, weapon, death-art and linked-shading
checks pass, as do US/PAL cold/dirty-RAM reset and autonomous BC music-transition
checks. Normal/Rush 3P/4P assisted progression also passes on this exact ROM. All
current verification jobs are terminal. The package is
`.local/candidates/Side-Arms-MD-v1.4-expansion-5f6aa68a-test.zip`; its ROM hash
and ZIP contents were verified. `handoff.json` records the package checksum.

Evidence: `.local/bc-r3-pickup-diver/status.json`. Earlier candidates below are
historical evidence, not additional current-ROM claims. Final displayed-rate
acceptance remains unresolved; this is not yet a final release.


## Presentation-rate experiment after 5f6aa68a

The current 4P BC R3 periodic sample averages 59.49 gameplay updates/sec but
11.65 presentation batches/sec. The Normal 4P section-eight sample averages
59.82 updates/sec and 29.49 presentation batches/sec. These are bounded
samples, not full-campaign displayed-rate measurements.

An isolated four-update BC catch-up cap increases the R3 sample's presentation
rate to 16.48 batches/sec. However, its recorded route matches all 21,200
states while falling to 45.54 gameplay updates/sec in R2. It is rejected;
5f6aa68a and its packaged ROM retain the eight-update cap. Evidence:
`.local/bc-present-cap4-5f/status.json`. The pending user question distinguishes
50+ gameplay updates with skipped pictures from 50+ newly drawn frames.

## Historical candidates 0b891d42 through c5b7dbd5

The isolated candidate routes R3 curve handlers through the existing ordered
single-child path. All 2,048 host boundary cases pass. A recorded controller
replay through the first 25,000 campaign updates matches every canonical state;
minimum rolling five-second gameplay rate rises from 46.7397 to 51.7333.

Normal's pattern-transfer allowance rises from 6 KiB to 8 KiB, while BC retains
6 KiB and the cache-churn hint still triggers after 2 KiB of uploads. The failing
Normal 4P section 8 fixture now has zero sprite misses, with all 6,000 gameplay
states unchanged and minimum update rate 56.5271. The same combined candidate
still matches all 25,000 BC states and the 51.7333 minimum. The transfer guard
observes 3,319 protected flushes and 4,270 HUD writes outside flushes; maximum
queued entries is 29, below the 80-entry capacity. These are bounded emulator
checks, not a physical hardware claim.

All 42 Normal/Rush cases now pass, minimum 56.1276 updates/sec, zero sprite
misses and zero HuCard underruns. Every compared gameplay-state prefix matches
04615f99. The full 4P BC campaign completes with zero audio/render counters,
but its rolling minimum is 45.1418 in R5 (ticks 46,168–46,394). This controller
path differs from the earlier full campaign; do not label it a same-workload
regression. It remains a gate failure. A 46,999-state input record reproduces
it; the corrected profile attributes 27.91% to general actor dispatch. The actor-mix replay identified R5 segmented trains as the dominant fallback
handler (5,194 samples over 500 scene entries). Candidate 1ebee6a8 extends
the existing train path to official R5/R7 resources. Its 2,000 three-pass host
cases preserve 123,240 ordered events, including 3,000 child births and 3,000
allocation failures. The native replay preserves all 46,999 recorded states and improves the
minimum from 45.1418 to 46.7397 updates/sec, still below the target. Another
6,144 host cases cover every byte wait value. The R7 four-player periodic
fixture passes at 55.5284 minimum updates/sec with no HuCard underruns.
A follow-on candidate also routes official R5 divers through the existing
single-child path; host and native replay checks are running under
`.local/bc-r5-diver-direct/`. The diver candidate (6a698f53) preserves all 46,999 recorded states and raises
minimum update rate to 49.5361, still below the gate. Candidate walker dispatch
now reuses a multi-child envelope; 2,304 host cases pass, plus eight explicit
burst cases that include six ordered child events. Its emulator replay matches all 46,999 recorded states and raises the
minimum to 50.1354 updates/sec (worst window now R4). The full BC4P campaign finishes all rounds, credits and Home return without
audio underruns, but a different R3 encounter reaches 48.5374 updates/sec
(ticks20,344–20,587). The exact-input prior route remains above50; that narrower
pass does not establish full-campaign performance. A new recorded prefix is
being captured under `.local/bc-r3-crowded/`. All40 round/player cases pass (minimum52.7320);42Normal/Rush cases are
complete under `.local/bc-r5-walker-direct/`: all42pass, minimum56.1276,
zero software sprite misses or HuCard underruns. The new R3 record and actor
mix match all21,200 states. A400-scene profile identifies general family
fallback as the largest cost. R3 pickup/diver shortcuts pass3,504host cases
and99,864ordered events; the combined native build exceeded4MiB after crossing a sound-bank alignment
boundary and was rejected. The pickup-only variant fits the existing cartridge
layout; both captured R3/R5 controller routes pass with21,200/46,999states
unchanged and minima51.5336/50.5348updates/sec. A full four-player campaign
and native NTSC/PAL SoundTest are running before integration. The R3 diver remains on the existing dispatcher. Evidence: `.local/bc-r3-pickup-diver/`.
This is simulation throughput, not proof of 50 displayed FPS. No candidate is integrated. Evidence: `.local/bc-r5-train-direct/`. Main remains 04615f99. Evidence: `.local/bc-r3-curve-direct/` and
`.local/normal-upload8k/status.json`.

## Historical 04615f99 failures

04615f99 is not release-complete. A full protected 4P BC campaign measured at
rolling five-second resolution reaches **46.7397 gameplay updates/sec** in R3,
ticks23,655–23,889. All114,238 eligible windows exclude intentional waits,
transitions and ending; the measurement run reproduces the original campaign's
exact end-RAM hash and video duration. Earlier 1,000-update campaign windows
and shorter periodic fixtures missed this interval. Evidence:
`.local/expansion-04615-campaign/bc-4p-rolling/rolling-timing.json`.

All42 Normal/Rush timing cases pass (minimum54.5297), including both12-boss
Rush completions through player fire. However, Normal4P section8 HuCard has24
software sprite misses:12 each at measured updates2,644 and2,656. Only47/48 SAT
entries are submitted, but sprite-transfer budget is exhausted. The47c4 fixture
has the same6,000 gameplay state hashes and zero misses. This is a rendering
regression, not a full-SAT limit. Evidence: `normal-rush-timing/` and
`normal-4p-8-drop-trace/` under `.local/expansion-04615-campaign/`.

## Historical 04615f99 — HuCard and enemy-dispatch optimization

Integrated October 10. `make all` reproduces the isolated tested ROM exactly:
`04615f99dad9a256c5113501ac52a81db6125306697df6c93141ee61735ef152`.
HuCard snapshots free queue slots once, skips unchanged pitch/instrument
packet writes, and only refreshes operator multipliers on instrument changes.
BC reaim decoding is deferred until its timer expires. Round-one curve enemies
reuse the existing single-child event path, avoiding unrelated family dispatch;
custom resource relocations retain general dispatch precedence.

All twenty 3P/4P BC round timing fixtures pass, minimum 51.933 updates/sec.
These are protected periodic-input samples, not proof of full campaign speed.
Same-consumed-input replays preserve 6,478 states in R1, 2,390 in R3 and 5,943
in R9. R1 rises from main c494's 49.536 to 55.728 minimum updates/sec; R9 rises
from 49.936 to 51.134. Displayed rates remain lower (R1 31.290, R9 13.023).
The prior failures below are historical and remain documented for comparison.

Host differential coverage passes 4,096 two-update curve cases, all byte waits,
four handlers, firing latches and free/full pools; 135,680 ordered events match.
The first host fixture omitted bullet terrain and crashed; only the corrected
fixture with valid terrain contributes evidence. A host-only CPU profile of
R1 ticks 4,200–4,599 identified general dispatch at 32.14% versus audio at 10.76%
before the curve change; its gameplay counts match the unprofiled replay.
The first profile used the wrong phase gate, was terminated, and is excluded.

Native Sound Test passes all 21 tracks in NTSC and PAL, 420 packet comparisons
each, no underruns, stop silence and Arcade resumption. All twelve Team Player
3P/4P Normal/BC/Rush launch/save/reset/migration cases pass across NTSC/PAL.
The graphics-transfer check observes 3,155 protected flushes and 1,575 catch-up
entries without pending DMA. No enemy, boss, attack, or artwork was removed.

Evidence: `.local/hucard-refill-snapshot/status.json`, `curve-archive/`,
`curve-host.json`, `curve-multiplayer-timing/`, `curve-gameplay/`,
`curve-r1-replay/`, `curve-r3-replay/`, `curve-r9-replay/`, both
`curve-audio-*/` directories, and `curve-dma-guard/`.
Final displayed-rate acceptance and broader current-ROM campaign coverage
remain incomplete. The twenty current-ROM solo/duo round samples also pass, minimum 58.724
updates/sec (R3 duo ends naturally at Game Over; other cases reach the frame
limit). Earlier art and full Normal/Rush evidence remains historical, not
relabeled as this ROM. Solo evidence: `curve-solo-timing/`. The clean rebuild passes with no warnings in src/ or inc/ and reproduces
the tested ROM hash. Packaged as
`.local/candidates/Side-Arms-MD-v1.4-expansion-04615f99-test.zip`.


## Additional current-ROM content and boot verification — 04615f99

The current cartridge passes imported boss bodies/attacks, boss projectiles,
serpent, player weapons and death-art checks. The linked recolor check covers
144 records, 90,624 pixels and 335 ordered ramps with 1,435 visible shade steps,
including gallery variants. This checks source geometry and shade ordering;
it does not independently approve semantic matches or subjective hue fidelity.

US/PAL cold and dirty-RAM launch/reset checks pass, as does the autonomous
four-player BC stage-to-boss music transition. These model emulator conditions
and do not claim physical EverDrive certification. All six longer 3P/4P progression checks pass on this exact ROM. BC uses
protected controller combat and completes all ten rounds, 5,760 credits updates
and Home return without forced boss defeats, seeded weapons/health, unmapped
art or software sprite drops/remaps. 3P takes 109,111 updates / 121,605 frames;
4P takes 117,710 updates / 132,253 frames, including ending. Normal/Rush use
assisted hits and complete all sections/encounters and result/exit checks. All
six runs have zero HuCard underruns. These are not unassisted combat or full-speed
claims. Evidence: `verified-campaigns.json`.
Evidence: `.local/expansion-04615-campaign/status.json`, `content/` and
`boot-transition/`. Those checks are terminal; their failures are summarized at the top of this
document. The corrected R3 heavy-interval CPU profile is complete: 400 scene calls
average 1.126 frame budgets; 264 exceed one budget. General family fallback
accounts for 17.08% of attributed cycles. The original profiling attempt used
the multi-update engine boundary and failed its one-update assertion; it is
excluded. Evidence: `bc-r3-heavy-scene-profile/profile/profile.json`.
All campaign, timing and diagnostic processes are terminal.

## Historical c494 gate failure — resolved in 04615f99

On October 10, the same-input R9 comparison exposed a c494eb63 failure missed
by the periodic-fire samples: HuCard's lowest five-second simulation rate is
49.9356 updates/sec. Arcade reaches 59.1238. Both match all 5,943 recorded
canonical states; neither has audio underruns. The former 47c4 heavy replay
passed at 51.334, so this is a current-build performance regression to resolve.
The c494 package remains a development test build, not an accepted release.

R3's displayed rate is 12.384 HuCard / 16.778 Arcade; R9's is 12.993 / 19.395.
The recorded prefixes match, but fixed video windows cover differing amounts
of simulation, so these are observed cadence differences, not pure audio CPU
percentages. Runtime checks find zero active regular music channels in all
5,997 active HuCard samples. Regular sound effects remain enabled.
Evidence: `.local/bc-music-cost/summary.json`. The timing tool now accepts
`--music arcade|hucard`; HuCard remains the default. No game source changed.

## HuCard refill snapshot candidate — not integrated

Candidate `73a0d982` reads free queue slots once per refill instead of repeatedly
halting the Z80 to check fullness. It passes all 21 tracks in NTSC/PAL (420 packet
checks each, no underruns), all twelve native gameplay launch/save cases, and
3,181 guarded flushes with 1,561 catch-ups free of pending DMA. The heavy R9
replay preserves 5,943 states and rises to 51.134 updates/sec. However, R1 4P
periodic-fire timing falls to 49.736, so it is not integrated. Fixture timing can
change the consumed input sequence; this result alone does not prove the new
producer is slower on identical R1 gameplay. Further comparison is needed.
Evidence: `.local/hucard-refill-snapshot/status.json`. All jobs are terminal;
main remains c494eb63 with its documented heavy-replay gate failure.

## HuCard packet optimization and controlled R1 follow-up — October 10

Replaying the same R1 inputs on main c494 reaches only 49.536 updates/sec;
snapshot 73 reaches 49.736. The earlier differing periodic samples therefore
do not establish a snapshot regression. Both still miss the target.

Candidate 49ff02a5 additionally avoids rewriting unchanged pitch/instrument
bytes and operator multipliers. Exhaustive host FM verification covers 524,288
frames, and native NTSC/PAL tests each verify 420 packets across 21 tracks with
zero underruns, stop silence and Arcade resumption. Controlled R1 matches 6,478
states but reaches 49.936 updates/sec; R9 matches 5,943 and reaches 51.134.
It is not integrated. Displayed rates remain 29.212 and 13.023 respectively.

Guest-clock measurements around the full HuCard interrupt producer show mean
costs of 0.110725 video-frame budgets on main and 0.106000 on 49ff in the R1
periodic fixture (5,994 samples each). This includes Z80 bus waits. It is a
small reduction, not a solution to the overall slowdown. The two periodic
runs are not identical-input gameplay comparisons. A first attempt to combine
two instruction-hook wrappers crashed the host and is excluded; the successful
measurements use one wrapper with the ordinary timing fixture.
Evidence: `.local/hucard-refill-snapshot/controlled-results.json`,
`operator-archive/`, `operator-r1-replay/`, `operator-r9-replay/`,
`operator-audio-ntsc/`, `operator-audio-pal/` and both `*-r1-budget-plain/`.

Combining the earlier reaim-expiry optimization with this audio candidate
produces `1c4b0507`. Both controlled replay rates and matched-state counts
remain identical to 49ff above; R1 still fails. All jobs are terminal, and no
candidate is integrated. Archive: `.local/hucard-refill-snapshot/combined-archive/`.

## Historical build c494eb63 — BC catch-up extended to 1P/2P

Main `make all` reproduces the tested isolated ROM exactly:
`c494eb63334515bad35490d82e3f6f0e69d58ede8019dcaebc7a864e7e055121`.
Only the BC party-size catch-up guard changed from the previous main build;
the reaim and animation experiments are not integrated.

All twenty 1P/2P BC round samples pass the simulation gate, minimum 58.724
updates/sec, with no audio underruns. R3 duo ends naturally after 3,996 measured
video frames from stationary terrain deaths; the other nineteen run 6,000.
Menu/pause/freeze/resume/reset checks pass for both party sizes; two-player
shared-credit/unlimited continues pass; both autonomous HuCard stage-to-boss
transitions pass. The native guard observes 4,089 protected flushes and 655
catch-ups without pending DMA. Solo consumed-input replay matches 1,983 states.
Evidence: `.local/bc-presentation-pacing/solo-integration-evidence.json`.

`tools/check` passes without source/header warnings and reproduces c494eb63.
Current-ROM 3P/4P R1/R3/R9 timing checks all pass (minimum 52.532 updates/sec),
as do all twelve native Team Player mode/party/region launch/save/reset cases.
The 4P consumed-input replay preserves 2,390 states. The initial controller
wrapper run targeted the wrong ROM path and was terminated; its evidence under
`interrupted-gameplay-wrong-rom-path/` is excluded. The corrected isolated-ROM
run is `integrated-gameplay/summary.json`.

Updated package: `.local/candidates/Side-Arms-MD-v1.4-expansion-c494eb63-test.zip`.
Its embedded ROM checksum is verified; the detailed handoff is
`.local/bc-presentation-pacing/handoff.json`. Previous full art/audio/Normal/Rush
results remain attributed to 47c4adc5, not to this build. All jobs are terminal.
These results do not resolve the displayed-FPS requirement or complete the release.

## Current CPU budget measurements — October 10

Host-only scene entry/return hooks preserve the uninstrumented current-ROM
simulation, presentation and render-skip counts exactly in R3 and R9 4P HuCard
fixtures. Ratios below use one stock NTSC video frame's 896,040 master clocks.

| Round | Updates without drawing: mean / 95th percentile | Updates with drawing: mean / 95th percentile |
| --- | --- | --- |
| R3 | 0.821 / 0.919 frames | 1.259 / 1.420 frames |
| R9 | 0.662 / 1.142 frames | 0.933 / 1.454 frames |

The measurements include interrupts during a scene but exclude outer input
handling and final VBlank/DMA. Drawn/skipped groups have different workloads;
subtracting their means is not a controlled measure of drawing alone. R9 even
has simulation-only updates exceeding a video frame. These results support
prioritizing simulation cost as well as rendering, rather than another scheduler
cap change. They do not establish a hardware performance ceiling or justify
removing enemies, attacks or art. Evidence: `.local/bc-update-budget/summary.json`.
All measurement jobs are terminal; main ROM remains c494eb63.

## Shared pose-cache experiment (not integrated)

`.local/bc-pose-cache/host.json` verifies 47,104 ordinary/boss-shot pose mappings,
including repeated cache hits. Both inlined and outlined prototypes cross the
current sound-bank alignment boundary and fail the existing ROM finalizer;
the outlined text size is 4,226,204 bytes. No mapper was added and no performance
gain was claimed. The experiment is archived and source restored. This is a
constraint of this build's current unbanked layout, not an EverDrive size limit.

## Previous handoff: 47c4adc5 — displayed-rate acceptance unresolved

Current ROM: `47c4adc56acb923409d146da41e2513bef448af4e9edad5d848e848a09ebb09e`.
Local package: `.local/candidates/Side-Arms-MD-v1.4-expansion-47c4adc5-test.zip`.
`make all` and `tools/check` reproduce this ROM, with no game source/header
warnings. The ROM remains 4 MiB and retains the v1.4 startup/header/DMA fixes.

The previous R9 timing miss is addressed by testing terrain first and doing
homing aim/vector decoding only when the original byte timer expires. The
non-turning path retains timer wrap, contact order, movement, attacks and enemy
counts. All 16,000 host differential cases pass. A native replay applies inputs
at the verified player-step argument boundary and preserves all 5,943 recorded
heavy-scene states, with a minimum 51.334 updates/sec. Earlier scene-entry input
replay was inadequate: video-frame input writes can occur within a long update.
The direct-inline experiment and the always-called helper are superseded.

| Current-ROM check | Evidence/result |
| --- | --- |
| Normal 3P/4P, ten sections, both music sources | All 40 cases pass; Normal/Rush minimum 56.128 simulation updates/sec |
| Full protected Rush 3P/4P | All twelve bosses defeated with player fire in each run; no injected kills |
| BC 4P, all ten rounds | Minimum 51.134 simulation updates/sec; 6,000 video frames per sample |
| BC 3P, all ten rounds | Minimum 57.126 simulation updates/sec; R3 ends naturally at Game Over after 5,069 measured frames; others run 6,000 |
| HuCard Sound Test | All 21 selections in NTSC/PAL; 420 packet checks per region; zero underruns |
| Native Team Player launch/save/reset/migration | All twelve 3P/4P mode/region cases pass, without logical pad override |
| Flash-cart-like startup | NTSC/PAL cold/dirty RAM boots and resets pass; current native HUD/DMA guard check passes |
| Music transition | Autonomous 4P BC stage-to-boss transition passes |
| Art | All 134 explicit choices preserved; 22,000 BC selection cases and 326 ordered ramps checked; current boss/attack/weapon/death imports, R5 and R7 checks pass |
| Blue effects | 159 post-DMA layer pairs across all seven poses match source geometry/mapping; every repaired visible scanline fits sprite limits |

One Normal 4P Arcade section-six fixture retains ten brief sprite-upload misses,
matching its baseline. The stationary BC 3P R3 fixture loses lives to terrain;
protection supplies invulnerability, not immunity to terrain/checkpoint deaths.
`qa_bc_frameskip_timing.py --stop-on-game-over` reports the shortened sample and
uses its actual duration. It does not pad the result with menu frames or assert
that 6,000 frames were played. Unsupported runtime statuses still fail.

**Do not call the update-rate results 50 FPS.** The heavy BC 4P fixtures average
8.589–26.436 displayed pictures/sec with frame skipping. The user has been asked
whether their minimum means displayed frames/sec or simulation updates/sec.
Until clarified, the expansion remains active and is not release-complete.
If the requirement is 50 displayed frames/sec, the present build does not meet it.

Authoritative rollup: `.local/blue-effect-shades/handoff.json` (package checksum
verified). Detailed current-ROM evidence is under `final-normal-rush/`,
`homing-expiry-summary.json`, `final-bc-3p-summary.json`, `homing-gameplay/`,
`homing-audio/`, `finish-safety/`, `homing-native-guard/`, and `live-final/` in that
same directory. Original boss/attack/weapon/death checks are under
`.local/current-content-47c4adc5/`. All jobs in this batch are terminal.
These are emulator checks; physical hardware testing was explicitly out of scope.


## Follow-up pacing experiments (not integrated)

Evidence: `.local/bc-presentation-pacing/status.json`. Main stays `47c4adc5`.
Reducing BC catch-up batches from eight to four raises presentation frequency
in some scenes, but fails the simulation floor in R1 (46.340/sec) and R8
(46.939/sec). That scheduler change was rejected and restored in the isolated
workspace. The per-video input fixture is a throughput check, not an identical
workload comparison.

The isolated `649f74c0` candidate moves re-aim expiry work into a separate helper.
All 8,192 host differential cases pass. Exact consumed-input R3 replay preserves
2,390 canonical states and the 59.523/sec rolling update minimum. Presentation
improves only from 12.317 to 12.417/sec in that sample. It is not integrated or
accepted as a solution to visible choppiness. Its subsequent ten-round 4P timing
matrix passes (minimum 51.134 updates/sec, zero underruns). Separating animation
decoding in candidate `bcc11346` preserves the same 2,390 replay states but
reduces presentation from 12.417 to 12.051/sec, so that experiment is rejected.
Evidence is in `reaim-matrix/` and `animation-replay-r3/` under the same directory.

## One/two-player BC catch-up gap (isolated candidate c494eb63)

The timing fixture now accepts 1–4 players and asserts the active party size.
Current main 47c4 disables catch-up below three players. R3 solo reaches a
31.360 update/sec rolling minimum; R8 solo and duo reach 30.361 and 31.759.
R3 duo reaches Game Over at tick 4,588 from stationary terrain deaths, so its
original non-terminal-aware fixture has no completed timing report.

The isolated candidate changes only the minimum party-size guard to allow 1P/2P.
Pause, startup audio, continues, ending, round exits and queued-DMA guards remain.
Four R3/R8 solo/duo samples all pass at >=59.323 updates/sec without audio
underruns. Presentation is 26.176–43.983/sec; this is not 50 displayed FPS.
Exact consumed-input replay matches all 1,983 recorded solo states.
The earlier reaim optimization is absent from this candidate.
Evidence: `.local/bc-presentation-pacing/player-scaling/`, `solo-catchup/`,
`solo-record/` and `solo-replay/`. Remaining rounds and transition checks are
still required before integration. Main ROM and distributed ZIP are unchanged.

## Earlier shading build — BC R9 gate was still open

Current `out/release/rom.bin`: `3561f02db0f0edfa21098cded83073f6881c6c96ccad75020350b26d9df83c18`.
The regular generator/build now reproduces the isolated shade prototype byte for
byte. `make all` and `tools/check` pass, with no game source/header warnings.
The new generator is `tools/blue_effect_shades.py`; CPU-only lookup-table packing
is integrated into `tools/build_assets.py`. The preceding distributed test ZIP
remains bc389f61; no new release ZIP is published for this failing timing gate.

The strengthened live check verifies 159 shade pairs across all seven poses,
including post-DMA pixels and the physical 20-sprite/320-pixel limit on every
repaired visible scanline. Evidence is
`.local/blue-effect-shades/runtime/live-scanline-4p-8/blue-live.json`.
Native TeamPlayer 4P Rush HuCard launch/save/reset/migration also passes:
8,079 guarded/disabled-interrupt flushes, 83,211 safe window writes and 236
catch-up entries without queued DMA. See `.local/blue-effect-shades/native-guard/`.

A fresh ten-round BC 4P HuCard matrix runs 6,000 video frames per round.
Nine rounds pass the minimum rolling five-second 50-update gate; round nine
fails at **47.738 updates/sec**, versus **59.723** in a fresh bc389f61 baseline.
All ten have zero audio underruns. Presentation rates are separate and range
from 8.61 to 27.52 batches/sec in this fixture. Evidence:
`.local/blue-effect-shades/bc-regression/summary.json` and `round-9-baseline/`.

Profiling reproduces those measurements. The candidate spends 15.24% of measured
cycles in homing-actor processing versus 2.24% in the baseline, with substantially
less VBlank waiting. This fixture supplies input per video frame, so its two
runs do not establish identical logical-input histories or identical actor
workloads. The observation does not yet distinguish a workload divergence from
an implementation regression. Diagnose that difference and restore the timing
gate before acceptance; do not promote the nine passing rounds into a full pass.
Profiles: `bc-regression/profile-base/cpu.json` and `profile-new/cpu.json` under
`.local/blue-effect-shades/`. All jobs in this batch are terminal.


## Earlier isolated blue-effect shading verification

The retained ROM remains `bc389f613b23cc724217728db34020da9d333f072da1b90151108c4614a13566`.
The isolated shade prototype is `3561f02db0f0edfa21098cded83073f6881c6c96ccad75020350b26d9df83c18`.
It reuses source pixels already stored in the cartridge and splits seven Normal blue
explosion poses between the existing two sprite palettes when the picture has room.
The unpadded text grows by 800 bytes; CPU table packing retains identical payloads
for all 128 resources (`.local/blue-effect-shades/runtime/packing.json`).
No mapper support or artwork removal is involved.

A native post-DMA VRAM check compared 159 emitted layer pairs, exercising all seven
poses, against independently decoded source pixels and the selected shade mapping.
Layer opacity, paired positions/dimensions, and flip/priority bits matched. Evidence:
`.local/blue-effect-shades/runtime/live-4p-8/blue-live.json`. This is not a complete
scanline-clipping audit or proof of every gameplay scene.

The comparison fixture previously allowed a Normal warp after FS_PLAY but before
players spawned. A changed rendering cost could move one build across that boundary,
leaving the fixtures in different initial states. `qa_normal_fixed_updates.py` now
waits for every selected player to be alive before issuing the warp. Both ROMs were
rerun with this corrected setup; all 6,001 state samples (initial plus 6,000 updates)
match for each scene below. Hashes cover the tool's documented state subset.

| Four-player section index | Music | Minimum rolling 5-second updates/sec | Presentations/sec | Sprite drops, prototype / baseline |
| --- | --- | ---: | ---: | ---: |
| 3 | HuCard | 58.525 | 30.601 | 0 / 0 |
| 8 | HuCard | 56.128 | 29.080 | 0 / 0 |
| 6 | Arcade | 59.124 | 53.094 | 10 / 10 |

All three runs had zero recorded HuCard-driver underrun frames. Evidence:
`.local/blue-effect-shades/runtime/comparison.json`. Presentation and simulation
rates are distinct; these tests support the permitted frame-skipping target.
Previous pre-spawn fixture runs remain historical evidence, not corrected results.

Remaining for this prototype: integrate its generator and runtime changes, validate
full SAT visibility and fallback behavior, then run final-build regressions including
BC and the native controller/save/audio/compatibility paths. The overall expansion
is not yet release-complete. All jobs from this verification batch are terminal.


The objective remains the complete four-player, Before Christ and HuCard
soundtrack expansion. It is **not release-complete**. This document distinguishes
current cartridge evidence from historical tests and supersedes older status
notes where their work was subsequently completed.

The user confirmed **emulator testing only** on October9. Physical-console testing
is not a completion gate. Hardware limits still matter as emulated behavior;
no physical-console certification is claimed. This supersedes older hardware-test
requirements in the historical notes below.

## Updated performance requirement — user clarification October 9

The user requires **50 or more game updates per second, with frame skipping
allowed**. This supersedes the older strict 60 fps / one draw per update gate.
Rendering may be skipped; actors, weapons, collisions, score, input and audio
must keep their intended behavior. PAL uses its nominal 50 Hz cadence; NTSC
must sustain at least 50 simulation updates per second. Frame skipping must
not overclock the emulator, remove enemies/attacks, shorten animation rules,
or treat repeated video frames as completed simulation updates.

The current candidate implements engine-owned catch-up for 3/4P BC. The tested
NTSC routes meet the updated simulation-rate target, but presentation can fall
to about 9 Hz in crowded fixtures. This must not be described as smooth 50 fps.

## Latest integrated build — bc389f61 (Normal and Boss Rush catch-up)

ROM: `bc389f613b23cc724217728db34020da9d333f072da1b90151108c4614a13566`.
The same bounded Normal scheduler now also serves Home Boss Rush. Both protected
HuCard runs defeat all 12 bosses through player fire, without injected kills or
assisted boss damage. The 3P run completes 17,710 updates; 4P completes 23,802.
Their minimum five-second simulation rates are both 58.32 updates/sec, versus
31.36/29.36 in the preceding cartridge. Every canonical gameplay-state sample
matches its baseline (private boss internals are outside those hashes). Both
runs have zero software sprite drops and zero audio underruns.

The three targeted 4P Normal regressions pass at minima 52.73–59.12 updates/sec.
Two still have brief upload misses (14 and 10); the former worst section9 HuCard
case has none. The earlier full40-case Normal matrix retains hash965be78d and
must not be presented as a full matrix on this cartridge.

Native Team Player 4P NTSC and3P/4P PAL Rush launch, save/reset and migration
checks pass. The native Rush guard audit checks8,121 flushes,83,292 HUD writes
outside the DMA guard, and194 catch-up entries with no queued DMA. Main
`make all` and the clean `tools/check` rebuild reproduce the isolated candidate
exactly, with no source/header warnings. Interim test package:
`.local/candidates/Side-Arms-MD-expansion-v14-rush-bc389f61-test.zip`. Evidence:
`.local/normal-frameskip/rush-full-probe/summary.json`, `rush-native-guard/`,
`rush-native-pal/`, and `rush-integration.json`.

### PAL timing interpretation correction

The preceding965be78d stressed Normal PAL run maintains49.7097 updates/sec over
5,999 video frames against the core's49.7015 Hz cadence. Its worst five-second
window is47.7054, but there is no cumulative slowdown: update-boundary timing
ranges from six frames ahead to five behind and finishes at its starting offset.
The region-specific threshold experiment maintains49.7346 overall and48.7034
in the worst five seconds, with identical gameplay states, but adds sprite
misses. It is not retained. The older statement that these short windows alone
prove loss of sustained native cadence was too strong. The timing spread remains
reported; this is not a claim of50 distinct displayed frames/sec or a physical
hardware result. PAL's nominal50 Hz target differs from the NTSC rolling50 gate.

The early2427a959 Rush experiment used a stale4608-byte guard constant after a
source copy preserved timestamps. A native-byte comparison identified this; the
retained bc389f61 rebuild uses4096 and has fresh full-Rush evidence. Earlier
hashes retain their exact measurements and are not source-reproduction claims.

## Normal catch-up integration — 965be78d

Candidate ROM: `965be78d5455fe843e39a588fbae63fd4c01992d7d541a364dccb6ae8902d2a9`.
The 3P/4P Home Normal scheduler now catches up at most eight simulation updates
per presentation, polling controllers between updates. It forces drawing before
another update when DMA is queued or the last picture streamed more than 2 KiB
of sprite patterns. The existing 6 KiB sprite upload limit is unchanged. Menus,
world freezes, stage transitions and other session owners stop catch-up.

All 40 protected AUTO-fire fixtures (ten section warps, 3P/4P, Arcade/HuCard)
pass the 50-update rolling five-second gate. Minimum 55.13 updates/sec; average
presentation rates range 30.44–59.92 pictures/sec. All 20 Arcade canonical-state
sequences match 03a94363, as does the separately compared HuCard section 9 case.
There are zero HuCard audio underruns. Two 3P section 10 fixtures naturally return
Home at 5,712 updates; the other 38 fixtures reach 6,000. This is bounded route
coverage, not full unassisted campaign acceptance.

Two cases retain brief sprite-upload misses: 4P section 7 Arcade has 10 versus 8
in 03a94363, and 4P section 4 HuCard has 6 versus 19 in its fresh baseline. All other
38 cases have zero software drops. The 4P section 9 problem is reduced to zero
with either soundtrack. Hardware scanline clipping is separate from these
software counters. The remaining misses are not considered fixed.

Native Team Player Normal 4P NTSC and 3P/4P PAL launch/save/reset/migration tests
pass without logical pad injection or audio underruns. The NTSC native audit
observes 7,598 guarded-or-HInt-disabled DMA flushes, 81,557 HUD writes outside the
guard, and 580 catch-up entries with no pending DMA. This checks the retained
v1.4 guard in Normal gameplay; it is not physical EverDrive certification.

Evidence: `.local/normal-frameskip/guard4096-matrix/matrix.json`,
`native-guard/result.json`, `native-pal/{3p,4p}/result.json`, and the drop traces.
The stricter 5 KiB threshold is rejected for 49.74 updates/sec in section 9 HuCard;
the intermediate 4.5 KiB threshold moves additional upload misses into that scene.
Main `make all` and `tools/check` both reproduce this exact candidate; the
clean build has no source/header warnings. Fresh BC R1/R7 4P HuCard fixtures pass
at minimum51.33/54.33 updates/sec, with no underruns. The remaining-mode check
finds Rush HuCard below target (3P33.16,4P29.36), and the stressed PAL Normal4P
section9 HuCard fixture reaches47.71 versus native49.70 Hz. These are open
performance failures, not passes. The isolated Rush catch-up ROM2427a959 passes both samples at minimum58.92,
with identical canonical states, zero software drops and zero underruns. It is
not integrated. A separate region-aware threshold experiment8e918432 improves
PAL to48.70 but still misses native cadence and is not promoted. Evidence: `.local/normal-frameskip/integration.json` and
`final-regression/summary.json`.
Interim test package: `.local/candidates/Side-Arms-MD-expansion-v14-normal-965be78d-test.zip`.
It explicitly lists the remaining Rush/PAL failures in the retained ROM.

## Previous integrated test build — 03a94363 (BC turret-cap composition)

ROM: `03a943633267d935f94ec4bbc2c8eb704ebf1318baee396dd62377577092acbd`.
The main asset/build pipeline now regenerates the precomputed cap patterns
through `tools/bc_cap_patterns.py`. Main `make all` exactly reproduces the
tested isolated candidate. It includes the existing red-ring repair, BC frame
skipping, HuCard soundtrack, multiplayer modes and v1.4 EverDrive source fixes.
`tools/check` completes with no source/header warnings and reproduces the same
ROM. Test package:
`.local/candidates/Side-Arms-MD-expansion-v14-compositor-03a94363-test.zip`.

The compositor combines identical overlapping turret caps only when row order,
fetch width, cache availability and transfer safety permit it. Actors, attacks
and collision processing are preserved. Host checks pass 992 compositor
fallback/offset/flip cases and 159,360 existing strip-splicing cases. Exact-ROM
timing and live-pixel evidence is recorded in the compositor sections below;
this is a bounded improvement, not elimination of all sprite clipping.

Fresh integrated-ROM checks pass all 21 HuCard Sound Test selections in both
regions, 12 native-adapter 3P/4P Normal/BC/Rush launch/save/migration cases, an
autonomous BC music transition, and four cold/dirty boot-reset region cases.
There are no audio underruns. The R7 native-controller DMA check verifies 1,976
flushes and 3,096 empty-queue catch-up entries; HInt is disabled in that fixture,
so this does not replace Normal-mode raster verification.

Evidence: `.local/final-compositor-03a94363/`, including `integration.json`, `summary.json`,
`status.json` and `dma-guard/result.json`. Fresh audio comparison:
`.local/hucard-audio-review-03a94363/index.html`.
Remaining work includes current Normal/Rush performance acceptance, broader
sprite crowding, blue-effect shading and final scope-wide acceptance. Earlier
campaign results retain their original ROM hashes; no full current-ROM campaign
or physical-console certification is claimed here.

## Historical Normal/Rush baseline and earlier catch-up experiments

Current 03a94363 protected AUTO-fire fixtures cover 3P/4P Normal from all ten
section warps and two 6,000-update Rush runs. Eight Normal fixtures miss the
50-update rolling target: 3P section 7 and 4P sections2,4,5,6,7,8,9 (one-based).
The worst sampled five-second rate is 31.56 updates/sec in 4P section 9, despite
a 54.53 average. Both Rush samples stay above 58.52; they do not cover every
boss. The 3P section 10 fixture returns Home at update5,712 and is reported as
a bounded Home-return run rather than forced to reach 6,000 updates.

The timing tool now records actual refresh rate, update-boundary video times,
rolling five-second rates, presentation cadence and optional drop samples.
It recognizes the current out-of-line input-update function and retains the
legacy full-speed exit convention. A targeted CPU profile of the slow section 9
window matches all6,001 state hashes and video timestamps from its unprofiled
run. Actor updates, drawing and the following blank wait dominate that window.
Evidence: `.local/normal-rush-performance-03a94363/summary.json` and its profile.

An isolated Normal-only catch-up prototype preserves simulation and polls input
between updates, forcing presentation on queued DMA or an ineligible flow state.
An eight-update cap passes all eight slow fixtures with identical state hashes,
but raises section 9 software drops from1 to12. A two-update cap, hash
`f0b3dcc45405d938684c39e4dde00febe5d078e880cb810988c217305d0dd562`,
also passes all eight (minimum51.13) with every6,001-state sequence matching.
It lowers section 9 drops to4, all in one transfer-budget-exhausted draw, but
that is still above the retained build's1. Section7's drops fall from8 to0.
The prototype is not promoted. Native-controller, transition, HUD/background
and DMA/raster checks also remain. Main ROM remains03a94363.
Evidence: `.local/normal-frameskip/status.json`, `two-matrix/matrix.json`,
and `two-4p-8/result.json`; all jobs are terminal.

## Previous retained test build — 082f88aa (red-ring shading)

ROM: `082f88aac2da4bcf6d6eb929df20710fefc9c94f95bc53112a50254b359a7111`.
The final Normal enemy death-ring pose (code1F6, palette8) and its four small
pieces now use the existing dark-red sprite palette. This restores four
visible shades instead of two. Source RGB3 squared color error falls from
0.84371 to0.05739; geometry and opacity are unchanged. The preceding seven
animation poses retain their original mappings after comparison.

Main `make all` reproduces the independently prepared candidate exactly.
Only403 ROM bytes change versus a677fc8a, within five existing pattern blocks,
five lookup entries and the checksum. Runtime code, palettes, sprite sizes,
pattern counts and other assets are byte-identical. No new storage or draw
work is added. Performance/campaign evidence below belongs to a677fc8a;
this is a bounded artwork-only successor, not a fresh whole-campaign claim.

Independent checks cover2,048 source pixels, Standard/Vivid ramp ordering,
exhaustive supported BC actor-selector isolation, and imported/player keys.
A real Home/Normal emulator launch with an injected death pose verifies the
native SAT palette and512 uploaded pattern bytes, with zero remaps/drops.
The historical spare-pen verifier could not be reused with its old baseline
because of previously changed Vivid colors; no new pass is claimed for it.

Evidence:`.local/red-ring-shades/status.json`; comparison:`family.png` there.
The blue energy effects and broader final acceptance remain open.

## Current-build HuCard acceptance refresh

082f88aa passes all 21 Sound Test selections in both regions, 420 packet checks
per region, zero underruns and all 12 3P/4P Normal/BC/Rush launch/save/migration
combinations. These launch checks use the emulated Team Player adapter without
logical input overrides. BC pause preserves music playback; the autonomous
stage/boss request waits at most two frames. Source/current listening controls
also pass, using new captures from this exact ROM.

Evidence:`.local/final-audio-082f88aa/summary.json`.
Review:`.local/hucard-audio-review-082f88aa/index.html`.
This closes stale-ROM playback/listening-page provenance. It does not claim
subjective listening approval or replace full-campaign evidence.

## Current-build Round5 parallax check

The 082f88aa linked background exactly matches the previous separation study.
Keeping the original background only in the HUD rows prevents holes but
introduces a texture seam: 30 of 160 sampled camera/phase cases gain boundary
discontinuities. This offline workaround is rejected; the retained ROM is
unchanged. Evidence: `.local/bc-r5-hud-protection-082f88aa/hud-protection.json`.
Additional BC parallax remains conditional on a correct, affordable layer
design; this check does not establish runtime timing or full route coverage.

## Current-build Round7 sprite-pressure refresh

082f88aa completes a protected four-player Round7/HuCard fixture with 1,800
engine-frame calls, 6,976 simulation updates and 6,985 video frames. Final RAM
matches a separate uninstrumented replay exactly. The post-upload audit samples
1,799 presentations: ten exceed 20 sprite entries on a line and 658 exceed the
320-pixel sprite-width budget. Software drop/remap counters remain zero.
These are hardware demand counts, not final-screen missing-pixel counts.

At captured tick3,533, the limited sprite plane omits 893 opaque pixels relative
to unlimited composition. An independent invocation of the pinned native core
matches all 224 lines of that model exactly. Removing the only completely
hidden/offscreen sprite recovers no pixels. Hypothetically trimming every
transparent outer tile row/column in that snapshot also recovers none. The
cropped variant preserves unlimited composition but has not been uploaded or
tested in runtime; no sprite change is retained. This rules out those two
simple fixes for this particular snapshot, not for every scene.

The profiler now verifies duplicated hoisted frame-call initialization through
control-flow paths and accepts up to eight updates per catch-up frame. Its
regression checks reject paths bypassing initialization, register overwrites,
implicit MOVEM restores and unverified indirect branches. Timing remains
reported per engine call separately from simulation updates.

Evidence: `.local/current-sprite-pressure-082f88aa/result.json`,
`visibility.json`, `native-visibility.json`, and `border-crop.json`.
The ROM remains unchanged. Hardware sprite crowding is still unresolved;
this fixture does not establish full-campaign visual acceptance.

### Overlapping-pattern composition opportunity

A source-preserving pair-composition study on that same tick3,533 snapshot
recovers 570 of the 893 omitted sprite-plane pixels; 323 remain missing.
Eight greedy merges reduce 50 entries to 46. Each candidate uses the same
palette and priority, overlapping bounds, and no more than two legal hardware
pieces. Every accepted step preserves the entire unlimited sprite image,
including palette/priority values and submission-order effects. Of 321 pair
trials, 233 preserve that image; the others are excluded.

Independently repacking the final patterns into scratch VRAM and invoking the
pinned native sprite renderer reproduces all 224 lines exactly. This establishes
a rendering opportunity, not a usable runtime implementation. The final set
has eleven generated pieces totaling 1,984 pattern bytes; it still needs a
bounded compositor, available VRAM/cache storage, DMA budgeting, and measured
CPU cost against the 50-update requirement. The full sprite inventory in this
isolated test occupies 12,224 pattern bytes. No production ROM change is made.

Evidence in `.local/current-sprite-pressure-082f88aa/`: `merge-study.json`,
`native-merged.json`, reproducible scripts, and `merged-comparison.png`.

A second native capture adds cache-resource observations using cache offsets
derived by the target compiler. Its SAT/VRAM snapshot matches the previous
capture exactly and its uninstrumented replay matches final RAM. At tick3,533,
six large and 45 small slots are unpinned, with 5,632 DMA-budget bytes remaining.
A more bounded study excludes recursive merges, caps each pair at 512 pattern
bytes, and rejects any pair that would cross an overlapping intervening sprite.
It recovers 485 pixels (408 remain omitted). Its eight combinations fit six
available large slots and two available small slots, reserving 3,328 VRAM bytes
and uploading 2,112 bytes. The allocation overlaps no live sprite patterns.
This is snapshot feasibility only: queue capacity, source-buffer lifetime,
compositor RAM/CPU cost and the 50-update performance gate remain unproven.
Evidence: `.local/sprite-compositor-capacity/capacity.json`, `abi.json`,
`capture/result.json` and repeatable scripts. No ROM change is installed.

### Isolated turret-cap compositor prototype

The isolated workspace now contains a bounded runtime prototype for identical
overlapping BC turret caps. It permits at most four combinations per picture,
checks intervening sprite bounds before changing order, and uses only unpinned
cache slots. It preserves actors and collision processing. A first version
building pixels on the CPU failed the speed gate (38.14 updates/sec average,
25.57 minimum five-second rate) and is rejected.

The replacement uses 13,568 bytes of precomputed ROM patterns. Prototype hash
`876ebb1aa671c2c1ca80d3a87b2da36d1042453cfb8754dcaff3654a2d30ca3c`
passes the 6,000-video-frame four-player NTSC Round7 fixture at 59.46 updates/sec
average and 54.93 minimum five-second rate, with zero HuCard underruns. All 124
linked offset/flip variants match independent source composition (54,272 pixels).
A separate 1,800-engine-call fixture observes 977 runtime combinations, zero
software drops/remaps, and final RAM identical to an uninstrumented replay.
This replay proves observer neutrality, not equivalence to the retained ROM.

The main ROM remains 082f88aa. Before promotion, the prototype still needs live
before/after sprite-plane equality, actual pattern-upload and cache-fallback
checks, broader regressions, and a reproducible asset-generation step. Its
scanline-demand counts cannot be directly compared with earlier fixtures whose
presentation/input sampling changed. Evidence and archived code/ROM are in
`.local/sprite-compositor-runtime/`, summarized by `status.json`.

Live checks subsequently confirmed 977 combinations preserved the intended
sprite image and native post-DMA SAT fields; 7,000 controlled simulation updates
also matched 082f88aa's canonical state exactly. However, the limited sprite
plane gained 5,112 pixels while losing 292 elsewhere, including five pictures
with a net loss. That prototype is therefore not suitable for promotion.

The revised isolated candidate
`ef5c678360126934d51a39b9cffb9cce4a9ce7b020456d95391edd60497a547a`
rejects pairs crossing intervening sprites on the same rows and conservatively
requires enough remaining scanline fetch width for the combined pattern.
Across 1,798 checked presentations, 398 combinations preserve 25,446,400
compared sprite-plane pixels in 355 changed pictures. The limited-plane model
recovers 1,320 pixels and loses zero previously visible pixels. Native SAT
uploads match, and the instrumented/uninstrumented final-RAM replay passes.
The 6,000-video-frame timing fixture achieves 59.12 updates/sec average and
53.73 minimum five-second rate, with zero audio underruns. Linked pattern data
is byte-identical to the independently verified 124-case predecessor.

This remains an isolated, protected four-player NTSC Round7 result, not a
full-scene clipping fix or general release gate. Broader regression, explicit
cache/queue fallback checks, canonical-state replay of this revised candidate,
and reproducible build integration remain. The main ROM is still 082f88aa.
Evidence: `.local/sprite-compositor-runtime/guard-status.json`,
`guard-live-r7/`, `guard-timing-r7/`, and `replay-comparison.json` (the latter
belongs to the unguarded predecessor).

The ef5c6783 guarded candidate subsequently matches all 7,000 canonical
simulation states against 082f88aa under identical per-update input
(`guard-replay-comparison.json`). Fallback review found the new compositor
claimed a cache entry before checking DMA enqueue success. The latest isolated
candidate moves the claim after successful enqueue and rejects a source transfer
crossing a 128 KiB DMA bank boundary, preserving original sprites on failure.
Host tests exercise 992 offset/flip/fallback cases, including rejected enqueue,
cache exhaustion, insufficient byte budget, row-order/fetch guards and 2P bypass.

Latest isolated hash:
`03a943633267d935f94ec4bbc2c8eb704ebf1318baee396dd62377577092acbd`.
All ten 4P NTSC rounds pass the 6,000-video-frame timing fixture; the minimum
five-second rate across them is 50.34 updates/sec. Additional R7 3P NTSC and
3P/4P PAL fixtures complete without underruns (PAL uses nominal50/native49.70 Hz).
The live R7 check observes 429 combinations across 1,798 presentations, preserves
24,514,560 compared pixels in 342 changed pictures, and recovers 1,368 limited
sprite-plane pixels with zero newly lost pixels. Native SAT uploads and the
instrumented/uninstrumented replay match. The canonical-state comparison above
belongs to ef5c6783; it is not relabeled as a new-hash test.

The candidate is still isolated. Reproducible build integration and final
cross-mode/boot/audio regression remain before promotion. All these jobs are
terminal; main ROM stays 082f88aa. Latest evidence:
`.local/sprite-compositor-runtime/queue-status.json`, `region-matrix/`,
`queue-live-r7/`, and `fallback-result.json`.

## Blue-effect palette study — current ROM unchanged

The seven blue death/explosion poses still have shade collapse. Fixed spatial
dithering improves four-by-four average color error but visibly checkerboards
the orbs; that trial is rejected. A single replacement palette color improves
selected poses but would displace grey used by other sprites; it is not installed.

An exact-color feasibility search finds no two-bank,15-opaque-color allocation
that preserves the current linked Normal sprite color combinations and adds
both proposed blue/cyan shades. It exhausts7,726,160 assignments even with text
colors free to change banks. Each proposed shade alone also fails3,268,760
assignments. The unmodified-palette control is feasible. This is a bound on the
specified inventory/constraints, not a claim that every possible rendering or
quantization method is impossible. It excludes background/HUD and BC-index
constraints, which would add restrictions rather than relax this necessary test.

Evidence:`.local/blue-effect-shades/status.json`, `comparison.png`,
`exchange.png` and the repeatable scripts beside them. No sprite/palette/runtime
bytes changed, and the red-ring correction remains retained. Further improvement
requires a verified narrower live inventory or a reviewed color/renderer tradeoff.

## Previous retained test build — a677fc8a (BC frame skipping)

ROM: `a677fc8a61a9cab26159e59c2d4aa5e9b110f76a847dbe9de8e9d26cad2f286b`.
Package: `.local/candidates/Side-Arms-MD-expansion-v14-frameskip-a677fc8a-test.zip`.
Main `make all` reproduces the isolated cartridge exactly. The v1.4 EverDrive
source fixes and existing artwork/audio remain in this build.

The regular engine owns a bounded eight-update catch-up batch; controller
polling/mapping advances per update. BC defers drawing while behind, but forces
presentation for queued DMA, menus/continues and scene handoffs. Eliminated
teammates alone no longer disable catch-up. Normal/Rush scheduling is unchanged.

- All ten 4P NTSC round fixtures: 6,000 measured video frames each after warm-up.
  Lowest rolling five-second rate 51.13 simulation updates/sec; average
  presentation cadence 8.8–24.6 Hz. Those are separate metrics.
- R3/R7/R8 4P and R7 3P PAL fixtures:near-native 49.70 Hz average simulation,
  minimum rolling five-second rate 49.30; no HuCard underruns.
- 10,300 canonical per-update states match 083b48ac across R1 and R7.
- Native emulated TeamPlayer input edges, all-controller pause/freeze/resume,
  Home re-entry/reset, stack separation and DMA atomicity pass. BC catch-up
  begins with an empty DMA queue; transfers are guarded or HInt is disabled.
  BC has no active HUD HInt, so this is not a fresh Normal raster audit.
- Cold/dirty reset passes in NTSC/PAL. All six protected/assisted 3P/4P
  Normal/BC/Rush campaign regressions pass. BC reaches all ten rounds, credits
  and Home. Worst 1,000-update BC windows: 3P 57.62/sec, 4P 51.44/sec.
- R7 post-presentation audit: 1,546 samples, 1,894,480 visible tile checks and
  28,881 resident pattern checks; no background-cache corruption.

Evidence and limitations: `.local/bc-frameskip/status.json`. Reusable timing
check: `tools/qa_bc_frameskip_timing.py`; it fails NTSC below 50 in a rolling
five-second window. These fixtures are not every possible input route. Physical
EverDrive certification is not claimed. Hardware sprite crowding and remaining
visual/listening/parallax acceptance still require a final scope audit; the
whole expansion remains incomplete. Older strict 60 fps failures below are
historical and do not override the user's updated requirement.

## Current shading audit correction — a677fc8a

The global audit now reads the linked cavern lower palette and separates the
upper/lower authored-route masks. The old fixed-palette audit misread the
cavern conversion. All 4,738 non-cavern records are unchanged by this audit
correction. Cavern off-route pixels and live raster timing are excluded;
this does not replace the earlier runtime pixel checks.

Current BC recolor verification covers 144 records, 90,624 linked pixels,
335 ordered ramps and 1,435 visible shade steps in Standard/Vivid. It passes.
The shared Normal sprite inventory still contains visible flattening: blue
energy examples at source palette7/codes1C6 and1D0 and a red ring at
palette8/code1F6. The source/current contact sheet confirms the visual loss;
actual runtime use must be checked before selecting repairs. These are
specific remaining examples, not a claim that every palette merge is a defect.

Evidence: `.local/final-a677fc8a/status.json` and
`worst-sprite-shading.png` in that directory. The ROM remains unchanged.

## Previous retained test build — 083b48ac (cavern shading)

ROM: `083b48ac269853be74a0fa67350e0c3291e0c9a63c394c50b647622e7bd60cc9`.
Package: `.local/candidates/Side-Arms-MD-expansion-v14-cavern-083b48ac-test.zip`.

The reproducible cavern generator and repeated-frame palette split are now in
the main workspace. Main `make all` produces the exact isolated/tested ROM.
All six protected 3P/4P Normal, BC and Rush progression checks pass on this hash;
Normal/Rush use assisted boss-hit fixtures. Real controller soft reset from an
injected cavern view, Home launch into BC, and return to Home pass in Standard
and Vivid, with 32 BC CRAM words verified and no lingering cavern raster writes.

Both background planes match 6,059,326 pixels across 115 sampled route views,
excluding HUD rows and sprite rectangles. BC art binaries are unchanged; the
regenerated Vivid LUT retains two additional source colors to preserve shading.
All ten BC rounds pass native palette checks in both color modes. The package
includes verification records and verified checksums. Native DMA/restore tests
on the preceding hash cover identical runtime code; its only five byte
changes are in the Vivid LUT and cartridge checksum. The current hash also passes all 22 safety/audio jobs: NTSC/PAL cold and dirty
RAM reset; 20,329,102 traced Z80 instructions (maximum PC 0B13); 10,000 frames
of HUD protection; all 21 HuCard tracks in both standards; 12 mode/player/region
launch cases; and plain/HuCard stack checks. Evidence: `safety/status.json`
under the cavern verification directory.

The expansion is not release-complete. Crowded multiplayer performance and
remaining whole-project release requirements still need review. The measured
cavern route costs about 2% more video frames than b3d03cbc. No physical hardware
certification is claimed. Evidence: `.local/cavern-v14-raster/release-result.json`.
All campaign, lifecycle, build and packaging jobs are terminal.

## Previous retained test build — b3d03cbc (v1.4 integration)

ROM: `b3d03cbc40b3a9dee6a10262eac37038bcaa09a992e016c26632d34d81692127`.
Package: `.local/candidates/Side-Arms-MD-expansion-v14-b3d03cbc-test.zip`.

Integrated all upstream changes through `e52d280` into the existing expansion,
including v1.3 combined autofire with four-player-aware mapping. The source
checkout's Git history was not rewritten. Local additions and documentation
were preserved. Also corrected the SDK upload in a build-local source copy:
an instruction trace exposed a brief boot-time Z80 escape before the repair
hooks; with the exact upload, all 20,335,296 observed instructions stay below
`$2000` (maximum `$0B13`).

Passed NTSC/PAL cold and dirty-RAM reset checks; four-player Team Player
Normal/BC/Rush launches with HuCard music, zero underruns and saved settings;
combined autofire; 2,036 atomic DMA transfers; and 10,000 video frames of HUD
monitoring (9,360 guarded flushes, 356 blocked H-ints, 34,933 safe window writes).
All ten BC rounds retain their prior background pixels, palettes and collision
resources. Evidence: `.local/v14-integration/result.json` and linked reports.

The full 3P/4P Normal, BC and Rush progression checks also pass on this hash.
BC reaches all ten rounds, completes 5,760 credit updates and returns to Home;
its gallery palettes match the archived colors with no unmapped art or software
submission drops. These are protected runs; Normal/Rush use assisted boss-hit
fixtures. Both stack checks, reviewed recolors and the Standard intro pass.
All 21 HuCard tracks pass in NTSC and PAL with 420 published-packet checks per
standard and zero underruns. These checks do not establish subjective timbre.

A separate `make all` rebuild regenerates assets and produces a byte-identical
ROM. The package now includes the expanded validation summary. Current-hash
evidence is in `.local/v14-integration/regression/` and `reproducibility.json`.
All test/build processes are terminal. The outstanding art and crowded
multiplayer performance work remains; no new raster palette prototype was
included. No physical EverDrive test is claimed.

## Previous retained test build —8d5e4ffc

ROM: `8d5e4ffcbffff5560582bef6038de2982ff3fed497056260cc9f8ff967ca0af6`.
Package: `.local/candidates/Side-Arms-MD-expansion-8d5e4ffc-test.zip`.

HuCard instrument2 now uses YM algorithm5, feedback7, multipliers3/5/3/4 and
levels39/32/18/24. Measured harmonic-magnitude error falls about79% at full
level and stays below30% of the old error at0/6/18/36dB attenuation. Absolute
loudness error stays below0.44dB; no tested channel clips. More than99.5% of
output energy remains at harmonic bins, guarding against noise being hidden by
normalization. Phase and subjective timbre fidelity are not claimed.

The Z80 HuCard path now retains all six algorithm/feedback bits, excluding
stereo bits. Its linked5120-byte driver differs from2b by one mask byte; the
standalone sound cartridge has the identical driver and patch data. MAME
observes370 complete packets and15972 register writes over Title/Final Stage samples,
including four nonzero-feedback writes. The renderer preserves modulation depth
for supported nonlinear patches.524288 packet checks, all21 NTSC/PAL native
tracks and all12 regression jobs pass. The standalone sound test Makefile now
copies the generated pitch assembly, fixing its stale sync rule.

Three bounded HuCard BC routes preserve8600 simulation states and workloads.
Mean scene CPU increases0.0205%/0.0367%/0.0537% for R7-4P/R8-4P/R2-3P;
frames change7290→7315,964→960,4892→4887. This is a small measured fidelity
tradeoff, not a speed improvement. Full BC pilot completion ticks differ, so
aggregate campaign durations are not matched performance evidence. Normal
captures also group some transient events differently across video frames;
separate ordered music-start, section, boss-kill and flow-state sequences match.
The original failed equality assertions are retained in the study logs.

All156 linked generated binary resources, arcade sound banks and pitch tables
match2b. Existing artwork is preserved, not declared complete. Full make
reproduces this ROM; ZIP payload and every checksum are verified. Evidence is
`.local/hucard-alg5-study/`, including `accepted.json`, `linked.json`, `registers.json`,
`fm-timbre-qa.json`, and `regression/`. No jobs remain live. The broader visual,
multiplayer performance, conditional parallax and listening work remain open.

## Previous retained test build —2b9d5d6f

ROM: `2b9d5d6fd54c41079f1dd7f0b0c8f9c9b0b02f8cce8f917e993d4b7b3f422111`.
Package: `.local/candidates/Side-Arms-MD-expansion-2b9d5d6f-test.zip`.

This partial Normal background repair restores 117 stored pixels to exact RGB3
source colors across 18 metatiles in zones 1/6/8/10/14. It reuses existing
sprite palette banks without adding palettes or runtime logic. Opacity and
non-palette attributes are preserved, with no new checked Standard/Vivid
source-pair merges or componentwise-source brightness reversals. All 10 linked
BC rounds retain their materials, palettes and collision data.

Injected stationary camera checks cover all 18 affected metatiles, including
Home variants, with actual VRAM/CRAM verification. These prove renderer output,
not natural reachability. Two protected Normal 4P routes match 10,002 state
hashes and 10,000 scheduler rows against917; frame counts stay4076/6005.
The full Normal 4P campaign also passes the production background observer
for zones0/1/5/6/8/10/14; it naturally samples three repaired metatiles,
with other repaired tiles covered by the stationary fixture and bounded route.

All12 regression jobs passed: six3P/4P Normal/BC/Rush campaigns, paired stack
checks,21 HuCard tracks in both NTSC/PAL, reviewed recolors and Standard intro.
Campaign semantic results and observed durations match917. The full build is
reproducible, and ZIP payload/checksums are verified. Evidence is under
`.local/normal-sprite-palette-background/`, including `accepted.json`,
`linked-verification.json`, `camera-probes/result.json`, and `regression/`.
The before/after page is `index.html` in that directory.

This is a retained test build, not the completed expansion. Broader shading,
crowded multiplayer slowdown/sprite limits, conditional parallax and listening
review remain open. Validation is emulator-only as requested. No jobs remain live.

## Active Normal cavern shading experiment

The latest isolated ROM is
`a13be00dd82814aba567a4ec45ffed74d52114d04179672d06e7124a4a6bee1b`.
Its general HUD path now uses precomputed row commands in the assembly
interrupt; the obsolete C raster fallback is removed. A forced noncontiguous
row-mask fixture verifies 29,923 native window-register writes. Simple HUD,
general HUD and PAL timing fixtures each verify 960 settled frames with no
missing color sequence or source-derived color-use deadline errors. CRAM
pairs remain interrupt-atomic and DMA-guarded; all observed FIFO processing
falls within HBlank. Six shades remain distinct in each organic ramp in both
Standard and Vivid.

Independent VRAM decoding and framebuffer comparison verify 183,375 visible
high-priority opaque Plane B pixels per color mode across four route-camera
fixtures, with zero mismatches. HUD rows, sprite rectangles and low-priority
Plane B pixels are excluded, so this is not a whole-frame fidelity claim.
The retained ROM passes the same oracle as a control. All ten BC linked
scenery resources remain equivalent. Evidence:
`.local/cavern-v14-raster/hud-pixel-pal-summary.json` and its referenced reports.
Moving-camera fidelity, low-priority/far layers, fades/transitions, crowded-route
cost and generator integration remain pending. The prototype remains isolated;
the retained v1.4 cartridge is unchanged. These results supersede older
prototype hashes and general-HUD/PAL limitations below.

The subsequent HBlank probe found that the first raster prototype's writes
occurred during active display despite matching scanline numbers. The current
isolated version (`3826ef926d00e4e9ce9de2187223df3988ae9f52f9c618cca794215b64fcbf51`)
uses an interrupt every other line, polls an early horizontal-counter window,
and spreads the ten changes through the source-verified color-use gap. A bounded
event pointer permits delayed servicing without reading beyond the ten colors.
The HUD's simple split now tolerates servicing after its target line.

Across 8,935 observed writes, data instructions start at master cycles 364–647
and finish at 476–773 within the core's H40 HBlank interval (228–872).
Every FIFO entry is scheduled at cycle 820. The 960 settled fixture frames
have the expected per-frame slot sequences with no color-use deadline errors.
There are 138 deviations from nominal scanlines (one or two lines later);
these remain inside each slot's source-derived safe interval. All writes are
interrupt-atomic and outside the DMA guard. All ten BC linked backgrounds
remain unchanged. The four stationary fixtures still run 240 updates in
240 video frames each; crowded gameplay cost is unmeasured.

This remains **isolated and unaccepted**. Whole-frame pixel fidelity, general
HUD fallback, fades, PAL, transitions and generator integration are pending.
Current evidence and limitations supersede the earlier prototype figures below
in `.local/cavern-v14-raster/status.json` and `audit.json`.

The v1.4-based isolated prototype in `.local/cavern-v14-raster/workspace`
now contains the regional patterns and a native ten-color raster sequence.
Its ROM is `29b23540507e4a0d548ff286eb4814f31a9c765c63582e4b7cbc663d17aef84b`;
it is **not retained or packaged**. The first C interrupt handler missed
scanlines and produced wrong boundary colors. The smaller assembly handler
completed 1,063 ten-write frames (10,630 observed CRAM writes) on the expected
scanlines in injected stationary fixtures. Every observed pair was interrupt
atomic and outside the v1.4 DMA guard. All ten BC scenery resources remain
equivalent to the retained cartridge.

Four muted-enemy camera fixtures each maintain 240 updates in 240 video frames,
matching the retained build. That is not crowded-route performance evidence.
Whole-frame pixel comparison, HBlank placement, general HUD behavior, fades,
Vivid shade separation, transitions and generator integration remain pending.
An off-route synthetic camera shows invalid colors; the offline allocation
only proves route-masked fidelity. See `status.json`, `audit.json`, `timing.json`
and `bc-equivalence.json` in the prototype directory. All jobs are terminal;
the retained v1.4 build remains unchanged.

An additional exact-color repacking check on retained8d5e4ffc covers1741
base/Home/far consumers with240 distinct color sets. Unlike the earlier
single-pen removal check, it permits complete rearrangement of both background
banks and reassignment to either fixed sprite bank. Stars remain pinned.
The solver proves the minimum is30 background slots, with an objective bound
of30; independent set coverage verifies its solution. Thus exact preservation
of all existing colors cannot free a slot through bank rearrangement alone.
This does not prove a better shade-preserving approximation impossible.
Evidence: `.local/normal-organic-repack/solve.py` and `result.json`.
No generated assets or runtime files were changed by this check.

A subsequent existing-palette uniform-mapping test requires the four source
organic highlight colors to remain distinct in both Standard and Vivid, with
no new pair merges, previously ordered brightness inversions or increased
per-metatile RGB3 error. Four solutions pass independent pixel reconstruction;
visual inspection identifies them as blue backing and neutral machinery,
not the organic surfaces. The remaining nonempty selected metatiles are
infeasible under this restricted model. This is not a proof against arbitrary
per-subtile mappings or a redesigned palette. No repair is retained.
Evidence: `ramps.json`, `ramps-verified.json`, `ramps.png`, and `status.json`
in `.local/normal-organic-repack/`. All study jobs are terminal.

The follow-up joint allocation in `.local/normal-organic-global/` includes all
1741 base/Home/far consumers. It gives each organic source ramp six distinct,
strictly increasing Standard/Vivid shades and allocates both background banks
together, with sprite banks and star slots fixed. Exact non-ramp preservation
is infeasible in this model. Allowing non-ramp colors to move one RGB3 channel
step, while preserving their distinctions and componentwise brightness order,
is also infeasible. Allowing squared RGB3 distance2 instead ends UNKNOWN after
180 seconds, with no feasible candidate; this is not an impossibility proof.
The global source-pen and old-color mapping assumptions are restrictive and
can be relaxed to material-specific assignments. No palette or ROM change is
retained. `check.py` is prepared for independent reconstruction/rendering but
has not run successfully because there is no feasible candidate. Results,
solver duration/bound and terminal status are saved in that study directory.

The material-specific follow-up at `.local/normal-organic-material/` removes
the requirement that a stored non-ramp color use the same replacement across
different source materials. It preserves distinctions within each material.
Both an optimization run and a separate feasibility-only run end UNKNOWN
after60 seconds, without a candidate. These results do not prove infeasibility.
There is no visual improvement to claim and no production change. All jobs are
terminal; `status.json` records the next step as examining conflicting color-set
requirements or authored allocation, rather than repeatedly increasing solver
time limits.

Capacity diagnosis in `.local/normal-organic-capacity/` resolves one cause of
the failures. Under exact non-ramp preservation and uniform six-shade ramps,
the minimum maximum background-bank size is19 opaque colors (37 total),
versus the hardware limit15 per bank. Removing star reservations only reduces
that maximum to18. Correcting the duplicate purple source highlight pen14 to
follow pen6 leaves the19-color bound unchanged. An independent reconstruction
checks all1741 base/Home/far consumers, fixed sprite/star colors, both display
modes' ramp ordering, and the relaxed solution's source error24521→23327.
That palette is diagnostic only and cannot be rendered with the current banks.

Assumption-based diagnosis reduces the conflict to five color-set constraints:
base metatile12/subtile9,74/13,26/2,64/10 and88/5, plus matching consumers
including Home variants. This is a sufficient conflicting subset, not a proven
minimum. `conflicting-materials.png` shows source and retained tiles with the
relevant subtiles outlined. Before changing these materials, verify their
actual route visibility: zone rectangles contain padding, and runtime
`auto_zone()` retains a zone while the camera center remains inside it, so a
section5-only visibility estimate would not cover section6 transitions.
All jobs are terminal; no runtime or generated artwork changed. Bounds apply
to the tested static allocation model, not all possible Genesis techniques.

The follow-up `.local/normal-organic-visibility/` replays all generated scroll
legs with the MD viewport and current center-based zone retention. A continuous
protected/assisted Normal 4P native campaign then completes129285 video frames,
with128499 gameplay observations and10476 zone10 observations. Constraints
142/147/153/182 have displayed VRAM-pattern/template/flip witnesses; the two
purple witnesses use actual Home variants117/108. Constraint88 (meta12) never
intersects the displayed viewport in this campaign. Native section 4 corresponds
to source section5; no developer camera or stage warp is injected.

The route-model visibility masks exclude13 complete base metatiles and portions
of others. Re-solving only visible base/Home pixels plus the full far texture
reduces consumers1741→1525, but the minimum peak bank size remains19. Padding
therefore does not solve the tested allocation conflict. These masks do not
prove invisibility in every mode or BC donor use. All original campaign music,
boss progression and underrun checks pass. The cartridge is unchanged; jobs are
terminal. Evidence: `route.json`, `capacity.json`, `native/result.json`,
`native/visibility.json`, native conflict screenshots and `status.json`.

## Regional cavern palette allocation — offline feasible

`.local/normal-organic-regions/` tests separate palettes for the lower-right
cavern (world x>=1536,y>=2048) and other route-visible pixels. A whole-width
horizontal split leaves the lower bank requirement at16; the more precise
region fits both halves. With hardware-sized banks and source-error minimization,
all checked primary pink/purple ramp pixels become exact source RGB3 colors.
Independent reconstruction verifies804 upper/outer and713 lower base/Home tile
color sets. Bank sizes are14/14 and15/15.1737+13183 stored ramp pixels change;
their squared source error falls3474+20167→0. Non-ramp colors remain unchanged,
and star reservations and both sprite palettes stay fixed.

The source/retained/target image `comparison-0.png` visually restores the organic
gradients; it is an offline source-map rendering, not an emulator screenshot of
a new build. This result does not yet provide compatible palette slot placement,
pattern storage, a safe scanline switch, HUD/fade integration or performance
evidence. The current cartridge remains8d5e4ffc. Next work is common-slot
alignment and a boundary color-use schedule before runtime implementation.
All study jobs are terminal. Evidence: regional `fidelity.json` files,
`verified.json`, comparison images and `status.json`.

The next offline step jointly allocates both regions instead of assigning them
independently. With exact tested ramp colors and unchanged other colors, it
finds10 changed CRAM slots: bank0 slots9–15 and bank1 slots13–15. Star slots and
sprite banks remain fixed. The route model never requires the two regions
side by side on one scanline. Base and Home color-use intervals allow one write
before each world row2048–2057. A replay of those ten writes preserves every
checked used color; all far-map entries can use a bank and indices whose colors
remain stable across the switch. This is a pixel-use scheduling proof, not a
hardware HBlank timing proof. No interrupt code or generated game assets have
changed. Native address-port safety, HUD/fade integration, VBlank restoration,
pattern storage, region transitions and frame cost remain to be tested.
Evidence: `joint.json`, `camera-partition.json`, `assignments.json` and
`schedule.json` under `.local/normal-organic-regions/`; all jobs are terminal.

The retained2b9d5d6f ROM remains unchanged. A current-ROM R5 check confirms
five protected pink, purple and blue ramps; its six linked review views were
refreshed. The remaining Normal cavern flattening is a separate allocation issue.

An exhaustive zone10 one-pen removal study found no freeable background slot
while preserving all base/Home/far colors in the four existing palettes. A broader
offline four-bank fit pins every source color in pink/purple materials. It recovers
201 source-color pair distinctions within those materials, with no new merges
there, and reduces whole-base-atlas mean RGB3 channel error0.206858→0.154221.
However it introduces162 new pair merges elsewhere, mostly gold machinery and
neutral structural materials. It is not integrated or accepted. Home/far/Vivid
validation is deliberately not claimed. The next action is to resolve those
material regressions before considering an in-game candidate.

Evidence and source/retained/experiment views:
`.local/normal-organic-bank-study/{capacity.json,fit.json,status.json,index.html}`.

The follow-up constrained study independently reconstructed62 feasible base
metatiles with no new Standard/Vivid pair merges, ordering reversals or larger
per-metatile RGB3 error. Another34 fail the uniform source-color mapping model;
that restriction is not proof of general palette impossibility. Four machinery
controls pass a finer 8x8 model at their existing assignments; both tested organic
palettes fail those same four under that finer model, and the full-organic palette
also fails55/56/63. Earlier commentary claiming100/104 was premature after a
serialization failure; complete results supersede it. A simple horizontal raster
split is not established because machinery and purple art overlap in row7 and
the boundary cap also fails. All solver jobs are terminal; no ROM data changed.
Evidence: `solver-verified.json`, `tiles-baseline-fixed.json`, `tiles-trial.json`,
`tiles-flexible.json`, `tiles-boundary.json`, and `material-bands.json` in the
study directory. Next is a visual experiment with shade-aware spatial mixing
using existing colors, before considering more expensive runtime changes.

The subsequent ordered-mixing experiment was rejected on visual inspection:
its Bayer4x4 checker pattern is conspicuous in the purple rock. It is not in the
ROM. Evidence: `.local/normal-organic-bank-study/mix/{comparison.png,status.json}`.

All21 HuCard audition clips were freshly captured from retained2b9d5d6f through
Sound Test; clock, audibility, no clipping/underruns, stop, source-switch and
return controls pass. The PCE/current comparison page was refreshed at
`.local/hucard-audio-review/index.html`. All84 original/level-matched WAV files
were checked, and A/B control logic tests pass. Browser playback remains
unverified: the browser tool blocked the local-file URL. No workaround was
attempted, and no subjective listening claim is made. Evidence:
`.local/normal-sprite-palette-background/audio-review-verified.json`.

## Previous retained test build —91725541

Retained ROM is917255411ea129f514f569b3967d11be13c8f2a3e2d0a1331e7c5e536b4b528f;
It is retained as the latest test build;25177d55 remains available as the preceding package.
It repairs partial Normal opening industrial and stage4 organic shading, with
83/81 recovered source-color pairs, no new checked source-pair merges or
componentwise-source luminance reversals in Standard/Vivid. Across zones0/5,
96 metatiles improve their distinct-color count and none worsen. Mean RGB3
channel error rises0.096446→0.104206 and0.149983→0.156216; this tradeoff and
source/current/proposal images are in `.local/normal-shading-next/index.html`.

Four Normal binary blobs change; preserving BC's reused original patterns
adds7168 bytes to the shared BC bank and relocates subsequent code/data.
Independent resolved-material comparisons cover every mapped cell in all10 BC
rounds, their palettes and collision source code. All other linked binary
resources match. The original whole-ROM same-address check failed on this
expected bank growth; the new verifier explicitly proves BC material equivalence
instead and does not claim byte-identical runtime code.

Two protected Normal 4P routes match8002 state hashes and8000 scheduler rows;
4006/4091 display frames stay unchanged. Settled Vivid checks cover499 samples,
8540 resident pattern checks and15968 CRAM words in zones0/5. BC R7/R8 match4600
state/workload/scene-time rows and7290/964 display frames. Their scheduler timing
matches, but raw SP+4 words differ at entries with unknown calling convention;
these words are neither decoded as arguments nor claimed equal. The initial
whole-record comparison failure is preserved in the log. Full make reproduces
91725541 exactly.

All12 regression jobs passed and are terminal: all six3P/4P Normal/BC/Rush
campaigns, paired bounded stack checks,21 HuCard tracks in NTSC and PAL,
reviewed recolors and Standard intro. Both BC campaigns match the preceding
build's ticks, display duration and ending results. Normal campaign timing and
music events match. Full reproduction and the package payload/all checksums
are verified. Evidence lives under `.local/normal-shading-next/`: `accepted.json`,
`regression/package-verified.json`, `regression/campaign-comparison.json`,
`regression/stack-comparison.json` and the linked/native checks above.

Package: `.local/candidates/Side-Arms-MD-expansion-91725541-test.zip`.
The full expansion remains incomplete: remaining shading, crowded multiplayer
performance/sprite limits, conditional parallax and listening checks.
The zone12 study remains offline. Sprite-palette borrowing is now integrated
in an unaccepted working candidate, 2b9d5d6f. It restores 117 exact RGB3 pixels
across zones 1/6/8/10/14 without adding palettes or runtime logic. All 18
affected metatiles passed injected-camera renderer checks, and all 10 BC
rounds match retained materials. Reproduction and regression gates are in
progress; this candidate is not yet the retained test package.

## Previous retained test build —25177d55

ROM: `25177d5599eb7075dcbb5ce6b2e8b7327772dd6b2df4c166db244d2b7839c913` (4 MiB).
ZIP: `.local/candidates/Side-Arms-MD-expansion-25177d55-test.zip`.
ZIP SHA256: `8dca5015b07adce36da8ca9798b0752b32db68bf179bc2e2f5412c9273803f13`.

The partial Normal zone10 shade repair is retained. All12 regression jobs are
terminal and passed, including all six3P/4P campaigns,21 HuCard tracks in both
NTSC/PAL, paired bounded stack runs, recolor and intro checks. Both BC runs
match c7e8fe90's RAM/timing/ending results exactly; Normal total campaign frame
counts also match. Full make reproduces the cartridge, and the test ZIP payload
and every file checksum are verified. Only zone10 palette/pattern bytes and
checksum differ from c7e8fe90; code, audio, other art and Vivid LUT are unchanged.

It restores44 base/30 Home source-pair distinctions with no new checked merges
or luminance inversions. Far texture pixels stay identical. Mean RGB3 error
rises0.20221→0.20730; the visual improvement is partial, not complete shading
acceptance. Evidence: `.local/normal-zone10-fit/accepted.json`,
`linked-shading.json`, `native-comparison.json`, `campaign-comparison.json`,
`regression/package-verified.json`. No jobs remain live.

The full objective remains incomplete: remaining shading, crowded multiplayer
speed/sprite limits, conditional parallax, listening and hardware validation.

## Previous retained test build — c7e8fe90

ROM: `c7e8fe90d88e8ecb54bef338e9a3594c614dc90657093c2264029578dd7ff549` (4 MiB).
ZIP: `.local/candidates/Side-Arms-MD-expansion-c7e8fe90-test.zip`.
ZIP SHA256: `b7fe1ec0faf998b219c1d724c3645803b08f767b331acfbc68e12ed5d6049828`.

All twelve regression jobs are terminal and passed: six3P/4P campaigns,
paired bounded stack runs, NTSC/PAL21-track playback, reviewed recolors and
Standard intro. Both BC runs clear without forced boss defeats, complete
5760 credit updates, preserve gallery colors, and return Home. Full make
reproduces the tested ROM; package payload and every checksum are verified.

Round7 4P mean scene CPU improves4.053%, with7492→7290 display frames for
4000 matching state/workload/sprite-plane samples. Normal controls stay within
0.04% mean CPU; section8 takes one extra frame. Round8 4P takes two extra
frames and0.109% more mean CPU. These tradeoffs are explicit, not a universal
speed claim. Other tested BC controls improve. The candidate is now retained.

Evidence: `.local/bc-r7-specialized-space/v4-regression/accepted.json`,
`art-checks.json`, `performance-checks.json`, `package-verified.json`, and
`../v4-reproducibility.json`. Earlier running statements below are historical.
No jobs remain live. The preceding b72a065b package remains available.

The full expansion remains incomplete: crowded multiplayer speed, sprite
crowding, remaining shading (including the newly confirmed zone10 organic
highlights), conditional broader parallax, listening and hardware checks remain.

## Pending Round7 compiler specialization — c5078d7e

The working ROM is a candidate; b72a065b remains the retained/test-packaged
build below. A dedicated Round7 actor loop compiles the existing shared core
with a fixed round, plus an idle-launcher path enabled only in that compiled
loop. Other loop variants eliminate the launcher test. The original family
dispatcher still handles firing/transition ticks and alternate resource layouts.
8,192 three-update launcher cases plus192 guards match the baseline;7,099 PCE
actor loops (135,533 actor updates,521 children) match source captures.

To fit the4MiB window, the cartridge omits21,092 bytes of unreachable zone2/base
and Home storage. Source assets and numeric zone IDs remain. Its zero descriptor
and null Home pointer preserve all16,900 checked camera-centre selections;
no wheel descriptor selects it. All154 retained generated linked blobs and
all wheel map/extra data match b72a065b at their new addresses. Full make
reproduces the tested candidate exactly. This supersedes the initial temporary
generated-file experiment; the production generator now implements the omission.

The 4P R7 route preserves4,000 states/workloads and4,000 ideal sprite planes;
mean scene cost falls3.916%, with7,492→7,329 display frames. R4 takes1,070→1,065,
R6 1,106→1,100, solo R7 1,209→1,204. R8 takes962→964 despite0.179% lower mean
scene cost, so this is a mixed control result, not a universal timing gain.
All compared states/workloads match. The earlier fixed-round-only variant
improved R7 mean scene cost2.741%; the isolated launcher branch adds the gain
without the prior generic-launcher R4/R6 regressions.

All six c5078d7e campaigns, NTSC/PAL HuCard tracks, paired bounded stack checks,
reviewed recolors and Standard intro passed; all those jobs are terminal.
However, four Normal fixed-update controls preserve state/workload while mean
update CPU rises 0.67–0.93%. Disassembly shows flow_update unexpectedly inlined
into game_frame. The candidate is not accepted.

The f6308ad0 follow-up kept flow_update out of line but did not remove the
Normal regression. All its jobs are terminal. Instruction attribution instead
localized almost all of the extra cost to shot_move being outlined from Normal
weapons code. Candidate c7e8fe90 explicitly keeps that small per-shot step inline
and retains the flow_update boundary.

Its four Normal controls preserve all16,004 state hashes and16,000 workloads;
mean CPU differences are within0.04%, with frames4076/4033/4004/4473 versus
4076/4033/4004/4472 retained. R7 4P preserves4,000 states/workloads and ideal
sprite planes, improves mean scene CPU4.053%, and takes7290 versus7492 frames.
R4/R6/soloR7 improve, while R8 takes964 versus962 frames and costs0.109% more
mean CPU. These are measured tradeoffs, not universal full-speed acceptance.
Profile and Normal jobs are terminal. Full make reproduced c7e8fe90 exactly,
and the independent linked-asset/storage check passed. Full regressions are
running in session45324, isolated under v4-regression; inspect its running.json
and v4-regress.log for status. Do not rebuild while these readers run. Not retained.

Current v4 results: both Rush runs, paired stack replay, reviewed recolors,
Standard intro and all21 HuCard tracks in NTSC/PAL passed. Four Normal/BC
campaign jobs remain live. Additional settled background audits for zones9/18
match all8,002 state hashes and all scheduler rows against the same candidate
without the observer. Their exit1 is the pre-existing full-speed criterion,
not failed color/cache assertions. The independent storage verifier links the
retained source-shading evidence to unchanged current generated artwork.
Art/performance summaries are prepared in v4-regression; no package or final
acceptance has been issued. The fresh broad shading audit remains diagnostic:
there are still source-color merges to review, not a complete shading signoff.

Evidence: `.local/bc-r7-specialized-space/v2-comparison.json`, `storage.json`,
`reproducibility.json`, `running.json`, and `regress.log`. Not retained or final.

## Previous retained cartridge — b72a065b

Previously retained/test-packaged build: `b72a065b6dac97ca499e80b6c29a11ea39f2e0becbf0da8e72c54f9a9bd69b83` (4 MiB).
ZIP: `.local/candidates/Side-Arms-MD-expansion-b72a065b-test.zip`.
ZIP SHA256: `1f831983a873320c270465fe6f84e2a0b4e8fe603aed4a8eb8abea14aaf0be46`.

Selective Normal background repacking restores3,869 stored pixels across
zones1,2,4,9,18 to exact source RGB3 colors. Unselected colors, transparency,
geometry, star pens and existing Standard/Vivid shade distinctions are
preserved. Zone2 is contained inside earlier zone1 and is not selected by
ordinary camera/wheel paths; its65 repaired pixels are linked-asset maintenance,
not another demonstrated on-screen improvement. Active repaired zones account
for3,804 stored pixels. All 400 Home cutout subtiles and1,376 wheel extra subtiles
retain every displayed color. BC artwork and sprite patterns are unchanged.

The independent whole-ROM diff permits only the intended background data and
checksum: code, audio, symbols and Vivid LUT are identical to0b1d54e7.
`qa_normal_material_shading.py` checks the preceding material layer only after
independent verification of the selective layer and its exact input ROM.
Both material verifiers pass. Full make reproduces the tested cartridge;
the ZIP payload and every packaged checksum have been verified.

Four protected4P Normal routes,4,000 updates each, preserve16,004 state hashes,
all scheduler/workload records and4,076/4,033/4,004/4,472 display-frame counts.
Additional read-only input-boundary checks preserve8,002 states and timing,
verify47/19 settled samples in active zones9/18, and check1,247 resident pattern
blocks plus2,112 CRAM words. Continuous4P campaign samples verify zones1/4.
The first frame-end observer required unused zone2 and missed settled9/18
samples; its failed diagnostic is archived and is not counted as a pass.
A corrected full4P campaign and separate input-boundary checks pass.

All six current-ROM3P/4P progression checks pass for Normal, BC and Rush with
zero HuCard underruns. BC3/4 match the preceding build's complete timing and
ending results, including gallery palette samples and Home return. Normal
campaign timing/music events match; Normal/Rush use assisted hit paths.
All jobs are terminal. Evidence: `.local/normal-selective-shades/accepted.json`,
`summary.json`, `art-checks.json`, `performance-checks.json`,
`campaign-comparison.json`, `reproducibility.json` and `package.json`.
Review: `.local/normal-selective-shades/index.html`.

This is a verified test build, not final-release acceptance. Crowded4P speed,
hardware sprite crowding, remaining visual/listening review, conditional
parallax and physical hardware acceptance remain open.

## Previous retained cartridge — 0b1d54e7

Previous retained/test-packaged build: `0b1d54e71c4b0703c07a3f03ce815975d50ccf0817b5fea73091c1112bc2b836` (4 MiB).

Previous retained build: `376abb8b47bf0bb7fc46b1cd845ae289a9b2c8d1dcfc28bbbecb24f957ee1b3e`.

Normal sprite shades recover6,014 stored pixels across296 blocks/300 alias keys,
using two previously spare palette pens without adding pattern bytes. Independent
source decoding proves exact recovered colors, unchanged transparency and no new
Standard/Vivid merges. Exhaustive supported BC actor/boss frame/palette mapping,
imported keys and all player-page variants are protected. Only sprite_pal,
spr_bank and spr_big change among135 linked graphics blobs;132 remain unchanged,
including BC backgrounds/bosses. Gallery and boss palette inputs are isolated.

Native Normal 4P samples preserve1,201 states each and unchanged workloads:
opening1,200updates/1,200frames, section 9 1,200updates/1,221frames. Both baseline
and candidate miss full speed in section 9; this is equivalence, not a speed pass.
BC R7 preserves4,000 states/workloads and ideal sprite planes,7,492frames and
mean scene cost1,005,947.6. Six native capture comparisons preserve the top24 HUD
rows; this bounded check does not certify every HUD state.

All six protected/assisted campaigns pass. BC3:109,514updates/165,683frames;
BC4:121,109updates/206,850frames, matching the preceding build. Both complete
ten rounds,5,760 credit updates and Home return without forced boss defeats.
Normal/Rush use assisted hit paths. The native gallery CRAM observer matches
archived colors across5,820 3P and5,818 4P unfaded samples in explicit Vivid mode.
The initial gallery verifier had a ROM/RAM lookup bug; corrected full runs pass,
and failed diagnostics remain archived. They are not counted as passes.

All21 HuCard tracks pass NTSC/PAL checks. The bounded stack replay has no
overlap and matches its independent plain replay. Full make reproduces the
exact tested ROM. ZIP: `.local/candidates/Side-Arms-MD-expansion-0b1d54e7-test.zip`.
Evidence: `.local/normal-sprite-spare-shades/accepted.json`, `summary.json`,
`performance-checks.json`, `reproducibility.json` and `package.json`.
All jobs are terminal. Full-speed, remaining visual/listening review, conditional
parallax and physical hardware acceptance remain open. Earlier running/pending
statements below are historical and superseded by this acceptance.

A subsequent R7 idle-launcher shortcut was tested and rejected. It preserved
4,000 R7 states/workloads and ideal sprite planes, passed 8,192 three-update
host cases plus 192 scroll/state guards, and matched 7,099 captured PCE actor
loops. R7 mean scene CPU cost fell 1.27% (7,492 to 7,435 display frames), but
matched current-build R4/R6 controls increased mean scene cost 1.33%/1.21%.
R8 was unchanged; solo R7 improved 2.15%. This is not a retained optimization.
Evidence: `.local/bc-launcher-idle/comparison.json`, `controls.json`, and
`source-loop.json`. The full-speed requirement remains open.

The preceding376abb8b build retained the aligned HuCard active-channel check
with source/native equivalence, modest mixed timing improvements and six passing
campaigns. Evidence remains in `.local/hucard-active-word/`.

The preceding 527bfe25 build retained the grouped six-voice FM cache. Its
native packets, matched gameplay/planes, all six campaigns and exact full
rebuild passed. Evidence remains in `.local/hucard-voice-cache-layout/`.

The preceding ddf2af86 build retained aligned native-endian internal HuCard
channel words, with source capture equivalence, all six campaigns and an exact
full rebuild. Evidence remains in `.local/hucard-native-channel/`.

The preceding ed1e4e61 build retained deferred envelope-address calculation,
with matching source capture state, all tracks, six campaigns and exact rebuild.
Evidence remains in `.local/hucard-lazy-envelope/`.

The preceding 7d0a19e9 build retained a packed HuCard pan table with source-exact
stereo bits and attenuation. All pan/volume pairs, 524,288 packets, all tracks,
six campaigns and exact rebuild passed. Evidence remains in `.local/hucard-pan-table/`.

The preceding 37af9e5f build retained successful Round 7 curve-birth indexing.
Its measured spawn spike fell 7.15%, with identical compared gameplay states
and ideal sprite planes. Its six campaigns, art, sprite, bounded stack replay
and byte-exact full build passed; evidence remains in `.local/bc-curve-birth-index/`.

The preceding 8aba301b build removed an unused ROM key inventory and added the
idle R7 burst-turret fast path. Its matched R7 mean scene CPU cost improves
3.24%; R6 rises 0.31%. Its six campaigns and full-make reproducibility passed;
evidence remains in `.local/bc-burst-idle/`.

The preceding 5b678b7d evidence remains historical below. The reviewed pod uses one
source-exact 32x24 sprite, and cropped draw kinds are cached with animation
poses. All six protected 3P/4P campaigns, artwork checks, actor-cache checks,
159,360 SAT cases, crop flip checks and full-make reproducibility pass.
Normal/Rush results match af20e09c except ROM hash. The bounded R7 comparison
preserves 4,000 ideal sprite planes and all simulation states; entry-over-limit
line observations fall 13→9 and width-over-limit observations 25,081→24,313,
with 0.18% higher mean scene CPU cost. R8 stays at 1,013 frames. The native
snapshot check is at tick3487, not the preceding build's tick3481; its missing
pixel count must not be compared directly. Evidence:
`.local/bc-short-pod/accepted.json`, `sprite-checks.json`, `summary.json`,
`normal-rush-comparison.json`, `reproducibility.json`, and `package.json`.
ZIP: `.local/candidates/Side-Arms-MD-expansion-5b678b7d-test.zip`.
The retained ROM, ELF, symbols and headers are archived under `retained/` in
that evidence directory. Remaining crowding/performance acceptance is open.

The following describes the preceding af20e09c build. The source-exact surfacer crop
uses one 32x16 entry and half the pattern upload bytes. All six protected 3P/4P
campaigns, artwork checks, four-flip pen checks, matched bounded sprite/state
traces and exact full-make reproducibility pass. Compared with b03fb25e, the
R7 fixture reduces entry-over-limit line observations60→13 and width-over-limit
observations27,735→25,081, with0.52% higher mean scene CPU cost. The reference
snapshot recovers another51 missing sprite-plane pixels (442→391). Hardware
crowding remains; these counts precede background/window composition.
Normal/Rush results match b03fb25e except ROM hash. Evidence:
`.local/bc-short-surfacer/accepted.json`, `sprite-checks.json`,
`normal-rush-comparison.json`, `summary.json` and `package.json`.
ZIP: `.local/candidates/Side-Arms-MD-expansion-af20e09c-test.zip`.

The following b03fb25e measurements describe the preceding build. Its recorded
BC spike-strip renderer recovers 201 missing sprite-plane pixels in the crowded
R7 reference snapshot; the matched R7 route reduces width-over-limit line
observations by 31% at a 2.3% mean scene CPU cost. All six protected 3P/4P
campaigns, artwork checks, 159,360 SAT link/fallback cases and exact full-make
reproducibility pass. A 4P R7 stack observation has zero overlaps, with a
12,968-byte minimum gap; its uninstrumented replay matches RAM/frame/tick state.
Campaign completion times changed and are not equal-state CPU benchmarks.
Hardware sprite crowding remains, and this is not full-speed or final-release
acceptance. Evidence: `.local/bc-spike-recorded/accepted.json` and related files.
ZIP: `.local/candidates/Side-Arms-MD-expansion-b03fb25e-test.zip`.


The preceding da75 build adds74 exact source-shade pixels in Normal zone3
(stage3 cave) through existing palette banks. No previously distinct displayed
colors merge in Standard or Vivid. All684 BC background cells, the Vivid LUT,
stars, collision data and symbol addresses remain unchanged. Exactly61 ROM
bytes change, confined to zone3 tiles/attributes and the cartridge checksum.
Full make reproduces the build. A matched four-player Normal section3 replay
passes4,000 updates in4,028 frames with every reported field equal except ROM
hash. This is bounded validation, not full-speed or full-campaign acceptance.
Evidence: `.local/normal-local-shade-repair/accepted.json`, `materials.json`,
`local-verification.json`, `rom-scope.json`, `normal-comparison.json` and
`comparison.png`. All jobs are terminal. Current-hash campaigns and repackaging
now pass for all six protected3P/4P modes, with zero HuCard underruns and every
reported field identical to0a981d93 except ROM hash. Artwork checks pass too.
The new verified ZIP is `.local/candidates/Side-Arms-MD-expansion-da75dc6a-test.zip`
(SHA256 `e23c172be2d18609de5efcec3e9b572e9ab34bde7bce2376c0cba03f953bca56`).
Evidence: `.local/da75-campaigns/summary.json`, `comparison.json`,
`art-checks.json` and `package.json`. This supersedes the prior test package;
full-speed, remaining visual/material review and conditional parallax
acceptance remain open.
The instrument21 improvement is retained after exact full-make reproducibility,
exhaustive packet checks, isolated spectrum/power checks, all 21 NTSC/PAL Sound
Test entries and matched 3P/4P ending fixtures. Exactly ten bytes differ from
4646: the instrument's patch/algorithm and header checksum; symbol layout and
all other bytes are identical. A 9,000-frame ending capture exercises 127 active
instrument21 samples and 9,293 ticks, with zero underruns. Before/after audio
first differs at 81.387 seconds; earlier samples are identical. Both ending
fixtures match every reported field except ROM hash, including 5,823 gallery
frames and 5,760 credit updates, Home return and re-entry. This is not subjective
listening or harmonic-phase certification. Evidence:
`.local/hucard-spectrum-audit/accepted.json`, `validation-summary.json`,
`reproducibility.json` and `audition/index.html`.
At the preceding0a981d93 checkpoint, all six protected3P/4P campaigns and the artwork suite passed.
BC takes 170,771/194,563 frames; Normal takes 115,379/133,950; Rush completes
all twelve encounters and last-player exit. All six have zero HuCard underruns
and match the preceding campaign frame counts. Evidence: `.local/0a98-campaigns/summary.json`
and `art-checks.json`. All campaign jobs are terminal. The verified package
`.local/candidates/Side-Arms-MD-expansion-0a981d93-test.zip` includes the audio
improvement and supersedes 4646 (ZIP SHA256
`aa4e2ec68089bd1077d1a82ae6c633660d0654444fdf543911c5ec62ef2884f8`).
It remains a test build, not a final-release claim.

Round7 now also has live gameplay evidence, beyond the debug camera page.
The 4P HuCard 9,000-update fixture checks post-DMA plane-B entries, RAM shadow,
cell residency and pattern bytes every32 updates: 281 samples, 335,552 visible
tile checks and 4,782 resident pattern checks pass across194 camera positions
from586 to2464 (y1536). The 600-update opening control matches all pre-existing
profile fields with and without the read-only observer, including983frames.
Captures show real sprites/HUD; terrain can still crush protected players.
This does not cover every intervening frame, the entire round, palette fades
or raster timing. Results: `.local/bc-r7-live-background/`; gameplay captures
are included in `.local/bc-r7-materials/index.html`. All audit jobs are terminal.

The full campaign observer now closes the late-route tile-coverage gap.
Round7 passes13,703 post-upload samples at every observed simulation update,
covering2,305 camera positions from480 through2784 at y1536:16,182,880 visible
tile-entry checks and196,586 resident-pattern checks. The protected4P campaign
still finishes in194,563 frames/112,808 ticks, and every pre-existing result
field—including gameplay-end RAM hash, audio diagnostics, transitions and
ending data—is identical to the no-observer run. Only the added audit report
differs. Ten real gameplay captures are included in the R7 review page, including
late machinery and the boss approach. Evidence:
`.local/bc-r7-live-background/campaign-comparison.json` and `campaign4/`.
All audit jobs are terminal. These checks prove tile/cache fidelity during this
route; they do not prove palette-fade/raster behavior, hardware sprite limits
or full-speed gameplay. The preceding simpler steering fixture also passed
12,000 observations but stalled atcamera2112, so it is not used for full-route
coverage. ROM and the packaged build remain unchanged.

Round7 now also verifies actual background CRAM during gameplay in both
Standard and Vivid. Each protected 4P HuCard fixture runs 300 warmup and 9,000
measured updates, observing 8,999 post-upload boundaries:287,968 palette words,
10,749,760 visible tile entries and153,261 resident-pattern checks per mode.
All match; camera coverage is579..2464 at y1536 across1,886 positions. Each run
takes17,623 video frames and matches exact final RAM, tick and frame state of
an independent replay without the observer. This closes the palette-upload
gap for this bounded route, not sprite palettes, fades, raster effects or the
full stage. The two native captures are now in the R7 review page. Evidence:
`.local/bc-r7-live-palette/summary.json`. Both jobs are terminal; ROM unchanged.

The source-pair fitter now also covers zones19/20, recovering 19/21 source-color
distinctions in both Standard and Vivid while reducing mean channel error and
adding 240/309 exact source-color pixels. Linked artwork checks preserve every
other binary asset, all 684 BC cells, geometry, stars and the Vivid lookup.
The old Vivid output for word3264 is explicitly retained because it still
satisfies every new shade edge; otherwise the greedy generator changed it.
Full `make` reproduces this candidate; payload/headroom remain 4,167,156/27,148.
The R9 4P HuCard 600-update control takes 858 frames in both builds, with
identical canonical state, workload, scene timing and scheduler rows. Raw end
RAM hashes differ; no whole-RAM equivalence is claimed.

Normal multiplayer controls now pass: 3P completes 15,640 updates in 15,731
frames; 4P completes 19,354 updates in 20,263 frames. Both exercise zones
16/18/19/20/21, and every result field except ROM hash matches the preceding
build. These are protected, seeded-loadout controls, not unassisted combat.
The original 4P result mislabeled its Home stop as update_limit because the
report sampled flow after the core finished the video frame. Its count is below
the requested limit, and the only other stop branch is Home; this derivation is
recorded separately without rewriting the original result. The harness now
latches the stop reason at the watched boundary. Both stopping branches pass
focused execution checks, including a subsequent flow change.
Evidence: `.local/normal-stage9-refit/accepted.json`, `normal-comparison.json`
and `review/index.html`. All bounded-control jobs are terminal. The current-build artwork suite and all six protected 3P/4P progression checks
pass. BC completes all ten rounds, ending, 5,760 credit updates and Home return
in 170,771/194,563 frames, with no forced boss defeats or seeded health/weapons.
Normal completes all ten sections in 115,379/133,950 frames; Rush completes
all twelve encounters and the last-player exit. Normal/Rush use assisted hits.
All six runs report zero HuCard underruns; their frame counts match 4764.
Evidence: `.local/4646-campaigns/summary.json` and `art-checks.json`.
The verified test package is
`.local/candidates/Side-Arms-MD-expansion-46463dfb-test.zip`, SHA256
`303959d5b8e883953f94266b0adcfea1f5fcfff46a1c8a691d084e84ac262611`.
It supersedes the 4764 package. All campaign jobs are terminal. This remains a
test build, with performance, remaining visual review and audio fidelity work
still open; it is not final-release acceptance.

The retained 4646 build also passes all nine original boss-body and four
composite-attack imports, 60 native projectile flip cases and all 20 original
serpent poses (80 native flip cases). There are no software sprite drops or
runtime remaps in the latter two fixtures. These pixel/pose fixtures do not
prove unassisted boss combat. Results are included in the current art summary.
All 21 HuCard tracks pass NTSC and the PAL-header variant, with zero underruns
and 840 total published-packet checks across both regions. Results are under
`.local/4646-campaigns/audio-{ntsc,pal}`; the PAL variant hash is explicit.

An offline instrument-21 fit improves measured harmonic-magnitude error by
72.2%, with absolute level error below 0.227 dB at four attenuation levels.
It remains outside the campaign ROM until production delivery, timing and
listening checks. Evidence: `.local/hucard-spectrum-audit/candidate21.json`.

The stage-four zone6 palette fit is now retained. It restores 40 source-color
distinctions in Standard and Vivid without newly merging source-color pairs.
All 684 BC cells, geometry, stars and the Vivid lookup remain unchanged; the
aggregate material verifier also passes. This deliberately trades some color
accuracy for shading: mean squared channel error changes from 0.1470 to 0.1566,
weighted error from 142,450 to 153,500, and exact source-color pixels decrease
by 299. It is not a source-exact conversion.

Protected 3P and 4P Normal controls each cover 12,000 updates through zones
5, 6 and 7. Every reported field except the ROM hash matches the baseline,
including 12,007 and 12,795 video frames respectively. The 600-update BC R4
4P HuCard control likewise matches every field except hash, taking 1,111 frames.
Full `make` reproduces this cartridge; payload headroom remains 27,148 bytes.
Evidence and native comparisons: `.local/normal-zone6-refit/accepted.json` and
its `review/index.html`.

All six preceding 4764-build 3P/4P progression runs pass with zero HuCard underruns.
BC completes ten rounds, the ending, 5,760 credit updates and Home return in
170,771/194,563 frames; the protected controller runs use no forced boss defeats
or seeded health/weapons. Normal's assisted-hit controls complete all ten
sections in 115,379/133,950 frames without injected stage warps or completion
events. Both assisted-hit Rush controls complete twelve encounters and the
last-player exit. These are progression checks, not unassisted combat or
full-speed certification.

The accompanying art suite also passes on the preceding 4764 hash: aggregate Normal
material/source-pair checks, frontend shades, reviewed recolor selection,
Round7 native rendering/comparisons and both native intro color modes.
Evidence: `.local/4764-campaigns/summary.json` and `art-checks.json`.
The new package `.local/candidates/Side-Arms-MD-expansion-47641ef9-test.zip`
passes ZIP integrity and extracted-byte/checksum checks. It supersedes the
7344 package. All jobs are terminal. Heavy multiplayer slowdown, the remaining
shading work and conditional parallax still prevent a final-release claim.

The current-ROM actor-cache audit found zero avoidable attribute-only key
changes among 3,051 observed changes across R2/R4/R8/R10, each sampled for
600 protected four-player HuCard updates. All existing R4 profile fields match
the same run without this optional host observation. Consequently no runtime
key-masking change is retained; it would add work without demonstrated benefit
in these windows. This is bounded evidence, not a whole-game proof. Tool:
`profile_bc_budget.py --actor-cache-audit`; results:
`.local/actor-cache-attribute-audit/summary.json`. All audit jobs are terminal.

A distinct enemy-timer experiment kept SUBQ/BEQ but replaced the global memory
clobber with an explicit timer output. The m68k compiler rejects outputs on
`asm goto`, so no game build or runtime change was made. The unchanged helper
passes all 512 native timer/alignment/sentinel cases using the expanded source
and output-path options in `qa_bc_timer_native.py`. Evidence:
`.local/bc-timer-goto-output/rejected.json`.

Offline source-pair fitting also found improvements for Normal zones19/20:
19/21 recovered distinctions respectively in both Standard and Vivid, zero
new source-pair merges, and lower mean channel error in each. These are now integrated in retained build 46463dfb, with the validation
evidence above. The current campaign ROM remains immutable. Zone21's smaller
three-pair recovery increases color error and is not selected for integration.
Evidence: `.local/normal-shade-loss-fit/remaining-zones.json`.

Preceding fully campaign-tested build: `7344a15fe025096b23e54a9ede27f8747b89091a8f134806c9a50f8ef19f0357`.

The city shade repair is now retained: 3,055 source-color pixels restored,
with every other Normal material and all 684 BC background cells unchanged.
BC R1 uses its pre-repair donor data to preserve its authored pen meanings.
The Vivid lookup stays byte-identical and satisfies all current shade edges.
A full rebuild reproduces this ROM; payload headroom is 27,148 bytes. Normal 4P
opening and BC4P R1/R8 controls match prior timing, states and workloads.
Evidence and before/after native images: `.local/city-shades-fit/`.
Full 3P/4P progression checks on this hash are recorded below.

The unused Earth world bank is now omitted from the cartridge; its source files
remain available and the intro retains its separate scene graphics. This recovers
32 KiB (35,340 payload bytes available before the city repair). At that storage-only checkpoint, all 159 remaining linked binary
assets and 684 BC cells were unchanged. Both intro modes, all 21 HuCard tracks
in NTSC/PAL, bounded Normal 4P checks across ten sections, and BC R8 4P pass.
Storage-checkpoint evidence:
`.local/unused-earth-storage/accepted.json`.

The latest test package is `.local/candidates/Side-Arms-MD-expansion-7344a15f-test.zip`.
All six current-ROM 3P/4P progression checks pass with zero HuCard underruns.
BC completes all ten rounds, gallery, 5,760 credit updates and Home return:
3P takes 110,611 simulation ticks / 170,771 video frames; 4P takes 112,808 /
194,563. These protected controller runs use no forced boss defeats, seeded
health/weapons or injected stage warps. Software drops, remaps and unmapped
art remain zero. They are not equal-workload timing comparisons with older
live-pilot runs or hardware scanline-overflow certification.

Normal's protected assisted-hit campaigns complete all ten sections in
115,379 frames (3P) and 133,950 (4P), without injected stage warps or completion
events. Both Boss Rush party sizes pass twelve encounters and last-player exit
using assisted hit paths. ZIP integrity and extracted ROM/evidence bytes pass.
The package includes current-ROM artwork checks and controls. Evidence:
`.local/7344-campaigns/summary.json`, `art-checks.json` and `package.json`.
It supersedes the b7 test package and includes the city-shading repair and
unused Earth-bank removal as well as the earlier corrections below.
Heavy multiplayer slowdown, remaining shading and broader conditional parallax
still prevent a release-complete claim.

The subsequent shade search on current-ROM banks 6, 19, 20, 21 and 22 is
complete: 1,909 source-color pairs and 1,328 whole-color-group selections
produced no additional candidate under the existing two-bank, fixed-star and
unchanged-other-pixels constraints. Packing attempts were bounded at 50,000
nodes; this is not a proof that better palettes are impossible. All fifteen
input blobs were verified against this cartridge. No runtime assets changed.
Evidence: `.local/normal-shade-material-groups/summary.json`. Further repairs
need material-aware fitting that can improve several inaccurate colors together,
rather than treating every existing output color as immutable.

An offline material-fitting trial now tracks the identities of source-color
pairs, not just aggregate shade counts. For zone6, its stronger candidate
recovers 40 source-color distinctions under both the current Standard and
Vivid palettes, introduces zero new source-pair merges, and improves merge
counts in 31 of 62 metatiles. However, mean squared channel error increases
from 0.1470 to 0.1566, and exact source-color pixels decrease by 299. This is
an experimental color-versus-shading tradeoff, **not a retained ROM repair**.
All fitting jobs are terminal; the current cartridge remains 7344. Comparison
images and independent pair checks are in
`.local/normal-shade-loss-fit/source-pairs-z6-p64/`; overall trial status is
`.local/normal-shade-loss-fit/status.json`. BC donor isolation and integration
checks have not been performed for these offline candidates.

The first three Earth-burning frames now recover 570 orange source pixels
(54/364/152 respectively). The existing shared burning palette was repacked;
no new scene palettes or palette switches were added. Every other rendered
pixel remains unchanged, including Earth/flash, the title and all gameplay
artwork. Standard and Vivid preserve all previously distinct shades within
each checked 32×32 region. Only 212 ROM bytes differ from 6123, confined to
`fe_set1_tiles`, `fe_set1_pal` and the cartridge checksum; executable code and
all other bytes are identical.

Four-player HuCard intro checks again cover all 15 scenes. Their results are
identical to 6123 except for the ROM hash, including every displayed-scene
duration, 595/604 frames to play in Standard/Vivid and zero underruns. These
counts retain the earlier Earth-palette-switch cost versus ad0; this subsequent
orange-shade repair adds no further delay. Remaining burning shades are not
claimed source-exact. Evidence: `.local/frontend-burn-shades/`.

Preceding working build: `6123b67b659de6ebcd3e7d1fc8b8993084085262613af7f85630e183421251ef`.

The actual Earth and Earth-flash intro frames now retain every source RGB3
shade, restoring 5,679 pixels. They share a dedicated palette; the scene loader
restores the original palette for burnt/burning frames. All 14 other frontend
frames preserve their pixels and opacity. Star pen indices remain fixed, and
Vivid keeps the new palette's colors distinct. This supersedes the Earth/flash
limitation in the preceding audit; burning-frame shade loss remains open.

Native four-player HuCard fixtures verify all 15 intro maps, complete tile
uploads and palette contents in Standard and Vivid, with zero underruns.
Scene order is unchanged, but palette switching during the alternating
flash/burnt phase adds measurable cost: this fixture reaches play in 595 versus
594 frames in Standard, and 604 versus 594 in Vivid. Individual scene display
durations are not identical. The improvement is retained with that bounded
intro cost disclosed; it is not a zero-overhead claim.

The four-player Normal 1,200-update sample preserves state hashes, sprite
rendering and workloads, taking 1,240 frames in both builds; scheduler timings
change slightly. BC R8's 600-update four-player HuCard sample preserves all
simulation/workload/scene timing rows and 1,005 video frames. Its scheduler
observations match except for relocated code addresses. These are bounded
regression checks, not full-game performance certification.

All 137 linked non-frontend binary blobs remain identical. Full `make`
reproduces the tested ROM. Raw payload remains 4,191,732 bytes (2,572 free).
Evidence: `.local/frontend-shade-repair/verification.json`, `comparisons.json`,
`native-standard/`, `native-vivid/`, `reproducibility.json` and `review/earth.png`.
The historical af243 package excluded these shading changes; the current b7
package includes them. Broader shading, multiplayer performance and conditional
parallax work remain open.

Preceding working build: `ad0dcf5b7ff6a083c43c912565a16360a3f1a25946daaf44c7aeba628f33598f`.

Normal zones 5, 12 and 13 now restore another 520 source-color pixels: 63 in
scenery detail, 92 in machinery and 365 in lava highlights. All other displayed
colors, opacity, stars and BC cells remain unchanged. Standard and Vivid checks
forbid merging previously distinct shades in a metatile. Only these zones'
tile/palette bytes and the header checksum differ from b78; executable code,
resource addresses and other data are byte-identical. Payload and headroom
remain unchanged.

Three four-player fixtures visit the affected zones and match every state,
sprite-render hash, workload and scheduler result: section-index 3 takes
1,240 frames for 1,200 updates; index 5 takes 5,131 frames for 5,000 updates
(zones 10/12/13); index 6 takes 1,201 frames for 1,200 updates (zone 13).
These are equivalence passes, not full-speed passes. Evidence and source/before/
after images: `.local/normal-shade-batch/`.

A zone-23 Earth-tile prototype was excluded: the visible intro uses separate
`fe_set1` data, so modifying the general Earth tile set would not repair that
screen. A linked-ROM audit of the actual 16 frontend scenes finds the title
source-exact, but Earth and its flash lose shades; this remains open.
Evidence: `.local/frontend-shading-audit/audit.json` and `earth.png`.
The last full-campaign-tested package remains af243 below.

Preceding working build: `b78a59710a30199ce969ff6e405e4ff9dd2b171ed09e457d27669f9a8e44c914`.

Normal zone 14 now restores 2,300 source-red pixels in foundry machinery and
lava. The repair selects source color `0x008` in palettes 17, 29 and 30,
retaining every other rendered color. Standard and Vivid checks prohibit
merging previously distinct shades within a metatile. Source opacity, star
pens and all 684 BC background cells remain unchanged. The entire ROM outside
zone-14 tile/palette data and the header checksum is byte-identical to af243;
no executable code, resource addresses or other data changed. Payload remains
4,191,732 bytes, with 2,572 bytes free.

The protected four-player section-7 fixture reaches zones 13 and 14 and takes
5,198 video frames for 5,000 updates in both builds. Every state, sprite-render,
workload and scheduler result matches. A shorter 1,200-update sample remains
in zone 13 and takes 1,201 frames in both; it is not zone-14 visual coverage.
These are equivalence checks, not full-speed or whole-campaign certification.
Evidence: `.local/normal-zone14-shades/verification.json`, `all-materials.json`,
`binary-scope.json`, `timing-comparison.json` and `comparison.png`.

The most recent full-campaign-tested package remains af243 below; it does not
include this subsequent Normal palette repair. Broader shading, multiplayer
performance and conditional parallax work remain open.

Last packaged build: `af243c4a34f155b8a0731fd5ec5e561e55c91ebbb2d412b896d07ee5b3be6096` (4 MiB).

The latest test package is now
`.local/candidates/Side-Arms-MD-expansion-af243c4a-test.zip`. All six packaged-ROM
3P/4P progression runs pass for Normal, BC and Boss Rush with zero HuCard
underruns. BC completes all ten rounds, the gallery, 5,760 credit updates and
Home return using protection and controller aiming, without forced boss defeats,
seeded health/weapons or injected stage warps. BC 3P uses 110,611 simulation
ticks / 170,801 video frames; BC 4P uses 112,808 / 194,599. Both report zero
software sprite drops, remaps and unmapped art. These live controller runs are
not equal-workload performance comparisons against earlier ROMs.

Normal's protected assisted-hit runs complete ten sections in 115,465 frames
(3P) and 133,916 (4P), without injected stage warps or completion events. Both
Boss Rush party sizes pass twelve encounters and last-player exit using the
assisted-hit fixture. These tests prove progression/audio behavior under their
stated assistance, not unassisted combat or full speed. Full `make` reproduces
the tested ROM exactly. The ZIP contains controls, checksums, campaign results
and current-ROM art regression scope; ZIP integrity and extracted bytes pass.
Evidence: `.local/af243-campaigns/summary.json`, `reproducibility.json` and
`package.json`. This package supersedes the earlier `c7aca8d3` test package;
heavy multiplayer slowdown, remaining visual issues and broader parallax work
remain open. It is not a release-complete claim.

Normal zones 3, 16, 17 and 18 now recover another 1,426 original RGB3 pixels:
225 in palette-4 scenery, 112 in palette-24 machinery detail, and 1,089 across
the later palette-17/19 machinery regions. All 72,054 pixels in the selected
materials match source colors. Surrounding material colors, transparent masks,
star pens, the Vivid LUT and sprites remain unchanged. All 124 componentwise
shade relationships remain ordered in Vivid. All 684 BC cells retain rendered
color/opacity/priority; R3's pen numbering changes only for storage reuse.

Four-player Normal before/after checks preserve state, sprite rendering,
workloads and scheduler observations: 1,200-update samples take 1,202, 1,240
and 1,211 video frames respectively; the 5,000-update route through zones
16/18/19 takes 5,524 frames in both builds. These runs exit 1 on their existing
full-speed gate, not on equivalence checks. Zone 17 is source-to-ROM verified
but was not entered by those gameplay samples. BC R3's four-player HuCard
sample preserves all 600 states/workloads/scene timings and 707 video frames;
native rendering passes 57 cameras / 63,840 subtiles. Recolor checks still pass
all 144 records. Raw payload stays 4,191,732 bytes (2,572 free).
Evidence: `.local/normal-material-packing/`; reproduce the pixel checks with
`tools/qa_normal_material_shading.py --baseline PATH --output PATH`.

The global audit now excludes appended BC lookup keys from Normal source
comparisons and verifies every examined generated blob against the linked ROM.
The earlier audit incorrectly treated 110 small BC variants as Normal assets.
The af243 diagnostic counts are 875/1,344 backgrounds, 2,536/2,795 Normal small
sprites and 773/800 Normal large sprites containing palette color collisions.
These counts do not imply every flagged asset is visibly defective; remaining
shading work is open. BC variants retain their separate linked-pixel audit.
Evidence: `.local/normal-material-packing/global-audit/audit.json`.

Preceding accepted build: `efff7a0cd3b99b2551cd9b310c708a73fa5b42dec6581a2b5a3fddf0300f6d7a`.

Normal zone 16 (section 8 machinery) now retains all four original blue material
shades. Offline palette repacking restores 526 pixels across 24 metatiles to
their source RGB3 values; 3,123 blue source pixels are verified. All other
rendered colors, transparency, star palette slots, the Vivid LUT and sprite
banks remain unchanged. All 684 BC background cells retain their rendered
colors, opacity and priority. BC R8's generated pen numbering changes to reuse
the revised Normal patterns, with no visible change; its native loader passes
30 cameras / 36,736 subtiles. Both Standard and Vivid retain the four blue steps.

Protected four-player Normal section 8 preserves all 1,201 state and sprite
render snapshots plus workloads and scheduler observations: 1,200 updates take
1,221 video frames before and after. Both runs return exit 1 for their existing
full-speed gate; these are equivalence passes, not full-speed passes. BC R8's
1,000-update four-player HuCard comparison preserves simulation, workloads,
individual scene timings and 1,799 video frames. All 144 BC recolor records also
pass linked-pixel checks. Raw payload remains 4,191,732 bytes, leaving 2,572.
Evidence and visual comparison: `.local/normal-zone16-shading/`. Reproduce the
source/ROM check with `tools/qa_normal_zone16_shading.py --baseline PATH --output PATH`.
The six-campaign package below still belongs to the earlier `c7aca8d3` build.

Preceding accepted build: `678465896ce2112f61eea3666e2c65353dbb31a33282b9312fabe544b533b7cc`.

The linked-pixel recolor audit now covers all 144 generated ordinary BC
recolor/unique/beam records, including gallery variants: 90,624 source-to-ROM
pixel checks and 335 ordered material ramps pass in Standard and Vivid.
It reads actual sprite indices, packed pixels and palette/LUT words from the
cartridge; converter metadata alone cannot satisfy it. There are 1,435 visible
shade steps across those per-pose ramps. This closes that specific coverage
gap, not the separate Normal-asset, boss-import or semantic-match audits.
Evidence: `.local/bc-linked-shading/audit.json`; reproduce with
`tools/qa_bc_linked_recolor_shading.py --output PATH`.

The whole-backdrop R8 parallax prototype was rejected because slowing the
complete map delays/skips distinctive machinery. The current ROM was restored
exactly; no additional parallax is retained. See `docs/parallax.md` and
`.local/bc-r8-backdrop-depth/rejected.json` for the bounded timing comparison.

The actor common path now relies on the already-validated party binding:
`bc_party_bind` attaches only 2–4-member parties, and solo players use NULL.
Party setup retains its invalid-count/member checks. Removing the redundant
per-actor count test preserves all sampled gameplay states/workloads: solo
R7 improves 601→600 frames, 2P R8 704→702, 3P R8 813→810, 4P R7 985→983,
and 4P R6 1,714→1,710. The candidate's heavy R8 profile exactly matches an
independent replay's full final RAM. Its live-pilot timing is not claimed as
an equal-workload comparison, because rendering changes can alter input arrival.
An older eight-round input corpus matches both builds through 10,339 scenes,
then both diverge from the old corpus with the same state hash; the remainder
of that corpus is not current-build evidence. Party routing, contact semantics,
1–4P frame behavior and invalid binding tests pass. Raw payload remains
4,191,732 bytes. Evidence: `.local/bc-party-bind-invariant/accepted.json`.

The complete six-run campaign matrix and downloadable package below belong to
the preceding `c7aca8d3` build, before this actor-path optimization. They remain
the latest packaged candidate; this newer build has bounded checks only.

HuCard voice packets now use aligned 12-byte cache rows and three 68000
long-word copies, retaining a byte-copy path for odd destination addresses.
The change adds 18 RAM bytes and preserves every packet byte. Native checks
cover 16,384 packets at even/odd addresses and repeated poisoned buffers;
exhaustive host math covers all 16-bit periods. All 21 Sound Test tracks pass
in NTSC/PAL (840 published packets, zero underruns). Protected 4P HuCard samples
preserve state/workload while reducing R7's 600-update run from 1,002 to 985
video frames and R6's 1,000-update run from 1,730 to 1,714. Full speed remains
unproven. Evidence: `.local/hucard-packet-copy/accepted.json`.

Round 7 now preserves every source RGB3 color across all 61 playable cells.
The mismatched Normal floor was replaced with BC floor geometry; removing two
unreachable fallback cells then freed palette capacity for the exact hanging
orange shade. Cells 86/88 occur only left of column 16 within the stage strip,
where the runtime clamps to the first valid column. No collision data changes.
All six Standard review views now match decoded PCE backgrounds pixel-for-pixel.
Native rendering passes 33 route cameras, and all-round palette upload passes
640 Standard/Vivid CRAM words. The protected 4P HuCard sample preserves all 600
simulation/workload/timing rows, the full instruction-cycle array and 1,002 video
frames. This is unchanged performance, not full-speed verification.
Raw payload is 4,191,732 bytes, leaving 2,572 bytes. Evidence:
`.local/bc-r7-exact-orange/`; aligned review generated with
`tools/build_bc_r7_review.py` at `.local/bc-r7-materials/index.html`.

All six preceding-build 3P/4P progression runs pass for Normal, BC and Boss Rush,
with zero HuCard underruns. Both BC runs finish ten rounds, the gallery, 5,760
credit updates and Home return using damage protection and controller aiming,
without forced boss defeats, seeded health/weapons or stage warps. BC 3P uses
107,013 simulation ticks / 163,913 video frames; BC 4P uses 116,808 ticks /
203,118 frames. Both have zero software sprite drops/remaps and unmapped art.
Normal and Boss Rush use protected players and assisted hit paths: ten sections
and twelve boss encounters pass at both player counts, including last-player
Rush exit. These are progression/audio checks, not unassisted combat,
full-speed or physical-console certification.
Evidence: `.local/c7ac-campaigns/summary.json`.

The latest packaged local test-build ZIP is
`.local/candidates/Side-Arms-MD-expansion-c7aca8d3-test.zip`. Its ROM, controls,
known limits, acceptance summary and checksums pass ZIP integrity and exact
extracted-byte verification. It is **not the final release**. Experimental
parallax masks are excluded. Packaging provenance:
`.local/c7ac-campaigns/package.json`. The older `f97004d1` package remains an
archived candidate and is superseded by this one.


The Round 7 green machinery and bases now use complete BC source assemblies,
replacing forced Normal fragments, arbitrary flips and red/orange base pieces.
Nineteen patterns cover 44 quadrants in 15 cells (10,901 pixels changed). The
Normal floor panel used in that pass is superseded by the screen-review fix above. All green/blue
source colors remain exact, and five green levels, three blue levels and seven
warm levels stay distinct in Standard/Vivid. The other 48 R7 cells, all 623
other-round cells, 113 Normal blobs, ten source/collision banks and global Vivid
LUT remain unchanged. Native checks pass 33 cameras / 40,208 subtiles and 640
Standard/Vivid CRAM words across all rounds. The protected 4P HuCard sample
keeps all 600 simulation/workload/cycle rows and 1,002 video frames, with seven
safe late flushes. This does not prove full speed. Payload is 4,192,756 bytes,
leaving 1,548 bytes free. Evidence and six-view review: `.local/bc-r7-machinery/`.
The earlier machinery defect below is superseded by this repair. Performance,
remaining material review and conditional parallax expansion remain open.

Preceding build: `ca188190` (floor-panel repair).

The superseded Round 7 floor repair completed Normal tile 328's panel: reference
pattern 35/11 previously selected an unrelated machine-head quadrant from tile
320. The corrected lower quadrant retains Normal source geometry and shades.
Exactly 458 pixels in R7 cell 12 change; the other 62 R7 cells, 623 cells in other
rounds, 113 Normal blobs and ten source/collision banks remain unchanged. Native
rendering passes 33 cameras / 40,208 subtiles. A protected four-player HuCard
sample keeps all 600 simulation/workload/cycle rows and scheduler observations
identical, using 1,002 video frames before and after, with seven safe late flushes.
This is not full-speed evidence. Raw payload remains 4,192,244 bytes, leaving
2,060 bytes free. Evidence and before/after review: `.local/bc-r7-floor-fix/`.
At that checkpoint, green machinery component mismatches remained; these are
superseded by the current source-exact repair above. The unverified parallax wrapping experiment is archived in
`.local/parallax-wrap/candidate/` and removed from active source/build.

Preceding build: `c9cf03a8` (R1 shade repair).

The latest repair removes extra shade merging from the authored Round 1 ledge
family (cells 20/21/22/3A/3B). The texture now reads the original Normal source
pens before palette fitting and maps its four levels to distinct, ordered base,
dark and light relief ramps. Previously the fitted donor had three shades and
the light relief merged those to two. Unused R1 palette pen 15 restores RGB3
(2,3,2). The bright source (4,4,5) remains approximated as (4,4,4); this is not an
all-source-colors-exact claim. Contours and warm rock details are unchanged.

The repair changes 1,404 pixels in exactly five cells. Verification checks 3,968
source stone pixels, all 64,512 R1 opacity positions and preserved warm material.
All 623 other-round cells, 113 Normal blobs, ten source/collision banks and the
Vivid LUT are unchanged. Every declared four-level ramp stays distinct and
ordered in Standard and Vivid; individual regions may contain fewer source
levels. Native validation passes 103 cameras / 115,360 subtiles and all 640
Standard/Vivid CRAM words. The protected 4P HuCard R1 sample keeps all 600
state/workload records and 635 video frames, with seven safe late flushes.
Full `make` reproduces the tested ROM exactly, with 2,060 payload bytes free.
Evidence, before/after review and snapshot: `.local/bc-r1-shading/`, `index.html`,
`accepted/`. The campaign/controller evidence below belongs to the preceding
`45e7faf9` cartridge; it has not been relabeled as new full-campaign evidence.
Performance, remaining material correspondence and parallax work stay open.

Preceding-ROM (`45e7faf9`) continuous campaign checks pass for both three and four players
in Normal, BC and Boss Rush. BC completes all ten rounds, the gallery, all 5,760
credit updates and Home return: 3P uses 107,111 simulation ticks and 165,216 video
frames including ending; 4P uses 115,126 ticks and 200,055 frames. The pilot uses
damage protection but no forced boss defeats, seeded health/weapons, stage warps
or injected completion. Both record zero HuCard underruns, software sprite drops,
runtime remaps and unmapped-art counts. This does not measure hardware scanline
overflow or certify unassisted combat/full speed.

Normal completes all ten sections and Home return in 115,893 video frames (3P)
and 134,263 (4P), using protected players and assisted boss hits. Boss Rush also
passes all encounters, clear/result music and return via the last selected
player for both party sizes through assisted hit paths. All six checks have
zero audio underruns and verify expected audible music. Evidence:
`.local/current-campaigns/summary.json`. Earlier campaign reports below remain
historical; this paragraph binds the current evidence to `45e7faf9`.

A read-only R1 ledge audit identifies remaining shade loss. Its Normal stone
donor maps four source RGB3 shades to three, then the authored light-relief ramp
maps those three texture shades to two. Base and dark relief retain three.
The recipe's five entries do not imply five actual input shades. No ROM change
has been made for this finding. Evidence: `.local/bc-r1-ramp-audit/audit.json`.
That R1 finding is repaired by the newer cartridge described above; full-speed
and broader art/parallax work remain open.

The preceding `45e7faf9` cartridge also passes twelve protected four-player HuCard gameplay
checks using emulated controller protocols rather than logical input injection.
NTSC covers Normal, BC and Boss Rush with Team Player on either port and EA
4-Way Play; PAL covers all three modes with Team Player on port 1. Each case
runs 1,800 gameplay frames, observes buttons from all four controllers, retains
the expected music tracks with zero queue underruns, saves/reloads the music
and player settings, and migrates v4 settings. BC pause freezes simulation while
music continues. The PAL copy changes only the region header. These bounded
checks do not establish full-campaign correctness or full speed. Evidence:
`.local/hucard-controllers/summary.json`; reproduce with
`tools/qa_hucard_gameplay.py --mode MODE --players 4 --adapter ADAPTER`.

A general actor-loop experiment moved uncommon enemy families and their event
buffer into a separate function. It preserved all 600 protected Round 6
simulation/workload records but regressed 1,128 to 1,141 video frames. The
experiment was rejected; source and the exact `45e7faf9` ROM are restored.
Evidence: `.local/bc-common-loop-envelope/rejected.json`. No performance
improvement is claimed for this pass.

The Team Player callback fix now covers SDK initialization as well as gameplay.
A project-local build adaptation (`tools/guard_joy_callback.py`, loaded by
`tools/cart_boot.mk`) adds the missing null check in the SDK reader. The original
SDK stays unchanged; the adapter rejects an unexpected source implementation.
This replaces the earlier game-installed no-op callback, which was installed too
late to protect buttons held during startup with the other controller port empty.

All six emulator configurations now pass: Team Player on either port and EA
4-Way Play, each with three- and six-button pads. Across them, 228 isolated
button/release checks pass, alongside held-Up startup and held-Up reset for all
four players. Team Player port 1 is tested with the other port empty. The port-2
six-button failure was a test configuration issue: GX sets physical pad-type
indices 4–7 for that adapter but consumes logical indices 1–4 when a standalone
pad precedes it. The test initializes both groups through the public controller
API before selecting the final wiring. No ROM input or logical-pad overrides
are used for the controller checks. Physical adapter testing is not claimed.

Four-player Normal/Boss Rush joins, wave scaling, merge, save/reload and v3
migration pass. BC menu/cancel/launch, audio, every-controller pause/freeze/resume,
inhibit, return/re-entry and paused soft reset pass. The protected Round 6 HuCard
sample retains all 600 simulation/workload records, taking 1,128 video frames
versus the preceding build's 1,124; its two late flushes finish inside VBlank.
This safety fix does not solve the existing heavy multiplayer slowdown. The
profiler accepts only null callbacks or a ROM callback whose first instruction
is RTS, allowing a sound baseline against the superseded no-op-callback build.

Full `make` reproduces the tested ROM exactly, with 2,060 payload bytes free.
Evidence and snapshot: `.local/multitap-startup/`, `accepted/`. The preceding
no-op fix and its evidence remain in `.local/multitap-current/` for comparison.
The background-only evidence below identifies the earlier `aa530f65` ROM and
must not be relabeled as full verification of this input-fix ROM.

**The expansion is incomplete. R7's reported art defects and R2's cave/machinery
layout defects are repaired; inferred material matches still need visual review.**

The latest change preserves all five steps in Round 5's blue texture. Source
(0,0,3) previously collapsed into (0,0,2); it now uses existing palette color
(0,1,3), a one-green-level approximation. Both alternatives are one unweighted
RGB3 channel step from the source, but the fitter weights green more heavily;
this deliberate choice prioritizes a distinct intermediate shade. All five
steps remain distinct and ordered in Standard and Vivid. No palette word or
other material is changed. This restores shade count, not exact source RGB.

The audit finds 45 source colors across the selected composition and 37
nonblack source colors in a sampled view excluding HUD rows (camera 1248,1108),
exceeding the two background banks' 30 opaque slots. Exact static color fidelity
therefore needs a different rendering strategy; colors in separate sections do
not explain the entire mismatch. Evidence: `.local/bc-r5-exact/packing.json`,
`visible-colors.json`, and its source/current visual comparison.

The retained repair changes only 376 blue pixels in cells 17,18,71. All 613
other-round cells, 113 Normal blobs, ten source/collision banks, all R5 palette
words and the Vivid LUT remain identical. Source geometry and the protected
pink/purple ramps pass, alongside 36 native cameras / 44,352 subtiles and 640
Standard/Vivid palette-word checks. The protected 4P HuCard sample preserves
all 600 state/workload records and 842 video frames; twelve late flushes finish
inside VBlank. ROM headroom remains 2,060 actual payload bytes. Evidence and
review: `.local/bc-r5-blue-ramp/`; snapshot: `accepted/`. Broader shading,
performance, parallax and final release verification remain open.

The preceding change restores Round 4's pre-fit source shading and removes invalid
opening-margin filler. Source cells 45, 60 and 24 occur only at x=480, outside
the valid stage beginning at x=512; they supplied unrelated machinery and 11
extra colors. As in R7, the existing column-offset table now extends the first
valid source column into the extra Genesis margin. This changes rendering only;
source cell IDs, collision descriptors and scripts are untouched.

The 22 playable material cells need 25 nonblack RGB3 colors, which fit exactly
in two banks at character boundaries. All 22,528 composed pixels match original
Normal source colors. The repair changes 3,613 pixels, including six small-rock
highlights previously discarded by the fitted-color mask and six grass-shadow
pixels previously collapsed to transparent black. Component placement, sampling
and character selection remain the same. The oval machine regains its original
orange ramp, neutral/green frame shades and highlights. All 142 ordered Vivid
pairs pass, and the global Vivid LUT is unchanged.

All 664 other-round cells, ten source/collision banks and 113 Normal blobs are
unchanged. Native checks pass 58 cameras / 64,960 subtiles, including the repaired
opening, plus all 640 Standard/Vivid palette uploads. All 600 protected 4P HuCard
state/workload records match; the sample improves 1,112 to 1,109 video frames,
with one late flush safely inside VBlank. The complete unpadded payload is
4,192,244 bytes, leaving 2,060 bytes. Evidence and before/after review:
`.local/bc-r4-shading/`; snapshot: `accepted/`. This repairs R4's identified
source-shade loss and invalid margin; broader shading, performance, parallax and
final release validation remain open.

The preceding change restores the Normal final-chamber face's source palette
before zone-wide fitting. All 20,480 composed pixels and mirrored pieces now
match the original Normal source geometry and colors: 294 material pixels
regain blue shades, warm metal shades and highlights. Fourteen distinct RGB3
colors are used by the composition; 81 Vivid shade relationships pass. All nine
other BC rounds and Normal zones remain pixel/color exact. The final-chamber
verifier now resolves the shared character indices/flips instead of assuming
physical slot order matches each logical metatile.

The initial exact-color build exceeded 4 MiB. Deterministic offline packing
tries bounded equal-size orderings and keeps the smallest group count, saving
two 512-byte blocks without changing the runtime upload size. The unchanged
607-entry DMA-source pointer table is emitted alongside early assembly data,
occupying padding before the mandatory sound-bank boundary. No decompression
or gameplay code is added. An exploratory frontend-alignment change saved no
final cartridge space and was reverted; frontend generation remains unchanged.

All ten rounds pass 502 native camera views / 579,536 subtiles, including boss
bank reservations. All 640 Standard/Vivid palette-word uploads pass; the Vivid
LUT is unchanged. The protected 4P HuCard final-round sample retains all 600
state/workload records and 1,055 video frames, with three safe late flushes.
The 3P and 4P Home menu checks pass cancellation, entry, every-controller pause/freeze,
resume, game-over return, re-entry and paused soft reset. Their snapshot sizes now
match Runner’s resolved RAM addresses; the old name-only lookup incorrectly
used the 9,738-byte ROM sound routine for the 35-byte BC score record and read
unrelated live input memory. This is a test correction, not a pause-code change.

Actual unpadded payload is 4,192,756 bytes, leaving **1,548 bytes** in the 4 MiB
window. Earlier `_etext`-based headroom figures omit trailing linked read-only
and initialized data; this value measures the complete binary. Evidence and
before/after review: `.local/bc-r10-shading/`; snapshot: `accepted/`. Round 4's
then-outstanding palette losses are repaired above; remaining shading, performance, parallax and final
release verification are still open.

The preceding change restores all selected Round 3 material colors before the
Normal zone-wide palette fit. The cyan rock colors used from source palette 4
are a subset of palette 6, allowing palettes 6 and 3 to cover all selected
characters exactly. All 21 distinct RGB3 colors now survive; 8,116 pixels regain
their source shades, including dark blue, cyan steps and warm/neutral machinery
highlights. No geometry, flip or placement changes. The independent source check
covers all 131 cells / 134,144 pixels and 113 ordered Vivid relationships.
All 558 other-round cells, ten source/collision banks, 113 Normal blobs and the
Vivid LUT are unchanged. Native checks cover 57 cameras / 63,840 subtiles and
640 Standard/Vivid palette-word uploads. The protected 4P HuCard sample retains
all 600 state/workload records and 707 video frames, with nine late flushes
inside VBlank. ROM headroom is 3,132 bytes. Evidence and before/after review:
`.local/bc-r3-shading/`; snapshot: `accepted/`. This closes this palette loss,
not the broader shading, performance, parallax or final release requirements.

The preceding change removes the inherited palette-fitting loss from BC Round 9.
Its selected Normal chamber characters use one source palette: all fourteen
RGB3 colors now survive, with unchanged shapes, flips and placement. The repair
restores 1,214 pixels: 950 blue shade pixels, 180 warm gray pixels and 84 brighter
warm highlights. Two distinct source shades previously shared the same gray.
All 49 cells / 50,176 pixels match the independent source decode, with 58 Vivid
shade relationships preserved. All 640 other-round cells, ten source/collision
banks, 113 Normal blobs and the global Vivid LUT are unchanged. Native checks
cover 103 cameras / 118,720 subtiles and all 640 Standard/Vivid palette words.
The 4P HuCard sample retains all 600 gameplay/workload records and 871 video
frames, with four safe late flushes. ROM headroom remains 5,692 bytes. Evidence
and before/after review: `.local/bc-r9-shading/`; snapshot: `accepted/`.
This closes Round 9's source-shade loss, not the broader all-assets shading or
full-speed requirement. Round 3’s inherited losses are subsequently repaired above.

The preceding change removes the inherited Normal palette-fitting loss from BC
Round 8. The selected quadrants all use source palette 19; fifteen opaque source
pens (13 distinct RGB3 colors) fit exactly in one bank. The existing Normal
geometry and BC layout are unchanged. This restores 682 pixels from (0,2,3) to
(0,2,4) and 29 from (0,4,5) to (0,3,5), without merging another shade. The
independent source check covers 45 cells / 46,080 pixels and the complete
cylinder front, plus 38 ordered Vivid pairs. All 644 other-round cells, ten
source/collision banks and 113 Normal blobs remain exact. The Vivid LUT is
unchanged. All 30 native cameras / 36,736 subtiles and 640 Standard/Vivid
palette-word uploads pass. The protected
4P HuCard sample preserves all 600 state/workload records and 1,016 video
frames; four late flushes finish inside VBlank. This is not full-speed evidence.
ROM headroom is 5,692 bytes. Evidence: `.local/bc-r8-shading/`, including the
before/after review and archived build. Broader shading, performance, parallax
and final release verification remain open.

HuCard validation on the preceding `e7f24f2a…` build passes all 21 Sound Test selections on NTSC
and PAL (42 outputs, 840 complete packet checks covering all four ring slots),
with correct clock rates, no underruns, audible output and no clipped samples.
STOP, Arcade-source return and Options return pass. Twelve actual Home launches
cover Normal/BC/Boss Rush × 3P/4P × NTSC/PAL, including saved music/player count
and v4 SRAM migration. BC pause preserves simulation and continues music. A
protected 4P BC run reaches the stage-to-boss music transition autonomously,
without injected music commands; maximum observed wait is two video frames.
Evidence: `.local/hucard-final-current/summary.json`, generated by
`tools/qa_hucard_acceptance.py` with strict current-ROM and PAL-header hashes.
The refreshed `.local/hucard-audio-review/index.html` contains 21 PCE/Genesis
listening pairs (original gain and level-matched); its controls pass the page
harness. These bounded tests do not establish subjective timbre fidelity or
full-campaign playback coverage. No cartridge code changed in this validation.

The preceding change corrects the existing Normal/Home cave parallax cut mask.
Palette membership alone removed 16,463 pixels that did not match the repeating
far texture. They now remain on the world plane; a mask valid across mirrored
uses keeps the original 19 Home tile variants and 12,348 bytes of ROM headroom.
All 333,824 pixels across 326 cut cells reproduce their source at the locked
texture position. No cells under HUD rows are cut. Only `zone10h_tiles`,
`zone10h_attr` and the ROM checksum differ; all code and BC artwork remain exact.
A protected Normal stage-five four-player run retains 5,001 state hashes and
5,000 workload records, takes 5,005 video frames before and after, and drops no
sprites. Five missed frames remain; this is not a full-speed claim. Native
captures reach both star and moving-far-layer modes through the current Home
player dialog. Evidence: `.local/parallax-expansion/cut-fidelity.json`,
`rom-isolation.json`, `timing-comparison.json`, `native/`; archive: `accepted/`.
The requested all-level parallax extension is still open. This repairs the
existing method before reusing it elsewhere; candidate scans are exploratory.

The current R2 repair replaces unrelated small-machine fragments with eight BC
patterns across 62 quadrant placements, including source empty spacing. Machine
geometry is source-exact; hues deliberately follow Normal blue/olive/red
materials. Four blue and four olive steps remain distinct and ordered in Standard
and Vivid. Six additional cap/rail combinations now use corresponding Normal
halves, retaining the three earlier lamp-housing repairs. All other rounds,
Normal assets, source/collision banks and the Vivid LUT are unchanged.

Native checks pass 58 cameras / 64,960 subtiles and all ten Standard/Vivid palette
uploads. All 600 four-player HuCard simulation/workload records match the prior
build; the sample remains at 736 video frames, with five late flushes entirely
inside VBlank. Current headroom is 12,348 bytes. Evidence:
`.local/bc-r2-materials/small-machinery-verification.json`,
`small-machinery-native.json`, `small-machinery-vivid/native.json`,
`small-machinery-timing-comparison.json`; archive: `small-machinery-build/`.
The updated R2 review page decodes this cartridge. Inferred visual suitability
is not a user approval. Broader shading, performance, parallax, audio listening
and final expansion acceptance remain open.

The preceding housing build (`09e6a459…`) established the following evidence:

That change repairs R2 compound housing cells 0x44, 0x4c and 0x4f:
corresponding Normal lamp/cap halves and a complete inverted lamp replace three
copies of the same upright tile. All source shades are retained. All other R2
cells, other rounds and source/collision banks remain unchanged. Native checks
pass 58 cameras / 64,960 subtiles. The protected four-player HuCard sample keeps
all 600 simulation/workload records and takes the same 736 video frames, with
all five late flushes inside VBlank. Current headroom is 10,300 bytes. Evidence:
`.local/bc-r2-materials/machine-verification.json`, `machine-native.json`,
`machine-timing-comparison.json`; archive: `machine-build/`.
Small background machinery matches and broader expansion work remain open.

The preceding cave build (`347bee20…`) established the following evidence:

R2 now uses 40 BC cave/background/blank patterns across 240 quadrant placements,
replacing narrow-column and stair-stepped slope filler. Geometry and empty
quadrants are checked against the hashed PCE capture. Brown and cyan hues come
from the Normal source material ramps, preserving seven rock and six background
steps. One additional dark-blue shade occupies an unused palette slot; no ramp
steps merge. This is BC geometry with Normal material colors, not a claim of
unchanged Normal geometry or exact PCE colors. The four machine-frame flips
remain, and retained machinery preserves its original source RGB3 shades.

Checks cover 91,136 geometry pixels, 24,480 retained Normal pixels and 39,438 BC
geometry/material pixels. The other 600 background cells, all ten source/collision
banks and 113 Normal blobs are unchanged. R2 native rendering passes 58 cameras /
64,960 subtiles with boss graphics reserved. Standard/Vivid uploads pass across
ten rounds. All 1,482 shade constraints and 478 explicit ramps pass; the global
Vivid LUT is byte-identical to the preceding source-shade build.

The protected four-player HuCard R2 sample preserves all 600 simulation/workload
records and improves from 739 to 736 video frames. All five late flushes finish
in VBlank. This is a bounded sample, not full-speed/unassisted acceptance. ROM
headroom is 11,324 bytes. A full rebuild reproduces the cartridge byte for byte.
Evidence: `.local/bc-r2-materials/cave-verification.json`, `cave-native.json`,
`cave-vivid/`, `cave-timing-comparison.json`, `cave-reproducibility.json`.
Archive: `cave-build/`. Current comparison: `.local/bc-r2-materials/index.html`.

The preceding source-shade build introduced lossless mirrored-character sharing
using hardware tile flags. Whole-cell orientations have distinct logical records;
pre-authored whole-cell flips are baked before packing, avoiding the renderer's
additive whole-cell flip behavior. Opaque black, priority, palettes and the
active-zero sentinel are preserved. No runtime conversion or render-loop change
was introduced. Its all-round coverage passed 502 camera views / 579,536 subtiles,
mode handoff, and R2/R6/R7 timing samples without regression. Those reports in
`shading-all-rounds/`, `shading-handoff/`, `shading-heavy-timing.json` describe the
prior build; current tests above establish the R2 delta and unchanged other art.

At this historical checkpoint, R7 retained its BC wall, machine, hanging and lava
repairs plus the extended opening column. Dark orange (7,2,0) used (7,1,0);
that approximation is removed in the current source-exact repair above. Its opening extends
the first valid column into the extra Genesis width with precomputed offsets;
collision data is unchanged. Dedicated review: `.local/bc-r7-materials/index.html`.
Historical repair evidence remains in `.local/bc-r7-repair/`.

Open work: review inferred R2 machinery matches; broader shading corrections; performance;
HuCard listening/final release validation; the requested parallax extension;
final full-expansion acceptance. The full goal remains active.

## R5 exact-blue allocation constraint (shade-count repair above)

The source blue material has five RGB3 steps; its current conversion has four,
merging (0,0,3). An exhaustive two-bank assignment search over the 17 maximal
8×8 character color sets proves that restoring this shade while preserving all
current material colors cannot fit the two 15-opaque-color background palettes.
The total is only 28 colors, but the required per-character combinations force
additional duplication between banks. No palette change was made: silently
restoring blue by flattening another material would not satisfy the shading
requirement. Evidence and a source/current blue-strip image are in
`.local/bc-r5-blue/audit.json`, `packing-study.py`, `blue-source-current.png`.
A broader material/palette redesign remains necessary for this loss; the test
only rules out lossless reassignment of the current colors plus the missing blue.

## Rejected large-actor cache experiments

On current `e7f24f2a…`, caching the last large actor sprite within a frame kept
600 simulation/workload records and all post-flush VDP hashes identical in both
heavy four-player HuCard samples. R6 improved 1128→1119 frames, but R7 regressed
980→1006. Actor-local VRAM residency hints with validated slot keys also preserved
state/video, but cost 1134/1012 frames; a fixed-offset alias view cost 1133/1007.
All three variants were rejected and the original sprite renderer was restored.
Evidence: `.local/bc-big-repeat/rejected-experiments.json`, including per-ROM
hashes and both baseline traces. These results do not justify retaining a
round-specific optimization solely to fit the measured sample.

## Rejected player/terrain performance experiments

Keeping the weapon dispatcher out of the player update preserved all 600
simulation/workload records in each four-player HuCard sample but slowed R2
736→786 frames and R6 1128→1150. Shared 1/2/3/4P behavior checks passed. Rejected.
Replacing terrain address arithmetic with two 128-word tables passed 33,554,432
coordinate probes (including all 16-bit wrapping), but slowed R2 736→757 and
R6 1128→1139, again with identical gameplay/workload records. Rejected. The prior
source and ROM are restored; neither experiment is part of the expansion.
Evidence: `.local/bc-terrain-offsets/rejected-experiments.json`, plus the native
profiles in that directory and `.local/bc-weapon-dispatch/`.

## Rejected shot-index performance experiments

On current build `72d4005b…`, pointer `restrict` hints produced identical ROM
bytes. Keeping four index bounds local preserved all 600 state/workload records
but changed R2 4P HuCard timing from 736 to 750 frames and R6 from 1128 to 1125.
Keeping only X bounds local changed those samples to 747 and 1133 frames. Both
variants also increased attributed shot-index ticks. All native/host differential
checks passed, but both changes were rejected for timing regression and the
source was restored. Evidence: `.local/bc-index-alias/rejected-experiments.json`,
including the candidate hashes and native probe logs (4096 complete indices).
Further performance work should target player/actor update costs; do not retain
these local-bound experiments based on their shorter native micro-probe alone.

## Retained character-storage improvement

Previous retained build: `8fb77859ad36f412ee25bd28b95c4a849801624d6bdd87ea2278d37dc95cd55a` (4 MiB).
The offline BC character packer now uses all sixteen slots in a DMA block when
an active character can safely occupy index zero. It tracks which low-priority
PAL0 characters cannot occupy that slot, splitting incompatible groups rather
than producing a zero/inactive template. This replaces the unconditional spare
slot and unchanged-full-block fallback; no runtime renderer changes are needed.

Private storage falls from 249 to 224 blocks, saving 12,800 bytes. All 689 mapped
cells / 705,536 rendered pixels, 320 palette words, ten source/collision banks
and 113 Normal blobs remain unchanged. Native coverage checks 499 camera views /
576,064 subtiles with each encounter's boss reserve. Normal/BC/Rush handoff passes.
The protected four-player HuCard R6 sample retains all 600 simulation, workload
and scene-tick records and takes the same 1,125 video frames. This preserves the
previous build's timing; it does not close the broader performance requirement.

ROM headroom is now 19,772 bytes. Logical sources remain 473, including 131
Normal references. A full rebuild reproduces the cartridge byte for byte.
Evidence: `.local/bc-character-capacity/`. The R5/R6 visual
repairs below are retained without pixel changes. R2/R7 materials, remaining
shading corrections, performance, HuCard listening/final release validation and
the parallax extension remain open. The full goal remains active.

## Retained R6 material replacement

Previous retained build: `38b276f56c4fa323d304af91209c9d96cc8b2a0707b7e6c548952dfca20444f5` (4 MiB).
BC round six now uses the corresponding Normal zone-13 mechanical shaft,
replacing generic zone-one placeholders. Whole source characters compose the
pale machinery, dark supports, curved housing and complete octagonal connectors.
Diagonal edges use the central donor characters to keep their joins continuous.
Both original source palettes fit into its two background banks; every opaque
source shade survives Genesis RGB3 quantization without additional palette fitting.
Bijective pen renumbering preserves these colors while allowing exact byte reuse.

All 131 cells / 134,144 geometry pixels and 76,272 opaque shade pixels match the
specified original-source composition. All ten source/collision banks, 558 other
round cells and 113 Normal blobs remain unchanged. Native route coverage passes
23 cameras / 29,280 subtiles with the six-block R6 boss bank reserved. Native
Standard/Vivid palette upload checks pass across all ten rounds. The main review
retains its decision IDs and passes rendering/persistence/export/filter checks.

The protected four-player HuCard R6 sample preserves 600 simulation and workload
records, but takes 1,125 video frames versus 1,124 before: a one-frame regression,
not full-speed acceptance. ROM headroom is now 6,972 bytes; the shared bank has
473 logical sources, 131 Normal references and 249 private blocks. A second full
build reproduces the cartridge byte for byte. Further space
recovery is needed for the remaining expansion work. Evidence and comparison:
`.local/bc-r6-materials/`; native captures: `.local/bc-background-draft6/`.

Remaining work includes R2/R7 material replacements, shading corrections outside
R5/R6, performance, HuCard listening/final release validation and the requested
parallax extension. R6 composition remains inferred rather than user-approved.
The full expansion goal remains active.

## Retained Vivid shade guard

Previous retained build: `90870c13d73e054c3567d3adc47e38a199377a20dd6c084da573855794def836` (4 MiB).
The default Vivid transform now preserves ordered shades already present in the
converted assets. An offline guard checks componentwise shade pairs in 58
palette banks, including gallery colors, and 476 explicit BC material ramps.
It falls back to Standard colors where the boost merges/reverses shade order.
All 1,307 constraints pass; 62 old violations are removed by changing 56 of the
512 lookup entries. This cannot recover upstream quantization losses.

The linked cartridge differs from the previous build only in 87 lookup bytes
and its two-byte checksum. Runtime code, Standard palettes, graphics, stage
banks, bosses/attacks, audio and ROM space are unchanged. Native checks verify
640 CRAM words across all ten BC rounds in Standard and Vivid, plus return to
the menu. The protected four-player HuCard R5 sample preserves 600 simulation
and workload records and takes the same 853 video frames; all ten late flushes
finish inside VBlank. This is regression evidence, not full-speed acceptance.
A second full build reproduces the cartridge byte for byte.
Evidence and visual comparison: `.local/vivid-shade-guard/`.

The complete expansion remains unfinished: upstream shading losses, remaining
R2/R6/R7 materials, performance, HuCard listening/final release validation and
the requested parallax extension remain open. New parallax must preserve tile
joins and pass four-player timing comparisons before retention.

## Retained R5 source-shading repair

Previous retained build: `e2e77365c2189263b8162c617202b28fba0e335793c5053c3fa57a03ceda8bc1` (4 MiB).
BC round five now repacks its reused Genesis-source characters before the old
Normal palette fit loses their shade distinctions. Its own two background
palettes fit only the materials used in this round; unused Normal assets and
starfield colors no longer displace visible shades. The source geometry and
corrected complete window assemblies remain unchanged. No runtime conversion,
additional palette banks, or additional per-frame processing is introduced.

Both pink and purple main rock ramps retain all five original Genesis-gamut
steps. The neutral rock highlight is exact. Blue texture shades and the main
blue-gradient steps are protected; the five-color gradient retains four colors,
with lower color error than the old four-color result. Source checks cover all
74,752 geometry pixels and 53,949 protected-shade pixels. Across each of the five
used source material groups, pixel-weighted squared RGB error is lower than in
the old Normal conversion. This is measured color improvement, not a claim that
every unprotected source shade is exact or that the user has approved the art.

The source scripts/collision banks, 616 other-round cells and 113 Normal blobs
remain unchanged. Native R5 rendering passes 36 cameras / 44,352 subtiles with
the ten-block PCE boss bank reserved. The protected four-player HuCard sample
preserves 600 simulation/workload records and takes the same 853 video frames;
ten late flushes finish inside VBlank. Boss/attack/serpent and review checks pass.
A full rebuild reproduces the cartridge byte for byte.
`_etext=0x3f68c4` leaves 38,716 bytes. The 361 logical sources reference 140 Normal
blocks and 195 unique private blocks. Evidence: `.local/bc-r5-shading-fix/`;
current linked-ROM comparison: `.local/bc-r5-materials/index.html`.

This repair closes the identified rock-ramp and highlight loss in BC R5, not the
broader shading audit. Other Normal/BC backgrounds and sprites still need review
and corrections. Remaining work also includes round 2/6/7 material replacements,
performance, HuCard listening/final release validation, and the user's parallax
extension request, which requires no four-player timing regression.

## Previous window-assembly build

Previous retained build: `9325951092e1f6941f0bcb031a37a5c4d629e8afca35aeb6afd0c901ca516f2a` (4 MiB).
The user's round-five review identified two distinct problems: missing original
shades from the shared conversion and mismatched window pieces. The window
geometry is corrected: patterns 59/5A/5C/5D now assemble the complete Normal
metatile 61, with matching wall-frame halves. Four complete windows in the
source map match all 4,096 donor pixels. The next window is clipped by the
source-map edge and is not counted as complete.

All 73 R5 cells / 74,752 donor pixels, 36 native cameras / 44,352 subtiles,
unchanged source banks, 616 other-round cells and 113 Normal blobs pass.
The protected four-player HuCard sample retains 600 simulation/workload records
and takes 853 video frames before and after; ten late flushes finish in VBlank.
Original PCE boss/attack/serpent checks and review persistence/export/filtering
pass. A second full build reproduces the ROM byte for byte.
Evidence: `.local/bc-r5-wall-fix/`; updated comparison:
`.local/bc-r5-materials/index.html`.

### User-rejected shading remains a release blocker

Earlier statements that donor shading was preserved only proved equality to
already-quantized Normal assets. They did **not** prove original shading
survived the shared conversion. Do not count that equality as art acceptance.
The user explicitly requests checking flatter/posterized shading everywhere.
`tools/audit_asset_shading.py` compares source colors after direct Genesis-gamut
conversion to actual packed assets. It flags color merging in 935/1,344 Normal
background metatiles, 2,605/2,905 original-key small sprites and 786/813 original
large composites. These are diagnostic counts, not counts of visibly defective
assets. BC recolor/import variants and the authored organic set still need
separate coverage. Evidence: `.local/shading-audit/audit.json` and its HTML page.

A protected-ramp zone-10 prototype restores pink/purple rock steps and neutral
highlights but worsens machinery. It is **not** in the ROM. Fix both rather than
accepting that tradeoff. The complete-window correction does not close shading.
Round-six matching is also a local prototype, not a production replacement.

### Additional parallax request

The user requests parallax in all levels with tiled backgrounds, conditional on
no performance drag. Evaluate Normal and BC, reusing the existing Home parallax
system where appropriate. Preserve collision, background joins, boss resource
reservations and the user's toggle; require four-player timing evidence before
retaining each extension. Existing Home stars and section-five far texture do
not prove this broader request complete. No new parallax is implemented yet.

## Previous character-storage build

Previous retained build: `ae67a8c4686ca91bdb222fbca96d517fe062cbe1834f161071c24388990ecb90` (4 MiB).
Exact background character reuse frees 31,232 bytes for remaining scenery.
Logical metatile IDs, cache behavior, pixels, colors, priority and flips remain
unchanged. A generated source block may contain a shared subset of characters;
per-cell templates select the correct indices. No runtime conversion or
decompression is introduced: each cache miss still uploads one 512-byte block.
PAL0 index-zero and active-transparent-character cases are explicitly checked.

All 689 cells / 705,536 rendered pixels, all 320 palette words, ten stage banks
and 113 Normal material blobs match the previous cartridge. Native loader
checks pass 499 cameras / 576,064 subtiles across all ten rounds, with actual
boss banks reserved. Normal → BC → Rush → BC → Normal handoffs pass. Original
PCE bosses, attacks and serpent pass current-ROM pixel/shading/render checks.
The 893-card review passes persistence, export and filtering checks.

The protected four-player HuCard R5 sample preserves all 600 simulation and
workload records and takes the same 853 video frames. Ten late video flushes
finish inside VBlank. Full speed remains unverified. The 361 logical sources
reference 147 Normal blocks and 190 unique private blocks (214 references).
`_etext=0x3f5ec4` leaves 41,276 bytes. A second full `make` reproduces
the cartridge byte for byte. Evidence:
`.local/bc-character-storage/`.
The remaining work is still corresponding backgrounds for rounds 2, 6 and 7,
performance, subjective HuCard listening and final release validation.

## Previous round-five build

Previous retained build: `67da8b9464208872b2c9ec88a91f3a81a80a73900fc8350a3acfe91a41cd8ae5` (4 MiB).
Round five now uses corresponding Normal zone-10 pink and purple cavern rock,
skulls, bones and machinery. Whole eight-pixel characters preserve original
Normal colors and shading. Complete decorative objects are adapted to the PCE
cell dimensions; these inferred compositions are not additional user approvals.
Source pattern plus palette identity distinguishes pink and purple variants.

All 73 mapped cells / 74,752 pixels and 32 palette words pass material checks.
All ten source script/collision banks, 616 other-round background cells and
113 Normal material blobs remain unchanged. Native rendering passes 36 camera
positions / 44,352 subtiles with the ten-block original PCE boss bank reserved.
All original PCE boss bodies, attacks and serpent pass on this cartridge.
The refreshed 893-card review passes persistence, export and filtering checks.

The protected four-player HuCard round-five sample retains all 600 simulation
and workload records and takes 853 video frames both before and after. Ten
late video flushes finish inside VBlank. This is not full-speed acceptance.
The pool now contains 361 logical blocks: 110 reused Normal blocks and 251
private blocks. `_etext=0x3fd8c4` leaves 10,044 bytes of payload space.
A second full `make` reproduces the cartridge byte for byte.
Evidence and linked-ROM comparison: `.local/bc-r5-materials/`.
Rounds 2, 6 and 7 still need corresponding background material replacements;
performance, subjective HuCard listening and final release validation remain.

## Previous round-three build

Previous retained build: `435e4cba92076110471eefd44159e412f02e3d81971c8af8723397fd36fe477c` (4 MiB).
Round three now uses the detailed Normal zone-3 cyan rock and corresponding
embedded machinery instead of the coarse zone-one substitutions. All original
Normal palette colors and character shading are retained. Eight-pixel donor
recipes follow the primary PCE pattern layout, with subject-corrected striped
supports and yellow emitters. The 81 primary material cells are adapted Genesis
compositions; 50 additional mapped IDs use defensive machinery fill at the
expanded viewport margins. They are not claimed as faithful PCE artwork.

Checks verify all 131 mapped cells / 134,144 pixels, all 32 palette words,
unchanged source scripts/collision banks, 558 unchanged cells in the other
nine rounds and 113 unchanged Normal material blobs. Native camera checks cover
57 positions / 63,840 subtiles with all six boss blocks reserved. The native
checker now reserves the actual boss bank for rounds one through four as well
as later rounds; all four pass (276 cameras, with 3/7/6/8 blocks reserved).
Original PCE bosses, shots and serpent pass on
this cartridge. Review persistence/export/filter checks pass.

The protected four-player HuCard R3 sample preserves 600 simulation/workload
records, taking 710 video frames versus 708 before. Seven late video flushes
finish inside VBlank. This is not full-speed acceptance. The source table now
has 307 logical entries (109 Normal blocks and 198 private blocks), with
`_etext=0x3f66c4` and 39,228 payload bytes remaining. Rounds 2, 5, 6 and 7 still
need material matching; full-speed and release validation remain open.
Evidence and visual comparison: `.local/bc-r3-materials/`, especially
`materials.json`, `native.log`, `timing-comparison.json`, and `index.html`.

### Prior cartridge: Normal/BC background source sharing

Current retained build: `40a7131f0b62c7817ed670540614b4186507167f5eb6f046763981236e8640d8` (4 MiB).
BC's logical background bank now reuses 113 byte-identical Normal blocks at
their existing ROM addresses, retaining 138 private blocks. A 251-entry source
table is read only on background cache misses; no decompression is introduced.
The shared loader accepts an optional source table and clears it on Normal,
Boss Rush and session-reset paths. This saves 56,832 linked bytes, leaving
71,996 bytes below 4 MiB (`_etext=0x3ee6c4`). It makes room for the pending
round-three materials without dropping artwork; those materials are not yet
linked in this cartridge.

All 689 BC cells / 705,536 pixels, 320 palette words, ten source stage/collision
banks and 113 Normal material blobs remain identical. The complete logical
pattern bank is also byte-identical. Every source is 512-byte aligned and stays
within a fast-DMA bank. Native rendering passes 499 cameras / 576,064 subtiles
across all ten BC rounds, including boss reservations. R4/R8/R9 material checks,
final-chamber checks and original-PCE boss/shot/serpent checks pass. Populated
Normal → BC → Rush → BC → Normal transitions verify the indexed source table
is selected only for BC and cleared on release/restart.

Four-player HuCard R4 preserves 600 simulation/workload records; video frames
change from 1,119 to 1,113 and the one late video flush remains inside VBlank.
Four-player Normal's ten 600-update samples preserve all 6,010 state and 6,010
sprite-render records and every section's frame count. Worst measured updates
increase by two scanlines in sections 2, 5 and 8; the other seven are unchanged.
These bounded comparisons do not establish full-speed or full-campaign release
acceptance. Review persistence/export/filters pass. Evidence:
`.local/bc-normal-storage/`, particularly `equivalence.json`,
`native-summary.json`, `mode-handoff/`, `timing-comparison.json`, and
`normal-comparison.json`.

### Prior cartridge: round-four materials

Current retained build: `8be9cec0372dbebe5d89ae87c2c479d078e54fb627f369f9e0aebb98bccee53a` (4 MiB).
Round four now uses the corresponding Normal zone-6 grass ledges, organic
rocks, attached weapon/machinery details, vertical supports and oval machinery.
The previous generic zone-one stone and robot-face substitutions are removed.
Colors remain from the original 32-word Normal palette, without averaging or
recoloring. The isolated boulder is sampled smaller; the narrower machinery
uses whole 8-pixel characters to avoid mixing palette banks. This is adapted
Genesis scenery, not identical PCE outlines. Off-route margin cells 24/45/60
retain defensive machinery fill from the same material bank.

Checks verify 25 cells / 25,600 pixels, 58 native camera positions / 64,960
subtiles, unchanged source script/collision banks for all ten rounds, 664
unchanged other-round cells and 113 unchanged Normal material blobs. The
original PCE bosses, shots and serpent pass current-ROM checks. Review choice
IDs, persistence, exports and filters remain intact. A PAL0 first character
uses stored horizontal mirroring plus the hardware flip bit to avoid confusing
its template with the renderer's zero/inactive sentinel; the effective pixels
are checked independently in the linked ROM.

The protected four-player HuCard sample preserves 600 simulation/workload
records. Video frames increase from 1,113 to 1,119; the one late video flush
finishes inside VBlank. This is not full-speed acceptance. The linked payload
ends at `0x3fc4c4`, leaving 15,164 bytes. Remaining background matching,
performance and final release validation remain open. Evidence and comparison:
`.local/bc-r4-materials/`, especially `materials.json`, `native.log`,
`timing-comparison.json`, and `index.html`.

### Pending round-three composition and storage requirement

An isolated draft in `.local/bc-r3-materials/` replaces the coarse cyan rock
substitutions with corresponding Normal zone-3 quadrants and machinery. It is
not linked: 307 shared blocks would need 30,464 more raw data bytes, exceeding
the current 15,164-byte payload margin. `normal-storage-audit.json` identifies
113 current BC blocks already stored byte-identically in Normal banks (57,856
bytes). An indexed source table could recover approximately 56,852 raw bytes
after its 1,004-byte pointer table; linked savings remain unproven. Implementing
that needs shared-renderer DMA, bank-boundary, mode-switch and timing checks.
Do not simplify or discard the matching art merely to fit the old storage.

The first-character sentinel audit passes all ten current generators: no
nonempty characters have inactive templates. `write_scenery` now rejects that
case; its negative check rejects a deliberately hidden character. Regeneration
leaves every current scenery C file byte-identical. Draft comparison and
pattern candidates are in `.local/bc-r3-materials/index.html` and `definition.json`.
Small machinery joins and defensive margin fills still need review before the
round-three draft is accepted.

### Prior cartridge: mirrored background storage

Current retained build: `9ad26f832408203b90f79cda7bbebbd79cb625f75a3b0b9d0fbe6396d377d158` (4 MiB).
Whole mirrored background blocks now share storage using the renderer's
existing flip bits. The bank drops from 255 to 231 blocks, saving 12,800 linked
bytes and leaving 25,916 bytes below 4 MiB (`_etext=0x3f9ac4`). No scenery,
source script/collision bank, palette or Normal material is changed.

The linked comparison decodes effective pixels and palette/priority attributes
rather than requiring identical physical bank ordering. It verifies 689 cells /
705,536 pixels, 320 palette words and 113 Normal blobs. Native checks pass all
ten rounds, 499 camera positions and 576,064 subtiles. R8/R9 material checks
and original-PCE boss/shot/serpent checks also pass. The review retains decision
persistence/export/filter behavior.

There is a measured tradeoff: the protected four-player HuCard round-nine
sample keeps all 600 state/workload records identical but increases video
frames from 871 to 878 (0.8%). Eight late video flushes finish inside VBlank.
This is a storage improvement, not a performance acceptance result. Full-speed
and final-release work remain open. Evidence: `.local/bc-mirror-pool/`, including
`equivalence.json`, `native-summary.json`, and `timing-comparison.json`.

### Prior cartridge: round-nine chamber materials

Current retained build: `ead9251276cf8d57718b963ccfd5b0cb42121a52dd25130eecab7dc1a86adbd4` (4 MiB).
Round nine now uses the corresponding Normal zone-19 chamber walls, floating
panels and ornament instead of unrelated zone-one machinery. Whole 8-pixel
characters preserve original material shading and both palette banks. The
narrower PCE chambers require shortening and rearranging these characters;
this is adapted Genesis scenery, not exact PCE background geometry.

Checks verify 49 source cells / 50,176 pixels and all 32 original palette
words. All ten stage/collision banks, 640 other BC cells and 113 Normal blobs
remain unchanged. Native rendering passes 103 cameras / 118,720 subtiles,
including boss-bank reservations. The protected four-player HuCard opening
preserves 600 simulation and workload records; video frames are 873 before
and 871 after. Five late video flushes complete inside VBlank. These bounded
checks do not establish full-speed gameplay or complete release acceptance.
Original-PCE boss body, projectile and serpent checks pass on this ROM.

Evidence and visual comparison: `.local/bc-r9-materials/`, especially
`materials.json`, `native.log`, `timing-comparison.json` and `index.html`.
The shared background bank now contains 255 blocks. Linked payload ends at
`0x3fccc4`, leaving 13,116 bytes in the 4 MiB cartridge.

### Prior cartridge: round-eight machinery

Current retained build: `3f9a03694519b0730bb4a1c2bcd04271cd2b9d68acc611b8632f7b7f17f14aad` (4 MiB).
Round eight now uses the corresponding Normal zone-16 red pipe lattice,
crossed panels and cylindrical assemblies, replacing eight unrelated zone-one
machine blocks. Its 45 mapped cells compose 62 Normal material quadrants into
42 blocks. Every material pixel and all 32 palette words retain Normal colors
and shading. PCE repeats the cylinder every three 16-pixel quadrants; Normal
uses four. The adaptation shortens barrel sections at quadrant boundaries while
preserving all four original quadrants of each complete circular front. This
is adapted Genesis scenery, not exact PCE geometry. The live boss and attacks
remain original-PCE imports.

The ROM check verifies 180 material quadrants / 46,080 pixels, the intact
1,024-pixel circular front, all ten original source script/collision banks,
644 unchanged cells in other BC rounds, and 113 unchanged Normal material
blobs. Native rendering passes 30 camera positions / 36,736 subtiles. Cell
0x81 retains a nonblank pipe filler outside the sampled gameplay route; mapped
cells 0x23, 0x28 and 0x29 are also absent from those viewport samples.

The four-player HuCard opening has identical 600 simulation/workload records
and 1,017 video frames before/after; four late video flushes remain within
VBlank. A longer protected controller-fire route reaches the original R8 boss
at update 26,715; the explicitly forced-defeat test reaches all clear phases,
waits 421 updates, and reaches the loader handoff. It does not load round nine
or claim an unassisted clear. Stage, boss and clear cues (tracks 8/18/10) are
audible, with zero underruns, unmapped art or software submission drops/remaps.
The earlier fixed 7,500-update test trigger was too early for this co-op route;
the test now waits for the actual boss and exercises its entry before defeat.
Original-PCE boss body/shot/serpent checks and review persistence/export/filter
checks pass. Full-speed and final-release acceptance remain incomplete.

Evidence: `.local/bc-r8-materials/`, especially `materials.json`, `native.log`,
`timing-comparison.json`, `clear-4p.log` and the PCE/before/current `index.html`.

### Prior cartridge: shared background storage

Current retained build: `78267701770ff7847ffbf8133a1f39ebbe0cbe4287e10eea738ac10d18e9b893` (4 MiB).
Identical background pattern/template blocks now share one aligned bank across
all ten BC rounds. Each round keeps its own palette and original cell remap;
there is no runtime decompression, new renderer branch, or artwork reduction.
265 per-round blocks become 172 unique blocks, saving 50,592 data bytes and
53,248 bytes in the linked payload after alignment. This makes room for the
remaining faithful background replacements; it does not itself fix round eight.

All 689 source cells / 705,536 pixels, 320 palette words, ten source code and
collision banks, and 113 Normal material blobs match the preceding cartridge.
Native background checks pass 499 camera positions / 576,064 subtiles across
all ten rounds. Their old six-block boss-seven/nine assumption was replaced
with each imported boss bank's actual block count; the preceding ROM also
reserves five blocks for boss seven. No renderer behavior changed.

Four-player Normal's ten 600-update sections have identical 6,010 state records,
6,010 sprite-render records and all ten timings. Four-player HuCard R8 has
identical 600 state/workload and 599 VDP records, with 1,017 frames before/after;
R10 has identical 600 state/workload records, with 1,053 frames before/after.
All 21 HuCard tracks pass NTSC/PAL (840 packet checks, zero underruns), and
original-PCE boss body/shot/serpent checks pass. The review's stable IDs,
decisions, export and filters remain intact. Full-speed and release acceptance
remain incomplete. Evidence: `.local/bc-background-pool/`, especially
`equivalence.json`, `native-summary.json`, `normal-comparison.json`,
`r8-comparison.json`, `r10-comparison.json`, and the two HuCard results.

### Prior cartridge: final-chamber artwork correction

Current retained build: `ac49fb58a12d70286d89b3e68f082455f2ebce7b4f6a2f47cd946c4a18045317` (4 MiB).
Round ten now reuses the actual Normal final-chamber mechanical face from zone
21, replacing unrelated zone-one machinery. Its intact 4×5-cell composition and
all 32 palette words are preserved. The PCE version redraws/offsets details
within its cells; this is the matching Genesis scenery, not exact PCE pixels.
The live serpent boss and attacks remain original-PCE imports.

`qa_bc_final_chamber.py` proves 20,480 Normal face pixels and all 20 source IDs,
all ten original source code/collision banks unchanged, rounds 1–9 scenery
unchanged, and all 24 Normal zones unchanged. Native rendering verifies 1,120
subtiles including mirrored cells. Ten shared blocks replace thirteen old
blocks, using the renderer's existing flip bits. One- and four-player protected,
forced-defeat serpent checks pass all six heads and the ending handoff with no
software drops/remaps. A 600-update four-player HuCard comparison has identical
simulation/workload records and takes 1,053 video frames versus 1,055 before.
This remains below full-speed acceptance. The boss pixel/shading/render checks
and review-page persistence/export/filter checks also pass on this cartridge.

Evidence: `.local/bc-final-chamber/`, including `composition.json`, `native.log`,
`scene-4p.log`, `timing-comparison.json` and the before/PCE/current `index.html`.
The complete protected campaigns described below are from the immediately
preceding cartridge; this scenery-only change has not repeated full campaigns.

### Prior cartridge: sparse train allocation fix

Current retained build: `9d049f5d218d262d9da79b4cc25644286855ae033020c928fad0d81d66933e54`
(4 MiB). The 3P/4P train allocator now falls back to eight ascending free slots
when a contiguous eight-slot run is unavailable. Explicit predecessor/successor
indices occupy otherwise unused train scratch bytes. Existing actors are not
moved; complete formations, member order, tail fire, head promotion and delayed
deaths remain intact. Original 1P/2P allocation and successful contiguous births
retain their source behavior. Template reuse clears the sparse-link marker.

Both protected Home-launched campaigns now complete all ten rounds, ending,
credits and Home return: 3P takes 106,607 updates / 163,847 video frames including
the ending; 4P takes 120,310 updates / 211,989 video frames including the ending.
No boss defeats, weapons, health or score are seeded. Both runs have zero audio
underruns, unmapped art, software sprite drops or remaps. This resolves the
reproduced fragmented-pool round-two stall below; it is not unassisted or
full-speed acceptance.

Host verification covers 288 sparse formations, 115,200 lifecycle update
batches, 1,728 head deaths, 288 tail shots, 192 reused members and 24 unchanged
allocation failures, all six train rounds / both variants. Six thousand
contiguous three-pass loop cases match the archived dispatcher; original R2
captures match 4,999 loops / 108,372 actor updates. Birth-contact, wave-count,
queue and four-player input/respawn/re-entry tests pass. Normal's 6,010 state and
render records and all ten section timings are unchanged. All 21 HuCard tracks
pass NTSC/PAL (840 packet checks); original boss/attack/serpent render checks
pass. HuCard opening totals change 16,185 to 16,183 frames, with small local
regressions; performance remains incomplete.
Evidence: `.local/bc-sparse-train/`, especially `campaign-summary.json`,
`lifecycle.json`, `normal-comparison.json` and the archived accepted build.

### Prior campaign failure and scene optimization

**Historical campaign finding on ff6350 (fixed above):** the retained build completes a protected 3P
Home-to-ending campaign (112,707 updates, 172,568 video frames including ending)
with all ten rounds, audible mapped HuCard music, zero underruns, zero software
sprite drops/remaps and no unmapped art. The same controller policy with 4P
stalls at round two, camera (1840,512), through the 180,000-update limit.
Independent 12,000/26,000-update captures reproduce the stall. Stage handler
`ba7c` needs eight contiguous slots; at 26,000 updates 28 slots are free but
no free run exceeds seven. Camera holding on failed formation allocation keeps
the pool fragmented by surviving ceiling enemies. This is an unresolved
progression case, not release acceptance or an unassisted campaign claim.
Prioritize preserving complete formations while resolving this retry stall.
Evidence: `.local/bc-scene-outline/campaign/summary.json` and `4p-probe/`.

Current retained build: `ff6350ddea8ac78bac8a816a19201d86cd6ff315f7c7ebefcb2df4c0fd27e875`
(4 MiB). `bc_scene_frame` is kept outside the shared game-loop function with
`noinline`, isolating a useful compiler decision discovered in the rejected
round-six experiment. No actor specialization or gameplay changes are retained.
The twenty HuCard samples improve 16,596 to 16,185 video frames (19 improve;
R3/3P regresses by one), and the Arcade samples improve 13,111 to 12,963 with
no regressions. R6/4P's 6,000-update HuCard run improves 11,091 to 10,934 frames,
with no audio underruns: approximately 55% simulation speed, still unfinished.
The instrumented R6 check improves 1,140 to 1,121 frames, matches 600 state and
599 VDP records, and passes independent uninstrumented replay and video timing.
Normal 4P matches all 6,010 state and render records across ten 600-update
sections, with identical frame counts and zero sprite drops/remaps. The existing
Normal timing failures remain. Four-player controls, respawn and re-entry pass;
all 21 Sound Test tracks pass in NTSC/PAL (840 packet checks), and all original
boss bodies, attacks and serpent render checks pass. The boss review is refreshed.
Evidence: `.local/bc-scene-outline/decision.json` and adjacent reports.

### Prior retained build and VBlank repair

Current retained build: `281c4fdd48224091c349f210f671af6706ebacd518504eb337bd9ad9afab69f0` (4 MiB).
It combines the HuCard pitch tables with a coherent VBlank admission check:
the scanline sample must not span VInt, and line 224 is excluded. The former
pitch-table failure was traced to a stale line-224 sample surviving HuCard
VInt processing through line 258, admitting video transfers too late.
The candidate passes the 600-update R6/4P HuCard comparison: 1,147 to 1,140
video frames, identical 600 state/workload and 599 VDP records, and independent
uninstrumented replay. The twenty HuCard samples improve 16,874 to 16,596 video frames (18 improve,
one unchanged, R1/4P regresses by four). Arcade samples increase 13,101 to
13,111 frames across six cases. These small regressions are retained for the
correct VBlank admission and overall HuCard improvement; neither matrix is
full-speed. The 6,000-update R6/4P HuCard run improves 11,150 to 11,091 frames
without audio underruns, still only approximately 54% simulation speed.
All 21 Sound Test tracks pass in NTSC and PAL, with 840 packet comparisons,
no underruns, correct playback clocks, stop and source switching. PAL uses
a region-patched fixture ROM recorded in its report. All 8,192 linked pitch
words match independent arithmetic, and 524,288 FM frames / 3,145,728 voices
match the reference across both regions. The timing verifier rejects the
archived unsafe candidate and accepts this corrected capture.
All nine composite boss bodies, four composite attack poses, fifteen projectile
variants and twenty final-serpent poses pass current-ROM geometry/shading/render
checks. The composite review page has been regenerated from this candidate.
Evidence: `.local/bc-vblank-coherent/` and the three boss-art QA reports.

### Previous validated cartridge evidence

The previous build is `out/release/rom.bin`, SHA-256
`0156af010096b01d74ef8166e74d396601ce4bc66945d11e44d13b272512e9af`.
The latest change checks the two score-stream bytes directly for zero rather
than assembling an offset for the active-channel test. All 166,377 captured
score ticks across 18 distinct tracks still match. HuCard twenty-sample timing
improves 17,003 to 16,874 frames, with regressions in R1/3P (+1), R3/3P (+1),
R6/4P (+2), and R8/4P (+3). Arcade timings remain unchanged. A longer R6/4P
run takes 11,150 versus 11,165 frames for 6,000 updates, with active music and
no underruns; this is only about 54% simulation speed, not full-speed evidence.

The short instrumented R6 comparison retains all 600 state/workload and 599
VDP records but fails its timing gate (1,145 to 1,147 frames). That failure is
preserved; the change is retained for the net matrix and longer-run gain.
NTSC/PAL Sound Test checks pass all 21 tracks, 840 published-packet comparisons,
clock, queue, STOP and source switching. The ROM still fits 4 MiB.
Evidence: `.local/hucard-stream-active/`.

The preceding ROM `8746a25a7b57459e4c233aeac0b3f7cf4305427d36e236c03e0f240459b01b23`
caches the nine non-pitch FM packet bytes per voice, keyed
by volume, pan and instrument, using 72 additional RAM bytes. The mathematical
comparison passes 524,288 complete frames / 3,145,728 voices, including repeated
settings written into a different poisoned destination. All 21 cartridge Sound
Test tracks pass NTSC/PAL checks, with 840 exact published-packet comparisons,
zero underruns, correct clocks and STOP/source-switch behavior.

Twenty HuCard 3P/4P openings improve from 17,447 to 17,003 frames: nineteen
improve, while R1/3P costs two extra frames. All twenty Arcade timings are
unchanged. R6/4P matches all 600 state/workload and 599 VDP records while
improving 1,158 to 1,145 frames; the latest late flush ends at line 257.
The 990-update four-player fixture passes independent controls, individual
respawn and Home/reentry with no drops/remaps. The ROM remains 4 MiB and the
sound bank remains at `0x2c0000`. Evidence: `.local/hucard-timbre-cache/`.
These bounded checks still do not establish full-speed or campaign acceptance.

The preceding ROM `a9736b57ac0fcab814aa022a29a55e7593df8090e196183203a7fd2afebc026f`
packs CPU-read zone maps, attributes and palettes on word
boundaries, retaining 512-byte alignment for DMA resources. This recovers
23,552 bytes before the sound bank for future code growth; the sound bank stays
at `0x2c0000` and the finalized cartridge remains 4 MiB. All 163 linked binary
assets (2,431,868 bytes) match the prior ROM and generated source exactly.
Ten Normal 4P sections pass 6,000 updates / 6,010 state and sprite records
with identical timing. Separate one-player checks match 1,200 complete
VRAM/CRAM/VSRAM snapshots over all ten sections. All twenty BC HuCard timing
samples also remain identical. Evidence: `.local/rom-metadata-packing/`.
This is layout headroom, not a new runtime speed gain or full-campaign proof.

The preceding ROM `33b49362df200d9740a92d358aee011366e92a57e39156f489d5c9d5813b5cfa`
copies each 72-byte HuCard packet with eight byte writes per
loop, reducing VInt work and Z80 bus ownership without changing packet contents.
Twenty 3P/4P HuCard opening samples improve from 17,763 to 17,447 video frames
for 12,000 total updates. Nineteen improve; R2/3P costs one additional frame.
All twenty Arcade-music timings match the prior accepted matrix exactly.
The instrumented R6/4P comparison passes all 600 state/workload and 599 VDP
records (1,161 to 1,158 frames), with its late flush ending at scanline 253.
All 21 actual Sound Test selections pass in NTSC and PAL, including 840 exact
published-packet checks covering every queue slot, zero underruns, correct
clock, silent STOP and Arcade-source restoration. Evidence is in
`.local/hucard-packet-copy/`. Heavy HuCard workloads still miss full speed.

The timing tools now explicitly support HuCard selection through Home Options.
Their older default matrices measured Arcade playback. Cross-source frame
counts are not a controlled music-only comparison because the HuCard fixture
also enters Home configuration; the before/after HuCard optimization tests use
identical menu paths and inputs.

The preceding ROM `ef853ea841cbffda4b71419cbbcd8eb72aae16c4da3a9e75f54c181efad56b78`
corrected three round-one background cells: `12` restores
city material on the left and water on the right; `28` and `32` trim oversized
rock donors to low-edge contours. The contours agree across 29 PCE gameplay
captures. Only those three decoded cells change; all ten background palettes
retain their Normal colors. The emulator verifies 103 camera positions and
115,360 subtiles. The ROM remains 4 MiB with identical symbol addresses; all
923 bytes changed from the previous ROM belong to round-one art/templates or
the checksum. Evidence is in `.local/bc-r1-edge-fixes/`.

The preceding waterfront correction (`.local/bc-r1-waterfront-fix/`) removed
the unrelated blue hill from cell `10`, using Genesis city and water material.

The following boss, audio and timing evidence was recorded on preceding ROM
`62e6af760aa88f11df9466d66590c97c0c2d2d59ee254ce1479dc76bf264022f`.
Successive byte comparisons confirm that the scenery corrections changed none of that
ROM's executable code, boss art, or audio data; it is not a new full campaign
or performance run.

That build resets cached actor poses to frame zero (hidden for every
family) when boss context changes, instead of testing an invalidation flag on
every actor draw. Resetting both visibility and missing-art status prevents
stale results when the empty frame matches. Family/base checks and the full
animation/attribute key remain unchanged; nonempty frames refresh normally.
No additional RAM or sprite assets are introduced.

The all-original PCE boss policy was verified on that preceding ROM. A fresh
`qa_bc_pce_boss_bodies.py` run passes 1,105,920 pixel comparisons for nine
composite bodies and four composite attack poses, including reprise rendering.
The same-ROM shot and serpent reports pass fifteen projectile variants and
twenty final-serpent poses with ordered shading. The refreshed
`.local/bc-composite-review/index.html` shows all 48 comparisons. Original
geometry is preserved; shared Genesis palettes still approximate PCE hues.

On that same preceding ROM, all 21 actual Sound Test selections pass NTSC/PAL
audio, clock, queue, STOP and source-switch checks. A local side-by-side PCE /
Genesis listening page includes approximately ten-second clips for every
selection, with original and level-matched playback. Source recording state
matches 16,596 earlier reference ticks. See `.local/hucard-audio-review` and
`docs/hucard-soundtrack.md`; subjective timbre acceptance remains open.


All 600 state/workload and 599 VDP records match for round-six 4P, improving
865 → 859 video frames; vulnerable play improves 331 → 328 with all 300/299
records matching. Late-blank writes finish by line 258. Twenty 3P/4P openings
save sixteen frames overall (13,117 → 13,101), with small regressions in R2/4P
(+3), R3/4P (+1), R4/3P (+1), R7/4P (+1), and R9/4P (+2). The biggest sample
gains are R10/4P (-8), R6/4P (-6), and R4/4P (-4).

Host cache checks include 96 known/unknown reset collisions, 121 shared-shot
boss transitions, final-serpent slot promotion, 1,200 persistent cache updates,
and 256 synchronized updates. Native boss shots (60 flipped cases), serpent
art (80 cases), and four-player controls/respawn/re-entry pass with no drops or
remaps. Evidence and accepted snapshots: `.local/bc-art-cache-reset/`. The ROM
remains 4 MiB. This is not full-speed or final-release acceptance.

The preceding change bypasses family dispatch for moving pickups on idle ticks
(canonical `86F0`, standard relocation, both timers different from one).
Scroll, the two timer decrements, common movement/contacts and event delivery
retain their order. Direction/appearance transitions and custom resource
layouts retain the full dispatcher. The shortcut reuses the existing common
path and excludes the separate round-eight loop. An initial duplicated version
crossed the sound data's 32 KiB alignment boundary and exceeded 4 MiB; it was
rejected. The retained cartridge fits 4 MiB with `_etext` at `003FF2C4`.

All twenty protected 3P/4P opening samples improve or stay unchanged: total
frames decrease 13,190 → 13,117. Round-four 4P improves 876 → 853 and round-six
4P 891 → 865. Traced round-four timing uses a boundary one frame later
(877 → 854); all 600 state/workload and 599 post-flush VDP records match in
both rounds. Vulnerable round-six improves 334 → 331 with all 300 state/workload
and 299 VDP records matching. The latest late-blank flush ends at line 258.
Host comparisons pass 4,800 three-update boundary cases / 136,800 ordered
events, plus 773 complete PCE round-six loops. Four-player inputs, respawn,
packed shots, Home and re-entry pass with no drops/remaps. This remains a
bounded performance improvement, not full-speed or final-release acceptance.
Evidence and accepted snapshots: `.local/bc-moving-item-idle/`.

The preceding change gives the round-six diver handler (`B4D2`) a direct runtime
path, retaining scroll, firing, child updates, movement/contact and event order.
The shared preparation stays forced-inline in the general dispatcher: allowing
it to be outlined regressed round four. Source branches remain the fallback for
missing RNG, alternate relocation and all other handlers.

The protected round-six 4P replay improves 955 → 891 video frames for 600
updates, with all 600 normalized state/workload records and 599 post-flush VDP
records identical. The latest late-blank flush ends at line 258. Across all
20 protected 3P/4P openings, total frames decrease 13,258 → 13,190. Round-seven
3P regresses 602 → 603 and round-nine 4P 615 → 617; other samples improve or stay
unchanged. The vulnerable round-six replay retains all 300 state/workload and
299 VDP records but regresses 332 → 334 frames, so its strict timing gate fails.
This is a retained net improvement, not full-speed acceptance.

Host differential checks cover 2,304 three-update boundary cases and 65,664
ordered events, matching actors, players, counts and RNG. The source round-six
loop replay covers 773 loops / 8,197 actor updates and 26 later-slot child
updates (141 records after a source round transition are explicitly excluded).
Evidence and accepted source/ROM snapshots: `.local/bc-diver-direct/`.

It contains the nine imported PCE composite bosses, final serpent, boss attack
variants, four-player integration and native HuCard music implementation.
The weapon-art classification now covers all 22 source poses: six retained
Genesis frames, two Genesis recolors and fourteen imported PCE shapes. The
three charged-beam segments retain existing warm shaded Genesis artwork and
direction-specific frames. The middle and round end silhouettes match the
PCE exactly; the tapered segment intentionally retains six differing edge
pixels as a corresponding Genesis design. Native pixel/upload checks cover
5,632 pixels and 176 facing/flip cases. Source flight comparison covers all
three-, four- and five-segment launches in both directions, 266 active slot
updates and 24 retirements. That art review changed no ROM bytes and was verified on `d47742df...`. It closes the outstanding weapon-art classification,
with the four option-death poses' loaded-bank provenance still explicitly
labelled. Evidence: `.local/bc-beam-art-review` and the weapon review page.

A fresh round-six 4P profile (warmup 300, 600 updates) takes 955 video frames.
The general actor loop, actor drawing and common actor update account for
13.00%, 9.20% and 8.39% of measured guest cycles respectively. Overall
performance remains unfinished; this profile identifies the next work area.

The preceding correction replaces the four blue-cross option-death substitutes
(`1E0`–`1E6`) with two exact-silhouette Genesis explosions (`138`, `13C`, color 8)
and two original PCE patterns. All nineteen corrected weapon poses pass 4,864
pixel checks and 152 native flip/facing cases. The four option-death patterns
agree across eleven loaded PCE graphics snapshots; their live destruction
sequence has not been observed in the reference captures. A native branch
fixture checks both facings and four initial flip combinations, displaying
four poses for four ticks each before retirement. Four-player control, respawn,
packed-shot and re-entry checks pass with zero sprite drops/remaps. All existing
903 big keys, 2,903 small keys and both sprite palettes remain unchanged.
Evidence: `.local/bc-option-death-art`; comparison pages label the loaded-bank
provenance. Overall performance remains open; the later beam review above closes correspondence.

The preceding correction maps BC straight shot `1B8` to the matching existing
Genesis single-bar frame `00B` (color 8), replacing the double-bar frame `016`.
Both individual submissions and packed multiplayer triples/fallbacks use the
same generated selection. Genesis pixels and colors are reused unchanged;
its silhouette exactly matches the captured PCE shot. All fifteen corrected
weapon poses pass 3,840 pixel checks and 120 native flip/facing cases. Ordered
submission and four-player control/respawn/re-entry tests pass. All 903 existing
big keys, 2,903 small keys and both palettes remain unchanged. The round-four
4P timing sample retains identical state and workloads for all 600 updates,
but takes 880 video frames versus 875 before (warmup 300). This small regression
is recorded rather than claiming full-speed completion. Evidence:
`.local/bc-straight-art-fix` and the refreshed weapon comparison page.

The preceding correction reuses Genesis impact frames `01C` and `01F` for BC
`1D4` and `1D6`, with orange/yellow shade ramps inferred from captured PCE
colors. The larger impact previously used the smaller `01D` frame. Both
silhouettes match the PCE exactly; Genesis pen regions are retained, including
four distinct levels in the larger impact. All fourteen corrected weapon poses
pass 3,584 pixel checks and 112 native flip/facing cases. Drawing-order checks
cover 2,400 projectile pools, and four-player control, respawn and re-entry
checks pass with zero sprite drops/remaps. All 903 existing big keys, 2,901
small keys and both sprite palettes remain unchanged from `69c6ddfb...`.
Evidence: `.local/bc-impact-recolor`, with an updated weapon comparison page.

The preceding weapon-art correction covers twelve original PCE poses: fireballs,
expanding/fading rings, orbs and the horizontal shot. All 3,072 source pixels,
96 native flip/facing cases and ordered shade ramps pass. Existing 903 big
sprite keys, 2,890 small keys and palette bytes are unchanged from the previous
cartridge. Four-player scene/respawn/re-entry and projectile submission tests
pass. The later beam review above closes the remaining weapon-art classification.
Projectile `1BA` now uses its original PCE horizontal-shot geometry instead of
the unrelated Genesis crescent. Its 256 pixels, eight flip/facing cases and
ordered shades pass native checks; 2,400 projectile pools preserve ordered
submission semantics. Existing sprite keys and palettes are unchanged. Other
weapon-art mismatches identified by the correspondence audit remain open.
It corrects the five-phase player death artwork: one matching Genesis flash
and four imported PCE shapes with ordered shades. Native mapping, 4,096 source
pixels, twenty multiplayer uploads, 4P respawn/re-entry and continue tests pass.
Existing sprite patterns and palettes are unchanged; the ROM remains 4 MiB.
It also corrects the BC late-entry player-art selection from Normal pose `076` to
the visually matching `072`, following the complete campaign checks on
`2c3fed51...`. Native four-player art initialization and the robot-render
fixture pass; the full campaigns described below precede these player-art fixes.
The preceding build adds the measured actor-cache branch-layout improvement documented below
to `e38d7e18...`. That preceding skyline correction changed only 209 bytes from
`548a8303...`: round-one scenery and the cartridge checksum. The skyline passes
native background upload/camera and all-round palette/visibility checks.
Historical audio and performance measurements retain their recorded ROM identities.

Boss artwork was reverified against the preceding `69c6ddfb...` cartridge:
nine composite bodies and four composite attack poses pass 1,105,920 pixel
comparisons, fifteen shot variants pass 3,840 source-pixel and sixty native
flip checks, and twenty serpent poses pass 20,480 source-pixel and eighty
native flip checks. The capture audit matches 2,828 projectile uses across
six attack families with no unknown or mismatched shapes. The comparison
page now requires all three native reports to match the current ROM hash.
All BC bosses and their attacks are original-PCE imports; this supersedes
ordinary-sprite reuse decisions for boss artwork. Ordered shades are retained,
while hues remain approximations within the Genesis palettes.

## Complete campaign checks after all PCE boss imports

On `2c3fed514a9359bc98c2ba4bf7444d1541ef74f4f9c1eb3c7422cc3a19ee6df5`,
3P and 4P BC controller pilots complete all ten rounds, the gallery, 5,760
credit updates and Home return. Both use damage protection, with no forced
boss defeats, seeded health/weapons or injected completion. Final simulation
ticks are 111,107 (3P) and 118,309 (4P), starting at tick 17; elapsed video
frames including ending are 183,036 and 218,211 respectively. Every required
stage/boss/clear/ending music request and audible window passes, with zero
HuCard queue underruns and playback stopped on Home return.

The 3P run additionally records zero software sprite drops, runtime remaps
and unmapped-art counts throughout gameplay/ending. That diagnostic was added
after the 4P process started and is not claimed for its full run. Neither
software counter establishes absence of hardware scanline overflow.

The continuous 4P Normal HuCard run also passes all ten sections and Home
return in 139,449 video frames, with zero queue underruns. It uses protected
players and assisted boss hits; no stage warps or completion events are injected.
These establish assisted progression/audio coverage, not full-speed or
unassisted-combat acceptance. Evidence: `.local/pce-hucard/` directories
`current-boss-campaign-{3,4}p` and `normal-campaign-4p`.

## Retained actor-cache branch layout

The compiler now favors an unchanged cached frame/attribute word in
`bc_actors_draw`; all cache keys, invalidation, positions, art selection and
submission order remain unchanged. A hint covering the entire refresh
condition was rejected: its 20 opening samples cost one extra video frame
overall and round-ten 4P regressed 730 to 739. The narrower hint is retained.

Against `e38d7e18...`, the retained 20-case NTSC 3P/4P opening matrix reduces
total video frames from 13,251 to 13,233 for 12,000 gameplay updates. Individual
changes (round/player count, before → after): R2/4P 615→614; R4/4P 877→873;
R5/4P 641→639; R6/3P 625→621; R6/4P 957→956; R7/4P 661→660;
R8/3P 628→626; R8/4P 814→815; R10/3P 647→643. Other samples are unchanged.
The one-frame R8 opening regression is explicit; this is not full-speed acceptance.

Traced R4/4P improves 878→874 with all 600 state/workload records and 599
post-flush VDP hashes matching. Vulnerable R4/4P remains 304→304 with all 300
state and 299 VDP records matching. The heavy R8/4P sample (12,000 warmup,
1,000 measured updates) improves 1499→1495 with all 1,000 state/workload and
VDP hashes matching. Late flushes finish by scanline 258. Host actor-cache
tests also pass boss-entry/exit, serpent promotion, slot reuse, coordinates,
empty/composite poses and synchronized animations.

Evidence: `.local/bc-art-cache-likely/`, including `baseline-matrix`,
`narrow-matrix`, `narrow-comparison.log`, `narrow-vulnerable-comparison.log`,
`heavy-comparison.log` and `narrow-cache.log`. Full-speed gameplay remains open.

| Requirement | Evidence and remaining work |
| --- | --- |
| Four-player Normal and BC gameplay | Current 4646-ROM protected 3P/4P campaigns pass for Normal, BC and Rush. BC completes without forced boss defeats; Normal/Rush use assisted hit fixtures. Logical controller/menu/combat tests exist. Unassisted full-campaign and physical console/multitap verification are separate and unproven. |
| BC uses the regular engine | Shared session, player storage, scheduler, projectile collection and rendering integration are documented in `bc-shared-engine.md` and `bc-engine-integration-verification.md`. BC-specific source behavior remains in its policy/runtime code. |
| Original PCE bosses and attacks | Nine main bodies, four composite attacks, ordinary projectile variants and all twenty final-serpent poses are imported. Current-ROM native pixel/flip and encounter checks pass. Two protected-head orientations come from the loaded source bank but were not seen live in sampled captures. Palette hues are approximated with ordered Genesis shades. |
| Reviewed ordinary sprites | Review choices and inferred matches are implemented, except that the later all-bosses instruction intentionally supersedes the old serpent recolors. Current selection-isolation check covers 22,000 cases and confirms Normal banks/palettes unchanged. |
| Backgrounds retain Genesis colors and reuse suitable content | Color preservation is implemented. Remaining semantic correspondence issues described in the art notes, are not proven complete; the 22-pose weapon classification is now verified above. |
| HuCard soundtrack | Downloaded HuCard is found and integrated. Current cartridge passes all 21 Sound Test tracks in NTSC/PAL, 4P Normal/BC/Rush launch and save persistence, plus the BC ending/cleanup fixture. Source score, envelope, mapping, queue and historical campaign checks are documented in `hucard-soundtrack.md`. Current 4646-ROM protected full 3P/4P campaigns pass for all three modes with zero underruns. Subjective timbre acceptance remains separate. |
| Sustained stock-clock performance | Fails the BC opening matrices below. Normal-mode full-speed acceptance and complete-campaign performance also remain unproven. |
| Final distributable | Current ROM builds; no release-complete package or publication is claimed. |

## BC performance baseline before idle-family optimization

### Round-four dispatcher experiments after the skyline correction

The `e38d7e18...` cartridge's 4P round-four profile measured 877 video frames
for 600 updates (300-update warmup). Its general actor dispatcher accounts for
12.60% of sampled instruction cycles; drawing accounts for 10.32%, common
actor updates 9.59%, and player updates 8.95%. The profile includes VBlank
waiting, so these percentages are not independent estimates of recoverable
frame time. Evidence: `.local/bc-skyline-cpu-r4.log`.

Two candidates were rejected and restored:

- A constant-round-four clone of the generic loop exceeded the 4 MiB cartridge
  window. The finalizer rejected the build; it was not accepted for runtime.
- Moving the existing idle dome/hover branch ahead of projectile dispatch
  passed 2,848 boundary cases and 81,168 ordered events, plus all 600 normalized
  state/workload records and post-flush VDP hashes in the round-four sample.
  It nevertheless regressed traced timing from 878 to 883 video frames.
  Its uninstrumented 20-case opening matrix also completed, with round-four
  4P at 882 frames. No full-speed claim is supported.

Evidence is under `.local/bc-fourth-loop/`. Neither experiment is retained;
the next optimization must avoid duplicating the large family dispatcher and
must be justified by a measured gain, not reduced source-level branch count.

Pinned stock-clock emulator, protected players, periodic fire, 300 warmup
updates followed by 600 measured updates. These are bounded opening samples,
not whole campaigns. All twenty measurements completed without measurement
errors or cartridge changes. Numbers are video frames required for 600 updates.

| Round | 3 players | 4 players |
| --- | ---: | ---: |
| 1 | 600 | 601 |
| 2 | 601 | 612 |
| 3 | 600 | 616 |
| 4 | 625 | 971 |
| 5 | 601 | 639 |
| 6 | 628 | 963 |
| 7 | 603 | 672 |
| 8 | 628 | 814 |
| 9 | 601 | 619 |
| 10 | 647 | 730 |

Evidence: `.local/bc-current-opening-matrix/results.json`.
The round-four CPU profile attributes 14.63% of sampled cycles to the general
actor loop, 9.34% to actor drawing, and 8.66% to the common actor routine.
31.31% is VBlank waiting, so total elapsed frames must be measured alongside
instruction cost. Profiles are `.local/bc-current-cpu-r4.log` and
`.local/bc-current-cpu-r10.log`.

## Rejected compiler experiments

No candidate below is retained. Each was rebuilt before measurement.

| Candidate | Four-player measured result | Disposition |
| --- | --- | --- |
| Common actor routine `Os` instead of `O2` | Round 8: 814 → 849; round 10: 730 → 819 | Reverted. All 600 normalized state/workload records and post-flush VDP hashes matched before the frame-count gate rejected it. |
| Outline the family dispatcher instead of forced inlining | Rounds 4/6/8/10: 1072/1036/828/731 | Reverted; slower in all four timing fixtures. These runs do not establish full state/video parity. |
| Compile the general actor loop with `O2` | Rounds 4/6/8/10: 972/969/814/730 | Reverted; no benefit and two regressions. |

Evidence: `.local/bc-common-os/`, `.local/bc-step-outline/`,
`.local/bc-loop-o2/`. The accepted ROM and source snapshots are under
`.local/bc-perf-current-baseline/`. Rebuild restoration is checked byte-for-byte
against that ROM. Subsequent optimization should address measured runtime work;
these compiler-only variants do not solve the performance gate.


## Retained idle-family optimization

The common round-four dome and round-four/six hovering actors now bypass the
large family dispatcher only when their work is a timer decrement. Firing,
transition and unsupported/custom resource ticks retain the original dispatcher.
The order remains scroll, family timers, common movement/contact work, then
ordered event delivery. This introduces no new actor state or RAM allocation.

For the 600-update protected four-player traces, round four improved from 971
to 876 video frames and round six from 963 to 956. All 600 normalized simulation
and workload records matched in each comparison, as did all 599 post-flush VDP
records. The latest late-blank flush ended at line 258, before active display.
Independent uninstrumented opening results are tabulated below; their measurement
boundary can differ by one video frame from the traced comparisons.

For 300-update vulnerable four-player traces (100 warmup updates), round four
improved from 313 to 304 frames and round six from 334 to 333, with matching
simulation, workload and video records. These bounded comparisons are not full
campaign proofs.

The host differential test covers 2,448 three-update cases and 69,768 ordered
events: every dome timer byte, hover timer boundaries, full/free actor pools,
missing RNG and alternate resource relocation. It matches the old dispatcher
for actor/player state, counts, RNG and event delivery. Source replay also passes
914 round-four and 773 round-six captured complete actor loops. The latter
capture includes 141 round-seven records after transition; supplying the
round-six code bank for those records fails equally on the old and new build.
`qa_bc_actor_loop.py --source-round 6` now explicitly reports their exclusion.
Its default remains unfiltered and does not conceal that failure.

Current uninstrumented samples (600 updates, 300 warmup):

| Round | 3 players | 4 players |
| --- | ---: | ---: |
| 1 | 600 | 602 |
| 2 | 601 | 614 |
| 3 | 600 | 616 |
| 4 | 619 | 875 |
| 5 | 600 | 641 |
| 6 | 621 | 956 |
| 7 | 603 | 682 |
| 8 | 628 | 814 |
| 9 | 601 | 616 |
| 10 | 647 | 730 |

This is a net timing improvement, not a universal one: the four-player
round-seven opening worsened from 672 to 682 frames, and a few other samples
changed by one or two frames. Full-speed acceptance still fails. Further work
must remove the remaining dispatcher/drawing costs and address these regressions.

Evidence: `.local/bc-idle-families/`, `.local/bc-idle-families-edges.log`,
`.local/bc-idle-families-source4-scoped.log`, and
`.local/bc-idle-families-source6-scoped.log`. A further experiment hoisting the
eligibility checks traded a larger round-four loss for three round-six frames;
it was reverted to the measured version above.


## Round-seven hover follow-up

The idle hover path now also covers round seven's `B03E` handler, under the same
live-state, timer, RNG and source-relocation guards. The earlier round-seven
regression is recovered: the protected 600-update four-player trace improves
from 683 to 661 video frames, with all 600 state/workload records and 599
post-flush VDP records identical. Late flushes finish by line 258. The vulnerable
300-update comparison remains at 304 video frames with identical state/workload
and 299 post-flush VDP records, finishing late flushes by line 257.

The extended differential test passes 2,848 three-update cases with 81,168
ordered events. This includes round-five hover cases as unchanged controls;
round five does not use the shortcut. The round-seven source replay passes
773 loops and 6,325 actor updates; its 141 later-round records are explicitly
excluded because they need the next round's code bank.

An initial wider table-based shortcut improved rounds five/seven but regressed
rounds four/six enough to lose the overall benefit; that candidate was rejected.
The retained narrower variant preserves the previous implementation and adds
only the round-seven handler. Current uninstrumented opening samples:

| Round | 3 players | 4 players |
| --- | ---: | ---: |
| 1 | 600 | 602 |
| 2 | 601 | 615 |
| 3 | 600 | 616 |
| 4 | 619 | 877 |
| 5 | 600 | 641 |
| 6 | 625 | 957 |
| 7 | 602 | 661 |
| 8 | 628 | 814 |
| 9 | 601 | 615 |
| 10 | 647 | 730 |

All twenty measurements completed without measurement errors. Relative to the
previous idle-family build, their combined frame count decreases from 13,266 to
13,251. Some cases still regress slightly: round-six three-player rises from
621 to 625 frames; round-four four-player rises from 875 to 877; other increases
are one frame. These are intermediate tradeoffs, not full-speed acceptance.
The stock-clock performance gate remains open, as do the other acceptance rows.

Evidence: `.local/bc-idle-hover-middle/narrow-r7/`, `vulnerable-baseline/`,
`vulnerable-candidate/`, `final-matrix/`, `narrow-edges.log` and
`narrow-source7.log` in the same directory. `round7-mix` evidence is
`.local/bc-idle-round7-mix.json`.

### Constant round-six loop size experiment (2026-10-08)

Retested full constant-round specialization after metadata packing, on retained
build `281c4fdd48224091c349f210f671af6706ebacd518504eb337bd9ad9afab69f0`.
It still exceeds the 4 MiB cartridge limit: `_etext` is 4,223,888 bytes and the
padded output is 4,325,376 bytes. The new loop spans approximately 24,046 bytes
because the forced-inline actor dispatcher is duplicated. No gameplay timing
claim is made for this invalid cartridge. Source was restored and the rebuilt
ROM verified byte-identical to the retained build. Evidence:
`.local/bc-sixth-constant/decision.json`. A smaller fallback-sharing experiment
may retain the newer rain/pickup/hover/diver fast paths without this duplication;
it remains untested, and the earlier compact specialization was rejected.

### Shared-fallback round-six loop experiment (2026-10-08)

Sharing the uncommon dispatcher reduces the additional loop from roughly
24 KiB to 2,370 bytes. O3 still crosses the sound-bank alignment threshold;
Os and O2 fit 4 MiB. Both fit candidates match 600 state/workload records,
599 post-flush VDP records, and independent full-RAM replay. Source comparisons
cover 8,600 PCE actor loops / 217,160 actor updates across route and retirement
captures. These captures do not cover player deaths.

The twenty HuCard sample total improves 16,596 to 16,190 (Os) or 16,159 (O2),
but the targeted R6/4P 6,000-update run regresses 11,091 to 11,197 or 11,125
frames. The short timing gate also fails (1,140 to 1,147 / 1,145), after state
and video equality checks pass. Both candidates are rejected as round-six
optimizations; unrelated round gains warrant separate compiler-layout analysis.
Evidence and archived candidates: `.local/bc-sixth-shared/`. No full-speed or
release-completion claim follows from these bounded experiments.

### Current parallax follow-up (`f97004d1` restored)

A wrapping-counter far-map setup candidate preserved 5,001 Normal simulation,
sprite and full VDP-memory snapshots, but regressed a protected 4P section-5
sample from 5,005 to 5,006 video frames. The candidate is rejected and the exact
current cartridge/source restored. New reusable `--vdp-trace` support covers
background maps, pixels, scroll tables and palettes at input boundaries.
The BC material/collision audit now enumerates all ten rounds; it identifies
candidates for layer separation but does not establish safe parallax. See the
October 9 audit in `docs/parallax.md`. No additional parallax level is claimed.

### Opening-city paired-shade study rejected (October 9)

A paired source-color search found that Normal zone0 palettes0/22 can recover
3,055 pixels of RGB3 word2696 together. The existing two-bank allocation fits,
preserves other Normal pixels and existing Standard/Vivid distinctions, and a
bounded 4P opening replay remains 1200updates/1200frames with all reported
fields equal except ROM hash. This candidate is **not retained**.

Two integration issues prevent treating that local fit as an accepted repair:
- Re-running the greedy Vivid guard changes lookup2696 from3208 to2696 even
  though the old lookup satisfies the new constraints. An explicit preserved
  entry was tested and restored the full prior lookup, but remains archived
  with the rejected candidate, not enabled in production.
- R1 authors stone shades using Normal donor pen15; city recovery reuses that
  pen. Direct reuse therefore corrupts R1 despite the Normal-only fixture
  passing. Capturing pre-repair donor data preserves R1's inputs, but loses
  Normal DMA-block sharing and grows private BC graphics by8KiB. Raw payload
  becomes4,199,924 bytes:5,620 beyond the4MiB window. The cartridge-size gate
  correctly rejects this build.

Source/generator candidates, original donor hashes, comparisons, failed checks,
oversize payload and restore log are under `.local/normal-city-shades/`.
The paired search `.local/normal-shade-pairs/` also completes zones3,5,7,15
without a safe pair under its constraints; remaining zones are explicitly
deferred. Future recovery needs storage savings or less donor duplication;
this study does not waive BC visual isolation, cartridge size, or remaining
shading requirements.


### City shade repair retained after storage recovery — October 9

The earlier city candidate's size rejection is resolved by the unused Earth
bank removal above. Current repair 7344a15f leaves27,148 raw payload bytes.
BC R1 donor tiles/attributes/palette are captured before Normal material
repairs; the resulting BC graphics use8KiB more private storage but resolve
to exactly the same684cells across all ten rounds. All source collision banks
remain unchanged. Only zone0_tiles and zone0_pal differ among159 linked binary
blobs;157others, including all frontend resources and the Vivid lookup, match.

Four-player Normal opening:1200updates/1200frames; every report field except
ROM hash matches. BC R1 and R8 four-player HuCard:600updates after300warmup,
638/1005frames respectively; all canonical simulation states, workloads and
mean scene timings match. Full make reproduces the exact retained ROM. These
are scoped controls, not new full-campaign or full-speed acceptance.

Evidence: `.local/city-shades-fit/accepted.json`, `verification.json`,
`blob-scope.json`, `normal-comparison.json`, `bc-comparison.json`, and
`index.html` with native before/after and source-art comparisons.


### Contact spatial-grid opportunity audit — October 9

A read-only native contact-entry observer tested eight horizontal bins and a
4×4 grid after the existing shot-index AABB gate. Four-player HuCard fixtures
covered R2 and R8 (300 warmup + 600 measured updates) and R4 charged fire
(3,000 warmup + 600 measured updates). Respectively 40, 71 and 156 indexed
candidates passed the existing bounds; neither grid rejected any of them.
R4 examined 737 indexed records, so this includes multi-shot indices.

The R8 observer/control pair matches every pre-existing result field, including
state, workload and timing. This is a bounded opportunity study, not proof
that all campaign weapons lack spatial separation. It provides no basis for
adding per-update grid construction/query costs. No runtime changes were made.
The earlier actual row-mask experiment also regressed both long routes; its
evidence remains `.local/bc-shot-row-mask/rejected.json`. Current audit results
and explicit scope: `.local/bc-contact-grid-audit/summary.json`. All jobs are
terminal; cartridge remains 0a981d93 and performance acceptance remains open.

The R7 review page now puts the six aligned source/Standard comparisons first
and fits both images to the available width (stacked on narrow screens). Its
generator rechecks all six background pairs at zero differing pixels. This
review-layout correction does not change the ROM or certify runtime sprites,
palette transitions or timing.


### Rejected paired player-pose cache — October 9

A candidate grouped the cached body and weapon frame IDs into a contiguous
four-byte entry and copied the adjacent output fields together. All30,720
pose/countdown cases passed, including disabled cache, mismatched keys,
rebinding, every weapon ID and odd/wrapped source addresses. All600 canonical
state/workload records matched in each four-player HuCard fixture.

Mean full-scene cost nevertheless rose: R2 664,649.3→672,611.555 core ticks,
R8 886,474.19→894,598.02. Video frames changed735→743 and1005→1004; the R8
frame reduction alone does not establish a speedup. Candidate rejected. The
original source is restored, and the relinked cartridge exactly matches the
packaged da75dc6a SHA256. All jobs are terminal. Evidence:
`.local/bc-player-pose-pair/rejected.json`, `comparison.json`, host/profile logs
and `restore.log`. No experimental cache change is included in the test ZIP.


### Round7 sprite scanline pressure — October 9

The current da75dc6a four-player HuCard R7 fixture exposes a hardware-limit
coverage gap hidden by zero software submission drops. After300 warmup and
9,000 measured updates,8,999 post-upload SAT observations contain1,747 samples
with selected sprite-width demand above320 pixels on at least one line;12
samples exceed20 Y-overlapping sprite entries. Peaks are21 entries and576
pixels. Totals are42,370 width-over-limit line observations and60 entry-over
observations. This measures bounding-box demand, not visibly missing pixels:
transparent pixels, offscreen-X sprites and layer occlusion affect interpretation.
Masking and raster-time changes are outside this observer's scope.

The parser boundary model matches1,792 direct pinned-core scanlines across
eight synthetic cases; offscreen-X and width-boundary cases also pass. ABI
fields are16-bit as declared in the core header. Independent replay without
the observer matches exact final RAM/tick/frame state;17,623 video frames.
Adding the worst-SAT/VRAM snapshot leaves every result field unchanged.
At tick3481/camera1604,1536, no sprite has removable fully transparent edge
columns; that simple trimming approach cannot reduce the576-pixel peak.

Evidence: `.local/bc-scanline-pressure/summary.json`, `r7-capture/result.json`,
`r7-capture/sprite-scanline/worst-vram.bin`, `padding-opportunity.json`; native
boundary check: `tools/qa_sprite_scanline_audit.py`. Rules are grounded in
Genesis Plus GX `core/vdp_render.c` and `core/vdp_ctrl.h`. All jobs are terminal;
ROM/test ZIP unchanged. Sprite visibility under hardware limits is an explicit
remaining visual issue, not a claim that every over-budget sample loses visible
art or that it explains the user's specific R7 screenshot.


### Native confirmation and strip-packing opportunity — October 9

The R7 SAT/VRAM snapshot at tick3481 has40 sprites and8,281 opaque pixels
in its unlimited sprite plane. Applying the scanline entry/width limits omits
643 opaque sprite-plane pixels. The independently decoded result matches the
pinned native parser, pattern-cache builder and sprite renderer at every pixel
on all224 scanlines against a blank background. This excludes final background
and window occlusion; it is not a full-screen missing-pixel count.

Only slot18 is fully hidden/offscreen in the ideal image. Removing it preserves
that image but recovers just29 pixels under hardware limits, leaving614 omitted.
An offline horizontal-strip experiment removes transparent8-pixel edge bands
and merges vertically adjacent bands with identical width. Ideal pixels remain
identical, list size rises40→63 (within80), and omitted pixels fall643→284.
The native comparison validates the original/occlusion cases; the strip model
is currently offline only and still needs native repacking and runtime testing.

Ten repeated entries match linked spr_big block838/key0x7d30: the BC recolored
spike turret (source frame0x36b2, Normal code0x530). Restricting strips to that
asset raises entries40→50 and reduces omitted pixels643→442 in this snapshot.
This gives a concrete asset to investigate without changing art. Extra pattern
storage, DMA, submission cost and full-route/global SAT pressure are unmeasured;
no renderer change has been retained. Current ROM/test ZIP remains da75dc6a.

Evidence: `.local/bc-scanline-pressure/visibility.json`, `visibility.png`,
`native-visibility.json`, `strip-opportunity.json`, `strip-spike-opportunity.json`
and `repeated-spike-source.json`. All jobs are terminal.


### Round 7 sprite strip trial — rejected October 9

The v3 linked-SAT spike turret trial preserves all 3,999 shared ideal sprite
planes and all 4,000 simulation states on the matched four-player HuCard route.
It reduces sprite-width over-limit line observations from 40,131 to 27,735,
but leaves the entry-limit violations unchanged and increases mean scene cost
from 1,032,595 to 1,077,023 core ticks (4.3%). The route takes 7,719 video frames
instead of 7,662. Round 8 control states also match, but frames rise 1,005 to
1,012. No software sprite drops or remaps occur. These checks do not imply
absence of hardware sprite loss.

The runtime and generated-asset changes are rejected and restored to the
retained da75 source. The read-only sprite audit tools remain. Sprite crowding
is unresolved; the background comparisons do not certify the sprite layer.
Evidence: `.local/bc-spike-strips/rejected.json`, `r7-v3/result.json`,
`r8-v3/result.json`, and archived `candidate-v3.c` / `candidate-v3.bin`.


### Direct spike strip trial — rejected October 9

Emitting the packed cap and base at the actor draw call avoids the post-pass
scan and the duplicate full-square pattern upload. Matched R7 states and all
3,999 shared ideal sprite planes remain identical; width-over-limit line
observations fall 40,131 to 27,735. R7 mean scene cost still rises 1.95%, with
7,699 frames versus 7,662. R8 states match but scene cost rises 0.63%, with
1,008 frames versus 1,005. Neither bounded route reports software drops.

This approach is not retained: its extra entries can consume capacity needed
by later submissions. A check at the time of splitting cannot reserve unknown
later actor submissions. Future work must allocate extras after original
submissions or provide a verified collapse fallback without the earlier costly
full-list scan. The candidate and comparisons are archived in
`.local/bc-spike-direct/`; the retained da75 source is restored and rebuilt.


### Recorded sprite-strip candidate — October 9

Candidate b03fb25e records eligible BC idle spike turret SAT indices during
submission, then splits only as many as fit after all original submissions.
It leaves originals intact when the list is full or pattern cache/upload space
is unavailable. Linked appended bases preserve original painter order. The
previous full-list scans and moves are gone; original artwork stays unchanged.

53,120 host C checks of the production post-pass cover capacity, all flips,
links, ending links, unavailable upload budget/cache and count bounds. The
4,000-update four-player R7 replay has identical simulation states and all
3,999 shared ideal sprite planes. Width-over-limit line observations fall
40,131 to 27,735; entry-over-limit observations stay at 60. No software drops
or remaps occur. Mean scene cost increases 2.3%, and frames rise 7,662 to
7,722. The 600-update R8 control preserves states but rises 1,005 to 1,012
frames. This is a measured visual/cost tradeoff, not full-speed certification.

Full protected three- and four-player BC HuCard campaigns are running before
retention. The test ZIP is unchanged. Evidence and live process handles are
in `.local/bc-spike-recorded/candidate.json` and `running.json`.


The candidate artwork suite now passes (Normal material/source shades,
frontend Earth/burn, reviewed BC recolors, six R7 native/source comparisons,
and Standard/Vivid intro checks). At the same R7 tick3481/camera1604,1536,
its 50-entry sprite snapshot preserves 8,281 ideal opaque pixels and loses
442 under the hardware limits, compared with 643 in the original 40-entry
snapshot. The pinned native parser/pattern-cache/sprite renderer exactly
matches this candidate model on all 224 lines. These are sprite-plane counts
before background/window occlusion, not a complete-screen comparison.
Evidence: `.local/bc-spike-recorded/art-checks.json`, `visibility.json`, and
`native-visibility.json`. Full campaigns remain in progress.


### Recorded strip renderer retained and packaged

The b03fb25e candidate passes all six current-ROM progression checks. BC3P
finishes 106,007 simulation ticks in 162,333 video frames; BC4P finishes 121,006
in 212,402. Both complete all ten rounds, all 5,760 credit updates and return
Home, with no forced boss defeats, audio underruns, software sprite drops,
remaps or unmapped art. Normal3P/4P complete ten sections in 115,673/134,098
video frames; Boss Rush completes twelve encounters and last-player exit.
Normal/Rush use assisted hits. BC completion tick counts differ from the
baseline, so aggregate campaign durations are not isolated performance evidence.
The earlier matched tick-by-tick profile remains the bounded CPU-cost evidence.

All current artwork checks pass. Full make reproduces the tested hash exactly.
Expanded host splicing tests cover 159,360 head/tail/interleaved, flip, capacity
and fallback cases. The 4P R7 stack monitor reports zero overlaps and a minimum
12,968-byte gap; a separate uninstrumented replay matches final RAM/ticks/frames.
The verified test ZIP includes current-ROM campaign and artwork evidence.
All jobs are terminal. Remaining sprite crowding, heavy multiplayer slowdown
and the broader unfinished acceptance work remain open.


### Surfacer crop candidate — October 9

The exact key0x250 pose has empty outer eight-pixel rows. The BC renderer now
trials one 32x16 entry at y+8, using half the upload bytes in one existing big
cache slot. All four source flip variants reconstruct the exact original pens;
other poses and Normal mode keep their source art and renderer paths. Cache or
upload failure falls back to the original renderer. No extra SAT entries are
needed. In the 4,000-update four-player R7 comparison with retained b03fb25e,
all simulation states, workload counts and 4,000 ideal sprite planes match.
Entry-over-limit line observations drop60 to13; width-over-limit observations
drop27,735 to25,081. No software drops/remaps occur. Mean scene cost rises
0.52%, while elapsed video frames drop7,722 to7,695; these different metrics
must not be conflated. R8 preserves600 states/workloads, with1,012 to1,013
frames and0.56% higher mean scene cost. Full validation is pending.
Evidence: `.local/bc-short-surfacer/asset-check.json`, `comparison.json`.

The af20e09c candidate artwork suite passes, including reviewed BC recolors,
Normal/front-end shades, R7 native/source comparisons and both intro color
modes. `tools/qa_bc_surfacer_strip.py` separately checks linked pens and all
four flips. Full campaign processes remain live; handles and current evidence
are recorded in `.local/bc-short-surfacer/running.json`. The retained b03fb25e
package is unchanged until full validation completes.


### Surfacer crop retained and packaged

The af20e09c full rebuild is byte-identical to the ROM used for all six passing
campaigns. BC3P finishes111,337 ticks/173,360 frames; BC4P finishes116,004
ticks/201,586 frames. Both complete all ten rounds,5,760 credit updates and
Home return, without forced boss defeats, HuCard underruns, software sprite
drops/remaps or unmapped art. Normal3P/4P and Rush3P/4P match every b03fb25e
reported field except the ROM hash, including115,673/134,098 Normal frames.
Normal/Rush use assisted hits. BC pilot completion ticks differ, so campaign
frame totals are not equal-state performance comparisons.

The package includes campaign, artwork and sprite evidence, including exact
source pens in all four flips and the matched4,000-update R7 sprite trace.
The pinned native sprite renderer confirms391 missing opaque sprite-plane
pixels at the saved crowded snapshot, down from442 in b03fb25e and643 before
the two fixes. Remaining crowding and broader performance/visual acceptance
are open. All jobs are terminal; this is a test package, not a final release.


### Pod crop and cached draw-kind candidate — October 9

Candidate5b678b7d crops the empty last tile row from reviewed pod key0x7ed6.
Its single32x24 entry preserves every source pen in all four flips, with the
y-origin shifted8 pixels only for vertical flips. Crop selection now occurs
when the actor pose changes, rather than repeatedly checking three keys during
every draw. The cache keeps its20-byte layout. Host actor-cache checks pass,
as do159,360 retained spike SAT checks and both crop pen checks.

V2/V3 hit the next32 KiB sound alignment boundary and exceeded4 MiB. The
candidate shares cold crop fallback code and word-aligns bc_sprite_pal: its
only runtime consumer is pal_load, which copies colors into RAM before DMA.
Direct-DMA graphics retain512-byte alignment. The complete build fits4 MiB.

Relative to retained af20e09c, the4,000-update R7 replay preserves every
simulation state, workload count and ideal sprite plane. Entry-over-limit
line observations fall13→9; width-over-limit observations25,081→24,313.
No software drops/remaps occur. Mean scene cost rises0.18%, with7,695→7,713
video frames. The600-update R8 control preserves states/workloads and stays
at1,013 frames; mean scene cost improves slightly. Full campaigns are pending.
Evidence: `.local/bc-short-pod/comparison-v4.json`, `asset-v4.json`,
`surfacer-v4.json`, `actor-cache.log` and `running.json`.

The candidate artwork suite passes. Its saved worst-demand snapshot moves to
tick3487 (50 entries), where the pinned native sprite renderer matches the
independent model exactly and384 opaque sprite-plane pixels are missing.
This is a different snapshot from af20e09c's tick3481/391 pixels, so those
counts must not be treated as a direct before/after comparison. The earlier
same-scene66-pixel opportunity is an offline projection at tick3481. Full
campaigns remain running; live handles are in `running.json`.


### Pod crop and draw-kind cache retained

All six current-ROM progression checks pass for 5b678b7d. BC3P completes
108,911 ticks in169,537 frames; BC4P completes121,608 ticks in214,993 frames.
Both complete all ten rounds,5,760 credit updates and Home return with no
forced boss defeats, HuCard underruns, software sprite drops/remaps or unmapped
art. Normal/Rush match af20e09c in every reported field except ROM hash.
BC completion ticks differ, so aggregate campaign durations are not equal-state
performance comparisons. Full make reproduces the tested4 MiB ROM exactly;
the word-aligned BC sprite palette remains byte-identical to its source file.
The verified package includes campaign, artwork and sprite evidence. All jobs
are terminal. This remains a test build; crowding and broader acceptance work
remain open.


### Smaller-cache compatibility check — October 9

Current retained5b678b7d passes the real Home/menu, per-controller pause,
exit and re-entry checks for1P and2P. Their13-slot big-sprite cache differs
from the19 slots used by3P/4P, so the new crop paths were also exercised in
protected4,000-update R7 routes. Both have zero software sprite drops/remaps
and zero entry-over-limit lines. The1P route has88 width-over-limit line
observations;2P has none. This is bounding-box demand, not visible lost pixels.

1P takes4,922 video frames (mean scene639,176 core ticks);2P takes5,268
(mean686,281). Thus even these bounded routes are not full speed. Different
player counts produce different gameplay workloads and cannot be treated as
an isolated per-player cost experiment. ROM and package remain unchanged.
Evidence: `.local/5b-small-cache/summary.json`, per-player profiles and menu
results. All jobs are terminal. `qa_bc_menu.py --output` now permits separate
versioned evidence directories without overwriting prior menu evidence.


### Ordinary 32x32 draw outlining rejected — October 9

Separating spr_bc_bits32 into a noinline O2 function preserved all matched
simulation states, workload counts and ideal sprite planes, but was slower
in every measured route. R7 1P increases4,922→4,997 frames and mean scene
cost639,176→648,260 core ticks; R7 4P increases7,713→7,769 and1,063,648→
1,079,354; R8 4P increases1,013→1,030 and895,544→924,597. No software
sprite drops/remaps occur in the R7 routes. The trial is rejected and the
retained source restored. Evidence: `.local/bc-key32-outline/rejected.json`.
The earlier small-cache checks remain valid for retained5b678b7d.

## Burst turret idle candidate — bounded verification, not packaged

Working ROM `8aba301b622c81f9419bb933edd79e1cdf7757ecf4227f13bcff89eff1ef33fb`
retains the cropped sprites and adds the Round 7 burst-turret countdown to the
existing idle-family check. Firing ticks, custom relocation layouts and absent
RNG contexts retain the full dispatcher. Scroll and common collision/animation
work still execute in source order. The source capture comparison passes 7,099
loops, 135,533 actor updates and 521 child updates without unsupported loops.

The unused 5,810-byte sprite-key inventory is no longer linked; its development
binary is still generated and asserted equivalent to populated lookup entries.
The shading audit enumerates the linked index instead. All 135 other data.s
blobs match the last packaged cartridge byte-for-byte. ROM size remains 4 MiB:
sound-bank alignment absorbs the reclaimed space. This is code headroom, not a
claim of reduced final cartridge size or new shading improvements.

Against 5b678b7d, matched 4P HuCard tests after 300 warmup updates:

| Round | Updates | Video frames before/after | Mean scene core ticks before/after |
| --- | ---: | ---: | ---: |
| 4 | 600 | 1116 / 1115 | 958801.585 / 955813.355 |
| 6 | 600 | 1128 / 1130 | 964633.437 / 967647.357 |
| 7 | 4000 | 7713 / 7682 | 1063647.711 / 1029180.166 |
| 8 | 600 | 1013 / 1013 | 895543.845 / 895543.845 |

Every sampled simulation state and workload matches. All 4,000 R7 ideal sprite
planes match; software drop/remap counters remain zero. R7 scene cost improves
3.24%, with a 0.31% R6 cost regression. Video-frame improvement is much smaller
than scene CPU improvement; this does not resolve full-speed performance or
hardware sprite crowding. An earlier separate check was rejected for larger
R4/R6 regressions. The current variant is a candidate pending full campaigns and
final acceptance, not a replacement test ZIP.

Evidence: `.local/bc-burst-idle/comparison-v2.json`, `source-loop-v2.json`,
`linked-data.json`, `shading-v2/audit.json`; immutable build under
`.local/bc-burst-idle/candidate/`. All recorded jobs terminated successfully.

### Burst-turret candidate retained after complete regression checks

All six protected 3P/4P campaigns passed on 8aba301b. BC3 completed
110,911 gameplay updates in 171,569 recorded frames; BC4 completed 135,510
updates in 241,434 frames. Both finished all ten rounds, 5,760 credit updates
and Home return without forced boss defeats, unmapped art, software sprite
drops/remaps or HuCard underruns. The controller pilot takes different paths
as timing changes; these full-campaign totals are not equal-state performance
comparisons. Normal/Rush also pass all sections/encounters and player-exit
checks with assisted hit paths and zero underruns.

The full `make` regenerated assets and reproduced the campaign ROM byte-for-byte.
The retained test ZIP is `.local/candidates/Side-Arms-MD-expansion-8aba301b-test.zip`;
it includes campaign, art, sprite and matched-state performance evidence.
See `.local/bc-burst-idle/accepted.json`, `summary.json`, `reproducibility.json`,
and `package.json`. All jobs are terminal. This supersedes the pending status
of the bounded-verification section above; remaining performance and hardware
limits are not waived.

## Rejected Round 3 burst-turret shortcut

Candidate `0f55ae284f047ab6c59d986f75e46363d11a4e8a2a71e8dcd28e8a986021ba0c`
added the idle burst countdown to the specialized third-round actor loop.
Source comparisons passed 868 turret loops and 6,006 full-route loops; the
turret capture includes 1,495 idle updates and 50 firing ticks. The 4P route
preserved 4,000 states/workloads and 3,999 ideal sprite-plane samples, with mean
scene ticks 1,023,500.814 to 1,018,535.994 and frames 7,280 to 7,270.

The 1P control regressed: 1,200 identical state/workload updates took
1,317 rather than 1,311 frames, with mean scene ticks 471,314.334 to
477,826.563 (+1.38%). R7/R8 controls passed with essentially unchanged timing.
The small 4P gain does not justify the solo regression; this candidate is
rejected. Evidence: `.local/bc-third-burst-idle/rejected.json`,
`comparison.json`, `controls.json`, `source-coverage.json`, `source-loop.json`
and `source-route.json`. The previously packaged 8aba301b remains retained.

Restoration passed byte-for-byte for both source and ROM; see
`.local/bc-third-burst-idle/restored.json`. All jobs are terminal.

## Route-wide transparent-border sprite inventory

The retained 8aba301b worst snapshot has no further nonempty sprites with
wholly transparent outer tile rows/columns. A new optional read-only
`--sprite-crop-inventory` profile mode therefore inventories the full route.
It normalizes palette/flips and records source pens, occurrence counts and
scanline-pressure overlap; pressure does not mean visible missing pixels.
The new four-flip/palette normalization check and existing eight SAT/parser
boundary cases pass. All 4,000 R7 state/workload/timing rows, 7,682 video frames
and 4,000 ideal sprite-plane hashes exactly match the unextended observer.

Thirteen distinct crop candidates were found and matched to linked pattern
bytes. The leading three are launcher frames 0x28/0x30/0x20 of family0x3688:
keys0x7a64/0x7a66 retain their lower32x24, and key0x7a56 its lower32x16.
They appear2,016/1,008/2,057 times, including828/539/459 pressure-overlapping
occurrences. Removing these transparent rows would preserve all source pens
and palette shades, but runtime implementation, flip offsets, cache fallback,
DMA alignment and actual timing/rendering gains remain to be verified.
Other candidates include pod0x7ec6 and ordinary key0x242; see the inventory
before generalizing. No game source, resource data or ROM was changed.

Evidence: `.local/bc-crop-inventory/summary.json`, `observer-check.json`,
`matched.json`, `auditor-checks.log`, and `r7/result.json`. All jobs terminal.

## Launcher crop candidates — rejected for added CPU cost

Three original launcher patterns were cropped only through transparent top
rows: key0x7a56 to32x16 and keys0x7a64/0x7a66 to32x24. Original pens and all
four flip placements match exactly, with separately512-byte-aligned DMA sources.
The crops each retain one SAT entry and one existing cache slot; original32x32
submission remains the fallback. Production-function host tests pass37,536
cache-hit/miss, insufficient-budget, capacity, flip and clipping cases; actor
cache tests preserve source keys, positions and simulation. No artwork color
or source palette is altered.

Three implementations were measured against retained8aba301b:

| Variant | R7 mean scene ticks | R7 frames | R8 mean ticks | Solo R7 mean ticks |
| --- | ---: | ---: | ---: | ---: |
| Retained | 1029180.166 | 7682 | 895543.845 | 460210.444 |
| V1: separate cropped submission | 1039922.550 | 7714 | 901059.483 | 468650.245 |
| V2: cached bucket, inline hit/cold upload | 1042308.594 | 7729 | 905193.777 | 467390.432 |
| V3: outlined hit, reordered draw dispatch | 1042659.944 | 7722 | 904162.233 | 468776.473 |

R7 uses4,000 matched updates, R8 uses600, solo uses1,200. Every simulation state
and non-SAT workload matches. All4,000 shared R7 ideal sprite planes and1,199
solo planes match. Each variant reduces R7 width-over-limit line observations
24,313→22,192 (8.72%); entry-over-limit lines remain9. Software drop/remap
counters remain zero. The sampled before/after tick1201 isolated sprite plane
has zero missing pixels in both, so it does not establish visible pixel recovery.
The useful reduction in bounding-box pressure is not enough to accept added
CPU cost while the performance gate remains open. None of these variants is
retained. Source snapshots, ROMs, generated-test scripts and reports are under
`.local/bc-launcher-crops/`, including `rejected.json`, `comparison-v1.json`,
`comparison-v2.json`, `comparison-v3.json`, `linked-crops*.json`, and the
`cache-checks*.log` and `actor-cache*.log` reports. Avoid repeating these same
three dispatch/upload variants without a new mechanism or acceptance basis.

Launcher restoration passed: original source bytes and full-make ROM match
retained8aba301b exactly. All jobs terminal; see
`.local/bc-launcher-crops/restored.json`.

## Rejected zero-axis scroll guards

Candidate0dd2a14d added `if(dx)`/`if(dy)` guards to camera-relative enemy
scroll subtraction. Captured source comparisons pass90,139 vertical and
135,533 horizontal updates, including24-bit wrapping in the aligned32-bit
storage. Matched native state/workload/ideal-plane traces pass. R7 mean scene
cost improved0.085%, R8 improved0.142%, and the solo R7 control improved0.291%.
However, matched600-update controls regress R3 by0.492%, R4 by1.021% and R6
by0.904%; R4/R6 frame counts rise1115→1123 and1130→1144. The final-round
control improves1053→1045 frames. The mixed outcome does not justify retaining
this global hot-path change; it is rejected. Evidence:
`.local/bc-zero-scroll/comparison.json`, `controls.json`, `source-scroll.json`,
`source-horizontal.json` and `rejected.json`.

The source-scroll QA's wrap statistic was separately corrected to use the
current aligned position representation (`dx*256`/`dy*256` in unsigned32-bit
coordinates). Its original full-field equality assertions remain unchanged.
This is a development-tool reporting correction, not a gameplay change.

Zero-scroll restoration passed byte-for-byte for source and cartridge; see
`.local/bc-zero-scroll/restored.json`. All jobs terminal.

## Successful curve-birth indexing candidate

Fresh retained-ROM profiles identify tick4015 as a worst R7 scene:
1,990,093 core ticks, including338,310 attributed to `actor_contacts`. The
most expensive instruction sequence scans all28 shot slots20 times during five
curve births, before the normal actor pass installs compact shot indices.
Both focused observations (ticks4015/3500) match independent uninstrumented
replay; evidence is under `.local/bc-current-hotspots/`. Earlier all-event
indexing was rejected and existing eight-segment birth indexing remains intact.

Candidate37af9e5f indexes only successfully allocated Round 7 curve births.
Pre-existing indices are reused; inactive/null members are not indexed, and
every temporary pointer is restored. Failed allocations and unrelated events
retain the original path. The240 differential cases cover all five lanes,
1–4P, ordinary/piercing shots, vulnerable/protected/dead/null players, failed
allocation, occupied prefixes and pre-existing indices. All gameplay/event
bytes match the uncached reference, including120 ordered contacts and100
consumed shots. Captured PCE stage-event comparisons pass61 events.

The matched tick4015 scene falls1,990,093→1,847,797 ticks (-7.15%). Over4,000
R7 updates, every state/workload and ideal sprite plane matches; elapsed frames
fall7682→7675, while mean scene cost rises0.061%. P99 falls1,462,831.58→
1,436,944.81 and the route maximum falls1,990,093→1,955,674. This is a tail-cost
improvement, not an average CPU speedup. R8 frames1013→1009; solo stays1246.
Controls preserve all states/workloads but are mixed in elapsed frames:
R4 1115→1118, R6 1130→1138, R10 stays1053, vulnerable R7 436→441. Their
mean scene costs are slightly lower or unchanged; these frame regressions
remain explicit rather than being described as universal gains.

Evidence: `.local/bc-curve-birth-index/comparison.json`, `controls.json`,
`spike-comparison.json`, `differential.log`, `source-stage.json`. Full campaigns remain running; see `running.json`. Current-ROM art and
sprite checks pass, including linked pod/surfacer flips, 159,360 SAT cases
and production actor-cache comparisons. The 4P R7 stack fixture observes
129,798,226 instruction boundaries over 4,500 updates, with zero overlaps
and a 12,942-byte minimum gap to peer allocations. Independent uninstrumented
replay matches the complete RAM digest, 8,550 frames and 4,500 ticks. This
fixture uses Arcade music and proves only this route; see `stack-comparison.json`.
This is an unpackaged candidate, not final acceptance.

Curve-birth candidate follow-up: Normal and Boss Rush 3P/4P campaign wrappers
completed successfully. All four reports match retained8aba301b apart from
the ROM hash, including zero HuCard underruns. These use assisted hit paths.
Evidence: `.local/bc-curve-birth-index/normal-rush-comparison.json`. Both BC
controller-pilot campaigns remain live; do not rebuild the cartridge yet.

Curve-birth candidate retained as a test build after all six campaign gates
and full-make reproduction passed. BC3 completed 107,113 updates/166,106
frames; BC4 completed 114,408 updates/199,598 frames. Different controller
trajectories mean these campaign totals are not equal-state speed benchmarks.
Both have zero HuCard underruns, software drops/remaps or unmapped art, and
completed credits/Home return. Hardware sprite crowding and sustained speed
remain unresolved; this package is not final-release acceptance.

## Rejected dedicated Round 7 actor loop

A compile-time Round 7 specialization of the existing actor loop exceeded
cartridge capacity: linked payload end 4,197,684 bytes, with the padded image
4,325,376 bytes. The existing 4 MiB finalizer correctly rejected it. No timing
or gameplay gain is claimed. The original source and retained37af9e5f ROM
were restored byte-for-byte. Evidence: `.local/bc-r7-loop-specialization/`.
Do not repeat this full-loop clone without first resolving its code size.

The retained37af9e5f sustained hotspot profile covers R7 updates3200–3799
with4P/HuCard: 600 updates in1,203 video frames, mean scene cost1,169,743.59
core ticks,581 scenes over the896,040-tick frame budget. Independent plain
replay matches complete RAM/frame state. General actor dispatch, actor drawing
and common actor updates lead recurring cost. Per-instruction attribution and
linked disassembly are in `.local/bc-sustained-hotspots/`; all jobs terminal.
This confirms ongoing performance work, not a new speed improvement.

## Rejected per-pass idle-handler selection

Candidate8c44da34 selected hover/dome/burst handler IDs once per actor pass
and shared their unchanged common-update continuation. PCE source comparison
passes7,099 loops/135,533 actor updates/521 children. Native comparisons retain
all states/workloads and4,000 long-R7 plus1,199 solo ideal sprite planes.
The sustained R7 sample improves1,203→1,199frames and0.40%mean CPU, but the
full4,000-update route only saves10frames (7,675→7,665) while mean cost rises
0.022%. Solo mean cost rises0.77% despite1,246→1,240frames. R4 mean rises0.90%
and frames1,118→1,126; R6 mean rises0.87% with frames unchanged1,138; R8 is
unchanged. Rejected as a mixed global change. Original source and37af9e5f ROM
restored exactly. All jobs terminal; `.local/bc-idle-handler-hoist/` preserves
source, candidate ROM, comparisons, rejection and restoration evidence.

## Packed HuCard pan-table candidate

Candidate7d0a19e9 replaces two source-pan curve lookups, comparison and stereo
bit construction with one512-byte ROM table. The louder-side level and hard
pan bits remain identical. Host packet tests pass524,288frames/3,145,728voices
across all65,536period inputs and both regions, including changed envelopes
and poisoned alternate destinations. All21actual-cartridge Sound Test tracks
pass in NTSC and PAL. The preceding max-nibble/one-curve variant was rejected
for a slight crowded-R7 regression; it is archived separately.

Native candidate comparisons preserve all gameplay states/workloads. R7long
4,000updates takes7,675→7,620frames, mean scene ticks1,029,803.86→1,026,314.20,
and3,999shared ideal sprite planes match. Solo1,200updates takes1,246→1,230frames,
mean460,211.02→459,110.67. R4/R6/R8 mean CPU costs decrease0.38%/0.22%/0.41%;
frames1,118→1,102 /1,138→1,139 /1,009→1,002. The R6frame increase remains explicit.
Full six-campaign and artwork regressions are running. Do not promote/package
before their current-ROM results and full-make reproducibility pass.
Evidence: `.local/hucard-pan-table/` (`comparison.json`, `controls.json`,
`fm-frames.log`, `audio-ntsc/result.json`, `audio-pal/result.json`, `running.json`).
Retained37af9e5f package remains available; full-speed goal is still incomplete.

Pan-table candidate acceptance is complete as a local test build: all six
campaigns and current-ROM gates passed, and the full rebuild reproduced the
ROM exactly. Its archive is verified. This supersedes pending statements in
the candidate section above; performance/hardware release gates remain open.

## Deferred HuCard envelope address candidate

Candidate ed1e4e61 preserves source-selected instrument updates but resolves
its envelope address only when the envelope or note actually consumes it.
Silent envelope phase 4 keeps its original no-op behavior. Captured source
checks match all 166,377 ticks, including complete channel/voice state and
three aliases. No source timing, note, volume or pan change is intended.

The sustained R7 sample takes 1,197→1,195 frames; solo takes 1,230→1,227.
The 4,000-update R7 route retains 7,620 frames but reduces mean scene cost
1,026,314.20→1,022,464.08 ticks. All states/workloads and 3,999 shared ideal
sprite planes match. R4/R6/R8 controls take 1,102→1,096 / 1,139→1,128 /
1,002→994 frames, with lower mean scene costs in all three. These are bounded
improvements, not full-speed acceptance. Full campaign, art and NTSC/PAL audio
regressions are running; retained 7d0a19e9 remains the packaged build.
Evidence: `.local/hucard-lazy-envelope/` and its `running.json`.

Deferred-envelope acceptance is complete as a local test build: all six
campaigns, current-ROM art/sprite/audio checks and exact full-make reproduction
passed. The verified package is recorded in `package.json`. This supersedes
pending candidate statements above; full expansion release acceptance remains open.

## Rejected HuCard native byte-word decoder

Candidate 66e5c11e used a three-instruction, odd-address-safe 68000 word reader
in the sequencer. The native test passes all 65,536 values at both alignments,
including unsigned extension and source/sentinel preservation. Gameplay states
and workloads match, but the crowded 600-update R7 sample rises 1,195→1,197
frames and mean scene cost 1,166,381.98→1,170,083.73 ticks. Solo remains 1,227
frames, with a small CPU reduction. Rejected for the crowded-scene regression.
Original source and retained ed1e4e61 ROM restored byte-for-byte; all jobs are
terminal. Source, probe, ROM, comparison and restoration evidence remain in
`.local/hucard-word-read/`. Do not repeat this global decoder substitution.

## Native-endian HuCard channel candidate

Candidate ddf2af86 pads each internal channel from 23 to 24 bytes, aligning
stream and period words, and stores those internal words in big-endian order.
Original score operands remain little-endian and byte decoded. The internal
score state grows by six bytes. Source QA normalizes the two internal word
pairs and checks the padding separately; all 166,377 captured ticks and three
aliases pass. Native reads/writes pass all 65,536 values at three aligned offsets,
including unsigned extension and sentinel preservation. The preceding aligned
little-endian variant is archived but not retained.

Against retained ed1e4e61, the long R7 route takes 7,620→7,566 frames and mean
scene cost falls 1,022,464.08→1,018,855.86 ticks. All 4,000 gameplay states,
workloads and ideal sprite planes match. R4/R6/R8 frame counts improve
1,096→1,088 / 1,128→1,125 / 994→973; their mean CPU costs also decrease.
Solo improves 1,227→1,221 frames. The shorter sustained R7 sample takes one
extra frame (1,195→1,196) despite lower CPU cost; this remains explicit.
Full six-campaign, NTSC/PAL audio, art and paired stack regressions are running.
Evidence and live handles: `.local/hucard-native-channel/running.json`.
Do not promote or package until those checks and full-make reproduction pass.

Native-endian channel storage is retained after all current-ROM regression
and exact-rebuild gates passed. The local test ZIP is verified. This supersedes
pending candidate statements above; full release acceptance remains open.

## Grouped HuCard voice-cache candidate

Candidate 527bfe25 groups each voice's pitch keys, timbre keys and aligned
packet into one 20-byte record, retaining the 120-byte cache payload. Host
mathematical checks pass 524,288 packets/3,145,728 voices. Native comparison
against the preceding renderer passes 16,384 packets with aligned/odd and
poisoned repeat destinations. There is no synthesis or score-rule change.

Against retained ddf2af86, the long R7 route improves 7,566→7,512 frames and
mean scene cost 1,018,855.86→1,008,545.95 ticks. All 4,000 states/workloads
and ideal sprite planes match. R4/R6/R8 frame counts improve 1,088→1,075 /
1,125→1,102 / 973→965, with roughly 1% lower mean scene costs. Solo improves
1,221→1,208 frames. Full campaign, audio, art, sprite and paired stack checks
are running under `.local/hucard-voice-cache-layout/regress.py` (session39304).
The runner waits for every regression before rebuilding and verifying exact
ROM reproduction, then packages only on success. `running.json` records each
job and phase. Candidate acceptance is still pending; full speed remains open.

## Pending active-channel word check (376abb8b)

The working candidate replaces the HuCard active-channel byte OR with the
existing aligned internal-word accessor. Source state matches all 166,377
captured ticks and three aliases; native helper checks cover all 65,536 values
at three aligned offsets. R7 long improves 7,512→7,492 frames and mean scene
cost 1,008,545.951→1,005,947.600, with all 4,000 gameplay/workload rows and
shared ideal sprite planes identical. R4 improves 1,075→1,070; R8 965→962.
Results are mixed: R6 takes 1,106 rather than 1,102 frames despite lower mean
CPU cost; solo takes 1,209 rather than 1,208 with essentially unchanged mean.

This candidate is NOT retained or final. The full regression runner is live
in exec session 31333, writing `.local/hucard-active-word/running.json` and
`regress.log`. It will rebuild and test-package only after all checks pass;
its completion does not automatically accept the candidate. Do not mutate the
shipping ROM/source while it runs. Latest accepted build remains 527bfe25.

### Current Normal sprite shade inventory (read-only)

The 376abb8b audit inspects 1,279 original background metatiles, 2,795 original
16x16 sprite keys and 800 original 32x32 composites, verifying examined generated
blobs against the ROM. Palette merges remain in 788/2,536/773 entries respectively.
These counts include duplicated and potentially unused pattern combinations;
they are diagnostics, not counts of defective on-screen objects. The worst
ranked robot-pose comparison shows warm source highlights becoming pale green
or gray, so BC source-matching checks do not close all Normal shading work.

A read-only spare-pen study proves pen15 is unused by examined Normal small
sprite patterns. Each Normal palette has a spare slot. Exact source gray
(6,6,6) would recover 3,650 indexed pixels in bank0; these are pattern-bank
counts, not gameplay pixel counts. BC already uses its corresponding spare
pens for middle shades, so shared-pattern compatibility/isolation is mandatory
before integrating any Normal repair. No generated assets or runtime source
were changed by this study. Evidence:
`.local/hucard-active-word/shading-inventory/{audit.json,spare-pen-study.json,sprite-loss-review.png}`.

The active-word regression remains live in session31333; it must finish before
new ROM changes. Candidate acceptance remains pending and 527bfe25 remains
the retained/test-packaged cartridge.

### Offline Normal spare-shade prototype (after 376abb8b)

`.local/normal-sprite-spare-shades/` holds an unintegrated data-only prototype.
An exhaustive compiled actor/boss mapper scan covers every 16-bit frame and
16 palette values for supported families; imported keys and all player-page
palette variants are additionally protected. Modified blocks must contain only
known Normal keys, all aliases must request the same pixel edits, and no
protected lookup may change. No pattern storage is added.

The initial gray highlight choice collapsed to white through the existing
Vivid LUT and was superseded. The current choices (1,2,0) and (2,0,0) restore
6,014 stored pixels across296 blocks to exact source shades. The existing
Vivid LUT preserves their distinction and componentwise shade ordering;
transparency and other pixels remain unchanged. These are stored-pattern
counts, not on-screen asset counts or a complete shade repair.

Integration remains required: gallery_colors currently derives its palette
from Normal sprite_pal, so its original zero pen15 entries must be preserved
in both runtime gallery setup and build-time constraints. The old generic
Normal-unchanged assertion must be replaced with independently verified,
source-exact repair exceptions; it must not simply be disabled. Full-make
reproduction, native rendering/controls and campaign checks remain outstanding.
The shipping/generated assets and retained 376abb8b ROM are unchanged.
Evidence: study.json, protected.json, study.py and review.png in that directory.

### Integrated spare-shade candidate — pending 0b1d54e7

The Normal sprite repair now runs in build_assets via normal_sprite_shades.py
and an explicit hash-checked source recipe. It restores6,014 stored pixels in
296 pattern blocks (300 alias keys), adds no pattern bytes, and preserves all
existing Standard/Vivid distinctions. Independent QA decodes original source
pixels, checks every alias and unchanged block, scans all16-bit actor/boss
frames with16 palettes, and protects imported/player keys. The old generic
Normal-unchanged recolor check now requires an explicit repair baseline and
runs this independent verifier before admitting hash-checked exceptions.

BC gallery setup preserves its original zero spare pens. The boss importer
also explicitly preserves its original palette input; otherwise it would
silently fit to Normal's new shades. The Vivid LUT is unchanged. The linked
ROM remains4MiB: only sprite_pal/spr_bank/spr_big change among135 graphics
blobs, with132 unchanged, including all BC background/boss artwork.

Native Normal 4P opening:1,200updates/1,200frames; section 9:1,200updates/1,221frames.
Each matches its archived baseline's1,201 state samples and rendering workloads.
The section 9 test intentionally returns nonzero for both builds because both
miss full speed; equivalence is proven, full speed is not. BC R7's4,000-update
comparison preserves all gameplay/workload rows,4,000 ideal sprite planes,
7,492video frames and mean scene cost1,005,947.6.

Full regression is running in exec session 42710, writing
`.local/normal-sprite-spare-shades/running.json` and regress.log. Both BC
campaigns additionally verify more than5,000 unfaded gallery CRAM samples
against the archived palette. This check is pending, not yet passed. The
runner rebuilds/packages only after all checks pass, and does not accept the
candidate automatically. Do not mutate ROM/build sources while it runs.
Latest retained/test-packaged build remains376abb8b. No final-release claim.

The first art job failed because the historical background verifier still
required all sprite bytes to be unchanged. It now accepts an explicit sprite
repair baseline only after independent source-shade verification AND matching
those pre-repair bytes to its historical ROM. A separate art retry in session
79308 completed successfully: all seven art jobs passed; evidence is
art-retry-complete.json and art-checks.json. No ROM changes were needed.

Original runner42710 still owns the campaign/audio/stack jobs. Do not restart
it: its thread pool will finish remaining jobs before reporting the original
art-job exception. After confirming it is terminal and every other job passed,
run `.local/normal-sprite-spare-shades/finish.py` once to consolidate the verified
art retry, perform the full rebuild and test-package. That script requires the
original phase=failed plus current-ROM retry evidence. It does not accept the
candidate automatically. Inspect gallery palette sample counts before acceptance.

The first gallery observer had a test bug: it read the ROM Vivid LUT through
Runner.read, which accesses RAM. The game defaults to Vivid; therefore the
initial3P/4P gallery checks failed. These are archived as bc-3p-testbug and
bc-4p-testbug; the ROM is unchanged. Original runner42710 is now terminal failed.
The extra first Vivid diagnostic18276 was deliberately stopped after identifying
the same bug, and archived as bc-vivid-4p-testbug. It was not restarted for a timeout.

The corrected explicit-Vivid4P diagnostic is live in session54434, writing
bc-vivid-4p; corrected3P is live in session92950, writing bc-3p. Keep both running
and preserve the ROM. Once4P succeeds, copy its evidence directory/log to bc-4p
for packaging, retaining the Vivid-named originals and recording the provenance.
finish.py now requires successful current-ROM3P/4P Vivid results, Home return
and >5,000 matching gallery CRAM samples each, before admitting these retries.
All other original regression jobs and the independent art retry passed.
Earlier references to Standard campaign runs were incorrect: these fixtures
use the game's default Vivid. The separate source-shade verifier covers both
Standard and Vivid distinctions; the native gallery observer now explicitly
records its selected mode. This supersedes the earlier running statements.

### Larger fast sprite lookup rejected (acab1827)

FAST_SLOTS256 doubles the two fast tables, consuming2,048 additional RAM bytes
without adding VRAM slots. The native address probe passes196,608 cases across
all65,536 keys and three origins. R7 long preserves4,000 gameplay/workload rows
and all3,999 shared ideal sprite planes; reference tick300 is not sampled in
the candidate. Frames improve7,492→7,485 and mean scene CPU falls only0.083%.

Controls against the immediate pre-shading376abb8b predecessor (not exact-build
controls) are mixed: solo1,209→1,211; R4 1,070→1,073; R6 1,106→1,103;
R8 962→954, with identical compared states/workloads. The small/mixed benefit
does not justify permanently consuming2KiB RAM. No whole-campaign or stack
acceptance was attempted. The experiment is rejected; src/sprites.c and the
retained0b1d54e7 ROM are restored byte-for-byte. All jobs are terminal.
Evidence: `.local/sprite-fast-256/rejected.json`, comparison.json and native-hash.log.

## Pending Normal zone10 visual repair

Offline review in `.local/normal-zone10-review/comparison.png` confirms lost
pink organic highlight steps in stage5. The first fixed-star Lloyd refit is
rejected: aggregate RGB error improves slightly but two metatiles merge more
source shades and none improve their merge count. Exact pink restoration with
all other current colors preserved requires35 opaque colors against30 available;
this negative base-zone result precedes additional Home constraints. No runtime
or generated artwork changed. `status.json` records the next investigation;
this is an unresolved visual issue, not accepted artwork.

### Zone10 bounded offline fit

Keeping tile palette assignments fixed permits a partial shade improvement.
The bounded512 trial improves24 of104 base metatiles and worsens none by the
merge-count diagnostic. Independent per-source-pair checks find63 recovered
base distinctions and49 Home distinctions with zero newly merged pairs in
both Standard and Vivid. Exact pixels rise56190→57226, while mean squared
RGB3 error rises0.20221→0.22012. This is a documented color-accuracy tradeoff.
The rendered comparison still lacks some source highlights; it is not a full
shading repair or integrated change. Far-layer colors, brightness ordering and
native checks remain pending. All optimizer/check jobs are terminal. Evidence:
`.local/normal-zone10-review/status.json` and `bounded-comparison.png`.

### Zone10 ordered fit integration pending

The bounded512 fit introduced34 luminance-order reversals across Standard and
Vivid and was rejected. The revised ordered512 fit independently recovers44
base and30 Home source-pair distinctions, introduces no merges or tested
luminance inversions in either mode, and preserves all1024 far-layer pixels
with unchanged512-byte pattern storage and map bytes. Mean channel error
changes0.20221→0.20730; exact base pixels56190→57005. Visual recovery remains
partial. Production integration is now building in session96973; it is not
yet verified or retained. Baseline/source snapshots and pending gates are in
`.local/normal-zone10-fit`. Latest retained package remains c7e8fe90.

### Integrated zone10 candidate —25177d55, not retained

The first build changed one global Vivid LUT entry and was rejected. Explicit
preservation of source word1646 passes the generator's current ramp constraints
and restores the entire previous LUT. Whole-ROM verification now permits only
zone10_pal/zone10_tiles/zone10h_tiles and checksum:1286 bytes differ, symbol
addresses, runtime, audio, other art and the4MiB size remain unchanged.
Independent decoded candidate pixels match the intended fit, preserve opacity
and all attr words, and recover44 base/30 Home source-pair distinctions with
no new source merges or tested luminance inversions in Standard/Vivid.

The protected4P stage5 route matches6001 states,6000 scheduler/workload rows
and6005 frames. Native zone10 samples verify5715 resident pattern blocks and
10464 CRAM words across327 settled samples. Scope excludes fades, nametable
placement and unsampled frames. Pixel checks and native jobs are terminal.
Full-make reproduction followed by all12 regression jobs is live in session
21243. Evidence lives in `.local/normal-zone10-fit`; do not rebuild/change the
ROM while those readers run. Latest retained/test package remains c7e8fe90.

The zone10 full rebuild reproduced25177d55 exactly. Reusable independent
verification now lives in tools/qa_normal_zone10_shading.py; it verifies
source-fit pixels, opacity, source-pair distinctions, componentwise-source
luminance ordering, far-layer referenced colors and whole-ROM change scope.
It passes for the candidate. The baseline screenshot rerun matches all6001
states and6000 scheduler rows; matched final captures differ at1358 pixels.
Visible improvement remains subtle/partial. Review page:
`.local/normal-zone10-fit/index.html`. Regression session21243 remains live;
Rush, stack, audio, recolor and intro jobs passed, while Normal/BC campaigns
are still running. No test package or retention yet.

### Large-sprite fallback outlining rejected

`.local/bc-big-fallback-outline` tests moving only the cold four16x16 fallback
out of cached_key32, leaving ordinary lookup/emit inline. All compared states
and workloads match; R7's4000 ideal sprite planes also match. CPU gains are
small (typically0.1–0.5%), with R7 4P7290→7284 frames but R6 4P1104→1107,
solo R7 1204→1205 and R10 4P1024→1026. R10 mean CPU worsens0.118%. Normal
s2/s8 improve slightly. None of the measured routes executes the outlined
fallback branch, so this does not certify that branch's behavior.
The small mixed result is rejected. All jobs are terminal; src/sprites.c and
the retained25177d55 cartridge are restored byte-for-byte after explicit
source recompilation. No package changes.

## Read-only player sprite split study — October 9

The retained ROM remains25177d55, byte-identical. No renderer change is retained.
The study in `.local/bc-sprite-margin-study/` models splitting eligible BC
32×32 player bodies into a24×32 rectangle and one narrow edge strip using
existing contiguous VRAM patterns, with no new pattern data. Independent
geometry checks cover112 pose/flip compositions and preserve every pen.

Round7 covers4000 post-upload samples. All state/workload/timing profile fields
match the exact retained baseline. Of1391 pressured samples,300 improve and
none worsen in the offline hardware-limited sprite-plane model. Summed differing
pixels fall238652→234953 (1.55%); over-limit entry/width line counts stay9/24313.
This is not final-screen visibility or native performance acceptance.

Round4/6/8 controls each cover999 observed post-upload samples from1000 scene
calls. Modeled differences are46676→46676,116→112,9582→8900 respectively,
with0/1/54 improved samples and no worsened samples. Round4 introduces one
additional entry-over-limit line despite no modeled pixel regression; other
control threshold counts stay unchanged. No masking samples were skipped.

The candidate needs native implementation/timing and broader visibility checks
before retention. Extra SAT entries have a cost, and the modeled benefit is
modest. All study jobs are terminal. Evidence: `geometry.json`,
`demand-replay.json`, `route-summary.json`, `controls.json`, and `status.json`
in that study directory. The full expansion remains incomplete.

## Native player sprite split rejected — October 9

The offline candidate above was implemented and tested as2a6333f7, then rejected.
The implementation uses only existing player VRAM patterns, defers extra pieces
until all ordinary and spike submissions finish, and splices spare SAT entries
without changing submission priority. It retains the ordinary fallback if no
single32×32 body or spare entry is available.

All five paired native routes preserve every sampled simulation hash and ideal
sprite-plane hash. However, scene CPU increases3.934% in R7 4P,4.354% in R4,
3.784% in R6,4.236% in R8, and2.340% in solo R7. Display-frame counts rise
7290→7515,1068→1109,1104→1144,964→998; solo remains1204. Instruction attribution
locates the main added cost in robot strip emission and per-body bookkeeping,
with additional sound interrupt work from the longer runs. This cost outweighs
the previously measured modest visibility benefit.

All prototype jobs are terminal. All three modified source/header files were
restored exactly and rebuilt, reproducing retained ROM25177d55 byte-for-byte.
Evidence: `.local/bc-player-split-native/comparison.json`, `cost-attribution.json`,
and `rejected.json`. No part of this split prototype is retained. The crowded
multiplayer performance and visibility requirements remain open.

## Existing sprite palettes for background shades — isolated prototype

The retained working ROM stays91725541. An isolated generated-asset prototype
at `.local/normal-sprite-palette-background/workspace/` builds as2b9d5d6f.
It uses existing Normal sprite palette banks2/3 for selected background8×8
patterns. No native renderer changes, extra palettes, or pattern bytes are
introduced by these proposed files; production generation is not integrated.

Independent decoding verifies110 base+7 Home exact source RGB3 pixel repairs,
with every other displayed color, opacity and non-palette attribute preserved.
The initial177-pixel version introduced6 Standard/Vivid brightness-order
violations on3 blue-water metatiles; its60 affected pixels were excluded, and
v2 has none. Both versions preserve BC's684 generated mapped cells; v2 also
passes all10 linked BC cell pen/attribute, palette, collision-code and source
alignment comparisons. These exclude untested runtime integration assumptions.

A stage2 Normal 4P probe matches4001 states/4000 timing rows and confirms the
sprite CRAM lifetime at249 settled samples, but does not encounter its repaired
metatiles. A stage5 Normal 4P probe matches6001 states/6000 timing rows and6005
display frames. It verifies327 settled samples of all64 background+sprite CRAM
words and565 uploaded plane-B borrowed-palette entries on repaired metatiles59
and66. The latter count includes offscreen ring entries, not a visible-pixel
count. Other repaired zones and Home variants remain unverified natively.

All prototype jobs are terminal. Evidence: `prototype.json`,
`independent-check.json`, `bc-equivalence.json`, `linked-bc.json`,
`native-check.json`, `native-check-s4.json`, and `status.json` in that directory.
Next steps are reproducible production integration, four-bank-aware auditing,
coverage of remaining repaired zones and full acceptance. No part of this
prototype is in the retained91725541 package.

## Cavern prototype palette caching — isolated, not packaged

Prototype `78eb16f6` caches transformed palette colors per DMA buffer and
invalidates them when source colors, color mode or fade changes. The completed
instruction profile had attributed 1.266 billion route cycles to cave_prepare.
For 10,000 protected four-player updates, caching reduces video frames from
11,127 to 10,334 (retained build: 10,108). All 10,001 semantic states match;
mean scheduler work falls from 698,109 to 578,254 ticks, versus baseline 533,392.
Worst work is still 598 lines versus baseline 543, so this is not a full-speed
result and the prototype remains isolated.

Standard and Vivid each match 183,375 opaque high-priority background pixels
across four stationary route views, excluding HUD and sprite rectangles.
The instruction audit observes 8,935 atomic, DMA-guard-respecting palette writes
inside the core HBlank window, with zero source-color deadline errors or slot
sequence errors across 960 measured frames. PAL/general HUD and moving pixel
checks must be repeated for this hash. Evidence: `.local/cavern-v14-raster/cache-result.json`.
The retained v1.4 expansion ROM is unchanged.

## Cavern interrupt save optimization — isolated 35b3a0b0

Save D2–D5 only when processing a palette event, and return immediately for
a guarded flush. Protected moving 4P route now takes 10,246 video frames for
10,000 updates (baseline 10,108; prior cached prototype 10,334), preserving
all 10,001 state hashes. Worst work remains 598 lines; not a full-speed claim.
Simple HUD, forced alternate HUD and PAL instruction audits pass palette
sequence, source-color deadline, HBlank FIFO and DMA/interrupt atomicity checks.
Alternate HUD audit verifies 30,025 register writes. Initial alternate/PAL
commands omitted fixture environment settings; those logs are not evidence for
those modes. Configured reruns supply the reported evidence.

The moving framebuffer oracle requires better synchronization: using current
CPU camera gives 832,558 mismatches; prior camera reduces this to 285 in one
view among 3,046,494 checked pixels. Pre-frame VRAM increases mismatches to
40,616, so neither arbitrary frame-boundary snapshot establishes render-time
VRAM state. Do not claim moving pixel fidelity yet. A render-time snapshot is
the next verification step. All jobs are terminal. Retained ROM unchanged.
Evidence: `.local/cavern-v14-raster/short-save-result.json`.

## Moving cavern render-state observation

A read-only wrapper of Genesis Plus GX render_bg snapshots video memory and
scroll registers immediately before line 16. The wrapper preserves all 10,001
compared states and the 10,246-frame route duration. Across 65 sampled moving
views, the retained build matches all 3,046,494 checked high-priority opaque
background pixels. Prototype 35b3a0b0 differs at 285 pixels: one flat purple
scanline at screen y=16, camera (1568,1983). This is a prototype regression,
not cleared by the corrected capture alignment. HUD and sprite rectangles
remain excluded; this is not whole-frame coverage.

A ten-color/two-span DMA experiment worsened the result to 5,188 differences
and 10,263 route frames. Reverted it and reproduced 35b3a0b0 exactly. The next
step is DMA/display-state observation at the affected scanline. No prototype
was promoted; all jobs are terminal. Evidence: `.local/cavern-v14-raster/moving-render-result.json`.

## Repeated video frame diagnosis

Instruction tracing around the bad view shows frame 6581 has no DMA flush
or palette event and all observed cavern H-ints return under flush_guard.
The previous frame's lower palette remains live. All 285 differing pixels
match the lower-palette color exactly, including Vivid conversion. This
supports a repeated-video-frame palette lifetime defect, rather than the
initial hypothesis of excessive DMA length. Reducing transfer length was
therefore the wrong remedy and remains reverted.

The prototype must restore and repeat its palette split on every displayed
frame independently of main-loop completion, while excluding actual queued
DMA setup/transfer and preserving v1.4 HUD safety. Palette/frame commit timing
also needs review when the prepared camera has not yet reached VRAM. No runtime
fix is claimed yet. Evidence: `.local/cavern-v14-raster/repeat-frame-diagnosis.json`
and `trace-dma-palette/trace.json`. All trace jobs are terminal.

## Repeated-frame palette fix — isolated f4a1eaf0

Cavern frames now commit after the queued picture flush, restore their top
palette in VBlank on repeated video frames, and repeat raster events independently
of simulation completion. A separate cave_dma_busy flag covers flushQueue's
complete command setup and transfer; the original flush_guard still blocks HUD
writes until main completes its flush. Commit and CPU palette restoration after
flush run with interrupts masked. None of this is in the retained build yet.

The moving observer matches all 3,046,494 checked high-priority opaque background
pixels in 65 sampled vertical-route views. All 10,001 gameplay states match the
retained build. 10,000 updates take 10,324 video frames versus 10,108 retained;
worst work is 599 lines, so overhead and slowdown remain. NTSC, PAL and alternate
HUD audits have zero event-sequence, color-use deadline, HBlank FIFO or actual
DMA-exclusion errors. The palette observer now derives displayed Y from hardware
VSRAM and the committed frame's start, avoiding the prepared-camera mismatch
which had reported nine transition errors. Earlier CPU-camera reports are not
used to establish display deadlines.

Broader moving coverage, VBlank CPU restoration/commit stress, non-cavern cost
and generator integration remain. All jobs terminal. Evidence:
`.local/cavern-v14-raster/repeat-frame-result.json`.

## Inactive cavern path and CPU restore audit — isolated ffc16588

Skip frame preparation when the cavern is absent, avoid interrupt masking when
no cavern frame is pending, and avoid reconfiguring the HUD for static cavern
views. The sampled moving pixel check remains clean (3,046,494 pixels) and all
10,001 states match; cavern route takes 10,326 video frames. A separate zone-0
2,000-update comparison has matching states and 2,000 video frames in both builds;
mean work rises 527,137 to 529,374 ticks (about 0.42%, not zero overhead).

The native CPU restore/DMA descriptor audit fails its VBlank-only assertion:
a palette restore ends at frame 4014, visible scanline 1. Earlier sampled pixel
and raster-event checks do not rule this out. A survey retaining the DMA and
CRAM correctness assertions while collecting all visible restores is running
(session 22786 when recorded). Read `.local/cavern-v14-raster/restore-dma-survey/`
and its log before restarting. Production integration remains blocked on fixing
this technical issue, not on user approval. The retained ROM is unchanged.

The survey completed; session 22786 is terminal. Its report contains 9 visible before/after restore samples and verifies 22292 DMA descriptor pairs. Use this result rather than the preceding running-state note.

## Redundant restore removal — isolated 3918fbb9

Restore at VBlank only for a frame with a raster split. After DMA, compare the
new starting colors with the colors already supplied by VBlank or a queued
palette load; restore only when they differ. A deferred restore remains tracked
when VInt encounters an active DMA queue. This eliminates the observed visible
CPU palette writes without suppressing the palette update on repeated frames.

The full protected 10,000-update cavern audit verifies 1,163 complete CPU
restores, all starting and ending in scanlines 226–257, with exact resulting
CRAM values and 22,292 intact atomic DMA descriptor pairs. No observed restore
runs during actual DMA. All 10,001 gameplay states match. Route duration is
10,313 video frames versus retained 10,108; worst work is 592 lines.

Expanded moving views cover horizontal and vertical route sections: 115 views,
4,242,603 checked pixels, zero mismatches. Standard colors separately match
183,375 stationary-view pixels. Opaque high-priority Plane B only, excluding HUD
and sprite rectangles; low-priority/far layers still need independent checks.
PAL and alternate-HUD raster audits have zero deadline, sequence or HBlank FIFO
errors. Production generation, lifecycle transitions and broader regressions
remain. All jobs terminal; retained v1.4 build unchanged.
Evidence: `.local/cavern-v14-raster/elision-result.json`.

## Reproducible cavern conversion and both background planes — isolated 083b48ac

Added tools/build_cavern_palette.py and its fixed palette-allocation recipe in
the isolated workspace. It regenerates visibility from extracted level legs,
reads original arcade pixels, repacks Normal/Home tiles, and fits the far texture
to palette slots stable across both regions. All eight outputs exactly reproduce
the reviewed prototype; no exploratory scripts or cached cavern images are used.
The step runs after BC donor generation and before Vivid generation. A generated
header supplies the runtime palette and changed-slot list. BC art binaries remain
identical to the retained build. The existing organic-stage generator needs its
reference image inputs; those were copied into the isolated workspace after the
first build attempts reported them missing.

Two complete make all runs succeed and reproduce SHA-256
083b48ac269853be74a0fa67350e0c3291e0c9a63c394c50b647622e7bd60cc9.
The five ROM bytes differing from 3918fbb9 are confined to the regenerated Vivid
table and checksum. Two RGB3 colors (0848 and 084A) now retain Standard values
in Vivid to preserve shade order. All 1,560 generated ordered-pair constraints
pass. All ten BC rounds pass native CRAM comparisons in Standard and Vivid.

The moving framebuffer oracle now composites both hardware background planes,
including low-priority tiles, transparent areas and backdrop. Across 115 route
views it checks 6,059,326 pixels with zero mismatches, including 1,046,451 visible
Plane-A pixels. HUD rows and sprite rectangles remain excluded; the observer
uses actual hardware scroll and a render-time VRAM snapshot. Lifecycle and final
mode regressions remain before production promotion. All jobs terminal; retained
v1.4 build unchanged. Evidence: `.local/cavern-v14-raster/generator-result.json`.

## Current-hash safety and next performance target

All 22 safety/audio jobs pass on retained 083b48ac and are terminal. The test
ZIP has been refreshed with current-hash boot/Z80/HUD/audio evidence; ROM bytes
are unchanged. 20,329,102 Z80 instructions stay below 2000 (max 0B13). HUD
monitoring observes 9,360 guarded flushes, 358 blocked hints and 34,931 safe
window writes. Both 21-track audio runs and all 12 launch cases pass.

A new bounded R7 4P HuCard profile (300 warmup, 1,200 measured updates) takes
1,890 video frames. VDP wait accounts for 30.11% of attributed cycles; sound_vint
is 11.06%, player stepping 8.42%, the R7 actor loop 7.76%, actor drawing 7.67%,
and common actor processing 7.16%. No new speed claim or optimization yet.
The audio producer is the largest measured non-wait function and is the next
optimization candidate; all score, packet and sound fidelity must be retained.
Evidence: `.local/cavern-v14-raster/performance/profile.json`.

## HuCard counter batching experiment — rejected

Retained ROM remains 083b48ac. The isolated counter-batching candidate 9242a403
combines only score-clock passes that cannot parse commands or advance envelopes.
It passes 441,000 host full-state comparisons, 42,000 native 68000 comparisons,
166,377 original PCE capture ticks, and all 21 Sound Test tracks in NTSC/PAL
(420 packet checks per standard, zero underruns). No subjective timbre claim.

The R7 instrumented opening improves 1,890 to 1,875 frames for 1,200 updates.
However the uninstrumented ten-round 4P HuCard matrix (300 warmup, 600 measured
updates per round) improves only 8,591 to 8,580 frames; R3/R4/R5 regress by
1/10/1 frames respectively. This is insufficient and inconsistent improvement
to retain the additional sequencer complexity. Candidate source and ROM are
archived, production is unchanged, and isolated source was restored. All jobs
are terminal. Evidence: `.local/hucard-counter-batch/decision.json` and adjacent
reports. Next performance target is active actor/collision and draw work in
crowded BC 4P routes, not further speculative score-clock batching.

## Round 7 dispatcher experiments — rejected

Instruction attribution on retained 083b48ac shows stack traffic in the large
seventh_actor_loop hot path. Moving its full uncommon event dispatcher into a
separate function increased text from 4,174,692 to 4,207,224 bytes, exceeding the
4 MiB cartridge window. The finalizer correctly rejects it. An accidentally
continued diagnostic profile of that oversized image also worsened the opening
from 1,890 to 1,934 frames; that profile is not valid cartridge acceptance.
No oversized image was promoted or packaged.

A separate O2 compilation of only seventh_actor_loop fits the ROM window but
raises the same 1,200-update HuCard opening from 1,890 to 1,891 frames and
increases attributed loop cycles. Neither experiment is retained. Production
source and ROM remain 083b48ac; isolated source is restored. Evidence in
`.local/bc-r7-dispatch-outline/decision.json` and
`.local/bc-r7-loop-o2/decision.json`. These results rule out simple dispatcher
extraction and O2 selection as fixes for the crowded 4P deficit; they do not
prove remaining performance, rendering or whole-release gates complete.

## Current-ROM Round 7 visual audit and crop evidence

Retained 083b48ac passes the source-pixel R7 material assertions: 61 cells,
62,464 geometry pixels, 30,679 imported opaque PCE pixels, and the seven/five/three
warm/green/blue shade ladders in Standard and Vivid. The test uses the current
ROM as its baseline argument; its unchanged-other-assets counters are therefore
self-comparisons and are not independent regression evidence. Source-pixel and
shade assertions are independent. Report: `.local/bc-current-r7-materials`.

A fresh protected 4P HuCard 4,000-update R7 trace takes 7,324 video frames.
Hardware demand exceeds width on 24,313 sampled lines and entry count on nine.
No software drops/remaps occur. At tick 3487, camera 1605,1536, 50 SAT entries
lose 384 opaque sprite-plane pixels under hardware limits. Native parser/render
checks match the independently decoded limited image on all 224 lines. No
whole sprite is fully hidden/offscreen in that snapshot. Background/window
composition is excluded, so this is not a final-screen missing-pixel count.

The read-only scanline audit now saves the first pressured SAT/VRAM snapshot
for each transparent-border crop candidate. Its second 4,000-update run matches
every state and ideal sprite-plane hash from the first; native synthetic
boundary/flip checks also pass. Ten snapshots identify exact linked keys.
Cropping key 0x242 from 32x32 to 24x32 recovers 31 sprite-plane pixels at its
first pressure snapshot (tick 2660), retaining every ideal pen and requiring no
new patterns. The initial runtime candidate preserves 4,000 states/ideal planes
but slows 7,324 to 7,365 frames for only 21 fewer width-pressure lines. It is
not promoted; an isolated implementation is being evaluated. Evidence:
`.local/bc-current-r7-visual/`, `.local/bc-current-r7-crop-snapshots/`,
`.local/bc-width24/`. Production ROM remains unchanged.

The isolated width24 V2 also preserves all 4,000 states and ideal planes, but
takes 7,360 frames for the same 21-line pressure reduction. Both implementations
are rejected for their added cost. Candidate files/ROM are archived under
`.local/bc-width24/candidate-v2/`; production gameplay source is unchanged and
isolated gameplay source is restored. The read-only audit improvement remains.
All measurement jobs are terminal.

## Frame-skipping prototype — initial evidence, not retained

Isolated84b7534b uses engine-owned VInt time debt and at most three BC updates
per outer frame. Intermediate eligible updates skip presentation; queued DMA,
transitions, continue/ending UI and final batch updates force presentation.
Pause/non-BC ownership resets debt. Catch-up clears logical press edges.
Physical input/autofire advancement per catch-up update still needs refinement.

The R7 4P HuCard 4,000-update plain sample takes4,500 video frames (about53.3
updates/s at nominalNTSC60), with zero audio underruns. A separately hooked
per-update input replay matches all4,300 canonical gameplay states against
083b48ac, completing in4,753 versus7,741 frames including startup. Ten protected
4P HuCard openings (300warmup/2,500measured) range50.20–60 nominalupdates/s;
R3 is closest to the threshold. These are preliminary cadence samples, not
whole-route or exact50Hz acceptance. Rendering cadence is lower than simulation
cadence. Four-player menu, each-controller pause/freeze/resume, exit/re-entry
and paused reset checks pass.

All jobs terminal; source/ROM archived in `.local/bc-frameskip/candidate-v1/`.
The isolated workspace retains this prototype for continued work; root gameplay
source and packaged083b48ac remain unchanged. Remaining checks and measured
rates: `.local/bc-frameskip/status.json`.


## v2.0 release — October 11, 2026

The user accepted the existing frame-skipping performance and requested the
release at `dist/Side Arms MD v2.0.bin`. SHA-256: `9a1f73be50b4e53630bbf3f1d914114f8c1c71ef4b0d459a990211c092caf3ad`.
The 4 MiB release retains the v1.4 cartridge-header, Z80 upload/idle and protected
HUD DMA fixes. Sound data remains 32 KiB aligned; read-only bank ordering and
grouped 64-byte frontend palettes remove padding without removing content.

Home's exact developer code is Up, Up, Down, Down, Left, Right, Left, Right, A, B.
The menu adapts Black Tiger's stage selection, invincibility and infinite lives
for Normal/BC, adds 1–4 players and Sound Test, and prevents normal ranking writes
from practice sessions. Reset/Home clear the practice session.

Evidence: `.local/developer-v2/` records native menu launches, toggle/death-path
checks, reset cleanup, all 21 HuCard tracks, and multiplayer pause checks. Previous
full-campaign measurements above retain their original hashes; they are not
new measurements of this release. Testing remains emulator-only.


### v2.0 shoreline correction

Round-one BC cells 1A and 1B selected a broad blue shelf and a disconnected
rock face. They now reuse Normal's adjoining shoreline/cliff donors 54 and 56,
retaining their original pens and palette banks. All other BC cells and palettes
compare identically. A normal one-player BC launch ran 5,000 emulator frames with
312 successful live tile-cache samples; the reported scene was visually checked.
Updated `dist/Side Arms MD v2.0.bin` SHA-256: `90d0f2c0e83ab4632af58790bc61273ce3c29eaa8a4ef7fb5b0f9eba6d0cf136`.
Evidence and the preceding ROM are in `.local/bc-v2-background/`.


### v2.0 Home and boot controls update

The Home menu now uses two columns with a reserved lower-right Developer slot.
The current unlock code replaces the earlier code: Up, Down, Up, Down, Left,
Right, Left, Right. One Start press during either boot logo skips the remaining
sequence, preserving cleanup and consuming held Start before the menu opens.
Native emulator checks covered single-frame Start at frames 60 and 300, exact
unlock, Developer BC launch/reset, and four-player Home music/pause/save flow.
Current `dist/Side Arms MD v2.0.bin` SHA-256: `38f5c20cb1138e37d51ecc633e31db04ef00b88545563f29d7676f5f24ee4e1f`.
Evidence: `.local/home-ui-v2/`.


### v2.0 Options navigation and Developer reveal

Options uses two columns of six entries with values below labels. Up/Down
cycles across both columns; Left/Right changes values without moving selection.
Home no longer switches columns with Left/Right. The directional code reveals
Developer on Home without entering it. Explicit selection opens Developer.
Native menu tests and the Developer Normal launch/reset test passed; the Options
screen was visually checked. Current release SHA-256: `cdb2a715977831bf4af631fab39080cf25cb3962a4f908a015a41e89f42bafd8`.
Evidence: `.local/options-ui-v2/`.


### v2.0 Developer pickups and round-one scenery

Developer immunity now gates harmful BC contacts and terrain crush damage
independently of the respawn timer. Pickup contacts remain enabled. Native
rule tests checked all nine pickup types and ordinary/protected enemy contact;
an emulator fixture moved a live actor into pickup contact and verified weapon
selection and power increase with Developer immunity enabled.

Round one uses the dithered water ramp instead of city sky strips and consistent
floor quadrants below its rocks/panels. Its visual background extends the last
plain-floor column into the wider display margin instead of showing uninitialized
horizon cells. Collision/stage banks, palettes and rounds 2–10 remain unchanged.
An 8,500-frame emulator run completed 524 live tile-cache samples through the
boss arena; gameplay captures were visually inspected.
Current release SHA-256: `e8c3f6a3ec26e933c08f27f9c5463927cf551d625fb93a5971bca2eab7252822`. Evidence: `.local/bc-r1-fixes/`.

### v2.0 BC ground-creature facing

The two Genesis walking poses for BC family `0x368a` face opposite the
unmirrored PCE poses. Correct their horizontal orientation before applying the
source flips; leave the three attack poses unchanged. This corrects the green
creatures in round two and the same shared walking art in other BC rounds.

An 85,376-case host comparison checked all mapped family/frame/palette/flip
combinations: only the two intended walking poses changed. Genesis Plus GX
pose captures and a round-two gameplay replay verified both directions; sampled
actor positions, velocities and source attributes matched the previous build.
The finalized ROM remains 4 MiB and passes the cartridge-header checks.
Evidence: `.local/bc-r2-facing/`.
Updated release SHA-256: `a3ccd41a8328be2e39d15469225af503e15a3045a732d9de27ff65f7aa3a16cf`.

### v2.0 BC round-three shaft margins

Round three scrolls vertically within a 256px source shaft. The centered 320px
display previously exposed unrelated map columns outside that shaft, producing
broken rock faces and disconnected machinery on the right. Its 32px margins now
reflect the adjacent authored edge cells. The central playfield, source map,
collision data, artwork and palettes remain unchanged.

The shared metatile renderer now XORs cell flips with character flips instead of
adding them. Shared BC characters can already contain flips; addition could
carry into the other flip or palette bits when reflecting the margin. The
routine uses size optimization to retain the unbanked 4 MiB cartridge limit.

Genesis Plus GX replay covered the opening through the boss arena: 195 live
cache samples, 244,960 visible tile checks and 2,779 resident-pattern checks
passed. Captures were visually inspected. An extracted-renderer test checked
114,688 nametable words across all flip, palette, priority and cache-slot
combinations. All ten linked BC scenery and stage/collision banks compare equal
to the prior release. Finalization passed the ROM-size and cartridge-header
checks. Evidence: `.local/bc-r3-wall/`.
Updated release SHA-256: `9b64d2a321661723f91022f67e148dfac783b7a5530352abf30a51e9aaf1f7c5`.

### Round-three boss health verification

Checked the original PCE template at `$ACC7`: the core has seven bars of ten HP
and collision half-extents 8x4 pixels. The upper/lower sections are protected;
the core also closes during movement and has temporary protection on entry and
between bars. The translated actor-step comparison passed 4,431 captured PCE
updates, including this boss's opening/closing and defeat handlers.

In the current Genesis Plus GX build, a one-player fixture using ordinary
B-button shots defeated the boss after exactly 70 damaging one-point hits.
The fixture positioned the player to align the muzzle with the core, without
modifying boss HP, protection, movement or death state. Centering the player's
body instead of the muzzle can miss this small target: straight shots launch
five pixels above the player's position. No health or difficulty change was
made. Evidence: `.local/bc-r3-health/result.json` and `near.log`.

### v2.0 Home menu footer and final Back entry

Home now places Developer above Back, with Back always in the bottom-right
slot. Up/Down skips the locked Developer entry. Removed the last-player-count
indicator beside the shared credits. The copyright's final row aligns with
V2.0 on both boot selection and Home. Emulator captures were inspected and
controller checks passed for locked/unlocked navigation, wrapping, Developer
entry and Back. ROM finalization still passes at 4 MiB.
Evidence: `.local/home-footer-v2/`.
Updated release SHA-256: `8bde57b52139f7f3499b811ef1982b49b62011f23a482977a8b14201d94e3d2e`.

### BC terrain review and round-five underwater robots

Reviewed the round-three and round-four source collision descriptors alongside
the linked artwork. Several suspended-rock tips and the green machinery are
non-solid in the PCE map. A controller-driven round-three test stopped at the
solid blue wall (player x=70), including with Developer immunity enabled.
Player collision uses 8px probes, smaller than the 32px artwork, and the source
spawn-entry motion bypasses terrain. Most flying enemy movement has no terrain
probe. Collision rules were retained; all ten source/scenery banks compare
equal to the previous ROM, and 33,554,432 terrain lookup comparisons pass.

Round five now applies a static 25% transparency dither to fully submerged
living robot bodies in the pool, retaining their existing palette and shading.
This is a port enhancement: the inspected PCE underwater reference retains an
opaque player. Wet/dry poses use distinct sprite-cache keys, with at most four
512-byte RAM conversion buffers held until the frame's DMA flush. Cache hits
require no pattern conversion or extra DMA; sprite counts are unchanged.

One-player traversal through the pool and exit passed 276 background samples;
four-player traversal passed 137. The four-player VRAM check matched all four
wet robot patterns byte-for-byte against their masked originals. Captures were
visually inspected. ROM finalization passes at 4 MiB. Evidence:
`.local/bc-terrain-water/` (terrain atlas, `solid3.json`, `cache.json`, captures).
Updated release SHA-256: `5bd950384665778db1aed2bbf959881b039061cbaa6d7d95066124f4e342005e`.

### BC round-five embedded water seams (2026-10-11)

The blue texture inside rock-edge donor characters was out of phase with the
uninterrupted water. `normalize_water()` now aligns palette-11 water-owned
pixels to cell $43's 16px repeat after donor flips/composition. The shoreline
palette-21 gradient, every rock pixel and all collision/source banks remain
unchanged. This is offline tile correction, not a new parallax plane, and adds
no runtime rendering work. All 1,277 changed pixels belong to the water mask;
11,603 water pixels and the retained shade ramps pass the linked-ROM check.
All nine other BC rounds compare identically to the prior release.

The extra character variants initially exceeded the unbanked cartridge window.
The unchanged 640-byte BC palettes and 512-byte R5 remap now occupy existing
padding before the sound bank. Sound still starts at $80000; payload ends at
$3FFE80 and ROM finalization passes at exactly 4 MiB. No mapper or content was
removed. A 9,000-frame Genesis Plus GX traversal through the water and exit
passed 278 samples / 341,536 visible tile checks / 4,324 resident-pattern checks.
The underwater screenshots were visually reviewed.

The green walkers' visible overlap with smooth rock slopes is retained. Their
16px terrain probes and wall-climbing transitions match the PCE reference:
400 updates each of fall-in ($B050), walking ($B0BF), climbing ($B1EA) and
falling ($B189) matched, including actor state and coordinates. Original PCE
underwater imagery also shows slope overlap. This verifies movement parity;
it does not claim a new pixel-accurate slope-contact presentation.

Evidence: `.local/bc-r5-seams/` (`equivalence.json`, `shading.json`,
`walkers.json`, `after/audit.json`, before/after captures).
Release SHA-256: `d0b5e3ce883c23101ca63f62cc642d9253657b405d14a843ea3e056b7c0692bb`.

### All BC boss collision comparison with PCE (2026-10-11)

No collision discrepancy was found in the checked cases on release
`d0b5e3ce883c23101ca63f62cc642d9253657b405d14a843ea3e056b7c0692bb`.
The playable ROM is unchanged. New repeatable audit tools:
`qa_bc_all_boss_collisions.py` and `qa_bc_boss_collision_edges.py`.

Coverage includes bosses in all ten rounds, all eight round-nine rematches,
round nine's own boss and the final serpent's head/body/tail. Every replayed
round's linked source bank matches its captured PCE bank byte-for-byte.
9,630 sampled complete actor tasks (1,136 boss-part tasks and 8,494 attack/other
actor tasks during boss encounters) match PCE before/after RAM. This includes
positions, hitbox sizes, flags, HP/bars, protection timers, shot state, player
contact results and phase/death transitions. Sampling retains health/state
changes and distinct part/pose/protection states. The oracle fixtures include
controlled setups; these are routine comparisons, not ten fresh natural
playthroughs or time-to-defeat measurements.

Ten distinct observed boss-part dimensions passed 147,000 shot-boundary/gate
cases and 3,920 player-body boundary/option cases. Independent PCE routine
traces passed 20,732 shot scans and 2,191 player-contact scans. The production
indexed query passed 32,000 differential scans, and streamed 1P–4P contact
processing passed 32,000 comparisons. An outdated test fixture supplied a
party pointer for 1P despite the production contract requiring NULL; that
fixture was corrected, with no game-code change. Co-op health tests confirm
the intentional effective multipliers: 1P/2P 1×, 3P 1.5×, 4P 2.25×.

Native 68000 scratch-cartridge checks passed 1,048,576 solo body predicates,
1,048,576 paired party bounds and 4,096 complete shot-index comparisons.
Linked boss body geometry and native sprite offsets match 1,105,920 PCE
reference pixels, including rematches; all 20 final-serpent poses and 80 flip
cases pass. Dedicated boss projectile geometry/upload checks also pass.

Interpretation: composite bosses generally expose an 8px-by-4px *half-size*
central weak point. The larger visible body has separate contact records and
protected parts; touching its artwork with a shot does not imply core damage.
Strict edge comparisons, phase locks and post-bar protection are inherited
from PCE. Final-serpent records use 8px-by-8px half-sizes. No hitbox enlargement,
protection reduction or health rebalance was applied.

Evidence and per-round part/flag/protection inventories:
`.local/bc-all-boss-collision/report.json`, `boundaries.json`, replay logs,
PCE contact results and native-test logs. These are emulator/source checks,
not new physical-hardware acceptance or an exhaustive proof of every phase.

## BC protected crush boundary (October 11)

Investigating the reported round-seven pipe overlap found a Developer-only
coordinate wrap: source movement returns early on a scrolling crush, before
screen clamping. Suppressing death allowed repeated subtraction past the left
limit and eventually moved the player to the opposite edge. `bc_player_control`
now restores the left/top minimum on a protected crush. Ordinary terrain probes
and unprotected crush deaths are unchanged. An invulnerable player can still
survive scenery scrolling over a trapped position; this change is not solid-body
push-out or a claim to reproduce the reported direct entry into the block.

The linked round-seven source/collision bank matches the PCE reference exactly.
Four stationary-camera native approaches to the pipe block movement, with and
without Developer protection. The controlled scrolling probe previously moved
x=16 to x=5 and then x=239; the rebuilt ROM stays at x=16. The host regression
checks 4,104 updates across both crush axes and four scroll increments, including
ordinary crush deaths. The existing source player-flow replay passes 1,075
control and 1,073 pose updates. Evidence: `.local/bc-r7-block/` and
`tools/qa_bc_invulnerable_crush.py`. These are bounded emulator/fixture tests.

ROM SHA-256: `a941de925fada0a30bc605c393592aee47fc6c6960a100da44672d26543f71ff`.
The finalized ROM remains 4 MiB with the existing EverDrive header checks;
`_stext=0x3ffe80`. Boss-entry audio remains unresolved and is unchanged.

## BC bosses 6–10 selection audit (October 11)

The user reported the same boss appearing across late levels. On unchanged ROM
`a941de925fada0a30bc605c393592aee47fc6c6960a100da44672d26543f71ff`,
current-source replays pass 6,702 sampled boss/attack updates for rounds 6–10
(9,630 for all rounds), including HP, collision and phase transitions. Imported
boss bodies, attacks, reprise poses and final-serpent rendering pass native
pixel/VRAM checks. The synthetic collision edge/gate sweep also passes.

The native 6→7→8→9 continuous test observes distinct families 36BA, 36C6, 36C0,
then 36B6 (round nine's first reprise) and verifies their resident graphics bytes
against the corresponding ROM banks. Round nine separately completes all nine
encounters and enters round ten with scores/lives retained; round ten completes
six head-death stages and reaches its ending handoff. Progression uses explicit
forced defeats and protected controller routes, not natural combat completion.
Round-six/seven/eight clear tests also run with HuCard music monitoring. A real
Home BC launch enters FS_BC. Developer mode defaults to NORMAL and has a separate
mode selector; this is a possible explanation, not a diagnosis of the user's run.

No stale boss bank or source behaviour mismatch was found in these tests. The
long-ship screenshots do not match current BC bosses six (disc) and seven
(vertical composite); the user's reported BC run remains unresolved without its
state. Round nine's repeats of rounds one through eight are intentional source
behaviour. No production/ROM changes were made. Evidence:
`.local/bc-boss-6-10-audit/`, including `chain.json` and source/graphics reports.

## Menu-launched full BC boss playthrough (October 11)

Following the user's request to play to the reported encounters, two fresh solo
runs launch BEFORE CHRIST through Home and its player-count dialog, with HuCard
music, from round one through all ten rounds, the ending and return to Home.
Both use explicit debug invulnerability and controller movement/fire, with no
round warps, forced boss defeats, seeded health/weapons or forced stage exits.
Both reach `final_clear` at 103,607 simulation updates. This is a protected
playthrough, not an unassisted difficulty or performance certification.

The recorded run captures each boss 180 updates after its first observation,
after its graphics become visible. All 18 encounters are captured: eight stage
bosses, nine round-nine encounters, and the final serpent. The visible bosses in
rounds six/seven/eight are respectively the disc, vertical composite and blue
vertical boss. Round nine repeats families 36B6,36C4,36BC,36BE,36B8,36BA,36C6,36C0
then introduces 36C2; round ten uses 36D0. No incorrect repeat or missing art was
observed. Audio monitoring reports no queue underruns or software sprite drops.

Evidence: `.local/bc-boss-playthrough/recorded/result.json`,
`boss-observations.json`, its PNGs and `controller-inputs.bin`. The initial run
is retained under `solo/`; its boss-entry pictures were taken before drawing
settled and should not be used as visual evidence. Current ROM is still
`a941de925fada0a30bc605c393592aee47fc6c6960a100da44672d26543f71ff`.
The user's long-ship screenshots still differ from this current BC run; no
cause is established for that discrepancy, and no production fix is claimed.

## Developer launch control ambiguity (October 11)

After the user identified Developer launch as a possible distinction in the
wrong-boss screenshots, a controller-only Developer launch with MODE BEFORE
CHRIST and ROUND 7 reaches FS_BC and boss family36C6. The prior ROM also launches
that selection correctly. However, the non-grid menu accepted A/C as value-step
buttons: independently reproduced selecting BC then pressing A on MODE changes
it back to NORMAL. This is a confirmed input ambiguity, not a confirmed diagnosis
of the user's screenshots.

Home Developer settings now change only with Left/Right. A/C/Start leave value
rows unchanged, while action rows still activate. A footer displays the exact
launch mode and round. Native tests cover both Normal and BC, per-button MODE
and ROUND stability, Left/Right protection/lives toggles, Sound Test navigation,
practice reset and ordinary launch. A direct BC round-seven launch reaches its
vertical boss. Evidence: `.local/bc-developer-launch/` and
`tools/qa_developer_menu.py`.

Finalized 4 MiB ROM SHA-256:
`fb0a68a91668e2c7c0c7c77bc184168b7ea83dcef2560e9be33b1c63dfac95db`.
Copied to `dist/Side Arms MD v2.0.bin`. No boss assignments, behaviour or graphics
were changed. The prior full protected campaign applies to the preceding build;
this build has the focused Developer-menu and round-seven checks described above.

## All BC Developer launches (October 11)

Tested the current `fb0a68a9…` cartridge through the actual Home secret code,
Developer MODE/ROUND/LAUNCH controls and Options PC Engine music selection.
Ten fresh emulator launches and ten successive soft-reset/relaunches in one
emulator session cleared every selected round. Both round-ten runs completed
the ending and returned Home. Developer invulnerability and infinite lives were
ON; no debug protection, seeded weapons/health, forced defeats or stage exits
were used. Gameplay movement and firing came from the controller pilot.

The fresh series uses the QA Genesis Plus GX core. The successive series uses
`~/Library/Application Support/RetroArch/cores/genesis_plus_gx_libretro.dylib`,
loaded directly through libretro. This checks the user's installed core, but
not RetroArch frontend configuration or a previously loaded save state.

All 36 boss encounters across the two series match the expected BC families:
rounds one through eight: 36B6,36C4,36BC,36BE,36B8,36BA,36C6,36C0;
round nine repeats those eight then introduces 36C2; round ten uses 36D0.
Settled screenshots show the disc in six, vertical composite in seven, blue
vertical boss in eight and serpent in ten. Each boss was defeated by shots.
Neither series reproduces the reported incorrect long-ship repeat.

Music command/track checks and queue monitoring pass throughout. Installed-core
boss-entry clips for rounds five and six contain two seconds before entry and
ten seconds afterward; neither clips (peaks 7930 and 7900 of 32767) and neither
has a queue underrun. These measurements do not establish subjective fidelity
or identify the reported chaotic sound. No further production fix is claimed.

Evidence and reproduction scripts: `.local/bc-developer-all/`. `report.json`
contains all twenty results, exact ROM/core hashes and limitations. `r1`–`r10`
are fresh launches; `sequential-r1`–`sequential-r10` are the installed-core
same-session runs. Each contains Developer selection, music setting, boss
screenshots and audio monitoring. `sequential-r5/boss-entry.wav` and
`sequential-r6/boss-entry.wav` preserve the reported transitions for comparison.
The dist cartridge remains identical to the verified finalized release ROM.

## BC round-one opening correction (October 11)

The user's new screenshot reproduces on `fb0a68a9…`: the wider viewport exposes
column 15, before the authored stage begins at column 16, as a stray vertical
city strip. Round one's visual border now clamps both to its first authored
column (16) and its existing final column (78). Collision data is unchanged.

The city-base mapping also remained incorrect. Source cell 0F used an unrelated
whole Normal metatile with a flat grey upper half. It now shares 0E's lower
facade and uses the existing city material above. Cells 11/12 finish the city
against the sea; 12 shares 0F's left facade and the sea cell's right half.
Only these three R1 cells change. All palettes, source/collision banks and
rendered cells in rounds 2–10 compare equal to the preceding release.

The earlier live cache checks proved correspondence to generated assets, not
that those assets were visually correct. This correction was inspected against
the PCE reference composition and actual native opening captures. An 8,500-frame
native level-one replay passed 524 cache samples, 623,616 visible tile checks
and 5,874 resident-pattern checks. A separate real Developer menu / PC Engine
music launch reached and defeated the first boss through controller fire.
Source quadrant joins were independently checked on the linked ROM. Evidence:
`.local/bc-r1-opening/`, including `0000.png`, `compare0.png`, `checks.json`,
`live.log` and `developer/result.json`.

Finalized ROM remains 4 MiB with the standard cartridge/RAM/SRAM header and
checksum. Release SHA-256:
`f203f494e798ea5f45dc16320a8173a88beb8f75a65aaaf9af582263cb18cbee`.

## BC round-one cave joins (October 12)

The mid-stage cave still used unrelated whole-metatile substitutions. Rebuilt
its 23-cell family from shared 16px quadrant identities, checked against the
original source table. Repeated rock sections now use consistent Genesis rock
material; arch upper/lower sections share one continuous donor arch; floor and
console pieces no longer splice unrelated large scenery blocks into the wall.
The external slope envelopes follow reference geometry while all interior
pixels use existing Genesis materials. This is adapted art, not PCE pixel parity.

Generator: `tools/bc_background_r1_cave.py`; silhouette envelopes:
`tools/data/bc_background_r1_cave_contours.json`. Native visual evidence and
reference comparisons are under `.local/bc-r1-cave/`. The linked-ROM regression
`tools/qa_bc_r1_cave.py --before .local/bc-r1-cave/before` verifies 92 source
quadrants, equality of shared pieces, changes confined to the cave family,
unchanged collision/source banks and unchanged rendered rounds 2–10. Earlier
opening-city and border fixes remain intact. A native 8,500-frame replay passed
524 live background samples through the boss arena; entrance, middle and exit
captures were inspected. The finalized 4 MiB cartridge was copied to the v2 dist.

## All-ten-round BC background comparison (October 12)

Compared all 684 linked cells and 158 route positions against original PCE
backgrounds reconstructed from captured code/VRAM/palette. Reviewed the paired
route sheets and native 320px gameplay sheets, including the additional display
margins. Genesis material/colors and some adapted object dimensions intentionally
differ; this is a broken-join/omission review, not a claim of PCE pixel parity.

Additional confirmed defects and corrections:
- R1 cells 13/14/15 used flat cyan donor water behind the pre-cave rocks. Their
  water pixels now match the surrounding sea in the correct world phase. Mixed
  rock/water characters use the unchanged sea palette bank; rock colors in those
  characters select its nearest existing grey/olive shades. Shape and palette
  arrays stay unchanged. 1,947 linked water pixels match the surrounding sea.
- R2's initial extra left column exposed an unrelated map block. It now reflects
  the authored entrance wall, preserving the original central playfield.
- R5's initial extra left column likewise exposed unrelated scenery. It now
  extends the actual stage's first column, removing the disconnected strip.

No further broken joins were found in R3, R4 or R6–R10 in the reviewed routes.
Repeated-pattern variant candidates in R1–R4/R10 were reviewed against composed
objects; differences alone were not treated as corruption or automatically
replaced. No missing visible-cell substitutions or unmapped route cells remain
in the comparison. All source/collision banks and R2–R10 linked artwork compare
equal to the pre-audit ROM; the runtime border policy changes only R2 and R5.

The final build completed all ten real Developer-menu solo launches with PC
Engine music, Developer invulnerability and controller-driven boss defeats.
All ten post-upload background audits passed: 2,465 sampled states, 2,936,688
visible tile checks, and 44,522 resident pattern checks. Sampling is every 32
simulation updates; this is not exhaustive frame, multiplayer or hardware timing
coverage. The final-round run completed its ending and returned Home.

Evidence: `.local/bc-all-backgrounds/report.html`, `report.json`, per-round
`route-comparison.png`, `cell-comparison.png`, `native-route.png`, and results.
Regression: `tools/qa_bc_r1_water.py --before .local/bc-all-backgrounds/before`.
The 4 MiB cartridge passed finalization and was copied to `dist/Side Arms MD
v2.0.bin`. Final SHA-256:
`6914f0a56dc31a2736239dc8a19aac3dc003d504b75783937e66ba6a5b8bcf66`.


## Sequential Developer launches on installed core (October 12)

The final v2 cartridge above was retested in one emulator session using the
installed RetroArch Genesis Plus GX core. Each BC round, 1 through 10, was
selected individually through the Developer menu after a soft reset, with
PC Engine music, invulnerability and infinite lives enabled. Menu input and
automated movement/fire reached and defeated every boss without forced defeats,
seeded health/weapons, or injected music requests.

All ten launches passed. Round 9 defeated its eight reprises and its own boss;
round 10 completed the ending and returned Home. Boss families and requested
music tracks matched the expected mapping. Audio monitoring recorded no queue
underruns, and saved boss-entry clips had no clipped samples. This does not
establish that the reported chaotic entry noise is fixed. The test used the
installed core headlessly, without the RetroArch frontend settings/save states.

Local evidence: `.local/bc-developer-final/report.json`, `bosses.png`, and the
per-round menu screenshots, boss observations, results and entry audio.


## v2.1: first-stage Vivid and PC Engine audio (October 12)

Normal stage 1 uses the v1.2 background conversion again. Its linked tiles,
attributes, map and base palette match byte ranges in the saved v1.2 cartridge;
its dedicated 32-word Vivid palette uses the original v1.2 transform. Standard
mode also uses that restored first-stage base conversion. All other consumers
retain the prior shared Vivid LUT byte-for-byte. BC's ten rendered background
banks, palettes and collision data compare equal to v2.0.

HuCard carrier levels are raised by eight YM total-level steps (6 dB); modulator
depth, score timing and PSG effects are unchanged. Matched 180-frame Sound Test
recordings show roughly 4–5.5 dB more measured RMS through Genesis Plus GX,
depending on the track and the chip's nonlinear output. On instrument changes,
the Z80 now loads pitch, stereo and total levels before key-on. Previously it
keyed on using the previous pitch/levels. This removes a transition hazard;
it is not proof that the user's particular reported end-of-boss glitch was
reproduced or that all audible artifacts are resolved.

Validation:
- `tools/qa_v21_first_stage.py` compares against the user-supplied v1.2 ROM,
  checks the unchanged shared LUT and all ten BC background banks.
- 524,288 FM packet renders cover all 16-bit period values, both regions and
  repeated/changed cache keys. MAME verifies actual chip writes for stage,
  boss and clear tracks, including the corrected key-on ordering.
- All 21 tracks pass 600-frame audio checks in NTSC and PAL: clock, queue,
  audible output, no clipping, stop, return to Arcade and exit to Options.
- Final-ROM Developer Normal stage 1 reaches and defeats the boss with assisted
  hit tests, plays the clear jingle and reaches stage 2. No queue underruns or
  clipped samples; peak 13,652. Four live CRAM checks verify the restored first
  stage and the normal palette policy in stage 2.
- Final-ROM Developer BC stage 1 clears with controller-driven shooting and no
  injected defeat. All ten BC palettes also pass native Standard/Vivid checks.

Local evidence: `.local/v21/first-stage.json`, `final-normal/`, `final-bc1/`,
`final-music/`, `final-music-pal/`, `final-bc-palettes/`, `fm-frames.log`,
and `registers.log`. Cartridge: `dist/Side Arms MD v2.1.bin`, 4 MiB, SHA-256
`d7d1f2ebcc50a81a026608eb8e3b3e3336cb4d5dfa09c6a961b7c903f5a96ac4`.


## v2.1 follow-up: BC first-stage visual remaster (October 12; superseded)

Kept BC's stage rather than substituting Normal's map or encounters. BC R1 now
uses the same original Vivid transform as the restored Normal first stage,
through a dedicated 32-word palette. Its base palette and the shared LUT remain
unchanged. The coastal rocks retain their masks and water phase, with Normal
stone grain, lit upper edges and darker undersides. The cave uses Normal's
32px central rock texture within the existing BC silhouettes, shaded with the
existing charcoal/slate/highlight colors. Metal supports use the complete Normal
arch material so the cross-bracing is visible. Shared BC shape envelopes remain
identical; larger texture phases intentionally need not repeat at every 16px
source quadrant.

`tools/qa_bc_r1_remaster.py` verifies 64,512 silhouette pixels, 92 shared cave
shape quadrants, and 1,947 unchanged water pixels. BC R1 source/collision/event
bytes and palette are unchanged; all nine other BC backgrounds and 103 linked
Normal artwork blobs compare equal. The change affects 21 BC R1 cells plus its
Vivid presentation. The final cartridge passes all 640 native Standard/Vivid
background palette checks across the ten BC rounds.

A real Developer-menu BC R1 launch with invulnerability, one player and PC Engine
music reached and defeated the boss through controller-driven shooting. The
post-upload background audit passed 211 samples, 255,136 visible tile checks,
and 2,558 resident pattern checks. No audio underruns or forced boss defeats.
Normal first-stage replay also checks the original Vivid palette and its reset
at stage 2; its boss defeat is assisted. These are emulator checks, not physical
console or exhaustive frame coverage.

The Z80 sound bank precedes BC palette metadata in link order to avoid an
extra 32 KiB alignment gap. The final ROM passes the 4 MiB header/checksum gate.

Evidence: `.local/bc1-remaster/art-checks.json`, `comparison.png`, `final-cart-play/`,
`final-cart-palettes/`, and `final-cart-normal/`. Updated `dist/Side Arms MD v2.1.bin` SHA-256:
`997c88b589bea8fc141660cffd9ce657cd2605ad5599ced42d7414b23f3b361b`.

## v2.1 correction: remove rejected BC R1 texture replacements (October 12)

User reported the remaster as more vivid but visually broken. Inspection shows
excessive white coastal outlines and repeated diagonal cave textures. Reverted
the cave and water generators to the pre-remaster v2.1 versions, retaining the
dedicated brighter BC R1 Vivid palette. This is a rollback of those artwork
substitutions, not a claim that every historical BC art issue is resolved.
The previous mask-only checks did not establish visual quality.

The corrected ROM matches every resolved background pixel and attribute in all
ten BC rounds against the pre-remaster baseline. Source/collision bytes, base
palettes and 103 linked Normal artwork blobs also match. Native Standard/Vivid
checks pass all 640 palette words. A Developer-menu BC R1 replay clears the boss
through controller shooting, with 211 background samples, 255,136 visible tile
checks and no audio underruns. Route captures include the restored cave supports.
Testing is emulator-only.

Evidence: `.local/bc1-correction/art-checks.json`, `comparison.png`, `play/`,
and `palettes/`. Release: `dist/Side Arms MD v2.1.bin` (4 MiB). SHA-256:
`6dd3f5ac54a3f40ffc92734f5163877dc5a616dab15efe3bd8e6bda59c51348a`.

## v2.1 follow-up: correct BC R1 cave donor selection (October 12)

The previous rollback did not fix the wrong donor tiles. The cave composer used
meta 74 (a rock face) for metal arches, stretching its lower rows into legs. It
also assigned one lower-left crop of meta 70 to eight distinct source patterns,
then overwrote sloping edge materials with that same crop.

Use the complete meta 75 arch quadrants without vertical stretching. Select
distinct Normal rock-face and wall quadrants for the corresponding BC motifs,
and apply the existing source edge contours to those selected materials. The
low ridge now uses rock material rather than the prior water-colored donor edge.
These are visually selected Normal counterparts, not pixel-identity claims to PCE.
The city and coastal-water mappings are unchanged by this correction.

Compared the PCE quadrant atlas and Normal donor quadrant sheet, then inspected
native entrance, middle and exit captures (route 008, 010, 013). The Developer
BC R1 replay clears the boss by controller input with no forced defeat. All
211 background samples and 640 Standard/Vivid palette words pass. Exact shared
quadrant checks cover 92 cave quadrants, and their IDs agree with the original
BC source table. Other BC rounds, source/collision bytes, Normal art, and water
pixels remain unchanged. This verifies the targeted cave correction, not every
historical BC tile selection.

Evidence: `.local/bc1-tile-mapping/` (source-patterns.png, normal-cave-quadrants.png,
art-checks.json, play/, palettes/). Latest v2.1 ROM SHA-256:
`d33b3ae694335bb131a5fdfc0f7bd46aca1c7082c5feab656d2cdaee76fde233`.

## v2.1: original PCE artwork for BC level 1 (October 12)

User chose the PCE presentation after comparing both versions. BC R1 now
converts original captured PCE characters directly; the Normal donor recipes
are no longer used for this round. The existing PCE layout, encounters and
collision bytes remain intact. `tools/bc_background_r1_pce.py` pins the capture
hashes and generates native 4bpp resources offline. No runtime PCE emulation.
Source-derived assets remain in ignored generated directories.

Two Genesis scenery banks fit the original water, cave rock, stone floor and
red-earth ramps exactly. Other source palettes use consistent nearest-color
assignments per original palette: 42,350 of 49,319 opaque pixels (85.87%) retain
exact RGB3 colors in Standard. Vivid uses its own guarded palette to keep shade
steps distinct. Standard is closest to the original PCE color presentation.

`qa_bc_r1_pce.py` independently decodes all 63 original cells and verifies 64,512
pixel positions/silhouettes, consistent color correspondence, and protected
source ramps against the linked ROM. All nine other BC backgrounds and 103
Normal resources are unchanged. The shared Vivid LUT is unchanged after rebuild.

Original PCE tiles required additional space. Splitting the R5 map from the BC
palettes and placing four small Normal palettes in the unused pre-sound padding
keeps the full artwork within the 4 MiB cartridge. Sound still starts at $80000;
DMA tile blocks retain their 512-byte alignment. No assets were dropped.

Final-ROM checks: real Developer-menu BC1 replay reaches and clears the boss
through controller input, 211 live background samples, 255,136 visible tile
checks, 2,744 resident patterns, zero audio underruns. Inspected native opening,
coast, cave middle and exit captures. All 640 Standard/Vivid palette words pass
across BC rounds. Normal1 also reaches stage2 and retains its intended palettes
and audio behavior; its boss defeat is assisted. Emulator checks only.

Evidence: `.local/bc1-pce-art/` (source-checks.json, play/, palettes/, normal/,
opening.png, cave.png and their Standard counterparts). ROM:
`dist/Side Arms MD v2.1.bin`, SHA-256 `55a64cd761f02969116be0e094dd16d851be200a372fd5497150d7a69bea7695`.

## v2.1 itch-report fixes (October 14)

Reviewed the current [itch comments](https://rester159.itch.io/side-arms#comments)
and [v2.0 devlog comments](https://rester159.itch.io/side-arms/devlog/1703356/side-arms-md-20#comments).
Current actionable reports: quiet PC Engine music/first-stage ending glitch,
washed-out Normal stage-one scenery and boss, BC rapid fire, and wheel gun
placement/wrong animation tile/missing lightning. The audio/color reporter
explicitly identifies Normal (calling it Arcade), not BC. Actual Arcade mode
continues to use its original soundtrack. The recent PAL-clone reply reports
v2.0 working; no new startup workaround was added.

Changes:

- The controller mapper now reads the active BC player arena, including allocated
  peers, instead of interpreting BC storage as Normal players. Both rapid-fire
  buttons and six-button facing lock use BC state. Disabling turbo retains held
  fire for charging. Normal AUTO and combined leader/ring behavior is preserved.
- Original arcade `$71EF/$71F2` initialize both pod startup waits. Restoring the
  first wait prevents the guns attaching to the background too early.
- Home cutouts and wheel frames reused numeric extra-metatile IDs for different
  pixel data. Cache hits now check source identity and upload the correct bank.
  The first reproduction found two stale resident cells; the fixed replay has none.
- Wheel health-bar loss now draws original bank-three `$9367..$9F2B` text graphics,
  five frames held six game ticks each, using existing font graphics. The window
  replaces stars on occupied text rows while the effect is visible.
- Stage-one sprites/boss/HUD now receive the original Vivid transform as well as
  the already-restored v1.2 background. Other Normal stages retain the guarded LUT.
  BC1 keeps the original PCE artwork selected October 12.
- Retained the v2.1 +6 dB PC Engine carrier-level adjustment and register ordering
  fix: instrument/pitch/pan/levels are written before key-on.

Validation on final cartridge `723fbf96...`:

- 2,848 production input-mapper cases under address/undefined-behavior sanitizers:
  BC 1–4-player slots, dead/inactive slots, facing lock, held fire, Normal AUTO and
  combined leader/ring. Native physical A/B holds in 1P and 4P BC produce 24 press
  edges per 96 video frames with turbo enabled, one edge with turbo disabled.
  Native tests inject settings/protection; they do not bypass the input mapper.
- Native sections 2, 4 and 9, with Home parallax on/off, plus a four-player wheel
  run: 292,100 resident pattern comparisons, all three rotation frames and all
  five lightning frames, source startup-delay checks, and boss exits pass. Boss
  runs warp before entry and use assisted damage; these are not unassisted clears.
- Normal1 PC Engine intro/stage/boss/clear/stage2 sequence completes with zero
  queue underruns or clipped samples (peak 16,236). Native CRAM checks verify all
  64 background/sprite words and restoration of the later-stage palette policy.
  Boss defeat is assisted. This does not confirm audio on physical Models 1–3.
- 524,288 FM-frame cases/3,145,728 voices pass, covering both regions and all
  65,536 pitch inputs. All 640 Standard/Vivid BC background CRAM checks pass.
- First-stage tiles, templates, map and base palette match the local v1.2 ROM;
  both stage-one palettes use its original Vivid transform. All ten BC background
  resources remain unchanged from the October 12 PCE-art build.

The cartridge remains 4 MiB; no mapper is required. Compact front-end code and
small crack/palette tables in the pre-sound alignment gap keep the sound bank at
`$80000`. Gameplay simulation modules retain their existing optimization settings.
Evidence: `.local/itch-v21-oct14/`. Tests are emulator/host checks; physical-console
music balance and the reported hardware end-of-stage noise still need retesting.

Release: `dist/Side Arms MD v2.1.bin`. SHA-256:
`723fbf9661e4fe1799cba381c81673dd0b4d0daf590ebc7d4978fb7e4fef20c3`.


## v2.2 itch follow-up (October 20, 2026)

Reports reviewed: [PAL/60 Hz Mega EverDrive Pro crash after about 20 seconds](https://itch.io/post/17657451)
and [PC Engine music/SFX balance and residual first-boss ending noise](https://itch.io/post/17625345).
The commenter suggestion about expansion-bus termination is not an established
cause. No physical console or EverDrive was available to reproduce this failure.

Changes:

- The local SDK DMA adapter requires acknowledged Z80 bus ownership before both
  queued and immediate DMA. Interrupt protection covers acquiring/releasing the
  bus, and immediate DMA issues both command words after acquisition. The SDK
  installation is not modified. Unknown source patterns fail the build. This
  addresses a bus-contention risk; it is not proof of the reported crash's cause.
- PC Engine music gains another four carrier TL steps (up to +3 dB versus v2.1),
  while its PSG effects drop three attenuation steps (6 dB). The effects mix
  persists across boss-stop/clear preparation. Arcade effects are unchanged.
- Home and options display v2.2. Existing v2.1 gameplay/art corrections remain.

Validation on SHA-256 `9b4befdf59514a8203bac70c30f512abd5d7c5c3cd5e88cf1403d2ff91fad72b`:

- PAL and NTSC dirty-RAM/I/O boot and reset: 2,000 frames before reset, 2,120
  after reset each; driver ready and 120/120 final game-loop updates.
- 4,000-frame boot/attract native DMA audit: 3,435 transfers, descriptor register
  checks and atomic paired command writes pass. Linked immediate DMA inspection
  confirms the bus acknowledgement loop precedes both command words.
- Normal first-stage Home/Developer PCE route passes intro/stage/boss/clear/stage2
  transitions over 8,443 frames after launch, with assisted boss damage. No music
  queue underruns or clipped samples; boss-clear peak 12,563. Reduced SFX mix
  remains active on every tested frame, including stop/clear transitions.
- Protected four-player BC Home launch reaches stage/boss music naturally with
  zero queue underruns and maximum track-preparation wait of two frames.
- 524,288 FM frames / 3,145,728 voices pass all pitch inputs in both regions;
  512 linked Z80 attenuation cases pass both source mixes and silence clamping.
- Normal stage-one artwork still matches v1.2; all ten BC background resources
  and the shared Vivid table are unchanged from v2.1.

Evidence: `.local/v22/`. These checks do not certify hardware compatibility or
resolve analog output differences between console models. The EverDrive crash
and remaining physical-console audio complaint require reporter retesting.

Release: `dist/Side Arms MD v2.2.bin`, 4 MiB, source-only Git repository.
