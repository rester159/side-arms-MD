# HuCard soundtrack conversion

## Current build: 5f6aa68a

ROM `5f6aa68ad8c9fce146ae952f0885957fb063436257f1f144f9c4c9b70e184cab`
passes all 21 Sound Test selections in NTSC and PAL, with 420 complete packet
checks per region, no underruns, stop silence and Arcade resumption. All twelve
native Team Player 3P/4P Normal/BC/Rush launch/save/reset/migration cases pass.
Both protected BC campaigns complete all rounds and credits without underruns;
the autonomous four-player stage-to-boss music transition also passes. Only one
music source runs at a time; HuCard selection disables the Arcade sequencer
while retaining game sound effects. HuCard score processing uses the 68000.

Evidence: `.local/bc-r3-pickup-diver/`. This verifies playback, timing, switching
and persistence. The FM conversion's documented timbre/phase limits remain;
these tests do not establish bit-identical PCE synthesis or subjective approval.
Expansion release acceptance is tracked in `expansion-acceptance.md`.


## Historical build: 47c4adc5

ROM `47c4adc56acb923409d146da41e2513bef448af4e9edad5d848e848a09ebb09e`
passes all 21 Sound Test selections in NTSC and PAL, 420 complete packet checks
per region, and all twelve native-Team-Player 3P/4P Normal/BC/Rush launch/save/
reset/migration cases. The autonomous 4P BC stage-to-boss transition passes.
Both protected 3P/4P Rush runs defeat all twelve bosses through player fire.
There are no observed audio underruns in these runs or the current timing sweep.
Evidence: `.local/blue-effect-shades/homing-audio/`, `homing-gameplay/`,
`finish-safety/`, and `final-normal-rush/`. Overall release acceptance still
requires clarifying the displayed-frame-rate target; see `expansion-acceptance.md`.


## Previous-ROM full Rush catch-up checks

ROM `bc389f613b23cc724217728db34020da9d333f072da1b90151108c4614a13566`
finishes all12 Boss Rush encounters with3P and4P protected players using player
fire, without injected kills. Both full runs have zero audio underruns and a
minimum58.32 simulation updates/sec. Native Team Player4P NTSC and3P/4P PAL
launch/save/reset checks pass. See `.local/normal-frameskip/rush-integration.json`.
Sound Test and other-mode historical evidence below retain their original hashes.

## Previous-ROM Normal catch-up checks

ROM `965be78d5455fe843e39a588fbae63fd4c01992d7d541a364dccb6ae8902d2a9`
passes the 20 HuCard Normal timing fixtures (3P/4P from all ten section warps),
with no underruns and a minimum 55.13 updates/sec. Native Team Player Normal 4P
NTSC and 3P/4P PAL launch/save/reset/migration checks also pass with no underruns.
The PAL copy changes only the region header. Full-track and other-mode results
below retain their original ROM hashes and are not relabeled as fresh checks.
Evidence: `.local/normal-frameskip/guard4096-matrix/matrix.json`, `native-guard/`
and `native-pal/`.

## Previous-ROM playback — integrated compositor build

ROM `03a943633267d935f94ec4bbc2c8eb704ebf1318baee396dd62377577092acbd`
passes all 21 Sound Test selections in NTSC and PAL, with 420 packet checks per
region and zero underruns. All 12 native-Team-Player 3P/4P Normal/BC/Rush
launch/save/migration cases and the autonomous BC stage/boss music transition
pass; the maximum music request wait is two frames.
Evidence: `.local/final-compositor-03a94363/summary.json`.
The regenerated `.local/hucard-audio-review-03a94363/index.html` uses captures
from this exact ROM and passes its A/B playback-control checks. This is bounded
emulator evidence, not subjective listening approval or full-campaign coverage.

## Previous-ROM playback and listening comparison — October 9

Previous ROM: `082f88aac2da4bcf6d6eb929df20710fefc9c94f95bc53112a50254b359a7111`.
All 21 Sound Test selections pass in NTSC and PAL, with 420 complete packet
checks per region and zero underruns. Stop silence, Arcade resume and return
to Options also pass. Twelve 3P/4P Normal/BC/Rush region combinations pass
using the emulated Team Player adapter with no logical-input override;
settings save/reset and version-four migration pass. A protected real-Home BC
stage-to-boss run changes music without injected music requests, with a maximum
two-frame request wait. These are bounded tests, not physical-console certification.

The fresh `.local/hucard-audio-review-082f88aa/index.html` compares all 21 original
PCE recordings with current-ROM Genesis captures. Original/level-matched audio,
A/B position switching and exclusive-playback control tests pass. Evidence:
`.local/final-audio-082f88aa/summary.json` and the page's `manifest.json`.
This replaces 083b48ac as the current listening comparison. It does not establish
subjective timbre approval or phase-exact synthesis.

The user-supplied source is available at
`.local/pce-hucard/SideArms - Hyper Dyne (USA).pce`, extracted from
`~/Downloads/SideArms - Hyper Dyne (USA).zip`. It is 262,144 bytes; SHA-256:
`06b8ac408d5f7942165bb06b5ce0795a6283022d034ca70dc256e17ed1af87cd`.
The ROM, decoded source data, and reference captures remain local inputs.

## Verified source work

- Run the USA cartridge as MAME `tg16`. Its region check at `$E006-$E011`
  redirects a mismatched machine before the game starts.
- Sound code lives in ROM banks 8/9, mapped at `$4000-$7FFF` during the
  timer handler at `$E0C8-$E102`. `$4003` dispatches a command; `$4000`
  advances the driver. `$40A2` writes the PSG register selected by X.
- The timer uses a 113 x 1024 CPU-clock divisor, approximately 61.870 Hz.
  Music has a separate fractional tempo accumulator, not a video-frame clock.
- The queue is `$2600-$260F`, read at `$E0DB`, with its cursor at `$2610`.
  The capture fixture substitutes commands on this read, suppressing game SFX
  and subsequent game requests without modifying the soundtrack's execution.
- `$4A00` declares 42 commands. Twenty-one are music entries (0–20), with
  aliases 8, 19 and 20 pointing to song 4: 18 distinct scores. The other
  entries are SFX and are not substituted for the existing Genesis SFX.
- Instruments begin at `$4A57`: 32 records of 40 bytes, each containing
  32 five-bit wavetable samples and eight envelope/modulation bytes.
- `decode_hucard_score.py` decodes 8,196 reachable score instructions and
  checks boundaries and branches. Every score operand/control transfer is
  represented; there is no original CPU program in the Genesis cartridge.

## Reproducible commands

```sh
.venv/bin/python tools/inspect_hucard_music.py
.venv/bin/python tools/decode_hucard_score.py
.venv/bin/python tools/capture_hucard_music_set.py
.venv/bin/python tools/qa_hucard_score_model.py \
  .local/pce-hucard/music-01-reference-v1
.venv/bin/python tools/build_hucard_score.py
.venv/bin/python tools/qa_hucard_native_score.py
```

