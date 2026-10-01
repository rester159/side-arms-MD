# Side Arms MD: Capcom's 1986 arcade shooter, rebuilt natively for the Sega Genesis / Mega Drive

Hi everyone! I'd like to show you a project I've been working on: **Side Arms MD**, a port of Capcom's
arcade game **Side Arms – Hyper Dyne** (1986) to the Sega Genesis / Mega Drive.

Side Arms never came out on the Genesis. It got PC Engine and home-computer versions, but nothing on
Sega's 16-bit machine. This port tries to fill that gap. It's built to play like the arcade game,
feel at home on the Genesis, and run at a solid 60 frames per second.

The whole game is in: all 10 sections, every enemy type, every boss, the final boss and the ending,
2-player co-op, and the combined robot. There's also a full front end with options, and settings and
high scores are saved.

**Source code:** https://github.com/rester159/side-arms-MD

Below I explain how a port like this is made, in plain language, and then go through what's in the
game. At the end there are a few questions I'd love your answers to.

---

## Part 1: How do you "port" an arcade game?

### Two very different machines

The Side Arms arcade board and the Genesis are not alike. Here's a rough comparison:

| | Side Arms arcade board (1986) | Sega Genesis (1988) |
|---|---|---|
| Main processor | Z80 at 8 MHz | 68000 at 7.6 MHz (a different chip family, with different machine code) |
| Screen | 384 × 224 pixels | 320 × 224 pixels |
| Colours | 4 bits per channel (4,096 possible colours), with lots of palettes on screen | 3 bits per channel (512 possible colours), at most 61 on screen at a time |
| Background | a huge 4096 × 4096 pixel world map read straight from ROM | 64 KB of video memory, which holds only a small part of a map |
| Sprites | 128 on screen | 80 on screen |
| Sound | two Yamaha YM2203 chips: 6 FM channels plus 6 square-wave channels | one Yamaha YM2612 (6 FM channels) plus one SN76489 (3 square-wave channels and noise) |

You can't copy the arcade program onto a Genesis cartridge. The processors speak different
languages, and the graphics hardware works in a different way.

### The approach: "native", not emulation

There are roughly two ways to port an arcade game:

1. **Translate the original code.** You convert the arcade program instruction by instruction into
   something the Genesis can run. It's faster to get working, but you end up with arcade code
   running on hardware it was never designed for. I tried this on an earlier port and it topped
   out at about 48 frames per second.
2. **Rewrite it natively.** You study the original very closely until you know exactly what it
   does, then write a new game from scratch for the Genesis that does the same things.

Side Arms MD uses the second approach. Think of it like transcribing a piece of music: I didn't copy
the original recording. I worked out the score note by note, then played it again on a different
instrument.

### Step 1: Reverse engineering, or "reading the score"

Before writing any game code, I took the arcade game apart to understand it:

- **Disassembly.** The arcade's program was turned back into readable instructions. That's how I
  found where the routines are that move the player, spawn enemies, run each boss and play each tune.
- **Measuring the real game.** I wrote automated scripts that run the original game in the MAME
  emulator with no screen. Frame by frame, they record where every object is, when enemies appear,
  how fast bullets fly and when the music changes. I call these recordings "oracles", because they
  give the correct answer to "what should happen on frame 4,356?"
- **Writing it all down.** All of this went into detailed notes covering the hardware, the game
  flow, the levels, every enemy and the sound program. Those notes became the specification for
  the port.

The rule I followed: **no guessing.** Every speed, timer, hit box, score value and spawn moment in
the port comes from the original. The source code says where each one came from: almost every rule
has a comment pointing to the exact spot in the arcade program it reproduces. When something didn't
match, I didn't make small adjustments until it looked right. I found the actual cause first.

### Step 2: Graphics

**The background.** The arcade draws its levels from a giant 4096 × 4096 pixel world map in ROM.
The Genesis can only keep a screen or two of map in video memory. So the port uses a "rolling
window": as the camera moves, new pieces of the map are loaded just before they scroll into view,
and the ones that leave are recycled. The world is built from 32 × 32 pixel blocks, and a cache
keeps the 56 blocks the screen needs at any moment. The port loads one column ahead of the camera,
a little each frame, so the scroll never stalls. I compared it with the arcade, and background
scrolling lines up with it pixel for pixel.

**The starfield.** On the arcade, the scrolling stars behind the levels come from a dedicated
hardware circuit. The Genesis doesn't have that circuit, so I calculated the circuit's whole star
pattern ahead of time and stored it as a background layer that the Genesis scrolls on its own. It
costs the processor almost nothing.

