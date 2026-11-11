"""Build the Field Inspector page from what the pipeline and the owner's runs left on disk.

    python3 build.py              the real page, from the frozen photos and designs, the recorded reads and the scores
    python3 build.py --preview    the preview, on the drawn plates and the stand-in, labeled in red and never staged

The stages: the scores (the scorer and the model comparison, read from the recordings), then the page (the data bundle,
the code view, index.html, the never-word and other-demo scans, the copy lint, the privacy scan and the weight check).
No AI step runs here. The build replays what the owner's recorder saved, validates every reply again, and confirms every
value against the photo's own text before the page uses it. Standard library only, Python 3.9 or newer.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from app import bundle, code_view, names, never, page, readme, words  # noqa: E402
from engine import privacy  # noqa: E402

SITE = HERE.joinpath("site")
FONTS = ("inter-latin.woff2", "jetbrains-mono-latin.woff2", "Inter-LICENSE.txt", "JetBrainsMono-OFL.txt")
SHIPPED = ("index.html", "app.css", "app.js", "rules.js", "normalize.js", "data.js", "favicon.svg")
WEIGHT_LIMIT = 1_000_000


def score_stage(preview):
    from evals import compare, freeze, score
    if preview:
        score.main(["--preview"])
        return
    for stage in ("photos", "designs"):
        if not freeze.ready(stage):
            raise SystemExit(f"The {stage} stage isn't frozen and unchanged. Run python3 evals/freeze.py --check.")
    score.main([])
    compare.main()


def runs_rows(data):
    """One row per recorded read of the job's photos for How it works."""
    from agents import replay
    out = []
    for m in data["models"]:
        for p in sorted(data["models"][0]["reads"]):
            rec = replay.load(p, m["id"], strict=False)
            if not rec:
                continue
            meta = rec.get("meta") or {}
            cost = meta.get("cost_usd")
            out.append([p, m["label"], rec.get("date"), f"{meta.get('input_tokens')} and {meta.get('output_tokens')}",
                        "" if cost is None else f"${cost:.4f}", round((rec.get("ms") or 0) / 1000, 1)])
    return out


def lint(path):
    """The copy lint on WORDS.md, when the private tool is here (it never ships, so a public clone skips it)."""
    tool = HERE.joinpath("tools", "lint_copy.py")
    if not tool.exists():
        return []
    spec = importlib.util.spec_from_file_location("lint_copy_build", str(tool))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return [s for line in mod.prose(path) for s in mod.sentences(line) if mod.check(s, strict=True)]


def page_stage(preview):
    w = words.load()
    missing = [f for f in FONTS if not SITE.joinpath("fonts", f).exists()]
    if missing:
        raise SystemExit(f"Stopped: site/fonts/ is missing {', '.join(missing)}.")
    data = bundle.build(w, preview)
    size = bundle.write(data, preview)
    code_size = code_view.write(code_view.collect())
    evals = HERE.joinpath("evals")
    scores_path = evals.joinpath("preview_scores.json" if preview else "scores.json")
    comp_path = evals.joinpath("model_comparison.json")
    extra = {"scores": json.loads(scores_path.read_text(encoding="utf-8")) if scores_path.exists() else None,
             "comparison": json.loads(comp_path.read_text(encoding="utf-8")) if comp_path.exists() and not preview
             else None,
             "privacy": privacy.scan(HERE), "runs": [] if preview else runs_rows(data)}
    SITE.joinpath("index.html").write_text(page.render(w, data, extra), encoding="utf-8")
    readme.write(data, extra["scores"], extra["comparison"])
    problems = never.scan([SITE.joinpath(n) for n in SHIPPED + ("code.js",)] +
                          [HERE.joinpath("WORDS.md"), HERE.joinpath("config", "names.json")])
    if problems:
        raise SystemExit("Stopped: " + "; ".join(problems))
    flagged = lint(HERE.joinpath("WORDS.md"))
    if flagged:
        raise SystemExit(f"Stopped: the copy lint flags {len(flagged)} sentences in WORDS.md. Run "
                         f"python3 tools/lint_copy.py --strict WORDS.md")
    if not preview and extra["privacy"]["problems"]:
        raise SystemExit("Stopped: the privacy scan found problems. Run python3 engine/privacy.py")
    fonts = sum(p.stat().st_size for p in SITE.joinpath("fonts").glob("*.woff2"))
    weight = sum(SITE.joinpath(n).stat().st_size for n in SHIPPED) + fonts
    if weight > WEIGHT_LIMIT:
        raise SystemExit(f"Stopped: the page weighs {weight:,} bytes before photos, over the {WEIGHT_LIMIT:,} budget.")
    unused = [k for k in w.entries if not k.startswith("ui.") and k not in w.used]
    return {"data": size, "code": code_size, "weight": weight, "unused": unused, "names": names.load() is not None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--preview", action="store_true")
    ap.add_argument("--only", choices=["score", "page"])
    a = ap.parse_args(argv)
    t0 = time.time()
    if not a.preview:
        names.cast()
    if a.only in (None, "score"):
        score_stage(a.preview)
    if a.only in (None, "page"):
        out = page_stage(a.preview)
        print(f"Page: data.js {out['data']:,} bytes, code.js {out['code']:,} bytes (loaded on demand), "
              f"{out['weight']:,} bytes before photos" + (f". Unused words: {', '.join(out['unused'])}"
                                                           if out["unused"] else ""))
    print(f"Built {'the preview' if a.preview else 'the page'} in {time.time() - t0:.1f} s.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
