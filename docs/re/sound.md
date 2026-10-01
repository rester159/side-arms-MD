# Side Arms — sound driver (audiocpu `a_04k.rom`)

Ground truth: `reference/disasm/sound.txt` (regenerate: `tools/disasm_sound.py`; region-aware, data is
dumped as hex so the listing never mis-syncs), decoded data `res/generated/sound.json`
(`tools/extract_sound.py`), and per-command MAME logs `reports/sound/` (`tools/re_sound.py`).
All addresses are audiocpu ROM/RAM addresses. "MAME-verified" = checked against the logs of
`tools/re_sound.py --verify` (`reports/sound/verify.txt`). Everything else is read from the code; guesses are
marked **UNCONFIRMED**.

## Hardware recap
Z80 @ 4 MHz. `$0000-$7FFF` ROM (used up to `$677F`, rest `$FF`), `$C000-$C7FF` RAM, `$D000` sound latch (R),
`$F000/$F001` YM2203 #1 addr/data, `$F002/$F003` YM2203 #2. Only YM #1's IRQ is used (Timer A).
Main CPU side: one command per VBLANK popped from the ring at `($E316)` into `$C800`, `$FF` when the ring is
empty (hardware.md).

## Program structure
| addr | what |
|---|---|
| `$0000` | reset: `im 1`, `sp=$C800`, init at `$0055` |
| `$0055` | delay, clear RAM, `$2D` (prescaler /6) on both chips, Timer A `NA = $C8<<2 \| $01 = 801` (`$24/$25`), `$27=$05`, `ei`, idle loop `$0097` — **everything runs in the IRQ** |
| `$0038` | IRQ: `$27=$15` (reset+reload Timer A), `$C000++` (tick counter), `$00A9` latch, `$0236` music, `$05D5` SFX sequencer, `$0A12` SSG register output |
| `$009A` | YM write (bc = chip port, a = reg, d = data, waits busy) |
| `$0018/20/28/30` | rst helpers: `hl+=a`; `hl+=a, a=(hl)`; `de=table[a]`; inline jump table |

**Tick rate**: Timer A period `72*(1024-801)/4 MHz = 4.014 ms` → **249.13 Hz**. MAME-verified: the logged IRQ
rate is 249.13 Hz in every run (`I|` lines). The music tick, SFX tick and command polling all run at this rate.

## Command dispatch (`$00A9`)
`a = ($D000)`; if `a == ($C001)` (last value) → ignore; store; if `a == $FF` → ignore; else dispatch `a & $3F`
through the 64-word table at `$00BB` (`rst $30`). Consequence: **a command identical to the previous latch value
is dropped** — the main CPU's `$FF` "empty" writes normally separate commands, but back-to-back ring entries
(e.g. attract frames 1528-1530: `03,03,03`) arrive as one value at the 4 polls/frame and only the first fires
(code-derived, `$00AD-$00B1`).

| cmd | handler | meaning |
|---|---|---|
| `$00` | `$013B` | stop all: clear SFX slots (`$0141`) + all music sets (`$015C`) + silence FM |
| `$01-$0F, $11-$15, $17, $18, $1A-$1E` | `$08DE-$09E2` | SFX (SSG): `ld ix,slot; ld hl,data; jp $09EC` |
| `$10, $16, $19, $1F` | `$0141` | stop all SFX |
| `$20-$38` | `$2A15...$64BB` | music (FM): `call clear_set; ld hl,header; jp $01F2` |
| `$39-$3F` | `$015C` | stop all music (+ FM silence, patch cache reset) |

## Voice allocation
- **Music = FM only**, 6 channels: channel record *i* (0-5) drives YM #(1 + i/3) FM channel i%3
  (`$02C1`, `$03ED`). The SSG is never touched by music.
- **SFX = SSG only.** Each SFX command owns a whole chip's SSG (tone A/B/C + noise + mixer + 3 volumes).
  YM #1 SSG and YM #2 SSG each run one SFX at a time, so at most **2 SFX programs** sound together.