**The narrower screen.** The arcade screen is 64 pixels wider than the Genesis screen. The port
keeps the view centred on the arcade's view. Where it matters, things are moved to fit: for example,
the sprite bosses sit 32 pixels further left so they aren't cut off at the right edge. Everything
is still in the same place relative to everything else, so the fights play the same.

**Colour.** This was one of the hardest parts. The Genesis has fewer colour steps than the arcade
and fewer colours on screen at once. A build tool works out the best possible Genesis palettes for
each area of the game. Every level zone gets its own pair of fitted palettes, and each sprite picks
whichever of two shared sprite palettes suits it better. You can choose between two colour modes in
the options (more on that below).

**The HUD.** The scores, lives, weapon bar and speed meter are drawn on a separate screen layer.
A small timing trick switches that layer between the top rows and the bottom rows partway down the
screen, so the starfield still shows in the middle.

**No ROM data in the project.** The repository contains **none** of Capcom's graphics, sound or
data. When you build the game, the tools read *your own* copy of the arcade ROMs, check each file
against a list of known fingerprints, and convert everything into Genesis formats on the spot.

### Step 3: Sound

The arcade has two sound chips with 6 FM channels and 6 square-wave channels between them. The
Genesis has one FM chip with 6 channels, plus a simpler chip with 3 square-wave channels and a noise
channel.

- **Music:** the arcade's 6 FM channels map onto the Genesis's 6 FM channels, so the music is
  played by the same kind of synthesiser. A build tool converts every song into a compact Genesis
  format. It then plays every song back in a simulation and checks that all **12,081 notes and
  rests** start at exactly the right moment. If even one is off, the build fails.
- **Sound effects:** the arcade uses 6 square-wave voices for effects, and the Genesis has 3. The
  sound driver picks the 3 loudest voices at each moment and plays those. Some detail is lost, but
  the loud, important parts of each effect come through.
- **A custom sound driver:** I wrote a new sound program for the Genesis's second processor (a Z80)
  from scratch. It runs on its own timer at the arcade's music speed, about 249 updates a second.
  The music keeps perfect time even when the game is busy, and the main processor only has to say
  "play song X".

### Step 4: Gameplay

Gameplay is written in normal, readable C code made for the Genesis. Each player, enemy, bullet and
boss is its own small object with its own logic. The arcade's behaviour was copied very closely,
including some of its quirks. A few examples:

- Enemy groups are limited to the same number of slots as the arcade. If the arcade would drop an
  enemy because its slots are full, the port drops it too. That's part of how the game feels.
- Difficulty works as it does in the arcade: it controls how many enemy bullets can be on screen
  and how fast they fly, using the arcade's own tables.
- Points for kills go to the right player in co-op, using the arcade's rules, including the special
  cases for the combined robot.

**How do I know it plays the same?** I fed the same controller inputs to the arcade (in MAME) and
to the port, then compared them frame by frame. In stage 1, over almost 5,000 frames, the camera,
every enemy path and **all 358 player shots** appeared on the same frames and followed the same
paths. Player deaths from being crushed by the scrolling wall, and the respawns after them, also
happened on the same frame and at the same pixel.

### Step 5: Performance (holding 60 fps)

The arcade runs at 60 frames per second, so the port has to as well. The Genesis processor is about
as fast as the arcade's on paper, but it has a lot more work to do: it handles graphics tasks that
the arcade did with dedicated hardware.

An automated test bot plays every section from start to finish, in 1 player and 2 player, through
every boss to the ending. It counts every frame that misses the 60 fps target. The first version
dropped up to 14% of frames in 1 player and up to 23% in 2 player. Then I fixed the slow parts one
at a time:

- Big 32 × 32 sprites used to be assembled from pieces while the game ran. Now they're prepared
  ahead of time, and each one is a single fast copy.
- Converting the score to text used slow division. It's been replaced with a much quicker method.
- The HUD's screen-splitting trick used to interrupt the processor 28 times a frame. Now it does
  so twice.
- Background loading is now spread over several frames.

**Results (from the latest test run):**

- **1 player:** close to a locked 60 fps. Over a full run of each section, about 0.1% of frames are
  dropped, and most of those are at moments when the camera jumps to a new area. Section 9's
  boss fight is the heaviest, at about 1%.
- **2 players:** between 0.1% and 3% dropped, depending on the section. The worst cases are big
  waves with both players using rapid-fire weapons, or the combined robot. The original arcade
  slows down in some of the same busy spots.

The test bot also checks that the game never freezes or gets stuck, and that no sprite is ever lost.

---

## Part 2: The game

### Starting up

After the SEGA and CAPCOM logos, you choose between two ways to play:

