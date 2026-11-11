"""A dress rehearsal of the real build, run before any real photo is read.

    python3 tests/rehearse.py           build and check the rehearsal in .cache/rehearsal/
    python3 tests/rehearse.py --real    the same on the real photos, recordings and freeze, with bracketed stand-ins
                                        for the cast, for the time between the last run and the names

It copies the code into .cache/rehearsal/ and gives that copy a made-up world from the preview's drawn plates. The
photos are stand-in JPEG files that pass the privacy scan's marker check and are never shown in a browser, and they come
with their recognized text, a key with a dev and a test split, and the job and its designs. Two rehearsal models get
recordings in the recorder's own format. One reads everything right, and one carries planted mistakes: a wrong model the
photo's text seems to confirm (past the line), a wrong model one character off (caught), and volts that don't read as
volts (held). Then it freezes, scores, compares and builds the real page there, and runs the node click-through and the
export's checks on it. Nothing it makes is a result, and nothing leaves .cache/. With --real it skips the made-up world
and copies the real data and freeze instead, so the real page and its click-through can be checked before
config/names.json arrives. Standard library only.
"""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.joinpath(".cache", "rehearsal")
PREVIEW = HERE.joinpath("tests", "fixtures", "preview")
COPY = ("build.py", "WORDS.md", "app", "agents", "engine", "evals", "generate", "owner", "prompts", "config", "tests", "tools",
        "site/app.js", "site/rules.js", "site/normalize.js", "site/app.css", "site/favicon.svg", "site/fonts", "reference/LICENSE")
SKIP = ("__pycache__", "frozen.json", "scores.json", "preview_scores.json", "model_comparison.json",
        "tuning_rounds.json")
DEV = {"p09": ("p03", "angled"), "p10": ("p07", "glare"), "p11": ("p06", "low light")}
MISTAKES = {"p05": ("model", "DRY-Z7E"), "p06": ("model", "DW-24P1"), "p04": ("volts", "two forty")}


def seg(marker, body):
    return b"\xff" + bytes([marker]) + (len(body) + 2).to_bytes(2, "big") + body


def fake_jpeg(tag):
    """A file with a clean JPEG's markers and the photo's id in its data, so every hash differs."""
    data = bytes(b for b in tag.encode() if b != 0xFF)
    return (b"\xff\xd8" + seg(0xE0, b"JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00") + seg(0xDB, b"\x00" + bytes(64)) +
            seg(0xC0, b"\x08\x00\x10\x00\x10\x01\x01\x11\x00") + seg(0xC4, bytes(17)) +
            seg(0xDA, b"\x01\x01\x00\x00\x3f\x00") + data + b"\xff\xd9")


def sha(b):
    return hashlib.sha256(b).hexdigest()


def run(*args):
    r = subprocess.run([sys.executable] + list(args), cwd=ROOT, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"Rehearsal stopped at {' '.join(args)}:\n{(r.stdout + r.stderr)[-1500:]}")
    return r.stdout


def copy_code():
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for rel in COPY:
        src = HERE.joinpath(rel)
        if not src.exists():
            continue
        dest = ROOT.joinpath(rel)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*SKIP))
        else:
            shutil.copyfile(src, dest)


def make_world():
    key = json.loads(PREVIEW.joinpath("key", "key.json").read_text(encoding="utf-8"))
    designs = json.loads(PREVIEW.joinpath("designs.json").read_text(encoding="utf-8"))
    for new, (src, shot) in DEV.items():
        plate = "dev-" + key["photos"][src]["plate"]
        key["photos"][new] = dict(key["photos"][src], plate=plate, shot=shot, split="dev")
        key["plates"][plate] = dict(key["plates"][key["photos"][src]["plate"]], photos=[new], split="dev")
        designs["plates"][plate] = designs["plates"][key["photos"][src]["plate"]]
    data = ROOT.joinpath("data")
    for folder in ("photos/thumbs", "ocr", "key"):
        data.joinpath(folder).mkdir(parents=True, exist_ok=True)
    entries = []
    for pid in sorted(key["photos"]):
        src = DEV.get(pid, (pid,))[0]
        ocr = json.loads(PREVIEW.joinpath("ocr", f"{src}.json").read_text(encoding="utf-8"))
        ocr["photo"] = pid
        photo, thumb = fake_jpeg(pid), fake_jpeg(pid + "-thumb")
        data.joinpath("photos", f"{pid}.jpg").write_bytes(photo)
        data.joinpath("photos", "thumbs", f"{pid}.jpg").write_bytes(thumb)
        ocr["sha256"] = sha(photo)
        data.joinpath("ocr", f"{pid}.json").write_text(json.dumps(ocr), encoding="utf-8")
        entries.append({"id": pid, "sha256": sha(photo), "thumb_sha256": sha(thumb), "w": ocr["w"], "h": ocr["h"],
                        "bytes": len(photo), "masks": [[0.09, 0.12, 0.55, 0.22]]})
    data.joinpath("photos", "manifest.json").write_text(json.dumps({"made_by": "tests/rehearse.py", "photos": entries}),
                                                        encoding="utf-8")
    data.joinpath("key", "key.json").write_text(json.dumps(key, indent=1, sort_keys=True), encoding="utf-8")
    data.joinpath("designs.json").write_text(json.dumps(designs, indent=1), encoding="utf-8")
    shutil.copyfile(PREVIEW.joinpath("job.json"), data.joinpath("job.json"))
    write_cast()


