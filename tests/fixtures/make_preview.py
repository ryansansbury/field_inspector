"""Write the preview job in tests/fixtures/preview/: drawn plates and everything the build needs to run on them.

    python3 tests/fixtures/make_preview.py

The preview lets the page be built and tested before the real photos are read. Each plate is an SVG drawing in a
monospace face, so the text-recognition fixture can give every word its exact box. It has flat patches where a maker's
name and a serial would be masked, and a glare blob over one model, which its recognized text misreads. The plates
carry no maker and their model numbers are made up. The preview's key, designs and job plant the same outcomes as the
real job: a breaker over the plate's maximum (across two photos), a capacity that differs, a model under glare, and a
model one character off. Every screen the preview reaches says it's a preview, and the real build refuses it.
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.joinpath("preview")
W, H = 1568, 1176
FONT = "Menlo, Consolas, monospace"
ADVANCE = 0.6           # a monospace character's width, in font sizes

# (photo, kind, shot, [(x, y, size, text, recognized-as)], masks, glare). y is the text's baseline. recognized-as is
# what the text recognition reads there, when it differs from the drawing (None reads nothing).
PLATES = [
    ("p01", "heat pump", "straight", [
        (140, 300, 44, "MODEL NO.", ""), (700, 300, 48, "HPX-36B2", ""),
        (140, 380, 44, "SERIAL NO.", ""),
        (140, 460, 44, "VOLTS/PH/HZ", ""), (700, 460, 48, "208/230-1-60", ""),
        (140, 540, 44, "MIN. CIRCUIT AMPACITY", ""), (1040, 540, 48, "18.6", ""),
        (140, 620, 44, "MAX. FUSE OR CKT. BKR.", ""), (1040, 620, 48, "25", ""),
        (140, 700, 44, "REFRIGERANT", ""), (700, 700, 48, "R-454B", ""), (980, 700, 40, "7 LB 4 OZ", ""),
        (140, 780, 44, "COMPRESSOR RLA/LRA", ""), (1040, 780, 48, "14.1/82", ""),
        (140, 860, 44, "MFG DATE", ""), (700, 860, 48, "06/2026", "")],
     [(140, 130, 720, 110), (700, 340, 420, 56)], None),
    ("p02", "breaker", "straight", [], [], None),
    ("p03", "air handler", "angled", [
        (160, 330, 46, "MODEL", ""), (560, 330, 50, "AHX-24A1", ""),
        (160, 430, 46, "VOLTS", ""), (560, 430, 50, "208/230", ""), (900, 430, 46, "PH", ""), (1000, 430, 50, "1", ""),
        (160, 530, 46, "MCA", ""), (560, 530, 50, "9.1", ""),
        (160, 630, 46, "MAX FUSE", ""), (560, 630, 50, "15", "")],
     [(160, 150, 640, 110)], None),
    ("p04", "water heater", "straight", [
        (150, 320, 46, "MODEL", ""), (600, 320, 50, "EWH-50T2", ""),
        (150, 420, 46, "VOLTS", ""), (600, 420, 50, "240", ""),
        (150, 520, 46, "CAPACITY", ""), (600, 520, 50, "50 GAL", ""),
        (150, 620, 46, "TOTAL WATTS", ""), (600, 620, 50, "4500", "")],
     [(150, 150, 700, 110)], None),
    ("p05", "dryer", "glare", [
        (180, 360, 48, "MODEL", ""), (620, 360, 52, "DRY-27E", "DRY-Z7E"),
        (180, 470, 48, "VOLTS", ""), (620, 470, 52, "120/240", ""),
        (180, 580, 48, "AMPS", ""), (620, 580, 52, "24", "")],
     [(180, 170, 640, 110)], (760, 330, 240, 110)),
    ("p06", "dishwasher", "straight", [
        (200, 420, 52, "MOD. DW-24P7", ""),
        (200, 520, 52, "120V~ 60Hz 12.0A", "")],
     [(200, 220, 600, 100), (200, 600, 760, 90)], None),
    ("p07", "range", "angled", [
        (170, 360, 48, "MODEL", ""), (620, 360, 52, "RNG-30E", ""),
        (170, 470, 48, "VOLTS", ""), (620, 470, 52, "120/240", ""),
        (170, 580, 48, "RATED POWER", ""), (620, 580, 52, "12.2 KW", "")],
     [(170, 170, 620, 110)], None),
    ("p08", "panel", "straight", [
        (170, 380, 48, "CAT. NO.", ""), (620, 380, 52, "PNL-200", ""),
        (170, 490, 48, "VOLTS", ""), (620, 490, 52, "120/240", ""), (1000, 490, 48, "1PH", ""),
        (170, 600, 48, "MAX AMPS", ""), (620, 600, 52, "200", "")],
     [(170, 180, 700, 110)], None),
]
BREAKERS = [(330, "20"), (784, "30"), (1238, "20")]
KEY = {
    "p01": {"model": "HPX-36B2", "volts": "208/230", "phase": "1", "mca": "18.6", "max_breaker": "25",
            "refrigerant": "R-454B"},
    "p02": {"breaker": "30"},
    "p03": {"model": "AHX-24A1", "volts": "208/230", "phase": "1", "mca": "9.1", "max_breaker": "15"},
    "p04": {"model": "EWH-50T2", "volts": "240", "capacity": "50 GAL"},
    "p05": {"model": "DRY-27E", "volts": "120/240", "amps": "24"},
    "p06": {"model": "DW-24P7", "volts": "120V", "amps": "12.0A"},
    "p07": {"model": "RNG-30E", "volts": "120/240", "capacity": "12.2 KW"},
    "p08": {"model": "PNL-200", "volts": "120/240", "phase": "1PH", "amps": "200"},
}
DESIGNS = {
    "heat-pump": {"model": "HPX-36B2", "refrigerant": "R-454B", "volts": "240", "phase": "1", "breaker": "30",
                  "checks": ["model", "refrigerant", "volts", "breaker_max", "breaker_min", "panel"]},
    "breaker": {"checks": []},
    "air-handler": {"model": "AHX-24A1", "volts": "240", "phase": "1", "breaker": "15",
                    "checks": ["model", "volts", "breaker_max", "breaker_min"]},
    "water-heater": {"model": "EWH-50T2", "volts": "240", "capacity": "40 GAL", "checks": ["model", "volts", "capacity"]},
    "dryer": {"model": "DRY-27E", "volts": "120/240", "checks": ["model", "volts"]},
    "dishwasher": {"model": "DW-24P1", "volts": "120", "checks": ["model", "volts"]},
    "range": {"model": "RNG-30E", "volts": "120/240", "capacity": "12.2 KW", "checks": ["model", "volts", "capacity"]},
    "panel": {"model": "PNL-200", "volts": "120/240", "checks": ["model", "volts"]},
}
PLACES = {"heat-pump": "side_yard", "air-handler": "attic", "water-heater": "garage", "dryer": "laundry",
          "dishwasher": "kitchen", "range": "kitchen", "panel": "garage"}


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def words_of(x, y, size, text):
    """Each word's box as fractions, from the monospace advance: the cap height above the baseline, a little below."""
    out, cx = [], x
    for part in text.split(" "):
        w = ADVANCE * size * len(part)
        out.append({"text": part, "box": [round(cx / W, 4), round((y - 0.78 * size) / H, 4), round((cx + w) / W, 4),
                                          round((y + 0.18 * size) / H, 4)]})
        cx += ADVANCE * size * (len(part) + 1)
    return out


