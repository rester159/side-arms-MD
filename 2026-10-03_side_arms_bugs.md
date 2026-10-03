# Side Arms — itch.io bug follow-up, 2026-10-03

Source: https://rester159.itch.io/side-arms#comments (read 2026-10-03).
Target: the reported v1.0 problems. Existing multiplayer / Before Christ work is
outside this fix scope. Hardware reports remain open until the affected machines
are retested; emulator passes alone cannot certify them.

## Reported bugs

| ID | Report and source | Fix / investigation plan | Test / acceptance plan |
| --- | --- | --- | --- |
| B01 | EverDrive launch fails: jackic, original V1 (two units), https://itch.io/post/17493833; SleepingGiant-b0r3d, EverDrive v3 on PAL Model V4 with region mod, blue screen in NTSC/region-free and freezes at TMSS in PAL, https://itch.io/post/17494952; ravage1974 corrects the initial report: X3 fails, Mega SD works, https://itch.io/post/17507205. | Audit the released header, reset path, SRAM mapping and intro initialization. Reproduce flash-cart-like entry with dirty work RAM and configured controller ports. Correct demonstrated boot defects and validate cartridge metadata. | Compare baseline/fixed boot with clean and dirty startup state; cold and reset boot; NTSC/PAL; SRAM save/reload. Inspect boot/menu images. Affected EverDrive models still need physical retest. |
| B02 | patrickf56: MiSTer FPGA displays a white screen, https://itch.io/post/17507114. | Share boot investigation with B01, keeping MiSTer a separate validation target; do not assume the same cause without evidence. | Same emulator boot matrix and header validation; MiSTer core/version/settings and retest needed to close the hardware report. |
| B03 | Zanac28 and ravage1974: music overwhelms SFX in v1.0; latter tested PicoDrive and Mega SD (corrected), https://itch.io/post/17504522 and https://itch.io/post/17506599. | Reduce music output at FM carrier operators only, preserving modulation, pitch, timing and PSG effects. Measure before/after audio and check every patch. | Check carrier attenuation/clamping for all algorithms; unchanged modulators and SFX; compare isolated music/SFX audio; run music/priority/SFX regression in NTSC/PAL. Listening and affected hardware feedback remain subjective validation. |
| B04 | Jankins97: music sometimes briefly speeds up or stutters; platform unspecified, https://itch.io/post/17491993. | Audit Timer A polling, YM writes and game sound commands; reproduce timing bursts and correct any demonstrated clock/register defect. | Stress music + effects, song changes and priority transitions; measure tick rate, polling gaps and lateness; verify no musical event changes. Record whether the reported symptom is reproduced rather than claiming hardware certainty. |

## Execution plan

1. Preserve baseline ROM/data; inspect startup and audio paths before editing.
2. Add focused regressions that exercise the demonstrated defects.
3. Apply fixes, build in an isolated local snapshot to avoid colliding with ongoing work,
   and run the planned checks. Keep commands, results and limitations below.
4. Write an itch.io post describing only verified changes and asking for the remaining
   hardware retests. A draft does not imply that a new download has been published.

## Other feedback

Before Christ mode and requests for other ports are feature requests, not bugs.
The requested turbo option already exists as per-button autofire under Home controls;
mention where to find it in the post. Community discussion without a reproducible
technical report is not included as a defect.

## Fixes and current status

### B01 / B02: startup and cartridge metadata

The v1.0 binary and the pre-fix workspace binary both contain SGDK's controller-port
test before TMSS: nonzero `$A10008` / `$A1000C` branches to `_reset_entry`, which
does not initialize this game's RAM/data. A flash-cart menu can leave these ports
configured. With work RAM filled with `$A5` and those ports set, the baseline never
entered the game loop: `flow_state = 0xA5A5A5A5`, zero updates, sound not ready.

`tools/cart_boot.py` removes that heuristic from the installed SGDK startup during
assembly. Every launch/reset now checks TMSS and takes full initialization. The rest
of SGDK's vectors/interrupt code is retained. The script fails on an unfamiliar
startup source instead of silently applying a guessed patch. The normal Makefile
and snapshot builder both include `tools/cart_boot.mk`; the shared SDK is untouched.

