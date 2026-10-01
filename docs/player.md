# Player, weapons and the combined robot (native)

Owner: `src/player.c`, `src/weapons.c`, `src/combined.c`, `src/player_local.h` (private), `inc/player.h`,
`tools/build_player.py`. Specification: `docs/re/flow_player.md` (cited as RE §n); code comments cite the
arcade address of every rule.

## Design

One `Player` struct per player (`players[2]`, 2-player simultaneous co-op), each owning 9 `Shot` slots.
Nothing mirrors the arcade's sprite-RAM objects or its task kernel; the arcade is only the specification
for *what* happens each frame.

Per frame, `players_update()` runs, in the arcade's order:

1. **Weapon select** for both players (`$1E03`), reading the *previous* frame's pad, as the arcade does
   (its select runs before the input of the frame is read).
2. Per player (P1 then P2):
   - death animation / death task, or
   - entry glide (`B2:$829F`) **or** movement + clamp + terrain (`B2:$8368-$84B4`),
   - weapon pose, orbiters, launcher (`B2:$8511`),
   - fire + the weapon's shot-update loop (`B2:$86CC-$8D11`),
   - body composite: firing pose, orbit reference (`B2:$8EF5`).

`players_draw()` submits shots, orbiters, launcher and the body through `spr_16`/`spr_32` only.

### Generated data (`tools/build_player.py` → `src/gen/player_data.c`, `inc/gen/player_data.h`)

Run by `tools/build_assets.py` after `build_levels.py`. Inputs: `res/generated/player.json` (every record is
cross-checked against the ROM bytes it cites) plus the ROM (hash-checked) for tables the extractor does not
export.

| table | source | content |
|---|---|---|
| `SR_NORMAL`, `SR_BIT`, `SR_BIT_NORMAL`, `SR_SG1-3`, `SR_MBL`, `SR_3WAY`, `SR_AUTO10`, `SR_AUTO11` | B2:`$90DF-$9277` | `ShotRec` {code (attr code bits folded in), colour, spawn dy/dx, vy/vx, half_w px, half_h}; `[0]` = facing left |
| `SR_RING_P1` / `SR_RING_P2` | B2:`$927F/$92BF` / `$92FF/$933F` (ROM) | combined-robot rings, patterns A/B |
| `MOVE_TABLE[4][16][2]` | B2:`$864C/$866C/$868C/$86AC` (ROM, all 16 stick nibbles) | speed 1-3, robot |
| `BIT_PATH[32]`, `BIT_START_*` | `$1F56`, `$1F26` | orbit steps (dy, dx, code) |
| `DEATH_CODES`, `PARTNER_EXPLODE` | `$23AD`, `$34F0` | 32x32 composites, colour 8 |
| `EXTEND_TABLES[4]` | `$09F7/$0A07/$0A37/$0A5F` | bonus-life scores, `0xFFFFFFFF` ends |

Hit boxes: the arcade keeps the half width in x/2 units (collision `$2500` compares x/2), so `half_w` is
stored ×2, in pixels. `half_h` is in pixels. Box centred on (x+8, y+8) of the 16x16 shot.

It also writes `res/generated/player_sprites.json`, every (code, colour) pair the module draws (see
interface notes).

## Behaviour

### Movement, entry, terrain
- Movement table by speed level (`B2:$864C..`), clamp y `$20-$C0` (screen 16-176); x clamped to the
  visible 0-288 instead of the arcade's `$50-$190` (the Genesis view is 64 px narrower — deviation kept).
- Terrain: one probe at world (cam+x+16, cam+y+16) (`B2:$84B5`); blocked → retry new-x/old-y, old-x/new-y,
  both old; still inside → pushed 1 px against the scroll, crushed (`$222C`, no invulnerability test)
  past the edge (`B2:$8451`: x < sprite $50, y < $20); the dying body keeps the x of the last drawn
  composite (`$8495`, i.e. before the push: stage 2 dies at x $50 = 80, as MAME). The retries' scratch writes to `+$22/+$23` also move the orbit reference
  for that frame (arcade quirk kept).
- Respawn `$1871`: entry timer 80, invulnerable 80, facing right, sound `$09`. Glide 3/2/1/0 px per frame,
  codes `$62/$66/$72/$76` (−2 facing left). A direction while the timer is < 60 latches control (`+$2A`):
  the glide still runs that frame, normal movement from the next one, **the timer keeps running** (no
  terrain test, blink, normal shot only until it ends). Blink: hidden while the timer is even (`B2:$8F02`,
  OBS die2 f1044-1061; RE doc §2.5 said "odd" — the code and trace say even).

### Fire (`B2:$86E2`) and weapons
Button 1 (A) fires left, button 2 (B) right; facing persists. One shot per press (latch released only when
both buttons are up), except AUTO. A press sets the plain firing code `$20/$22` for that frame (the weapon
pose is dropped on the press frame — OBS weap f1020 `$26`), then the pose timer adds +4. While the entry
timer runs only the normal shot exists.