def write_cast():
    ROOT.joinpath("config", "names.json").write_text(json.dumps(
        {"installer": "[installer]", "technician": "[technician] [one]", "reviewer": "[reviewer] [two]"}),
        encoding="utf-8")


def copy_real():
    """The real photos, their text, the key, the job, the designs, the recordings and the freeze."""
    shutil.copytree(HERE.joinpath("data"), ROOT.joinpath("data"), ignore=shutil.ignore_patterns("__pycache__"))
    for rel in ("evals/frozen.json", "evals/tuning_rounds.json"):
        shutil.copyfile(HERE.joinpath(rel), ROOT.joinpath(rel))
    write_cast()


def make_recordings():
    """The stand-in through the real recorder, then two rehearsal models made from its records."""
    run("owner/record_ai_runs.py", "--split", "all", "--stand-in")
    runs = ROOT.joinpath("data", "ai_runs", "read")
    for photo_dir in sorted(runs.iterdir()):
        base = json.loads(photo_dir.joinpath("stand-in.json").read_text(encoding="utf-8"))
        for model, label, cost, ms in (("claude-sonnet", "Rehearsal model A", 0.0124, 6200),
                                       ("claude-haiku", "Rehearsal model B", 0.0011, 3900)):
            rec = dict(base, model=model, label=label, ms=ms,
                       meta={"ms": ms, "input_tokens": 2600, "output_tokens": 640, "cost_usd": cost})
            if model == "claude-haiku" and photo_dir.name in MISTAKES:
                field, value = MISTAKES[photo_dir.name]
                reply = json.loads(rec["reply"])
                reply["fields"][field]["value"] = value
                rec["reply"] = json.dumps(reply)
            photo_dir.joinpath(f"{model}.json").write_text(json.dumps(rec, indent=1), encoding="utf-8")


def main(argv=None):
    real = "--real" in (sys.argv[1:] if argv is None else argv)
    copy_code()
    if real:
        copy_real()
    else:
        make_world()
        run("evals/freeze.py", "photos")
        run("evals/freeze.py", "designs")
        make_recordings()
    built = run("build.py")
    node = subprocess.run(["node", "tests/js/check_app.js", str(ROOT.joinpath("site"))], cwd=ROOT, capture_output=True,
                          text=True)
    # The export tool stays out of the public repo, so a clone rehearses everything up to the export.
    export = (run("tools/export_public.py", "--dry-run", "--dest", ".cache/public/field_inspector")
              if ROOT.joinpath("tools", "export_public.py").exists() else "skipped: the export tool isn't in this copy")
    scores = json.loads(ROOT.joinpath("evals", "scores.json").read_text(encoding="utf-8"))["models"]
    out = {"built": built.strip().splitlines()[-1], "click_through": (node.stdout.strip().splitlines() or [""])[-1],
           "click_through_ok": node.returncode == 0, "failures": [ln for ln in node.stdout.splitlines() if ln.startswith("FAIL")],
           "export": export.strip().splitlines()[-1],
           "route": json.loads(ROOT.joinpath("evals", "model_comparison.json").read_text(encoding="utf-8"))["route"],
           "test": {m: {"accuracy": s["test"]["fields"]["accuracy"], "past_line": s["test"]["line"]["partial"]["past"],
                        "caught": s["test"]["line"]["partial"]["caught"], "missed": s["test"]["checks"]["missed"]}
                    for m, s in scores.items()}}
    print(json.dumps(out, indent=1))
    return 0 if out["click_through_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
