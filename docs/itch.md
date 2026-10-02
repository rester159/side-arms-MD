# Side Arms MD

**Capcom's 1986 arcade shooter, rebuilt from scratch for the Sega Genesis / Mega Drive. Smooth 60 fps, 2-player co-op, every section and every boss.**

Hi, and thanks for stopping by! 👋

Do you remember *Side Arms – Hyper Dyne*? It's Capcom's 1986 arcade shooter where you pilot a little flying mech, blast in both directions, and team up with a friend to merge into one giant robot. It came out for the arcades, the PC Engine and some home computers, but it never came to the Sega Genesis / Mega Drive.

So I made that version myself. **Side Arms MD** is a fan-made port, written from scratch for the Genesis, that plays like the arcade game and runs at a smooth 60 frames per second.

Below you'll find what's in the game, how to get it, and the story of how it was built, explained so anyone can follow along, no tech background needed.

Version 1.0 · Free, non-commercial fan project · Source code: https://github.com/rester159/side-arms-MD

---

## What's in the game

- **The whole arcade game.** All 10 sections, every enemy, every boss, the final boss and the ending.
- **2-player co-op.** A friend can jump in any time, and the two mechs can **combine into one big walking robot**, the move Side Arms is famous for.
- **All the weapons**, each with its power-up levels: BIT (little helper drones), S.G. (spread shot), M.B.L. (piercing beam), 3WAY and AUTO (rapid fire). Shoot the POW capsules to cycle through power-ups and find the hidden bonuses.
- **The arcade's music**, played on the Genesis's own FM synthesiser chip.
- **Saving.** High scores, your settings and your best Boss Rush run are remembered when the console is off.

### Two ways to play

**🕹️ ARCADE mode: the original machine**

It works just like standing in front of the cabinet: press Start to drop in a coin, then Start again to play. You get the attract mode with the arcade's own recorded demo plays, name entry, the continue countdown and the ranking table.

*Psst:* on the INSERT COIN screen, try **Up, Up, Down, Down, Left, Right, Left, Right**. It opens the arcade board's secret **DIP switches**, the little switches arcade owners used to set difficulty, lives, bonus lives, continues and demo sounds.

**🏠 HOME mode: made for your couch**

