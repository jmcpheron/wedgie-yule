# The visitor book (grey X in the room): the draws so far, then a postcard for every legendary visit.
# Green on a postcard asks to seal it: the screen says what gets signed, and only a real press on the
# wedgie says yes (ui.ask). Then the Trust M's factory key signs the postcard's SHA-256 (yule_chip.seal).
# Loaded only while it's open (yule.book), so the room doesn't carry it.
import time
import lcd as L
import ui
import yule as Y
import yule_chip as chip
import yule_room as R

d = Y.d
# The postcard's own colors, in slots ui.say's button squares don't use (1 4 6 10 11 13 stay as they are).
CARD = {15: ((18, 36, 28), (28, 18, 40)), 9: ((236, 222, 184), (226, 214, 190)), 3: ((70, 46, 30), (50, 30, 60)),
        12: ((176, 26, 32), (226, 100, 20)), 14: ((220, 170, 60), (220, 170, 60)), 2: ((34, 56, 120), (70, 40, 130)),
        7: ((170, 150, 120), (160, 140, 150))}
BACK, PAPER, INK, WAX, GOLD, STAMP, FADED = 15, 9, 3, 12, 14, 2, 7
WHO = {"santa": "Santa", "horseman": "Horseman"}


def wait():
    """The next key: A B X Y left right (up down press ignored)."""
    time.sleep_ms(250)
    Y.keys.pressed()
    while True:
        for k in Y.keys.pressed():
            if k in ("A", "B", "X", "Y", "left", "right"):
                return k
        time.sleep_ms(30)


def summary(visits):
    b = R.bk
    t = b["tiers"]
    s = b["seen"]
    lines = [(chip.name if chip.name else "no Trust M: no draws", ui.INK)]
    if b["draws"]:
        lines.append(("%d draws, last %04d" % (b["draws"], b["last"]), ui.MUTED))
    lines.append(("Santa %d  Horseman %d" % (s.get("santa", 0), s.get("horseman", 0)), ui.INK))
    lines.append(("rare %d  uncommon %d" % (t[2], t[1]), ui.MUTED))
    ui.page(d, "Visitor Book", lines, "{r} back" + ("  joystick: cards" if visits else ""))


def card(v, i, n):
    """A postcard: who, which visit, the draw, and the wax seal once the chip has signed it."""
    sc = v.get("scene", 0)
    d.fill(BACK)
    for k, c in CARD.items():
        L.tint(k, *c[sc])
    d.text("%d of %d" % (i + 1, n), 8, 10, ui.MUTED)
    d.fill_rect(10, 30, 220, 156, PAPER)
    d.rect(14, 34, 212, 148, FADED)
    d.text("NORTH POLE POST" if sc == 0 else "HOLLOW POST", 22, 46, INK)
    d.fill_rect(182, 40, 36, 40, ui.WHITE)            # the stamp: the hearth's snowflake
    d.fill_rect(185, 43, 30, 34, STAMP)
    for x in range(182, 218, 4):
        d.pixel(x, 40, PAPER)
        d.pixel(x, 79, PAPER)
    R.snowflake(d, 200, 60, 11, ui.WHITE)
    for k in range(3):                                  # the postmark
        for x in range(150, 186, 2):
            d.pixel(x, 66 + k * 5 + (x >> 2 & 1), FADED)
    who = WHO.get(v["ev"], v["ev"])
    d.big_text(who.upper()[:8], 22, 74, INK, 2)
    d.text("VISIT #%04d" % v["n"], 22, 98, INK)
    d.text("DRAW %04d" % v["draw"], 22, 112, INK)
    if v.get("var") not in (None, "", "pass"):
        d.text({"wave": "IT WAVED" if sc == 0 else "IT REARED", "chimney": "CAME INSIDE"}.get(v["var"], ""), 22, 126, FADED)
    d.hline(22, 142, 140, FADED)
    sealed = bool(v.get("sig"))
    if sealed:
        d.text("SIGNED BY", 22, 150, INK)
        d.text(chip.label or "HEARTH", 22, 162, INK)
        d.ellipse(196, 152, 18, 18, WAX, True)
        d.ellipse(196, 152, 18, 18, INK)
        R.snowflake(d, 196, 152, 10, GOLD)
    else:
        d.text("NOT SEALED YET", 22, 156, FADED)
    ui.say(d, "{k} receipt  {r} back" if sealed else "{g} seal it  {r} back", 222, ui.MUTED)
    d.show()


def seal(v):
    """Ask, on the wedgie's own screen, then sign. Only ui.ask's real presses count."""
    who = WHO.get(v["ev"], v["ev"])
    if not chip.pub:
        ui.page(d, "Can't seal", [("no Trust M answered", ui.INK)], "{g} ok")
        wait()
        return
    rec = chip.record(("winter", "midnight")[v.get("scene", 0)], v["ev"], v.get("var") or "pass", v["n"], v["draw"])
    if not ui.ask(d, "Seal postcard", ["%s visit #%04d, draw %04d" % (who, v["n"], v["draw"]),
                                       "the Trust M signs it as " + chip.name], yes="seal", no="not now"):
        return
    ui.progress("Sealing", "on the Trust M", bar=False)
    try:
        v["sig"] = list(chip.seal(rec))
        R.keep_book()
    except Exception:
        ui.page(d, "Not sealed", [("the chip didn't answer", ui.INK)], "{g} ok")
        wait()


def receipt(v):
    """The signature, to check by hand (verify.py does it from a saves backup)."""
    r, s = v["sig"]
    ui.page(d, "Receipt", [], "{r} back", show=False)
    y = 92
    d.text("%s #%04d  draw %04d" % (WHO.get(v["ev"], v["ev"]), v["n"], v["draw"]), 8, y, ui.INK)
    for name, h in (("r", r), ("s", s)):
        y += 14
        d.text(name, 8, y, ui.MUTED)
        for k in range(0, 64, 26):
            d.text(h[k:k + 26], 24, y, ui.INK)
            y += 10
    d.show()
    while wait() != "Y":
        pass


def run():
    visits = R.bk["visits"][::-1]           # newest first
    i = -1                                  # -1: the summary page
    while True:
        if i < 0:
            summary(visits)
        else:
            card(visits[i], i, len(visits))
        k = wait()
        if k == "Y":
            return
        if k == "right" and i < len(visits) - 1:
            i += 1
        elif k == "left" and i >= 0:
            i -= 1
        elif i >= 0 and k == "A" and not visits[i].get("sig"):
            seal(visits[i])
        elif i >= 0 and k == "X" and visits[i].get("sig"):
            receipt(visits[i])