The SRAM header now declares odd-byte storage at `$200001-$20FFFF`, matching the
actual save accessors. The finalizer rejects the old even-start declaration as well
as an SSF mapper header. The v1.0 console name/checksum were already correct, so the
previously documented SSF issue was not treated as this release's root cause.

**Status:** demonstrated startup defect fixed; emulator matrix passes. The reported
EverDrive V1/v3/X3 and MiSTer failures remain **awaiting device retest**. In particular,
the MiSTer white screen has not been reproduced on a MiSTer and cannot be closed on
emulator evidence alone. The author's test hardware/core versions were not supplied.

### B03: music/effect balance

`tools/build_sound.py` adds 16 total-level steps to music carrier operators only
(nominal 12 dB attenuation), saturating at 127. All eight algorithm topologies are
covered; modulator levels, envelopes, pitches, musical events and SFX frames are
unchanged. The measured mix reduction differs from the nominal operator setting.

Genesis Plus GX, equal 600-frame captures through the complete game driver:

| Capture | Before RMS dBFS | Final RMS dBFS | Difference |
| --- | ---: | ---: | ---: |
| Stage music `$21` | -6.91 | -15.18 | -8.27 dB |
| Isolated effect `$0C` | -30.10 | -30.24 | -0.14 dB |
| Music + repeated `$0C` | -6.84 | -14.71 | -7.87 dB |

These are DC-removed whole-capture measurements at the core's reported 44.1 kHz,
not perceived-loudness certification. SFX register states are checked against the
reference at each driver tick; the faster driver changes wall-time placement and
noise phase, so final WAV files are not expected to be byte-identical.

**Status:** adjusted and regression-tested; PicoDrive/Mega SD and listener feedback
are still needed to judge the preferred balance on those setups.

### B04: sound processing backlog during combat

The standalone jukebox passed, but a full-game stress run reproduced a distinct
timing problem. In section 9 with 1P continuous AUTO fire, the pre-fix workspace ROM
produced 229–272 sound ticks per 60 video frames, up to 12 in a single frame, and
67 pending half-ticks (roughly 135 ms). Section 1 reached 187 pending half-ticks.
Sound work was falling behind and later catching up. This is consistent with the
report, although the comment did not specify a platform or reproduction route.

Changes in `src/sound/sa_sound_drv.s80`:

- Reuse each chip's selected effect slot instead of searching twice per tick.
- Clear lower priorities only after a command could have activated one. Preserve
  the fallback search when the selected effect ends.
- Precompute exact PSG pitch conversion for every 12-bit period in both regions,
  using previously unused space in the existing SFX bank. No extra ROM bank and
  no pitch approximation. Remove the now-unnecessary period cache/arithmetic.
- Upload instrument registers with a shorter burst loop, retaining busy checks and
  safe spacing between YM address/data writes.

Final 3,000-frame samples (50 seconds each), with an invincible AUTO-fire bot:

| Players / section | Sound ticks / 60 video frames | Max pending half-ticks | Max consecutive frames with no sound tick |
| --- | --- | ---: | ---: |
| 1P / 1 | 249–250 | 4 | 0 |
| 1P / 9 | 246–250 | 4 | 1 |
| 2P / 1 | 248–250 | 5 | 0 |
| 2P / 9 | 245–250 | 4 | 1 |

The regression rejects three consecutive frozen sound frames, more than 16 pending
half-ticks (about 32 ms), or a 60-frame window outside 240–260 ticks. All four final
samples pass without relaxing these limits. Music/SFX sequencing is not skipped
to meet the timing budget. Short DMA/transition delays remain; this is not a claim
of zero jitter or whole-game 60 fps. The 2P section-9 sample had 2,903 gameplay
updates in 3,000 video frames, while the sound clock continued near its target rate.

**Status:** reproduced combat backlog fixed in the tested scenes. The original
reporter should still retest their setup and provide a recording if the symptom remains.

## Test record and reproduction

