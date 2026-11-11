"""The privacy scan: every published photo is stripped and masked, and nothing private sits anywhere it would ship.

    python3 engine/privacy.py                 the build folder
    python3 engine/privacy.py --root DIR      another copy, such as the public export

The build is standard library only and can't decode a JPEG, so the scan proves the masking another way:
1. each photo's markers hold no metadata of any kind (only a plain JFIF header with no thumbnail, the tables and the
   image) and nothing follows the end of the image, where phones hide depth maps and second pictures;
2. each photo's hash matches the masking log that owner/prepare.py --mask wrote, so it's the masked copy;
3. the text recognition of the masked photo found no word under a mask;
4. no image of any kind sits anywhere else, so an unmasked copy can't ride along, apart from the README's screenshots
   of the page in docs/gallery/, which must be PNGs that carry no text, date, or camera block and nothing after the end;
5. no word from the private list of masked words (owner/private/, on the owner's machine only) appears in any text file.
It reports problems by file and count and never prints a private word. Standard library only.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PHOTO_DIRS = ("data/photos", "site/photos")
IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp", ".gif", ".tif", ".tiff", ".bmp", ".dng", ".avif")
TEXT_SUFFIXES = (".py", ".js", ".css", ".md", ".json", ".jsonl", ".html", ".txt", ".sh", ".svg")
SKIP = ("reference", ".venv", ".cache", "node_modules", "__pycache__", "owner/private", "owner/out", "data/unmasked",
        "data/ocr_draft", "data/raw", "mockups")
GALLERY = "docs/gallery/"
PNG_TEXT = (b"tEXt", b"zTXt", b"iTXt", b"eXIf", b"tIME")
UNDER_MASK = 0.2          # a recognized word with this share of its area under a mask means the mask let text through
STANDALONE = set(range(0xD0, 0xDA)) | {0x01}
FRAME = set(range(0xC0, 0xD0)) - {0xC4, 0xC8, 0xCC}


def jpeg_problems(data):
    """[] for a clean JPEG, or what's wrong with it. Walks every marker, including the scans of a progressive file."""
    if data[:2] != b"\xff\xd8":
        return ["not a JPEG"]
    problems, i, n = [], 2, len(data)
    while i < n:
        if data[i] != 0xFF:
            return problems + ["a broken marker"]
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return problems + ["cut short"]
        marker = data[i]
        i += 1
        if marker == 0xD9:
            if data[i:].strip(b"\x00"):
                problems.append(f"{n - i} bytes after the end of the image")
            return problems
        if marker in STANDALONE:
            continue
        if i + 2 > n:
            return problems + ["cut short"]
        size = int.from_bytes(data[i:i + 2], "big")
        body = data[i + 2:i + size]
        if marker == 0xE0:
            if not (body[:5] == b"JFIF\x00" and len(body) >= 14 and body[12] == 0 and body[13] == 0):
                problems.append("an APP0 block that isn't a plain JFIF header")
        elif 0xE1 <= marker <= 0xEF:
            kind = body[:4].decode("latin-1", "replace")
            problems.append(f"an APP{marker - 0xE0} block ({re.sub(r'[^A-Za-z]', '', kind) or 'unnamed'})")
        elif marker == 0xFE:
            problems.append("a comment block")
        elif marker not in FRAME | {0xC4, 0xDB, 0xDD, 0xDA, 0xDC, 0xDE, 0xDF}:
            problems.append(f"an unknown block 0x{marker:02X}")
        i += size
        if marker == 0xDA:
            while i < n - 1 and not (data[i] == 0xFF and data[i + 1] not in (0x00,) and
                                     not 0xD0 <= data[i + 1] <= 0xD7):
                i += 1
    return problems + ["no end of image"]


