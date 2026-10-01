# Side Arms — object / enemy system

Scope: object records, the per-frame updater, the motion-script engine, spawning, the enemy roster,
items/POW, enemy bullets, bosses (object side), sprite output and collision.
Read `docs/re/hardware.md` first. Related: `levels.md` (script interpreter, camera, stage table),
`flow_player.md` (player object, weapons, player shots).

Tools (all development-only):
- `tools/extract_spawns.py` → `res/generated/spawns.json` and `res/generated/metasprites.json`.
  It simulates the stage script and *executes* every spawn routine in `tools/z80lite.py`, a small
  Z80 interpreter. This yields the exact object records each event creates.
- `tools/re_objects.lua` + `tools/re_objects.py` is the MAME probe. It uses the debug DIPs: invincible,
  full power, stage select. It also NOPs the terrain-crush death call at B2:`$84B1`, probe only.
  Output goes to `reports/oracle/obj_sNN/events.txt`:
  - `N`/`K`: object appears / disappears
  - `C`/`G`: sprite statistics
  - `T`: camera
  - `S`: sprite RAM at the peaks

Notation: `$xxxx` is fixed ROM, `B0:$xxxx` is bank 0 (`$8000-$BFFF`). Object code always runs with
bank 0 mapped (`$21B6`, `$20CF`). Items marked **UNCONFIRMED** are static reading only.

---

## 1. Objects live *in* sprite RAM

There is no separate object table. Every 32-byte sprite record `$F000+32n` is also an object
record:
- bytes `+0..+3` are the hardware sprite (code, attr, y, x)
- bytes `+4..+$1F` are the object state

An object that uses several sprites (2x2, boss) owns consecutive records. Only the *head* record
holds state, and the update code rewrites the sub-records every frame. Deleting an object sets
`y=0` (the hardware skips the record) and `+8=0`.

### 1.1 Regions and allocators

| region | layout | used by | allocator / updater |
|---|---|---|---|
| `$F000-$F1FF` | 16 x 1-sprite | enemy bullets, homing missiles, bomb columns, snake chains, boss laser bursts, 3-way spreads | `$0531` (1 rec), `$054B` (2 consecutive, stride `$40`), `$0561` (3), `$057A` (4, stride `$80`). Each record is updated as an independent 1x1 object by `$23CB` (loop `$21BB`). Multi-record allocators only reserve neighbours. |
| `$F200-$F3FF` | player 1: ship 2x2 `$F200`, BIT/attachments `+$80..`, 9 shots `$F2E0-$F3C0` | player code | flow_player.md |
| `$F400-$F5FF` | player 2 (same layout) | | |
| `$F600-$FA7F` | **9 x 2x2** (`$80` bytes) | all normal enemies, explosions, boss parts | `$0583` (needs `+8`, `+$28`, `+$48`, `+$68` all 0). Updater `$2784` (loop `$21D1`). |
| `$FA80-$FAFF` | 4 records | combined-robot partner (flow_player.md) | — |
| `$FB00-$FEFF` | 1 x 8x4 (32 records) | sprite bosses | direct copy. Updater `$2B0B` (`$21E7`). |
| `$FF00-$FFFF` | 8 x 1-sprite | script `SPAWN` objects (hidden bonuses), item pickups, mines, orb burst | `$0528`. Updater `$23CB` (loop `$21F2`). |

Allocation convention: `call $05xx` returns to the next instruction (normally a 3-byte `ret`/`jp`)
when there is no free slot. When a slot is free it returns to the caller+3 with `IY=DE=slot`
(`$0545` → `$0384`, "skip-return"). **A spawn with no free slot is silently dropped.** This was
verified live: 10 of the 210 stage-1 spawns were missing in MAME, and every one of them happened
while all 9 big slots were busy.

### 1.2 Record layout (head record)

| off | meaning |
|---|---|
| +0 | sprite code low 8 bits |
| +1 | attr: b0-3 colour (palette 512+16c), **b4 = X bit 8**, b5-7 code bits 8-10 |
| +2 | Y (screen raw, 0 = hidden; visible 16..239) |
| +3 | X low 8 bits (screen raw, 9-bit with attr b4; visible 64..447) |
| +4 | frames left in the current motion step |
| +5 / +6 | dy / dx per frame (signed) |
| +7 | category. `$E400+cat` counts live objects (`$059F` inc, kill dec). Only cat 0 (enemy bullets) is capped (§5). Seen: `$00` bullets, `$20` pickups/hidden bonuses, `$40` enemies, `$41` eye turret, `$50` sprite bosses, `$7F` effects/chains |
| +8 | state: 0 free, `$80` active (`$C0` on player shots = hit spark) |
| +9 | flags: b0 immune to player shots; b1 no player contact; b2 ignore terrain; b5 locked to BG (moves with the camera); b6 kill request (→ death at once); b7 death runs native code at `+$1C` instead of a death script |
| +A | item code (0 = enemy). See §4 |
| +B | hit points (−1 per shot hit per check) |
| +C / +D | shot hitbox half-height / half-width÷2 |
| +E / +F | player-contact hitbox half-height / half-width÷2 |
| +10..+16 | per-type scratch. `+$10` is often a heading or orientation, `+$11/+$12` are counters. `+$16` = last aim direction (0-31) |
| +17 | X/2 (9-bit X halved), refreshed before collision checks |
| +15 | score index into `$2337` (§7.1) |
| +18 | carried item letter (big enemies; set from `$E048` by `$08D2`) |
| +1A/1B | terrain handler: jumped to when the move hits terrain (after the position is restored) |
| +1C/1D | death: script address (b7 clear) or native routine (b7 set) |
| +1E/1F | motion pointer (current step) |