| slot | weapon | rule | slots / loop |
|---|---|---|---|
| 0 | normal | first free of 0-3, v 14, pose 5, sound `$01` | 0-3 linear |
| 1 | BIT 1-3 | orbiters step once a frame on the 32-step path around the last drawn body (y, x+16) (one-frame lag, `B2:$85EF`), +8 y merged; a press fires one `$0B` shot from each orbiter into 4/5/6 (only if all three free) plus a normal shot | 0-6 linear |
| 2 | S.G. 1-3 | 3/5/7 pellets, only if 0-6 all free; fuse 15 (moving 14 frames), burst `$80→$81→$82`, gone 6 frames later; sound `$02`, burst `$03`; pose 8. **Quirk kept**: a press while pellets are out runs the M.B.L. loop that frame (pellets move, fuses pause, slot 6 frozen) — `$88B7` | 0-6 S.G. |
| 3 | M.B.L. 1-2 | needs 0, 3, 5 free; 6 segments (head/4 body/tail; lv1: head, 2 body, tail) at (x+8, y+2), launch delays 0..5 (lv1 tail 3), v 16, `pierce`; launcher sprite code 4/6 (+1 while firing) beside the body; pose `+$10`, timer 15, sound `$04` | 0-5 delay+linear |
| 4 | 3WAY 1-2 | volley of 3 into the first free group 0-2/3-5/6-8; lv2 shots show `$18+(frame&3)` (also overwrites a terrain explosion's code — quirk kept); pose `+$20`, sound `$01` | 0-8 |
| 5 | AUTO `$10` | while exactly one fire button is held: 1 shot every 4 frames, first free of 0-7, sound `$05`, pose timer 2 | 0-7 |
| 5 | AUTO `$11` | every 8 frames a 3-shot volley up/forward/down into a free group, sound `$06` | 0-8 |

Shots move linearly (`$93FB`), die off the arcade screen (sprite y ≥ `$F4` incl. wrap, x < `$30` or
≥ `$1C0`), explode on terrain: probe world (cam_x+x+24, cam_y+y+8) (`$949C`); explosion codes
`$1C→$1E`, colour 5, 16 frames (`$9467/$9480`). `shot_hit()` explodes the shot unless `pierce`.

**Weapon select** (`$1E03`): slot 0 with a weapon owned → first owned slot. Otherwise the arcade's latch
is inverted: the selection steps when button 3 is **released**, and also once right after the first weapon
is acquired (latch still clear) — OBS weap f1000→1001 and f1012→1013. Changing slot (even to itself)
clears all shots and orbiters and rebuilds the orbit; sound `$1C`.

### Items (`player_apply_item`, `$2657`)
`$80` speed+1 (max 3, `$1A`), `$81` speed−1 (min 1, `$1B`), `$01` BIT+1 (max 3, orbit rebuilt), `$02` S.G.
(3), `$03` M.B.L. (2), `$04` 3WAY (2), `$10`/`$11` AUTO type (all `$1C`), `$06` combine (if not merged),
`$07` nothing, `$08` extra life (`$1D`) to the collector (`$2747` reads `$E0A2`, which the contact
test `$2568/$2573` sets to the touching player). Kills by shots are credited by `player_credit()`
(`$2516`): the shot's owner, or the other player when the owner has no lives left (combined-robot ring
in the slots of a partner out of play).

### Scoring (`player_add_score`, `$2272/$22AE`)
Only while `score_enabled` (arcade `$E010`; set FALSE for the attract demo). Score capped at 999 999 990.
`hi_score` follows any score ≥ it. One bonus life when the score reaches the next entry of
`EXTEND_TABLES[extend_setting]` (sound `$1D`). `extend_setting` = DSW0 bits 4-5: **0 = 100 000 once (MAME
default)**, 1 = every 100 000 to 500 000, 2 = every 150 000 to 600 000, 3 = every 200 000 to 600 000.

### Death (`$222C`, `B2:$822E`, `$1A2D`)
Kill: sound `$0F`, speed 1, all shots/orbiters cleared; the animation starts the next frame (8 × 5 frames,
codes `$164..$1B6` colour 8). 41 frames after the kill: the selected weapon's level is lost, selection 0,
orbit rebuilt, lives−1, respawn at once if any left (OBS die2: kill f1003 → respawn f1044, glide from
f1045, selection f1045 — reproduced to the frame). `player_kill` is ignored while invulnerable.
Out of lives → `in_play = FALSE`; `player_out_of_lives()` is TRUE; continue/game over belong to the front
end (`player_continue`, `player_start`).