**ARCADE mode: the original experience**
- Works like the arcade machine. Press **Start** to insert a coin, then Start again to play.
- Includes the attract mode with the warning screen, the title and ranking table, and both recorded
  demo plays from the arcade.
- The full arcade flow: the Earth intro, name entry, the continue countdown, game over and the
  ranking.
- **Secret:** on the INSERT COIN screen, enter **Up, Up, Down, Down, Left, Right, Left, Right** to
  open the **DIP switches**, like the switches on the real arcade board:
  - difficulty 1–8
  - lives: 3 or 5
  - bonus life: the four arcade settings
  - continue: on or off
  - demo sounds: on or off
  - colour mode

**HOME mode: made for playing on a console**
- A home title screen ("SIDE ARMS" with an **MD** badge) with START GAME and OPTIONS.
- **OPTIONS:**
  - **Difficulty:** EASY, the arcade's levels 1–8, or HARD. EASY and HARD are new and go one step
    past the arcade's range in each direction.
  - **Lives:** 1–7
  - **Bonus life:** the four arcade settings, or NONE
  - **Continue:** OFF, LIMITED (uses up your credits) or UNLIMITED
  - **Credits:** 1–9 per game
  - **Color:** ARCADE or VIVID
  - **Controls** (see below)
  - **Sound test:** every song and sound effect in the game

### Controls

Default layout: **A** fires left, **B** fires right, **C** switches weapon, **Start** starts the
game or inserts a coin.

In the **CONTROLS** menu you can:
- Move fire left, fire right and weapon select to any button.
- With a **6-button pad**, give X, Y and Z extra jobs: previous weapon, next weapon, jump straight
  to a specific weapon, or **LOCK FIRE**, which shoots in the direction you're facing without
  turning around. The defaults are X = previous, Y = next, Z = lock fire.
- Turn on **autofire** for each fire button separately. It fires at the same rate as the arcade's
  AUTO weapon, one shot every 4 frames.

Press A+B+C+Start together to go back to the mode select screen at any time.

### Colour modes

- **ARCADE:** the closest the Genesis can get to the arcade's original colours.
- **VIVID** (default): a bit more colour saturation and brightness. It makes up for the Genesis's
  coarser colour steps and for how dark many emulators show Genesis video. Greys stay
  neutral.

### What's in the game

- **10 sections** with horizontal, vertical and diagonal scrolling, played in order as in the
  arcade.
- **All the weapons**, each with its power-up levels: normal shot, BIT (orbiting helpers), S.G.
  (spread shot), M.B.L. (piercing beam), 3WAY, and AUTO (rapid fire) in both of its forms.
- **The POW system:** shoot the POW capsule to cycle through power-ups and speed-ups, and collect
  hidden bonuses.
- **Every enemy type:** troopers, turrets, homing jets, pod columns, snake chains, mines and more.
- **Every boss:** the sprite bosses, the huge background "wheel" bosses and the final boss, followed
  by the ending and the staff roll.
- **2-player co-op** with drop-in join, including **the combined robot**, the famous move where the
  two ships merge into one walking robot.
- **Battery save:** the high score table (with initials) and all your settings are kept when the
  console is off.

---

## Part 3: What I'd love to hear from you

The game is complete and playable, but it isn't finished. This is the stage where feedback helps
most. In particular:

1. **Real hardware.** All the testing so far has been in emulators (Genesis Plus GX and others). If
   you have a flash cart and a Genesis / Mega Drive (or a Nomad, or a clone), please tell me how it
   runs: any slowdown, glitches, flickering, sound problems, or save problems. Please say which
   model and region you used.
2. **Colours.** Do you prefer ARCADE or VIVID? Does any level look wrong or washed out compared to
   your memory of the arcade, or to the arcade running in MAME? Screenshots help a lot.
3. **Feel.** If you know the arcade well: does anything feel off? Movement speed, bullet speed,
   enemy timing, difficulty, hit boxes? Please tell me where (section number and roughly where in
   the section).
4. **Sound.** The music should be very close to the arcade. Sound effects go through a 3-voice
   reduction. Do any effects sound wrong, or cut off the music in a bad way?
5. **Performance.** 2-player co-op and the combined robot can still drop the occasional frame in
   the busiest moments. Did you notice it while playing? Did it bother you?
6. **Options and controls.** Is anything missing? Was any default a bad choice (button layout,
   autofire, the Home mode credit and continue settings)?
7. **Anything else.** Bugs, crashes, odd moments, or ideas.

Comments here or issues on the GitHub repository are both great. Thanks for reading, and enjoy the
game!

— **RESTER 159**

*Side Arms is © Capcom. This is a non-commercial fan project. The repository holds only original code
and tools, and no Capcom data. To build the game you need your own copy of the arcade ROM set.*
