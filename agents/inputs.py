"""What the read sees: the system prompt, the user text and the photo, built the same way in the recorder and in the
build's replay check.

The system prompt is prompts/read.md followed by the field table from config/fields.json, so the prompt hash covers both
and a change to either makes an old recording stale. The read never sees the job's design, so a model can't read what
it expects to find. The input hash covers the photo's bytes and the user text.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
MEDIA = "image/jpeg"


def fields():
    return json.loads(HERE.joinpath("config", "fields.json").read_text(encoding="utf-8"))["fields"]


def system_prompt():
    rows = "\n".join(f"- `{f['id']}`: {f['means']}" for f in fields())
    return HERE.joinpath("prompts", "read.md").read_text(encoding="utf-8").rstrip() + "\n\n" + rows + "\n"


def prompt_hash():
    return hashlib.sha256(system_prompt().encode("utf-8")).hexdigest()[:16]


def user_text(photo, w, h):
    return f"Photo {photo}, {w} by {h} pixels. Read every field and answer with the JSON object only."


def image(path):
    return {"media_type": MEDIA, "bytes": Path(path).read_bytes()}


def input_hash(image_bytes, user):
    return hashlib.sha256(hashlib.sha256(image_bytes).digest() + user.encode("utf-8")).hexdigest()[:16]
