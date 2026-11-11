"""The owner's machine only. Text recognition with the Mac's own Vision framework, so nothing leaves the machine.

    .venv/bin/python3 owner/ocr.py --draft      the unmasked copies (data/unmasked/) into data/ocr_draft/, with each
                                                field's draft value, the proposed masks, and the face and person check
    .venv/bin/python3 owner/ocr.py              the masked photos (data/photos/) into data/ocr/, the text the page and
                                                the confirmation step use
    .venv/bin/python3 owner/ocr.py --self-test  a plate it draws itself, before any real photo

Vision runs at its accurate level with language correction off, so a model number is never "corrected" into a word.
Each recognized line keeps its confidence and each word its own box, taken from the line's character ranges. Every
box is stored as fractions of the photo with the origin at the top left. The draft read and the mask proposals use the
same matching as engine/confirm.py, and a person confirms all of it on the verification page. owner/bootstrap.sh runs the
self-test, which names the failing call if Vision's bindings differ on this macOS.
"""
import argparse
import hashlib
import json
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import confirm, normalize as norm  # noqa: E402

UNMASKED, DRAFT = HERE.joinpath("data", "unmasked"), HERE.joinpath("data", "ocr_draft")
PHOTOS, OCR = HERE.joinpath("data", "photos"), HERE.joinpath("data", "ocr")
ENGINE = "Apple Vision text recognition, accurate, language correction off"
SEEN = 0.6          # a face or a person Vision is at least this sure of stops the photo until a person looks
WEB = re.compile(r"WWW|HTTP|\.COM|\.NET|\.ORG|@")
PHONE = re.compile(r"\(?[0-9]{3}\)?[-. ][0-9]{3}[-. ][0-9]{4}|1-8[0-9]{2}-")
ADDRESS = re.compile(r"(?:^|[^A-Z])[A-Z]{2},? [0-9]{5}(?:-[0-9]{4})?(?![0-9])")


def flip(rect):
    """Vision's normalized rectangle (origin at the bottom left) as [x0, y0, x1, y1] from the top left."""
    try:
        x, y, w, h = rect.origin.x, rect.origin.y, rect.size.width, rect.size.height
    except AttributeError:
        (x, y), (w, h) = rect
    box = [x, 1.0 - (y + h), x + w, 1.0 - y]
    return [round(min(1.0, max(0.0, v)), 4) for v in box]


def where(e):
    """The file and line an exception came from, so a failure on the owner's machine names its call."""
    tb = traceback.extract_tb(e.__traceback__)
    last = tb[-1] if tb else None
    return f"{type(e).__name__}: {e}" + (f" (ocr.py line {last.lineno}: {last.line})" if last else "")


def split_box(line_box, text):
    """Each word's box as its share of the line's box, by characters, for when Vision won't give word boxes."""
    x0, y0, x1, y1 = line_box
    step, out = (x1 - x0) / max(1, len(text)), []
    for m in re.finditer(r"\S+", text):
        out.append({"text": m.group(0), "box": [round(x0 + step * m.start(), 4), y0,
                                                round(x0 + step * m.end(), 4), y1]})
    return out