### Combined "Side Arms" robot (`combined.c`)
Verified by code reading; the arcade run of this feature was only seen in the attract demo, so the parts
marked UNVERIFIED are best-effort.
- Merge `$2E4E`: sound `$0A`, both players' shots cleared, the arcade suspends all other tasks
  (`players_world_frozen()` is TRUE). Leader transform `$76,$72,$66,$62` × 12 frames. Partner object:
  from the partner's position if it was on screen (that player is hidden; its object first plays the
  transform, 20 frames per code), else from a fixed point (H: sprite (y `$98`, x `$40`) moving +3 px/frame
  right 24 frames; V: (y 8, x `$80`) +2 px/frame down) — then homes with the 16 velocities of `$3130`,
  re-aimed every 12 frames. **UNVERIFIED**: the contact test that ends the flight (taken as the object vs
  player box with the template's half sizes 16/8).
- `$2F9A`: sound `$0B`, merge animation `$140..$146` (P1-led) / `$180..$186` (P2-led) × 12 frames, colour 0;
  hit points `combined_hp` = 1 with both players in play, else 2; orbits rebuilt.
- Merged: 32×48 body (2×2 + the partner's 2 cells below). Leader moves with `B2:$86AC` (5 / 4 px; when its
  stick is idle and both players have lives, the OR of both sticks), keeps its terrain/crush rules and fires
  its own weapon (8 px lower; M.B.L. 16 px, no launcher). The partner's buttons (the leader's when no
  partner is in play) fire an 8-way ring every 4 frames when all 8 partner slots are free, patterns A/B
  alternating: P1-led linear ring (sound `$07`), P2-led boomerang ring that stops, reverses at 20 frames
  and bursts at 29 (sound `$08`). Muzzle flash from the shared fire timer `$E016` (+`$1A`/+`$1C`),
  decremented by every merged player's update (twice a frame with a partner).
- A kill costs a hit point (`$2237`); at 0 (`$223F`): reverse animation, both bodies 12 frames, then both
  respawn in place (`$1960`: control at once, 80-frame blink/invulnerability); a partner without lives
  explodes (`$34F0`) instead. A player starting/continuing while merged splits the robot (`$1B41`).
  **Not done here**: the explosion the arcade plays on the enemy that broke the robot (`$32CE`).

## Verification

Headless runner (`tools/run_rom.py`, `dbg_pad_override`) replaying the inputs of the MAME probes
(`tools/re_player.py`), with the port's player, camera and frame phase synchronised to the arcade at the
start, comparing every shot slot (state, code, position relative to the body), the selected weapon, the
body sprite code and the orbiter positions on every frame:

| run | weapons | result |
|---|---|---|
| `weap` (existing) | M.B.L. 2, 3WAY 2, AUTO `$10`, BIT 3, S.G. 3, select cycle | body code identical 835/835 frames; orbiters identical (except the arcade's uninitialised path pointer at f1000); every shot-slot divergence starts with an arcade shot exploding on an **enemy** (none in the test build) — 12 of 17, the other 5 are the knock-on of one of them (a 3WAY volley landing in another slot group) |
| `weap2` (new, `reports/oracle/weap2`) | S.G. 1, M.B.L. 1, 3WAY 1, AUTO `$11`, BIT 1, S.G. 2, BIT 2, select cycle | body code identical 1245/1245; 26 divergence onsets, all enemy hits, 0 other |
| `die2` | death → respawn | kill→respawn 41 frames, glide, weapon loss, auto-select: frame-exact |
| port only | items, score/extends, entry latch, 2P, merge/ring/split | as specified above (screenshots checked) |

Performance (2 players, all weapons cycling, both firing every other frame; measured in the active
display so the V counter is monotonic): `players_update` avg ≈ 25 lines, p99 ≈ 41 (≈ 16 % of the frame);
idle ≈ 3 k cycles per player, ≈ 0.4 k per flying shot. `prof_player[0/1]` (update/draw) stays in the
build as an approximate debug readout. The draw cost is dominated by the shared sprite engine
(≈ 2.5 lines per `spr_*` call at the time; about 1 line since the QA rewrite of sprites.c, docs/qa.md), not by this module.

## Deviations
- x clamp 0-288 (Genesis view) instead of arcade `$50-$190`.
- S.G. burst: one `$03` command per frame instead of one per pellet (same sound).
- The arcade hangs (`$1E62`) if button 3 is used with nothing owned; the port ignores it.
- Combined robot: partner contact test, and the enemy explosion on split, see above.
- Orbiters at the first frame of an un-built path: the arcade reads ROM garbage, the port uses step 0.

## Interface notes
- `inc/player.h`: unchanged existing fields; added `in_play`, entry latch, orbiter/launcher state,
  `extend_idx`, `name[3]`, `Shot.timer/phase/delay`; `player_start/continue/out_of_lives`, `hi_score`,
  `extend_setting`, `score_enabled`, `combined`, `combined_hp`, `players_world_frozen()`.
- Enemies: test only `active == 1` shots; `half_w/half_h` are pixel half sizes around (x+8, y+8); call
  `shot_hit()`; `player_kill()` (handles the robot's hit points).
- Game loop: while `players_world_frozen()` the level scroll and enemies must not update (arcade `$3078`
  suspends every task).
- `res/generated/player_sprites.json` should be added to the pattern-bank walk in `tools/build_assets.py`
  (and `build_player.py` run before it): P2 weapon poses / launcher and the P1-led robot are otherwise
  missing from the bank and go through the slow runtime remap.
- Test hook: `dbg_player_cmd[2]` (host writes an item code, `$FF` kill, `$FE` start with 3 lives, `$FD`
  +10 000 points).
