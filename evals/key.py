"""The answer key, built from what a person confirmed on the verification page (data/key_draft.json).

    python3 evals/key.py            build data/key/key.json and draw the split
    python3 evals/key.py --check    list anything in the draft that won't build, and build nothing

No model ever touches the key. The text recognition drafted each value from the photo and a person confirmed or corrected
every one. This script checks each value against its field's format, groups the shots of each plate by the name the
person gave it, stops if two shots of one plate disagree on a value, and stops if a plate's name holds a word from under the
masks, since plates are named by what they are and never by their maker.

The split is drawn by plate with a fixed seed and fixed rules before any model runs, so it can't be picked by how hard
the photos are. Dev takes one plate that prints both a minimum circuit ampacity and a largest breaker (never the one
with the lowest largest breaker, which the job's cross-photo check needs most), one breaker close-up (never the
highest rated), and up to three more plates at random, as long as eight or more plates stay in test for the job.
Test holds the rest. Standard library only.
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import confirm, normalize as norm, privacy  # noqa: E402

DRAFT = HERE.joinpath("data", "key_draft.json")
KEY = HERE.joinpath("data", "key", "key.json")
SEED = 11
JOB_PLATES = 8


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def build(draft, fields, private=()):
    """(key, problems). The key holds every photo a person confirmed, with every field's value or null."""
    kinds = {f["id"]: f["kind"] for f in fields["fields"]}
    photos, plates, dropped, problems = {}, {}, {}, []
    pat = re.compile("|".join(re.escape(w) for w in private), re.I) if private else None
    for pid, s in sorted(draft.get("photos", {}).items()):
        if s.get("status") == "dropped":
            dropped[pid] = s.get("dropped_why") or "dropped"
            continue
        if s.get("status") != "done":
            problems.append(f"{pid} isn't confirmed yet")
            continue
        name = " ".join((s.get("plate") or "").split())
        if not name:
            problems.append(f"{pid} has no plate name")
            continue
        if pat and pat.search(name):
            problems.append(f"{pid}'s plate name holds a word from under the masks, so name it by what it is")
        values = {}
        for fid, kind in kinds.items():
            v = (s.get("fields") or {}).get(fid)
            if v is None:
                values[fid] = None
                continue
            c = norm.canon(kind, v.get("value"))
            if c is None:
                problems.append(f"{pid} {fid} \"{v.get('value')}\" doesn't read as a {kind} value")
                continue
            values[fid] = {"value": v["value"], "canon": c, **({"box": v["box"]} if v.get("box") else {})}
        plate = slug(name)
        photos[pid] = {"plate": plate, "kind": s.get("kind") or "other", "shot": s.get("shot"), "fields": values}
        p = plates.setdefault(plate, {"name": name, "kind": s.get("kind") or "other", "photos": []})
        p["photos"].append(pid)
    for plate, p in plates.items():
        for fid in kinds:
            seen = {photos[pid]["fields"].get(fid)["canon"] for pid in p["photos"] if photos[pid]["fields"].get(fid)}
            if len(seen) > 1:
                problems.append(f"the shots of {p['name']} disagree on {fid}: {', '.join(sorted(seen))}")
    return {"made_from": "data/key_draft.json", "confirmed_by": draft.get("confirmed_by", "a person"), "seed": SEED,
            "photos": photos, "plates": plates, "dropped": dropped}, problems


def plate_facts(key):
    """Per plate: whether it prints a minimum circuit ampacity and a largest breaker, its largest breaker, and a
    breaker close-up's rating."""
    facts = {}
    for name, p in key["plates"].items():
        vals = {}
        for pid in p["photos"]:
            for fid, v in key["photos"][pid]["fields"].items():
                if v:
                    vals[fid] = float(v["canon"]) if fid in ("mca", "max_breaker", "breaker") else v["canon"]
        facts[name] = {"kind": p["kind"], "mca": vals.get("mca"), "max": vals.get("max_breaker"),
                       "rating": vals.get("breaker"), "breaker": p["kind"] == "breaker" or "breaker" in vals}
    return facts


def draw_split(key, seed=SEED):
    """{plate: "dev" or "test"} by the fixed rules in the docstring."""
    rng = random.Random(seed)
    facts = plate_facts(key)
    names = sorted(facts)
    hvac = [n for n in names if facts[n]["mca"] is not None and facts[n]["max"] is not None]
    breakers = [n for n in names if facts[n]["breaker"]]
    dev = []
    if len(hvac) >= 2:
        keep = min(hvac, key=lambda n: (facts[n]["max"], n))
        dev.append(rng.choice([n for n in hvac if n != keep]))
    if len(breakers) >= 2:
        top = max(breakers, key=lambda n: (facts[n]["rating"] or 0, n))
        dev.append(rng.choice([n for n in breakers if n != top]))
    rest = [n for n in names if n not in hvac and n not in breakers]
    room = len([n for n in names if n not in breakers and n not in dev]) - JOB_PLATES
    dev += rng.sample(rest, max(0, min(3, room, len(rest))))
    return {n: ("dev" if n in dev else "test") for n in names}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    if not DRAFT.exists():
        raise SystemExit("No data/key_draft.json yet. The verification page writes it.")
    key, problems = build(json.loads(DRAFT.read_text(encoding="utf-8")), confirm.load_fields(),
                          privacy.private_words(HERE) or ())
    for line in problems:
        print("  " + line)
    if problems:
        raise SystemExit(f"{len(problems)} problems in the draft. Fix them on the verification page.")
    split = draw_split(key)
    for name, p in key["plates"].items():
        p["split"] = split[name]
        for pid in p["photos"]:
            key["photos"][pid]["split"] = split[name]
    if a.check:
        print(f"The draft builds: {len(key['photos'])} photos of {len(key['plates'])} plates.")
        return 0
    KEY.parent.mkdir(parents=True, exist_ok=True)
    KEY.write_text(json.dumps(key, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    n_dev = sum(1 for p in key["photos"].values() if p["split"] == "dev")
    print(f"Wrote data/key/key.json: {len(key['photos'])} photos of {len(key['plates'])} plates, {n_dev} photos in dev "
          f"and {len(key['photos']) - n_dev} in test, {len(key['dropped'])} dropped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
