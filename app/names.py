"""The cast, from config/names.json, written after the names check.

Three names: the installer (a company) and the technician and the reviewer (people). Each entry can be
a plain string or an object with a "name" field. Until the file lands, the preview shows a bracketed token for each
name and the real build refuses to run, so no invented name ever reaches anything tracked.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
PATH = HERE.joinpath("config", "names.json")
ROLES = ("installer", "technician", "reviewer")
PEOPLE = ("technician", "reviewer")


class Pending(SystemExit):
    pass


def load(path=None):
    """{role: name}, or None when the file isn't here yet."""
    path = Path(path or PATH)
    if not path.exists():
        return None
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    for role in ROLES:
        value = raw.get(role)
        if isinstance(value, dict):
            value = value.get("name")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"config/names.json has no {role}")
        out[role] = " ".join(value.split())
    return out


def pending():
    return {role: f"[{role}]" for role in ROLES}


def cast(preview=False, path=None):
    """The names the page uses. The preview may run on the bracketed tokens, and the real build may not."""
    got = load(path)
    if got:
        return got
    if preview:
        return pending()
    raise Pending("config/names.json isn't here yet. The names check writes it, and until then only the preview "
                  "builds.")
