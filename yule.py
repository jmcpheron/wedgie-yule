# Yule Log for the wedgie: a retro pixel fireplace. Two rooms: Winter Hearth (a stone hearth, a dog, snow
# outside) and Midnight Draw (a cauldron, a cat, a graveyard moon). Every 3 minutes the Trust M draws a
# number 0000-9999; the lower it is, the rarer what visits (yule_ev.py). Santa and the Horseman leave a
# postcard in the visitor book that the chip seals when you say yes (yule_book.py).
# Joystick left/right: room, up/down: flame. Green stokes it, grey X the book, grey B the next draw, red back.
import time, random, gc, micropython
import lcd as L
import ui, save

d = L.LCD()
keys = L.Keys()
buf = d.buffer                      # 240x240, 4 bits a pixel: byte = 2 pixels, high nibble first

FRAME = 40                          # ms per frame: 25 fps
DRAW_MS = 180000                    # a draw every 3 minutes
# The 16 palette slots, tinted per room. They mean the same in both: sprites (tools/art.py) use them.
BG, F1, F2, F3, F4, F5, ICE, STONE, DARK, WOOD, LIGHT, LEAF, SKY, ACCENT, GLOW, WALL = range(16)
SCENES = (
    ("Winter Hearth", ((0, 0, 0), (100, 16, 4), (190, 44, 4), (240, 110, 10), (255, 175, 40), (255, 236, 150),
                       (140, 200, 255), (120, 112, 120), (52, 36, 34), (176, 116, 56), (246, 246, 240),
                       (30, 140, 60), (24, 36, 90), (210, 32, 36), (255, 206, 60), (58, 32, 22))),
    ("Midnight Draw", ((0, 0, 0), (90, 14, 4), (180, 46, 6), (236, 108, 12), (255, 170, 40), (255, 232, 140),
                       (150, 70, 210), (92, 84, 104), (36, 28, 44), (92, 62, 44), (232, 228, 206),
                       (90, 230, 60), (52, 40, 110), (240, 110, 12), (255, 214, 80), (40, 24, 34))),
)
# The fire: Doom's, on a grid of 4x4 cells inside the firebox. Cell values are heat 0..63.
FX, FY, FW, FH, CELL = 24, 116, 21, 16, 4
fire = bytearray(FW * FH)
seed = bytearray(2)
LA, LB = bytearray(64), bytearray(64)   # heat -> a byte of two pixels, on even rows and on odd rows
for _i in range(64):
    _k = min(10, _i * 10 // 9)          # 11 steps: black, the 5 fire colors and a checker between each
    _c1, _c2 = _k // 2, (_k + 1) // 2
    LA[_i], LB[_i] = _c1 << 4 | _c2, _c2 << 4 | _c1
HEAT = (4, 6, 7, 9, 11)                 # flame 1..5: the heat under the logs
STRIP = 214                             # the number strip: rows 214..239
st = {"scene": 0, "flame": 3, "stoke": 0, "soft": 0, "dirty": 0, "t": 0, "next": 0}

SPARKS = 10                             # x, y (px inside the firebox), y speed, life (frames)
sx, sy, sv, sl = [0] * SPARKS, [0] * SPARKS, [0] * SPARKS, [0] * SPARKS


@micropython.viper
def burn(f: ptr8, w: int, h: int, s: ptr8, heat: int):
    """One step: the bottom row gets the heat, every cell above takes the one below it, a little
    cooler and swaying sideways."""
    r = s[0] | s[1] << 8
    b = (h - 1) * w
    x = 0
    while x < w:
        r = (r * 25173 + 13849) & 0xFFFF
        v = heat - ((r >> 8) & 3)
        e = x if x < w - 1 - x else w - 1 - x
        if e < 5:
            v = v - (5 - e)                 # cooler toward the sides: a rounded flame, not a wall
        if (r >> 4) & 15 == 0:
            v = 0                           # now and then a gap, so tongues of flame split
        f[b + x] = v if v > 0 else 0
        x += 1
    y = 1
    while y < h:
        row = y * w
        x = 0
        while x < w:
            v = f[row + x]
            if v == 0:
                f[row - w + x] = 0
            else:
                r = (r * 25173 + 13849) & 0xFFFF
                k = (r >> 8) & 3
                t = x + k - 1 if k < 3 else x     # drift -1, 0, +1 or 0: flames sway, no wind
                if t < 0:
                    t = 0
                if t >= w:
                    t = w - 1
                f[row - w + t] = v - ((r >> 11) & 1)
            x += 1
        y += 1
    s[0] = r & 0xFF
    s[1] = r >> 8


@micropython.viper
def paint(f: ptr8, out: ptr8, la: ptr8, lb: ptr8, w: int, h: int, x0: int, y0: int):
    """The grid into the framebuffer: each cell 4x4 pixels, checkered between two colors."""
    i = 0
    cy = 0
    while cy < h:
        o = (y0 + cy * 4) * 120 + (x0 >> 1)
        cx = 0
        while cx < w:
            v = f[i]
            a = la[v]
            b = lb[v]
            p = o + cx * 2
            out[p] = a
            out[p + 1] = a
            out[p + 120] = b
            out[p + 121] = b
            out[p + 240] = a
            out[p + 241] = a
            out[p + 360] = b
            out[p + 361] = b
            cx += 1
            i += 1
        cy += 1


def tint():
    for i, rgb in enumerate(SCENES[st["scene"]][1]):
        L.tint(i, *rgb)


import yule_chip as chip            # the Trust M: identity, draws, seals
import yule_room as room            # the room, drawn once per scene, and what moves in it
import yule_ev as ev                # what visits

# ---- the number strip ----------------------------------------------------------------------------
TIER_NAMES = ("COMMON", "UNCOMMON", "RARE", "LEGENDARY")
TIER_C = (LIGHT, LEAF, ICE, GLOW)
sp = {"mode": "idle", "t": 0, "n": 0, "shown": 0, "tier": 0, "kind": "", "var": "", "name": ""}


def strip_bg():
    d.fill_rect(0, STRIP, 240, 26, BG)
    d.hline(0, STRIP, 240, DARK)


def strip_idle():
    strip_bg()
    x = 6
    if chip.ident:
        room.snowflake(d, 13, STRIP + 13, 5, ICE)
        x = 26
    s = (chip.label + "  " if chip.label else "") + "QUIET NIGHT"
    d.text(s, x + (234 - x - 8 * len(s)) // 2, STRIP + 9, LIGHT)
    d.show(STRIP, 240)


def strip_note(s, c=LIGHT):
    strip_bg()
    d.text(s, (240 - 8 * len(s)) // 2, STRIP + 9, c)
    d.show(STRIP, 240)


def strip_number(c=None):
    """The draw: its digits shown so far (the rest hidden), the tier and the visitor once all are out.
    A first leading zero is green; two make them all gold."""
    strip_bg()
    n = "%04d" % sp["n"]
    gold = sp["shown"] >= 2 and n[:2] == "00"
    for i in range(4):
        x = 6 + i * 16
        if i >= sp["shown"]:
            d.fill_rect(x + 2, STRIP + 16, 12, 3, DARK)
            continue
        lead = n[:i + 1] == "0" * (i + 1)
        col = c if c is not None else (GLOW if lead and gold else LEAF if lead else LIGHT)
        d.big_text(n[i], x, STRIP + 5, col, 2)
    if sp["shown"] >= 4:
        t = sp["tier"]
        d.text(TIER_NAMES[t], 80, STRIP + 4, c if c is not None else TIER_C[t])
        d.text(sp["name"][:19], 80, STRIP + 15, c if c is not None else LIGHT)
    d.show(STRIP, 240)


def strip_tick():
    """Once a frame: reveal the digits left to right, hold while the visit plays, fade, back to idle."""
    m = sp["mode"]
    if m == "idle":
        return
    sp["t"] += 1
    t = sp["t"]
    if m == "reveal":
        if t % 12 == 0:
            sp["shown"] += 1
            if sp["shown"] == 2 and sp["n"] < 100:
                st["soft"] = 50                 # two zeros: the fire hushes for a moment
            strip_number()
            if sp["shown"] >= 4:
                sp["mode"], sp["t"] = "hold", 0
                ev.start(sp["tier"], sp["kind"], sp["var"], sp["n"])
    elif m == "hold":
        if not ev.cur and t > 75:
            sp["mode"], sp["t"] = "fade", 0
    elif m in ("fade", "note"):
        if m == "note" and t < 75:
            return
        if t % 6 == 0:
            step = t // 6 - (12 if m == "note" else 0)
            if step > 3:
                sp["mode"] = "idle"
                strip_idle()
            elif step > 0:
                fc = (STONE, DARK, BG)[step - 1]
                if m == "fade":
                    strip_number(fc)
                else:
                    strip_note(sp["name"], fc)


def note(s):
    sp["mode"], sp["t"], sp["name"] = "note", 0, s
    strip_note(s)


# ---- the draw ------------------------------------------------------------------------------------
def draw():
    """Ask the chip for a number. No chip, no draw: the strip says so and the fire keeps going."""
    st["next"] = time.ticks_add(time.ticks_ms(), DRAW_MS)
    n = chip.number()
    if n is None:
        note("DRAW UNAVAILABLE")
        return
    tier = 0 if n >= 1000 else 1 if n >= 500 else 2 if n >= 100 else 3
    kinds = ev.KINDS[st["scene"]][tier]
    i = chip.below(len(kinds)) if len(kinds) > 1 else 0
    if i is None:
        note("DRAW UNAVAILABLE")
        return
    k = kinds[i]
    var = ev.variation(tier, n)
    ev.cancel()
    sp.update(mode="reveal", t=0, n=n, shown=0, tier=tier, kind=k, var=var, name=ev.title(k, var))
    room.log_draw(n, tier, k, var)
    strip_number()


# ---- sparks --------------------------------------------------------------------------------------
def spark(n):
    for i in range(SPARKS):
        if n <= 0:
            return
        if sl[i] <= 0:
            sx[i] = 12 + random.getrandbits(6) % 60
            sy[i] = FH * CELL - 22
            sv[i] = 1 + random.getrandbits(2)
            sl[i] = 10 + random.getrandbits(4)
            n -= 1


def sparks():
    for i in range(SPARKS):
        if sl[i] > 0:
            sl[i] -= 1
            sy[i] -= sv[i]
            if random.getrandbits(1):
                sx[i] += random.getrandbits(2) - 1
            if sy[i] < 2 or sx[i] < 1 or sx[i] > FW * CELL - 3:
                sl[i] = 0
                continue
            d.fill_rect(FX + sx[i], FY + sy[i], 2, 2, F5 if sl[i] > 4 else F3)


# ---- the loop ------------------------------------------------------------------------------------
def frame():
    t = st["t"]
    heat = HEAT[st["flame"] - 1] + (st["stoke"] >> 3) + ev.heat()
    if st["stoke"]:
        st["stoke"] -= 1
    if st["soft"]:
        st["soft"] -= 1
        heat -= 3
    burn(fire, FW, FH, seed, max(0, min(63, heat)))
    paint(fire, buf, LA, LB, FW, FH, FX, FY)
    if random.getrandbits(4) < st["flame"]:
        spark(1)
    sparks()
    room.hearth_over()
    ev.over_fire(t)
    d.show_rect(FX, FY, FW * CELL, FH * CELL)
    if t & 1:
        room.window(t)
    if t % 3 == 0:
        room.candles()
    room.ambient(t)
    strip_tick()


def pace(t):
    left = FRAME - time.ticks_diff(time.ticks_ms(), t)
    time.sleep_ms(left if left > 0 else 1)


def keep():
    save.store("prefs", {"scene": st["scene"], "flame": st["flame"]})
    st["dirty"] = 0


def title():
    """The controls, and which room. Joystick left/right picks it; green lights it."""
    ui.page(d, "Yule Log", [], "{g} light it", show=False)
    ui.say(d, "joystick: room, flame", 166, ui.MUTED)
    ui.say(d, "{g} stoke {k} book {r} back", 182, ui.MUTED)
    while True:
        d.fill_rect(0, 116, 240, 24, ui.WHITE)
        ui.say(d, SCENES[st["scene"]][0], 120, ui.INK, 2)
        for x, sgn in ((3, 1), (236, -1)):      # arrows: there's another room each way
            for k in range(6):
                d.vline(x + sgn * k, 127 - k, 2 * k + 1, ui.MUTED)
        d.show()
        while True:
            t = time.ticks_ms()
            k = keys.pressed()
            if "A" in k:
                return
            if "left" in k or "right" in k:
                st["scene"] ^= 1
                keep()
                break
            pace(t)


def book():
    import sys
    gc.collect()
    import yule_book
    yule_book.run()
    del sys.modules["yule_book"]
    gc.collect()


def light():
    fire[:] = bytes(FW * FH)
    room.draw()
    strip_idle()


def run():
    random.seed(time.ticks_us())
    p = save.load("prefs", None)
    if isinstance(p, dict):
        st["scene"] = 1 if p.get("scene") == 1 else 0
        f = p.get("flame", 3)
        st["flame"] = f if f in (1, 2, 3, 4, 5) else 3
    s = random.getrandbits(16)
    seed[0], seed[1] = s & 255, s >> 8
    chip.open()
    room.load_book()
    while True:
        title()
        gc.collect()
        light()
        if not st["next"] or time.ticks_diff(st["next"], time.ticks_ms()) > DRAW_MS:
            st["next"] = time.ticks_add(time.ticks_ms(), DRAW_MS)
        while True:
            t = time.ticks_ms()
            k = keys.pressed()
            if "Y" in k:
                break
            if "left" in k or "right" in k:
                st["scene"] ^= 1
                st["dirty"] = 1
                ev.cancel()
                sp["mode"] = "idle"
                light()
            if "up" in k and st["flame"] < 5:
                st["flame"] += 1
                st["dirty"] = 1
            if "down" in k and st["flame"] > 1:
                st["flame"] -= 1
                st["dirty"] = 1
            if "A" in k:
                st["stoke"] = 60
                spark(SPARKS)
            if "B" in k and sp["mode"] == "idle":
                left = max(0, time.ticks_diff(st["next"], t)) // 1000
                note("NEXT DRAW %d:%02d" % (left // 60, left % 60))
            if "X" in k:
                ev.cancel()
                sp["mode"] = "idle"
                book()
                light()
            if st["dirty"]:
                st["dirty"] += 1
                if st["dirty"] > 75:     # 3 s after the last change: one write, not one a press
                    keep()
            if time.ticks_diff(t, st["next"]) >= 0 and sp["mode"] in ("idle", "note"):
                draw()
            frame()
            st["t"] += 1
            pace(t)
        if st["dirty"]:
            keep()
