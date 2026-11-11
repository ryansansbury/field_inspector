"""Render the synthetic photos from generate/plates.json, and write the answer key, the designs and the job from the same
file, so every value the key holds is exactly what its photo shows.

    .venv/bin/python3 generate/render.py            every photo into data/photos/, with the key, the designs and the job
    .venv/bin/python3 generate/render.py --sheet    the same, plus contact sheets in owner/out/sheets/ to look at

Each plate is drawn flat in the site's own fonts (Inter and JetBrains Mono at the weight and width its spec gives, or
Pillow's built-in sans), then photographed. It's set on an equipment surface, turned and tilted in perspective, lit
unevenly, and given a camera's softness, grain and JPEG compression. An angled shot tilts it further, a glare shot
washes out a bright patch over a chosen value (a hard one whites out the middle of it, so no reader can make it out),
and a low light shot darkens it with more grain and blur. Flat patches stand where a maker's name, a serial and a
barcode would be masked on a real photo, and they go in the masking log the privacy scan checks. Every value's box goes through the same perspective into the key. Seeded, so the same file always
renders the same photos. Needs Pillow, which owner/bootstrap.sh puts in .venv/.
"""
import argparse
import hashlib
import json
import math
import random
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import normalize as norm  # noqa: E402

SPECS = HERE.joinpath("generate", "plates.json")
DATA = HERE.joinpath("data")
FONTS = {"inter": HERE.joinpath("site", "fonts", "inter-latin.woff2"),
         "mono": HERE.joinpath("site", "fonts", "jetbrains-mono-latin.woff2")}
OUT = (1568, 1176)
SCENE = (2352, 1764)
FLAT_W = 1800
STYLES = {
    "metal": {"top": (218, 221, 224), "bottom": (184, 189, 195), "ink": (34, 38, 43), "edge": (140, 147, 154)},
    "label": {"top": (246, 246, 241), "bottom": (234, 234, 228), "ink": (22, 22, 24), "edge": (30, 30, 30)},
    "paper": {"top": (240, 237, 228), "bottom": (226, 222, 210), "ink": (30, 30, 34), "edge": (120, 116, 106)},
}
SURFACES = ((205, 200, 188), (92, 98, 104), (232, 232, 228), (58, 62, 66), (176, 180, 170))
FIELDS = ("model", "volts", "phase", "amps", "mca", "max_breaker", "capacity", "refrigerant", "breaker")
KINDS = {"model": "code", "volts": "volts", "phase": "phase", "amps": "amps", "mca": "amps", "max_breaker": "amps",
         "capacity": "capacity", "refrigerant": "refrigerant", "breaker": "amps"}


