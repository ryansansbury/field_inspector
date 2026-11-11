"""Freeze the photos and the key, then the job and its design, then the prompt and the scoring code, so nothing scored
is tuned after the fact.

    python3 evals/freeze.py photos      the masked photos, their masking log, their recognized text and the key
    python3 evals/freeze.py designs     the job, the designs, the rules and the code that runs them
    python3 evals/freeze.py prompts     after the dev round: the read prompt, the field schema, normalizing, the
                                        confirmation step, the reply check and the scorer
    python3 evals/freeze.py --check     list anything changed since it was frozen, and exit 1 if so

Each stage writes its hashes into evals/frozen.json once. Freezing a stage again needs --again, and the old hashes move
to "history" with the time, so a change after the fact shows. The recorder refuses every real model run until the
photos and the designs are frozen, and the test photos until the prompts are. The build checks before it shows a score.
Adapted from the Call Companion's freeze, with every stage a set of files. Standard library only.
"""
import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent.parent
FROZEN = "evals/frozen.json"
STAGES = {
    "photos": ["data/photos/*.jpg", "data/photos/thumbs/*.jpg", "data/photos/manifest.json", "data/ocr/*.json",
               "data/key/*.json"],
    "designs": ["data/job.json", "data/designs.json", "config/rules.json", "engine/rules.py"],
    "prompts": ["prompts/read.md", "config/fields.json", "engine/normalize.py", "engine/confirm.py",
                "agents/validate.py", "evals/score.py"],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def files(stage, root=HERE):
    out = {}
    for pattern in STAGES[stage]:
        for p in sorted(Path(root).glob(pattern)):
            out[p.relative_to(root).as_posix()] = sha(p)
    return out


def load(root=HERE):
    path = Path(root).joinpath(FROZEN)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def now():
    return datetime.now(ZoneInfo("America/Los_Angeles")).isoformat(timespec="seconds")


def freeze(stage, again=False, root=HERE):
    data = load(root)
    if stage in data and not again:
        raise SystemExit(f"{stage} is already frozen at {data['at'][stage]}. Use --again to refreeze, and the old "
                         f"hashes go to history.")
    current = files(stage, root)
    if not current:
        raise SystemExit(f"Nothing to freeze for {stage} yet.")
    if stage in data:
        data.setdefault("history", []).append({"stage": stage, "at": data["at"][stage], "replaced": now(),
                                               "hashes": data[stage]})
    data[stage] = current
    data.setdefault("at", {})[stage] = now()
    Path(root).joinpath(FROZEN).write_text(json.dumps(data, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return data


def changed(stage, root=HERE):
    """[(path, why)] since the stage was frozen, or None when it isn't frozen."""
    data = load(root)
    if stage not in data:
        return None
    then, current = data[stage], files(stage, root)
    out = []
    for name in sorted(set(then) | set(current)):
        if name not in current:
            out.append((name, "removed"))
        elif name not in then:
            out.append((name, "added"))
        elif then[name] != current[name]:
            out.append((name, "changed"))
    return out


def ready(stage, root=HERE):
    c = changed(stage, root)
    return c is not None and not c


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", nargs="?", choices=list(STAGES))
    ap.add_argument("--again", action="store_true")
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if a.check or not a.stage:
        bad = False
        for stage in STAGES:
            c = changed(stage)
            if c is None:
                print(f"{stage}: not frozen yet")
                continue
            print(f"{stage}: frozen {load()['at'][stage]}, {'unchanged' if not c else f'{len(c)} changed'}")
            for name, why in c:
                print(f"  {why}: {name}")
                bad = True
        return 1 if bad else 0
    data = freeze(a.stage, a.again)
    print(f"Froze {a.stage} at {data['at'][a.stage]}: {len(data[a.stage])} files in {FROZEN}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