Templates: every `ld hl,T / ld bc,$0020 / ldir` in the ROM copies a 32-byte template T into a slot.
There are 53 of them, all decoded in `spawns.json` → `templates`.

---

## 2. Per-frame flow

Main loop, once per frame (sync `$0200`): `$1D8A` players → `$1FB7` (`$E003`++, scroll + script on
odd `$E003`) → B2:`$8000` player input / movement → B2:`$813A` aim-target choice → `$21B2`
objects → back.

```
$21B2 objects:
  for rec in $F000..$F1E0 step $20: if rec+8: small_update(rec)      ; $23CB
  for slot in $F600..$FA00 step $80: if slot+8: big_update(slot)     ; $2784
  if $FB08: boss_update($FB00)                                        ; $2B0B
  for rec in $FF00..$FFE0 step $20: if rec+8: small_update(rec)      ; $23CB
```

### 2.1 Motion-script engine (`$23CB` small, `$2784` big, `$2B0B` boss)

A motion step is 5 bytes `[dur, code, attr, dy, dx]`. The pointer `+$1E` addresses the *current*
step. A template's pointer is therefore set 5 bytes before its first step.

```
update(o):
  if o.flags & $40: goto die(o)                         ; $25EF / $2AAD
  if o.flags & $20 and ($E003 & 1):                     ; same frames the camera moves
      o.y -= $E088 ; o.x -= $E089  (fix X bit8)         ; stay glued to the BG
  save (attr,y,x) -> $E0C0..2
  if --o.timer == 0:
      o.ptr += 5
      step:
      s = *o.ptr
      if s.dur == $00: jp s.code|s.attr<<8              ; native code (bank 0 / fixed)
      if s.dur == $FF: o.ptr = word; goto step          ; goto
      if s.dur == $FE: kill(o); return
      o.code = s.code ; o.attr = (o.attr & $10) | s.attr
      o.dy, o.dx, o.timer = s.dy, s.dx, s.dur
  o.y += o.dy ; o.x += o.dx (bit8 fix-up: low byte $0x → set b4, $Fx → clear b4)
  kill if: small y >= $F1 | big $F1 <= y < $F8 |
           (x<256 and x < $30 small / $20 big) | x >= $1C0
  2x2 only: subrecords +$20/+$40/+$60 get code c+1, c+8, c+9; y, y+16; x, x+16 ($281D-$28F7)
  if !(o.flags & 4) and terrain_hit(o):                  ; $07C0 small / $082F big (bank 2 map $A000)
      restore saved attr/y/x; jp o.wall                  ; +$1A
  collisions (§7) on even $E003 (small) / odd $E003 (big, boss)
```

Native code resumes a script with `ld hl,STEP / jp SET`, where `SET` = `$2435` (small),
`$27EE` (big) or `$2B1B` (boss). These store HL in `+$1E` and load that step at once. Natives run
with `IX` = object.

Kill (`$257F` small, `$29A3` big, `$2D7A` boss): `$E400[cat]`−1, `y=0`, `+8=0` on every record
(boss: clear `$FB00-$FEFF`).

Death (`$25EF`/`$2AAD`, also `$2DEE` boss):
```
flags |= 3
if flags & $80: jp (+$1C)
else: +$1E = +$1C - 5 ; timer = 1
```
Common death scripts:

| script | anim | for |
|---|---|---|
| `$4D5E` | 2x2 explosion `$1C0,$1C2,$1C4,$1C6,$1D0,$1D2,$1D4,$1D6`, colour 8, 4 f each, then kill | most big enemies |
| `$4D87` | the same, colour 7 | troopers, surfacing robot |
| `$4DAB` | 1x1 `$138-$13E`, colour 8, 5 f each | missiles, mines |
| `$513C` | `FE`: vanish | pickups, coin-egg dragonflies |

### 2.2 Aim helper `$06E8`

Target = `($E020, $E021)` = (Y, X/2) of the chosen player. B2:`$813A` re-chooses it every 8 loops:
- **Both players alive, horizontal stage:** the more advanced player is the target if its X/2 ≥ `$60`.
  - Otherwise B2:`$8195` decides. It compares weapon totals: UNCONFIRMED.
- **Vertical stage:** the same test on Y with threshold `$80`.
- **No player:** (`$78`,`$E0`).

`$06E8` returns a direction 0-31 in A and `+$16`. 0 = right, 8 = down, 16 = left, 24 = up.
- It works on (dy, dx/2), so it is an octant plus a 5-sector ratio test (table `$0780`). Horizontal
  aim is therefore coarser.
- `$06F7`/`$0706` aim at P1/P2 explicitly.

---

## 3. Spawning

### 3.1 Script → objects

The stage script is documented in levels.md §1. Its records are 4 bytes `{cmd, trig, lo, hi}` in
bank 1 and fire when the low byte of the scrolling coordinate equals `trig`. Spawning happens in
two ways:

