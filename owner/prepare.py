"""The owner's machine only. Prepare the owner's photos: stripped and upright first, masked after a person confirms the masks.

    .venv/bin/python3 owner/prepare.py              part one: ~/Pictures/field_inspector_raw/ into data/unmasked/
    .venv/bin/python3 owner/prepare.py --mask       part two: the confirmed masks into data/photos/, then the unmasked
                                                    copies and the draft read are deleted
    .venv/bin/python3 owner/prepare.py --sheets     the contact sheets again (part two writes them too)
    .venv/bin/python3 owner/prepare.py --self-test  a photo it makes itself, tagged and turned, before any real one

Part one reads the raw folder directly, so a raw photo never enters the build folder. It takes HEIC, JPEG and PNG
(a Live Photo's movie is skipped), sorts them by the time they were taken, turns each upright from its orientation tag,
converts its colors to sRGB, drops every metadata block (the location included) by rebuilding the image from its pixels,
and saves it at 1568 pixels on the long edge as p01 and up.

Part two fills each confirmed mask with a flat patch in the area's own median color, padded by 8% with a soft edge,
since blurred or pixelated text can sometimes be read back. It saves the masked photo and a thumbnail with no
metadata, writes the masking log (data/photos/manifest.json) that the privacy scan checks every published photo
against, keeps the words that were under the masks in owner/private/ (gitignored, on this Mac only) for the brand
checks, writes the contact sheets for review, and deletes the unmasked copies and the draft read.
"""
import argparse
import hashlib
import io
import json
import math
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import confirm, normalize as norm, privacy  # noqa: E402

RAW = Path.home().joinpath("Pictures", "field_inspector_raw")
UNMASKED, DRAFT = HERE.joinpath("data", "unmasked"), HERE.joinpath("data", "ocr_draft")
PHOTOS = HERE.joinpath("data", "photos")
THUMBS = PHOTOS.joinpath("thumbs")
KEY_DRAFT = HERE.joinpath("data", "key_draft.json")
OUT, PRIVATE = HERE.joinpath("owner", "out"), HERE.joinpath("owner", "private")
LONG_EDGE, THUMB_EDGE = 1568, 320
WORK_QUALITY, QUALITY, THUMB_QUALITY = 92, 82, 70
PAD = 0.08
SUFFIXES = (".heic", ".heif", ".jpg", ".jpeg", ".png")


def stop(text):
    raise SystemExit(text)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ------------------------------------------------------------------ part one
def open_image(path):
    from PIL import Image
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
    except ImportError:
        if Path(path).suffix.lower() in (".heic", ".heif"):
            stop("pillow-heif isn't installed, so HEIC photos can't be read. Run bash owner/bootstrap.sh again.")
    return Image.open(path)


def taken_at(img, path):
    """When the photo was taken, from its own tag, or the file's time when it has none. Used only to order them."""
    try:
        exif = img.getexif()
        stamp = exif.get_ifd(0x8769).get(36867) or exif.get(306)
        if stamp:
            return datetime.strptime(str(stamp).strip()[:19], "%Y:%m:%d %H:%M:%S").isoformat()
    except (ValueError, AttributeError, KeyError):
        pass
    return datetime.fromtimestamp(Path(path).stat().st_mtime).isoformat(timespec="seconds")


def upright_srgb(img):
    """Turned upright from its orientation tag, its colors converted to sRGB, and rebuilt from its pixels so no metadata
    of any kind can ride along."""
    from PIL import Image, ImageCms, ImageOps
    img = ImageOps.exif_transpose(img)
    icc = img.info.get("icc_profile")
    if icc:
        try:
            img = ImageCms.profileToProfile(img.convert("RGB"), ImageCms.ImageCmsProfile(io.BytesIO(icc)),
                                            ImageCms.createProfile("sRGB"), outputMode="RGB")
        except (OSError, ValueError, ImageCms.PyCMSError):
            pass
    img = img.convert("RGB")
    return Image.frombytes("RGB", img.size, img.tobytes())


