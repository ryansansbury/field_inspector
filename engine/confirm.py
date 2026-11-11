"""The confirmation step: is each value the AI read really on the photo, and by its label?

The photo's own text comes from on-device text recognition (data/ocr/<photo>.json), run by the owner's script and never
by a model. For each read this looks for the value among the recognized words after normalizing both sides by the
field's kind, then asks where it sits. Three levels come out.

- Found means the exact value by its label (or carrying its own unit, for fields where a unit says enough) on a line
  the recognizer rated 0.5 or higher.
- Partly found means the exact value away from its label, one character off by its label (codes and refrigerants of
  four or more characters only), pieced together across two lines, or on a line rated under 0.5.
- Not found means anything else, including a value the AI said it couldn't read.

A value by another field's label of the same kind, or by a label no field uses (RLA, HZ, SERIAL and the rest of
config/fields.json), is away from its label, so a minimum circuit ampacity read as the largest breaker can't be found.
The box comes from the recognized words whenever they hold the value, and otherwise it's the AI's own box, marked
approximate. This is the vision version of the Call Companion's evidence check. The owner's draft read uses the same
matching to suggest each field's value. Standard library only.
"""
import json
import re
from pathlib import Path

from engine import normalize as norm

HERE = Path(__file__).resolve().parent.parent
FOUND, PARTIAL, MISSING = "found", "partial", "missing"
LEVELS = (FOUND, PARTIAL, MISSING)
CONF_MIN = 0.5      # a line the recognizer rated under this can't confirm on its own
ROW = 0.75          # same row: centers within this many label heights, after the photo's tilt is taken out
BELOW = 2.5         # below: starting within this many label heights under the label
REACH = 2.0         # below: starting no further than this many label heights left or right of the label
GROW = 0.5          # a field with no label must sit inside the AI's box grown by half on every side
ONE_OFF_KINDS = ("code", "refrigerant")
BREAKER_SIZES = ("15", "20", "25", "30", "35", "40", "45", "50", "60", "70", "80", "90", "100", "125", "150", "200")


def load_fields(path=None):
    return json.loads(Path(path or HERE.joinpath("config", "fields.json")).read_text(encoding="utf-8"))


def to_px(box, w, h):
    return (box[0] * w, box[1] * h, box[2] * w, box[3] * h)


def to_frac(box, w, h):
    return [round(min(1.0, max(0.0, v)), 4) for v in (box[0] / w, box[1] / h, box[2] / w, box[3] / h)]


def union(boxes):
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def center(box):
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def label_owners(fields):
    """{label words: owners}, where an owner is a field id, "serial", or "other" for a label no field reads."""
    owners = {}
    for f in fields["fields"]:
        for lab in f.get("labels", ()):
            owners.setdefault(tuple(norm.words(lab)), set()).add(f["id"])
    for key, group in (("other", "other_labels"), ("serial", "serial_labels")):
        for lab in fields.get(group, ()):
            owners.setdefault(tuple(norm.words(lab)), set()).add(key)
    return owners