1. **`$FE` CALL** of a bank-0 *spawn routine*. This is how almost every enemy appears.
   - A routine is usually a fan of entry points `ld c,n / jr common`.
   - `common` does `call alloc / ret / nop nop`, then the success path:
     - copies the template
     - takes Y (a lane) or a table entry from `C`
     - optionally sets a carried item via `$08D2`
   - The parameter tables differ per family. The extractor therefore *runs* them in z80lite
     instead of decoding them.
2. **`SPAWN` (any other cmd byte)** `$2080`. It copies template `lo|hi` into a `$FF00` slot.
   - X-scroll: `y = cmd`.
   - Y-scroll: `y = $F0`, `x = (cmd&$FE)<<1`, with bit 7 → X bit 8.
   - The script only uses this for the hidden bonuses (§4.3).

Helper commands that matter for objects (bank 0):

| routine | effect |
|---|---|
| `$8000-$8030` (13 entries, `c` = 2..16) | `$E017 = max(0, c + table $8049[d])` = **maximum live enemy bullets**. `d = ~DSW0 & 7` (difficulty, MAME default 3 → +0); table `$8049` = −3,−2,−1,0,1,2,2,3. Verified: stage 1 cap 2, stage 4 cap 4, stage 10 cap 16. The probe never exceeded these. |
| `$80CA-$8109` (music) | also `$E050` = bullet direction table by stage × difficulty (§5) |
| `$82CC-$830E` | `$E048 = letter` (`P t b m 3 y s A C T I M`). It is consumed by the *next* `$08D2` call, so the next carrier enemy gets it. `$A905` sets `P` on all four of its pods. |
| `$5523` | coin easter egg: when `$E240` (coins inserted, `$09AF`) has a low nibble of 0, spawns task `$3B6D`. That task creates `$E240>>4` dragonflies (`$5548`, 1/s, HP 4, 3000 pts). Purpose UNCONFIRMED. |

`spawns.json` → `stages[i].events[]` contains:
- `tick` and `frame` (×2): time since the game start at 0.5 px/frame, excluding boss halts
- `stage_tick`
- `camera` `{x,y}`, the BG scroll at the firing tick
- `routine` and `family`
- `objects[]`: slot, template, screen x/y, hp, score, item, flags, motion, carried letter

**Verified against MAME** (`obj_s01`):
- Every event fired at simulated frame + 771 (the game-start delay). Camera X matched exactly.
- Stage 2 kept a constant offset that included the 2396-frame boss halt.
- 200/210 objects matched by frame (±2), Y and death handler. The other 10 were slot-full drops.

### 3.2 Roster counts by stage (difficulty 3)

From `spawns.json`: events with objects, per family, per section 1-10.

| family | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| drum_homing | 120 | 69 | | 79 | 27 | | | 17 | 15 | |
| jet_homing | 36 | 76 | 8 | 162 | 54 | 11 | 30 | 85 | 39 | |
| pod_vertical | | 13 | 75 | 108 | 30 | 79 | 95 | 57 | 24 | |
| trooper_tan | 30 | 7 | | 17 | | | | | 7 | |
| trooper_green_drop | 5 | | 11 | 27 | | 12 | | | 10 | |
| trooper_yellow | | 29 | | | 12 | | | | 20 | |
| trooper_hover | | | 2 | | 26 | 8 | | 41 | 8 | |
| trooper_red | | | 6 | | | 2 | | | | |
| surfacing_robot | 4 | | | | 9 | | 16 | | | |
| pod_column_pow (×4 pods) | 3 | 1 | | 3 | 1 | | 7 | 4 | 4 | |
| mine_homing | | 8 | 23 | 4 | | | | 8 | | |
| bomb_column | | 8 | | | | | 5 | | 6 | |
| turret_crab / missile / spike / dome | | 10/0/0/0 | 0/10/5/0 | 0/7/2/12 | | 0/3/0/0 | 0/0/13/0 | | | |
| eye_turret / orb_burst | | | | 6/11 | | 7/14 | | | 0/6 | |
| barrier_pair | | | 4 | | | | | | | |
| snake_chain_a / _b | | 2/0 | 1/1 | 2/2 | 1/0 | 3/0 | 0/5 | 4/5 | 2/2 | |
| hidden bonuses (α / cow / 3000 / 1UP) | 1/1/0/0 | 0/0/1/0 | 0/3/2/0 | 0/1/6/0 | 1/1/3/0 | 1/1/8/0 | 1/0/0/0 | 1/5/1/0 | 0/2/0/0 | 1/0/0/1 |
| bosses | `$69D0` | wheel `$7192` | `$6C12` | wheel `$719C` | `$6C12` | | `$6DB4`×2 | `$6DB4`×2 | `$6DB4`, wheel `$71A6` | final `$5FC3` |

---

## 4. Items, POW and hidden bonuses

### 4.1 Carriers → pickups

When a big enemy dies (`$2A17`):
1. sound `$11`
2. score
3. if `+$18` is set, `$2A23` maps the letter to a pickup template
4. the pickup is allocated with `$0528` (`$FF00`) and placed at the enemy's centre (`y+8, x+8`)

Small objects (`$25E3`, sound `$12`) never drop items.