def fit(img, edge):
    from PIL import Image
    if max(img.size) <= edge:
        return img
    scale = edge / max(img.size)
    return img.resize((max(1, round(img.width * scale)), max(1, round(img.height * scale))), Image.LANCZOS)


def save_clean(img, path, quality):
    """A baseline JPEG with no metadata: nothing is passed to the encoder but the pixels and the quality."""
    img.save(path, "JPEG", quality=quality, optimize=True)


def prepare_one(path):
    with open_image(path) as img:
        return fit(upright_srgb(img), LONG_EDGE)


def part_one(raw=RAW, again=False):
    if not again and list(PHOTOS.glob("p*.jpg")):
        stop("The masked photos are already in data/photos/. Part one renumbers every photo, so it needs --again.")
    if not again and KEY_DRAFT.exists():
        stop("The verification page has saved work in data/key_draft.json. Part one would renumber the photos and "
             "lose its place, so it needs --again, and only if the raw folder hasn't changed.")
    if not raw.exists():
        stop(f"No folder at {raw}. AirDrop the photos there first.")
    files = [p for p in sorted(raw.iterdir()) if p.suffix.lower() in SUFFIXES and not p.name.startswith(".")]
    if not files:
        stop(f"No photos in {raw}. AirDrop them there first.")
    items = []
    for p in files:
        with open_image(p) as img:
            items.append((taken_at(img, p), p.name, p))
    items.sort()
    UNMASKED.mkdir(parents=True, exist_ok=True)
    for old in UNMASKED.glob("p*.jpg"):
        old.unlink()
    log = {}
    for n, (when, name, p) in enumerate(items, 1):
        pid = f"p{n:02d}"
        img = prepare_one(p)
        save_clean(img, UNMASKED.joinpath(f"{pid}.jpg"), WORK_QUALITY)
        log[pid] = {"raw": name, "taken": when, "w": img.width, "h": img.height}
        print(f"  {pid}: {img.width} by {img.height}")
    OUT.mkdir(parents=True, exist_ok=True)
    OUT.joinpath("prepare_log.json").write_text(json.dumps(log, indent=1), encoding="utf-8")
    print(f"Prepared {len(items)} photos into data/unmasked/: upright, stripped and {LONG_EDGE} pixels on the long edge.")


# ------------------------------------------------------------------ part two
def pad_box(box, w, h, pad=PAD):
    """(the padded box, the box itself) in whole pixels, from a box in fractions."""
    x0, y0, x1, y1 = box[0] * w, box[1] * h, box[2] * w, box[3] * h
    px, py = max(4.0, (x1 - x0) * pad), max(4.0, (y1 - y0) * pad)
    outer = (max(0, math.floor(x0 - px)), max(0, math.floor(y0 - py)), min(w, math.ceil(x1 + px)),
             min(h, math.ceil(y1 + py)))
    core = (max(0, math.floor(x0)), max(0, math.floor(y0)), min(w, math.ceil(x1)), min(h, math.ceil(y1)))
    return outer, core


def apply_masks(img, masks):
    """Each mask as a flat patch in the area's median color. The box itself is fully covered and only the padding
    fades into the photo."""
    from PIL import Image, ImageDraw, ImageFilter, ImageStat
    for box in masks:
        outer, core = pad_box(box, img.width, img.height)
        if outer[2] <= outer[0] or outer[3] <= outer[1]:
            continue
        region = img.crop(outer)
        patch = Image.new("RGB", region.size, tuple(int(v) for v in ImageStat.Stat(region).median))
        rel = (core[0] - outer[0], core[1] - outer[1], core[2] - outer[0] - 1, core[3] - outer[1] - 1)
        alpha = Image.new("L", region.size, 0)
        ImageDraw.Draw(alpha).rectangle(rel, fill=255)
        edge = max(1.0, min(rel[0], rel[1], region.width - 1 - rel[2], region.height - 1 - rel[3]) / 2)
        alpha = alpha.filter(ImageFilter.GaussianBlur(edge))
        ImageDraw.Draw(alpha).rectangle(rel, fill=255)
        img.paste(patch, outer[:2], alpha)
    return img


