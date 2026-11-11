"""The installer's design rules, run on the reads: each asset's checks, its state, and what waits for a person.

The same code runs in the page as site/rules.js, so editing the design, moving the confidence line, and the person's
accept or correct all rerun these checks live, and the parity vectors prove the two agree on every case.

What goes in:
- the job: each asset with its photo (and the photo of the breaker that feeds it), and its design, which lists the
  checks that apply to it, written after the key;
- the reads: for each photo and field, the AI's status and value and the confirmation step's level;
- the person's decisions: accept or correct on a read, approved equal or wrong unit on a model one character off;
- the confidence line: which levels go to a person.

No verdict stands on a read that's waiting for a person. A failing check whose inputs are all settled turns its asset
red, anything uncertain keeps it blue, and the rest is green. Standard library only.
"""
import json
from pathlib import Path

from engine import normalize as norm

HERE = Path(__file__).resolve().parent.parent
SENT = {"missing": ("missing",), "partial": ("partial", "missing"), "all": ("found", "partial", "missing")}
NUMERIC = ("max_breaker", "mca", "breaker")


def load_config(rules_path=None, fields_path=None):
    rules = json.loads(Path(rules_path or HERE.joinpath("config", "rules.json")).read_text(encoding="utf-8"))
    fields = json.loads(Path(fields_path or HERE.joinpath("config", "fields.json")).read_text(encoding="utf-8"))
    return {"rules": {r["id"]: r for r in rules["rules"]}, "volt_classes": rules["volt_classes"],
            "kinds": {f["id"]: f["kind"] for f in fields["fields"]}}


def needed(design, cfg):
    """The plate fields this asset's checks read."""
    out = []
    for rule in design.get("checks") or []:
        if rule != "panel":
            optional = cfg["rules"][rule].get("optional") or ()
            out += [f for f in cfg["rules"][rule]["fields"] if f not in out and f not in optional]
    return out


def read_state(photo, field, reads, person, line, need):
    """(value, level, settled) for one read. A person's accept or correct settles it, except that a read the AI
    couldn't make out is only settled by a correction, since accepting it would say the plate doesn't print the value
    (changed 11/9). A read the AI marked absent counts as not found when a check needs it, so the person confirms the
    plate really doesn't print it."""
    r = (reads.get(photo) or {}).get(field) or {"status": "absent"}
    act = (person.get("reads") or {}).get(photo + "/" + field)
    if act and act.get("action") == "correct":
        return act.get("value"), "person", True
    if act and r.get("status") != "unreadable":
        return (r.get("value") if r.get("status") == "read" else None), "person", True
    if r.get("status") == "read" and r.get("value"):
        level = r.get("level") or "missing"
    elif r.get("status") == "unreadable" or need:
        level = "missing"
    else:
        return None, None, True
    value = r.get("value") if r.get("status") == "read" else None
    return value, level, level not in SENT[line]


def volts_fit(plate, design, classes):
    """Each design voltage needs a plate rating inside its class, so 208/230 fits a 240 V design and 115 fits 120."""
    ratings = [float(v) for v in plate.split("/")]
    for d in design.split("/"):
        lo_hi = classes.get(d) or [float(d), float(d)]
        if not any(lo_hi[0] <= r <= lo_hi[1] for r in ratings):
            return False
    return True