class Photo:
    """One photo's recognized text, with its labels found and its candidate values ready to look up."""

    def __init__(self, ocr, fields):
        self.w, self.h = float(ocr["w"]), float(ocr["h"])
        self.fields = {f["id"]: f for f in fields["fields"]}
        self.owners = label_owners(fields)
        self.lines = []
        for line in ocr.get("lines") or []:
            words = [{"text": wd["text"], "box": to_px(wd["box"], self.w, self.h)} for wd in line.get("words") or []]
            if words:
                self.lines.append({"i": len(self.lines), "text": line.get("text", ""), "conf": line.get("conf", 1.0),
                                   "box": union([wd["box"] for wd in words]), "words": words})
        self.slope = self.tilt()
        self.slopes = [self.slope_near(line) for line in self.lines]
        self.labels = self.find_labels(self.owners)
        self.label_words = set(word for lab in self.owners for word in lab)
        self._cands, self._pieces = {}, {}

    @staticmethod
    def line_slope(line):
        """How far a line of two or more words climbs or falls per pixel across, or None for a short one."""
        a, b = line["words"][0]["box"], line["words"][-1]["box"]
        run = center(b)[0] - center(a)[0]
        if len(line["words"]) >= 2 and run > 3 * (a[3] - a[1]):
            return (center(b)[1] - center(a)[1]) / run
        return None

    def tilt(self):
        """The photo's tilt: the median slope over every line long enough to have one."""
        slopes = sorted(s for s in (self.line_slope(line) for line in self.lines) if s is not None)
        return slopes[len(slopes) // 2] if slopes else 0.0

    def slope_near(self, line):
        """A line's own slope, or the median of the lines near it, since a perspective shot tilts each row a little
        differently from the next."""
        own = self.line_slope(line)
        if own is not None:
            return own
        cy, h = center(line["box"])[1], line["box"][3] - line["box"][1]
        near = sorted(s for s in (self.line_slope(other) for other in self.lines
                                  if abs(center(other["box"])[1] - cy) < 6 * h) if s is not None)
        return near[len(near) // 2] if near else self.slope

    def level(self, box):
        """A box shifted up or down by the photo's tilt at its center, as if the photo were held level."""
        dy = self.slope * (center(box)[0] - self.w / 2)
        return (box[0], box[1] - dy, box[2], box[3] - dy)

    # ------------------------------------------------------------------ labels
    def find_labels(self, owners):
        """Every place a label occurs, longest first: "HZ" inside "V PH HZ" belongs to the longer label."""
        found = []
        for line in self.lines:
            flat = [(word, j) for j, wd in enumerate(line["words"]) for word in norm.words(wd["text"])]
            seq = [word for word, _ in flat]
            for lab, own in owners.items():
                n = len(lab)
                for s in range(len(seq) - n + 1):
                    if n and tuple(seq[s:s + n]) == lab:
                        found.append({"line": line["i"], "s": s, "e": s + n - 1, "a": flat[s][1],
                                      "b": flat[s + n - 1][1], "n": n, "owners": set(own)})
        keep = [o for o in found if not any(p["line"] == o["line"] and p["n"] > o["n"] and p["s"] <= o["s"]
                                            and o["e"] <= p["e"] for p in found)]
        merged = {}
        for o in keep:
            k = (o["line"], o["s"], o["e"])
            if k in merged:
                merged[k]["owners"] |= o["owners"]
            else:
                merged[k] = o
        for o in merged.values():
            o["box"] = union([wd["box"] for wd in self.lines[o["line"]]["words"][o["a"]:o["b"] + 1]])
        return list(merged.values())

    def relation(self, c, lab):
        """(how, distance) when the candidate sits by the label: 0 on its line after it, 1 on its row to its right, 2
        under it. None otherwise. Distances are in label heights. The row runs out from the label's last word at the
        tilt of the label's own line, since a perspective shot tilts each row a little differently, and a row match
        further off that line counts as further away (changed 11/9 after the first real text recognition)."""
        L, C = lab["box"], c["box"]
        last = self.lines[lab["line"]]["words"][lab["b"]]["box"]
        lh = max(1.0, last[3] - last[1])
        if lab["line"] == c["line"]:
            fused = lab["b"] == c["a"] == c["b"]
            return (0, max(0.0, (C[0] - L[2]) / lh)) if lab["b"] < c["a"] or fused else None
        end, mid = center(last), center(C)
        off = abs(mid[1] - end[1] - self.slopes[lab["line"]] * (mid[0] - end[0])) / lh
        if off <= ROW and C[0] >= L[2] - 0.5 * lh and C[0] - L[2] <= 0.6 * self.w:
            return (1, max(0.0, (C[0] - L[2]) / lh) + 4 * off)
        L, C = self.level(L), self.level(C)
        if L[3] - 0.2 * lh <= C[1] <= L[3] + BELOW * lh and C[2] >= L[0] - REACH * lh and C[0] <= L[2] + REACH * lh:
            return (2, max(0.0, (C[1] - L[3]) / lh))
        return None

    def governing(self, c, extra=()):
        """The label a candidate sits by: on its own line first, then its row, then above it, nearest first."""
        best = None
        for lab in list(self.labels) + list(extra):
            r = self.relation(c, lab)
            if r is not None and (best is None or (r, -lab["n"]) < (best[0], -best[1]["n"])):
                best = (r, lab)
        return best[1] if best else None

    def ai_labels(self, f, label):
        """The label the AI reported, tried as one more label for this field, unless it holds a label that belongs to
        anything else (so an AI can't label a minimum circuit ampacity as the largest breaker and have it found)."""
        words = tuple(norm.words(label or ""))
        if not words or words in self.owners:
            return []
        for lab, own in self.owners.items():
            n = len(lab)
            if own - {f["id"]} and any(words[s:s + n] == lab for s in range(len(words) - n + 1)):
                return []
        return [dict(o, owners={f["id"]}) for o in self.find_labels({words: {f["id"]}})]

    # ------------------------------------------------------------------ candidates
    def pieces(self, kind, text):
        key = (kind, text)
        if key not in self._pieces:
            self._pieces[key] = norm.pieces(kind, text)
        return self._pieces[key]

    def span_values(self, kind, words, a, b):
        """The values a run of words holds. Codes and refrigerants are also read with the words run together, since
        the recognizer splits "HPX-36 B2" at random, and numbers never are, since "BKR." and "25" aren't ".25"."""
        texts = [" ".join(w["text"] for w in words[a:b + 1])]
        if all(set(norm.words(w["text"])) <= self.label_words for w in words[a:b + 1]):
            return set()
        if b > a and kind in ONE_OFF_KINDS:
            texts.append("".join(w["text"] for w in words[a:b + 1]))
        return set(v for t in texts for v in self.pieces(kind, t))

    def candidates(self, kind):
        """Every value of this kind in the photo's text: from one word, from two or three words joined on one line
        when no smaller part holds the value, and from the last word of a line joined to the first word under it."""
        if kind in self._cands:
            return self._cands[kind]
        out = []
        for line in self.lines:
            ws = line["words"]
            for a in range(len(ws)):
                for b in range(a, min(a + 3, len(ws))):
                    vals = self.span_values(kind, ws, a, b)
                    if b > a:
                        vals -= set().union(*[self.span_values(kind, ws, x, y) for x in range(a, b + 1)
                                              for y in range(x, b + 1) if (x, y) != (a, b)])
                    for v in sorted(vals):
                        out.append({"v": v, "line": line["i"], "a": a, "b": b, "split": False, "conf": line["conf"],
                                    "text": " ".join(w["text"] for w in ws[a:b + 1]),
                                    "box": union([w["box"] for w in ws[a:b + 1]])})
        for up, down in self.stacked():
            first, last = down["words"][0], up["words"][-1]
            joined = set(self.pieces(kind, last["text"] + " " + first["text"]))
            if kind in ONE_OFF_KINDS:
                joined |= set(self.pieces(kind, last["text"] + first["text"]))
            for v in sorted(joined):
                if v in self.pieces(kind, last["text"]) or v in self.pieces(kind, first["text"]):
                    continue
                out.append({"v": v, "line": up["i"], "a": len(up["words"]) - 1, "b": len(up["words"]) - 1,
                            "split": True, "conf": min(up["conf"], down["conf"]),
                            "text": last["text"] + " / " + first["text"], "box": union([last["box"], first["box"]])})
        self._cands[kind] = out
        return out

    def stacked(self):
        """Pairs of lines where the second sits right under the first and overlaps it across."""
        pairs = []
        for up in self.lines:
            uh = up["box"][3] - up["box"][1]
            for down in self.lines:
                B, U = down["box"], up["box"]
                if down is not up and U[1] + 0.5 * uh <= B[1] <= U[3] + uh and B[0] < U[2] and B[2] > U[0]:
                    pairs.append((up, down))
        return pairs

    # ------------------------------------------------------------------ placing a candidate
    def has_unit(self, f, c):
        """True when the candidate carries one of the field's units right after its number (12A, 120 V, 1PH)."""
        if f["kind"] in ("capacity", "refrigerant"):
            return True
        units = f.get("units") or ()
        if not units:
            return False
        ws = self.lines[c["line"]]["words"]
        tail = c["text"] + (" " + ws[c["b"] + 1]["text"] if c["b"] + 1 < len(ws) and not c["split"] else "")
        text = norm.drop_thousands(norm.clean(tail))
        pat = re.compile("(" + norm.NUM + r") ?(" + "|".join(sorted(units, key=len, reverse=True)) + r")(?![A-Z])")
        values = set(c["v"].split("/"))
        return any(norm.number(m.group(1)) in values for m in pat.finditer(text))

    def placement(self, f, c, ai_label=None):
        """"label" when the candidate sits by this field's label, "unit" when it carries the field's own unit and no
        label on its own line claims it for something else, and "away" otherwise. A label on the candidate's own line
        decides first, then the candidate's own unit, then a label on its row or above it, since the row above a line of
        units is usually somebody else's (changed 11/9 after the first real text recognition)."""
        extra = self.ai_labels(f, ai_label) if ai_label else ()
        own = [lab for lab in list(self.labels) + list(extra) if lab["line"] == c["line"]]
        lab = self.governing(c, extra) if not own else self.governing_from(c, own)
        if lab is not None and self.relation(c, lab)[0] == 0:
            return self.verdict(f, c, lab)
        if f.get("unit_confirms") and self.has_unit(f, c):
            return "unit"
        return self.verdict(f, c, lab) if lab is not None else "away"

    def governing_from(self, c, labels):
        best = None
        for lab in labels:
            r = self.relation(c, lab)
            if r is not None and (best is None or (r, -lab["n"]) < (best[0], -best[1]["n"])):
                best = (r, lab)
        return best[1] if best else self.governing(c)

    def verdict(self, f, c, lab):
        if f["id"] in lab["owners"]:
            return "label"
        same_kind = {o for o in lab["owners"] if o in self.fields and self.fields[o]["kind"] == f["kind"]}
        if same_kind or lab["owners"] & {"other", "serial"}:
            return "away"
        return "unit" if f.get("unit_confirms") and self.has_unit(f, c) else "away"

    def region(self, ai_box):
        """Where a field with no label has to sit: the AI's box grown by half, or the middle half of the photo."""
        if ai_box:
            x0, y0, x1, y1 = to_px(ai_box, self.w, self.h)
            gx, gy = (x1 - x0) * GROW, (y1 - y0) * GROW
            return (x0 - gx, y0 - gy, x1 + gx, y1 + gy)
        return (self.w * 0.25, self.h * 0.25, self.w * 0.75, self.h * 0.75)


def inside(point, box):
    return box[0] <= point[0] <= box[2] and box[1] <= point[1] <= box[3]


def narrow(c, printed):
    """The part of a word's box the value covers, when the value is only part of the word: "208/230" and "1" each get
    their own slice of "208/230-1-60". The slice is proportional to the characters, exact on a plate's monospace
    lettering and close on the rest. A value pieced from several words keeps the whole box."""
    if c["a"] != c["b"] or c["split"] or not printed:
        return c["box"]
    text, want = c["text"].upper(), re.sub(r"\s+", "", str(printed)).upper()
    if not want or len(want) >= len(text):
        return c["box"]
    m = re.search(r"(?<![A-Z0-9])" + re.escape(want) + r"(?![A-Z0-9])", text)
    i = m.start() if m else text.find(want)
    if i < 0:
        return c["box"]
    x0, y0, x1, y1 = c["box"]
    step = (x1 - x0) / len(text)
    return (x0 + step * i, y0, x0 + step * (i + len(want)), y1)


def result(photo, level, why, box=None, approx=False, want=None, seen=None):
    """What the page gets for one read. A box from the recognized words is in pixels and comes out as fractions."""
    if box is not None and not approx:
        box = to_frac(box, photo.w, photo.h)
    return {"level": level, "why": why, "box": list(box) if box else None, "approx": bool(approx and box),
            "canon": want, "seen": seen}


def grade(exact, how, c):
    """(level, why) for one candidate, or None when it doesn't count."""
    if how in ("label", "unit", "box"):
        if not exact:
            return (PARTIAL, "one_off")
        if c["split"]:
            return (PARTIAL, "split")
        if c["conf"] < CONF_MIN:
            return (PARTIAL, "low")
        return (FOUND, how)
    if exact and how in ("away", "ambiguous"):
        return (PARTIAL, how)
    return None


ORDER = {(FOUND, "label"): 0, (FOUND, "unit"): 1, (FOUND, "box"): 1, (PARTIAL, "low"): 2, (PARTIAL, "split"): 3,
         (PARTIAL, "ambiguous"): 4, (PARTIAL, "one_off"): 5, (PARTIAL, "away"): 6}


def confirm(photo, field_id, read):
    """The confirmation of one read: its level, why, its box and the text the photo holds there. None for a field the
    AI said isn't on the plate, since there's nothing to confirm."""
    f = photo.fields[field_id]
    status = (read or {}).get("status")
    ai_box = (read or {}).get("box")
    if status == "absent" or read is None:
        return None
    if status != "read" or not read.get("value"):
        return result(photo, MISSING, "unreadable", ai_box, approx=True)
    want = norm.canon(f["kind"], read["value"])
    if want is None:
        return result(photo, MISSING, "unparsed", ai_box, approx=True)
    if f.get("near_box"):
        return confirm_in_region(photo, f, want, ai_box)
    best = None
    for c in photo.candidates(f["kind"]):
        exact = c["v"] == want
        if not exact and not (f["kind"] in ONE_OFF_KINDS and len(want) >= 4 and norm.distance(c["v"], want) == 1):
            continue
        g = grade(exact, photo.placement(f, c, read.get("label")), c)
        if g is not None:
            rank = (ORDER[g], c["b"] - c["a"], c["line"], c["a"])
            if best is None or rank < best[0]:
                best = (rank, g, c)
    if best is None:
        return result(photo, MISSING, "none", ai_box, approx=True, want=want)
    _, (level, why), c = best
    return result(photo, level, why, narrow(c, read["value"] if level == FOUND or why != "one_off" else c["text"]),
                  want=want, seen=c["text"])


def confirm_in_region(photo, f, want, ai_box):
    """A field with no label (a breaker's rating): exactly one match inside its region is found, more than one is
    partly found, and a match only outside it is away."""
    zone = photo.region(ai_box)
    matches = [c for c in photo.candidates(f["kind"]) if c["v"] == want and not c["split"]]
    within = [c for c in matches if inside(center(c["box"]), zone)]
    mid = center(zone)
    near = lambda c: (center(c["box"])[0] - mid[0]) ** 2 + (center(c["box"])[1] - mid[1]) ** 2  # noqa: E731
    if len(within) == 1:
        c = within[0]
        level, why = grade(True, "box", c)
        return result(photo, level, why, c["box"], want=want, seen=c["text"])
    if within:
        c = min(within, key=near)
        return result(photo, PARTIAL, "ambiguous", c["box"], want=want, seen=c["text"])
    if matches:
        c = min(matches, key=near)
        return result(photo, PARTIAL, "away", c["box"], want=want, seen=c["text"])
    return result(photo, MISSING, "none", ai_box, approx=True, want=want)


def draft(photo):
    """The draft read the verification page starts from: each field's value by its label (or its unit), the nearest
    first, and a breaker's rating when the photo looks like a close-up of breakers. A person confirms every one."""
    out = {}
    for f in photo.fields.values():
        if f.get("near_box"):
            continue
        best = None
        for c in photo.candidates(f["kind"]):
            if c["split"]:
                continue
            how = photo.placement(f, c)
            if how not in ("label", "unit"):
                continue
            lab = photo.governing(c)
            rel = photo.relation(c, lab) if lab is not None and f["id"] in lab["owners"] else (3, 0.0)
            rank = (how != "label", rel, c["b"] - c["a"], c["line"], c["a"])
            if best is None or rank < best[0]:
                best = (rank, c)
        if best:
            c = best[1]
            value = c["text"] if f["kind"] == "code" else c["v"]
            out[f["id"]] = {"value": value, "canon": c["v"], "box": to_frac(narrow(c, value), photo.w, photo.h)}
    labelled = [lab for lab in photo.labels if lab["owners"] & set(photo.fields)]
    sizes = [c for c in photo.candidates("amps") if c["v"] in BREAKER_SIZES and c["a"] == c["b"] and not c["split"]]
    if not labelled and len(sizes) >= 2:
        mid = (photo.w / 2, photo.h / 2)
        c = min(sizes, key=lambda x: (center(x["box"])[0] - mid[0]) ** 2 + (center(x["box"])[1] - mid[1]) ** 2)
        out["breaker"] = {"value": c["v"], "canon": c["v"], "box": to_frac(c["box"], photo.w, photo.h)}
    return out