`capture_hucard_music_set.py` captures 9,000 video frames of each distinct song
in isolated directories, using three independent MAME processes. A completed
capture can be reused; an incomplete one is not silently restarted. Retaining
Lua references to the memory taps is necessary to avoid MAME invalidating a
callback during garbage collection.

`hucard_score_model.py` is a structured development model of the score semantics
at `$4383-$46AE`. It is neither a CPU emulator nor a shipping playback engine.
It covers tempo, gate, volume, instrument, triplets, ties, dots, transposition,
vibrato parameters, finite repeats, conditional breaks, jumps and endings.

All 18 captures pass the score-model comparison at every original driver tick
following fixture initialization: 166,305 ticks in total, across all six channels.
The test compares fractional tempo state, stream cursors, note/rest countdowns,
gates, parameters and loop counters. The subsequent envelope model also passes
all 166,305 ticks, including attack, decay, sustain, release, pitch slides,
vibrato and tremolo. Evidence: `.local/pce-hucard/score-model-qa.json`,
`envelope-model-qa.json`, `music-captures.json` and each capture's state files.

## Native sequencer

`tools/build_hucard_score.py` emits 9,738 bytes of reachable score data,
21 six-channel entry points, 32 resolved envelope records and the pitch table.
Branches are relocated to offsets in this compact buffer; tempo divisions and
envelope rate lookups are resolved at build time. Generated files stay ignored.
`make` regenerates this input; `HUCARD_ROM` overrides the default local source.

`src/sound/hucard_score.c` is the native C sequencer. It implements the complete
score/envelope behavior and provides six latched voices (pitch period, volume,
pan and instrument) for the Genesis renderer. New-note pitch writes retain the
source's one-envelope-step delay. Instrument changes silence the previous
wave immediately, including when the following event is a rest.

`qa_hucard_native_score.py` compiles that same C module, starts every unique
song from reset, and compares **166,377 original driver ticks**. It checks all
six channel records, fractional tempo and the audible pitch/volume/pan against
actual captured PSG writes at each completed sound interrupt. Three aliases
are compared for 10,000 ticks each; stop clears all channels. Instrument-change
acknowledgment bit 4 is masked in the channel-state comparison because it is
owned by waveform loading. This test does not verify YM2612 synthesis or the
real-time Genesis scheduler. Evidence: `.local/pce-hucard/native-score-qa.json`.

## Genesis output and review entry

`src/sound/hucard_fm.c` translates latched voices into 72-byte YM2612 frames.
The 68000 refills a four-slot ring from the real VInt, shared with the HUD's
existing interrupt callback. It computes each packet before requesting the Z80
bus; the short bus hold only copies/publishes the completed slot. The Z80's
independent Timer A clock consumes frames at the source rate, with separate
PAL/NTSC fractional increments. A stop/idle handshake protects track changes.
A rejected/full arcade command FIFO does not stop the current HuCard track.