def masked_words(draft, masks, plain):
    """The words the draft read found at least half under a mask, plus what any barcode held. Plain plate words and
    short numbers stay out, so the brand checks don't trip on "VOLTS" or "25"."""
    out = set()
    for line in draft.get("lines") or []:
        for wd in line.get("words") or []:
            b = wd["box"]
            area = max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))
            if not any(privacy.overlap(b, m) / area >= 0.5 for m in masks):
                continue
            token = re.sub(r"[^A-Za-z0-9]", "", wd["text"])
            if len(token) >= 3 and token.upper() not in plain and (not token.isdigit() or len(token) >= 5):
                out.add(token)
    for code in draft.get("barcodes") or []:
        out.update(t for t in re.findall(r"[A-Za-z0-9]{4,}", code.get("payload") or "") if t.upper() not in plain)
    return out


def part_two():
    if not KEY_DRAFT.exists():
        stop("No data/key_draft.json yet. Run bash owner/verify.sh and confirm every photo first.")
    state = json.loads(KEY_DRAFT.read_text(encoding="utf-8")).get("photos", {})
    ids = sorted(p.stem for p in UNMASKED.glob("p*.jpg"))
    if not ids:
        stop("data/unmasked/ is empty. Part two has already run, or part one hasn't.")
    waiting = [i for i in ids if (state.get(i) or {}).get("status") not in ("done", "dropped")]
    if waiting:
        stop(f"These photos aren't confirmed or dropped yet: {', '.join(waiting)}. Finish them on the page first.")
    fields = confirm.load_fields()
    plain = set(fields.get("plain_words", ())) | {w for lab in confirm.label_owners(fields) for w in lab}
    PHOTOS.mkdir(parents=True, exist_ok=True)
    THUMBS.mkdir(parents=True, exist_ok=True)
    for old in list(PHOTOS.glob("p*.jpg")) + list(THUMBS.glob("p*.jpg")):
        old.unlink()
    entries, words, kept = [], set(), [i for i in ids if state[i]["status"] == "done"]
    for pid in kept:
        masks = state[pid].get("masks") or []
        with open_image(UNMASKED.joinpath(f"{pid}.jpg")) as src:
            img = apply_masks(src.convert("RGB"), masks)
        path, thumb_path = PHOTOS.joinpath(f"{pid}.jpg"), THUMBS.joinpath(f"{pid}.jpg")
        save_clean(img, path, QUALITY)
        thumb = img.copy()
        thumb.thumbnail((THUMB_EDGE, THUMB_EDGE))
        save_clean(thumb, thumb_path, THUMB_QUALITY)
        area = [[round(v, 4) for v in m] for m in masks]
        entries.append({"id": pid, "sha256": sha(path), "thumb_sha256": sha(thumb_path), "w": img.width,
                        "h": img.height, "bytes": path.stat().st_size, "masks": area})
        draft_path = DRAFT.joinpath(f"{pid}.json")
        if draft_path.exists():
            words |= masked_words(json.loads(draft_path.read_text(encoding="utf-8")), area, plain)
        print(f"  {pid}: {len(masks)} masks")
    manifest = {"made_by": "owner/prepare.py --mask", "date": datetime.now().date().isoformat(),
                "note": "Every published photo, its hash and the areas masked on it. The privacy scan checks each "
                        "photo against this log.", "photos": entries}
    PHOTOS.joinpath("manifest.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    PRIVATE.mkdir(parents=True, exist_ok=True)
    PRIVATE.joinpath("masked_words.json").write_text(json.dumps({"words": sorted(words)}, indent=1), encoding="utf-8")
    contact_sheets(kept)
    shutil.rmtree(UNMASKED, ignore_errors=True)
    shutil.rmtree(DRAFT, ignore_errors=True)
    dropped = [i for i in ids if state[i]["status"] == "dropped"]
    print(f"Masked {len(kept)} photos into data/photos/ ({len(dropped)} dropped), kept {len(words)} masked words in "
          f"owner/private/, and deleted the unmasked copies and the draft read.")


def contact_sheets(ids):
    """Six masked photos to a sheet, each with its number, for a look before the key freezes."""
    from PIL import Image, ImageDraw, ImageFont
    folder = OUT.joinpath("sheets")
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("sheet-*.jpg"):
        old.unlink()
    cw, ch, gap = 600, 450, 14
    try:
        font = ImageFont.load_default(size=24)
    except TypeError:
        font = ImageFont.load_default()
    for k in range(0, len(ids), 6):
        sheet = Image.new("RGB", (3 * cw + 4 * gap, 2 * (ch + 34) + 3 * gap), "white")
        draw = ImageDraw.Draw(sheet)
        for j, pid in enumerate(ids[k:k + 6]):
            with open_image(PHOTOS.joinpath(f"{pid}.jpg")) as img:
                cell = img.convert("RGB")
                cell.thumbnail((cw, ch))
            x, y = gap + (j % 3) * (cw + gap), gap + (j // 3) * (ch + 34 + gap)
            draw.text((x, y), pid, fill="black", font=font)
            sheet.paste(cell, (x, y + 34))
        save_clean(sheet, folder.joinpath(f"sheet-{k // 6 + 1:02d}.jpg"), 85)
    print(f"Wrote {math.ceil(len(ids) / 6)} contact sheets into owner/out/sheets/.")


# ------------------------------------------------------------------ the self-test
def self_test():
    """A photo with an orientation tag, a camera tag and a date, turned on its side: part one has to stand it up and
    drop every tag, and a mask has to leave its area flat. HEIC too, when this Mac's pillow-heif can write one."""
    from PIL import Image, ImageDraw, ImageStat
    folder = HERE.joinpath(".cache", "selftest")
    folder.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (3000, 2000), (226, 228, 224))
    ImageDraw.Draw(img).rectangle((600, 800, 2400, 1100), fill=(20, 20, 20))
    exif = img.getexif()
    exif[0x0112], exif[0x010F], exif[306] = 6, "SelfTestCam", "2026:11:09 10:00:00"
    problems = []
    paths = [folder.joinpath("IMG_0001.JPG")]
    img.save(paths[0], "JPEG", exif=exif.tobytes())
    try:
        from pillow_heif import register_heif_opener
        register_heif_opener()
        img.save(folder.joinpath("IMG_0002.HEIC"), exif=exif.tobytes())
        paths.append(folder.joinpath("IMG_0002.HEIC"))
    except Exception as e:  # noqa: BLE001 - reading HEIC still gets checked on the real photos
        print(f"  (HEIC writing isn't available here, {type(e).__name__}, so only reading gets used.)")
    for p in paths:
        out = prepare_one(p)
        target = folder.joinpath(p.stem + ".clean.jpg")
        save_clean(out, target, QUALITY)
        bad = privacy.jpeg_problems(target.read_bytes())
        if bad:
            problems.append(f"{p.name} kept {', '.join(bad)}")
        if max(out.size) != LONG_EDGE or (p.suffix.upper() == ".JPG" and out.size != (1045, LONG_EDGE)):
            problems.append(f"{p.name} came out {out.width} by {out.height}, not standing up at {LONG_EDGE}")
    noisy = Image.new("RGB", (800, 600), (240, 240, 240))
    ImageDraw.Draw(noisy).text((300, 200), "SERIAL X12345678", fill="black")
    masked = apply_masks(noisy, [[0.3, 0.3, 0.7, 0.4]])
    spread = ImageStat.Stat(masked.crop((240, 180, 560, 240))).stddev
    if max(spread) > 1.0:
        problems.append(f"a mask left its area uneven (spread {max(spread):.1f})")
    if problems:
        stop("Self-test failed: " + "; ".join(problems))
    print(f"Self-test passed: {len(paths)} photo types stood up and stripped, and a mask left its area flat.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--mask", action="store_true")
    ap.add_argument("--sheets", action="store_true")
    ap.add_argument("--again", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        self_test()
    elif a.sheets:
        contact_sheets(sorted(p.stem for p in PHOTOS.glob("p*.jpg")))
    elif a.mask:
        part_two()
    else:
        part_one(again=a.again)


if __name__ == "__main__":
    main()
