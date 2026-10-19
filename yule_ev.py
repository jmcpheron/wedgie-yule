# What visits. A draw (yule.py) picks a tier by its number, then the chip picks a visitor in that tier:
#   1000-9999 common (90%)   0500-0999 uncommon (5%)   0100-0499 rare (4%)   0000-0099 legendary (1%)
# Legendary has its own variations: 0000-0009 waves (or rears), 0000 comes down the chimney.
# Each visitor draws itself through hooks the room calls: over the fire (every frame: it keeps the clock),
# in the window (every other frame), on the floor. Some leave something behind: footprints, a glow, a gift.
import framebuf, random
import yule as Y
import yule_room as R
from yule_room import GL, FB, WB, GW, GH

BG, F1, F2, F3, F4, F5, ICE, STONE, DARK, WOOD, LIGHT, LEAF, SKY, ACCENT, GLOW, WALL = range(16)

KINDS = (
    (("dog", "bird", "branch", "star"), ("elf",), ("stag",), ("santa",)),
    (("cat", "crow", "eyes", "bat"), ("ghost",), ("eye",), ("horseman",)),
)
TITLES = {"dog": "DOG STRETCHES", "bird": "CARDINAL", "branch": "BRANCH SNOW", "star": "SHOOTING STAR",
          "elf": "ELF VISIT", "stag": "WINTER STAG", "santa": "SANTA", "cat": "CAT STRETCHES", "crow": "CROW ON THE SILL",
          "eyes": "PORTRAIT EYES", "bat": "BAT PASS", "ghost": "WINDOW GHOST", "eye": "CAULDRON EYE",
          "horseman": "HORSEMAN"}
VAR_TITLES = {("santa", "wave"): "SANTA WAVES", ("santa", "chimney"): "CHIMNEY VISIT",
              ("horseman", "wave"): "HORSEMAN REARS", ("horseman", "chimney"): "GOLDEN SKULL"}


def variation(tier, n):
    if tier < 3:
        return ""
    return "chimney" if n == 0 else "wave" if n < 10 else "pass"


def title(kind, var):
    return VAR_TITLES.get((kind, var), TITLES[kind])


def pal(m):
    """A palette for blit: slot -> slot, the rest unchanged (fades, glows)."""
    p = framebuf.FrameBuffer(bytearray(32), 16, 1, framebuf.RGB565)
    for i in range(16):
        p.pixel(i, 0, m.get(i, i))
    return p


cur = None              # the visit playing now
trace = {"aurora": 0, "brew": 0}     # frames left of a glow a visitor left


class Ev:
    dur = 200
    watch = False       # the pet lifts its head while it plays

    def __init__(s, var, n):
        s.t, s.var, s.n = 0, var, n

    def win(s):
        pass

    def fire(s):
        pass

    def floor(s):
        pass

    def heat(s):
        return 0

    def pose(s):
        return "up" if s.watch else None

    def busy(s):
        return False        # True: the floor is drawn again every frame

    def end(s):
        pass


# ---- common ----------------------------------------------------------------------------------------
class Stretch(Ev):
    dur = 170

    def pose(s):
        t = s.t
        return "up" if t < 40 or 100 <= t < 140 else "str" if t < 100 else None