The first instrument conversion uses the four strongest representable Fourier
harmonics as additive YM carriers. Source envelopes drive carrier levels; pitch
slides/vibrato drive the F-number. It preserves hard stereo panning; YM's on/off
stereo cannot reproduce the source's separate left/right volume nibble exactly.
The PSG attenuation model is grounded in
[MAME's C6280 implementation](https://github.com/mamedev/mame/blob/master/src/devices/sound/c6280.cpp).
This is **a first synthesis pass**, not a completed timbre/audition gate. Some
waveforms retain only 55–67% of their spectral energy with four carriers, and
relative harmonic phase is not reproduced. Per-instrument measurements are in
`.local/pce-hucard/fm-patches.json`; these weaker conversions need attention.

### Carrier-level correction (October 8)

The initial builder incorrectly clamped carrier TL to a minimum of 16. That
value represents the common 12 dB mix headroom, not a maximum pre-headroom
harmonic amplitude: a five-bit square wave's fundamental can exceed amplitude
16. The builder now permits the corresponding stronger carrier while retaining
the common headroom. It also normalizes the four retained carriers' AC power
to the original wavetable, so discarded partials do not make complex instruments
unintentionally quieter. Spectral-energy reporting now derives its denominator
from source AC power, correctly accounting for the Nyquist bin.

`qa_hucard_fm_patches.py` independently compares the generated TLs' carrier-model
power with all 32 original waveforms. Maximum quantization error is 0.301 dB,
inside the 0.375 dB half-step bound. Instrument 24 improves from −2.221 dB to
+0.029 dB, and instrument 6 from −1.971 dB to +0.130 dB. These are analytical
patch-level measurements, not a claim of identical recorded output or timbre.
The omitted harmonics and relative-phase limitations remain; this correction
does not satisfy the remaining synthesis/audition gate by itself.

The real output test now also checks every track's peak for 16-bit saturation,
alongside its existing clock, queue, switching and SFX checks. Evidence is in
`.local/pce-hucard/fm-level-qa.json` and `fm-level-output-*.log`. The preceding
patch report and generated table are preserved in `fm-level-baseline/`.

All 21 entries pass the updated real-output check in NTSC and PAL, with zero
queue underruns or saturated samples. Largest measured peaks were 15,140 and
19,139 respectively (16-bit maximum 32,767). The main build also passes;
cartridge SHA-256 is
`250a964f9031055ae1916652fa8edc7a022b5d6818ff8e46240d47fcc1930b3a`.

The game now exposes the result in **Home → Options → Sound Test → Source:
PC Engine**. Music entries show source command IDs and track names. Sound effects remain the existing
Genesis effects. Switching Source or leaving Sound Test stops playback.
Home Options now also has a persistent **Music: Arcade / PC Engine** setting.
Arcade mode always retains its original music. SRAM settings version 5 appends
one byte; versions 1–4 default to Arcade and retain their compatible settings.
Sound Test's Source is independent of this saved gameplay preference.

The ROM stays within the fixed 4 MiB window. Exact deduplication of fallback
sprite pens replaces 2,048 raw patterns with 1,833 unique patterns plus a code
index, saving 23,424 bytes before alignment. The full development image remains
available for the art builders; every reconstructed pattern is byte-identical.

## Gameplay track mapping

The source's ten stage callbacks at `$92E5` through `$9309` (bank 1) occur in
campaign order in the event stream at ROM offsets `$51F3` through `$6CE6`.
Their IDs are not numerically ordered. The mapping is shared by Normal, Boss
Rush and BC through the sound API, including BC's direct retrying requests.

| Event | Arcade command | HuCard command |
|---|---|---|
| Opening | 20 | 11 |
| Stages 1–9 | 21–29 | 05, 04, 02, 03, 01, 06, 07, 08, 0E |
| Final stage | 36 | 10 |
| Boss forms 1–3 | 32–34 | 12, 0E, 0C |
| Wheel boss | 35 | 0D |
| Stage clear | 2A | 0A |
| Game over | 2E | 0B |
| Ending / BC credits | 2C / FE | 0F |

`qa_hucard_music_mapping.py` validates every native command result and its
source byte sequence. Boss starts come from bank 5 `$71A7/$71B4/$71C3/$7819`,
stage clear from `$7E50`, opening from bank 0 `$F155`, game over from `$EC94`
and credits from `$EDB7`. BC retains its existing presentation/stop policy;
it uses the HuCard counterpart of the shared music event. Existing SFX and
co-op death/continue behavior remain unchanged.

## Output checks

```sh
make
make -C tests/sound_rom
.venv/bin/python tools/qa_hucard_output.py
.venv/bin/python tools/qa_hucard_output.py --pal
.venv/bin/python tools/qa_hucard_menu.py
.venv/bin/python tools/qa_hucard_music_mapping.py
.venv/bin/python tools/qa_hucard_gameplay.py --mode bc --players 4
.venv/bin/python tools/sound_test.py cmd_21 scn_sfx --no-build --music-secs 8
```

The output test runs the real native score, VInt producer, Z80 consumer and
YM2612 in Genesis Plus GX. It verifies audible output, source-rate tick counts,
track replacement, SFX coexistence, full stop and return to arcade playback,
then plays all 21 source entries. NTSC/PAL reports and a song-01 WAV are in
`.local/pce-hucard/output-qa.json` / `output-pal-qa.json` and
`native-song01.wav` / `native-song01-pal.wav`. No queue underruns were observed.
The in-game Sound Test navigation also passes with no underruns.

MAME's existing arcade comparisons pass all 1,993 ticks for music command $21
and all 2,983 ticks of the SFX/music-switch scenario. Four-player BC's real menu,
launch, every-controller pause/resume, exit/re-entry and reset regression passes.
Gameplay checks now select the saved option with real menu input, launch all
three modes at 3P/4P, fire throughout 1,800 emulated frames, check mapped track
starts and queue underruns, and exercise reset/reload plus version-4 migration.
BC additionally freezes simulation while music continues during pause.
The aggregate evidence is `.local/pce-hucard/gameplay-matrix.json` (each case
records region, party size and the tested ROM hash). This is bounded opening
coverage, not an entire-campaign performance or audio audition pass.

The 12-case gameplay matrix passes at 3P/4P on both NTSC and PAL for Normal,
BC and Boss Rush, with zero queue underruns in the measured openings. The tested
NTSC cartridge SHA-256 is
`f5721d22fdddb0721780e62d25b0a65430b9c084f42425e33866d2430fdc9f04`.
An isolated `tools/agent_build.sh hucard-gameplay-check` build produces the same
ROM byte-for-byte. Its local HuCard input is a file symlink; generated reports
stay inside the snapshot rather than writing into shared reference captures.

## Extended playback verification (October 8)

`qa_hucard_output.py --track-seconds 150` and the corresponding `--pal` run
now pass for all 21 source entries. Each track is measured for approximately
150 seconds, rather than the default 600 video frames. The test checks each
track's consumed source-clock count, queue underruns, audible output and peak
sample level. Audio is accumulated in bounded chunks so longer runs do not
retain the entire soundtrack in memory. Reports identify both the test ROM
and emulator core by SHA-256.

The NTSC run covers 192,253 total video frames, with zero underruns and a
maximum per-track clock error of 0.9385 ticks. PAL covers 160,060 frames, zero
underruns and at most 0.7861 ticks of error. Maximum measured peaks are 5,330
(NTSC) and 4,901 (PAL), below 16-bit saturation. Evidence is in
`.local/pce-hucard/output-long-qa.json` and `output-pal-long-qa.json`, with
execution logs `long-output-ntsc.log` and `long-output-pal.log`. Both runs use
the rebuilt sound test cartridge, exercising the native sequencer, VInt queue,
Z80 consumer and emulated YM2612. Instrument carrier-level and source command
mapping checks also pass.

This proves bounded extended playback reliability; it does not establish
source-equivalent timbre, exact finite-ending timing, actual register-write
equivalence, or later gameplay transition correctness. Those gates remain.

## Z80 register delivery verification (October 8)

`tools/qa_hucard_registers.py` now captures the actual MAME Z80 writes to
YM2612 alongside the 72-byte queue packet consumed by each music update.
It checks the exact ordered pitch, panning, carrier-level, multiplier, envelope,
algorithm and key-on/off writes. Interleaved Timer A acknowledgements are
checked separately. A deliberately corrupted captured pitch write is rejected.

All 21 entries pass for 12 seconds each on both Genesis NTSC and Mega Drive
PAL: 15,582 completed music updates and 659,115 matching music-register writes
per region. Four additional 150-second captures per region cover source tracks
01 (looping music), 0A (stage clear), 0B (game over) and 0F (credits). Each
contains 9,280 verified updates with no queue underruns. The clear and game-over
tracks finish with all carrier levels muted; looping music and credits remain
active. The PAL track-01 capture ends mid-transaction at its final video
boundary; only completed transactions are included in the verification totals.

Evidence: `.local/pce-hucard/registers-{ntsc,pal}/report.json` and
`registers-{ntsc,pal}-150s/report.json`, with the complete corresponding logs.
The test cartridge SHA-256 is
`27da6f24a5e68eeedb2ccfe3161e202f4d3daf64bd5763cdccbb7cd4cf6d29cb`.
These checks establish delivery of the prepared packets to the emulated chip.
They do not prove that the four-carrier synthesis sounds like the source or
that later gameplay selects the right track; those remain separate gates.

## BC stage-to-boss gameplay check (October 8)

`tools/qa_hucard_bc_transition.py --players 3` and `--players 4` pass on the
current NTSC main cartridge (`250a964f...`). The verifier selects PC Engine
music through Home Options and launches the selected party through the real
menu. Protected players allow the first stage to reach its boss naturally;
music commands, acknowledgements and boss events are not injected.

The scene's stage command 21 selects HuCard 05 and its boss command 32 selects
HuCard 12. Both tracks produce audible output, with zero queue underruns and
at most two video frames waiting for audio. Reports and boss screenshots are
in `.local/pce-hucard/bc-transition-{3,4}p/`. The completed boss audio window
occurs at measured frame 8,519 (3P) and 10,970 (4P); these are functional
transition checks, not full-speed performance results. Other stage transitions,
Normal/Boss Rush progression, and ending presentation still need verification.

## BC ending with HuCard selection (October 8)

`qa_bc_completion_scene.py --players 3 --hucard` and `--players 4 --hucard`
pass on main ROM `250a964f...`. Music is selected through Home Options;
the existing fixture starts the final round and injects final completion.
This is ending-boundary coverage, not a complete campaign playthrough.

Both parties receive their separate completion bonuses, see all 20 gallery
entries/captions and 5,760 credits updates with source-matched scroll, return
to Home and re-enter BC with the saved soundtrack. Gallery track 05 and credits
track 0F are audible, and gameplay re-entry restores track 05. No HuCard queue
underruns occur. Reports and screenshots are under
`.local/bc-completion-{3,4}p-hucard/`.

The harness now resolves a RAM symbol ahead of a same-named ROM function:
the current link map contains both a sound function `score` and BC's
`score.lto_priv.0`. Previously, its score assertions addressed unrelated RAM
using the function's low address. Gallery timing also now reports logical
updates and video frames separately. HuCard runs take 5,829 video frames for
the required 5,810 gallery updates; this small slowdown remains a performance
issue, and the reports explicitly do not claim full speed.

## Pitch-conversion cache (October 8)

The single VInt music producer now caches each voice's encoded pitch by period
and region. Repeated notes can update envelopes, panning and instruments without
repeating the 68000's expensive 32-bit pitch divisions. Period zero still means
4096, region changes invalidate the matching entry, and track changes need no
reset because cached values depend only on those two inputs. Storage is 30
bytes of static arrays. Sound data and the Z80 driver are unchanged.

`qa_hucard_fm_frames.py` independently checks all 65,536 period values, six
voices and both regions, with repeated pitch keys and changing other voice
fields: 262,144 complete packets / 1,572,864 voice outputs match the original
formula. Both 21-track NTSC/PAL output checks pass without underruns or clipping.
The four-player HuCard ending regression also passes.

The same BC first-boss audio checkpoint improves from 8,519 to 8,150 video
frames at 3P and from 10,970 to 10,687 at 4P. The gallery improves from 5,829
to 5,828 video frames for its 5,810 updates. These bounded improvements do not
close the sustained-performance gate. Baseline source/ROM and measurements are
in `.local/hucard-pitch-cache-baseline/`; comparison and build/test logs are
`.local/pce-hucard/pitch-cache-*`. Current main ROM SHA-256:
`e857146122d92b5e0aa2e26939ab7daaa6818d0a6180c1be2e8ee4c86d214f57`.

## Single-division octave selection (October 8)

On a pitch-cache miss, the converter now chooses the YM octave using the exact
minimum divisor that produces a rounded 11-bit F-number: 2,151 for NTSC and
2,171 for PAL. It shifts the divisor until that threshold or octave seven,
then divides once. The previous implementation divided at every octave step.
Clamping at octave seven and period-zero handling remain identical.

The exhaustive packet checker again passes all 262,144 frames. The same BC
first-boss checkpoint improves from 8,150 to 7,640 video frames at 3P and from
10,687 to 10,413 at 4P relative to the pitch-cache build. These measurements
still do not establish full-speed gameplay. Evidence is in
`.local/pce-hucard/pitch-threshold-*`, with the previous build retained in
`.local/hucard-pitch-threshold-baseline/`. Main ROM SHA-256:
`72a62a05ff1e9691d9c347c8f8fc6c547774b46e4c2ed7caa4e24ac592fb4ee1`.

All 21 audio entries pass NTSC and PAL output checks, and the four-player
HuCard ending regression passes. Its video-step observer now accounts for
setup and an initial credits update occurring in one video step: it checks
every subsequently observed scroll value, requires no later missing clock
values, and still requires exactly 5,760 logical credits updates. This run
samples clocks 2 through 5,759; it does not claim a direct sample of clock 1.

## Native 68000 pitch division (October 8)

The remaining cache-miss division now uses `DIVU.W` on 68000, with the portable
C expression retained for host checks. After octave selection, the divisor is
128–65,535 and the largest rounded quotient is 34,723; the 16-bit hardware
quotient cannot overflow. The helper returns its low word, discarding the
hardware remainder in the upper word.

`qa_hucard_pitch_native.py` executes the production helper on Genesis Plus GX
for every 16-bit period in both regions (131,072 cases), comparing with a table
computed using the original repeated-division algorithm. All cases pass, as
does the full portable packet checker. The fresh current-artwork baseline's
BC boss checkpoint changes from 7,628 to 7,562 frames at 3P and from 10,413 to
10,354 at 4P. This is a bounded timing improvement, not a full-speed claim.
Evidence, previous source and previous main ROM are in
`.local/hucard-native-divide-baseline/`; the native probe and report are in
`.local/hucard-pitch-native/`. Main ROM SHA-256:
`7353c6805fd03422f07066c11449486280e7c0b04f1921f2226596bc724edded`.
The rebuilt sound cartridge passes all 21 entries in NTSC and PAL, with no
queue underruns or clipped samples, including track switching and stop/resume.

## Boss Rush progression and multiplayer result-screen fix (October 8)

`qa_hucard_rush_progression.py` passes with three and four selected players.
It selects PC Engine music through Home Options, launches Boss Rush through
the real modal, and checks all 12 encounters derived from the generated arcade
timeline. Every encounter reaches its expected HuCard track and produces audio;
the clear-results screen selects track 0F, and returning to Home stops playback.
There are no queue underruns. The fixture protects players and increments the
boss-kill counter after each audio window, so it checks arena progression and
result presentation, not natural combat or the bosses' death-audio sequences.

This test exposed an actual four-player UI omission: `flow_rush_end_update`
only read the first two controllers. It now checks all selected players while
retaining the 60-update input hold. The original build reproduced P4's failure
to leave results; the repaired build verifies P3/P4 return and confirms that
unselected P4 cannot dismiss a three-player result screen. Controller inputs
are injected through the existing logical-pad fixture, not physical adapters.

Evidence: `.local/pce-hucard/rush-progression-{3,4}p/result.json`, execution logs,
and `rush-progression-4p-before-fix.log`. Main ROM SHA-256:
`9b5bfd0db4febc1e4a1768b80c80984635ce16cf20d8d326bca775f735c35475`.

## Boss defeat audio through the damage path (October 8)

The `--autohit` variant of `qa_hucard_rush_progression.py` now passes at 3P and
4P on ROM `9b5bfd0d...`. It uses the existing `boss_dbg_autohit` fixture to
supply a hit when the production collision checks allow one. Boss hit points,
bars, vulnerability, death routines and kill-counter updates are handled by
the game; the test does not write completion counters or music commands.

All 12 bosses complete through that path. All 11 non-final defeats select
HuCard clear track 0A and produce audible output through the stop/blast/clear
command sequence. Subsequent arenas select their expected tracks, and the
final clear-results screen selects track 0F. P3/P4 return to Home still works,
and no queue underruns occur. The route uses protected players and supplied
hits, so it does not establish natural combat difficulty or performance.

Evidence: `.local/pce-hucard/rush-progression-{3,4}p-autohit/result.json` and
`rush-defeat-{3,4}p.log`. This extends the earlier completion-counter fixture
with actual boss damage/death handling; it does not replace its separate
arena/result coverage or verify Normal mode's stage progression.

## Continuous Normal campaign verification (October 8)

`qa_hucard_normal_campaign.py --players 3` and `--players 4` complete the Normal
campaign on ROM `9b5bfd0d...` in 122,573 and 139,135 video frames respectively.
The fixture selects HuCard music through Home
Options and starts the selected party through the real menu. All ten timeline
sections, twelve boss defeats, the ending, and the return to Home occur through
production progression. No stage warps, music commands, or completion counters
are injected. Players are protected and boss hits use the existing assisted
hit-test fixture, so this does not establish unassisted combat or frame rate.

The opening, every stage and boss track, all eleven non-final clear jingles,
and ending track 0F produce audible output. The queue underrun counter stays
zero throughout the run. Evidence is in
`.local/pce-hucard/normal-campaign-{3,4}p/result.json` and the execution logs.

## Dense-wave instrument conversion (October 8)

Instruments 6 and 24 now use YM algorithm 6: one modulated carrier and two
additive carriers. The other 30 patches are unchanged. These two source waves
lose substantial spectral detail with four isolated sine carriers. A search
against the actual Genesis Plus GX YM core found patches whose normalized
harmonic-magnitude error falls from 0.3493 to 0.0563 and from 0.4780 to 0.0986.
This measures spectral shape, not relative harmonic phase or subjective quality.

The modulator level stays fixed while source volume/envelope/pan attenuation
scales the carriers. Silent voices still mute every operator. The 72-byte
packet carries the algorithm in the unused low bits of its pan byte; the Z80
separates algorithm register B0 from the upper pan bits written to B4. The
producer checks modulator treatment once per voice, outside the operator loop.

`qa_hucard_fm_timbre.py` checks actual chip output against the source waveform
at four attenuation levels (0, 6, 18 and 36 dB), with at least a 70% reduction
in the spectral error at every level, at most 0.386 dB loudness error, and no
channel clipping. `qa_hucard_fm_frames.py` passes all 262,144 packets across
both regions, checking the new algorithm and fixed-depth fields as well as
the existing exhaustive pitch/cache cases. The 30 additive patches pass their
separate source-power check.

The sound cartridge passes all 21 music entries in NTSC/PAL with no queue
underruns or clipped output samples, including switching, SFX, stop and Arcade
resume. All 21 NTSC register captures pass the packet-to-chip check. These
sound-cartridge checks used hash
`004d19fde0e1a70352a40f15c0854ba417c683fc1df8510b13d4f3093fbcccc9`;
the final producer-loop simplification is packet-identical under the exhaustive
host check. The main cartridge rebuild is
`cdbdc2838a1b3e02633026835cbf200cf2c8d436b2f3e664cf3ec20c77cebcb6`.
That final main cartridge passes the protected four-player BC stage-to-boss
music transition, with audible stage/boss tracks and zero queue underruns.

Evidence: `.local/hucard-timbre/`, `fm-timbre-qa.json`, the output/register
reports under `.local/pce-hucard/`, and the isolated source/before/after audio
page at `.local/hucard-timbre/audition/index.html`. The probe uses the core's
[documented YM entry points](https://github.com/ekeeke/Genesis-Plus-GX/blob/master/core/sound/ym2612.h)
and enhanced precision to separate patch synthesis from DAC quantization.
Listening review and phase fidelity remain unverified.

## Continuous BC campaigns and audio teardown (October 8)

`qa_bc_campaign_pilot.py --home --protect --turret-lanes --hucard --updates
180000` completes all ten rounds with three and four players on ROM
`cdbdc283...`. The pilot supplies controller movement/fire; protection is the
only gameplay assist. It does not inject boss defeats, stage completion,
health, weapons, or music commands. The three-player run takes 114,811 gameplay
updates and 184,099 video frames including the ending; four-player takes
123,407 updates and 222,217 video frames. These are progression checks, not
full-speed or unassisted-combat claims.

The new `hucard_campaign_monitor.py` observes each actual video frame. Both
runs pass round-specific source-command/track checks and audible windows for
every stage, including real boss/clear transitions, the final clear, gallery
and credits. They reach the 5,760-update credits end and return to Home. No
queue underruns occur. Evidence is in
`.local/pce-hucard/bc-campaign-{3,4}p/{result,hucard-audio}.json`.

These traces exposed missing session cleanup: HuCard playback remained active
after Home return. The strengthened `qa_bc_completion_scene.py --hucard`
reproduced this on the old ROM. `flow_session_prepare` now stops all sound when
releasing BC, covering completion, game-over return and reset. The rebuilt ROM
`49c717da9da0badd61c759ccfd7b0470675cc88ca67ced8d145341172c3b4eb1`
passes the 3P/4P ending fixtures, including the new stopped-playback assertion
and re-entry music, and the 4P menu/pause/return/soft-reset regression.
Logs: `bc-exit-before-fix.log`, `bc-exit-fixed-{3,4}p.log`, and
`bc-exit-fixed-menu.log` under `.local/pce-hucard/`.

The full-campaign observations precede this teardown-only fix. The ending and
session regressions test the repaired handoff directly; they do not constitute
a second complete campaign on the new hash. Future `--hucard` campaign runs
also assert that playback is inactive on final Home return.

## Remaining implementation and release gates

The subsequent `2c3fed51...` cartridge completes protected 3P/4P BC campaigns
with all imported PCE bosses, all required audible music transitions, gallery,
credits and Home audio cleanup. The assisted 4P Normal campaign also completes.
Exact hashes, counts, assist scope and evidence directories are recorded in
`expansion-acceptance.md` under "Complete campaign checks after all PCE boss
imports". The later `a29a9a2d...` build changes only a player entry-pose byte and
checksum; those campaign results retain their actual tested hash.

### Current gameplay cartridge audio regression

ROM `548a830328c7db8969cae337435c23fc15f33407a7ac0d6a20f3a4dc284ee03a`
passes `qa_hucard_main_output.py` in NTSC and with `--pal`. Unlike the sound
test cartridge checks, this enters the actual game's Sound Test using controller
input and plays all 21 selections. Each is measured for 600 video frames:
audible output, no clipping, source-rate timer error below two ticks, and zero
queue underruns. STOP produces silence; switching source resumes Arcade music;
Back returns to Options. PAL uses a local region-header copy and records both
the shipping and tested hashes. Reports are under
`.local/pce-hucard/main-output-{ntsc,pal}/result.json`.

On this same shipping ROM, `qa_hucard_gameplay.py --players 4` passes separately
for Normal, BC and Rush: real Home selection/launch, 1,800 gameplay video
frames, expected tracks, zero underruns, saved settings after reset and
version-four save migration. BC pause freezes gameplay while audio continues.
`qa_bc_completion_scene.py --players 4 --hucard` also passes audible gallery
and credits, Home audio cleanup and re-entry. This ending fixture injects
completion; it is not a new full-campaign playthrough. These checks establish
current-cartridge audio delivery, not subjective instrument fidelity.

1. Audition source/converted audio, including the improved dense-wave patches.
   Packet-to-chip writes now pass the checks above, including bounded longer
   loops and finite endings. Source-to-synthesis fidelity still needs work;
   audible output and correct register delivery do not prove timbre fidelity.
2. Normal and BC three/four-player campaign soundtrack paths and Boss Rush
   defeat audio now pass the protected/assisted checks above. Preserve those
   results through remaining changes, and continue checking cartridge size.
3. Finish the expansion's separate BC art matching and performance gates.

HuCard music is now available in gameplay and Sound Test. The expansion still
has the synthesis, artwork and performance gates above; it is not complete.


## Listening comparison on the October 8 cartridge

The local `.local/hucard-audio-review/index.html` provides all 21 Sound Test
selections as original PCE / current Genesis pairs. Eighteen distinct source
commands were recorded through MAME's original HuCard driver; aliases 08, 13
and 14 reference command 04. The 922 captured driver states for each command
match the corresponding earlier reference capture (16,596 states, zero
mismatches). These are sound-command fixtures, not recorded playthroughs.

Genesis clips come from actual controller-driven Sound Test on ROM
`62e6af760aa88f11df9466d66590c97c0c2d2d59ee254ce1479dc76bf264022f`.
Both NTSC and PAL pass all 21 selections, clock-error/queue checks, STOP silence,
Arcade-source resumption and Back. Reports are in
`.local/pce-hucard/audition-genesis{-pal,}-v1` (NTSC: `audition-genesis-v1`;
PAL: `audition-genesis-pal-v1`). No shipping ROM bytes changed for this work.

The page offers original levels and constant-gain level matching (-20 dBFS RMS,
limited to -1 dBFS peak). No EQ/compression is applied. Start alignment uses
playback-request timing and is approximate, not sample/phase alignment. All 84
WAVs have valid stereo headers, matching durations and no clipping. The page's
control logic passes A/B position, gain switching and exclusive-player tests;
this is not a claim of browser listening or subjective timbre acceptance.

Reproduce with `tools/capture_hucard_audio_set.py`, then
`tools/qa_hucard_main_output.py --audio --output .local/pce-hucard/audition-genesis-v1`,
and `tools/build_hucard_audio_review.py`. Run `node tools/qa_hucard_audio_review.cjs`
for control-logic checks. Listening assessment remains open.

## Packet-copy performance and combined BC timing (October 8)

The BC timing fixtures now have `--hucard`, selecting the soundtrack through
Home Options before starting the native scene. The older default matrices use
Arcade music. The new uninstrumented 20-sample baseline (3P/4P, all ten rounds,
300 warmup / 600 measured updates) is `.local/bc-hucard-opening-timing/` on
`ef853ea841cbffda4b71419cbbcd8eb72aae16c4da3a9e75f54c181efad56b78`.
It takes 17,763 video frames for 12,000 updates, with no audio underruns.
The Home menu configuration differs from the default debug-entry fixture, so
cross-source timing differences are not a controlled music-only comparison.

The R6/4P instruction profile attributes 14.03% of measured CPU time to
`sound_vint.part.0`; its three largest packet-copy instructions total over
16 million master-clock ticks. `sound.c` now publishes a fixed 72-byte packet
with eight byte writes per DBRA group. It retains byte-only Z80 RAM access,
the bus handshake, queue publication order, producer score, synthesis and
independent playback clock. Generic driver uploads are unchanged.

Accepted ROM: `33b49362df200d9740a92d358aee011366e92a57e39156f489d5c9d5813b5cfa`.
The same twenty HuCard workloads take 17,447 frames, a net saving of 316;
nineteen improve and R2/3P regresses by one frame. Every Arcade-music sample
matches the previous accepted 20-sample matrix (13,101 total frames).
Instrumented R6/4P takes 1,158 versus 1,161 frames and matches all 600 state and
workload records plus 599 post-flush VDP records. The one late flush ends at
scanline 253. These bounded protected fixtures still fail the full-speed gate.

Actual Sound Test checks pass all 21 tracks in both NTSC and PAL: clocks,
audibility, no peak clipping, no queue underruns, STOP silence and Arcade
restoration. Added exact producer-buffer versus last-published Z80-slot checks
pass 420 times per region and cover all four ring slots. Subjective timbre
acceptance remains open. Evidence: `.local/hucard-packet-copy/`; CPU attribution
and disassembly: `.local/bc-hucard-cpu-audit/`.

## Rejected voice cache / FM outlining trials (October 8)

Examined unchanged FM inputs over 1,200 score ticks for all 21 selections:
57,322 of 151,200 voice observations repeat the complete pitch/volume/pan/
instrument tuple. Excluding pitch raises repeat rates to 4,950/7,200 for song
6 and 6,483/7,200 for song 16. Tested a per-channel cache for the nine non-pitch
packet bytes; the first candidate passes the mathematical host check for all
65,536 pitch inputs, both regions and changed envelopes (262,144 frames,
1,572,864 voices).

It cannot be retained within the cartridge layout: the aligned sound-data bank
moves from 0x2c0000 to 0x2c8000, and text ends at 0x407224, beyond the 4 MiB
window. Preventing loop unrolling, outlining the cached converter, using a
zero-initialized invalid key, and outlining the original uncached converter
also exceed the limit. No native performance benefit was measured or claimed.

Restored source and rebuilt ROM exactly match retained
`33b49362df200d9740a92d358aee011366e92a57e39156f489d5c9d5813b5cfa`.
Evidence: `.local/hucard-voice-cache/`, including rejected sources, build logs,
input-reuse counts, host result, and restoration report. Further audio work
must account for the pre-bank alignment boundary or reduce code/data first;
the apparent free bytes at the end of the cartridge alone are insufficient.

## ROM layout headroom recovered (October 8)

`build_assets.py` formerly aligned every zone map, attribute table and palette
to 512 bytes. These are CPU-read data: background/parallax code reads maps and
attributes, and `pal_load` copies palette words into RAM before DMA. They now
follow the DMA blobs as one word-aligned metadata group. All other resources,
including star-map DMA, sprite banks and graphics, retain 512-byte alignment.
The 64 KiB sound data remains 32 KiB aligned at 0x2c0000.

This packs out 23,552 bytes of scattered padding and leaves that space before
the sound bank, so small code growth need not immediately push the bank 32 KiB
later. The finalized cartridge remains 4 MiB; _etext remains 0x3ff224. Every
one of 163 linked blobs (2,431,868 bytes) matches its generated binary and the
previous ROM byte-for-byte. No asset or soundtrack data is removed.

Accepted ROM `a9736b57ac0fcab814aa022a29a55e7593df8090e196183203a7fd2afebc026f`:
ten Normal 4P sections retain all6,010 state/sprite records and timings across
6,000 updates; independent one-player checks match1,200 full video-memory
snapshots across ten sections. All 20 BC HuCard opening timings remain identical,
with active audio and no queue underruns. Evidence `.local/rom-metadata-packing/`.
This enables renewed optimization trials; it does not itself improve speed.

## Timbre packet cache retained after metadata packing (October 8)

The recovered pre-bank headroom permits the previously oversized timbre cache.
`hucard_fm_frame` caches the nine packet bytes determined only by volume, pan
and instrument; pitch and region retain their independent cache. The extra
state is 72 RAM bytes. A volume/pan key plus one makes zero an invalid initial
key for the source's 0..31 volume range. Every destination byte is still written,
including repeated calls with a different output buffer. The algorithm-six
modulator exception remains part of the cached result; score/clock behavior
is unchanged. Stop/start needs no invalidation because output depends only on
these complete input keys and the fixed patch tables.

The expanded mathematical check passes 524,288 frames / 3,145,728 voices over
all 65,536 periods and both regions, changing envelopes and poisoned alternate
outputs. Actual cartridge Sound Test passes all21 selections in NTSC/PAL,
including840 exact published-packet comparisons spanning all four queue slots,
zero underruns, correct playback clocks, STOP silence and Arcade restoration.

HuCard20 timing improves17447->17003 video frames for12000updates;19 samples
improve and R1/3P regresses603->605. Arcade20 remains13101 unchanged. R6/4P
instrumented1158->1145 matches600state/workload and599VDP records, with two
late flushes ending no later than scanline257. Four-player990-update controls,
respawn and Home/reentry pass with zero renderer drops/remaps. These protected
samples remain below full speed and do not establish full-campaign acceptance.

Accepted ROM `8746a25a7b57459e4c233aeac0b3f7cf4305427d36e236c03e0f240459b01b23`;
4MiB, sound bank0x2c0000. Evidence `.local/hucard-timbre-cache/`. This supersedes
the size-only rejection for this cache under the former asset layout.

## Direct active-stream check and sustained measurement (October 8)

After caching, a fresh R6/4P profile still attributes12.51% of measured cycles
to sound_vint. Its score-stream zero test unnecessarily assembled an offset
using a long shift. `hucard_score.c` now tests `(c[0] | c[1])` directly; generated
68000 code removes the shift and integer test while preserving active/inactive
semantics. Actual source-score comparison passes166377ticks over18distinct
tracks plus the established3aliases.

Accepted ROM `0156af010096b01d74ef8166e74d396601ce4bc66945d11e44d13b272512e9af`.
HuCard20 improves17003->16874frames (net129saved), with R1/3P+1,R3/3P+1,
R6/4P+2,R8/4P+3. Arcade20 remains unchanged. Instrumented R6/4P matches600
state/workload and599VDP records, but its timing gate fails1145->1147; that
failure is retained in the evidence. There are no late-blank flushes in this
candidate sample. The longer protected6,000-update R6-start run improves
11165->11150video frames, stays active through boss music and has no underruns.
It measures about54% simulation speed; neither sample proves full-speed play.

NTSC/PAL all21 actual SoundTest tracks pass840exact published-packet checks,
clock/audibility/peak/queue/STOP/Arcade restoration. Evidence is
`.local/hucard-stream-active/`, with the prior long run and updated CPU profile
in `.local/hucard-timbre-cache/`. Retained for net timing gains despite the
explicit short-sample regressions; ROM remains4MiB.

## Pitch-table trial held back by VBlank timing gate (October 8)

A candidate replaced division for periods1..4096 with exact NTSC/PAL lookup
values, retaining arithmetic for the rest of the16-bit range. The16KiB assembly
table fits before the sound bank; cartridge remains4MiB. All8192 linked words
match the prior formula. Host comparison passes524288frames/3145728voices,
including table/fallback/region and cached-output paths. Actual21-track tests
pass in both regions, with840packet checks and no clock/queue/STOP failures.

Candidate `cc14e947097091dff7103f31558a6723fbe4f4505691ddd330a56ffde31b5111`
improves HuCard20 from16874 to16556frames and the6000-update R6-start run from
11150 to11085. However, R6's scheduler safety gate fails at tick654: a200-byte,
one-operation queue enters SYS_doVBlankProcessEx at physical scanline255 and
returns at3, with unchanged vtimer3950. All600state/workload and599VDP snapshots
match, but matching final video memory does not prove safe raster timing.
The monitor covers the whole process, including callbacks and JOY_update;
individual VDP-write timing has not yet been isolated.

The trial is not retained pending that diagnosis. Source and rebuilt cartridge
are restored byte-for-byte to
`0156af010096b01d74ef8166e74d396601ce4bc66945d11e44d13b272512e9af`.
Evidence, candidate sources/ROM/symbols/table, the failed gate and restored
identity: `.local/hucard-pitch-table/`. No scheduler guard was weakened.

## Direct memory voice copy rejected (October 9)

Trial `eff83e17fbaa978f6f3737e552c5c32ee80330731134c15570c16ff3efeb7cf6`
replaced the aligned voice packet's six register-mediated MOVE instructions
with three memory-to-memory MOVE instructions. Odd destinations, cache keys,
score timing and byte-only Z80 publication were unchanged. A native 68000 probe
passed 16,384 packets including aligned/odd buffers, poisoned repeat outputs
and surrounding sentinels.

Four-player HuCard fixtures (300 warmup, 600 measured updates) preserve every
simulation state and workload record, but R2 regresses from 735 to 744 video
frames; R8 remains 1,005. Mean scene ticks rise from 664,649.3 to 665,623.99
and 886,474.19 to 887,082.02 respectively. This instruction simplification
therefore does not establish a whole-game performance benefit and is rejected.
Evidence, candidate and baseline are in `.local/hucard-direct-copy/`.

## Precise voice-copy memory operands rejected (October 9)

Trial `d2d7f359b158e7773436539a0b15db867fa0def7b6a5c39a1485ac48aae1cb99`
retains the original six native copy instructions, declaring their exact
12-byte source and destination instead of a global memory clobber. This
allows the compiler to retain unrelated cache state across each voice copy.
The native probe passes 16,384 packets across aligned/odd destinations and
poisoned repeat outputs. Both 600-update R2/R8 four-player HuCard fixtures
preserve all simulation states and workloads. R2 stays 735 video frames;
R8 changes 1,005 to 1,006 despite a lower mean scene cost.

A longer 3,000-update R8 control confirms the mixed result: scene mean falls
1,010,949.92 to 1,008,326.62 core ticks, but total video frames rise 5,660 to
5,667. Every state and workload record still matches. Reject this trial:
reduced isolated CPU attribution does not establish faster gameplay. Archived
source, ROM, native probe, disassembly and timing comparisons are under
`.local/hucard-copy-operands/`. No gameplay, score or queue rules were changed.

## Current-build audio verification and next instrument fit

Build `46463dfb88f8fc3b21844c5222eb0e3e3534065b2ce37a10db2fd8f4c3ae646a`
passes all 21 Sound Test tracks in NTSC and the PAL-region test variant, with
zero underruns and 420 packet checks per region across all four ring slots.
Stop silence, Arcade resume and return to Options pass. The PAL fixture changes
the region header; its tested hash is recorded separately. Evidence:
`.local/4646-campaigns/audio-{ntsc,pal}/result.json`.

An isolated audit of all 32 generated patches at four attenuation levels
identifies instrument 21 as the largest remaining harmonic-magnitude mismatch.
An offline algorithm-6 fit reduces its normalized squared spectral error from
0.314803 to 0.087578 at full level (72.2%), and preserves that improvement at
6/18/36 dB attenuation. Absolute loudness error stays below 0.227 dB, with no
channel clipping in these samples. Proposed multipliers are `[1,2,3,1]` and
levels `[8,36,22,19]`. This fit is **not integrated** into the campaign ROM.
These enhanced-precision YM measurements do not establish phase fidelity or
subjective quality; production packet/output and gameplay timing checks must
follow integration. Evidence: `.local/hucard-spectrum-audit/result.json` and
`candidate21.json`.

The instrument21 fit is now compiled in trial `0a981d93...`, pending rebuild
reproducibility and retention. Reachable score operands are zero-based; adding
one maps operand20 to voice instrument21 in the ending track. Its first use
occurs after the normal ten-second Sound Test sample, so the verifier now has
optional single-track/longer-duration controls and explicitly sampled active
instrument counts. A 9,000-frame ending run sees 127 active instrument21
samples, 9,293 score ticks and zero underruns. Before/after audio is identical
until 81.387 seconds. All 21 short-track NTSC/PAL audio metrics match, and both
3P/4P ending fixtures match every reported field except ROM hash. Packet tests
and the generalized nonlinear-patch verification pass. Exactly ten ROM bytes
change, confined to the patch, algorithm byte and header checksum; symbol
layout is identical. `.local/hucard-spectrum-audit/validation-summary.json`
records the limits, including no subjective listening or phase-fidelity claim.
The unchanged-volume 12-second audition excerpts are in `audition/index.html`.

Instrument21 is now retained in `0a981d93...`: full make reproduces the exact
cartridge after the validation above. Full current-hash campaigns are running
under `.local/0a98-campaigns`. The preceding 4646 test package remains available.
A separate offline algorithm6 search for the next weakest reachable instruments
1 and 2 did not meet the existing 70% magnitude-error improvement gate; the
normalized instrument1 fit also exceeded the 0.6 dB low-level error limit.
Neither is integrated. The unchanged searches need not be repeated; results
and their bounded scope are in `used-search-rejected.json`.

## Retained packed stereo/level table (October 9)

The FM renderer uses a 512-byte table containing the original louder-side
pan level and YM stereo bits. It changes no source pan curve or carrier levels.
`qa_hucard_pan_table.py` checks the linked table for all 256 pan values and 8,192
volume/pan pairs; `qa_hucard_fm_frames.py` also passes 524,288 packets with changing
pitch, instruments and envelopes. Actual-cartridge Sound Test passes all 21
tracks in both regions, with zero underruns and correct stop/Arcade return.
Evidence: `.local/hucard-pan-table/`. All six protected/assisted campaigns have
passed, and the full rebuild and packaged test ROM match exactly. Native scene-cost
improvements are modest and do not establish full-speed gameplay.

## Deferred envelope address calculation (October 9)

The sequencer preserves instrument selection on every source step, but computes
its envelope address only when a note or active envelope consumes it. The phase-4
silent envelope remains a no-op. Captured source comparison passes all 166,377
ticks and three aliases. Current-ROM NTSC/PAL output passes all 21 tracks, and
all six protected/assisted campaigns finish without HuCard underruns. Full-make
reproduction and the local test archive are verified. Evidence:
`.local/hucard-lazy-envelope/`. Measured CPU costs fall in each bounded route;
this does not establish full-speed gameplay or subjective timbre acceptance.

## Native internal channel words (October 9)

Each channel has 23 logical bytes plus one padding byte. Stream offsets and
periods use aligned big-endian words internally; original score operands remain
little-endian and may be unaligned. The score state grows by six bytes. Source
QA normalizes only the two word pairs and separately checks padding. Native QA
covers all 65,536 values at three aligned offsets, with read/write, unsigned
extension and sentinel checks. All original source ticks, both-region track
output checks, six protected/assisted campaigns, bounded paired stack replay
and exact rebuild pass. Evidence: `.local/hucard-native-channel/`.
Do not interpret raw internal channel word bytes as the original capture layout.
The change improves bounded performance, not full-speed release acceptance.

## Retained grouped voice cache (527bfe25)

The FM renderer stores each voice's cached pitch, timbre and complete packet in
an aligned 20-byte record (120 bytes total). Sequential voice traversal reduces
address calculations without changing synthesis or Z80 publication. Native
checks cover 16,384 packets with aligned/odd and poisoned repeated destinations;
host checks cover 524,288 packets. All 21 tracks pass NTSC/PAL output checks,
and six protected/assisted campaigns plus the exact full rebuild pass. Evidence:
`.local/hucard-voice-cache-layout/accepted.json`. This is a retained optimization,
not a completed listening, full-speed or physical-hardware acceptance gate.

## Retained active-channel word check (376abb8b)

The sequencer checks activity through its existing aligned native-word accessor
instead of OR-ing two bytes. Source capture and native helper checks pass;
all six protected/assisted campaigns, 21 tracks in both regions and the exact
full rebuild pass. R7 long improves modestly, while R6 and solo frame counts
regress slightly; see `.local/hucard-active-word/accepted.json` and
`comparison.json` for the measured limits. This does not close release gates.

## Instrument2 feedback patch retained (October9)

Retained8d5e4ffc uses algorithm5/feedback7 for instrument2. Its multipliers
are3/5/3/4 and levels39/32/18/24. All four tested attenuation levels exceed
the existing70% harmonic-error reduction gate and remain within0.44dB of
source loudness. A harmonic-energy check rules out off-harmonic noise hiding
behind normalized magnitude scores. The HuCard Z80 path now writes B0's six
algorithm/feedback bits; the68000 preserves the modulator level for supported
nonlinear patches. Main and sound-test cartridges share the same driver/patch
bytes, and actual MAME register traces include the feedback bits. Native NTSC
and PAL tracks, packet checks and all12 campaign/regression jobs pass. Bounded
3P/4P gameplay state/workload comparisons match8600 updates, with a small
0.02–0.054% scene CPU increase. Full pilot campaign duration is not a matched
performance measure because completion ticks differ. See expansion-acceptance.md
and `.local/hucard-alg5-study/` for scope and the verified test package. This
does not establish subjective timbre or phase fidelity.