# ------------------------------------------------------------------ geometry (plain Python, unit-tested)
def solve(a, b):
    """x with a x = b, by Gaussian elimination with partial pivoting."""
    n = len(b)
    m = [list(row) + [v] for row, v in zip(a, b)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[pivot] = m[pivot], m[col]
        for r in range(n):
            if r != col and m[r][col]:
                f = m[r][col] / m[col][col]
                m[r] = [x - f * y for x, y in zip(m[r], m[col])]
    return [m[i][n] / m[i][i] for i in range(n)]


def homography(src, dst):
    """The eight numbers of the perspective map taking each src point to its dst point."""
    a, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        a.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        b.append(u)
        a.append([0, 0, 0, x, y, 1, -v * x, -v * y])
        b.append(v)
    return solve(a, b)


def apply(h, x, y):
    w = h[6] * x + h[7] * y + 1
    return (h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w


def carry(h, box, size):
    """A box on the flat plate, taken through the perspective map, as fractions of the photo."""
    pts = [apply(h, x, y) for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [round(min(1, max(0, v)), 4) for v in (min(xs) / size[0], min(ys) / size[1], max(xs) / size[0],
                                                  max(ys) / size[1])]


def carry_quad(h, box, size):
    """A box on the flat plate as its four corners in the photo, in fractions, for a patch on a tilted plate."""
    pts = [apply(h, x, y) for x, y in ((box[0], box[1]), (box[2], box[1]), (box[2], box[3]), (box[0], box[3]))]
    return {"quad": [[round(x / size[0], 4), round(y / size[1], 4)] for x, y in pts]}


def quad(fw, fh, shot, rng, fill):
    """Where the plate's four corners land in the scene for a shot: centered with a little drift, turned, and pulled
    into perspective (gently when straight, hard when angled)."""
    W, H = SCENE
    s = min(W * fill / fw, H * fill / fh) * rng.uniform(0.94, 1.0)
    cx, cy = W / 2 + rng.uniform(-0.03, 0.03) * W, H / 2 + rng.uniform(-0.03, 0.03) * H
    turn = math.radians(rng.uniform(-6, 6) if shot == "angled" else rng.uniform(-2.2, 2.2))
    pull = rng.uniform(0.16, 0.24) if shot == "angled" else rng.uniform(0.0, 0.035)
    side = rng.choice((-1, 1))
    pts = []
    for x, y in ((-fw / 2, -fh / 2), (fw / 2, -fh / 2), (fw / 2, fh / 2), (-fw / 2, fh / 2)):
        far = (x * side) > 0
        y2 = y * (1 - pull if far else 1)
        x2 = x * (1 - pull * 0.35 if far else 1)
        rx, ry = x2 * math.cos(turn) - y2 * math.sin(turn), x2 * math.sin(turn) + y2 * math.cos(turn)
        pts.append((cx + rx * s, cy + ry * s))
    return pts


# ------------------------------------------------------------------ drawing the flat plate
def font(name, weight, size):
    from PIL import ImageFont
    if name == "sans":
        return ImageFont.load_default(size=size)
    f = ImageFont.truetype(str(FONTS[name]), size)
    f.set_variation_by_axes([weight])
    return f


def text(canvas, xy, s, f, fill, squeeze=1.0, emboss=None):
    """Draws s with its left edge at xy and returns its box. A squeeze under 1 narrows it like a condensed face."""
    from PIL import Image, ImageDraw
    l, t, r, b = f.getbbox(s)
    layer = Image.new("L", (max(1, r), max(1, b)), 0)
    ImageDraw.Draw(layer).text((0, 0), s, font=f, fill=255)
    if squeeze != 1.0:
        layer = layer.resize((max(1, round(r * squeeze)), b), Image.LANCZOS)
    x, y = round(xy[0]), round(xy[1])
    if emboss:
        canvas.paste(Image.new("RGBA", layer.size, emboss + (255,)), (x + 2, y + 2), layer)
    canvas.paste(Image.new("RGBA", layer.size, fill + (255,)), (x, y), layer)
    return (x + l * squeeze, y + t, x + r * squeeze, y + b)


def span(f, s, part, squeeze):
    """Where part sits inside s, as offsets from s's left edge."""
    i = s.find(part)
    if i < 0:
        return None
    return f.getlength(s[:i]) * squeeze, f.getlength(s[:i + len(part)]) * squeeze


def surface_noise(img, rng, amount):
    from PIL import Image, ImageChops
    noise = Image.effect_noise(img.size, amount).convert("RGB")
    return ImageChops.add(img, noise, 1.0, -128)


def plate(spec, rng):
    """The plate drawn flat: (RGBA image, {field: box}, [mask boxes])."""
    from PIL import Image, ImageDraw, ImageFilter
    st = STYLES[spec["style"]]
    name, weight, squeeze = spec["font"]
    size = 54 if len(spec["rows"]) <= 5 else 46
    f, small, head = font(name, weight, size), font(name, weight, int(size * 0.62)), font(name, weight + 120 if weight else 0,
                                                                                          int(size * 0.92))
    row_h = int(size * 1.62)
    top = 70 + (110 if spec.get("maker") else 0) + (100 if spec.get("title") else 0)
    height = top + row_h * len(spec["rows"]) + int(size * 0.95) * len(spec.get("notes", [])) + 120
    img = Image.new("RGBA", (FLAT_W, height), st["top"] + (255,))
    grad = Image.linear_gradient("L").resize((FLAT_W, height))
    img = Image.composite(Image.new("RGBA", img.size, st["bottom"] + (255,)), img, grad)
    img = Image.alpha_composite(img, surface_noise(img.convert("RGB"), rng, 10).convert("RGBA"))
    d = ImageDraw.Draw(img)
    if spec["style"] == "metal":
        streaks = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(streaks)
        for _ in range(140):
            y = rng.randrange(height)
            sd.line((0, y, FLAT_W, y), fill=(255, 255, 255, rng.randrange(4, 11)), width=rng.choice((1, 1, 2)))
        img = Image.alpha_composite(img, streaks.filter(ImageFilter.GaussianBlur(0.8)))
        d = ImageDraw.Draw(img)
        for cx, cy in ((44, 44), (FLAT_W - 44, 44), (44, height - 44), (FLAT_W - 44, height - 44)):
            d.ellipse((cx - 16, cy - 16, cx + 16, cy + 16), fill=(160, 166, 172, 255), outline=(110, 116, 122, 255), width=3)
    d.rounded_rectangle((8, 8, FLAT_W - 9, height - 9), radius=18, outline=st["edge"] + (255,), width=4)
    emboss = (248, 249, 250) if spec["style"] == "metal" else None
    masks, boxes = [], {}
    y = 70
    if spec.get("maker"):
        masks.append((90, y, 90 + rng.randrange(520, 760), y + 80))
        y += 110
    if spec.get("title"):
        if spec["style"] == "label":
            d.rectangle((24, y - 8, FLAT_W - 24, y + 78), fill=(28, 28, 30, 255))
            text(img, (90, y + 6), spec["title"], head, (246, 246, 241), squeeze)
        else:
            text(img, (90, y), spec["title"], head, st["ink"], squeeze, emboss)
        y += 100
    labels = [r["label"] for r in spec["rows"] if r.get("label")]
    col = 90 + max((f.getlength(s) * squeeze for s in labels), default=0) + 70
    for r in spec["rows"]:
        x = 90
        if r.get("label"):
            text(img, (x, y), r["label"], f, st["ink"], squeeze, emboss)
            x = col
        if r.get("patch"):
            masks.append((x, y - 4, x + rng.randrange(380, 520), y + size + 6))
        elif r.get("value"):
            box = text(img, (x, y), r["value"], f, st["ink"], squeeze, emboss)
            for field, printed in (r.get("fields") or {}).items():
                where = span(f, r["value"], printed, squeeze)
                if where:
                    boxes[field] = (x + where[0], box[1], x + where[1], box[3])
        y += row_h
    y += 20
    for note in spec.get("notes", []):
        text(img, (90, y), note, small, st["ink"], squeeze)
        y += int(size * 0.95)
    if spec["style"] == "label" and spec.get("maker"):
        masks.append((FLAT_W - 520, height - 150, FLAT_W - 90, height - 50))
    for m in masks:
        d.rectangle(m, fill=tuple(max(0, c - 14) for c in st["top"]) + (255,))
    return img, boxes, masks


def breakers(spec, rng):
    """A close look at three breakers stacked in a panel, the subject in the middle with its rating on the handle."""
    from PIL import Image, ImageDraw
    b = spec["breaker"]
    w, h = 1800, 1350
    img = Image.new("RGBA", (w, h), (43, 47, 51, 255))
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, w, 150), fill=(205, 209, 212, 255))
    d.rectangle((0, h - 150, w, h), fill=(205, 209, 212, 255))
    f, slot = font("inter", 760, 104), font("inter", 600, 44)
    ratings = [b["neighbors"][0], b["rating"], b["neighbors"][1]]
    heights = [260, 480 if b.get("poles") == 2 else 260, 260]
    y, boxes = 150 + (h - 300 - sum(heights) - 60) // 2, {}
    for i, (rating, bh) in enumerate(zip(ratings, heights)):
        d.rounded_rectangle((260, y, 1540, y + bh), radius=18, fill=(26, 28, 31, 255))
        d.line((280, y + 4, 1520, y + 4), fill=(58, 62, 67, 255), width=3)
        d.line((280, y + bh - 4, 1520, y + bh - 4), fill=(12, 13, 15, 255), width=4)
        for sx in (330, 1470):
            d.ellipse((sx - 14, y + bh / 2 - 14, sx + 14, y + bh / 2 + 14), fill=(88, 92, 97, 255))
            d.line((sx - 9, y + bh / 2, sx + 9, y + bh / 2), fill=(40, 42, 46, 255), width=3)
        handles = 2 if bh > 300 else 1
        for k in range(handles):
            hy = y + 40 + k * (bh - 80) // handles
            hh = (bh - 80) // handles - 20
            d.rounded_rectangle((760, hy, 1100, hy + hh), radius=12, fill=(48, 51, 55, 255))
            d.line((772, hy + 3, 1088, hy + 3), fill=(78, 82, 87, 255), width=3)
            box = text(img, (840, hy + hh / 2 - 62), rating, f, (236, 238, 240))
            if i == 1 and k == 0:
                boxes["breaker"] = box
        if handles == 2:
            d.rectangle((1110, y + 60, 1140, y + bh - 60), fill=(70, 74, 78, 255))
        text(img, (120, y + bh / 2 - 26), str(5 + 2 * i), slot, (205, 209, 212))
        y += bh + 30
    return img, boxes, []


# ------------------------------------------------------------------ photographing it
def photograph(flat, boxes, masks, shot, rng, over=None, close=False, hard=False):
    """The flat drawing as a phone photo for a shot, with every box carried into fractions of the photo."""
    from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter
    W, H = SCENE
    base = rng.choice(SURFACES)
    scene = Image.new("RGB", SCENE, base)
    scene = surface_noise(scene, rng, 14)
    fw, fh = flat.size
    dst = quad(fw, fh, shot, rng, 1.12 if close else 0.9)
    src = [(0, 0), (fw, 0), (fw, fh), (0, fh)]
    fwd, back = homography(src, dst), homography(dst, src)
    warped = flat.transform(SCENE, Image.PERSPECTIVE, back, Image.BICUBIC)
    if not close:
        shadow = warped.getchannel("A").filter(ImageFilter.GaussianBlur(14)).point(lambda v: v * 90 // 255)
        scene.paste((0, 0, 0), (9, 12), shadow.crop((0, 0, W - 9, H - 12)))
    scene.paste(warped, (0, 0), warped)
    spot = Image.radial_gradient("L").resize((int(W * 2.6), int(H * 2.6)))
    ox, oy = int(rng.uniform(0.15, 0.45) * W * 2.6 / 2.6), int(rng.uniform(0.15, 0.45) * H * 2.6 / 2.6)
    light = spot.crop((ox, oy, ox + W, oy + H)).point(lambda v: 255 - v * 55 // 255)
    scene = ImageChops.multiply(scene, Image.merge("RGB", (light, light, light)))
    if shot == "glare":
        target = boxes.get(over) if over else None
        if target and hard:
            pts = [apply(fwd, x, y) for x in (target[0], target[2]) for y in (target[1], target[3])]
            cx, cy = sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4
            a = (max(p[0] for p in pts) - min(p[0] for p in pts)) * 0.56
            b = (max(p[1] for p in pts) - min(p[1] for p in pts)) * 1.6
            core = Image.radial_gradient("L").resize((int(a * 4), int(b * 4)))
            core = core.point(lambda v: 255 if v <= 128 else max(0, int(255 * (1 - (v - 128) / 127) ** 2.2)))
            halo = Image.radial_gradient("L").resize((int(a * 7), int(b * 4)))
            halo = halo.point(lambda v: max(0, int((255 - v) * 0.55)))
            glow = Image.new("L", SCENE, 0)
            glow.paste(halo, (int(cx - a * 3.5), int(cy - b * 2)))
            hot = Image.new("L", SCENE, 0)
            hot.paste(core, (int(cx - a * 2), int(cy - b * 2)))
            glow = ImageChops.lighter(glow.filter(ImageFilter.GaussianBlur(24)), hot.filter(ImageFilter.GaussianBlur(5)))
        else:
            if target:
                cx, cy = apply(fwd, (target[0] + target[2]) / 2, (target[1] + target[3]) / 2)
                r = max(150, (target[2] - target[0]) * 0.7)
            else:
                cx, cy, r = W * rng.uniform(0.35, 0.65), H * rng.uniform(0.35, 0.6), 230
            blob = Image.radial_gradient("L").resize((int(r * 2.4), int(r * 1.6)))
            blob = blob.point(lambda v: max(0, 255 - v * 1.25))
            glow = Image.new("L", SCENE, 0)
            glow.paste(blob, (int(cx - r * 1.2), int(cy - r * 0.8)))
            glow = glow.filter(ImageFilter.GaussianBlur(18))
        scene = ImageChops.screen(scene, Image.merge("RGB", (glow, glow, glow)))
    if shot == "low light":
        scene = ImageEnhance.Brightness(scene).enhance(rng.uniform(0.42, 0.52))
        tint = Image.new("RGB", SCENE, (255, 236, 205))
        scene = ImageChops.multiply(scene, tint)
        scene = surface_noise(scene, rng, 26).filter(ImageFilter.GaussianBlur(1.3))
    scene = scene.filter(ImageFilter.GaussianBlur(rng.uniform(0.7, 1.1)))
    scene = surface_noise(scene, rng, 7)
    vig = Image.radial_gradient("L").resize(SCENE).point(lambda v: 255 - max(0, v - 150) * 70 // 105)
    scene = ImageChops.multiply(scene, Image.merge("RGB", (vig, vig, vig)))
    out = scene.resize(OUT, Image.LANCZOS)
    return out, {k: carry(fwd, v, SCENE) for k, v in boxes.items()}, [carry_quad(fwd, m, SCENE) for m in masks]


# ------------------------------------------------------------------ writing everything
def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(img, path, quality):
    from PIL import Image
    clean = Image.frombytes("RGB", img.size, img.convert("RGB").tobytes())
    clean.save(path, "JPEG", quality=quality, optimize=True)


def field_values(spec):
    out = {f: None for f in FIELDS}
    if "breaker" in spec:
        out["breaker"] = spec["breaker"]["rating"]
    for r in spec.get("rows", []):
        out.update(r.get("fields") or {})
    return out


def render(specs, sheet=False):
    photos_dir = DATA.joinpath("photos")
    thumbs = photos_dir.joinpath("thumbs")
    thumbs.mkdir(parents=True, exist_ok=True)
    for old in list(photos_dir.glob("p*.jpg")) + list(thumbs.glob("p*.jpg")):
        old.unlink()
    rng0 = random.Random(specs["seed"])
    entries, key_photos, plates, ids = [], {}, {}, {}
    n = 0
    for spec in specs["subjects"]:
        values = field_values(spec)
        for k, shot in enumerate(spec["shots"]):
            n += 1
            pid = f"p{n:02d}"
            ids[(spec["id"], k)] = pid
            rng = random.Random(rng0.random())
            close = "breaker" in spec
            flat, boxes, masks = (breakers if close else plate)(spec, random.Random(spec["id"]))
            photo, fboxes, fmasks = photograph(flat, boxes, masks, shot["shot"], rng, shot.get("over"), close,
                                             shot.get("hard", False))
            path, thumb_path = photos_dir.joinpath(f"{pid}.jpg"), thumbs.joinpath(f"{pid}.jpg")
            save(photo, path, 84)
            t = photo.copy()
            t.thumbnail((320, 320))
            save(t, thumb_path, 70)
            entries.append({"id": pid, "sha256": sha(path), "thumb_sha256": sha(thumb_path), "w": OUT[0], "h": OUT[1],
                            "bytes": path.stat().st_size, "masks": fmasks})
            fields = {}
            for field, printed in values.items():
                fields[field] = None if printed is None else {"value": printed, "canon": norm.canon(KINDS[field], printed),
                                                              **({"box": fboxes[field]} if field in fboxes else {})}
            key_photos[pid] = {"plate": spec["id"], "kind": spec["kind"], "shot": shot["shot"], "split": spec["split"],
                               "fields": fields}
            plates.setdefault(spec["id"], {"name": spec["kind"].capitalize(), "kind": spec["kind"],
                                           "split": spec["split"], "photos": []})["photos"].append(pid)
            print(f"  {pid}: {spec['id']}, {shot['shot']}")
    bad = [(p, f) for p, v in key_photos.items() for f, x in v["fields"].items() if x and x["canon"] is None]
    if bad:
        raise SystemExit(f"These values don't read as their kind: {bad}")
    manifest = {"made_by": "generate/render.py", "synthetic": True, "date": date.today().isoformat(),
                "note": "Synthetic photos rendered from generate/plates.json. The masks are the flat patches drawn where a "
                        "maker's name, a serial and a barcode would be masked on a real photo.", "photos": entries}
    photos_dir.joinpath("manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    DATA.joinpath("key").mkdir(parents=True, exist_ok=True)
    key = {"made_from": "generate/plates.json", "confirmed_by": "construction: each value is the one the renderer drew",
           "photos": key_photos, "plates": plates, "dropped": {}}
    DATA.joinpath("key", "key.json").write_text(json.dumps(key, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    designs = {"plates": {s["id"]: s["design"] for s in specs["subjects"]}}
    DATA.joinpath("designs.json").write_text(json.dumps(designs, indent=1) + "\n", encoding="utf-8")
    by_id = {s["id"]: s for s in specs["subjects"]}
    assets, asset_designs = [], {}
    for a in specs["job"]["assets"]:
        entry = {"id": a["id"], "photo": ids[(a["plate"], a["shot"])], "kind": by_id[a["plate"]]["kind"],
                 "place": a["place"]}
        design = dict(by_id[a["plate"]]["design"], checks=list(by_id[a["plate"]]["design"]["checks"]))
        if a.get("breaker"):
            entry["breaker_photo"] = ids[(a["breaker"], a.get("breaker_shot", 0))]
            design["checks"].append("panel")
        assets.append(entry)
        asset_designs[a["id"]] = design
    job = {"number": specs["job"]["number"], "day": specs["job"]["day"], "assets": assets, "designs": asset_designs}
    DATA.joinpath("job.json").write_text(json.dumps(job, indent=1) + "\n", encoding="utf-8")
    if sheet:
        contact_sheets(sorted(key_photos))
    return n


def contact_sheets(ids):
    from PIL import Image, ImageDraw
    folder = HERE.joinpath("owner", "out", "sheets")
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("sheet-*.jpg"):
        old.unlink()
    cw, ch, gap = 600, 450, 14
    for k in range(0, len(ids), 6):
        sheet = Image.new("RGB", (3 * cw + 4 * gap, 2 * (ch + 34) + 3 * gap), "white")
        draw = ImageDraw.Draw(sheet)
        for j, pid in enumerate(ids[k:k + 6]):
            with Image.open(DATA.joinpath("photos", f"{pid}.jpg")) as img:
                cell = img.convert("RGB")
                cell.thumbnail((cw, ch))
            x, y = gap + (j % 3) * (cw + gap), gap + (j // 3) * (ch + 34 + gap)
            draw.text((x, y), pid, fill="black", font=font("sans", 0, 24))
            sheet.paste(cell, (x, y + 34))
        save(sheet, folder.joinpath(f"sheet-{k // 6 + 1:02d}.jpg"), 85)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--sheet", action="store_true")
    a = ap.parse_args(argv)
    specs = json.loads(SPECS.read_text(encoding="utf-8"))
    n = render(specs, a.sheet)
    print(f"Rendered {n} photos into data/photos/ with the key, the designs and the job.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
