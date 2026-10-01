# Enemies, enemy bullets, pickups and effects

Native Genesis implementation of every normal enemy family of the 10 sections, the enemy bullets
and missiles, the POW capsule and item pickups, the hidden bonuses and free-standing explosions.
Bosses live in the boss module (docs/bosses.md); this module gives them bullets, aiming, POW drops
and explosions.

Behaviour reference: `docs/re/objects.md` (objects), `docs/re/flow_player.md` §6 (items, scoring).
Every rule in the C code cites the arcade address it implements.

| file | contents |
|---|---|
| `inc/enemies.h` | public API (level, game loop, bosses) |
| `src/enemy_int.h` | Enemy struct, pools, engine helpers for the family files |
| `src/enemies.c` | pools, motion engine, terrain, collisions, spawning, aiming, bullets, drawing, RNG |
| `src/enemy_air.c` | drum ship, jet (homing fliers) |
| `src/enemy_pods.c` | POW pod column, vertical pods, snake chains A/B |
| `src/enemy_troopers.c` | tan / green / yellow / red / hover troopers, surfacing robot |
| `src/enemy_ground.c` | bomb column, crab / missile / spike / dome turrets, eye turrets, orb burst, mines, barrier |
| `src/enemy_shots.c` | bullet terrain spark, homing missiles |
| `src/items.c` | carried-letter drops, pickups, POW cycle, hidden bonus reveals, `item_spawn_pow` |
| `src/fx.c` | free-standing explosions (`fx_explosion`) |
| `tools/build_enemies.py` | build-time generator -> `src/gen/enemy_data.c`, `inc/gen/enemy_data.h` |
| `tools/enemy_trace.py/.lua` | verification against MAME (development only) |

## Design

### Objects and pools

An enemy is a 40-byte `Enemy` struct in one of three fixed pools whose sizes are the arcade's:
16 small objects (bullets, missiles, bombs, snake segments), 9 big 2x2 objects (enemies), 8
pickup objects (pickups, hidden bonuses, mines, orb fragments). The sizes are part of the
behaviour: as in the original, a spawn that finds its pool full is dropped (objects.md 1.1: 10
of the 210 stage-1 spawns are dropped in MAME), and the bullet cap counts live bullets.

Positions are Genesis screen pixels of the sprite's top-left (arcade sprite coordinates minus
(96, 16)). The arcade's 8-bit y wrap and 9-bit x are kept by the movement code, and macros give
the natives the arcade view (`AX`, `AY`, `X2` = the stale `+$17`, `SUB_X16`/`SUB_Y16` = the 2x2
sub-record coordinates as of the last move).

### Motion scripts (data) and behaviour functions (code)

Each object plays a *motion script*: a list of steps "show sprite code/colour for N frames while
moving (dy, dx) px per frame". A control step can jump, remove the object, or call a family
*behaviour function*, which typically aims at the player and picks the next script. This is the
arcade's own split between data and code, kept because it makes the enemy patterns
data-exact while the decisions are ordinary C:

- the scripts are generated from the ROM into the ROM array `en_mot[]` (6-byte steps); the C code
  never interprets arcade bytes at run time;
- every decision is a small C function per behaviour (`drum_steer`, `crab_think`, `snake_step`,
  ...), written from the arcade routine's behaviour, not transliterated.

Per frame each object: kill request -> background lock (moves with the camera) -> step timer ->
move (removed when it leaves the arcade screen) -> terrain test (on contact: back to the old
position, family terrain handler) -> collisions on its frame parity.

### Generated data (`tools/build_enemies.py`)

The generator re-runs the spawn simulation of `tools/extract_spawns.py` (same code, in-process)
to get the full 32-byte record of every object every script event creates, and reads motion
scripts and tables from the ROM. The C code asks for what it needs by name, and only that is
generated (grep of `src/*.c`):

| symbol | meaning |
|---|---|
| `MOT_xxxx` | step index of the script step that is at arcade address $xxxx |
| `MOTTAB_xxxx_n` / `MOTPTR_xxxx_n` | n step indices read from a ROM word table (entries = steps / motion pointers) |
| `ROMB_xxxx_n` | n raw ROM bytes |
| `TPL_xxxx` | `EnemyInit` of the object template at $xxxx |
| `AI_xxxx` | behaviour id of the arcade native at $xxxx |
| `/* @native xxxx */ void f(Enemy *e)` | f implements the native(s) at $xxxx |