| letter | template | sprite (code/colour) | `+A` item | effect when touched (`$2657`) |
|---|---|---|---|---|
| `P` | `$4DCF` | POW `$118`, colour cycles 4/5/13 | `$80` | speed +1 (max 3). **Shooting it cycles it** (§4.2) |
| `t` | `$513D` | orange orb `$100-$103` c4 | `$01` | BIT (+$11, max 3; also rebuilds the attachment via `$1F26`) |
| `b` | `$5174` | `$104-$107` c10 | `$02` | S.G. (+$12, max 3) |
| `m` | `$51AB` | `$108-$10B` c5 | `$03` | M.B.L. (+$13, max 2) |
| `3` | `$51E2` | `$10C-$10F` c6 | `$04` | 3WAY (+$14, max 2) |
| `y` | `$5219` | `$110` c0/c3 | `$10` | AUTO (+$15 = `$10`) |
| `s` | `$5246` | star `$111` c5/c13 | `$11` | AUTO (+$15 = `$11`) |
| `A` | `$5273` | "α" capsule `$112-$117` c5, HP 250 | `$06` | combine into the "Side Arms" robot (`$2E4E`, flow_player.md) |
| `C` | `$546F` | cow `$134` | `$07` | bonus 10000 (+15=`$50`) |
| `T` | `$549C` | barrel `$135` | `$07` | bonus 3000 |
| `I` | `$54C9` | fruit `$136` | `$07` | bonus 3000 |
| `M` | `$54F6` | 1UP `$137` | `$08` | extra life, sound `$1D` |

Touching a pickup:
1. applies the effect
2. sound `$1A` (speed+), `$1B` (speed−) or `$1C` (weapon)
3. sets `+$1C=$5136` and goes through `$25E3` (sound `$12`, score from `+$15`, vanish)

Pickups use flags `$25`: immune to shots, ignore terrain, scrolled with the BG. The POW capsule is
the exception: it uses `$A4`, so it is shootable and has a native death, which drives the cycle
in §4.2.

### 4.2 POW cycle (death-handler chain from `$4E01`, `spawns.json` → `pow_chain`)

| step | form | `+A` | HP (hits) | idle anim |
|---|---|---|---|---|
| 0 | POW | `$80` speed+ | 1 | `$118` c4/c5/c13, 6 f |
| 1 | BIT | `$01` | 3 | `$100-$103` c4 |
| 2 | POW | `$80` | 1 | |
| 3 | S.G. | `$02` | 3 | `$104-$107` c10 |
| 4 | POW | `$80` | 1 | |
| 5 | M.B.L. | `$03` | 3 | `$108-$10B` c5 |
| 6 | POW | `$80` | 1 | |
| 7 | 3WAY | `$04` | 3 | `$10C-$10F` c6 |
| 8 | POW | `$80` | 1 | |
| 9 | speed DOWN | `$81` | 14 | `$11C` c2/c5/c9 |
| 10 | AUTO `$10` or `$11` | random: RNG `$E008`+`$6F`, bit 7 | — (immune) | `$110` / `$111` |

- Each change plays a 2-frame "turn" animation (`$119/$11A` or `$11E/$11F`, colour 5). The capsule
  is intangible during it (flags b0|b1).
- The chain loops between steps 0-9 only as listed. After step 10 it no longer changes.

### 4.3 Hidden bonuses (script `SPAWN`)

The templates `$52FF/$5337/$5385/$53D3/$5421` are:
- **Invisible:** code 0, flags `$A6` (no contact, ignores terrain, BG-locked, native death).
- **Held still for 200-frame steps.**

Shooting one for its HP reveals a pickup in place (death handlers `$5327/$535F/$53AD/$53FB/$5449`):

| template | HP | reveals |
|---|---|---|
| `$52FF` | 4 | α capsule (item 6) |
| `$5337` | 8 | cow (10000) |
| `$5385` | 4 | barrel `$135` (3000) |
| `$53D3` | 4 | fruit `$136` (3000) |
| `$5421` | 4 | 1UP `$137` |

All of the revealed pickups are touch pickups.

---

## 5. Enemy bullets

- **Template** `$4000`: code `$126` c8 / `$127` c7, alternating every frame.
  - flags `$01` (immune to shots), cat 0
  - contact box `$0C/$06`, i.e. ±12 px both axes, centre to centre
  - terrain handler `$4940`: the bullet dies on terrain (UNCONFIRMED detail)
- **Spawn**: the firer calls `$05AA` first, which succeeds only if `$E400` (live cat-0 count)
  < `$E017`.
  - Then `$0531`, template copy, `$059F`.
  - The motion pointer is taken from the direction table: `+$1E = word[$E050 + 2*dir]`.
  - Position `(y+8, x)` of the firer.
  - 3-way turrets (`$0561`) check the cap once and then spawn 3.
- **Speed** `$E050` → table at `$4022` / `$4066` / `$40AA` / `$40EE` = speed level 3/4/5/6.
  - Level 3 moves 3 px/f horizontally and 2 px/f vertically. The diagonals mix 1/2/3 px steps
    (see `spawns.json` → `enemy_bullet.direction_tables_by_speed`).
  - The level comes from tables `$813C + 8*stage` indexed by difficulty:

| stage table | diff 0..7 |
|---|---|
| 1 `$813C` | 3 3 3 3 3 4 4 4 |
| 2 | 3 3 3 3 4 4 4 4 |
| 3 | 3 3 3 4 4 4 4 5 |
| 4 | 3 3 4 4 4 4 5 5 |
| 5 | 3 3 4 4 4 5 5 5 |
| 6 | 3 4 4 4 4 5 5 5 |
| 7-9 | 3 4 4 4 5 5 5 6 |
| 10 `$8184` | 3 3 4 4 4 4 4 5 (`$8130` forces `$4066` = level 4) |

