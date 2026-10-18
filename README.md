# wedgie-yule

**Yule Log**: a crackling, retro arcade fireplace for the [wedgie](https://wedgie.dev). Plug it into a
USB charger, put it on a shelf, and let it burn.

Two scenes, one hearth, the same pixels with a different palette (the old arcade trick):

- **Yule**: red brick, stockings, a wreath, candles, a string of blinking lights, a warm orange fire.
- **Halloween**: a grey crypt, ghost-green fire with purple tips, flickering jack-o'-lanterns, cobwebs,
  a skull, and a bat that flaps by now and then.

The fire is Doom's fire algorithm on a 32x26 grid of 4x4 cells, checker-dithered between its seven
colors, written in `@micropython.viper` (~1 ms to burn and ~1.4 ms to paint a frame on an RP2040). It runs
at 25 fps and pushes only the rows that changed.

## Controls

| | |
|---|---|
| Joystick left / right | switch scene (on the title, too) |
| Joystick up / down | flame size, 1 (embers) to 5 (roaring) |
| Green | stoke it: sparks and a flare |
| Red | back to the title |

## Saves

`prefs`: `{"scene": 0, "flame": 3}`. `scene` 0 is Yule, 1 is Halloween; `flame` is 1-5. It's written
3 s after the last change, not on every press.

## Play it

- In the emulator: open https://wedgie.dev/code, load `jmcpheron/wedgie-yule` (or open this folder).
  `A` `D` switch scene, `W` `S` flame, `J` stokes, `;` goes back.
- On your wedgie: wedgie.dev/connect → your wedgie → Software → Apps from a GitHub repo →
  `jmcpheron/wedgie-yule`. Or from a terminal: `python3 wedgie.py install .`
  ([wedgie.py](https://wedgie.dev/wedgie.py)).

Until it's on the wedgie.dev shelf, an app added from a GitHub repo isn't signed by wedgie.dev, so it
installs with full access. This one only draws: it uses the screen, the buttons and its own save, and
never touches the secure chip or USB.

**On battery** the wedgie turns its screen off after 20 s with no press (that's the firmware, for every
app). Keep it on USB power to leave the fire burning.

Needs wedgie firmware 0.3.36 or newer (the 16-color screen and `lcd.tint`).

MIT