- **Options:** difficulty (a new EASY, the arcade's levels 1–8, and a new HARD), lives 1–7, bonus lives, continues (off, limited or unlimited), credits 1–9, colour mode, parallax, and a sound test with every song and sound effect.
- **Boss Rush** *(new in 1.0)*: all 12 bosses back to back, in the arcade's order. Instead of lives you get an energy bar with 8 segments. Each hit costs one, and beating a boss gives two back. A timer runs during the fights, and your best run is saved. A friend can join any time.
- **Parallax scrolling** *(new in 1.0)*: the background gets depth (more on how below). Prefer the original look? Switch it off in Options.

### Controls

**A** fires left · **B** fires right · **C** switches weapon · **Start** starts the game or adds a coin.

- Put any action on any button.
- Got a **6-button pad**? X, Y and Z can jump to the previous or next weapon, pick a specific weapon, or **LOCK FIRE**, which keeps shooting the way you're facing without turning around.
- Turn on **autofire** for each fire button separately.
- **A+B+C+Start** together takes you back to the mode select.

### Colour

- **ARCADE:** as close as the Genesis can get to the original colours.
- **VIVID** (default): a bit brighter and more colourful. The Genesis has fewer shades to choose from than the arcade, and many emulators make Genesis games look darker than they should, so VIVID gives the colours a small boost.

---

## How to get it

One important thing first: **there's no ROM file to download here.** Side Arms' graphics, music and game data belong to Capcom, so the project doesn't include any of them. Instead, it comes with tools that build the game from **your own copy** of the arcade ROMs:

1. Download the source code from GitHub (link above).
2. Put the 27 files of the MAME `sidearms` (World) ROM set in the `rom/` folder. The tools check each file's fingerprint to make sure it's the right one.
3. Install SGDK 2.12, Python 3 and Java, then run `make`.

That's it. The tools convert the arcade's graphics and music into Genesis formats and put together a cartridge file, `out/release/rom.bin`. Play it in a Genesis emulator (Genesis Plus GX works great) or put it on a flash cart for a real console. The README on GitHub has every detail.

---

## How do you bring an arcade game to the Genesis?

This is my favourite part. You don't need to know anything about programming to follow it.

### Two very different machines

Think of the arcade board and the Genesis as two kitchens. Both can cook the same meal, but they have different tools, different amounts of counter space, and chefs who speak different languages.

| | Side Arms arcade board (1986) | Sega Genesis (1988) |
|---|---|---|
| Brain (main processor) | Z80 chip | 68000 chip, a completely different family that speaks a different "language" |
| Screen width | 384 pixels | 320 pixels |
| Colours | 4,096 to choose from | 512 to choose from, at most 61 on screen at once |
| Level maps | one giant 4096 × 4096 pixel map, always available | 64 KB of video memory, enough for only a small piece of a map |
| Sprites (moving objects) | 128 on screen | 80 on screen |
| Sound | two sound chips with 12 voices | one FM chip with 6 voices, plus a simpler chip with 3 tones and a noise channel |

So you can't just copy the arcade game onto a Genesis cartridge. The Genesis wouldn't understand a single instruction of it.

### Rewrite, don't translate

There are two ways to port a game like this:

1. **Translate the arcade program** line by line into something the Genesis can run. It's quicker to get working, but it's like reading a book through a phrase-by-phrase dictionary: everything is slow and a bit clumsy. I tried this on an earlier port, and it couldn't go faster than 48 frames per second.
2. **Rewrite it.** Study the original until you know exactly what it does, then write a brand-new game for the Genesis that does the same things.

Side Arms MD is a rewrite. It's like learning a song by ear, writing down the sheet music, then playing it on a different instrument. Same song, new instrument.

### Step 1: Studying the original

Before writing any of the game itself, I took the arcade game apart to see how it works:

- **Reading its "recipe".** The arcade program was turned back into human-readable instructions, so I could find the exact spots that move your mech, send in enemies, run each boss and play each song.
- **Recording the real thing.** I wrote little helper programs that run the original game in the MAME arcade emulator, with no screen, and write down everything that happens, frame by frame: where each enemy is, when it appears, how fast every bullet flies. These recordings are my "answer key".
- **Taking notes.** Everything went into notes that became the blueprint for the port.

My one big rule was **no guessing**. Every speed, timer, hit box and score in the port comes from the original. When something didn't match, I didn't nudge numbers until it looked about right. I went and found the real reason.

### Step 2: The graphics

**The level maps: a train window.** The arcade keeps its whole world map available at all times, a huge picture 4,096 pixels on each side. The Genesis only has room for a small piece of it, so the port works like the view from a train window. As you fly forward, the next bit of scenery is loaded just before it comes into view, and the bit you've passed is cleared away to make room. The scenery is built from square blocks, and the Genesis keeps a little "pantry" of 56 blocks: exactly what the screen needs right now. I compared it with the arcade, and the scrolling lines up pixel for pixel.

**The stars: painted in advance.** On the arcade, the twinkling starfield behind the levels comes from a special circuit built just for that. The Genesis doesn't have one. So I worked out the circuit's entire star pattern ahead of time and saved it as a picture the Genesis can slide around by itself, almost for free.

**The narrower screen.** The arcade screen is 64 pixels wider than the Genesis screen. The port keeps the action centred, and where needed things are nudged to fit: for example, some bosses sit a little further left so they don't get cut off at the edge.

**The colours: a smaller paint box.** The Genesis has far fewer shades than the arcade, and fewer colours on screen at once. It's like repainting a picture with a smaller paint box. A tool picks the best possible set of Genesis colours for each area of each level and for every enemy and object.

**The scoreboard.** Your score, lives and weapon bar sit on their own layer. Halfway down the screen, the Genesis quickly flips that layer from the top rows to the bottom rows, so the game can show both without covering the action in the middle.

### Step 3: The sound

The arcade has 12 voices for music and sound effects, and the Genesis has 9 voices plus a noise channel, split across two chips.

- **Music.** The arcade's music is played by 6 FM synthesiser voices, and the Genesis has exactly 6 FM voices of its own, the same kind of instrument. So the songs are played on the same kind of synthesiser. The build tools convert every song, then "play" all of them in a simulation and check that each of the **12,081 notes and rests** starts at exactly the right moment. If even one note is late, the build stops.
- **Sound effects.** The arcade uses 6 voices for effects, and the Genesis has 3 to spare. So at each moment, the Genesis plays the 3 loudest parts of the effect. You lose a little detail, but the punchy parts come through.
- **A sound engine built from scratch.** The Genesis has a second, smaller processor that I gave a single job: running the sound. It updates the music about 249 times a second, the arcade's own tempo, so the music never drags, even when the screen is full of explosions.

### Step 4: The gameplay

The game itself is brand-new code, written in a way the Genesis likes. Each player, enemy, bullet and boss is its own little object with its own behaviour, copied carefully from the arcade, quirks included. For example:

- The arcade can only juggle a set number of enemies at once. If it's full, a new enemy simply doesn't appear. The port has the same limits, because they're part of how the game feels.
- Difficulty works just like the arcade's: it changes how many enemy bullets can be on screen and how fast they fly, using the arcade's own tables.

**How do I know it plays the same?** I gave the arcade and the port the exact same button presses and compared them frame by frame. In the first stage, over almost 5,000 frames, the camera, every enemy's path and **all 358 of the player's shots** showed up on the same frames and flew the same paths.

### Step 5: Keeping it smooth (60 fps)

The arcade game runs at 60 frames per second, so the port has to as well. That means the Genesis has 1/60th of a second to do everything before it draws the next picture: move every object, check every hit, update the scenery and the scoreboard.

The tricky part: on paper the Genesis's brain is about as fast as the arcade's, but it has more to do, because the arcade had special helper chips for jobs the Genesis does by hand.

So I built a **robot tester**, a little program that plays every section from start to finish, alone and with two players, through every boss to the ending, and counts every frame that comes in late. The first version was late on up to 14% of frames with one player and 23% with two. Then I fixed the slow spots one by one. A few examples:

- **Big enemies** used to be assembled piece by piece while the game ran. Now they're prepared in advance, like cooking with ingredients already chopped.
- **The score display** used a slow way of turning numbers into digits. Now it uses a much quicker trick.
- **The scoreboard trick** used to interrupt the processor 28 times per frame. Now it's twice.

**Where it stands now:** with one player, about 0.2% of frames come in late, so it's very close to perfectly smooth. With two players, 1–3% at the busiest moments, like big enemy waves with both players using rapid fire. Fun fact: the original arcade slows down in some of the same busy spots.

### New in 1.0: how the parallax works

"Parallax" is the effect you see from a car window: nearby trees whizz past, while faraway mountains barely move. That difference in speed is what makes a flat picture feel deep.

The arcade only has one layer of stars behind the action, so in Home mode I added depth:

- **Four layers of stars.** The starfield is split into four layers. Faint stars are "far away" and move slowly, and bright stars are "close" and move faster. The Genesis can scroll each line of the screen at its own speed, so every row of stars glides at its own pace.
- **Faraway scenery.** In section 5, the cave wall slides along behind the rock, like a backdrop.
- **Same game.** Only the look changes. Walls, enemies and bosses are exactly where they always were, so the game plays the same, still at 60 fps.

---

## I'd love your feedback 💬

Version 1.0 is out, but so far it's only been tested in emulators. Your help would mean a lot:

1. **Real hardware.** Tried it on a real Genesis or Mega Drive with a flash cart? Tell me how it went (slowdown, glitches, sound, saving), and which console and region you used.
2. **Colours.** Do you like ARCADE or VIVID better? Does any level look wrong? Screenshots are super helpful.
3. **Feel.** If you know the arcade game well, does anything feel off? Tell me which section and roughly where.
4. **Sound.** Does any sound effect sound wrong, or clash with the music?
5. **Two players.** Did you notice any slowdown? Did it bother you?
6. **Boss Rush and parallax.** Too easy, too hard, too busy? Love it?
7. **Anything else.** Bugs, crashes, ideas, wishes.

Leave a comment here or open an issue on GitHub. Thanks so much for reading, and have fun! 🚀

— **RESTER 159**

*Side Arms is © Capcom. Side Arms MD is a free, non-commercial fan project and isn't affiliated with Capcom or Sega. It contains only original code and tools, with no Capcom data: you need your own copy of the arcade ROM set to build it.*