Outputs: `en_mot[]` (2462 steps), `enemy_inits[]` (150 object initialisers), the per-section
spawn tables `en_spawn_sections[10]` (index = `EV_SPAWN b` of the level timeline, built in the
same order as `tools/build_levels.py`, which the generator checks against `level_data.c`), the
behaviour table `en_ai_table[]` (119 natives, all implemented), bullet direction tables for speed
levels 3-6, the aim table ($0780), the score table ($2337), the POW chain, the eye-turret
formations and the template/routine maps used for the attract demo. A script that would run into
code bytes (only reachable after the object has left the screen) is cut with a kill step.

### Spawning

`enemy_spawn_event(section, index)` creates the objects of one script record:

- sequential allocations that stop at the first full pool (`call alloc / ret`, $0384);
- snakes (8 consecutive records in one half of the small pool) and bomb columns (4 consecutive);
- eye turrets (big slots 3-7 only, random formation from $B70E/$B71E/$B72E);
- orb burst (only when all 8 pickup slots are free); barrier pair (random start phase);
- carried item letters: the letter records ($82CC-$830E) set the pending letter, the next spawn
  routine that calls $08D2 hands it to its object; the POW pods set 'P' themselves.

`enemy_spawn_record(cmd, target)` handles raw script records of the attract demo (spawn routine
calls and template SPAWN records).

### Collisions (objects.md 7)

Centre-to-centre boxes; small objects and pickups test on even frames, big objects on odd frames
(every frame while the combined robot is out). Player shots: each overlapping flying shot calls
`shot_hit()` and costs 1 HP; at 0 HP a big enemy plays sound $11, scores (`player_add_score`),
drops its carried letter and dies; a small one plays $12 and scores; a pickup or hidden bonus
dies without score (POW cycle / reveal). Contact: a hostile object kills a non-invulnerable player
(`player_kill`) and dies itself (scoring for that player); a pickup calls `player_apply_item()`
then vanishes with sound $12 and its score (the alpha capsule vanishes first and combines).

### Bullets, aiming, RNG

- `en_aim` is $06E8/$0715 (octant + 5-sector ratio test in (y, x/2) space, table $0780), against
  the target chosen every 8 frames by the B2:$813A rule (both players: the more advanced one past
  the threshold, else the better armed one).
- Enemy bullets ($4000) use the direction table of the stage's speed level
  (`level_bullet_speed`, set by level.c with the music) and are refused when the live-bullet count
  reaches `level.rank` (+ the difficulty offset, `game_rank_offset()`).