def png_problems(data):
    """[] for a PNG that holds only its image, or what else it holds."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return ["not a PNG"]
    problems, i = [], 8
    while i + 8 <= len(data):
        size, kind = int.from_bytes(data[i:i + 4], "big"), data[i + 4:i + 8]
        if kind in PNG_TEXT:
            problems.append(f"a {kind.decode('latin-1')} block")
        i += 12 + size
        if kind == b"IEND":
            return problems + ([f"{len(data) - i} bytes after the end of the image"] if data[i:] else [])
    return problems + ["no end of image"]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def skipped(rel):
    return any(rel == s or rel.startswith(s + "/") for s in SKIP) or "__pycache__" in rel


def files(root):
    root = Path(root)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not skipped(rel):
            yield rel, p


def overlap(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0.0, w) * max(0.0, h)


def inside(x, y, quad):
    """True when the point falls inside the four-cornered shape, by counting edge crossings."""
    hit = False
    for (x1, y1), (x2, y2) in zip(quad, quad[1:] + quad[:1]):
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            hit = not hit
    return hit


def covered(b, mask):
    """The share of a word's box under a mask. A mask is a box drawn upright on the photo, or the four corners of a
    patch on a tilted plate, measured on a grid of points so a tilted patch's corners don't count as covered."""
    if isinstance(mask, dict):
        pts = [(b[0] + (b[2] - b[0]) * (i + 0.5) / 8, b[1] + (b[3] - b[1]) * (j + 0.5) / 4) for i in range(8) for j in range(4)]
        return sum(inside(x, y, mask["quad"]) for x, y in pts) / len(pts)
    return overlap(b, mask) / max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))


def words_under_masks(ocr, masks):
    """How many recognized words sit at least a fifth under a mask (both in fractions of the photo)."""
    return sum(1 for line in ocr.get("lines") or [] for wd in line.get("words") or []
               if any(covered(wd["box"], m) >= UNDER_MASK for m in masks))


def private_words(root):
    path = Path(root).joinpath("owner", "private", "masked_words.json")
    if not path.exists():
        path = HERE.joinpath("owner", "private", "masked_words.json")
    if not path.exists():
        return None
    return [w for w in json.loads(path.read_text(encoding="utf-8")).get("words", []) if len(w) >= 3]


def redact(text, words, mark="[maker]"):
    """(text, count) with every private word replaced, so a maker's name a model writes never reaches a record."""
    if not words:
        return text, 0
    pat = re.compile("|".join(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])" for w in words), re.IGNORECASE)
    return pat.subn(mark, text)


def scan(root=HERE):
    root = Path(root)
    problems, photos = [], 0
    manifest_path = root.joinpath("data", "photos", "manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {"photos": []}
    known = {}
    for entry in manifest.get("photos", []):
        known[entry["sha256"]] = entry
        if entry.get("thumb_sha256"):
            known[entry["thumb_sha256"]] = dict(entry, thumb=True)
    for rel, p in files(root):
        if p.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if rel.startswith(GALLERY) and p.suffix.lower() == ".png":
            problems += [f"{rel}: {why}" for why in png_problems(p.read_bytes())]
            continue
        if not any(rel.startswith(d + "/") for d in PHOTO_DIRS) or p.suffix.lower() != ".jpg":
            problems.append(f"{rel} is an image outside the published photo folders")
            continue
        photos += 1
        bad = jpeg_problems(p.read_bytes())
        if bad:
            problems.append(f"{rel}: {', '.join(bad)}")
        entry = known.get(sha256(p))
        if entry is None:
            problems.append(f"{rel} isn't in the masking log, so it may not be the masked copy")
            continue
        ocr_path = root.joinpath("data", "ocr", f"{entry['id']}.json")
        if not entry.get("thumb") and ocr_path.exists():
            under = words_under_masks(json.loads(ocr_path.read_text(encoding="utf-8")), entry.get("masks", []))
            if under:
                problems.append(f"{rel}: the text recognition read {under} word(s) under a mask")
    private = private_words(root)
    if private:
        pat = re.compile("|".join(r"(?<![A-Za-z0-9])" + re.escape(w) + r"(?![A-Za-z0-9])" for w in private),
                         re.IGNORECASE)
        for rel, p in files(root):
            if p.suffix.lower() in TEXT_SUFFIXES:
                hits = len(pat.findall(p.read_text(encoding="utf-8", errors="ignore")))
                if hits:
                    problems.append(f"{rel} holds {hits} word(s) from the private list of masked words")
    return {"photos": photos, "problems": problems, "private_list": private is not None,
            "logged": len(manifest.get("photos", []))}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(HERE))
    a = ap.parse_args(argv)
    out = scan(a.root)
    for line in out["problems"]:
        print("  " + line)
    which = "with the private list" if out["private_list"] else "without the private list (it lives on the owner's machine)"
    print(f"Privacy scan, {which}: {out['photos']} photos checked, {len(out['problems'])} problems.")
    return 1 if out["problems"] else 0


if __name__ == "__main__":
    sys.path.insert(0, str(HERE))
    sys.exit(main())
