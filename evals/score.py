"""Score every recorded model against the answer key: the fields, the errors that got past the line, the person's load,
the checks, and cost and time per photo.

    python3 evals/score.py              every recorded model, into evals/scores.json (the real build runs it)
    python3 evals/score.py --preview    the stand-in on the preview, into evals/preview_scores.json, which proves
                                        only the wiring and never reaches the page

Each field on each photo is one of five things. Correct is the key's value read right after normalizing, wrong is a
different value, a miss is a printed value the AI left empty or couldn't read, a false read is a value the plate
doesn't print, and right-empty is an empty answer where the plate prints nothing (reported apart, since it's easy).
Accuracy is correct over the values the key holds.

The dangerous errors are wrong and false reads the confirmation step marked well enough that the line didn't send
them to a person, so they're counted on their own at each position of the line. The person's load is the share of
reads sent to a person at each position against the wrong reads it caught. For the checks, each verdict from the AI's
reads is compared with the verdict from the key's values, and a disagreement counts as caught only when the check
waited for a person. The bars are set in config/models.json before any read. Standard library only.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import normalize as norm, rules  # noqa: E402

POSITIONS = ("missing", "partial", "all")
DEFAULT_LINE = "partial"


def outcome(kind, key_value, read):
    """correct, wrong, miss, false or right_empty for one field of one photo."""
    k = key_value["canon"] if key_value else None
    a = None
    if read and read.get("status") == "read" and read.get("value"):
        a = norm.canon(kind, read["value"]) or ("\x00unparsed:" + str(read["value"]))
    if k and a:
        return "correct" if a == k else "wrong"
    if k:
        return "miss"
    return "false" if a else "right_empty"


def tally(rows):
    out = {"key": 0, "correct": 0, "wrong": 0, "miss": 0, "false": 0, "right_empty": 0}
    for r in rows:
        out[r] += 1
        out["key"] += r in ("correct", "wrong", "miss")
    out["accuracy"] = round(out["correct"] / out["key"], 3) if out["key"] else None
    return out


def key_reads(key, photo):
    return {f: {"status": "read", "value": v["value"], "level": "found"}
            for f, v in key["photos"][photo]["fields"].items() if v}


def photo_job(photo, plate, designs):
    return {"assets": [{"id": photo, "photo": photo}], "designs": {photo: designs["plates"][plate]}}


def check_agreement(jobs, ai_reads, truth_reads, cfg):
    """How each check's verdict from the AI's reads compares with the verdict from the key."""
    out = {"total": 0, "agree": 0, "caught": 0, "missed": 0, "missed_list": []}
    for job in jobs:
        ai = rules.evaluate(job, ai_reads, {}, DEFAULT_LINE, cfg)
        truth = rules.evaluate(job, truth_reads, {}, DEFAULT_LINE, cfg)
        for asset_id, a in ai["assets"].items():
            for got, want in zip(a["checks"], truth["assets"][asset_id]["checks"]):
                out["total"] += 1
                if got["status"] == want["status"]:
                    out["agree"] += 1
                elif got["waits"] or got["status"] in ("review", "unknown"):
                    out["caught"] += 1
                else:
                    out["missed"] += 1
                    out["missed_list"].append({"asset": asset_id, "rule": got["rule"], "ai": got["status"],
                                               "key": want["status"]})
    return out


def score_split(photos, key, designs, job, view, cfg, bars):
    """Every number for one model on one split. view is {photo: {"reads": {field: read with level}, "cost_usd",
    "ms"}} from agents/replay.py."""
    kinds = cfg["kinds"]
    rows, by_field, by_shot = [], {}, {}
    levels = {lv: {"reads": 0, "wrong": 0} for lv in ("found", "partial", "missing")}
    wrong_at = []
    for p in photos:
        reads = (view.get(p) or {}).get("reads") or {}
        shot = key["photos"][p]["shot"]
        for f, kind in kinds.items():
            r = reads.get(f)
            o = outcome(kind, key["photos"][p]["fields"].get(f), r)
            rows.append(o)
            by_field.setdefault(f, []).append(o)
            by_shot.setdefault(shot, []).append(o)
            if r and r.get("status") in ("read", "unreadable"):
                lv = (r.get("level") or "missing") if r.get("status") == "read" else "missing"
                levels[lv]["reads"] += 1
                if o in ("wrong", "false"):
                    levels[lv]["wrong"] += 1
                    wrong_at.append(lv)
    total = sum(v["reads"] for v in levels.values())
    line = {}
    for pos in POSITIONS:
        sent = sum(levels[lv]["reads"] for lv in rules.SENT[pos])
        caught = sum(1 for lv in wrong_at if lv in rules.SENT[pos])
        line[pos] = {"sent": sent, "share": round(sent / total, 3) if total else None, "caught": caught,
                     "past": len(wrong_at) - caught}
    ai_reads = {p: (view.get(p) or {}).get("reads") or {} for p in photos}
    truth = {p: key_reads(key, p) for p in photos}
    jobs = [photo_job(p, key["photos"][p]["plate"], designs) for p in photos if key["photos"][p]["plate"] in
            designs["plates"]]
    if job is not None:
        jobs = [job]
        for a in job["assets"]:
            for p in [a["photo"]] + ([a["breaker_photo"]] if a.get("breaker_photo") else []):
                ai_reads[p] = (view.get(p) or {}).get("reads") or {}
                truth[p] = key_reads(key, p)
    checks = check_agreement(jobs, ai_reads, truth, cfg)
    done = [view[p] for p in photos if p in view]
    fields = tally(rows)
    out = {"photos": len(photos), "recorded": len(done), "fields": fields,
           "by_field": {f: tally(v) for f, v in sorted(by_field.items())},
           "by_shot": {s: tally(v) for s, v in sorted(by_shot.items())},
           "levels": levels, "line": line, "checks": checks,
           "cost_per_photo": round(sum(v.get("cost_usd") or 0 for v in done) / len(done), 5) if done else None,
           "seconds_per_photo": round(sum(v.get("ms") or 0 for v in done) / len(done) / 1000, 1) if done else None}
    out["bars"] = {"accuracy": fields["accuracy"] is not None and fields["accuracy"] >= bars["accuracy"],
                   "past_line": line[DEFAULT_LINE]["past"] <= bars["past_line"],
                   "decisions": checks["missed"] <= bars["missed_decisions"]}
    return out


def score(key, designs, job, views, cfg, bars):
    """{model: {split: numbers}}, with the job scored on its own as well as inside test."""
    splits = {s: sorted(p for p, v in key["photos"].items() if v["split"] == s) for s in ("dev", "test")}
    job_photos = sorted({p for a in job["assets"] for p in [a["photo"]] + ([a["breaker_photo"]] if a.get(
        "breaker_photo") else [])}) if job else []
    out = {}
    for model, view in views.items():
        out[model] = {s: score_split(ps, key, designs, None, view, cfg, bars) for s, ps in splits.items() if ps}
        if job_photos:
            out[model]["job"] = score_split(job_photos, key, designs, job, view, cfg, bars)
    return out


def bars_from(models_cfg):
    b = models_cfg.get("bars") or {}
    return {"accuracy": b.get("accuracy", 0.9), "past_line": b.get("past_line", 0),
            "missed_decisions": b.get("missed_decisions", 0)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", action="store_true")
    a = ap.parse_args(argv)
    from agents import replay
    data = replay.world(preview=a.preview)
    cfg = rules.load_config()
    models_cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    bars = bars_from(models_cfg)
    views = {m: replay.views(m, preview=a.preview) for m in replay.models(preview=a.preview)}
    out = {"bars": bars, "line_default": DEFAULT_LINE, "preview": a.preview,
           "models": score(data["key"], data["designs"], data["job"], views, cfg, bars)}
    path = HERE.joinpath("evals", "preview_scores.json" if a.preview else "scores.json")
    path.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for model, splits in out["models"].items():
        print(f"  {model}: " + ", ".join(f"{s} {v['fields']['accuracy']} accuracy, {v['line'][DEFAULT_LINE]['past']} "
                                         f"past the line, {v['checks']['missed']} missed verdicts"
                                         for s, v in splits.items()))
    print(f"Wrote {path.relative_to(HERE)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
