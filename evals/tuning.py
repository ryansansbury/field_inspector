"""The tuning log: one line per dev round of the default model, and the freeze once a revision holds up.

    python3 evals/tuning.py              add the latest dev round to evals/tuning_rounds.json
    python3 evals/tuning.py --freeze     the same, then freeze the prompt if this round did no worse than the best before

At most two rounds run on dev, and the test photos stay unread until the prompt freezes. A round that did worse stops
for a decision on what to freeze, and docs/DECISIONS.md says why. Standard library only.
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from agents import inputs  # noqa: E402
from evals import freeze, score  # noqa: E402

LOG = HERE.joinpath("evals", "tuning_rounds.json")


def latest():
    cfg = json.loads(HERE.joinpath("config", "models.json").read_text(encoding="utf-8"))
    dev = json.loads(HERE.joinpath("evals", "scores.json").read_text(encoding="utf-8"))["models"][cfg["default"]]["dev"]
    return {"date": date.today().isoformat(), "model": cfg["default"], "prompt": inputs.prompt_hash(),
            "accuracy": dev["fields"]["accuracy"], "past_line": dev["line"][score.DEFAULT_LINE]["past"],
            "missed_verdicts": dev["checks"]["missed"], "person_share": dev["line"][score.DEFAULT_LINE]["share"]}


def better_or_equal(new, rounds):
    best = max(rounds, key=lambda r: (r["accuracy"] or 0, -r["past_line"]))
    return (new["accuracy"] or 0) >= (best["accuracy"] or 0) and new["past_line"] <= best["past_line"]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--freeze", action="store_true")
    a = ap.parse_args(argv)
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"rounds": []}
    new = latest()
    before = [r for r in log["rounds"] if r["prompt"] != new["prompt"]]
    log["rounds"] = before + [dict(new, round=len(before) + 1)]
    LOG.write_text(json.dumps(log, indent=1) + "\n", encoding="utf-8")
    print(f"Dev round {len(before) + 1}: accuracy {new['accuracy']}, {new['past_line']} past the line, "
          f"{new['missed_verdicts']} missed verdicts.")
    if not a.freeze:
        return 0
    if before and not better_or_equal(new, before):
        raise SystemExit("The revised prompt did worse on dev than the best round before it. Decide what to freeze before running again.")
    freeze.freeze("prompts", again="prompts" in freeze.load())
    print("Froze the prompt and the scoring code.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
