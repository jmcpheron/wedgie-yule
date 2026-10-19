# The Trust M, for the draw and the postcards. Nothing here makes a key, writes to the chip or locks it:
# - identity: the factory key's public key, from the chip's Infineon-signed certificate. Its SHA-256 names
#   the hearth ("HEARTH 7C2A") and shapes its snowflake (yule_room.snowflake).
# - draws: true random bytes, rejection sampled into 0000-9999 (no modulo bias). If the chip doesn't
#   answer there's no draw: never a number from anywhere else.
# - seals: the factory key signs a postcard's SHA-256. Only yule_book calls seal(), and only after the
#   person said yes on the wedgie's own screen (ui.ask, real presses).
import hashlib, binascii

c = None            # the optiga.Chip, kept open
pub = None          # the factory key's public key: 04 || X || Y
cert = None         # the certificate it came from
ident = None        # sha256(pub)
label = ""          # "HEARTH 7C2A"
name = ""           # "Hearth 7C2A", for sentences (MicroPython's str has no .title())


here = None         # a Trust M answered on the bus (None: not looked yet)


def present():
    """Is a Trust M there? Asked once, quickly (opening a chip that isn't there waits out a 10 s timeout:
    frozen fire). No pull-ups on SDA/SCL: nothing is on the bus. Else knock at 0x30 for up to 200 ms: the
    Trust M NACKs its address while it sleeps, and wakes to the knocking (trustm.py). A scan doesn't find it."""
    global here
    if here is None:
        here = False
        try:
            import time
            from machine import Pin, I2C
            for p in (4, 5):
                v = Pin(p, Pin.IN, Pin.PULL_DOWN).value()
                Pin(p, Pin.IN)
                if not v:
                    return False
            i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400000)
            for _ in range(200):
                try:
                    i2c.writeto(0x30, b"\x82")
                    here = True
                    break
                except OSError:
                    time.sleep_ms(1)
        except Exception:
            pass
    return here


def _chip():
    global c
    if c is None:
        import optiga
        c = optiga.Chip()
    return c


def open():
    """Find the chip and read who it is. False (and no draws) without a Trust M."""
    global pub, cert, ident, label, name
    if not present():
        return False
    try:
        import optiga
        k = _chip().read(optiga.CERT)
        i = k.find(b"\x03\x42\x00\x04")           # the P-256 key's BIT STRING in the certificate
        if i < 0:
            return False
        cert, pub = bytes(k), bytes(k[i + 3:i + 68])
        ident = hashlib.sha256(pub).digest()
        label = "HEARTH %02X%02X" % (ident[0], ident[1])
        name = "Hearth" + label[6:]
        return True
    except Exception:
        return False


def rand(n):
    """n true random bytes from the chip, or None. A chip that stopped answering (a host's chip check
    resets it) is opened again once."""
    global c
    if not present():
        return None
    for _ in range(2):
        try:
            return _chip().random(n)
        except Exception:
            c = None
    return None


def below(n):
    """A fair whole number 0 <= x < n (n up to 65536) from the chip, or None."""
    lim = 65536 // n * n                 # at or above this, small numbers would come up more often
    while True:
        b = rand(16)
        if b is None:
            return None
        for i in range(0, 16, 2):
            x = b[i] << 8 | b[i + 1]
            if x < lim:
                return x % n


def number():
    """The draw: 0..9999, every number as likely as any other, or None."""
    return below(10000)


def hexpub():
    return binascii.hexlify(pub).decode() if pub else ""


def record(scene, event, variation, visit, draw):
    """What a postcard says, and exactly what the chip signs the SHA-256 of. verify.py rebuilds it."""
    return ("wedgie hearth postcard v1\nhearth %s\nscene %s\nevent %s\nvariation %s\nvisit %d\ndraw %04d\nrules 1\n"
            % (hexpub(), scene, event, variation, visit, draw)).encode()


def seal(rec):
    """The factory key's ECDSA signature over sha256(rec), as two 64-digit hex strings."""
    import optiga
    r, s = _chip().sign(optiga.FACTORY_KEY, hashlib.sha256(rec).digest())
    return "%064x" % r, "%064x" % s
