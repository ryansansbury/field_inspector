"""Check a read before anything uses it.

The reply has to be one JSON object with every field from config/fields.json under "fields", each with a known status,
a value only when read, a short label, and a box of four fractions. A reply that fails that shape gets one repair
request in the recorder, with the problems listed. A box that's inside out, empty or bigger than half the photo is
dropped and the read kept. A value that doesn't read as its field's kind (volts that hold no voltage, a refrigerant
with no R number) is held: kept in the record, shown as unreadable with the reason, and never confirmed or checked.
The build runs the same check on every record again. Standard library only.
"""
import json
import re

from engine import normalize as norm

STATUSES = ("read", "absent", "unreadable")
MAX_VALUE, MAX_LABEL = 40, 60


def parse(text):
    """The JSON object in a reply, allowing a code fence around it. Raises ValueError when there's none."""
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object")
    return json.loads(t[start:end + 1])


def box_of(b):
    """A box as four rounded fractions, or None when it isn't a sane one."""
    if not (isinstance(b, list) and len(b) == 4 and
            all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in b)):
        return None
    x0, y0, x1, y1 = [min(1.0, max(0.0, float(v))) for v in b]
    area = (x1 - x0) * (y1 - y0)
    if x1 <= x0 or y1 <= y0 or area < 1e-5 or area > 0.5:
        return None
    return [round(v, 4) for v in (x0, y0, x1, y1)]


def read(text, fields):
    """(reads, held, problems). Problems are shape problems that call for the repair request."""
    try:
        data = parse(text)
    except ValueError as e:
        return {}, [], [f"the reply isn't one JSON object ({e})"]
    got = data.get("fields") if isinstance(data, dict) else None
    if not isinstance(got, dict):
        return {}, [], ["the reply has no \"fields\" object"]
    kinds = {f["id"]: f["kind"] for f in fields}
    reads, held, problems = {}, [], [f"\"{fid}\" isn't one of the fields" for fid in got if fid not in kinds]
    for fid, kind in kinds.items():
        r = got.get(fid)
        if not isinstance(r, dict):
            problems.append(f"\"{fid}\" is missing")
            continue
        status, value, label = r.get("status"), r.get("value"), r.get("label")
        if status not in STATUSES:
            problems.append(f"\"{fid}\" has the status {status!r}")
            continue
        if (value is not None and not isinstance(value, str)) or (label is not None and not isinstance(label, str)):
            problems.append(f"\"{fid}\" has a value or a label that isn't text")
            continue
        if status == "read" and not (value or "").strip():
            problems.append(f"\"{fid}\" is read but has no value")
            continue
        clean = {"status": status, "value": None, "label": " ".join(label.split())[:MAX_LABEL] if label else None,
                 "box": box_of(r.get("box")) if status != "absent" else None}
        if status == "read":
            v = " ".join(value.split())
            why = ("too long for a plate value" if len(v) > MAX_VALUE else
                   None if norm.canon(kind, v) is not None else f"doesn't read as a {kind} value")
            if why:
                held.append({"field": fid, "value": v[:MAX_VALUE], "why": why})
                clean.update(status="unreadable", held=why)
            else:
                clean["value"] = v
        reads[fid] = clean
    return reads, held, problems
