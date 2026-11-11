"""Write tests/vectors/rules.json: the cases the Python and JavaScript normalizers and rules must agree on.

    python3 tests/make_vectors.py

Normalizing: every case in tests/test_normalize.py, a spread of printed values for each kind, and 300 seeded strings
that run values of different kinds together. Rules: the mini job at each position of the line, the heat pump's breaker
at, under and over both limits, and 200 seeded random edits to the design, the reads, the person's decisions and the
line. tests/js/check_rules.js runs the page's files on the same cases. Phase 4 adds the real job's cases.
"""
import copy
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import normalize as norm, rules  # noqa: E402
from tests.helpers import mini_job  # noqa: E402
from tests.test_normalize import CASES  # noqa: E402

SEED = 7
PRINTED = {
    "code": ["HPX-36B2", "hpx 36 b2", "DW-24P0", "DW-24PO", "EWH-50T2", " -/ ", "X", "M/N 12-AB", "Ø1", "ß-9", "МCА",
             "СА13-24А1", "ΑΒ-12", "CA13-24AíŚ"],
    "volts": ["208/230", "208-230V", "230/208", "115V~", "120/240", "120 VAC 60 HZ", "200A", "60Hz", "277", "480V",
              "1,200 V", "120.0", "90", "601", "220-240", "12V", "208/230-1-60"],
    "phase": ["1", "1PH", "1Ø", "3", "3PH", "single phase", "THREE PHASE", "1-3", "230", "208/230-1-60", "ph 1", "13"],
    "amps": ["18.6", "18.60 A", "25A", ".5", "012.0", "14.1 / 82", "none", "1,250", "0", "30 A", "7.5A", "12."],
    "capacity": ["50 GAL", "4500W", "60,000 BTU/H", "60 MBH", "189 L 50 GAL", "1.5 TONS", "1,440 WATTS", "50", "7 LB",
                 "0.5 KW", "40 gallons", "12.2 kw", "3 TON", "0.75 W", "BTU/HR 40000"],
    "refrigerant": ["R-454B", "r410a", "HFC-134a", "R-454B·7 LB", "REFRIGERANT", "R1234yf", "R 32", "R-22", "HCFC-22",
                    "R600a"],
}
SEPARATORS = (" ", "-", "/", ", ", "", "·", "~ ")
BREAKERS = ("25", "24.9", "25.1", "18.6", "18.5", "30", "", "abc", "25 A", "0")


def normalize_cases(rng):
    out = [{"kind": k, "text": t, "want": norm.canon(k, t)} for k, t, _ in CASES]
    out += [{"kind": k, "text": t, "want": norm.canon(k, t)} for k, texts in PRINTED.items() for t in texts]
    pool = [t for texts in PRINTED.values() for t in texts]
    for _ in range(300):
        text = rng.choice(SEPARATORS).join(rng.choice(pool) for _ in range(rng.randint(1, 3)))
        kind = rng.choice(norm.KINDS)
        out.append({"kind": kind, "text": text, "want": norm.canon(kind, text)})
    return out


def edit(rng, job, reads):
    d = job["designs"]
    d["heat-pump"]["breaker"] = rng.choice(BREAKERS)
    d["dishwasher"]["model"] = rng.choice(["DW-24P1", "DW-24P7", "DW-24PO", "dw24p7", "XX-1", ""])
    d["dishwasher"]["approved"] = rng.choice([[], ["DW-24P7"], ["dw 24 p7", "XX-1"]])
    d["water-heater"]["capacity"] = rng.choice(["40 GAL", "50 gal", "50 GALLONS", "4.5 kW", "", "50"])
    for asset in ("heat-pump", "dishwasher", "water-heater", "dryer"):
        if rng.random() < 0.3:
            d[asset]["volts"] = rng.choice(["240", "120", "208", "120/240", "277", ""])
        if rng.random() < 0.2:
            d[asset]["phase"] = rng.choice(["1", "3", ""])
    for photo, fields in reads.items():
        for field in list(fields):
            roll = rng.random()
            if roll < 0.2:
                fields[field] = dict(fields[field], level=rng.choice(["found", "partial", "missing"]))
            elif roll < 0.25:
                fields[field] = {"status": "unreadable"}
            elif roll < 0.3:
                fields[field] = {"status": "absent"}
            elif roll < 0.35 and fields[field].get("status") == "read":
                kind = rules.load_config()["kinds"][field]
                pool = PRINTED["amps" if kind == "amps" else kind]
                fields[field] = dict(fields[field], value=rng.choice(pool))
    person = {"reads": {}, "checks": {}}
    for photo, fields in reads.items():
        for field in fields:
            if rng.random() < 0.12:
                person["reads"][f"{photo}/{field}"] = rng.choice(
                    [{"action": "accept"}, {"action": "correct", "value": rng.choice(["25", "30A", "DW-24P1", "x", ""])}])
    if rng.random() < 0.3:
        person["checks"]["dishwasher/model"] = rng.choice(["approved", "wrong_unit"])
    return person


