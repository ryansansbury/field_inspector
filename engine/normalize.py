"""Turn a value as printed into its canonical form by field kind, so a read, a recognized word and the key compare as
equals.

It never guesses a character. O stays O and 0 stays 0, since a model number that differs by one of them is a different
model. Numbers stay strings ("18.60 A" becomes "18.6"), and unit changes move the decimal point as text, so Python and
the page's site/normalize.js give the same answer for every input. The parity vectors in tests/vectors/ prove it. Only
ASCII ranges appear in the patterns, because Python and JavaScript read \\d and \\b differently.
"""
import re

KINDS = ("code", "volts", "phase", "amps", "capacity", "refrigerant")
PHASE_SIGNS = "ØøΦφϕ"
# Letters from other alphabets that look like Latin ones. The recognizer sometimes returns them ("МCА" for MCA).
LOOKALIKES = {"А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O", "Р": "P", "С": "C", "Т": "T",
              "Х": "X", "У": "Y", "І": "I", "Ј": "J", "Ѕ": "S", "а": "a", "е": "e", "к": "k", "м": "m", "о": "o",
              "р": "p", "с": "c", "т": "t", "х": "x", "у": "y", "і": "i", "ј": "j", "ѕ": "s", "Α": "A", "Β": "B",
              "Ε": "E", "Ζ": "Z", "Η": "H", "Ι": "I", "Κ": "K", "Μ": "M", "Ν": "N", "Ο": "O", "Ρ": "P", "Τ": "T",
              "Υ": "Y", "Χ": "X", "ο": "o"}
VOLT_MIN, VOLT_MAX = 90, 600
CAPACITY_UNITS = (("GALLONS", "GAL"), ("GALLON", "GAL"), ("GALS", "GAL"), ("GAL", "GAL"), ("BTU/HR", "BTUH"),
                  ("BTU/H", "BTUH"), ("BTUH", "BTUH"), ("BTU", "BTUH"), ("MBH", "MBH"), ("KW", "KW"), ("WATTS", "W"),
                  ("WATT", "W"), ("W", "W"), ("TONS", "TON"), ("TON", "TON"), ("L", "L"))
CAPACITY_ORDER = ("GAL", "BTUH", "KW", "TON", "L")
NUM = r"(?:[0-9]+(?:\.[0-9]+)?|\.[0-9]+)"
CAPACITY = re.compile("(" + NUM + r") ?(GALLONS|GALLON|GALS|GAL|BTU ?/ ?HR|BTU ?/ ?H|BTUH|BTU|MBH|KW|WATTS|WATT|W|TONS"
                      r"|TON|L)(?![A-Z])")
REFRIGERANT = re.compile(r"(?:^|[^A-Z0-9])(?:R|HFC|HCFC|HFO|HC) ?-? ?([0-9]{2,4}[A-Z]{0,2})(?![A-Z0-9])")
PHASE_DIGIT = re.compile(r"(?:^|[^0-9.])([13])(?=[^0-9.]|$)")
THOUSANDS = re.compile(r"([0-9]),([0-9]{3})(?![0-9])")
VOLT_NUMBER = re.compile("(" + NUM + r")( ?)([A-Z]?)")


def clean(text):
    """Upper case, the phase sign read as PH, and anything outside A to Z, 0 to 9 and . , / - as a space."""
    t = str(text if text is not None else "")
    for sign in PHASE_SIGNS:
        t = t.replace(sign, "PH")
    t = "".join(LOOKALIKES.get(ch, ch) for ch in t)
    t = re.sub(r"[^A-Z0-9.,/ -]", " ", t.upper())
    return " ".join(t.split())


def drop_thousands(t):
    """'60,000' to '60000', repeated so '1,000,000' comes out whole. A comma anywhere else stays."""
    while True:
        out = THOUSANDS.sub(r"\1\2", t)
        if out == t:
            return out
        t = out


def number(s):
    """A plain decimal in its shortest form: '018.60' to '18.6', '12.0' to '12', '.5' to '0.5'. None otherwise."""
    m = re.fullmatch(r"([0-9]*)(?:\.([0-9]*))?", s or "")
    if not m or not (m.group(1) or m.group(2)):
        return None
    whole = m.group(1).lstrip("0") or "0"
    frac = (m.group(2) or "").rstrip("0")
    return whole + ("." + frac if frac else "")