def check(rule, asset, design, reads, person, line, cfg):
    """One check's result: its status (pass, fail, review, unknown or skipped), why, its inputs and what it waits on."""
    kinds, photo = cfg["kinds"], asset["photo"]
    inputs, waits = [], []

    def plate(field, on=None, need=True):
        p = on or photo
        value, level, settled = read_state(p, field, reads, person, line, need)
        c = norm.canon(kinds[field], value) if value else None
        inputs.append({"from": "photo", "photo": p, "field": field, "value": c, "level": level})
        if not settled:
            waits.append(p + "/" + field)
        return c

    def want(field, kind):
        c = norm.canon(kind, design.get(field)) if design.get(field) else None
        inputs.append({"from": "design", "field": field, "value": c})
        return c

    def out(status, why):
        return {"rule": rule, "status": status, "why": why, "inputs": inputs, "waits": waits}

    if rule == "readable":
        got = [f for f, r in (reads.get(photo) or {}).items() if r.get("status") == "read" and r.get("value")]
        return out("pass", "read") if got else out("fail", "nothing_read")
    if rule == "panel":
        if not asset.get("breaker_photo"):
            return out("skipped", "no_breaker_photo")
        d, p = want("breaker", "amps"), plate("breaker", asset["breaker_photo"])
    elif rule == "volts":
        d, p = want("volts", "volts"), plate("volts")
        dp, pp = want("phase", "phase"), plate("phase", need=False)
        if p is None or d is None:
            return out("unknown", "no_read")
        if dp and pp and dp != pp:
            return out("fail", "phase")
        return out("pass", "fits") if volts_fit(p, d, cfg["volt_classes"]) else out("fail", "volts")
    elif rule in ("breaker_max", "breaker_min"):
        d = want("breaker", "amps")
        p = plate("max_breaker" if rule == "breaker_max" else "mca")
        if p is None or d is None:
            return out("unknown", "no_read")
        ok = float(d) <= float(p) if rule == "breaker_max" else float(d) >= float(p)
        return out("pass", "within") if ok else out("fail", "over" if rule == "breaker_max" else "under")
    else:
        d, p = want(rule, kinds[rule]), plate(rule)
    if p is None or d is None:
        act = (person.get("reads") or {}).get(photo + "/" + rule)
        blind = ((reads.get(photo) or {}).get(rule) or {}).get("status") == "unreadable"
        if act and act.get("action") == "accept" and p is None and not blind:
            return out("skipped", "absent_confirmed")
        return out("unknown", "no_read")
    if p == d:
        return out("pass", "equal")
    if rule == "model":
        approved = [norm.canon("code", a) for a in design.get("approved") or []]
        if p in approved:
            return out("pass", "approved")
        decided = (person.get("checks") or {}).get(asset["id"] + "/model")
        if decided == "approved":
            return out("pass", "approved_by_person")
        if decided == "wrong_unit":
            return out("fail", "wrong_unit")
        if norm.distance(p, d) == 1:
            return out("review", "one_off")
    return out("fail", "differs")


def evaluate(job, reads, person, line, cfg):
    """Every asset's checks and state, the person's queue, and the counts in the header."""
    person = person or {}
    assets, queue = {}, []
    counts = {"pass": 0, "fail": 0, "person": 0, "reads": 0, "sent": 0}
    for asset in job["assets"]:
        design = job["designs"][asset["id"]]
        checks = [check(rule, asset, design, reads, person, line, cfg) for rule in design.get("checks") or []]
        need = needed(design, cfg)
        queued = []
        photos = [asset["photo"]] + ([asset["breaker_photo"]] if asset.get("breaker_photo") else [])
        for p in photos:
            fields = sorted(set((reads.get(p) or {}).keys()) | set(need if p == asset["photo"] else ["breaker"]))
            for field in fields:
                value, level, settled = read_state(p, field, reads, person, line,
                                                   field in need if p == asset["photo"] else field == "breaker")
                if level is None:
                    continue
                counts["reads"] += 1
                if not settled:
                    counts["sent"] += 1
                    queued.append(p + "/" + field)
                    queue.append({"type": "read", "asset": asset["id"], "photo": p, "field": field, "level": level})
        for c in checks:
            if c["status"] == "review":
                queue.append({"type": "check", "asset": asset["id"], "rule": c["rule"]})
        if any(c["status"] == "fail" and not c["waits"] for c in checks):
            state = "fail"
        elif queued or any(c["status"] in ("review", "unknown") or c["waits"] for c in checks):
            state = "person"
        else:
            state = "pass"
        counts[state] += 1
        assets[asset["id"]] = {"state": state, "checks": checks, "queued": queued}
    return {"assets": assets, "queue": queue, "counts": counts}