- The arcade RNG $E008-$E00F is reproduced exactly: it steps every 3rd frame after the object
  update (the credit task's turn), $E008 += 1 and each next byte += previous + an odd constant
  (running sum starting at 1, measured in MAME). Natives add their constants to `en_rng` /
  `EN_E00F` as the arcade does.

### Drawing and the sprite limits

Everything goes through `spr_16` (1x1) / `spr_32` (2x2 composites). Order front to back follows
MAME's region order: small objects, explosions, big slots 0-1, 4-8, pickups, big slots 2-3.
The arcade peaks at 44 Genesis units and 592 px on a line (objects.md 8). When the estimate of
16-px units in any 32-line band exceeds 20 (320 px), the drawing order inside each group rotates
every frame, so the VDP's per-line overflow drops a different object each frame (flicker) instead
of always the same one.

## Verification

`tools/enemy_trace.py` runs the arcade in MAME (`tools/enemy_trace.lua`: debug-DIP invincible,
idle player, optional autofire, optional stage select) and the cartridge headless with the same
idle player, logs every object every frame in arcade units, aligns both on the camera, syncs the
RNG and the target-pick counter from the arcade at the first scroll step, and compares spawn
moments, positions and whole paths. Results (this build):

| run | result |
|---|---|
| stage 1, idle | camera identical; 157/157 big enemies spawned on the arcade's frame and slot; all 157 identical paths (240 f), bullets 61/61, pickups 2/2; every object identical frame by frame for the whole stage (6550 frames) up to the boss's lasers, except one frame of the surfacing robot's missile code (see deviations) |
| stage 1, autofire | identical frame by frame for the whole 4953-frame trace (QA, docs/qa.md): 145 big / 65 small / 6 pickups with identical paths, kills, explosions, POW drop and cycle, pickups, speed-up, the star (AUTO $11) and all 358 AUTO $11 / $10 shots. (The earlier "fires nothing after the star" was the harness: autofire input 2 frames off and `frame` not synced to $E003, see docs/qa.md) |
| stage 2, idle | identical frame by frame for the whole 7443-frame trace (QA): 160 big / 166 small / 8 pickups, including the scroll crush (both die at frame 6707 at sprite x 80) and the respawn |
| stage 4 | identical for 2190 frames until the player positions differ (player module) |
| stages 3, 5, 8 | spawn moments and early paths identical; divergence starts with player position / level halts (player and level modules) |
| bosses (7, 9) | the arcade's boss tasks write their lasers straight into the small-object region (overwriting snake segments, $3522); the port's bosses have their own objects |

Spawn timing of every section was also checked by the generator against the level timeline
(same event count and order as `level_data.c`). The two family agents checked their families
against their own MAME traces of stages 1, 2, 3 and 5 (see the comments in the family files).

Performance (headless, invincible autofiring player warped into a section, 4000 frames):
`enemies_update` averages 20-34 scanlines and peaks at 48-76 with 20-25 live objects (about 2.5
lines per object plus ~5 fixed; empty pools, absent players and idle explosions are skipped);
`enemies_draw` costs ~8 lines of its own plus `spr_16/spr_32`. Frames still dropped in the busiest
sections (section 9: 4% of frames) come from the whole frame (`prof_line` mean 110-130 lines) with
spikes in sprite pattern uploads (draw up to ~240 lines on single frames). Two problems outside
this module were found and reported during this work: the original `find_slot` scan in sprites.c
(~2000 cycles per sprite; an O(1) hint lookup halved the draw time; the sprite owner has rewritten
it) and a GCC m68k -O3/LTO miscompile in player.c (`EXTEND_TABLES[extend_setting & 3]` read a long
at an odd address: address error on the first kill; fixed by making `extend_setting` a u16). Test
hooks: `en_dbg_nodraw`, `en_dbg_mute`, `en_dbg_spawn` (spawn one event), `en_rng`/`en_rnd`/
`en_rng_div`/`en_target_tick` (RNG and target sync); `en_prof_update`, `en_prof_draw`,
`en_prof_nobj` hold the last frame's figures.

## Known deviations / gaps

- (fixed in QA) Score credit: the shooter is credited unless it has no lives left (then the other
  player), `player_credit()`, arcade `$2516`.
- A terrain handler that sets a motion makes the arcade move and test terrain again with no limit
  ($27EE -> $2856); the port re-runs it at most twice per frame (no arcade data needs more, and it
  cannot hang).
- One frame visual details not reproduced: the surfacing robot's missile shows the robot's code
  $200 for one frame; orb fragments keep colour 0 until their first step (invisible anyway).
- Kill-request flag ($40): kept as in the arcade (death restarts while set); nothing in the
  enemies sets it.
- Coin easter egg ($5523 dragonflies, number = coins inserted >> 4): not spawned (no coin counter
  on the Genesis).
- The bullet speed level per difficulty other than the default comes from level.c (built for
  difficulty 3).
- Homing missiles circle an idle target until they leave or hit it, exactly like the arcade; with
  an invincible test player they never die.

## Interface assumptions (other modules)

- level.c calls `enemy_spawn_event(section, b)` for every `EV_SPAWN`; `level.rank` = script rank,
  `level_bullet_speed` = $E050 level; `level.dir_x/dir_y` are 0 while halted.
- The game loop calls `enemies_update()` after `players_update()` (not while
  `players_world_frozen()`), `enemies_draw()` after `players_draw()`, `enemies_clear()` at game /
  attract start.
- Player module: `Shot.active == 1` = flying, `half_w/half_h` in pixels around (x+8, y+8);
  `shot_hit()` explodes non-piercing shots; `player_kill()` ignores invulnerable players;
  `player_apply_item()` applies the pickup effect and plays its sound ($1A/$1B/$1C/$1D) and handles
  item 6 (combine) only when not combined; `player_add_score()` handles attract mode and extends.
  `players[i].level[1..5]` are the weapon levels (target choice).
- Bosses: `enemy_bullet_spawn`, `enemy_aim`, `enemy_bullets_live`, `fx_explosion`,
  `item_spawn_pow`, `en_target_y/en_target_x2`.