Other enemy projectiles (`$F000` pool):

| template | sprite | behaviour |
|---|---|---|
| `$499C` | missile `$284` (1x1) | homing. Heading `+$10` (16 dirs). Each step it re-aims and turns one notch (±2) towards the target (`$4963`, tables `$49BC`/`$49DC`). HP 1, shootable 8x4, 100 pts. |
| `$4B89` | missile `$294` c5 | same homing logic (`$4B50`). Fired by sprite bosses (`$36B6` task). 0 pts. |
| `$4C6E` | bullet `$127` c7/c8 | straight 4 px/f, direction table `$4C4E`. Fired by snake tails. Immune. |
| `$3613` | beam `$120-$125` c8 | boss laser burst: 8 records written directly to `$F100-$F1E0` by task `$3522` every 60 f, sound `$18`. Immune, contact 9x4. |
| `$A14E` | beam `$1B8/$1B9` c8 | dome turret laser, table `$A16E` |

---

## 6. Enemy roster

Notes for all rows:
- **HP** is for MAME `sidearms` (World). `$0AA0` = 'N'. `trooper_tan` and `trooper_green_drop`
  get HP 2 only when `$0AA0` = 'J'.
- **Score** is the displayed points.
- **Codes** are the 2x2 base code `c`. The sprite uses c, c+1, c+8, c+9.
- **Frame lists** for each family: `metasprites.json` → `family_frames`.
- **"Fires"** always goes through the bullet cap.

