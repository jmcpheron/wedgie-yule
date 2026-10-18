# Yule Log for the wedgie: a crackling arcade fireplace to leave burning on a shelf. Two scenes, one
# hearth: Yule (bricks, stockings, a wreath, blinking lights) and Halloween (a crypt, ghost fire,
# jack-o'-lanterns, a bat). Same pixels, a different palette: the old arcade trick.
# Joystick left/right: scene, up/down: flame. Green stokes it, red goes back. Scene and flame are saved.
import time, random, gc, framebuf, micropython
import lcd as L
import ui, save

d = L.LCD()
keys = L.Keys()
buf = d.buffer                      # 240x240, 4 bits a pixel: byte = 2 pixels, high nibble first

FRAME = 40                          # ms per frame: 25 fps
# Every one of the 16 palette slots is tinted per scene. 10 stays light, 11 green and 13 red-ish, so
# the battery corner (ui.GREEN, ui.RED, ui.WHITE) still reads.
BG, F1, F2, F3, F4, F5, F6, BRICK, MORTAR, WOOD, LIGHT, LEAF, WALL, ACCENT, GLOW, BARK = range(16)
SCENES = (
    ("Yule", ((0, 0, 0), (90, 12, 0), (175, 32, 0), (232, 86, 4), (255, 146, 18), (255, 206, 56),
              (255, 246, 186), (142, 46, 32), (62, 24, 20), (160, 104, 56), (250, 250, 244),
              (28, 140, 52), (18, 48, 34), (220, 34, 34), (255, 214, 40), (92, 54, 28))),
    ("Halloween", ((0, 0, 0), (36, 0, 56), (88, 10, 128), (150, 32, 196), (38, 170, 64), (112, 232, 74),
                   (214, 255, 176), (78, 78, 90), (34, 34, 44), (78, 58, 48), (232, 228, 204),
                   (66, 128, 40), (30, 10, 46), (240, 112, 12), (255, 228, 92), (38, 28, 26))),
)
# The fire: Doom's, on a grid of 4x4 cells inside the firebox. Cell values are heat 0..63.
FX, FY, FW, FH, CELL = 56, 98, 32, 26, 4
fire = bytearray(FW * FH)
seed = bytearray(4)
LA, LB = bytearray(64), bytearray(64)   # heat -> a byte of two pixels, on even rows and on odd rows
for _i in range(64):
    _k = min(12, _i * 12 // 11)         # 13 steps: the 7 fire colors and a checker between each pair
    _c1, _c2 = _k // 2, (_k + 1) // 2
    LA[_i], LB[_i] = _c1 << 4 | _c2, _c2 << 4 | _c1
HEAT = (6, 8, 10, 12, 14)             # flame 1..5: the heat under the logs
st = {"scene": 0, "flame": 3, "stoke": 0, "dirty": 0, "t": 0}

# sparks: x, y (px inside the firebox), y speed, life (frames)
SPARKS = 14
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
        if e < 8:
            v = v - (8 - e)                 # cooler toward the sides: a rounded flame, not a wall
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


def sprite(w, h):
    fb = framebuf.FrameBuffer(bytearray(w * h // 2), w, h, framebuf.GS4_HMSB)
    fb.fill(WALL)                       # WALL is the transparent color: nothing in a sprite uses it
    return fb


# The logs and the grate, drawn once: blitted over the fire's bottom each frame.
LW, LH = 128, 28
LX, LY = FX, FY + FH * CELL - LH


def make_logs():
    g = sprite(LW, LH)
    g.fill_rect(10, 22, 4, 6, BG)       # the grate's feet
    g.fill_rect(114, 22, 4, 6, BG)
    g.fill_rect(6, 24, 116, 2, BG)
    for x0, y0, w, h in ((14, 12, 100, 12), (30, 2, 70, 11)):
        g.fill_rect(x0, y0, w, h, BARK)
        g.hline(x0, y0, w, WOOD)        # bark: a lit top edge, grain lines
        g.hline(x0 + 6, y0 + h // 2, w - 20, BG)
        g.hline(x0 + 14, y0 + h - 3, w - 30, BG)
        for e in (x0, x0 + w - 1):      # the cut ends: rings
            g.ellipse(e, y0 + h // 2, 4, h // 2, WOOD, True)
            g.ellipse(e, y0 + h // 2, 2, h // 4, BARK, True)
            g.pixel(e, y0 + h // 2, F3)
        for i in range(0, w - 8, 9):    # embers in the cracks
            g.hline(x0 + 5 + i, y0 + h - 2 - (i // 9) % 3, 3, F3 if i % 2 else F2)
    return g


LOGS = make_logs()

# The bat (Halloween): two frames, wings up and down.
BAT = ("....k......k....", "...kk......kk...", "..kkkk.kk.kkkk..", ".kkkkkkkkkkkkkk.",
       "kkkk.kkrrkk.kkkk", "kk....kkkk....kk", "k......kk......k", "................")
BAT2 = ("................", "................", ".......kk.......", "....kkkkkkkk....",
        "..kkkkkrrkkkkk..", ".kkk..kkkk..kkk.", "kk....k..k....kk", "k..............k")


def make_bat(rows):
    g = sprite(16, 8)
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != ".":
                g.pixel(x, y, BG if ch == "k" else ACCENT)
    return g


BATS = (make_bat(BAT), make_bat(BAT2))
bat = [-20, 10, 0]                      # x, y, frames to wait off screen


def tint():
    for i, rgb in enumerate(SCENES[st["scene"]][1]):
        L.tint(i, *rgb)


# ---- the room, drawn once per scene ----------------------------------------------------------------
def bricks(x0, y0, x1, y1, w=16):
    d.fill_rect(x0, y0, x1 - x0, y1 - y0, MORTAR)
    r = 0
    for y in range(y0, y1, 8):
        for x in range(x0 - (r & 1) * w // 2, x1, w):
            a, b = max(x, x0), min(x + w - 1, x1)
            if b > a:
                d.fill_rect(a, y, b - a, min(7, y1 - y), BRICK)
        r += 1


def room():
    d.fill(WALL)
    tint()
    halloween = st["scene"] == 1
    bricks(22, 56, 218, 206, 22 if halloween else 16)
    # the soldier course over the firebox, and the firebox's sooty frame
    d.fill_rect(48, 84, 144, 10, MORTAR)
    for x in range(49, 191, 7):
        d.fill_rect(x, 85, 6, 8, BRICK if not halloween else WOOD)
    d.fill_rect(FX - 4, FY - 4, FW * CELL + 8, FH * CELL + 6, BG)
    # the hearth and the floor
    d.fill_rect(10, 204, 220, 12, BRICK)
    d.hline(10, 204, 220, LIGHT if not halloween else WOOD)
    d.hline(10, 215, 220, MORTAR)
    d.fill_rect(0, 216, 240, 24, BARK)
    for y in (222, 230, 238):
        d.hline(0, y, 240, BG)
    for i, y in enumerate((216, 222, 230)):
        for x in range((i * 37) % 60, 240, 60):
            d.vline(x, y + 1, 6 if y < 230 else 7, BG)
    # the mantel
    d.fill_rect(6, 42, 228, 5, WOOD)
    d.fill_rect(10, 47, 220, 9, BARK)
    d.hline(10, 55, 220, BG)
    for x in (22, 210):                 # corbels
        d.fill_rect(x, 56, 8, 8, BARK)
        d.fill_rect(x + 2, 64, 4, 4, BARK)
    if halloween:
        skull(24, 194)
    else:
        stocking(30, 1)
        stocking(210, -1)
    top()
    lights(True)
    d.show()


def stocking(x, way):
    """A stocking hung from the mantel at x, its toe pointing way (1 right, -1 left)."""
    l = x if way > 0 else x - 14
    d.fill_rect(l + 2, 64, 14, 20, ACCENT)
    d.fill_rect(l + 2, 70, 14, 3, LIGHT)
    d.fill_rect(l + 2, 77, 14, 3, LEAF)
    toe = l + 2 if way > 0 else l - 8
    d.fill_rect(toe, 82, 22, 8, ACCENT)
    d.fill_rect(toe + (16 if way > 0 else 0), 84, 6, 6, LIGHT)
    d.fill_rect(l, 58, 18, 7, LIGHT)    # the cuff


def skull(x, y):
    d.fill_rect(x, y, 12, 8, LIGHT)
    d.fill_rect(x + 2, y + 8, 8, 3, LIGHT)
    d.fill_rect(x + 2, y + 3, 3, 3, BG)
    d.fill_rect(x + 7, y + 3, 3, 3, BG)
    d.vline(x + 4, y + 8, 3, BG)
    d.vline(x + 7, y + 8, 3, BG)


def pumpkin(cx, r, face):
    """A jack-o'-lantern sitting on the mantel, its face lit by the candle inside."""
    ry = r * 3 // 4
    cy = 42 - ry
    d.ellipse(cx, cy, r, ry, ACCENT, True)
    d.ellipse(cx, cy, r // 2, ry, BARK)
    d.vline(cx, cy - ry + 2, 2 * ry - 4, BARK)
    d.fill_rect(cx - 1, cy - ry - 4, 3, 5, LEAF)
    e = max(2, r // 5)
    for sgn in (-1, 1):                 # triangle eyes, a jagged grin
        ex = cx + sgn * (r // 2 - 1)
        for k in range(e):
            d.hline(ex - k, cy - ry // 3 - e + k, 2 * k + 1, face)
    for i in range(-r // 2, r // 2 + 1, 2):
        d.vline(cx + i, cy + ry // 4 + (1 if i % 4 else 0), 3, face)
    d.hline(cx - r // 2, cy + ry // 4 + 1, r, face)


def top():
    """The wall over the mantel: the parts that flicker or fly, redrawn when they move."""
    d.fill_rect(0, 0, 240, 42, WALL)
    if st["scene"] == 1:
        for a in (0, 239):              # cobwebs in the corners
            sgn = 1 if a == 0 else -1
            for k in (14, 24, 34):
                d.line(a, k, a + sgn * k, 0, MORTAR)
            for k in range(6, 30, 8):
                d.line(a, k, a + sgn * k, 0, LIGHT if k == 22 else MORTAR)
        if bat[2] == 0:
            d.blit(BATS[(st["t"] >> 2) & 1], bat[0], bat[1], WALL)
        pumpkin(44, 12, GLOW)
        pumpkin(120, 17, GLOW)
        pumpkin(196, 11, GLOW)
    else:
        d.ellipse(120, 22, 18, 18, LEAF, True)  # the wreath
        d.ellipse(120, 22, 10, 10, WALL, True)
        for a, b in ((-12, -10), (13, -8), (-15, 6), (8, 13), (16, 4), (-4, -16)):
            d.fill_rect(120 + a, 22 + b, 3, 3, ACCENT)
        d.fill_rect(114, 34, 13, 6, ACCENT)     # its bow
        d.fill_rect(118, 38, 2, 4, ACCENT)
        d.fill_rect(122, 38, 2, 4, ACCENT)
        for x in (40, 192):                     # candles
            d.fill_rect(x, 26, 8, 16, LIGHT)
            lean = (random.getrandbits(2) - 1) if st["t"] % 3 == 0 else 0
            d.fill_rect(x + 2 + lean, 18, 4, 7, GLOW)
            d.fill_rect(x + 3 + lean, 21, 2, 3, F6)
            d.vline(x + 4, 25, 2, BG)


# The Yule garland: hooks every 40 px, a sag between, bulbs along it.
GARLAND = bytearray(240)
for _x in range(240):
    _d = _x % 40
    GARLAND[_x] = 56 + _d * (40 - _d) * 7 // 400
BULBS = [x for x in range(14, 230, 13)]
BULB_C = (ACCENT, GLOW, LIGHT, F4)


def lights(full=False):
    if st["scene"] != 0:
        return
    if full:
        for x in range(10, 230):
            d.vline(x, GARLAND[x], 3, LEAF)
    k = st["t"] // 10
    for i, x in enumerate(BULBS):
        d.fill_rect(x - 1, GARLAND[x] + 3, 3, 4, BULB_C[(i + k) % 4])


# ---- sparks ---------------------------------------------------------------------------------------
def spark(n):
    for i in range(SPARKS):
        if n <= 0:
            return
        if sl[i] <= 0:
            sx[i] = 16 + random.getrandbits(7) % 96
            sy[i] = FH * CELL - LH - 4
            sv[i] = 1 + random.getrandbits(2)
            sl[i] = 12 + random.getrandbits(4)
            n -= 1


def sparks():
    c = F6
    for i in range(SPARKS):
        if sl[i] > 0:
            sl[i] -= 1
            sy[i] -= sv[i]
            sx[i] += random.getrandbits(2) - 1 if random.getrandbits(1) else 0
            if sy[i] < 2 or sx[i] < 1 or sx[i] > FW * CELL - 3:
                sl[i] = 0
                continue
            d.fill_rect(FX + sx[i], FY + sy[i], 2, 2, c if sl[i] > 4 else F4)


# ---- the loop -------------------------------------------------------------------------------------
def frame():
    t = st["t"]
    heat = HEAT[st["flame"] - 1] + (st["stoke"] >> 2)
    if st["stoke"]:
        st["stoke"] -= 1
    burn(fire, FW, FH, seed, min(63, heat))
    paint(fire, buf, LA, LB, FW, FH, FX, FY)
    if random.getrandbits(4) < st["flame"]:
        spark(1)
    sparks()
    d.blit(LOGS, LX, LY, WALL)
    d.show(FY - 2, FY + FH * CELL)
    if st["scene"] == 1:
        if bat[2]:
            bat[2] -= 1
        else:
            bat[0] += 3
            bat[1] = 8 + ((t >> 3) & 7 if (t >> 6) & 1 else 7 - ((t >> 3) & 7))
            if bat[0] > 240:
                bat[0], bat[2] = -20, 60 + random.getrandbits(7)
        if t % 2 == 0:
            L.tint(GLOW, 255, 150 + random.getrandbits(7) // 2, 40 + random.getrandbits(6))
            top()
            d.show(0, 42)
    else:
        if t % 3 == 0:
            L.tint(GLOW, 255, 190 + random.getrandbits(5), 20 + random.getrandbits(5))
            top()
            d.show(0, 42)
        if t % 10 == 0:
            lights()
            d.show(56, 70)


def pace(t):
    left = FRAME - time.ticks_diff(time.ticks_ms(), t)
    time.sleep_ms(left if left > 0 else 1)


def keep():
    save.store("prefs", {"scene": st["scene"], "flame": st["flame"]})
    st["dirty"] = 0


def title():
    """The controls, and which scene. Joystick left/right picks it; green lights it."""
    ui.page(d, "Yule Log", [], "{g} light it", show=False)
    ui.say(d, "joystick: scene, flame", 168, ui.MUTED)
    ui.say(d, "{g} stoke   {r} back", 184, ui.MUTED)
    while True:
        d.fill_rect(0, 120, 240, 20, ui.WHITE)
        ui.say(d, "< %s >" % SCENES[st["scene"]][0], 122, ui.INK, 2)
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


def run():
    random.seed(time.ticks_us())
    p = save.load("prefs", None)
    if isinstance(p, dict):
        st["scene"] = 1 if p.get("scene") == 1 else 0
        f = p.get("flame", 3)
        st["flame"] = f if f in (1, 2, 3, 4, 5) else 3
    s = random.getrandbits(16)
    seed[0], seed[1] = s & 255, s >> 8
    while True:
        title()
        gc.collect()
        fire[:] = bytes(FW * FH)
        room()
        while True:
            t = time.ticks_ms()
            k = keys.pressed()
            if "Y" in k:
                break
            if "left" in k or "right" in k:
                st["scene"] ^= 1
                st["dirty"] = 1
                room()
            if "up" in k and st["flame"] < 5:
                st["flame"] += 1
                st["dirty"] = 1
            if "down" in k and st["flame"] > 1:
                st["flame"] -= 1
                st["dirty"] = 1
            if "A" in k:
                st["stoke"] = 40
                spark(SPARKS)
            if st["dirty"]:
                st["dirty"] += 1
                if st["dirty"] > 75:     # 3 s after the last change: one write, not one a press
                    keep()
            frame()
            st["t"] += 1
            pace(t)
        if st["dirty"]:
            keep()
