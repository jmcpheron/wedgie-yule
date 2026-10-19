#!/usr/bin/env python3
"""Check Yule Log postcards: every sealed one in a saves backup, against the hearth's key.

  python3 wedgie.py saves backup saves.json        # wedgie.dev/wedgie.py: the wedgie asks first
  python3 verify.py saves.json                       # needs: pip install cryptography

For each postcard it rebuilds the exact text the chip signed (yule_chip.record) and checks the ECDSA
P-256 signature with the public key in the hearth's certificate (the Trust M's factory key, certified by
Infineon). It also checks that key is the one inside that certificate.

What a good signature proves: this chip's key signed this postcard, and nothing in it changed since. What
it doesn't prove: that the draw was honest, or that anything was on the screen. The chip signs what the
app hands it."""
import base64, binascii, hashlib, json, sys

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

SCENES = ("winter", "midnight")


def record(pub, scene, event, variation, visit, draw):
    """The same bytes as yule_chip.record."""
    return ("wedgie hearth postcard v1\nhearth %s\nscene %s\nevent %s\nvariation %s\nvisit %d\ndraw %04d\nrules 1\n"
            % (pub, scene, event, variation, visit, draw)).encode()


def check(pub_hex, rec, r_hex, s_hex):
    key = ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), binascii.unhexlify(pub_hex))
    try:
        key.verify(encode_dss_signature(int(r_hex, 16), int(s_hex, 16)), rec, ec.ECDSA(hashes.SHA256()))
        return True
    except InvalidSignature:
        return False


def load(path):
    b = json.load(open(path))
    files = b.get("files", {})
    get = lambda n: json.loads(base64.b64decode(files["/saves/yule/%s.json" % n])) if "/saves/yule/%s.json" % n in files else None
    return get("hearth"), get("book")


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    hearth, book = load(sys.argv[1])
    if not hearth or not book:
        sys.exit("no Yule Log saves (hearth, book) in %s" % sys.argv[1])
    pub = hearth["pub"]
    label = "HEARTH %s" % hashlib.sha256(binascii.unhexlify(pub)).hexdigest()[:4].upper()
    cert = binascii.unhexlify(hearth.get("cert", ""))
    in_cert = binascii.unhexlify(pub) in cert
    print("%s  key %s...%s  %s" % (label, pub[:10], pub[-6:], "in its certificate" if in_cert else "NOT in its certificate"))
    bad = n = 0
    for v in book.get("visits", []):
        if not v.get("sig"):
            continue
        n += 1
        rec = record(pub, SCENES[v.get("scene", 0)], v["ev"], v.get("var") or "pass", v["n"], v["draw"])
        ok = check(pub, rec, *v["sig"])
        bad += not ok
        print("%s  %s visit #%04d, draw %04d (%s)" % ("ok  " if ok else "BAD ", v["ev"], v["n"], v["draw"], v.get("var") or "pass"))
    print("%d sealed postcards, %d bad" % (n, bad) if n else "no sealed postcards yet")
    sys.exit(1 if bad or not in_cert else 0)


if __name__ == "__main__":
    main()