def vision(path):
    """(lines, barcodes, faces, people, notes) for one photo from Apple's Vision framework. Each request runs on its
    own, so a request this macOS refuses costs only its own result and notes says which and why. Text recognition is
    the one that has to work."""
    import Vision  # pyobjc-framework-Vision, installed by owner/bootstrap.sh
    from Foundation import NSURL, NSArray, NSDictionary

    # Real Foundation collections, never Python ones: Vision on newer macOS asks its options for keys they don't hold,
    # and the bridge's proxy for a Python dict raises "key does not exist" where an NSDictionary answers nil (11/9).
    url, notes, options = NSURL.fileURLWithPath_(str(path)), [], NSDictionary.dictionary()

    def perform(request, what):
        try:
            handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(url, options)
            ok, err = handler.performRequests_error_(NSArray.arrayWithObject_(request), None)
        except Exception as e:  # noqa: BLE001 - a refused request is reported, not fatal
            notes.append(f"{what}: {where(e)}")
            return None
        if not ok:
            notes.append(f"{what}: {err}")
            return None
        return list(request.results() or [])

    text = Vision.VNRecognizeTextRequest.alloc().init()
    for setting, call in (("accurate level", lambda: text.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)),
                          ("language correction off", lambda: text.setUsesLanguageCorrection_(False)),
                          ("English", lambda: text.setRecognitionLanguages_(NSArray.arrayWithObject_("en-US")))):
        try:
            call()
        except Exception as e:  # noqa: BLE001
            notes.append(f"text recognition setting ({setting}): {where(e)}")
    results = perform(text, "text recognition")
    if results is None:
        raise RuntimeError("text recognition failed: " + "; ".join(notes))
    lines, split = [], False
    for obs in results:
        top = obs.topCandidates_(1)
        if not top:
            continue
        cand, line_box = top[0], flip(obs.boundingBox())
        s = str(cand.string())
        words = []
        try:
            for m in re.finditer(r"\S+", s):
                box, _ = cand.boundingBoxForRange_error_((m.start(), m.end() - m.start()), None)
                if box is not None:
                    words.append({"text": m.group(0), "box": flip(box.boundingBox())})
        except Exception as e:  # noqa: BLE001 - the line's box still places its words
            if not split:
                notes.append(f"word boxes: {where(e)}, so each line's box is split by characters")
            split, words = True, split_box(line_box, s)
        if words:
            lines.append({"text": s, "conf": round(float(cand.confidence()), 3), "box": line_box, "words": words})
    codes = perform(Vision.VNDetectBarcodesRequest.alloc().init(), "barcodes") or []
    faces = perform(Vision.VNDetectFaceRectanglesRequest.alloc().init(), "faces")
    people = perform(Vision.VNDetectHumanRectanglesRequest.alloc().init(), "people")
    barcodes = [{"box": flip(o.boundingBox()), "payload": str(o.payloadStringValue() or "")} for o in codes]
    seen_faces = None if faces is None else [round(float(o.confidence()), 2) for o in faces]
    seen_people = None if people is None else [round(float(o.confidence()), 2) for o in people]
    return lines, barcodes, seen_faces, seen_people, notes


def size_of(path):
    from PIL import Image
    with Image.open(path) as im:
        return im.size


