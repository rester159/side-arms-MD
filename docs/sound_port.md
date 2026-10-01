# Side Arms MD — sound driver (native Genesis design)

An original Genesis sound driver: music on the YM2612, SFX on the SN76489 PSG. The arcade sound program
(audiocpu `a_04k.rom`) is used only as a **behavioural spec** (`docs/re/sound.md`); its code structure, RAM
layout and byte code are not reused. Where an arcade rule is reproduced, the source cites it as `spec $xxxx`.

| file | role |
|---|---|
| `tools/build_sound.py` | compiler: `res/generated/sound.json` → native data (`res/generated/sound_z80.bin`, `src/gen/sound_data.s`) |
| `src/sound/sa_sound_drv.s80` | Z80 player (sjasm → 68000 symbol `sa_sound_drv`, padded to 5 KB) |
| `src/sound/sound.c`, `inc/sound.h` | 68000 API |
| `tools/sound_model.py` | reference model of the PSG voice reduction (used by the verifier) |
| `tools/sound_test.py`, `tools/sound_test.lua`, `tools/re_sound_seq.lua` | verification against the arcade (MAME), second emulator (Genesis Plus GX) |
| `tests/sound_rom/` | standalone sound-test cartridge (driver + data + jukebox) |

Nothing ROM-derived is committed; `make` runs `tools/build_sound.py` in its `assets` step (it runs
`tools/extract_sound.py` first if `sound.json` is missing). `tools/agent_build.sh sound` builds a private copy.

## API (`inc/sound.h`, unchanged)

```c
void sound_init(void);        // load + start the Z80 driver (resets YM2612 and PSG)
void sound_command(u8 cmd);   // queue one command, arcade latch numbering; non-blocking
void sound_stop_all(void);    // = sound_command(0x00)
```

Commands: `$00` stop all, `$01-$1E` SFX (`$10 $16 $19 $1F` stop SFX), `$20-$38` music, `$39-$3F` stop music;
bits 0-5 are used (spec `$00B8`), `$FF` is ignored. Every call is executed (the game side models the arcade
latch, including its "same value twice is ignored" rule). Commands go into a 16-entry FIFO in Z80 RAM (15
usable, extra ones are dropped); the driver takes one per tick (~4 ms), as the arcade reads its latch once per
tick (spec `$00A9`). `sound_command()` holds the Z80 bus for a few µs inside nestable
`SYS_disableInts()/SYS_enableInts()`; calls before `sound_init()` are ignored. `sound_init()` holds the bus
while it copies 5 KB (once).

**SGDK toolchain bug**: with m68k-elf GCC 16.1 + LTO, SGDK's `Z80_upload()` compiles to
`move.b (a0)+,(0,a0,d0.l)` and writes every byte one address too high (MAME and Genesis Plus GX; SGDK's own null
driver is shifted too, so `Z80_loadCustomDriver`/XGM loaders are affected). `sound_init()` loads the driver
with its own asm copy loop and the SGDK reset sequence.

## Why the Z80

The music clock is the arcade's ~249 Hz tick, not the video frame: on the 68000 VBlank it would be 4.15 ticks
per 60 Hz frame (4.98 at 50 Hz) with up to a frame of jitter, would stall on game lag frames, and every
YM2612 write from the 68000 needs the Z80 bus anyway. On the Z80 the driver runs off YM2612 Timer A, is
independent of the game's frame rate and region, never touches the 68000 bus except to read its data through
the bank window, and costs the 68000 nothing but a FIFO write per command.

## Data format (`tools/build_sound.py`)

Two 32 KB banks, linked 32 KB-aligned (`.balign 32768` in `src/gen/sound_data.s`; the generated file carries
a data hash so a data change relinks). The driver gets the first bank number from `sound_init()`; bank M is
that bank, bank S the next one.

Bank M (`$8000` in the Z80 window):

| offset | contents |
|---|---|
| `$000` | command table, 64 × `{kind, arg, ptr}`: 0 stop all, 1 stop SFX, 2 stop music, 3 SFX (`arg` = slot 0-9 = virtual chip × 5 + priority, `ptr` = frame list in bank S), 4 music (`arg` = priority set 0-3, `ptr` = song header), 5 none |
| `$100` / `$200` | F-number tables NTSC / PAL by note number 1-96: `{block<<3 \| fnum'>>8, fnum'}`, `fnum'` = arcade F-number × 55.556/53.267 kHz (PAL ×55.556/52.781), block kept |
| `$300` | duration table, ≤ 256 × `{ticks to next event, key-off tick or 0}` (172 entries used) |
| `$700` | 32 patches × 32 bytes: YM2612 register block — values for `$30,$34…$8C` (+channel), `$B0` FB/ALG, key-on slot mask |
| `$B00` | songs: header 6 × `{stream pointer, start patch}`, then one event stream per channel |