| family | spawn routine(s) | template | sprite | HP | pts | behaviour (pseudocode summary) |
|---|---|---|---|---|---|---|
| **drum_homing** | B0:`$AD32-$AD42` (Y lanes `$28,$4B,$70,$94,$B8`) | `$AD5B` | drum ship `$3C0-$3E6` c5, 12 spin frames | 1 | 200 | Enters at the right edge (x=`$1BF`), dx −3 for 24 f. Aims (`$AD83`) and picks one of 5 headings (dy,dx ∈ {(1,−1),(1,−2),(0,−2),(−1,−2),(−1,−1)}) for 24 f of spin. Repeats (`$AE7F`) with 8 headings while it is still right of the player. Once past the player (`$E021 ≥ +$17`) it plays the U-turn `$B052` (frames `$3D0,$3E0-$3E6`, curves to dx +2), then `$B103`: 16 f at dx +4, fires 1 aimed bullet (`$B111`), then dx +4 off screen. |
| **jet_homing** | B0:`$A4DA-$A4EA` (same lanes) | `$A503` | jet `$5C0-$5E6` c6 | 1 | 200 | Same AI as drum_homing (`$A52B`, `$A627`, U-turn + 1 shot `$A8B9`), faster: entry dx −4, headings up to (±3,−2)/(±2,−3). |
| **pod_column_pow** | B0:`$A905` | `$A97E` ×4 | spinning pod `$6C0-$6E6` c12 | 2 | 200 | 4 pods at y `$40,$60,$80,$A0` (start timers 1-4), **all carry POW**. `$A9A1`: if the player is near the right edge (|`$E0`−X/2| < `$30`) → `$AA5F` path (UNCONFIRMED). Otherwise: decelerating entry dx −4,−3,−2,−1, stop, spin 24 f, fire 1 aimed bullet per spin, up to 8 times, then leave right (`$AA4B`). |
| **pod_vertical** | B0:`$AAB3-$AAC7` (table `$AAF6`: from top x=`$102/$132/$162`, from bottom x=`$120/$150/$180`) | `$AB0E` | pod `$7C0-$7E6` c5 | 2 | 200 | Moves vertically ±2 px/f while spinning. Every 24 f, if it has not reached the player's Y (`$E020`), it fires an aimed bullet (`$AB59`/`$ABD4`). After it crosses the player's Y it branches to `$AC24` (turn + horizontal exit, UNCONFIRMED). Uses terrain check `$082F`. |
| **trooper_tan** | B0:`$8314-$8320` (table `$8355`: y `$10,$40,$80,$B0`) | `$8365` | jet-pack mech `$200-$222` c1 | 1 | 300 | Dives in from the right at (dy +4, dx −3) for 15 f. `$838D`: aims and, if the direction is 12..20 (target to the left), fires one bullet. Keeps diving. On landing (terrain handler `$840F`) it becomes a walker: crouch `$214` 20 f, then `$843E` aims and fires forward or backward by facing (`$E01F` = `$4C`/`$52` picks the muzzle record), with hop motions. |
| **trooper_green_drop** | B0:`$8A57/$8A5B` (x `$6C`/`$174`, y 0) | `$8AA4` | mech `$200-$212` c13 | 1 | 300 | Falls at dy +4 until it touches terrain (`$8B88`, snaps to the floor via `$082F`). Then a walker: faces the player, fires an aimed bullet when the target is in its forward cone (`$8B9E`), and hops with 12 f crouch `$214` + 7 f arcs (dy −3..+3, dx ±2) (`$8ABF`). Handler table `$8C91` by `+$10` facing. |
| **trooper_yellow** | B0:`$90CA/$90CE` (table `$9107`: left x=`$21` / right x=`$1BF`) | `$9113` | yellow beetle-mech `$2A0-$2D6` c9 | 3 | 500 | Immune flag clear only after it lands. Falls dy +4 (`$912E`/`$9337`), then the terrain handler `$92BC`/`$94C3` → jumping walker. Uses RNG `$E008` for jump choice and fires bullets (6 bullet sites). UNCONFIRMED detail. |
| **trooper_hover** | B0:`$8DB6-$8DC2` (table `$8DF6`) | `$8E0A` | green soldier on hover-bike `$224-$252` c11 | 2 | 300 | Enters from the left (x `$21`) or right. Flies with crouch/turn frames and fires homing missiles `$499C` (2-record allocs `$054B`) (`$8E32`/`$8F83`). Ignores terrain. |
| **trooper_red** | B0:`$9547/$954B` (table `$9591`) | `$95AD` | capsule `$2E0` opening to a red soldier `$2F2-$2F6` c0 | 2 | 500 | Starts invisible (code 0) and slides until the terrain handler `$95D2`/`$95F3` fires. Then it becomes BG-locked (flags `\|$24`) and opens, firing missiles `$499C` (RNG `$E008`). UNCONFIRMED detail. |
| **surfacing_robot** | B0:`$8C9E-$8CAD` (x `$A8/$F0/$138/$180`, y `$B0`) | `$8CCC` | bubbles `$254/$256` → robot `$260-$276` c0 | 1 | 300 | 20 f of bubbles (immune), emerges, fires a homing missile `$499C` straight up (motion `$4A27`), more frames, a second missile, then submerges (kill). BG-locked. |
| **turret_crab** | B0:`$9B27-$9B2F` (table `$9B7C`: y, orientation `+$10`) | `$9BAC` | orange crab `$500-$506` c12 | 3 | 800 | BG-locked. Every 50 f: `$E00F += $63`, and if < `$64` (~39%) fires a **3-way** aimed spread (dir−1, dir, dir+1, `$0561`). The muzzle depends on `+$10` (`$6D` = other side). |
| **turret_missile** | B0:`$9CB7-$9CCF` (table `$9D08`) | `$9D38` | blue ship `$510-$526` c5 | 3 | 800 | BG-locked. Every 50 f: `$E00F += $63`, and if < `$C8` fires one homing missile `$499C` whose start heading depends on orientation `+$10` = `$61-$64`. |
| **turret_spike** | B0:`$9EAD-$9EC9` (table `$9F02`) | `$9F32` | spike ship `$530-$536` c3 | 3 | 800 | BG-locked. Fires 1 aimed bullet per 50 f period, at most 4 times (`+$11`), then `$9FCA` (leaves, UNCONFIRMED). |
| **turret_dome_laser** | B0:`$A008/$A014` (table `$A05D`) | `$A08D` | dome `$540-$546` c5 | 3 | 800 | BG-locked. Every 50 f, if `$E00F` ≥ `$B4` (~30%), fires laser `$A14E` aimed through table `$A16E`. |
| **eye_turret** | B0:`$B65D/$B662/$B667` (only if `$F780-$F980` heads are free; 5 objects placed from tables `$B70E/$B71E/$B72E`) | `$B82E` | eye `$360-$366`, `$370` c11 | 1 | 100 | Blinks (code alternates with blank) for `+$11` cycles, intangible. Then it opens and becomes vulnerable, and fires aimed bullets `+$12` times (`$B879`). Then `$B953` (close/leave). Category `$41`. |
| **orb_burst** | B0:`$B15D` (only if `$FF00-$FFE0` are all free) | `$B17F` | blue orb `$340-$346` c5 | 2 | 0 | Drifts left 2 px/f spinning. Native `$B2DE` and death `$B49E` both copy the 256-byte block `$B1DE` into `$FF00-$FFFF`: 8 radial fragments at the orb centre. |
| **mine_homing** | B0:`$BAF6-$BB12` (8 positions) | `$BB51` (`$FF00` pool) | mine `$550-$55E` c10 (`$500` c3 first) | 1 | 100 | Small homing mine (`$BB79`): aims, picks one of 16 motions from `$BBB3`/`$BBD3`, repeats. Ignores terrain. |
| **bomb_column** | B0:`$9815` (`$057A`: 4 bombs at x `$80,$C0,$60,$A0`+256) | `$992D` | bomb `$300-$30B`, `$318` c5 (1x1) | 1 | 100 | Hidden and intangible, waiting. When the player's X/2 is within `$18` (`$984A`), all four arm with stagger timers 0/20/40/60 f. They fall, accelerating dy 1→5 px/f. Immune to shots (flags `$A1`). |
| **barrier_pair** | B0:`$BD66` (2 objects) | `$BDBD`, `$BDDD` | grill `$380-$3B6` c14 | 5 | 500 | Two shutter pieces at x `$E0`/`$100`, y `$F0`. Animate open/close (`$396…$390`, 25/50 f holds), then `$BE23` sets "no contact" and closes (UNCONFIRMED). |
| **snake_chain_a** | `$5575` (8 × `$57FE` in `$F000-$F0FF` or `$F100-$F1FF`) | `$57FE` | segments `$400-$41F` set, c5 (1x1) | head 1 (others 250) | head 0, `$40`→3000 on seg 7 | Segment roles `+$11`: `$48` head, `$4D` body, `$54` tail. Start timers 5,10…40. **Head** (`$56F6`) steers toward the player while it is inside the box Y `$48-$A7`, X/2 `$40-$B7`, otherwise toward the screen centre (`$78`,`$80`); 16 headings. **Body** copies the heading of the record before it (`ix-$10`). **Tail** fires `$4C6E` bullets when lined up with the player. Death `$5616` toggles immunity. Kill rules UNCONFIRMED. |
| **snake_chain_b** | `$5A9C` (8 × `$5D25`) | `$5D25` | claw chain `$460-$47F` c6 | head 3 | 5000 | Same engine (`$5B87`...). |
| **coin egg** | `$5523` → task `$3B6D` | `$5548` | dragonfly `$133` | 4 | 3000 | Flies left 3 px/f. No contact. |