def shift(num, places):
    """Move a canonical number's decimal point as text: shift('4500', -3) is '4.5' and shift('60', 3) is '60000'."""
    whole, _, frac = num.partition(".")
    digits, point = whole + frac, len(whole) + places
    if point <= 0:
        digits, point = "0" * (1 - point) + digits, 1
    if point > len(digits):
        digits += "0" * (point - len(digits))
    return number(digits[:point] + "." + digits[point:])


def numbers_in(t):
    return re.findall(NUM, t)


def code(text):
    t = re.sub(r"[^A-Z0-9]", "", clean(text))
    return t or None


def volts(text):
    """Every voltage rating in the text, rising, joined by '/'. A number counts when it's between 90 and 600 and isn't
    followed by another unit's letter, so '200A' (a bus rating) and '60HZ' stay out."""
    t = drop_thousands(clean(text))
    found = []
    for m in VOLT_NUMBER.finditer(t):
        n, letter = m.group(1), m.group(3)
        if letter and letter != "V":
            continue
        value = number(n)
        if value is not None and VOLT_MIN <= float(value) <= VOLT_MAX and value not in found:
            found.append(value)
    if not found:
        return None
    return "/".join(sorted(found, key=float))


def phase(text):
    """'1' or '3' when the text names exactly one of them (1PH, the phase sign, SINGLE, THREE), else None."""
    t = clean(text)
    found = set(m.group(1) for m in PHASE_DIGIT.finditer(t))
    words = t.replace("-", " ").split()
    if "SINGLE" in words:
        found.add("1")
    if "THREE" in words:
        found.add("3")
    return found.pop() if len(found) == 1 else None


def amps(text):
    """The one number in the text, or None when there's none or more than one."""
    found = [number(n) for n in numbers_in(drop_thousands(clean(text)))]
    distinct = list(dict.fromkeys(f for f in found if f is not None))
    return distinct[0] if len(distinct) == 1 else None


def capacity_pairs(text):
    """Every number with a capacity unit in the text, canonical, in order."""
    t = drop_thousands(clean(text))
    out = []
    for m in CAPACITY.finditer(t):
        n, unit = number(m.group(1)), m.group(2).replace(" ", "")
        unit = dict(CAPACITY_UNITS).get(unit, unit)
        if n is None:
            continue
        if unit == "W":
            n, unit = shift(n, -3), "KW"
        elif unit == "MBH":
            n, unit = shift(n, 3), "BTUH"
        out.append(f"{n} {unit}")
    return out


def capacity(text):
    """The capacity the field means, by the order in config/fields.json: gallons, then BTU/h, kW, tons and liters."""
    pairs = capacity_pairs(text)
    for unit in CAPACITY_ORDER:
        for p in pairs:
            if p.endswith(" " + unit):
                return p
    return None


def refrigerants(text):
    return ["R" + m.group(1) for m in REFRIGERANT.finditer(clean(text))]


def refrigerant(text):
    found = refrigerants(text)
    return found[0] if found else None


CANON = {"code": code, "volts": volts, "phase": phase, "amps": amps, "capacity": capacity, "refrigerant": refrigerant}


def canon(kind, text):
    """The canonical form of a value of this kind, or None when the text doesn't hold one."""
    if kind not in CANON:
        raise ValueError(f"unknown kind {kind}")
    if text is None:
        return None
    return CANON[kind](text)


def pieces(kind, text):
    """Every canonical value of this kind that a stretch of recognized text holds. The confirmation step compares a
    read against these, so '208/230-1-60' offers the volts '208/230' and the phase '1', and '14.1/82' offers two amps."""
    if kind == "amps":
        found = [number(n) for n in numbers_in(drop_thousands(clean(text)))]
    elif kind == "capacity":
        found = capacity_pairs(text)
    elif kind == "refrigerant":
        found = refrigerants(text)
    else:
        found = [canon(kind, text)]
    return list(dict.fromkeys(f for f in found if f))


def distance(a, b):
    """The Levenshtein distance: the fewest single-character edits that turn one string into the other."""
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def words(text):
    """The words of a label or a recognized line for label matching: case folded, the phase sign as PH, punctuation
    dropped, '/' and '-' as spaces."""
    return re.sub(r"[^A-Z0-9 ]", " ", clean(text).replace("/", " ").replace("-", " ")).split()