class Bird(Ev):
    """A cardinal (a crow at midnight) flies in, lands on the sill, hops, flies off."""
    dur = 260

    def win(s):
        t = s.t
        land = (36, GH - 7)
        if t < 60:
            x, y = GW + 4 - (GW + 4 - land[0]) * t // 60, 20 + (land[1] - 20) * t * t // 3600
        elif t < 200:
            x, y = land[0] + ((t - 60) // 40) * 3 % 9, land[1]
        else:
            x, y = land[0] - (t - 200) * 2, land[1] - (t - 200) * (t - 200) // 40
        flap = t < 60 or t >= 200
        name = ("bird" if Y.st["scene"] == 0 else "crow") + ("1" if flap and t & 4 else "0")
        R.put(GL, name, x, y)


class Branch(Ev):
    """The snow on the branch lets go and falls."""
    dur = 90

    def __init__(s, var, n):
        super().__init__(var, n)
        s.p = [[random.getrandbits(4), 6 + random.getrandbits(1), 0] for _ in range(16)]

    def win(s):
        if s.t < 6:
            return
        R.room["branch"] = False
        for q in s.p:
            q[2] += 1
            q[1] += q[2] // 3
            if q[1] < GH - 10:
                GL.fill_rect(q[0], q[1], 2, 2, LIGHT)

    def end(s):
        pass                # the branch stays bare until the room is drawn again


class Star(Ev):
    dur = 40

    def win(s):
        t = s.t
        x, y = 86 - t * 3, 4 + t
        if x > -10:
            GL.line(x, y, x + 6, y - 2, LIGHT)
            GL.line(x + 6, y - 2, x + 12, y - 4, ICE)


class Eyes(Ev):
    """The witch in the portrait looks at you."""
    dur = 120

    def fire(s):
        if s.t == 10 or s.t == 100 or s.t in (50, 56):
            R.portrait_eyes(LEAF if s.t in (10, 56) else DARK)
            Y.d.show_rect(60, 28, 12, 4)

    def end(s):
        R.portrait_eyes(DARK)
        Y.d.show_rect(60, 28, 12, 4)


class Bat(Ev):
    dur = 130

    def win(s):
        t = s.t
        x = GW + 4 - t
        y = 18 + (t >> 2) % 6 if (t >> 5) & 1 else 23 - (t >> 2) % 6
        R.put(GL, BATS[(t >> 2) & 1], x, y)


BATS = ("bat0", "bat1")


# ---- uncommon --------------------------------------------------------------------------------------
class Elf(Ev):
    """An elf peeks over the sill, looks around, ducks. Footprints in the snow after."""
    dur = 320
    watch = True

    def win(s):
        t = s.t
        up = min(t, 30, max(0, s.dur - 20 - t))
        R.put(GL, "elf1" if (t // 40) & 1 else "elf0", 52, GH - up // 2 - 1)

    def end(s):
        for i in range(10):         # little boots, out along the snow
            x = 18 + i * 7
            WB.fill_rect(x, 90 + (i & 1) * 3, 2, 1, ICE)


class Ghost(Ev):
    """A ghost fades in at the glass, drifts, fades. A cold handprint stays."""
    dur = 320
    watch = True

    def __init__(s, var, n):
        super().__init__(var, n)
        s.p = (pal({LIGHT: SKY, BG: SKY}), pal({LIGHT: STONE, BG: DARK}), pal({LIGHT: ICE}), None)

    def win(s):
        t = s.t
        k = min(3, t // 15, max(0, (s.dur - t) // 15))
        x = 34 + (t >> 4) % 8 - 4 if (t >> 7) & 1 else 30 + (t >> 4) % 8
        R.put(GL, "ghost", x, 26 + ((t >> 3) & 3), s.p[k])

    def end(s):
        for x, y, w in ((60, 60, 5), (59, 61, 7), (59, 62, 7), (60, 63, 5)):
            WB.hline(x, y, w, ICE)
        for i in range(4):
            WB.vline(59 + i * 2, 56 + (i == 0) * 2, 4, ICE)


# ---- rare ------------------------------------------------------------------------------------------
class Stag(Ev):
    """The aurora comes up and a white stag walks out onto the snow. The glow stays a while."""
    dur = 520
    watch = True

    def win(s):
        t = s.t
        aurora(min(60, t), t)
        if t < 160:
            x = -30 + t * 60 // 160
        elif t < 360:
            x = 30
        else:
            x = 30 + (t - 360) * 70 // 160
        moving = t < 160 or t >= 360
        R.put(GL, "stag1" if moving and (t // 6) & 1 else "stag0", x, 58)

    def end(s):
        trace["aurora"] = 15000     # ten minutes of fading glow


def aurora(k, t):
    """Curtains of light over the trees: k 0..60 how strong."""
    if k <= 0:
        return
    step = 2 if k > 40 else 4 if k > 20 else 8
    for x in range(0, GW, step):
        h = 10 + ((x * 7 + (t >> 2)) % 23 if (x >> 3) & 1 else 22 - (x * 5 + (t >> 2)) % 19)
        y0 = 4 + ((x + (t >> 3)) % 9)
        GL.vline(x, y0, h * k // 60, LEAF if x % 8 < 4 else ICE)


class Eye(Ev):
    """Something in the cauldron opens an eye, looks around, blinks, sinks. The brew glows a while."""
    dur = 420
    watch = True

    def fire(s):
        t = s.t
        up = min(t, 40, max(0, s.dur - t - 20))
        y = 34 - up
        x = 22 + (((t // 50) % 3) - 1) * 2
        blink = t % 90 > 84
        R.put(FB, "eye1" if blink else "eye0", x, y)
        R.put(FB, "cauldron", 16, 30)          # the pot in front of what's in it

    def heat(s):
        return 2

    def end(s):
        trace["brew"] = 15000


# ---- legendary -------------------------------------------------------------------------------------
class Santa(Ev):
    """The sleigh crosses the moon. 0000-0009: it stops and Santa waves. 0000: he comes down the chimney,
    pets the dog, leaves a golden ornament. Every visit leaves a present by the hearth."""
    watch = True

    def __init__(s, var, n):
        super().__init__(var, n)
        s.stop = 120 if var != "pass" else 0
        s.cross = 330 + s.stop
        s.dur = s.cross + (560 if var == "chimney" else 0)
        s.trail = [[0, 0, 0] for _ in range(14)]

    def path(s):
        t = s.t
        if t < 255:
            u = t
        elif t < 255 + s.stop:
            u = 255                 # Santa in front of the moon
        else:
            u = t - s.stop
        x = -62 + u * 154 // 330
        return x, 8 + (x - 55) * (x - 55) // 160

    def win(s):
        t = s.t
        if t < s.cross:
            x, y = s.path()
            if t % 3 == 0:
                q = s.trail[(t // 3) % 14]
                q[0], q[1], q[2] = x + 2, y + 10, 30
            for q in s.trail:
                if q[2] > 0:
                    q[2] -= 1
                    GL.pixel(q[0], q[1] + (30 - q[2]) // 10, GLOW if q[2] > 12 else F4)
            R.put(GL, "sleigh1" if (t // 5) & 1 else "sleigh0", x, y)
            if s.stop and 255 <= t < 255 + s.stop and (t // 8) & 1:
                GL.fill_rect(x + 7, y - 2, 2, 3, ACCENT)     # his arm, waving
                GL.pixel(x + 7, y - 3, F4)

    def walk(s):
        """Down the chimney: (where, x, y, frame) or None."""
        t = s.t - s.cross
        if t < 0:
            return None
        step = "santa1" if (t // 6) & 1 else "santa0"
        if t < 60:
            return "fire", 30, -20 + t, "santa0"          # down into the firebox (its own x, y)
        if t < 220:
            return "floor", 54 + (t - 60) * 116 // 160, 189, step     # out across the floor to the dog
        if t < 340:
            return "floor", 170, 189, "santa2" if (t // 20) & 1 else "santa0"
        if t < 480:
            return "floor", 170 - (t - 340) * 116 // 140, 189, step
        return "fire", 30, 40 - (t - 480), "santa0"       # and back up

    def fire(s):
        w = s.walk()
        if w and w[0] == "fire":
            R.put(FB, w[3], w[1], w[2])

    def floor(s):
        w = s.walk()
        if w and w[0] == "floor":
            R.put(Y.d, w[3], w[1], w[2])

    def busy(s):
        w = s.walk()
        return bool(w) and (w[0] == "floor" or s.t - s.cross in (480, 481))   # one more, to wipe him off

    def heat(s):
        return -4 if s.var == "chimney" and s.t >= s.cross else 0

    def pose(s):
        w = s.walk()
        return "up" if w is None or w[0] == "floor" else 0

    def end(s):
        R.gift("present")
        if s.var == "chimney":
            R.gift("ornament")


class Horseman(Ev):
    """The Headless Horseman rides across the moon. 0000-0009: he rears and his head blazes. 0000: the fire
    roars and a golden skull is on the mantel. Every visit leaves a carved pumpkin."""
    watch = True

    def __init__(s, var, n):
        super().__init__(var, n)
        s.stop = 110 if var != "pass" else 0
        s.dur = 300 + s.stop + (120 if var == "chimney" else 0)

    def win(s):
        t = s.t
        if t >= 300 + s.stop:
            return
        if t < 178:
            u = t
        elif t < 178 + s.stop:
            u = 178                 # his head against the moon
        else:
            u = t - s.stop
        x = -46 + u * 140 // 300
        rear = s.stop and 178 <= t < 178 + s.stop
        y = 14 + ((t >> 2) & 1) - (4 if rear and (t >> 4) & 1 else 0)
        R.put(GL, "horse1" if (t // 5) & 1 and not rear else "horse0", x, y)
        for k in range(3 if not rear else 7):       # his head burns
            GL.pixel(x + 24 + random.getrandbits(3) % 5 - 1, y - 1 - random.getrandbits(2) - (k > 2) * 2,
                     F3 if k & 1 else F4)

    def heat(s):
        return 8 if s.var == "chimney" and s.t >= 300 + s.stop else 0

    def end(s):
        R.gift("pumpkin")
        if s.var == "chimney":
            R.gift("gskull")


CLASSES = {"dog": Stretch, "cat": Stretch, "bird": Bird, "crow": Bird, "branch": Branch, "star": Star,
           "eyes": Eyes, "bat": Bat, "elf": Elf, "ghost": Ghost, "stag": Stag, "eye": Eye, "santa": Santa,
           "horseman": Horseman}


# ---- what the room calls ---------------------------------------------------------------------------
def start(tier, kind, var, n):
    global cur
    if tier:                        # a new visitor of note: the old traces go, the window is fresh
        trace["aurora"] = trace["brew"] = 0
        R.window_scene(Y.st["scene"])
        R.wb_save()
    cur = CLASSES[kind](var, n)


def cancel():
    global cur
    cur = None


def heat():
    return cur.heat() if cur else 0


def over_fire(t):
    """Every frame, after the fire and the logs: the visit's clock, and anything in the firebox."""
    global cur
    if trace["brew"] and Y.st["scene"] == 1:
        trace["brew"] -= 1
        if t % 4 < 2 and random.getrandbits(14) < trace["brew"]:
            FB.fill_rect(20 + random.getrandbits(6) % 44, 22 + random.getrandbits(3), 2, 2, LEAF)
    if trace["aurora"]:
        trace["aurora"] -= 1
    if not cur:
        return
    cur.fire()
    cur.t += 1
    if cur.t >= cur.dur:
        e, cur = cur, None
        e.end()
        if isinstance(e, (Santa, Horseman)):
            R.draw()                # the gift by the hearth (and on the mantel)
            Y.strip_number()


def under_window(t):
    if trace["aurora"] and Y.st["scene"] == 0:
        aurora(trace["aurora"] * 40 // 15000 + 1, t)


def over_window(t):
    if cur:
        cur.win()


def over_floor():
    if cur:
        cur.floor()


def pose():
    return cur.pose() if cur else None


def floor_busy():
    return bool(cur) and cur.busy()
