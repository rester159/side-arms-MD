# Bosses, level progression and the ending

Modules: `src/boss.c` (framework, helpers, projectile/effect pool, VRAM block cache, death
explosions), `src/boss_sprite.c` (3 sprite bosses), `src/boss_wheel.c` (3 BG wheel bosses),
`src/boss_final.c` (final boss + ending), `src/boss_int.h` (private), `inc/boss.h` (public),
`src/level.c` (camera timeline), `src/bg.c` (BG engine, extended for bosses).
Data: `tools/build_bosses.py` -> `src/gen/boss_data.c`, `inc/gen/boss_data.h`;
`tools/build_levels.py` -> `src/gen/level_data.c`, `inc/gen/level_data.h`. Both run from
`tools/build_assets.py`. Arcade behaviour: `docs/re/levels.md` §2, `docs/re/objects.md` §6.1.

## Public interface (`inc/boss.h`)

| function | use |
|---|---|
| `boss_start(kind, id)` | level.c `EV_BOSS` (kind 0 sprite, 1 wheel, 2 final; id = arcade spawn routine) |
| `bosses_update()` / `bosses_draw()` / `bosses_reset()` | called by the front end (flow_game.c / flow_attract.c) |
| `BossHud boss_hud` | `active`, `bars` (remaining HP bars), `hits` (hits left in the bar, 20 per bar), `serial` (changes when the bars change). The arcade draws one `$6C-$6F` group per bar at text `$D137` ($0897) |
| `boss_ending_active()`, `boss_game_cleared()` | the ending task; the front end returns to the title when cleared ($0B84: the game does not loop) |
| `level_halt()`, `level_warp(section, boss)`, `level_bullet_speed` | level extras (declared in boss.h): `$8057` halt, debug/test warp, `$E050` bullet speed level loaded with the stage music |

