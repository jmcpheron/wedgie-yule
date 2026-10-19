# The room: drawn once per scene (draw), then only what moves is drawn again and pushed: the window
# (snow, visitors), the candles, the lights, the pet on its rug. Copies of the window's glass and of the
# floor (WB, FL) put the background back under whatever moves there.
# Also the visitor book's numbers (bk), the gifts visitors leave, and the hearth's snowflake.
import framebuf, random, time, micropython
import lcd as L
import save
import yule as Y
import yule_chip as chip

d = Y.d
GS4 = framebuf.GS4_HMSB
BG, F1, F2, F3, F4, F5, ICE, STONE, DARK, WOOD, LIGHT, LEAF, SKY, ACCENT, GLOW, WALL = range(16)

# The window's glass, and views onto the framebuffer that clip to it and to the firebox: anything drawn
# through GL or FB stays inside, whatever its x and y.
GX, GY, GW, GH = 140, 14, 90, 98
GL = framebuf.FrameBuffer(memoryview(Y.buf)[(GY * 240 + GX) // 2:], GW, GH, GS4, 240)
FB = framebuf.FrameBuffer(memoryview(Y.buf)[(Y.FY * 240 + Y.FX) // 2:], Y.FW * Y.CELL, Y.FH * Y.CELL, GS4, 240)
WBB = bytearray(GW * GH // 2)                                           # the glass with nothing moving
WB = framebuf.FrameBuffer(WBB, GW, GH, GS4)
FLY = 180                                                               # the floor: rows 180..213
FLB = bytearray(120 * 34)
MV = memoryview(Y.buf)


# The copies go back and forth as bytes, not blits (a blit is pixel by pixel: 8 ms for the floor).
def fl_save():
    FLB[:] = MV[FLY * 120:(FLY + 34) * 120]


def fl_put():
    MV[FLY * 120:(FLY + 34) * 120] = FLB


@micropython.viper
def _rows(dst: ptr8, do: int, ds: int, src: ptr8, so: int, ss: int, w: int, n: int):
    """n rows of w bytes, src -> dst, each with its own stride. (Slices would allocate a row each.)"""
    r = 0
    while r < n:
        i = 0
        while i < w:
            dst[do + i] = src[so + i]
            i += 1
        do += ds
        so += ss
        r += 1


def wb_save():
    _rows(WBB, 0, 45, Y.buf, GY * 120 + GX // 2, 120, 45, GH)


def wb_put():
    _rows(Y.buf, GY * 120 + GX // 2, 120, WBB, 0, 45, 45, GH)
PET = ((188, 186), (196, 188))                                          # where the dog / the cat lies
CANDLES = (10, 114)

# ---- sprites (yule_art.bin, made by tools/art.py) --------------------------------------------------
_idx = {}
_cache = {}
with open("yule_art.bin", "rb") as _f:
    _h = _f.read(5)
    for _ in range(_h[4]):
        _e = _f.read(13)
        _idx[_e[:8].rstrip(b"\0").decode()] = (_e[8], _e[9], _e[10], _e[11] | _e[12] << 8)


def spr(name):
    """(framebuf, w, h, key) for a sprite, read from flash the first time."""
    s = _cache.get(name)
    if s is None:
        w, h, key, off = _idx[name]
        b = bytearray(w * h // 2)
        with open("yule_art.bin", "rb") as f:
            f.seek(off)
            f.readinto(b)
        s = _cache[name] = (framebuf.FrameBuffer(b, w, h, GS4), w, h, key)
    return s


def put(fb, name, x, y, pal=None):
    s = spr(name)
    if pal:
        fb.blit(s[0], x, y, s[3], pal)
    else:
        fb.blit(s[0], x, y, s[3])


def forget():
    _cache.clear()


# ---- the visitor book's numbers --------------------------------------------------------------------
bk = {}


def load_book():
    b = save.load("book", None)
    if not isinstance(b, dict):
        b = {}
    bk.clear()
    bk.update({"draws": b.get("draws", 0), "last": b.get("last", -1), "tiers": b.get("tiers", [0, 0, 0, 0]),
               "seen": b.get("seen", {}), "visits": b.get("visits", []), "gifts": b.get("gifts", {})})
    if chip.pub:                    # the hearth's certificate, once, so verify.py can check postcards
        h = save.load("hearth", None)
        if not isinstance(h, dict) or h.get("pub") != chip.hexpub():
            import binascii
            save.store("hearth", {"pub": chip.hexpub(), "cert": binascii.hexlify(chip.cert).decode(),
                                  "label": chip.label})


def keep_book():
    try:
        save.store("book", bk)
    except OSError:
        pass                        # a full flash: the fire keeps going


def log_draw(n, tier, kind, var):
    bk["draws"] += 1
    bk["last"] = n
    bk["tiers"][tier] += 1
    bk["seen"][kind] = bk["seen"].get(kind, 0) + 1
    if tier == 3:
        bk["visits"].append({"n": bk["seen"][kind], "draw": n, "ev": kind, "var": var, "scene": Y.st["scene"]})
        del bk["visits"][:-24]      # the newest 24
    if tier or bk["draws"] % 10 == 0:
        keep_book()


def gift(name):
    g = bk["gifts"]
    g[name] = min(3, g.get(name, 0) + 1)
    keep_book()


# ---- the hearth's snowflake --------------------------------------------------------------------------
DIRS = ((256, 0), (128, 222), (-128, 222), (-256, 0), (-128, -222), (128, -222))


def snowflake(fb, cx, cy, r, c):
    """Six arms; where the side branches sit, how long they are, a ring, a tip: all from the hearth's
    identity, so the same chip always draws the same flake."""
    h = chip.ident or b"\0" * 8
    nb = 1 + (h[2] & 1) + (h[2] >> 7)
    for k in range(6):
        dx, dy = DIRS[k]
        fb.line(cx, cy, cx + dx * r // 256, cy + dy * r // 256, c)
        for j in range(nb):
            t = r * (3 + ((h[3 + j] >> 2) & 3) + 2 * j) // 8
            if t >= r:
                continue
            bl = max(1, r * (1 + (h[3 + j] & 3)) // 8)
            px, py = cx + dx * t // 256, cy + dy * t // 256
            for e in ((k + 1) % 6, (k + 5) % 6):
                ex, ey = DIRS[e]
                fb.line(px, py, px + ex * bl // 256, py + ey * bl // 256, c)
        if h[6] & 1 and r > 6:
            tx, ty = cx + dx * r // 256, cy + dy * r // 256
            fb.fill_rect(tx - 1, ty - 1, 3, 3, c)
    if h[6] & 2 and r > 6:
        q = r // 3
        for k in range(6):
            a, b = DIRS[k], DIRS[(k + 1) % 6]
            fb.line(cx + a[0] * q // 256, cy + a[1] * q // 256, cx + b[0] * q // 256, cy + b[1] * q // 256, c)


# ---- drawing the room ------------------------------------------------------------------------------
def blocks(x0, y0, x1, y1, w, h=8):
    d.fill_rect(x0, y0, x1 - x0, y1 - y0, DARK)
    r = 0
    for y in range(y0, y1, h):
        for x in range(x0 - (r & 1) * w // 2, x1, w):
            a, b = max(x, x0), min(x + w - 1, x1)
            if b > a:
                d.fill_rect(a, y, b - a, min(h - 1, y1 - y), STONE)
        r += 1


def tree(fb, x, y, h, c, snow):
    """A pine: its top at x, y."""
    for k in range(h):
        w = k * 2 // 5 + (k % 4)
        fb.hline(x - w, y + k, 2 * w + 1, c)
        if k % 4 == 3:
            fb.hline(x - w, y + k, 2, snow)
    fb.fill_rect(x - 1, y + h, 3, 3, DARK)


def window_scene(scene):
    """The view through the glass, into GL (local coordinates)."""
    rnd = bytearray(chip.ident or b"\x5a\xa5" * 16)     # the same sky over the same hearth
    if scene == 0:
        GL.fill(SKY)
        for i in range(0, 28, 2):
            GL.pixel(rnd[i % 32] % GW, rnd[(i + 1) % 32] % 60, LIGHT if i % 3 else ICE)
            rnd[i % 32] = (rnd[i % 32] * 5 + 17) & 255
        GL.ellipse(68, 18, 9, 9, LIGHT, True)
        GL.pixel(65, 15, STONE); GL.fill_rect(70, 20, 2, 2, STONE); GL.pixel(66, 22, ICE)
        GL.ellipse(20, 96, 44, 18, ICE, True)
        GL.ellipse(78, 98, 40, 14, ICE, True)
        GL.fill_rect(0, 86, GW, 12, LIGHT)
        GL.ellipse(56, 88, 36, 4, LIGHT, True)
        GL.fill_rect(56, 74, 16, 12, DARK)              # a cabin, its window lit
        for k in range(7):                              # its snowy roof
            GL.hline(62 - k, 67 + k, 4 + 2 * k, LIGHT)
        GL.fill_rect(60, 78, 4, 4, GLOW)
        GL.fill_rect(66, 80, 3, 6, WOOD)
        for x, y, h in ((12, 50, 34), (30, 60, 25), (84, 58, 28), (46, 70, 15)):
            tree(GL, x, y, h, LEAF, LIGHT)
    else:
        GL.fill(SKY)
        for i in range(0, 16, 2):
            GL.pixel(rnd[i] % GW, rnd[i + 1] % 40, LIGHT)
        GL.ellipse(62, 26, 14, 14, LIGHT, True)
        GL.fill_rect(56, 20, 3, 3, STONE); GL.fill_rect(66, 30, 4, 3, STONE); GL.pixel(60, 33, STONE)
        GL.hline(34, 36, 22, STONE); GL.hline(40, 37, 30, STONE); GL.hline(70, 35, 14, STONE)
        GL.ellipse(40, 112, 70, 26, BG, True)
        GL.ellipse(90, 108, 30, 20, BG, True)
        GL.fill_rect(70, 52, 8, 40, BG)                 # the church: tower, spire, a lit window
        for k in range(14):
            GL.hline(74 - k // 3, 38 + k, 1 + 2 * (k // 3), BG)
        GL.fill_rect(73, 60, 3, 5, GLOW)
        GL.fill_rect(78, 70, 14, 22, BG)
        for x, y in ((14, 84), (30, 88), (48, 86), (60, 90)):   # headstones and a cross
            GL.fill_rect(x, y, 7, 10, STONE)
            GL.hline(x + 1, y - 1, 5, STONE)
        GL.fill_rect(39, 80, 2, 10, STONE); GL.fill_rect(36, 83, 8, 2, STONE)
        GL.line(4, 98, 8, 60, BG); GL.line(8, 60, 2, 44, BG); GL.line(8, 66, 20, 50, BG)    # a bare tree
        GL.line(20, 50, 26, 46, BG); GL.line(6, 52, 0, 48, BG); GL.line(14, 56, 16, 44, BG)
        for x in range(0, GW, 5):                       # the fence
            GL.vline(x, 92, 6, BG)
        GL.hline(0, 94, GW, BG)


def draw():
    """The whole room, then the copies of what moves over it, then one push."""
    sc = Y.st["scene"]
    forget()
    d.fill(WALL)
    Y.tint()
    g = bk["gifts"]
    # the wall: wainscot under the window
    d.fill_rect(132, 124, 108, 66, WALL)
    d.hline(132, 122, 108, WOOD)
    d.hline(132, 123, 108, DARK)
    for x in range(138, 240, 26):
        d.rect(x, 130, 20, 54, DARK)
    # the window and its sill
    d.fill_rect(GX - 4, GY - 4, GW + 8, GH + 8, WOOD)
    d.rect(GX - 4, GY - 4, GW + 8, GH + 8, DARK)
    d.fill_rect(GX - 8, GY + GH, GW + 16, 8, WOOD)
    d.hline(GX - 8, GY + GH, GW + 16, F4 if sc == 0 else STONE)
    d.hline(GX - 8, GY + GH + 7, GW + 16, DARK)
    window_scene(sc)
    wb_save()
    mullions()
    # the mantel and what's on it
    d.fill_rect(0, 56, 132, 6, WOOD)
    d.hline(0, 56, 132, F4 if sc == 0 else STONE)
    d.fill_rect(2, 62, 128, 6, WOOD)
    d.hline(2, 67, 128, DARK)
    for x in (6, 118):
        d.fill_rect(x, 68, 8, 8, WOOD)
        d.fill_rect(x + 2, 76, 4, 3, WOOD)
    for x in CANDLES:
        d.fill_rect(x, 42, 8, 14, LIGHT)
        d.vline(x + 4, 40, 2, BG)
    if sc == 0:
        d.ellipse(66, 30, 17, 17, LEAF, True)       # the wreath
        d.ellipse(66, 30, 9, 9, WALL, True)
        for a, b in ((-11, -9), (12, -8), (-14, 5), (7, 12), (15, 3), (-3, -15), (-8, 11)):
            d.fill_rect(66 + a, 30 + b, 3, 3, ACCENT)
        d.fill_rect(60, 42, 13, 5, ACCENT)
        d.fill_rect(62, 46, 2, 5, ACCENT)
        d.fill_rect(69, 46, 2, 5, ACCENT)
        if g.get("ornament"):
            put(d, "ornament", 38, 49)
    else:
        d.fill_rect(40, 6, 52, 44, WOOD)             # the portrait
        d.fill_rect(44, 10, 44, 36, DARK)
        d.ellipse(66, 31, 6, 7, STONE, True)
        for k in range(12):
            d.hline(66 - k // 2, 12 + k, 1 + (k // 2) * 2, BG)
        d.hline(54, 24, 25, BG)
        d.ellipse(66, 46, 14, 7, BG, True)
        d.fill_rect(59, 26, 3, 14, BG)
        d.fill_rect(71, 26, 3, 14, BG)
        portrait_eyes(DARK)
        d.fill_rect(96, 47, 10, 7, LIGHT)            # a skull
        d.fill_rect(98, 54, 6, 2, LIGHT)
        d.fill_rect(98, 49, 2, 2, BG)
        d.fill_rect(102, 49, 2, 2, BG)
        for k in (10, 18, 26):                       # cobwebs in the corner
            d.line(0, k, k, 0, STONE)
        d.line(0, 0, 22, 22, STONE)
        if g.get("gskull"):
            put(d, "gskull", 24, 47)
    # the surround, the firebox, the hearth
    blocks(6, 68, 126, 182, 16 if sc == 0 else 20)
    d.fill_rect(16, 104, 100, 8, DARK)
    for x in range(17, 115, 7):
        d.fill_rect(x, 105, 6, 7, STONE)
    d.fill_rect(Y.FX - 4, Y.FY - 4, Y.FW * Y.CELL + 8, Y.FH * Y.CELL + 6, BG)
    if sc == 0:
        stocking(14, 1)
        stocking(116, -1)
        garland(True)
    d.fill_rect(0, 182, 132, 8, STONE)
    d.hline(0, 182, 132, LIGHT if sc == 0 else STONE)
    d.hline(0, 189, 132, DARK)
    # the floor and the rug
    d.fill_rect(0, 190, 240, 24, WOOD)
    for y in (196, 203, 210):
        d.hline(0, y, 240, DARK)
    for i, y in enumerate((190, 196, 203)):
        for x in range((i * 37) % 50, 240, 50):
            d.vline(x, y + 1, 6, DARK)
    d.fill_rect(150, 196, 88, 16, ACCENT if sc == 0 else ICE)
    d.rect(152, 198, 84, 12, GLOW if sc == 0 else DARK)
    for x in range(158, 232, 8):
        d.fill_rect(x, 203, 3, 3, GLOW if sc == 0 else DARK)
    if sc == 0:
        xmas_tree(True)
    else:
        shelf()
    for i in range(g.get("present" if sc == 0 else "pumpkin", 0)):
        put(d, ("present", "present2")[i & 1] if sc == 0 else "pumpkin", 96 + i * 12 - (i == 2) * 30, 196 - (i & 1))
    fl_save()
    room["pose"] = -1
    room["branch"] = True
    pet()
    d.show()


TREE = []           # the Christmas tree's bulbs: (x, y)


def xmas_tree(full=False):
    """A tree in the corner under the window, its lights chasing like the garland's."""
    cx = 160
    if full:
        TREE.clear()
        for k in range(58):
            w = 3 + k * 2 // 5 + (k % 8 > 4) * 2
            d.hline(cx - w, 126 + k, 2 * w + 1, LEAF)
            if k % 8 == 6:
                d.hline(cx - w, 126 + k, 2 * w + 1, DARK if k & 16 else LEAF)
                for x in range(cx - w + 2, cx + w - 1, 6):
                    TREE.append((x, 126 + k - 2))
        d.fill_rect(cx - 3, 184, 7, 6, DARK)
        for k in range(5):                      # the star
            d.hline(cx - k // 2, 118 + k, 1 + (k // 2) * 2, GLOW)
        d.hline(cx - 4, 121, 9, GLOW)
        put(d, "present", 140, 181)
        put(d, "present2", 168, 182)
    k = Y.st["t"] // 10
    for i, (x, y) in enumerate(TREE):
        d.fill_rect(x, y, 2, 2, BULB_C[(i + k) % 4])


def shelf():
    """A bookshelf under the window: spines, a jar, a candle stub."""
    d.fill_rect(138, 128, 50, 62, WOOD)
    d.rect(138, 128, 50, 62, DARK)
    for y in (130, 150, 170):
        d.fill_rect(141, y, 44, 18, DARK)
        x = 142
        i = y
        while x < 182:
            w = 3 + (i * 7) % 4
            h = 12 + (i * 5) % 6
            d.fill_rect(x, y + 18 - h, w, h, (ACCENT, ICE, LEAF, STONE, F2)[i % 5])
            x += w + 1
            i += 3
    d.fill_rect(170, 155, 8, 13, STONE)         # a jar with something in it
    d.fill_rect(171, 160, 6, 7, LEAF)
    d.fill_rect(146, 120, 5, 8, LIGHT)          # a candle stub on top
    d.fill_rect(147, 116, 3, 4, GLOW)


def mullions():
    GL.fill_rect(44, 0, 3, GH, WOOD)
    GL.fill_rect(0, 46, GW, 3, WOOD)


def portrait_eyes(c):
    d.pixel(63, 30, c)
    d.pixel(69, 30, c)


def stocking(x, way):
    l = x if way > 0 else x - 14
    d.fill_rect(l + 2, 78, 12, 14, ACCENT)
    d.fill_rect(l + 2, 82, 12, 2, LIGHT)
    d.fill_rect(l + 2, 87, 12, 2, LEAF)
    toe = l + 2 if way > 0 else l - 6
    d.fill_rect(toe, 91, 18, 7, ACCENT)
    d.fill_rect(toe + (13 if way > 0 else 0), 93, 5, 5, LIGHT)
    d.fill_rect(l, 73, 16, 6, LIGHT)


# The Winter garland along the mantel: hooks every 33 px, a sag between, bulbs along it.
SAG = bytearray(132)
for _x in range(132):
    _d = _x % 33
    SAG[_x] = 63 + _d * (33 - _d) * 3 // 272
BULBS = tuple(range(6, 128, 10))
BULB_C = (ACCENT, GLOW, LIGHT, ICE)


def garland(full=False):
    if full:
        for x in range(2, 130):
            d.vline(x, SAG[x], 3, LEAF)
    k = Y.st["t"] // 10
    for i, x in enumerate(BULBS):
        d.fill_rect(x - 1, SAG[x] + 3, 3, 3, BULB_C[(i + k) % 4])


# ---- what moves ------------------------------------------------------------------------------------
room = {"pose": -1, "breath": 0, "branch": True}
SNOW = 18
fx, fy, fv = bytearray(SNOW), bytearray(SNOW), bytearray(SNOW)
for _i in range(SNOW):
    fx[_i], fy[_i], fv[_i] = random.getrandbits(7) % GW, random.getrandbits(7) % GH, 1 + random.getrandbits(1)


def window(t):
    """The glass, every other frame: its copy, what falls, the visitor, the frame's bars."""
    import yule_ev as ev
    wb_put()
    ev.under_window(t)
    sc = Y.st["scene"]
    if sc == 0:
        if room["branch"]:
            put(GL, "branch", 0, 6)
        for i in range(SNOW):
            y = fy[i] + fv[i]
            x = fx[i] + (1 if (t >> 3) + i & 4 else 0) - (1 if (t >> 3) + i & 8 else 0)
            if y >= GH - 10 + (i & 7):
                y, x = 0, random.getrandbits(7) % GW
            fy[i], fx[i] = y, x % GW
            GL.pixel(fx[i], y, LIGHT)
            if i & 3 == 0:
                GL.pixel(fx[i] + 1, y, LIGHT)
    else:
        for i in range(6):          # leaves drifting down
            y = fy[i] + (t & 2 and 1)
            if y >= GH - 8:
                y, fx[i] = 0, random.getrandbits(7) % GW
            fy[i] = y
            x = (fx[i] + ((t >> 2) + i * 5) % 7 - 3) % GW
            GL.hline(x, y, 2, ACCENT if i & 1 else WOOD)
    ev.over_window(t)
    mullions()
    d.show_rect(GX, GY, GW, GH)


def candles():
    L.tint(GLOW, 255, 170 + random.getrandbits(6), 30 + random.getrandbits(5))
    for x in CANDLES:
        lean = random.getrandbits(2) - 1 if random.getrandbits(2) == 0 else 0
        d.fill_rect(x - 1, 28, 10, 12, WALL)
        d.fill_rect(x + 2 + lean, 32, 4, 8, GLOW)
        d.fill_rect(x + 3 + lean, 35, 2, 4, F5)
        d.pixel(x + 3 + lean, 31, GLOW)
        d.show_rect(x - 1, 28, 10, 12)


def hearth_over():
    """Over the fire every frame: the logs, and the cauldron in the Midnight room."""
    FB.blit(LOGS, 4, Y.FH * Y.CELL - LH, WALL)
    if Y.st["scene"] == 1:
        put(FB, "cauldron", 16, 30)
        t = Y.st["t"]
        for k in range(3):          # it bubbles
            if (t + k * 7) % 12 < 6:
                FB.fill_rect(24 + ((t * 7 + k * 13) % 36), 30 + ((t + k) % 3), 2, 2, LEAF if k else LIGHT)


def ambient(t):
    """The lights and the pet, when they change."""
    import yule_ev as ev
    if Y.st["scene"] == 0 and t % 10 == 0:
        garland()
        d.show_rect(0, 62, 132, 12)
        xmas_tree()
        d.show_rect(136, 124, 48, 58)
    want = ev.pose()
    if want is None:
        if t % 32 == 0:
            room["breath"] ^= 1
        want = room["breath"]
    if want != room["pose"] or (ev.floor_busy() and not t & 1):     # the window takes the odd frames
        room["pose"] = want
        pet()
        d.show(FLY, Y.STRIP)


def pet():
    """The floor's copy, the pet in its pose (0/1 asleep, 'up', 'str'), anything walking on the floor."""
    import yule_ev as ev
    fl_put()
    sc = Y.st["scene"]
    p = room["pose"]
    name = ("dog" if sc == 0 else "cat") + (str(p) if p in (0, 1) else p if p in ("up", "str") else "0")
    x, y = PET[sc]
    put(d, name, x, y - (2 if p == "str" and sc == 1 else 0))
    ev.over_floor()


def make_logs():
    g = framebuf.FrameBuffer(bytearray(LW * LH // 2), LW, LH, GS4)
    g.fill(WALL)                        # WALL is the clear color here
    g.fill_rect(6, 16, 3, 4, BG)        # the grate
    g.fill_rect(LW - 9, 16, 3, 4, BG)
    g.fill_rect(3, 17, LW - 6, 2, BG)
    for x0, y0, w, h in ((8, 9, 60, 9), (18, 2, 42, 8)):
        g.fill_rect(x0, y0, w, h, DARK)
        g.hline(x0, y0, w, WOOD)
        g.hline(x0 + 5, y0 + h // 2, w - 14, BG)
        for e in (x0, x0 + w - 1):
            g.ellipse(e, y0 + h // 2, 3, h // 2, WOOD, True)
            g.pixel(e, y0 + h // 2, F3)
        for i in range(0, w - 8, 8):
            g.hline(x0 + 4 + i, y0 + h - 2 - (i // 8) % 2, 3, F3 if i % 16 else F2)
    return g


LW, LH = 76, 20
LOGS = make_logs()