The build uses an isolated snapshot at `.local/build-itch-bugs`, preserving existing
multiplayer / Before Christ work in the main checkout. It is a development candidate
from that workspace, not a clean v1.0-only release branch. Root `out/` and the public
v1.0 download have not been replaced.

- Fresh full snapshot build completed with no compiler warnings in `src/` or `inc/`.
  Make emits the expected recipe-override notices for the project boot adaptation.
- Startup: **8/8 pass** — PAL/NTSC × clean/dirty initial state × launch/reset.
  Every case reached mode select, completed 120/120 observed game updates, and
  reported a ready sound driver. PAL dirty-reset and 2P gameplay images inspected.
- Home gameplay/save tests: **1P and 2P pass** — menus, normal waves, team start,
  Boss Rush, SRAM persistence across reset, and version-3 save migration.
- Data checks: **32 patches, eight FM algorithms including saturation, 8,192 period
  table entries pass**. Entire data blob checked against baseline: only carrier
  levels and the added period tables differ; music event streams/SFX frames are identical.
- Negative build checks: unrecognized SDK startup, SSF header and even-start SRAM
  header are rejected. Python syntax and changed-file whitespace checks pass.
- Gameplay sound-clock stress: **4/4 pass**, as listed above.
- Final sound suite: **57/57 cases per region, 114/114 total**. This includes all
  27 effects, 25 music tracks, four multi-command scenarios, and the 68000 API test.
  NTSC: 931,734 compared ticks; PAL: 931,941. No unexpected FM or PSG state mismatch,
  all commands on their expected ticks, and all 11 API commands delivered in order.
  Maximum status-read gap: 1.491 ms NTSC / 1.509 ms PAL, below the 2 ms limit.
  The test cartridge's assembled driver and data were compared byte-for-byte with
  those in the full-game candidate.
- The added dense-combat scenario still has transient lateness: maximum 8.39 ms
  NTSC / 28.27 ms PAL. The severe accumulating backlog is resolved in the sampled
  gameplay scenes, but **zero audio jitter is not established**. This residual and
  the unspecified reporter platform are reasons to request another listening test.

Test ROM: `dist/side-arms-md-2026-10-03-bugfix-test.bin` (3,014,656 bytes).
SHA-256: `fea50ed195c2746c0951cc7c2675129ebf360536be6e548cf74d9287192c0483`.
This is the exact tested snapshot, retained for hardware follow-up; the original
`dist/side-arms-md-v1.0.bin` is preserved.

Commands (run from the repository; use a fresh process per boot/audio case):

```sh
make -C .local/build-itch-bugs
.venv/bin/python tools/qa_itch_sound_data.py --baseline .local/itch-bugs-baseline/sound_z80.bin
.venv/bin/python tools/qa_itch_boot.py --rom .local/build-itch-bugs/out/release/rom.bin --region E --dirty --reset
# Repeat boot command with U/E, with/without --dirty, and with/without --reset.
SIDEARMS_BUILD="$PWD/.local/build-itch-bugs" .venv/bin/python tools/qa_multiplayer.py --players 1
SIDEARMS_BUILD="$PWD/.local/build-itch-bugs" .venv/bin/python tools/qa_multiplayer.py --players 2
SIDEARMS_BUILD="$PWD/.local/build-itch-bugs" .venv/bin/python tools/qa_itch_clock.py --players 2 --section 8
# Repeat clock test for 1P/2P and zero-based sections 0/8.
.venv/bin/python tools/qa_itch_audio.py --rom .local/build-itch-bugs/out/release/rom.bin --output reports/itch-bugs/audio
.venv/bin/python tools/sound_test.py --jobs 6
.venv/bin/python tools/sound_test.py --no-build --pal --jobs 6
```

Local evidence: `reports/itch-bugs/` (boot images/results, gameplay/clock results,
audio WAVs and metrics); full sound-register logs under `reports/sound_port/`.
Baseline ROM, driver, sound data, failed boot result and audio are preserved in
`.local/itch-bugs-baseline/`. These generated/local artifacts are intentionally ignored by Git.

The itch.io draft is `2026-10-03_side_arms_itch_post.txt`. It describes a local test
build and requests device retesting; no post or ROM has been published by this task.