def plate_svg(lines, masks, glare):
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
             "<defs><linearGradient id='m' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#e4e7ea'/>"
             "<stop offset='1' stop-color='#c9ced3'/></linearGradient><radialGradient id='g'><stop offset='0' "
             "stop-color='#fff' stop-opacity='.97'/><stop offset='.7' stop-color='#fff' stop-opacity='.75'/>"
             "<stop offset='1' stop-color='#fff' stop-opacity='0'/></radialGradient></defs>",
             f"<rect width='{W}' height='{H}' fill='#59616b'/>",
             "<rect x='90' y='70' width='1388' height='1036' rx='20' fill='url(#m)' stroke='#8e979f' stroke-width='5'/>"]
    parts += [f"<circle cx='{cx}' cy='{cy}' r='14' fill='#a7aeb5' stroke='#7c858d' stroke-width='3'/>"
              for cx, cy in ((140, 120), (1428, 120), (140, 1056), (1428, 1056))]
    for x, y, size, text, _ in lines:
        parts.append(f"<text x='{x}' y='{y}' font-family='{FONT}' font-size='{size}' fill='#1b2129'>{esc(text)}</text>")
    for x, y, w, h in masks:
        parts.append(f"<rect x='{x}' y='{y}' width='{w}' height='{h}' rx='6' fill='#cfd3d8'/>")
    if glare:
        x, y, w, h = glare
        parts.append(f"<ellipse cx='{x + w / 2}' cy='{y + h / 2}' rx='{w}' ry='{h}' fill='url(#g)'/>")
    return "".join(parts) + "</svg>\n"


