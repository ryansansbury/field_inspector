"""Compare the models and pick the route: accuracy, errors past the line, missed verdicts, the person's load, and cost
and time per photo.

    python3 evals/compare.py        into evals/model_comparison.json (the real build runs it after the scores)

Everything comes from evals/scores.json. Cost is what the recorded reads cost at list prices, and the figure per
thousand photos is that times a thousand, labeled as an estimate. The route is the cheapest model that clears every bar
on dev, or the most accurate on dev when none does. The page opens on it.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from evals import score  # noqa: E402


def compare(scores, cfg):
    by_id = {m["id"]: m for m in cfg["models"]}
    rows = []
    for model, splits in scores["models"].items():
        main = splits.get("test") or splits.get("dev")
        dev = splits.get("dev")
        if not main:
            continue
        line = main["line"][score.DEFAULT_LINE]
        rows.append({
            "model": model, "label": by_id.get(model, {}).get("label", model),
            "vendor": by_id.get(model, {}).get("vendor"),
            "accuracy": {s: v["fields"]["accuracy"] for s, v in splits.items()},
            "past_line": line["past"], "person_share": line["share"], "caught": line["caught"],
            "missed_verdicts": main["checks"]["missed"],
            "cost_per_photo": main["cost_per_photo"], "seconds_per_photo": main["seconds_per_photo"],
            "per_thousand_estimate": round(main["cost_per_photo"] * 1000, 2) if main["cost_per_photo"] is not None
            else None,
            "clears": {s: all(v["bars"].values()) for s, v in splits.items()},
            "clears_dev": bool(dev and all(dev["bars"].values())),
        })
    clears = [r for r in rows if r["clears_dev"]]
    if clears:
        route = min(clears, key=lambda r: (r["cost_per_photo"] or 0, -(r["accuracy"].get("dev") or 0)))["model"]
        why = "cheapest_clearing"
    else:
        route = max(rows, key=lambda r: r["accuracy"].get("dev") or 0)["model"] if rows else cfg.get("default")
        why = "most_accurate_on_dev"
    return {"rows": rows, "route": route, "route_reason": why, "bars": scores.get("bars")}


def main():
    scores = json.loads(HERE.joinpath("evals", "scores.json").read_text(encoding="utf-8"))
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    out = compare(scores, cfg)
    HERE.joinpath("evals", "model_comparison.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(f"Route: {out['route']} ({out['route_reason']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