- So the peak is 12 voices (6 FM + 6 SSG) plus 2 noise generators. MAME-verified: all 6 FM channels key on in
  every non-empty track except `$38`; most SFX program all 3 tones of their chip (many voices are delayed,
  quieter echo copies of voice A — e.g. `$0E`, `$1D` play the same arpeggio on A, B, C 32 ticks apart).

### Music priority sets
4 sets of 6 channel records (`$20` bytes each): `$C100` (prio 0) < `$C200` (1) < `$C300` (2) < `$C400` (3).
`$0236` plays **only the highest set whose channel 0 is active** (`(ix+0)` of its first record). Lower sets are
frozen (not advanced) and resume where they stopped when the higher one ends. A change of the playing set
calls `$0182` (TL=$7F on all operators, key-off, patch cache `$C010-$C015 := $FF`) so patches reload.
A set dies as soon as its **channel 0** hits `end`; its other channels are frozen without key-off
(`$2A`, `$38` show this: 2/12 decoded events after ch0's end never execute — MAME-verified).
`$01F2` sets `$C026` so the first tick after a start is skipped; from silence the first data byte is read on the
3rd IRQ after the command (MAME-verified offset = 3 ticks).

### SFX slots
Chip 1: `$C500,$C520,$C540,$C560,$C580` (prio 0-4), chip 2: `$C600...$C680`. Per chip only the highest active slot
is advanced (`$05DC/$0614`) and output (`$0A19/$0B56`); while a slot is active every lower slot whose
`(ix+$1F) != $FF` (not "repeat forever") is **killed** (`$0C38`). Re-triggering a busy slot restarts it
(`$09EC`), but does not clear its tone/volume fields (only mixer := $FF).
SSG output: shadow at `$C750` (chip 1) / `$C760` (chip 2); regs 0-10 written **every tick** (`$0BFF`); when no
slot is active the silent image `$0C3D` (mixer $FF) is written. Hardware envelope never used (volumes ≤ 15).

## Music data format
Header (`$01F2`): `tempo`, then 6 × `{ptr lo, ptr hi, patch, gate}`. Channel record fields:
`+0` active, `+1/2` fnum hi/lo, `+3/4` duration counter, `+6` key-on byte (patch slot mask | ch), `+8` gate,
`+9` channel 0-5, `+A/B` key-off countdown, `+C/D` stream ptr (hi,lo), `+E/F` loop mark, `+10` loop counter,
`+11` patch, `+13/14` note-table base, `+16` last byte, `+17` tempo, `+1E` slur count, `+1F` triplet flag.

Stream bytes (reader `$0362`), `lo = b & $1F`, `hi = b >> 5`:
| byte | meaning |
|---|---|
| `lo=$1F` | control, `hi` selects (`$048E`): `$1F n` octave/transpose: note base = table entry `n` (`$04A7`); `$3F n` tempo; `$5F n` writes `+15`, never read (dead); `$7F lo hi` jump; `$9F` loop mark; `$BF n` loop: body runs n+1 times (`$04E3`); `$DF b` dotted note/rest `b` (length table `$0472`); `$FF` end (channel off) |
| `lo=0` | rest, length index `hi` |
| `$01-$1E` | patch change to `b`, next byte = gate (`$03A1`; reloads the patch immediately) |
| `$30` | triplet: the next note's channel runs twice on odd ticks (`$030A`) → ≈ 2/3 length |
| `$21-$3E` (≠`$30`) | slur: `+1E = (b+1)&$1F`; while non-zero, no key-off (key-on rewritten without retrigger) and each note decrements it |
| `$41-$FE`, `lo≠0,$1F` | note `k = octave + lo` (`$03D7`: fnum from note table, `$A4`/`$A0`, key-on `$28`), length index `hi` |

Lengths: `dur = tempo × {_, _, 2, 4, 8, 16, 32, 64}[hi]` ticks (`$046A`, multiply `$047A`), dotted ×1.5 (`$0472`).
Key-off after `dur × max(gate&15,1) / 16` ticks (`$0439-$0469`, `$0348`). The next event is read exactly
`dur` ticks later (MAME-verified to the tick for all 14,006 decoded music+SFX events; triplet timing depends on the parity
of the free-running `$C000` and can differ by ±1 tick).
No volume command, no fades, no LFO/vibrato/pitch bend, no software envelopes: timbre and dynamics are entirely
in the patch. Usage across all tracks: 10,964 notes, 1,117 rests, 823 triplets, 676 dotted, 95 slurs, 101 patch
changes, 90 jumps (= loops); loop mark/loop count are never used by music.

**Note table** `$0513`: entry 0 = rest, entries 1-96 big-endian `(block<<3 | fnum>>8), fnum&$FF`, entry 1 = C#0
(MIDI 13); 12-TET at A4 = 440 Hz within 3.3 cents assuming `f = fnum · (4 MHz/72) · 2^block / 2^21`
(MAME-checked by FFT of `$38` ch0: k=48 → 264 Hz, k=55 → 392 Hz). Notes used: k = 11..89; max fnum 1234, blocks 0-7.

**Patches** `$0C49`: 32-byte records, `patch*32` (`$02D3`): bytes 0-23 = regs `$30,$34,$38,$3C` (DT/MUL), `$40..`
(TL), `$50..` (KS/AR), `$60..` (AM/DR), `$70..` (SR), `$80..` (SL/RR) in register order (S1,S3,S2,S4); byte 24 =
`$B0` FB/ALG; byte 25 = key-on slot mask (`$F0`). Music uses patches 0-30 (`$38` steps through all of them);
the 32 slots `$1029-$1428` look like valid patch data but are unreferenced (**UNCONFIRMED** leftovers). Patch
cache per HW channel `$C010-$C015`. SSG-EG (`$90-$9E`) is never written.

## SFX data format (`$0702`, `$0785`)
Reader `$08C5` returns the byte and peeks the next one into `+1B`. Top-level `(b >> 2) & 7`:
| byte | meaning |
|---|---|
| `$00-$03 nn` | **frame**: hold for `b<<8 \| nn` ticks (0 → 65536), then sub-commands follow while the next byte has `b & $E0 ≠ 0` |
| `$04-$07` | loop mark; `$08-$0B n`: repeat body until counter == n (n passes); `$0C-$0F`: restart from the beginning forever (`+1F=$FF`, survives higher-priority kills); `$10-$1F`: end |
Sub-commands (`b >> 5`): `1/2/3` tone A/B/C: `period = (b&$0F)<<8 | next` (0 → tone off in mixer, `$FFF` → keep),
then signed slide added every tick in 1/16 period units; `4/5/6` volume A/B/C: `b&$0F` (`$1F` keep), signed
slide in 1/16 steps every 4th tick; `7` noise: period `b&$1F` (`$1F` keep), next `& $38` = mixer noise bits
(active low), next = noise slide every 4th tick. Tone/vol/noise slides: `$0662-$06EC`.
SSG tone frequency in MAME = `125000 / TP` Hz (FFT of `$1D`: TP 119 → 1050 Hz, MAME-verified); noise
period presumably `125000/NP` (**UNCONFIRMED**). Tone periods used 19..3832; 27 of 605 tone settings are > 1143
(below 109 Hz). Noise periods used 0-30.

## Command list and game events
Music (`res/generated/sound.json`; lengths MAME-verified, loop re-entry checked for 3 passes):
| cmd | set | tempo | voices | length | game use (from oracle traces) |
|---|---|---|---|---|---|
| $20 | $C100 | 6 | 6 | 18.50 s + loop 6.17 s (loop @ $2A69) | name entry after Start (play1 f401) |
| $21 | $C200 | 11 | 6 | 11.30 s + loop 45.21 s (loop @ $2CC4) | stage 1 BGM (play1 f1047, after naming) |
| $22 | $C200 | 6 | 6 | 92.48 s + loop 27.74 s (loop @ $329E) | BGM, **UNCONFIRMED** which stage |
| $23 | $C200 | 8 | 6 | 12.33 s + loop 40.08 s | BGM **UNCONFIRMED** |
| $24 | $C200 | 10 | 6 | 10.92 s + loop 41.10 s | BGM **UNCONFIRMED** |
| $25 | $C200 | 6 | 6 | 9.25 s + loop 33.91 s | BGM **UNCONFIRMED** |
| $26 | $C200 | 10 | 6 | 14.13 s + loop 30.83 s | BGM **UNCONFIRMED** |
| $27 | $C200 | 9 | 6 | 18.50 s + loop 34.68 s | BGM **UNCONFIRMED** |
| $28 | $C200 | 9 | 6 | 9.25 s + loop 30.06 s | BGM **UNCONFIRMED** |
| $29 | $C200 | 6 | 6 | 18.50 s + loop 12.33 s | BGM **UNCONFIRMED** |
| $2A | $C200 | 6 | 6 | 7.90 s, ends | jingle **UNCONFIRMED** (stage clear?) |
| $2C | $C200 | 5 | 6 | 27.78 s, ends | **UNCONFIRMED** (ending?) |
| $2E | $C300 | 7 | 6 | 3.15 s, ends | game over (play1 f3995) — plays over the frozen BGM |
| $32 | $C200 | 9 | 6 | 12.59 s + loop 10.28 s | BGM **UNCONFIRMED** (boss?) |
| $33 | $C200 | 7 | 6 | 10.79 s + loop 7.19 s | **UNCONFIRMED** |
| $34 | $C200 | 10 | 6 | 5.78 s + loop 5.14 s | **UNCONFIRMED** |
| $35 | $C200 | 10 | 6 | 10.28 s + loop 10.28 s | **UNCONFIRMED** |
| $36 | $C200 | 8 | 6 | 4.11 s + loop 20.55 s | **UNCONFIRMED** |
| $38 | $C100 | 7 | 2 | 111.67 s, ends | "Twinkle Twinkle Little Star" on ch0 stepping through patches 0-30 + bass on ch1: patch demo / sound test (**UNCONFIRMED** use) |
| $2B,$30,$37 / $2F,$31 / $2D | $C200 / $C100 / $C400 | – | 0 | empty (all channels `$FF`) | effectively "stop set" (clear set, start empty set). Note `$2D` (the only `$C400` command) |

Per-channel loop lengths are identical except in `$20,$21,$25,$32,$33,$34`, where some channels loop a short
phrase that divides the long loop; the table shows the LCM. Intro = latest per-channel loop entry (e.g. `$22` ch2-5 enter their
loop at 64.7 s, ch0-1 at 92.5 s). The port should just execute the per-channel jumps.

SFX (chip/priority/data, all end by themselves):
| cmd | chip | prio (slot) | data | len | observed use (**UNCONFIRMED** unless noted) |
|---|---|---|---|---|---|
| $01 | 1 | 0 ($C500) | $1429 | 0.24 s | player shot: every 8 frames with autofire (play1 f2847+, attract) |
| $02 | 1 | 0 | $14A2 | 0.18 s | weapon shot (attract weapon demo) |
| $03 | 1 | 0 | $14F6 | 0.42 s | weapon shot, bursts of 3-5 (attract) |
| $04 | 1 | 1 ($C520) | $1547 | 0.55 s | weapon shot (attract f2091+) |
| $05 | 1 | 1 | $1688 | 0.08 s | rapid shot, every 4 frames (attract f3014+) |
| $06 | 1 | 1 | $16B1 | 0.20 s | alternates with $05 (attract f3178+) |
| $07 | 2 | 1 ($C620) | $1716 | 0.46 s | not seen |
| $08 | 2 | 1 | $1807 | 0.50 s | attract f3493+, every 36 frames |
| $09 | 1 | 2 ($C540) | $1880 | 0.72 s | player (re)appears: attract demo start, play1 respawn f2847 |
| $0A | 2 | 4 ($C680) | $1921 | 1.30 s | attract f3279 (Alpha/Beta union?) |
| $0B | 2 | 4 | $19D6 | 0.92 s | attract f3445 |
| $0C | 2 | 4 | $1A9F | 3.73 s | game start (play1 f402) |
| $0D | 2 | 4 | $1B96 | 1.30 s | name-entry letter (play1 f663, f708) |
| $0E | 1 | 3 ($C560) | $2960 | 1.16 s | continue countdown, every 60 frames (play1 f3335-3935) |
| $0F | 1 | 2 | $1C4B | 0.77 s | play1 f3009/f3132/f3294, attract f3443 |
| $11 | 2 | 0 ($C600) | $1D3C | 0.78 s | enemy hit/explosion (play1) |
| $12 | 2 | 0 | $1DF1 | 0.33 s | follows $1A/$1B/$1C in the next frame (attract) |
| $13 | 2 | 4 | $1E6A | 17.77 s | not seen (long) |
| $14 | 2 | 4 | $1F39 | 2.85 s | not seen |
| $15 | 2 | 4 | $1FF1 | 0.50 s | not seen |
| $17 | 2 | 0 | $207E | 0.12 s | not seen |
| $18 | 2 | 2 ($C640) | $20F7 | 0.64 s | not seen |
| $1A | 2 | 3 ($C660) | $21AF | 0.57 s | attract, with $12 |
| $1B | 2 | 3 | $23B4 | 0.67 s | attract, with $12 |
| $1C | 2 | 2 | $2659 | 0.19 s | POW / item, most frequent in attract (with $12) |
| $1D | 1 | 3 | $2706 | 2.18 s | not seen |
| $1E | 1 | 4 ($C580) | $285B | 1.02 s | coin inserted (play1 f309, coin at f300) — confirmed by timing |
Attract mode sends SFX only (no music commands). In play1 no command at all is sent between f1047 and f2846
although the player fires (ring empty in RAM) — **UNCONFIRMED** why (main-CPU side).

## Tools
- `tools/re_sound.py [CMD..] [--secs-music S --secs-sfx S --jobs N]` runs `tools/re_sound.lua` once per
  command: a write tap on main `$C800` replaces every latch value (`$FF` during 120 warm-up frames, the command
  for 2 frames, then `$FF`). Logs `reports/sound/cmd_XX.log` (`W|t|chip|reg|data` YM writes — SSG regs only on
  change; `R|t|addr|byte` sequence-data reads; `I|t` IRQs; t = s since the command) and `cmd_XX.wav`
  (`-wavwrite`, starts at machine start; command at `t0_abs` in the log header, ≈1.97 s).
  `--summary` → `summary.txt`; `--verify` → `verify.txt` (decoded event ticks vs. logged reads; loop re-entry).
  Full run (25 music × 200 s, 27 SFX × 20 s) takes ~45 s with 6 jobs (~590 MB, mostly wav).
- `tools/extract_sound.py [--print]` → `res/generated/sound.json`: command table, note table, used patches
  (decoded operators + raw), per-track channels with tick-accurate events (`t`, address, op, note k/MIDI,
  duration, gate, slur/triplet/dotted), loop/intro ticks, SFX frames with sub-commands.
- `tools/disasm_sound.py` → `reference/disasm/sound.txt` (annotated).

## Genesis plan — recommendation: (a) native sequence player on the Genesis Z80

Why it fits almost 1:1:
1. **Music is 6-channel FM-only, Genesis has exactly 6 OPN2 FM channels.** YM2203 FM is a subset of YM2612:
   same operator register layout `$30-$8C`, `$A0/$A4`, `$B0`, key-on `$28`. Patches copy verbatim (26 bytes);
   add `$B4+ch = $C0` (L+R, AMS=PMS=0), LFO off (`$22=0`), `$90-$9C = 0` (SSG-EG unused), `$2B=0` (DAC off so
   ch6 is FM), `$27` ch3 normal mode. Map arcade chip 1 ch0-2 → OPN2 part I ch1-3, chip 2 → part II ch4-6
   (`$28` channel codes 4,5,6; part II registers through Z80 ports `$4002/$4003`).
2. **Frequencies**: YM2203 sample rate 4 MHz/72 = 55.556 kHz, YM2612 7.670453 MHz/144 = 53.267 kHz (NTSC),
   7.600489/144 = 52.781 kHz (PAL). Keep the block, scale `fnum' = round(fnum × 1.04296)` (NTSC) /
   `× 1.05256` (PAL). Max fnum 1234 → 1299 < 2048, so no block change is ever needed; bake a 96-entry table at
   build time (one per region, or pick NTSC). Envelope/rate timing scales with the sample rate (≈4 % slower on
   NTSC, 5 % PAL) and DT detune is keycode-based — both inaudible in practice; not compensated.
3. **Tick**: 249.13 Hz. On the Z80, poll YM2612 Timer A (no IRQ on Genesis): NTSC `NA=810`
   (`144·214/7.670453 MHz` → 248.94 Hz, −0.08 %), PAL `NA=812` (248.97 Hz). Alternative on the 68000:
   4.152 ticks per 60 Hz frame with a fractional accumulator (≤ 4 ms jitter, 50 Hz PAL needs 4.98/frame).
4. **Data**: sequence + patches + SFX are ~23 KB (`$0C49-$677F`), fit in one 32 KB Z80 bank window; the Z80
   player is small (the arcade driver is ~3 KB of code). The data must be produced by a build tool from the
   user's ROM (like other assets) — re-encode from `sound.json` rather than copying the ROM block, so pointers
   can be rebased. Port the semantics exactly: 4 priority sets with freeze/resume, ch0-ends-the-set,
   "set change → silence + patch reload", gate key-off, slur, triplet on odd ticks, dotted lengths,
   per-channel jumps, the 3-tick start delay, dropped duplicate commands (optional).
5. **SFX: SSG → SN76489** is the only lossy part. Two SSG programs (chip 1 seen for player shots/coin/countdown,
   chip 2 for enemy hits, game start, name entry — **UNCONFIRMED** as a rule) each use up to 3 tones + noise, but PSG has 3 tones + 1 noise.
   Run both arcade SFX engines unchanged into two virtual SSG register images, then per tick map
   6 virtual tones → 3 PSG tones by audibility (volume, tone enabled; ties → chip 2 then chip 1, voice A first),
   and the louder noise-enabled channel → PSG noise. Echo voices (B/C copies of A) are the natural ones to drop.
   - tone: `N = round(TP × 3579545/32 / 125000) = TP × 0.8949`; N ≤ 1023 ⇒ TP ≤ 1143 (≥ 109 Hz). The 27 lower
     settings (TP up to 3832) → raise by octaves until N ≤ 1023 (or clamp). (PAL: 3546893/32 → ×0.8868.)
   - noise: PSG fixed rates (N=16/32/64 → NP ≈ 18/36/72) or "tone 3" mode with `N3 ≈ NP × 0.895` when tone 3
     is free; most noise uses NP 1-9 (bright), i.e. needs the tone-3 mode (**UNCONFIRMED** noise formula).
   - volume: SSG 4-bit (~3 dB/step, **UNCONFIRMED** for MAME's ymfm SSG table) → PSG attenuation `round((15-v)·1.5)` clamped 0..15 (PSG 2 dB/step);
     tune by ear. FM/PSG mix balance vs. arcade must be tuned by ear (**UNCONFIRMED** arcade mix levels).
   - Optional upgrade: chip-2 SFX as PCM on the DAC — but that steals FM ch6 from the music; not recommended.

Rejected (b) **record-and-replay of register streams**: measured from the logs (writes during intro + one loop,
~2 bytes/write + 1 byte/active tick) ≈ 132 KB music + 51 KB SFX ≈ **183 KB** — affordable in ROM, but it does
not remove the SSG→PSG reduction (still needed at playback), loses the interactive behaviour (set
freeze/resume under game-over/jingles, SFX priority kills) unless re-implemented anyway, and needs per-region
F-number rewriting. Native is smaller (~23 KB data) and exact.

## UNCONFIRMED / open
- Game-event names for most music tracks (`$22-$29`, `$2A`, `$2C`, `$32-$36`, `$38`) and most SFX; only the
  traces' contexts above are observed. A play trace through later stages (and the ending) would pin them.
- Why play1 issues no sound commands between f1047 and f2846 (main-CPU side).
- SSG noise frequency formula (tone measured as 125000/TP; noise assumed the same scale).
- Patch slots 31-62 (`$1029-$1428`) never referenced.
- Arcade output mix levels FM vs SSG (MAME route gains not checked).
