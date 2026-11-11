"""The owner's machine only. The verification page: a person confirms every value the draft read found, marks what
each plate doesn't print, sets the masks, tags the shots and names the plates.

    bash owner/verify.sh        (from the build folder) starts it on 127.0.0.1 at a free port and opens the browser

It serves the unmasked copies and the draft read, which never leave this Mac, and saves every change to
data/key_draft.json as it happens: the values, the tags and the mask boxes, never the text under a mask. It answers only
requests addressed to its own 127.0.0.1 address. Control-C stops it. Standard library only.
"""
import http.server
import json
import re
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))

from engine import confirm  # noqa: E402

PAGE = HERE.joinpath("owner", "verify")
UNMASKED, DRAFT = HERE.joinpath("data", "unmasked"), HERE.joinpath("data", "ocr_draft")
KEY_DRAFT = HERE.joinpath("data", "key_draft.json")
STATUSES = ("open", "done", "dropped")
SHOTS = ("straight", "angled", "glare", "low light")
KINDS = ("heat pump", "condenser", "air handler", "furnace", "water heater", "panel", "breaker", "range", "dryer",
         "washer", "dishwasher", "refrigerator", "microwave", "garage door opener", "charger", "other")
LIMIT = 2_000_000
FILES = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"),
         "/verify.js": ("verify.js", "text/javascript; charset=utf-8"), "/verify.css": ("verify.css", "text/css")}


def ids():
    return sorted(p.stem for p in UNMASKED.glob("p*.jpg"))


def state():
    """Everything the page starts from: the fields, the choices, each photo's draft and anything saved before."""
    fields = confirm.load_fields()
    drafts = {}
    for pid in ids():
        path = DRAFT.joinpath(f"{pid}.json")
        d = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        drafts[pid] = {"w": d.get("w"), "h": d.get("h"), "draft": d.get("draft") or {}, "masks": d.get("masks") or [],
                       "people": len(d.get("faces") or []) + len(d.get("people") or []),
                       "words": [{"text": w["text"], "box": w["box"]} for line in d.get("lines") or []
                                 for w in line.get("words") or []]}
    saved = json.loads(KEY_DRAFT.read_text(encoding="utf-8")) if KEY_DRAFT.exists() else None
    return {"fields": [{"id": f["id"], "name": f["name"], "kind": f["kind"]} for f in fields["fields"]],
            "shots": SHOTS, "kinds": KINDS, "ids": ids(), "drafts": drafts, "saved": saved}


def box_ok(b):
    return (isinstance(b, list) and len(b) == 4 and all(isinstance(v, (int, float)) and 0 <= v <= 1 for v in b)
            and b[0] < b[2] and b[1] < b[3])


def clean_save(body, known, field_ids):
    """The saved state, checked entry by entry, or a ValueError naming the first problem."""
    if not isinstance(body, dict) or not isinstance(body.get("photos"), dict):
        raise ValueError("the save holds no photos")
    out = {}
    for pid, s in body["photos"].items():
        if pid not in known or not isinstance(s, dict):
            raise ValueError(f"{pid} isn't one of the prepared photos")
        if s.get("status") not in STATUSES or s.get("shot") not in SHOTS:
            raise ValueError(f"{pid} has an unknown status or shot")
        fields = {}
        for fid, v in (s.get("fields") or {}).items():
            if fid not in field_ids:
                raise ValueError(f"{pid} names an unknown field {fid}")
            if v is None:
                fields[fid] = None
                continue
            value = " ".join(str(v.get("value") or "").split())[:60]
            box = v.get("box")
            fields[fid] = {"value": value, "box": [round(x, 4) for x in box] if box_ok(box) else None}
        out[pid] = {"status": s["status"], "plate": " ".join(str(s.get("plate") or "").split())[:60],
                    "kind": str(s.get("kind") or "")[:40], "shot": s["shot"], "fields": fields,
                    "masks": [[round(x, 4) for x in m] for m in (s.get("masks") or [])[:80] if box_ok(m)],
                    "checked_people": bool(s.get("checked_people")),
                    "dropped_why": str(s.get("dropped_why") or "")[:80]}
    return {"version": 1, "confirmed_by": "a person, on the verification page",
            "saved_at": datetime.now().isoformat(timespec="seconds"), "photos": out}


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "verify"

    def log_message(self, *args):
        pass

    def host_ok(self):
        return self.headers.get("Host") == f"127.0.0.1:{self.server.server_address[1]}"

    def send(self, code, body, ctype="text/plain; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if not self.host_ok():
            return self.send(403, b"This page only answers on its own address.")
        path = self.path.split("?")[0]
        if path in FILES:
            name, ctype = FILES[path]
            return self.send(200, PAGE.joinpath(name).read_bytes(), ctype)
        if path == "/api/state":
            return self.send(200, json.dumps(state()).encode(), "application/json")
        m = re.fullmatch(r"/photo/(p[0-9]{2,3})\.jpg", path)
        if m and UNMASKED.joinpath(f"{m.group(1)}.jpg").exists():
            return self.send(200, UNMASKED.joinpath(f"{m.group(1)}.jpg").read_bytes(), "image/jpeg")
        return self.send(404, b"Not here.")

    def do_POST(self):
        if not self.host_ok() or self.path != "/api/save":
            return self.send(403, b"This page only saves on its own address.")
        n = int(self.headers.get("Content-Length") or 0)
        if not 0 < n <= LIMIT:
            return self.send(413, b"That save is empty or too large.")
        try:
            fields = {f["id"] for f in confirm.load_fields()["fields"]}
            data = clean_save(json.loads(self.rfile.read(n)), set(ids()), fields)
        except ValueError as e:
            return self.send(400, str(e).encode())
        tmp = KEY_DRAFT.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
        tmp.replace(KEY_DRAFT)
        done = sum(1 for s in data["photos"].values() if s["status"] != "open")
        return self.send(200, json.dumps({"ok": True, "saved_at": data["saved_at"], "settled": done}).encode(),
                         "application/json")


def main():
    if not ids():
        raise SystemExit("No photos in data/unmasked/. Run bash owner/prepare.sh first.")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    print(f"The verification page is open at {url}")
    print("Every change saves as you go. Press Control-C here once the page says every photo is settled.")
    webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped. Next: bash owner/prepare.sh --mask")


if __name__ == "__main__":
    main()