### 6.1 Bosses (object side; scroll/halt in levels.md §2)

| boss | template | sprite | parts / HP | behaviour |
|---|---|---|---|---|
| `$69D0` (sect. 1) | `$69F7` → `$FB00` | 8x4 `$4A0-$4BF` c14 | `+$10` = **3 bars × 20 hits** (`+$0B=$14`). Bars drawn by `$0897` as `$6C-$6F` at `$D137`. | Spawns at (y `$60`, x `$140`) flashing c14/c15 for `+$11=$40` steps. Starts tasks slot 3 `$3522` (laser burst `$3613` ×8 every 60 f) and slot 4 `$36B6` (homing missiles `$4B89` from sub-record `$FC80`, only when y is in `$30-$A0`). Moves vertically 1 px/f toward the target Y (8-frame steps, limits y `$20-$A0`, `$6A3F`). Each emptied bar (`$6AE4`): bars−1, redraw, immune flash `$6B0F` (c8/c15), HP 20 again. Before the last bar `+$15` = `$58` (30000). Score per bar: `$38` → 1000. |
| `$6C12` (3, 5) | `$6C39` | `$4C0-$4DF` c14 (bone dragon) | **6 × 20** | Same engine (`$6C66`...), tasks via `$3527`/`$36BB` variants (UNCONFIRMED). |
| `$6DB4` (7-9, ×5) | `$6DDB` | `$4E0-$4FF` c5 (battleship) | **8 × 20** | Same engine plus aim (`$6E08`...). Probe: all 5 use code `$4E0`/c5 at spawn. levels.md notes different looks; what selects a variant is UNCONFIRMED. |
| wheel `$7192/$719C/$71A6` | 8 × `$721C` (2x2 in `$F600-$F9FF`) + core `$73DD` (`$FA00`) | parts `$430-$436` c5; core `$440` (c8/c15 flash), `$490-$496` | core 4 × 20 (`+$10=4`, `+$0B=$14`), 1000 per bar; parts HP 0, immune flags `$87` | The wheel itself is BG (levels.md). The parts (native `$723F`) fire bullets / beams `$7333`. Core logic `$7400-$752A`. UNCONFIRMED detail. |
| final `$5FC3` | 8 × `$6372` (2x2 in `$F600-$F9FF`) | rotating parts `$600-$6BF`, `$700-$73F` c3 | parts HP 250 (one gets HP 20 / score index → 300000) | Start timers `$0D,$1A,…,$4E` (staggered). Linked chain (`$60AB...`, death `$602E`). UNCONFIRMED. |

Boss hit rules (`$2D92`):
- **Each player shot** that overlaps the 16+s × 3+s box (§7) costs 1 HP and plays sound `$17`.
- **Non-piercing shots** turn into a hit spark.
- **Contact** box ±24 px Y / ±48 px X kills the player.

---

## 7. Collision

All tests are centre-to-centre boxes in (Y, X/2) space, using `+$17`. They are strict `<`.

| test | routine | condition |
|---|---|---|
| player shot vs small | `$2591` | shot `+8==$80`, obj flags b0 clear: `|o.y − s.y| < o.C+s.C` and `|o.x2 − s.x2| < o.D+s.D` |
| player shot vs 2x2 | `$29C7` | `|o.y+8 − s.y| < o.C+s.C`, `|o.x2+4 − s.x2| < o.D+s.D` |
| player shot vs boss | `$2D92` | `|o.y+$18 − s.y| < o.C+s.C`, `|o.x2+$1E − s.x2| < o.D+s.D` |
| small vs player | `$2617` | `|p.y+8 − o.y| < o.E`, `|p.x2+4 − o.x2| < o.F` |
| 2x2 vs player | `$2AD5` | `|p.y − o.y| < o.E`, `|p.x2 − o.x2| < o.F` |
| boss vs player | `$2E16` | `|o.y+$10 − p.y| < o.E`, `|o.x2+$18 − p.x2| < o.F` |

So the half-sizes in pixels are:
- Y: `C` (or `E`)
- X: 2×`D` (or 2×`F`)

Typical values:

| object | shot box | contact |
|---|---|---|
| 2x2 enemy (`$0C/$06`, `$10/$08`) | ±12 × ±12 px (plus shot size) | ±16 × ±16 px |
| enemy bullet | — | ±12 × ±12 |
| pickups | — | contact ±24 × ±24 |

The shot's own `+C/+D` is in flow_player.md.

On a hit:
- If the shot's `+7 == 0` (not M.B.L.), the shot becomes a spark: `+8=$C0`, `+$F=$10`,
  code `$1C`, colour 8.
- Object `+B`−1. At 0 it dies:
  - **Small object:** sound `$12`.
  - **2x2:** sound `$11` plus its item drop.
  - **Score:** `$2272` credits the shooter's score (`$E617` P1 / `$E627` P2, BCD, displayed ×10).
    Attract mode (`$E010=0`) gives no score.
