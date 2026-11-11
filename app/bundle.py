"""The page's data: the job, its photos with their recognized words, each model's confirmed reads, the designs, the
rules and every word the script shows. It's written to site/data.js as window.FI, and the page reads nothing else.

The real build reads the masked photos, the recordings (validated and confirmed again by agents/replay.py) and the
scores, and copies only the job's photos into site/photos/. The preview builds from the drawn plates and the stand-in,
and the page labels it in red. Standard library only.
"""
import json
import shutil
from datetime import date
from pathlib import Path

from agents import replay
from app import names
from engine import rules

HERE = Path(__file__).resolve().parent.parent
SITE = HERE.joinpath("site")
KEEP = ("status", "value", "label", "level", "why", "box", "approx", "seen", "held")


def job_photos(job):
    out = []
    for a in job["assets"]:
        for p in [a["photo"]] + ([a["breaker_photo"]] if a.get("breaker_photo") else []):
            if p not in out:
                out.append(p)
    return out


def model_order(preview):
    if preview:
        return replay.models(preview=True)
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    have = replay.models()
    return [m for m in cfg["compare"] if m in have] + [m for m in have if m not in cfg["compare"]]


def labels(preview):
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    out = {m["id"]: {"label": m["label"], "vendor": m["vendor"]} for m in cfg["models"]}
    out["stand-in"] = {"label": "Stand-in (no model)", "vendor": "Preview"}
    return out


def route(preview, order):
    if preview:
        return order[0]
    path = HERE.joinpath("evals", "model_comparison.json")
    picked = json.loads(path.read_text(encoding="utf-8")).get("route") if path.exists() else None
    return picked if picked in order else order[0]


def photos(world, preview, wanted):
    out = {}
    for p in wanted:
        ocr = replay.ocr(p, preview)
        shot = world["key"]["photos"][p]["shot"]
        ext = "svg" if preview else "jpg"
        out[p] = {"src": f"photos/{p}.{ext}", "thumb": f"photos/{p}.{ext}" if preview else f"photos/thumbs/{p}.jpg",
                  "w": ocr["w"], "h": ocr["h"], "shot": shot,
                  "words": [[wd["text"]] + wd["box"] for line in ocr.get("lines") or [] for wd in line["words"]]}
    return out


def copy_photos(preview, wanted):
    """Only the job's photos go to the site. The folder is cleared first, so nothing from a preview stays behind."""
    dest = SITE.joinpath("photos")
    if dest.exists():
        shutil.rmtree(dest)
    dest.joinpath("thumbs").mkdir(parents=True)
    src = replay.base(preview).joinpath("photos")
    for p in wanted:
        if preview:
            shutil.copyfile(src.joinpath(f"{p}.svg"), dest.joinpath(f"{p}.svg"))
        else:
            shutil.copyfile(src.joinpath(f"{p}.jpg"), dest.joinpath(f"{p}.jpg"))
            shutil.copyfile(src.joinpath("thumbs", f"{p}.jpg"), dest.joinpath("thumbs", f"{p}.jpg"))


def build(w, preview=False):
    """Everything the page's script needs, as one dict."""
    world = replay.world(preview)
    job = world["job"]
    wanted = job_photos(job)
    order = model_order(preview)
    names_ = labels(preview)
    models = []
    for m in order:
        views = replay.views(m, preview=preview)
        reads = {p: {f: {k: r.get(k) for k in KEEP if r.get(k) is not None} for f, r in views[p]["reads"].items()}
                 for p in wanted if p in views}
        done = [views[p] for p in wanted if p in views]
        models.append({"id": m, "label": names_.get(m, {}).get("label", m), "vendor": names_.get(m, {}).get("vendor"),
                       "date": max((v["date"] or "" for v in done), default="") or None, "reads": reads,
                       "seconds": {p: round(views[p]["ms"] / 1000, 1) for p in wanted if p in views},
                       "cost": round(sum(v["cost_usd"] for v in done), 4)})
    cfg = rules.load_config()
    return {"preview": preview, "built": date.today().isoformat(), "cast": names.cast(preview=preview),
            "job": {"number": job.get("number"), "day": job.get("day"), "assets": job["assets"],
                    "designs": job["designs"]},
            "photos": photos(world, preview, wanted), "models": models, "route": route(preview, order),
            "cfg": cfg, "line": json.loads(HERE.joinpath("config", "rules.json").read_text(encoding="utf-8"))["line"],
            "fields": [f for f in cfg["kinds"]], "words": w.ui()}


def write(data, preview=False):
    wanted = job_photos({"assets": data["job"]["assets"]})
    copy_photos(preview, wanted)
    path = SITE.joinpath("data.js")
    path.write_text("window.FI = " + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + ";\n",
                    encoding="utf-8")
    return path.stat().st_size