Channel stream: 2-byte events `{note, duration index}` — `note` 0 = rest, 1-96 = note number, bit 7 =
triplet; `$7D p` patch change, `$7E lo hi` jump (the loop), `$7F` end. All arcade per-note arithmetic is done
at build time:
- pitch: octave/transpose + note → note number (spec `$03D7`, `$04A7`);
- length: tempo × length class (dotted ×1.5) (spec `$041A/$041F`, `$046A`, `$0472`); a zero length counts as
  one tick (the arcade re-reads on the next tick);
- key-off: `G = dur × (max(gate,1)+1) >> 4` (spec `$0439-$0469`) fires only if `1 ≤ G < dur` and no slur is
  pending (spec `$0330`: the countdown only runs while the duration has not expired and the slur count is
  0; plain notes decrement the slur count, dotted notes and rests do not); stored as 0 otherwise;
- loops: octave, tempo, gate and slur persist over the jump, so a later pass can differ from the first (e.g.
  `$22` channel 3 plays its loop a semitone higher from the 2nd pass on). The compiler appends passes compiled
  from the state left by the previous one until a pass with the same events and end state exists, and jumps
  there (one extra pass is needed in a few tracks: music data 26.3 KB).

Build-time check: a Python model of the driver's channel stepping replays every compiled stream and must
start all 12,081 notes/rests of `sound.json`'s first pass on their arcade tick, or the build fails.

Bank S: SFX frame lists, loops unrolled (7.4 KB). Frame = `mask, ticks lo, ticks hi, fields`: mask bit 2i =
tone of voice i `{period lo, hi (0 = off, $FFFF = keep), slide}`, bit 2i+1 = volume `{v or $FF, slide}`,
bit 6 = noise `{period or $FF, mixer noise bits, slide}`, mask `$80` = end. Periods stay in SSG units because
the slides are linear in that domain (spec `$0662`) and the 2-chip → PSG reduction can only be done at run
time (two SFX of different chips mix freely); the conversion to PSG values is a fixed mapping at output.

## Z80 player

Memory: code `$0000-$08C7` (padded to `$1400`), state `$1400-$17FF` (globals, PSG reduction, 24 channel
records of 16 bytes = 4 sets × 6 channels, 10 SFX slot records of 32 bytes), stack, mailbox `$1F00`
(`+0` go, `+1` region, `+2/3` bank, `+4/5` FIFO write/read index, `+7` ready, `+$10` FIFO).

Clock: YM2612 Timer A at half a tick (NA 917 NTSC / 918 PAL); `poll` (in the idle loop, before every YM write,
per music channel, per SFX slot, in the PSG stage) acknowledges overflows and counts half periods, a tick runs
when two are pending → 248.91 Hz NTSC / 248.97 Hz PAL (arcade 249.13 Hz). A tick longer than 4 ms is caught
up by the next ones; no overflow is ever missed (longest gap between status reads measured: 1.36 ms < 2 ms).

Tick: take one command → music → SFX → SSG images → PSG.
- **Music** (behaviour of spec `$0236`): four priority sets; only the highest set whose channel 0 is active
  plays, lower sets keep their position (freeze) and resume when it ends; when the playing set changes the
  driver silences (TL `$7F` on `$40-$4D`, key-off on all 6 channels, as spec `$0182`) and plays nothing that
  tick; patches are reloaded on the next played tick. A song start initialises its set, silences and skips the
  next played tick (spec `$01F2`, `$C026`): from silence the first notes sound on the 3rd tick. Channel 0's end
  ends the set; the other channels just stop advancing. Per channel and tick: one step (two on odd ticks while
  the current event is a triplet, spec `$030A`); a step counts down to the next event, otherwise to the key-off.
  An event writes `$A4/$A0` + key-on `$28` (a key-on while the note is still keyed on gives legato, as on the
  arcade) or nothing (rest); patch changes load at once. Arcade chip 1 FM ch 0-2 → YM2612 part I ch 1-3, chip 2
  → part II ch 4-6. Init: LFO off, DAC off (ch 6 is FM), ch3 normal, pan L+R, SSG-EG off.
- **SFX** (spec `$05D5`, `$064C`, `$0A12`): two virtual SSG chips × 5 priority slots. Per chip only the highest
  active slot runs; while it plays every lower slot is stopped. A frame lasts its tick count; the reading tick
  has no slides; tone slides every tick, volume and noise slides on ticks ≡ 0 mod 4. Restarting a slot resets
  its mixer but keeps its voice fields (spec `$09EC`).
- **PSG reduction** (lossy by nature; model in `tools/sound_model.py`): 6 virtual tone voices in tie order
  chip 2 A,B,C, chip 1 A,B,C; the 3 loudest audible ones → PSG tones 0-2. Noise: per chip the loudest
  noise-enabled channel; the louder chip drives PSG noise; period ≥ 13 → white /512 (< 26) or /1024, period < 13
  → white noise clocked by tone 3 (when at least as loud as the 3rd tone, which is then dropped). Tone
  `N = TP − round(TP·27/256)` (×0.8945; PAL 29 → ×0.8867), halved while > 1023, volume → attenuation
  `[15,14,14,14,14,14,14,12,11,9,8,6,5,3,2,0]`; registers are written only when they change.