def rule_cases(rng, cfg):
    out = []
    job, reads = mini_job()
    for line in ("missing", "partial", "all"):
        out.append({"job": job, "reads": reads, "person": {}, "line": line})
    for breaker in BREAKERS:
        j = copy.deepcopy(job)
        j["designs"]["heat-pump"]["breaker"] = breaker
        out.append({"job": j, "reads": reads, "person": {}, "line": "partial"})
    for _ in range(200):
        j, r = copy.deepcopy(job), copy.deepcopy(reads)
        person = edit(rng, j, r)
        out.append({"job": j, "reads": r, "person": person, "line": rng.choice(("missing", "partial", "all"))})
    for case in out:
        case["want"] = rules.evaluate(case["job"], case["reads"], case["person"], case["line"], cfg)
    return out


def preview_cases(rng, cfg):
    """The preview job with the stand-in's confirmed reads: each line position, then 100 seeded random design edits
    and person decisions on the page's own data shapes."""
    from agents import replay
    views = replay.views("stand-in", preview=True)
    reads = {p: {f: {k: r[k] for k in ("status", "value", "level") if r.get(k) is not None} for f, r in v["reads"].items()}
             for p, v in views.items()}
    job = replay.world(preview=True)["job"]
    job = {"assets": job["assets"], "designs": job["designs"]}
    out = [{"job": job, "reads": reads, "person": {}, "line": line} for line in ("missing", "partial", "all")]
    keys = [(p, f) for p, fs in reads.items() for f in fs]
    for _ in range(100):
        j, r = copy.deepcopy(job), copy.deepcopy(reads)
        for a, d in j["designs"].items():
            for field_ in ("breaker", "capacity", "model", "volts"):
                if field_ in d and rng.random() < 0.25:
                    d[field_] = rng.choice(["25", "30 A", "15", "50 GAL", "40 gal", "12.2 kw", "HPX-36B2", "DW-24P7",
                                            "120/240", "240", "208", ""])
        person = {"reads": {}, "checks": {}}
        for p, f in rng.sample(keys, 3):
            person["reads"][f"{p}/{f}"] = rng.choice([{"action": "accept"}, {"action": "correct", "value": "30"}])
        if rng.random() < 0.4:
            person["checks"]["dishwasher/model"] = rng.choice(["approved", "wrong_unit"])
        out.append({"job": j, "reads": r, "person": person, "line": rng.choice(("missing", "partial", "all"))})
    for case in out:
        case["want"] = rules.evaluate(case["job"], case["reads"], case["person"], case["line"], cfg)
    return out


def main():
    rng = random.Random(SEED)
    cfg = rules.load_config()
    pool = sorted({c["want"] for c in normalize_cases(random.Random(SEED)) if c["want"]})
    out = {"cfg": cfg, "normalize": normalize_cases(rng),
           "distance": [{"a": a, "b": b, "want": norm.distance(a, b)} for a in pool[:20] for b in pool[:20]],
           "rules": rule_cases(rng, cfg) + preview_cases(random.Random(SEED + 1), cfg)}
    path = HERE.joinpath("tests", "vectors", "rules.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"Wrote {len(out['normalize'])} normalizing cases, {len(out['distance'])} distances and "
          f"{len(out['rules'])} rules cases to tests/vectors/rules.json")


if __name__ == "__main__":
    main()
