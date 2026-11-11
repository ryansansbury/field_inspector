"""Every visible word lives in WORDS.md, so the wording changes in one place.

Each `## key` heading starts an entry, and the text under it, up to the next heading, is its value. Lines inside a
paragraph join with spaces and paragraphs stay apart. A key the page asks for that the file doesn't have fails the
build, so nothing ships blank. {name} fields are filled by fill(), and entries whose keys start with "ui." go to the
page's script as they are. Adapted from the Inbox Agent's reader, which came from the Call Companion's.
"""
import re
import string
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
BASE = HERE.joinpath("WORDS.md")
KEY = re.compile(r"^##\s+([A-Za-z0-9_.-]+)\s*$")


class MissingWord(KeyError):
    pass


def parse(text, source="WORDS.md"):
    """({key: value}, {key: raw lines}). A key used twice is an error."""
    out, raw, key, buf = {}, {}, None, []

    def flush():
        if key is None:
            return
        if key in out:
            raise ValueError(f"{source} uses the key {key} twice")
        paras = [" ".join(p.split()) for p in "\n".join(buf).strip().split("\n\n") if p.strip()]
        out[key] = "\n\n".join(paras)
        raw[key] = "\n".join(buf)

    for line in text.splitlines():
        m = KEY.match(line)
        if m:
            flush()
            key, buf = m.group(1), []
        elif key is not None:
            buf.append(line)
    flush()
    return out, raw


class Words:
    def __init__(self, entries, raw):
        self.entries, self.raw = dict(entries), dict(raw)
        self.used = set()

    def __getitem__(self, key):
        if key not in self.entries:
            raise MissingWord(f"no words entry for {key} in WORDS.md")
        self.used.add(key)
        return self.entries[key]

    def __contains__(self, key):
        return key in self.entries

    def get(self, key, default=None):
        return self[key] if key in self.entries else default

    def fill(self, key, **values):
        text = self[key]
        names = {f for _, f, _, _ in string.Formatter().parse(text) if f}
        missing = names - set(values)
        if missing:
            raise MissingWord(f"{key} needs {', '.join(sorted(missing))}")
        return text.format(**values)

    def paragraphs(self, key):
        return self[key].split("\n\n")

    def table(self, key):
        """{name: label} from an entry written as lines of '- name = label'."""
        self[key]
        out = {}
        for line in self.raw.get(key, "").splitlines():
            line = line.strip()
            if line.startswith("- ") and " = " in line:
                name, _, label = line[2:].partition(" = ")
                out[name.strip()] = label.strip()
        return out

    def ui(self):
        """Every ui. entry for the page's script, with tables as objects."""
        out = {}
        for k in self.entries:
            if k.startswith("ui."):
                t = self.table(k) if any(ln.strip().startswith("- ") and " = " in ln
                                         for ln in self.raw[k].splitlines()) else self[k]
                out[k[3:]] = t
        return out


def load(base=None):
    entries, raw = parse(Path(base or BASE).read_text(encoding="utf-8"))
    return Words(entries, raw)
