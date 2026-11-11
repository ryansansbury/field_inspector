"""The owner's machine only. Record the AI read of every photo, the runs the page replays.

    bash owner/run.sh 1 and 2                                     the owner's two runs, in order
    .venv/bin/python3 owner/record_ai_runs.py --split dev          the dev photos with the default model
    .venv/bin/python3 owner/record_ai_runs.py --split all --models compare
                                                                  every photo with every model in the comparison
    .venv/bin/python3 owner/record_ai_runs.py --split dev --stand-in
                                                                  a dry run with no model and no network

Each read sends one masked photo with the prompt and gets the fields back. The reply is validated, and a reply with the
wrong shape gets one repair request that resends the photo with the problems listed, with both calls' cost kept. Any
word from the private list of masked words (owner/private/) in the record is replaced with "[maker]" before it's saved,
and the record counts the replacements, so no maker's name can reach the repo. Each record goes to
data/ai_runs/read/<photo>/<model>.json with the prompt hash, the input hash, the reply, the problems, tokens, cost and
time, and each read adds a line to data/ai_runs/audit.jsonl. A record that already matches today's prompt and photo is
skipped, so a stopped run can start again. Real runs need the photos and the designs frozen, and every photo outside dev
needs the prompt frozen too. A vendor that fails stops only its own model, and the summary says so. A model that reads
nothing on its first new photo stops before that record is saved, since the photo most likely isn't reaching it.
"""
import argparse
import json
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs, llm, validate  # noqa: E402
from engine import privacy  # noqa: E402
from evals import freeze  # noqa: E402
from owner import stand_in  # noqa: E402

RUNS = HERE.joinpath("data", "ai_runs")
KEY = HERE.joinpath("data", "key", "key.json")
PHOTOS = HERE.joinpath("data", "photos")


def key_for(item):
    """A vendor's key from the macOS Keychain, handed straight to the backend and never printed."""
    done = subprocess.run(["security", "find-generic-password", "-s", item, "-w"], capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError(f"no Keychain item named {item}")
    return done.stdout.strip()


def sizes():
    manifest = json.loads(PHOTOS.joinpath("manifest.json").read_text(encoding="utf-8"))
    return {p["id"]: (p["w"], p["h"]) for p in manifest["photos"]}


def record_path(photo, model):
    return RUNS.joinpath("read", photo, f"{model}.json")


def already(photo, model, input_hash):
    path = record_path(photo, model)
    if not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    return rec if rec.get("prompt_hash") == inputs.prompt_hash() and rec.get("input_hash") == input_hash else None


def combined(a, b):
    """Two calls' meta as one: time and tokens added, and the cost of both."""
    out = dict(b)
    for k in ("ms", "input_tokens", "output_tokens", "cost_usd"):
        if a.get(k) is not None and b.get(k) is not None:
            out[k] = round(a[k] + b[k], 6) if k == "cost_usd" else a[k] + b[k]
    out["calls"] = 2
    return out


def run_one(backend, label, photo, model, fields, private, size, first=False):
    image = inputs.image(PHOTOS.joinpath(f"{photo}.jpg"))
    user = inputs.user_text(photo, *size)
    input_hash = inputs.input_hash(image["bytes"], user)
    done = already(photo, model, input_hash)
    if done:
        return done, True
    system = inputs.system_prompt()
    t0 = time.time()
    text, meta = backend(system, user, image)
    reads, held, problems = validate.read(text, fields)
    repaired = False
    if problems:
        fix = (user + "\n\nYour reply had these problems:\n- " + "\n- ".join(problems) +
               "\n\nReturn the complete corrected JSON object, and nothing else.")
        text2, meta2 = backend(system, fix, image)
        reads2, held2, problems2 = validate.read(text2, fields)
        meta = combined(meta, meta2)
        if len(problems2) < len(problems):
            text, reads, held, problems, repaired = text2, reads2, held2, problems2, True
    if first and not any(r["status"] == "read" for r in reads.values()):
        raise RuntimeError(f"it read nothing on {photo}, its first photo, so the photo may not be reaching it, and the "
                           f"record wasn't saved (the reply began {text.strip()[:120]!r})")
    rec = {"photo": photo, "model": model, "label": label, "date": date.today().isoformat(),
           "recorded_at": datetime.now().isoformat(timespec="seconds"), "prompt_hash": inputs.prompt_hash(),
           "input_hash": input_hash, "user": user, "reply": text, "repaired": repaired, "problems": problems,
           "held": held, "ms": round((time.time() - t0) * 1000), "meta": meta}
    clean, redacted = privacy.redact(json.dumps(rec, ensure_ascii=False), private)
    rec = json.loads(clean)
    rec["redacted"] = redacted
    path = record_path(photo, model)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")
    with RUNS.joinpath("audit.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps({"at": rec["recorded_at"], "photo": photo, "model": model, "ms": rec["ms"],
                            "tokens_in": meta.get("input_tokens"), "tokens_out": meta.get("output_tokens"),
                            "cost_usd": meta.get("cost_usd"), "repaired": repaired, "problems": len(problems),
                            "redacted": redacted}) + "\n")
    return rec, False