- Shots are tested against small objects on even `$E003` and against big/boss on odd `$E003`
  (every frame in combined mode `$E014`≠0). **Piercing shots therefore lose at most 1 HP per 2
  frames per target.**

Contact with the player:
- **Skipped when:** the object has flag b1, the player is not `$80`, the player has `+$0E`≠0
  (respawn invulnerability), or the debug DIPs DSW0 b0+b7 are low.
- **Enemy** (`+A==0`): `$222C` kills the player. The enemy then dies too, giving its score to that
  player.
- **Pickup:** the item effect (§4).
- **Terrain** is separate. Enemy terrain is `$07C0`/`$082F`, which reads the bank-2 bitmap at
  `$A000` (levels.md). Player crush death is B2:`$84B1`.

### 7.1 Score table (`$2337`, index = `+$15`; value = 8 BCD digits × 10)

| index | `$08` | `$10` | `$18` | `$20` | `$28` | `$30` | `$38` | `$40` | `$48` | `$50` | `$58` | `$60` | `$68` | `$70` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| points | 50 | 100 | 200 | 300 | 500 | 800 | 1000 | 3000 | 5000 | 10000 | 30000 | 50000 | 80000 | 100000 |

Verified in `play1`: two jet kills raised `$E610-$E617` by `00000020` each, and the HUD showed 200.

---

## 8. Sprite output and Genesis budget

- **Composition rules** (`metasprites.json` → `rules`):
  - 1x1
  - 2x2 = codes `c, c+1, c+8, c+9` at (0,0) (16,0) (0,16) (16,16). The sprite sheet is 8 codes wide.
  - boss 8x4 = `c+r` at (16·(r%8), 16·(r/8)), r = 0..31
  - snake = 8 independent 1x1 segments
- **Colour** comes from the motion step's attr. The game flashes by alternating colours on
  consecutive 1-frame steps: hit flashes c8/c15, POW c4/c5/c13, bullets c8/c7.
- **Frames per family:** `metasprites.json` → `family_frames`. This is a static crawl of motion
  scripts and natives inside each family's code region. It is heuristic, but every code was
  checked against the rendered sheets.
- **Shared animations:** `shared_animations` (explosions, bullet).
- **Draw order** (MAME): regions `$F700-$F7FF`, then `$FE00-$FFFF`, then `$F800-$FEFF`, then
  `$F000-$F6FF`. Later regions are drawn on top.
  - Players, small objects and the first big slot ( `$F600`) are on top.
  - Pickups and bonuses (`$FF00`) sit under the boss bottom row and the 2x2 enemies.
  - Within a region MAME loops from the high address down, so lower addresses end up on top.
    UNCONFIRMED from memory of `sidearms.cpp`.

**Peak sprite usage, MAME probe.** Conditions: invincible, full power, P1 only, each section run
16000 frames, `reports/oracle/obj_sNN`.

| section | max 16x16 sprites visible | max per scanline | Genesis units (2x2 = one 32x32, boss = 8) | units/line | sprite px/line | frames with px/line > 320 |
|---|---|---|---|---|---|---|
| 1 | 89 | 31 | 37 | 20 | 512 | 937 |
| 2 | 55 | 27 | 27 | 20 | 432 | 16 |
| 3 | 91 | 36 | 37 | 24 | 592 | 2488 |
| 4 | 63 | 28 | 36 | 20 | 464 | 125 |
| 5 | 51 | 18 | 22 | 12 | 288 | 0 |
| 6 | 95 | 34 | 42 | 23 | 544 | 2023 |
| 7 | 93 | 30 | 41 | 23 | 480 | 1532 |
| 8 | 98 | 31 | 44 | 21 | 496 | 1642 |
| 9 | 95 | 27 | 41 | 22 | 432 | 625 |
| 10 | 61 | 29 | 34 | 23 | 464 | 679 |

The `play1` trace (normal power, stage 1) peaked at 38 visible sprites and 19 per line.

Takeaways for the port:
- **Sprite count is fine.** With 32x32 hardware sprites the object count stays under 45, well under
  80. The arcade's 16x16 sprite count (up to 98) only matters if every sprite is copied 1:1.
- **Scanline pixels are the real limit.** Boss fights exceed the Genesis 320 px/line (H40) budget,
  up to 592. The worst case is the boss row (128 px), the 2x2 enemies beside it and the bullets.
  - Lines over budget: about 3-15% of frames in the boss sections.
- **Mitigations:**
  - draw the boss (or its static parts) in a plane
  - flicker or priority-rotate the `$F000` small objects
  - cap the bullet pool. The arcade cap `$E017` is already 2-8 below stage 10.

---

## 9. Unconfirmed / open

- Full native detail is only partly traced for these families:
  - trooper_yellow, trooper_red, trooper_hover
  - pod_vertical's `$AC24` exit and pod_column_pow's `$AA5F` path
  - the turret_spike exit
  - barrier_pair
  - eye_turret closing
  - snake kill rules
  - wheel parts and core
  - final boss
- What makes the `$6DB4` bosses look different (levels.md says the sheets differ; the probe
  showed the same template and code `$4E0`).
- Who sets flag b6 (external kill request). Candidates: formation/bomb clearing.
- B2:`$8195`: the both-players target choice when neither is past `$60`.
- MAME's in-region sprite order (from memory, not re-read in this pass).
- The coin-egg purpose (`$5523`, `$E240`).
