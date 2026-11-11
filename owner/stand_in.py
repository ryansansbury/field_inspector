"""A stand-in for a model, for dry runs and the preview with no network: it answers each photo from the answer key.

It exists to prove the pipeline end to end (the inputs, the reply check, the records, the confirmation step, the scores
and the page) before anything is spent. Its reads are labeled "Stand-in (no model)" everywhere, and the real build never
shows them as results. Each value comes back exactly as the key holds it, with the key's box when it has one.
"""
import json
import re

LABEL = "Stand-in (no model)"
MODEL = "stand-in"


def reply(key, photo, fields):
    ph = key["photos"][photo]
    out = {}
    for f in fields:
        v = ph["fields"].get(f["id"])
        out[f["id"]] = ({"status": "read", "value": v["value"], "label": None, "box": v.get("box")} if v else
                        {"status": "absent", "value": None, "label": None, "box": None})
    return json.dumps({"fields": out})


class Backend:
    """model(system, user, image) that answers from the key, for the recorder's dry run."""

    def __init__(self, key, fields):
        self.key, self.fields = key, fields

    def __call__(self, system, user, image=None):
        photo = re.search(r"Photo (p[0-9]+)", user).group(1)
        return reply(self.key, photo, self.fields), {"ms": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                                                     "models": [MODEL]}

    def described(self):
        return {"backend": "stand-in", "model": MODEL}