def breaker_svg():
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{W}' height='{H}' viewBox='0 0 {W} {H}'>",
             f"<rect width='{W}' height='{H}' fill='#3b4148'/>",
             "<rect x='160' y='120' width='1248' height='936' rx='12' fill='#d8dbdf'/>"]
    for x, rating in BREAKERS:
        parts.append(f"<rect x='{x - 150}' y='260' width='300' height='640' rx='16' fill='#1f2328'/>")
        parts.append(f"<rect x='{x - 70}' y='430' width='140' height='300' rx='10' fill='#2c3238'/>")
        parts.append(f"<text x='{x - 1.2 * 30 * ADVANCE * len(rating) / 1.2}' y='610' font-family='{FONT}' "
                     f"font-size='60' fill='#f2f3f4'>{rating}</text>")
    return "".join(parts) + "</svg>\n"


def breaker_ocr():
    lines = []
    for x, rating in BREAKERS:
        size = 60
        left = x - 30 * ADVANCE * len(rating)
        words = words_of(left, 610, size, rating)
        lines.append({"text": rating, "conf": 1.0, "box": words[0]["box"], "words": words})
    return lines


def main():
    for folder in ("photos", "ocr", "key"):
        OUT.joinpath(folder).mkdir(parents=True, exist_ok=True)
    photos, plates = {}, {}
    for pid, kind, shot, lines, masks, glare in PLATES:
        svg = breaker_svg() if kind == "breaker" else plate_svg(lines, masks, glare)
        OUT.joinpath("photos", f"{pid}.svg").write_text(svg, encoding="utf-8")
        if kind == "breaker":
            ocr_lines = breaker_ocr()
        else:
            ocr_lines = []
            for x, y, size, text, seen in lines:
                shown = text if seen == "" else seen
                if shown is None:
                    continue
                words = words_of(x, y, size, shown)
                ocr_lines.append({"text": shown, "conf": 1.0, "box": [words[0]["box"][0], words[0]["box"][1],
                                                                     words[-1]["box"][2], words[-1]["box"][3]],
                                  "words": words})
        OUT.joinpath("ocr", f"{pid}.json").write_text(json.dumps(
            {"photo": pid, "w": W, "h": H, "engine": "preview fixture", "lines": ocr_lines}, indent=1),
            encoding="utf-8")
        slug = kind.replace(" ", "-")
        values = {f: None for f in ("model", "volts", "phase", "amps", "mca", "max_breaker", "capacity",
                                    "refrigerant", "breaker")}
        from engine import normalize as norm  # noqa: E402 - the generator runs from the build folder
        kinds = {"model": "code", "volts": "volts", "phase": "phase", "amps": "amps", "mca": "amps",
                 "max_breaker": "amps", "capacity": "capacity", "refrigerant": "refrigerant", "breaker": "amps"}
        for f, v in KEY[pid].items():
            values[f] = {"value": v, "canon": norm.canon(kinds[f], v)}
        photos[pid] = {"plate": slug, "kind": kind, "shot": shot, "split": "test", "fields": values}
        plates[slug] = {"name": kind.capitalize(), "kind": kind, "photos": [pid], "split": "test"}
    OUT.joinpath("key", "key.json").write_text(json.dumps(
        {"made_from": "tests/fixtures/make_preview.py", "confirmed_by": "the preview fixture", "seed": 11,
         "photos": photos, "plates": plates, "dropped": {}}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    OUT.joinpath("designs.json").write_text(json.dumps({"plates": DESIGNS}, indent=1) + "\n", encoding="utf-8")
    assets = []
    for pid, kind, _, _, _, _ in PLATES:
        slug = kind.replace(" ", "-")
        if kind == "breaker":
            continue
        a = {"id": slug, "photo": pid, "kind": kind, "place": PLACES[slug]}
        if slug == "heat-pump":
            a["breaker_photo"] = "p02"
        assets.append(a)
    job = {"number": "2318", "day": "2026-11-12", "assets": assets,
           "designs": {a["id"]: DESIGNS[a["id"]] for a in assets}}
    OUT.joinpath("job.json").write_text(json.dumps(job, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {len(PLATES)} drawn plates, their recognized text, the key, the designs and the job into "
          f"{OUT.relative_to(OUT.parents[2])}/")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()
