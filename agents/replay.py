"""Replay the recorded reads for the page and the scores, checking every one again exactly as the recorder did.

The build never calls a model. It reads data/ai_runs/read/<photo>/<model>.json, validates the reply again with
agents/validate.py, refuses a record made with a prompt that no longer matches prompts/read.md and the field table, and
confirms each value against the photo's own recognized text with engine/confirm.py. The preview runs the stand-in on the
drawn plates in tests/fixtures/preview/ instead, labeled everywhere and never published.
"""
import json
from pathlib import Path

from agents import inputs, validate
from engine import confirm
from owner import stand_in

HERE = Path(__file__).resolve().parent.parent
RUNS = HERE.joinpath("data", "ai_runs", "read")
PREVIEW = HERE.joinpath("tests", "fixtures", "preview")


class Stale(Exception):
    pass


def base(preview=False):
    return PREVIEW if preview else HERE.joinpath("data")


def world(preview=False):
    """The key, the designs and the job, from the data or from the preview's fixtures."""
    b = base(preview)
    job = b.joinpath("job.json")
    return {"key": json.loads(b.joinpath("key", "key.json").read_text(encoding="utf-8")),
            "designs": json.loads(b.joinpath("designs.json").read_text(encoding="utf-8")),
            "job": json.loads(job.read_text(encoding="utf-8")) if job.exists() else None}


def ocr(photo, preview=False):
    return json.loads(base(preview).joinpath("ocr", f"{photo}.json").read_text(encoding="utf-8"))


def models(preview=False):
    """Every model with a recording, the stand-in apart. The preview has only the stand-in."""
    if preview:
        return [stand_in.MODEL]
    return sorted({p.stem for p in RUNS.glob("*/*.json")} - {stand_in.MODEL})


def load(photo, model, strict=True):
    path = RUNS.joinpath(photo, f"{model}.json")
    if not path.exists():
        return None
    rec = json.loads(path.read_text(encoding="utf-8"))
    if strict and rec.get("prompt_hash") != inputs.prompt_hash():
        raise Stale(f"{photo} {model} was recorded with an older prompt. Record it again.")
    return rec


def confirmed(reads, photo_ocr, fields_cfg):
    """Each read with its confirmation: the level, why, the box from the photo's text or the AI's own, and the text the
    photo holds there. A field the AI marked absent gets no level."""
    page = confirm.Photo(photo_ocr, fields_cfg)
    out = {}
    for fid, r in reads.items():
        c = confirm.confirm(page, fid, r) or {"level": None, "why": None, "box": None, "approx": False, "canon": None,
                                               "seen": None}
        out[fid] = dict(r, ai_box=r.get("box"), **c)
    return out


def views(model, preview=False, strict=True):
    """{photo: everything the page and the scores use for one model}. Photos with no recording are left out."""
    w, fields_cfg = world(preview), confirm.load_fields()
    out = {}
    for photo in sorted(w["key"]["photos"]):
        if preview:
            rec = {"reply": stand_in.reply(w["key"], photo, fields_cfg["fields"]), "label": stand_in.LABEL,
                   "date": None, "ms": 0, "meta": {"cost_usd": 0.0}, "repaired": False, "redacted": 0}
        else:
            rec = load(photo, model, strict)
            if rec is None:
                continue
        reads, held, problems = validate.read(rec["reply"], fields_cfg["fields"])
        out[photo] = {"reads": confirmed(reads, ocr(photo, preview), fields_cfg), "held": held, "problems": problems,
                      "cost_usd": (rec.get("meta") or {}).get("cost_usd") or 0.0, "ms": rec.get("ms") or 0,
                      "date": rec.get("date"), "label": rec.get("label"), "repaired": bool(rec.get("repaired")),
                      "redacted": rec.get("redacted") or 0,
                      "tokens_in": (rec.get("meta") or {}).get("input_tokens"),
                      "tokens_out": (rec.get("meta") or {}).get("output_tokens")}
    return out