## Verification (`tools/sound_test.py`)

The arcade (MAME `sidearms`, latch forced per frame) and the test cartridge (MAME `genesis`; `--pal`:
`megadriv`) run the same schedule; each command reaches the driver FIFO on the tick the arcade dispatched it
and the arcade's tick counter is planted so triplet / slide parity agree. Per tick:
- **FM (musical equivalence)**: identical key-on/off writes (order, channel, slot mask), identical pitch
  writes, identical operator + FB/ALG register state of all 6 channels after the tick. Also counted: ticks
  whose complete FM write sequence is identical.
- **PSG**: state equal to `sound_model.py` applied to the arcade's SSG register images.
- **Commands** taken on the scheduled tick; tick rate, lateness, poll coverage.
- **Audio** (informative): 20 ms RMS envelope correlation of both `-wavwrite` files, sounding length.
- `api`: 11 commands through the real `sound_command()`; `--gpgx`: Genesis Plus GX via the 68000 API.

Cases: 27 SFX × 20 s, 25 music × 125 s (intros, ≥ 1 loop, full `$38`), scenarios `scn_priority` (game over
`$2E` over `$21`: freeze, silence, resume), `scn_sets` (`$38` frozen under `$21`, same-set restart, `$24`,
empty `$2B` ends `$C200` → `$38` resumes, `$2D`), `scn_sfx` (24 commands: SFX priorities/kills on both chips
over music, stop SFX/music/all).

Results (`reports/sound_port/report.txt`, `report_pal.txt`, `report_gpgx.txt`):
- NTSC 55/55 PASS: 926,755 ticks; **every tick musically equivalent** (all 41,542 key-ons and every
  key-off on the arcade's tick, i.e. ±0 ticks; same pitches; same patches); 926,714 ticks (99.996 %) even
  write-identical — the 41 others are silence ticks where the key-offs are written in a different order.
- PAL 55/55 PASS (926,961 ticks, 248.968 Hz).
- Tick rate 248.911 Hz; lateness ≤ 11.2 ms NTSC / 13.0 ms PAL right after song starts or SFX bursts
  (p99 ≤ 11.4 ms), always caught up.
- API: 11/11 commands in order, 15-19 ms after the frame that sent them. The main ROM (`tools/agent_build.sh
  sound`) runs the driver: 249 ticks per 60 frames in Genesis Plus GX.
- Audio: SFX envelope correlation 0.99-1.0 with identical lengths; music 0.11-0.995 at 20 ms resolution — the
  port's 0.09 % slower tick drifts ~0.1 s behind over 2 minutes and dense tracks have flat envelopes (e.g.
  `$34`: mean level −16.0 vs −15.8 dB); register-level equivalence is the actual check.
- Genesis Plus GX: commands taken, envelopes vs. the MAME run 0.90 (`$21`), 0.98 (`$2E`), 0.99 (`$0C`),
  0.10 (`$13`, long noise effect: different PSG noise emulation).

Run: `make` (or at least `.venv/bin/python tools/build_sound.py`), then
`.venv/bin/python tools/sound_test.py [--jobs 8] [--pal] [CASE ...]` (~80 s, builds `tests/sound_rom`),
`.venv/bin/python tools/sound_test.py --gpgx`. Jukebox: `tests/sound_rom/out/release/rom.bin`
(LEFT/RIGHT/UP/DOWN select, A play, B stop all, C stop SFX).

## Known deviations

- SFX on the PSG (by design): 3 tones + 1 noise instead of 6 tones + 2 noises; quieter (often echo) voices
  dropped per tick; bright noise takes tone 3; different noise generator; approximate volume curve. Not tuned
  by ear; FM/PSG balance vs. the arcade mix **unverified**.
- YM2612 vs YM2203: same registers, but envelopes run ~4 % slower (53.3 vs 55.6 kHz) and the output stage
  differs (release tails audible down to about −50 dB longer, e.g. `$2E` 3.2 s vs 4.5 s at −40 dB).
- Tempo −0.09 % (248.91 Hz); transient lateness up to ~13 ms after heavy ticks, no lost ticks.
- Silence ticks write the same registers in a different order. The arcade quirk where a triplet channel that
  ends on an odd tick reads one byte past its end marker is not reproduced (the channel just stops).
- Repeat-forever SFX (`$0C-$0F` top-level code) are not supported: the data never uses them (build asserts),
  so a playing slot always stops all lower ones.
- Genesis Plus GX measures 247.78 Hz for the same Timer A setting (MAME 248.91 Hz = nominal formula); real
  hardware **unverified**. Not tested on real hardware.

Correction to `docs/re/sound.md`: the key-off countdown is `dur × (max(gate,1) + 1) / 16` (spec `$0441-$0449`
adds `dur` g times to `dur`), not `dur × gate / 16`; confirmed by tick-exact key-offs against MAME.