Services used when linked (weak references, nothing breaks without them):
`enemy_bullet_spawn()`, `enemy_bullets_live()`, `enemies_clear()` (enemies.h), `hud_text()`
(hud.h), `item_spawn_pow(x, y)` (POW capsule `$4DCF` at a Genesis top-left - **not provided yet**,
so bosses drop no POW), `en_target_y` / `en_target_x2` (the enemy module's target choice B2:$813A).

## Coordinates

Boss logic runs in arcade sprite coordinates (raw x 64..447, y 16..239; collision boxes in
(y, x/2) as the arcade). Screen = raw - (96, 16) - `boss_shift`. **Sprite bosses use
`boss_shift = 32`**: the arcade puts the 128-px body at raw x $140, flush with the right edge of
its 384-px screen; on the 320-px Genesis view the last 32 px would be cut off, so the whole fight
(body, beams, missiles, explosions, collision tests against the players) is drawn 32 px further
left. Relative geometry is unchanged. Wheels and the final boss are tied to the background and use
no shift.

## Sprite bosses ($69D0 / $6C12 / $6DB4)

| | type 0 (sect. 1) | type 1 (3, 5) | type 2 (7-9) |
|---|---|---|---|
| body | $4A0 c14 | $4C0 c14 | $4E0 c5 |
| bars x 20 hits | 3 | 6 | 8 |
| vertical tracking | 1 px/f, y $20-$A0, 8 steps | 2 px/f, $28-$98, 11 steps | 3 px/f, $30-$90, 10 steps |
| last bar | 30000 | 50000 | 80000 |
| extra | | | ~27 % ($E00A += $63 < $46) charge at the aim direction, 4 px/f left, flashing c0/c8, back at 4 px/f |

Sequence (all from the native code): sound $13 + $32/$33/$34; intro flash c14/c15 x 64
(128 frames, immune, no contact); then laser task ($3522/7/C: 8 beams `$3613` from body cells
(1,2),(1,3),(3,2),(3,3), odd records without contact, first after 60 frames, then table x 6
frames) and missile task ($36B6/B/C0: homing missile `$4B89` up from cell 12 if y >= $30, one
frame later one down if y < $A0, both under the bullet cap; table x 6 frames). Every decision
($6A3F) re-enables contact/shots and moves 8-frame steps towards the target Y; the rest of the
step budget is spent holding. Shots hit the point (y+$18, x+$3C), box 16 x 6 (+ shot box), on
odd frames, 1 HP and sound $17 per shot. Contact box (y+16, x+48) +-24 x +-48. An emptied bar
($6AE4): score 1000 (the last bar its own index), immune flash c8/c15 x 6, 20 HP.
Death ($6B4E/$6B71): enemies, bullets and boss shots wiped, weapon tasks stopped, 4 POW in a
diamond, flash c8/c15 x 39 then gone; task $3916: sounds $00/$14/$2A, 45 explosions
(`$397C` offsets, 3 frames apart), 300 + 180 frames, then `level_resume()` ($8051).

Genesis: the body is 8 hardware sprites of 32x32 (4x2 blocks of the 8x4 cells). Their patterns
come from a build-time bank of pre-converted 32x32 blocks (`boss_block_*`, 136 blocks / 68 KB:
sprite boss bodies in every colour they show, wheel pods/core, final boss segments, explosions)
and live in VRAM blocks **borrowed from the BG metatile cache** (`bg_reserve_blocks`, one cache
slot = 16 tiles = one 32x32 sprite). The boss module keeps them in a small LRU with a hash hint
(`bc_draw`, <= 4 block uploads = 2 KB DMA per frame); the body's colours are loaded ahead during
the intro so hit flashes never wait. Beams, missiles and bullets use quarter blocks the same way
(`bs_draw`, 16x16). Both are far cheaper per sprite than the generic sprite cache's slot search.
Measured along every camera path, the view never needs more than 33 of the 56 cache slots (boss
arenas <= 20), so up to 27 blocks are lent during a fight (sprite bosses 16/24 + 3, wheels
10 + 1, final boss 24 + 1). Colour 15 (the arcade's flash partner) is an all-black palette: those
frames hide the body.

## BG wheel bosses ($7192 / $719C / $71A6) - the native solution

The arcade wheel is background art; it turns because the boss code jumps the BG scroll between
three copies of the wheel drawn in the world map (`$700B`, tables `$70D2/$70E2/$70F2`), one step
every 8/5/3/1 frames as the core goes from 4 to 1 bars. On the Genesis a camera jump means a full
plane reload (88 cells, up to ~50 metatile uploads = 25 KB) - impossible every frame.

Solution (`bg_frames_*` in `bg.c`, data from `build_bosses.py`):

1. **Build time.** For each wheel, the 11x8-cell rectangle seen from each copy becomes a *frame
   map* expressed in the palette zone that is active at the halt (simulated along the game path).
   Metatiles of the other copies that the zone lacks (22 for wheels 2 and 3) are converted as
   *extra metatiles* quantized to that zone's two palettes. The union is 44 / 36 / 40 metatiles.
2. **Halt.** The camera is put on copy 0 (2 px from the halt position) and stays there.
   `bg_frames_begin()` pins every metatile of the union in the cache (6 per frame, extras DMA'd
   from the generated data), then pre-renders each frame as a complete 64x32 plane image
   (3 x 4 KB on the SGDK heap; rendered in slices over ~15 frames so no frame overruns).
   Turns requested before that are skipped (the arcade core is immune for ~170 frames anyway).
3. **Turning.** `bg_frames_show(n)` queues one 4 KB DMA of image n. No tile upload, no CPU work:
   the turn is affordable every frame. The eight pods ride the 24-point orbit (`$7102`) one notch
   per turn, as in the arcade.
4. **Death** (`$74E0`): `bg_frames_end()`, the camera moves to the next section start (copy 3,
   `level_start(next)` + halt), task `$3A06` explodes and resumes the scroll after 480 frames.

Pods (`$721C`): enter hidden at x $1BF after their start delays, BG-locked, 250 frames idle, then
every 15 frames `$E00B += $4D >= $E6` fires: wheel 1 an aimed bullet, wheel 2 a beam pair `$7333`,
wheel 3 a homing missile; immune and harmless themselves. Core (`$73DD`): 2 x 122 frames hidden,
15 armour turns, then 4 bars x 20 (box (y+8, x+8) 18 x 4), 1000 per bar and 50000 for the last;
a lost bar resets the turn counter and flashes $440 c8/c15.

## Final boss ($5FC3) and ending

Eight 2x2 segments enter from x $1BF, 13 frames apart. 14-frame steps along 16 headings (tables
`$6312` head c3, `$62F2` hurt head c8, `$6332` body, `$6352` tail, decoded at build time).
Head: turns one notch towards the player while inside the box y $56-$91, x/2 $66-$87, else
towards the centre ($78, $80); fires 8 bullets (directions 0, 4, .. 28) when its half of the
bullet pool is empty; 20 HP. Body: copies the heading of the segment ahead, HP refilled to 250
(a shield). Tail: same, bursts in the other 8 directions. A dead head makes the next segment the
head (hurt colour for 8 steps, then 20 HP). The sixth head (slot 5, score $78 = 300000) dies with
the tail two behind: the last three explode (0 / 11 / 22 frames late) and task `$3B8A` runs:
120 frames, sound $2C, "CONGRATURATIONS ... THE END" for 1560 frames, staff roll (`$3BF9`) for
540 frames, then `boss_game_cleared()`. Text goes through `hud_text()` (arcade text column c ->
HUD column c - 12, row r -> r - 2).

## Level progression (`level.c`, `build_levels.py`)

* `EV_HALT` ($8057) stops scroll *and* script; the live directions (`level.dir_x/dir_y`, read by
  the player's push-back and BG-locked objects) read 0 while halted (`$1FC9`); the latched script
  directions return on `level_resume()` ($8051).
* Latched directions survive `level_start()` (only the script writes $E08A/$E08B): after wheel 2
  the scroll keeps moving right from C80,500 until section 5's first records fire at C81,500.
* `EV_NEXT` (new): each section's script ends with a call of the teleport that opens the next
  section (B0:$8194-$82CB); `build_levels.py` turns it into `EV_NEXT` (keeping its spawn index so
  the enemy tables stay aligned) and `level.c` starts the next section.
* `EV_MUSIC` carries the enemy-bullet speed level the arcade loads into `$E050` with the stage
  music (B0:$80CA, table $813C + 8*stage, default difficulty) -> `level_bullet_speed`.
* `dbg_warp` (RAM, test hook) = (section + 1) | (boss ordinal << 8) -> `level_warp()`.

## Verification

Headless runs with `tools/run_rom.py` (`SIDEARMS_BUILD=.local/build-bosses`), pads driven by the
runner, the player kept invulnerable by RAM writes, enemy spawns muted (`en_dbg_mute`):

* **Camera timeline vs MAME traces** (`reports/oracle/stage01..10`), counted in game frames from
  each section's start teleport: sections 1, 3, 4, 7, 8, 9, 10 match every trace sample within
  1 px and the first halt within 1 frame (e.g. section 4: 16123 vs 16124 frames). Section 2 and 5
  differ by the arcade slowdown documented in levels.md (128 / 151 frames); section 6's trace is
  distorted by the debug start's X creep, its boss halt (6811) equals the trace value of
  levels.md.
* **Sprite bosses** (sections 1, 3, 7): intro, tracking, lasers, missiles, charges (type 2),
  bars 3/6/8 x 20 hits, scores 32000 / 55000 / 87000 for a full kill (1000 per bar + last bar),
  death flash, explosions, resume after 616 frames, section transition.
* **Wheels** (sections 2, 4, 9): the wheel turns, pods orbit and fire, core 4 bars (53000 points),
  death -> next section start, halted 646 frames, resume. No lag frame while turning (the image
  DMA replaced an earlier copy loop that cost a frame every turn).
* **Final boss**: 6 heads killed in sequence, final explosions, ending text and staff roll on
  the window plane, `boss_game_cleared()` after 2346 frames (arcade 2340), front end back to the
  warning/title with the 300000 score ranked.
* **Performance** (`prof_line`, player firing, enemies muted): frame work averages 80-90 lines in
  sprite boss and wheel fights and ~124 in the final boss fight, peaks ~200-235; no lag frame
  during any fight. Remaining lag frames: camera jumps (warp, section change, wheel death zone
  load), the frame a boss appears, and 2 frames at the wheel halt.

## Deviations / gaps

* Sprite bosses are drawn 32 px left of the arcade position (see Coordinates).
* Wheel spawn wipes all enemies (`enemies_clear`); the arcade clears only the big-object area.
* Wheel bar loss: the arcade's text-layer "crack" animation (task `$365F`, 5 frames of graphics
  characters over the wheel) is not drawn; only its sound ($15) plays.
* POW capsules at boss deaths need `item_spawn_pow()` from the items module (not provided yet).
* The final boss bursts check that all 8 of their bullets are gone; the arcade checks 4 of them.
* Local boss bullets (final boss bursts, and pod bullets if the enemy module is absent) do not die
  on terrain ($4940).
* What gives the five `$6DB4` bosses different looks is still unknown (all use $4E0 c5).
* The ending's `&` characters are not in the HUD's ASCII set.