def line_for(photo, model, rec, cached):
    reads, held, _ = validate.read(rec["reply"], inputs.fields())
    n = sum(1 for r in reads.values() if r["status"] == "read")
    m = sum(1 for r in reads.values() if r["status"] == "unreadable")
    parts = [f"{n} read", f"{m} unreadable", f"{len(held)} held"]
    if rec.get("repaired"):
        parts.append("repaired")
    if rec.get("redacted"):
        parts.append(f"{rec['redacted']} maker words replaced")
    cost = (rec.get("meta") or {}).get("cost_usd")
    parts.append("(already recorded)" if cached else f"${cost or 0:.4f}, {rec['ms'] / 1000:.1f} s")
    return f"  {photo} {model}: " + ", ".join(parts)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", required=True, choices=["dev", "test", "all"])
    ap.add_argument("--models", default="default", help="default, compare, or one model id")
    ap.add_argument("--photos", default="", help="photo ids, comma separated")
    ap.add_argument("--stand-in", action="store_true")
    a = ap.parse_args(argv)
    key = json.loads(KEY.read_text(encoding="utf-8"))
    if not a.stand_in:
        for stage in ("photos", "designs"):
            if not freeze.ready(stage):
                raise SystemExit(f"The {stage} stage isn't frozen and unchanged, so no model runs yet.")
        if a.split != "dev" and not freeze.ready("prompts"):
            raise SystemExit("The prompt isn't frozen yet. It freezes after the dev round.")
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    by_id = {m["id"]: m for m in cfg["models"]}
    if a.stand_in:
        models = [(stand_in.MODEL, None)]
    else:
        ids = cfg["compare"] if a.models == "compare" else [cfg["default"]] if a.models == "default" else [a.models]
        models = [(i, by_id[i]) for i in ids if by_id[i].get("enabled", True)]
    fields, private, size = inputs.fields(), privacy.private_words(HERE) or [], sizes()
    names = [p for p in a.photos.split(",") if p] or sorted(p for p, v in key["photos"].items()
                                                           if a.split == "all" or v["split"] == a.split)
    print(f"Reading {len(names)} photos with {', '.join(m for m, _ in models)}")
    failed, spent = [], 0.0
    for model_id, entry in models:
        try:
            backend = stand_in.Backend(key, fields) if a.stand_in else llm.backend_for(entry, key_for)
        except (RuntimeError, ValueError) as e:
            failed.append(f"{model_id} ({e})")
            print(f"  {model_id}: skipped, {e}")
            continue
        label = stand_in.LABEL if a.stand_in else entry["label"]
        first = True
        for photo in names:
            try:
                rec, cached = run_one(backend, label, photo, model_id, fields, private, size[photo], first)
                first = first and cached
            except RuntimeError as e:
                failed.append(f"{model_id} on {photo}")
                print(f"  {photo} {model_id}: stopped, {str(e)[:900]}")
                break
            spent += 0 if cached else ((rec.get("meta") or {}).get("cost_usd") or 0)
            print(line_for(photo, model_id, rec, cached), flush=True)
    print(f"Spent about ${spent:.2f} on this run.")
    if failed:
        print("These stopped for the reasons above, and running the same command again picks up where they left off: "
              + "; ".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
