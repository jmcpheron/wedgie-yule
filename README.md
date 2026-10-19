# wedgie-yule

**Yule Log**: a retro pixel fireplace for the [wedgie](https://wedgie.dev), where the secure chip decides
who visits. Plug it into a USB charger, put it on a shelf, and keep half an eye on it.

Two rooms:

- **Winter Hearth**: a stone hearth with stockings, a wreath, candles and chasing lights, a lit tree,
  a sleeping golden dog, and snow falling past the window.
- **Midnight Draw**: a cauldron bubbling over the fire, a witch's portrait, a bookshelf, a black cat,
  and a graveyard under the moon.

## The draw

Every 3 minutes the OPTIGA Trust M's true random generator draws a number from **0000 to 9999**, every
number equally likely (rejection sampling, no modulo bias). The lower the number, the rarer the visitor:

| Number | Tier | Odds | Winter Hearth | Midnight Draw |
|---|---|---:|---|---|
| 1000-9999 | Common | 90% | the dog stretches, a cardinal, snow off a branch, a shooting star | the cat stretches, a crow, the portrait's eyes, a bat |
| 0500-0999 | Uncommon | 5% | an elf peeks in (leaves footprints) | a ghost at the window (leaves a handprint) |
| 0100-0499 | Rare | 4% | the aurora and a white stag (the glow fades over 10 min) | an eye in the cauldron (the brew glows for 10 min) |
| 0000-0099 | Legendary | 1% | Santa crosses the moon (leaves a present) | the Headless Horseman (leaves a pumpkin) |

- **0000-0009**: Santa stops in front of the moon and waves; the Horseman rears.
- **0000**: Santa comes down the chimney, pets the dog and leaves a golden ornament on the mantel; the
  fire roars and a golden skull appears.
- Within a tier, a second draw from the chip picks the visitor, so the tier odds stay as listed.

At a draw, four hidden digits are revealed left to right along the bottom. A first leading zero glows
green. A second turns them gold and the fire hushes: something legendary is coming. With 1% a draw,
Santa comes on average once every 5 hours. That's an average, not a schedule: about a 55% chance in a
4-hour evening.

If the chip doesn't answer, there is no draw. The strip says DRAW UNAVAILABLE and the fire keeps going.
It never falls back to any other source. A wedgie without a Trust M (an ATECC608, or the emulator) gets
the fireplace but no draws.

## The hearth's identity

The hearth is named from the SHA-256 of the Trust M factory key's public key, which is in the chip's
certificate (issued by Infineon): **HEARTH 7C2A**, with a six-armed snowflake drawn from the same hash.
The same chip always gets the same name and snowflake. The name is a short nickname; checking a
postcard uses the full key.

## Postcards

Each legendary visit goes into the **visitor book** (grey X) as a postcard: North Pole Post for Santa,
Hollow Post for the Horseman. Open one and press green to **seal** it. The wedgie's own screen asks
first and says what will be signed. Only a real press says yes: a computer can't press it over USB.
Then the Trust M's factory key signs the postcard (ECDSA P-256 over SHA-256), and the card gets its
wax seal. Grey X on a sealed card shows the signature.

Nothing is signed without that press. The app never creates a key, never writes to the chip, and never
locks anything: it reads the certificate, draws random numbers, and signs with the key the chip came with.

### Checking postcards

```
python3 wedgie.py saves backup saves.json      # wedgie.py from wedgie.dev; the wedgie asks first
pip install cryptography
python3 verify.py saves.json
```

`verify.py` rebuilds the exact text the chip signed for each sealed postcard, checks the signature, and
checks that the key is the one in the hearth's certificate. Change one character of a postcard and it
fails.

What a good signature proves: this chip's key signed this postcard, and nothing in it has changed since.
What it doesn't prove: that the draw was honest, that 3 minutes passed, or that the animation played.
The chip signs whatever the app hands it. Sharing a postcard also shares the hearth's identity, which
is the chip's factory certificate. That's the point of the signature, but know that it identifies the device.

## Controls

| | |
|---|---|
| Joystick left / right | switch room (on the title, too) |
| Joystick up / down | flame size, 1 (embers) to 5 (roaring) |
| Green | stoke it: sparks and a flare |
| Grey B | how long until the next draw |
| Grey X | the visitor book; joystick through the postcards, green seals one |
| Red | back |

## Saves (`/saves/yule/`)

- `prefs`: `{"scene": 0, "flame": 3}`, written 3 s after the last change.
- `book`: draws so far, the last number, counts per tier and visitor, the legendary visits with their
  signatures, and the gifts by the hearth. Written after every uncommon or rarer draw, and every 10th.
- `hearth`: the factory key and its certificate, written once, for `verify.py`.

## Play it

- In the emulator: open https://wedgie.dev/code and load `jmcpheron/wedgie-yule`. `A` `D` switch room,
  `W` `S` flame, `J` stokes, `L` is grey X, `;` goes back. The emulator has no chip, so there are no draws.
- On your wedgie: wedgie.dev/connect → your wedgie → Software → Apps from a GitHub repo →
  `jmcpheron/wedgie-yule`. Or from a terminal: `python3 wedgie.py install .`

Until it's on the wedgie.dev shelf, an app added from a GitHub repo isn't signed by wedgie.dev, so it
installs with full access. This one uses the screen, the buttons, its own saves, and the Trust M only
as described above (random numbers, reading the certificate, a signature after your press).

**On battery** the wedgie turns its screen off after 20 s with no press. That's the firmware, for every
app. Keep it on USB power to leave the fire burning.

Needs wedgie firmware 0.3.36 or newer.

## How it's built

- `yule.py`: the fire (Doom's algorithm on a 21x16 grid of 4x4 cells, checker-dithered, in viper), the
  loop at 25 fps, the number strip, the draw schedule.
- `yule_chip.py`: the Trust M: finding it (in 0.2 s, not a 10 s timeout, when it's missing), the draw,
  the postcard text, the seal.
- `yule_room.py`: both rooms, the window and floor copies that put things back under what moves, the
  snowflake, the visitor book's numbers.
- `yule_ev.py`: every visitor, and what each leaves behind.
- `yule_book.py`: the book, the postcards and sealing. Loaded only while open.
- `yule_art.bin`: the sprites, built from text by `python3 tools/art.py` (`--preview out.png` draws them all).

MIT
