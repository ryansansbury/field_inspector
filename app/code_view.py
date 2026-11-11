"""The code section on How it works: the project's real source, copied into the page on every build.

An allowlist picks the folders. The planning files, the references, the photos, the recordings and the writing-rules
tool never go in, and the never-word scan reads the code with the rest of the page. The files go to site/code.js as
data apart from the page's script, and the page loads that file only when the code view opens. Adapted from the Call
Companion's code view.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
FOLDERS = ("engine", "agents", "prompts", "app", "evals", "generate", "owner", "config", "tests")
TOP = ("build.py", "WORDS.md", "site/app.js", "site/rules.js", "site/normalize.js", "site/app.css")
SUFFIXES = (".py", ".js", ".css", ".md", ".sh", ".json", ".html")
SKIP = ("owner/out/", "owner/private/", "evals/frozen.json", "evals/preview_scores.json", "tests/vectors/",
        "tests/fixtures/preview/", "config/foreign_words.txt", "config/foreign_first_names.txt")
DEFAULT = "engine/confirm.py"
FEATURED = ("engine/confirm.py", "engine/rules.py", "prompts/read.md", "generate/render.py", "evals/score.py")


def collect(root=HERE):
    """{path: text} for every file the code section shows."""
    root = Path(root)
    paths = [root.joinpath(t) for t in TOP]
    for folder in FOLDERS:
        if root.joinpath(folder).exists():
            paths += sorted(root.joinpath(folder).rglob("*"))
    files = {}
    for p in paths:
        rel = p.relative_to(root).as_posix()
        if p.is_file() and p.suffix in SUFFIXES and "__pycache__" not in rel and not rel.startswith(SKIP):
            files[rel] = p.read_text(encoding="utf-8")
    return files


def write(files, path=None):
    path = Path(path or HERE.joinpath("site", "code.js"))
    path.write_text("window.FICODE = " + json.dumps({"files": files, "default": DEFAULT, "featured": FEATURED},
                                                     ensure_ascii=False, separators=(",", ":")) + ";\n",
                    encoding="utf-8")
    return path.stat().st_size
