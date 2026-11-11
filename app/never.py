"""Words that must never ship, and the scan that enforces it.

Three lists. The never list comes from tools/lint_copy.py's NEVER tuple and reference/private_words.txt (a line written
rot13:... is decoded first), and neither file ships. The foreign list, config/foreign_words.txt, holds the other demos'
companies and people, since each project stands alone. A match is a whole word or phrase without regard to case, so
"cat" never matches "category." The first-names list, config/foreign_first_names.txt, checks this build's cast against
the earlier casts' first names. Adapted from the Inbox Agent's scan, which came from the Call Companion's.
"""
import codecs
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def words(private=None, tool=None):
    out = []
    private = Path(private or HERE.joinpath("reference", "private_words.txt"))
    if private.exists():
        for line in private.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append(codecs.decode(line[6:], "rot13").lower() if line.startswith("rot13:") else line.lower())
    tool = Path(tool or HERE.joinpath("tools", "lint_copy.py"))
    if tool.exists():
        spec = importlib.util.spec_from_file_location("lint_copy_never", str(tool))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        out += [w.lower() for w in getattr(mod, "NEVER", ())]
    return tuple(dict.fromkeys(out))


def _list(path):
    path = Path(path)
    if not path.exists():
        return ()
    return tuple(line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
                 if line.strip() and not line.strip().startswith("#"))


def foreign(path=None):
    return _list(path or HERE.joinpath("config", "foreign_words.txt"))


def first_names(path=None):
    return _list(path or HERE.joinpath("config", "foreign_first_names.txt"))


def shared_first_names(people, taken=None):
    """The people in this build whose first name an earlier cast already used."""
    taken = set(first_names() if taken is None else taken)
    return [p for p in people if p.split()[0].lower() in taken]


def pattern(word_list):
    parts = [r"\b" + re.escape(w).replace(r"\ ", r"\s+") + r"\b" for w in word_list]
    return re.compile("|".join(parts), re.IGNORECASE) if parts else None


def hits(text, word_list):
    pat = pattern(word_list)
    if not pat:
        return []
    return list(dict.fromkeys(m.group(0).lower() for m in pat.finditer(text)))


def scan(paths, never_words=None, foreign_words=None):
    """A line per file that holds a never-word or another demo's name. The never-words themselves are never printed."""
    never_words = words() if never_words is None else never_words
    foreign_words = foreign() if foreign_words is None else foreign_words
    problems = []
    for path in paths:
        path = Path(path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        n, f = hits(text, never_words), hits(text, foreign_words)
        if n:
            problems.append(f"{path.name} holds {len(n)} word(s) from the never list")
        if f:
            problems.append(f"{path.name} names another demo's company or person: {', '.join(f)}")
    return problems