def propose(photo, fields, barcodes=()):
    """The masks the verification page starts with: the value after a serial label, every barcode and QR code, and
    every line with a web or email address, a phone number, a state and ZIP, a listing or patent word, or lettering
    much taller than the rest (a maker's name). Logos have no text, so a person draws those."""
    out = []
    listing, plain = set(fields.get("listing_words", ())), set(fields.get("plain_words", ())) | photo.label_words

    def add(box_px, why):
        out.append({"box": confirm.to_frac(box_px, photo.w, photo.h), "why": why})

    for lab in photo.labels:
        if "serial" not in lab["owners"]:
            continue
        after = photo.lines[lab["line"]]["words"][lab["b"] + 1:]
        if after:
            add(confirm.union([w["box"] for w in after[:3]]), "serial")
            continue
        below = [(photo.relation(c, lab), c) for c in photo.candidates("code") if c["a"] == c["b"] and len(c["v"]) >= 4]
        below = [(r, c) for r, c in below if r is not None and r[0] == 2]
        if below:
            add(min(below, key=lambda rc: rc[0])[1]["box"], "serial")
    for b in barcodes:
        out.append({"box": b["box"], "why": "barcode"})
    heights = sorted(line["box"][3] - line["box"][1] for line in photo.lines)
    median = heights[len(heights) // 2] if heights else 0
    label_lines = {lab["line"] for lab in photo.labels}
    for line in photo.lines:
        text, words = norm.clean(line["text"]), set(norm.words(line["text"]))
        tall = line["box"][3] - line["box"][1] >= 1.8 * median > 0
        if WEB.search(text):
            why = "web"
        elif PHONE.search(text):
            why = "phone"
        elif ADDRESS.search(text):
            why = "address"
        elif words & listing:
            why = "listing"
        elif tall and sum(ch.isalpha() for ch in text) >= 3 and line["i"] not in label_lines and not words <= plain:
            why = "lettering"
        else:
            continue
        add(line["box"], why)
    return out


def read_one(path, fields, draft):
    lines, barcodes, faces, people, notes = vision(path)
    w, h = size_of(path)
    out = {"photo": path.stem, "w": w, "h": h, "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
           "engine": ENGINE, "lines": lines}
    if draft:
        photo = confirm.Photo(out, fields)
        out.update(draft=confirm.draft(photo), masks=propose(photo, fields, barcodes), barcodes=barcodes,
                   faces=[c for c in faces or [] if c >= SEEN], people=[c for c in people or [] if c >= SEEN],
                   people_check=faces is not None and people is not None)
    out["notes"] = notes
    return out


def run(draft):
    src, dst = (UNMASKED, DRAFT) if draft else (PHOTOS, OCR)
    paths = sorted(p for p in src.glob("p*.jpg"))
    if not paths:
        raise SystemExit(f"No photos in {src.relative_to(HERE)}. Run bash owner/prepare.sh first.")
    dst.mkdir(parents=True, exist_ok=True)
    fields = confirm.load_fields()
    flagged, notes = [], {}
    for p in paths:
        out = read_one(p, fields, draft)
        for note in out.pop("notes"):
            notes.setdefault(note.split(":")[0], note)
        dst.joinpath(f"{p.stem}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        extra = ""
        if draft:
            extra = f", {len(out['draft'])} fields drafted, {len(out['masks'])} masks proposed"
            if out["faces"] or out["people"]:
                flagged.append(p.stem)
                extra += ", a face or a person to check"
        print(f"  {p.stem}: {len(out['lines'])} lines{extra}")
    print(f"Read {len(paths)} photos into {dst.relative_to(HERE)}/.")
    for note in notes.values():
        print(f"  Vision on this Mac: {note}")
    if draft and any(n.startswith(("faces", "people")) for n in notes):
        print("The face and person check couldn't run, so look at every photo for a person on the verification page.")
    if flagged:
        print(f"Vision saw a face or a person in {', '.join(flagged)}. The verification page holds those until you "
              f"look, and you can drop any that shows one.")


def self_test():
    """Draw a plate, read it back, and check the draft finds its values. Names the failing step if anything breaks."""
    from PIL import Image, ImageDraw, ImageFont
    folder = HERE.joinpath(".cache", "selftest")
    folder.mkdir(parents=True, exist_ok=True)
    font = None
    for name in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf"):
        try:
            font = ImageFont.truetype(name, 44)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default(size=44)
    img = Image.new("RGB", (1400, 700), "white")
    draw = ImageDraw.Draw(img)
    for y, text in ((80, "MODEL NO.   HPX-36B2"), (200, "VOLTS/PH/HZ   208/230-1-60"),
                    (320, "MIN. CIRCUIT AMPACITY   18.6"), (440, "MAX. FUSE OR CKT. BKR.   25")):
        draw.text((80, y), text, fill="black", font=font)
    path = folder.joinpath("p00.jpg")
    img.save(path, "JPEG", quality=92)
    try:
        out = read_one(path, confirm.load_fields(), draft=True)
    except Exception as e:  # noqa: BLE001 - the point is to name what broke
        raise SystemExit("Self-test failed in Vision: " + where(e) + "\n" + traceback.format_exc(limit=-4))
    for note in out["notes"]:
        print(f"  Vision on this Mac: {note}")
    got = {k: v["canon"] for k, v in out["draft"].items()}
    want = {"model": "HPX36B2", "volts": "208/230", "phase": "1", "mca": "18.6", "max_breaker": "25"}
    missed = {k: (v, got.get(k)) for k, v in want.items() if got.get(k) != v}
    if missed:
        lines = " | ".join(line["text"] for line in out["lines"])
        raise SystemExit(f"Self-test failed: the draft read {missed} (wanted, got). Vision saw: {lines}")
    checks = "with the face and person check" if out.get("people_check") else "without the face and person check"
    print(f"Self-test passed: Vision read the drawn plate and the draft found all {len(want)} values, {checks}.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--draft", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        self_test()
    else:
        run(a.draft)


if __name__ == "__main__":
    main()
