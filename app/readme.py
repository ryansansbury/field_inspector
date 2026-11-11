"""README.md, written by the real build from the same results the page shows, so the README can't drift from the page.

The prose lives here and follows the writing rules, and the table comes from evals/scores.json. A preview build writes
nothing because its numbers come from the stand-in.
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
LIVE = "https://www.ryansansbury.com/field-inspector/"
# The README's screens, picked from a reviewed screenshot round (owner/out/screens/) and copied into docs/gallery/.
SHOTS = (("job", "The job as it opens with the heat pump failing across its plate and its breaker photo"),
         ("dryer", "The dryer's model under glare as it waits for a person to type what the plate shows"),
         ("dishwasher", "The dishwasher's model one character off the design as it waits for a person to decide"),
         ("log", "The audit log with what the AI read, what the checks found, and each decision a person made"),
         ("phone", "The job on a phone"))
REASONS = {"cheapest_clearing": "the cheapest model that cleared every bar on the tuning photos",
           "most_accurate_on_dev": "the most accurate model on the tuning photos when none cleared every bar"}

INTRO = """# Field Inspector

A technician's nameplate photos go in, AI reads every plate, the photo's own text confirms each value, code checks the values against the job's design and across photos, and anything uncertain or failing goes to a person. The live demo is at {live} and it calls no model or service. The AI reads were recorded on the owner's machine, and the page replays them.

The photos are synthetic and were drawn and photographed by code to look like a technician's phone shots. The installer, the job, its design, and the people are made up."""

MAP = """## What's AI, what's code, and what's a person

- **AI** reads each plate into a fixed set of fields with the label it read each value under and a rough box. It never sees the design.
- **Code** finds the words on each photo with the Mac's own text recognition and confirms each read by the photo's own text near its label.
- **Code** runs the installer's rules on every value and across photos. The rules are kept as data in `config/rules.json` and run in Python for the scores and in JavaScript on the page.
- **A person** settles every read the photo couldn't confirm and decides whether a model one character off is an approved equal."""

RESULTS = """## The results

Every model got the same photos, and none of them saw the test photos until the prompt was frozen. The answer key comes from the same file that drew the plates and holds exactly what each photo shows. A wrong read past the line is one the photo's text seemed to confirm, and those are the dangerous ones."""

PRIVACY = """## The photos

`generate/render.py` draws each plate from `generate/plates.json` and photographs it with an angle, glare, dim light, and grain. For real photos `owner/` holds the path that strips every photo, masks makers' names and serials, and has a person confirm each value before any model sees it. The build runs a privacy scan on every published photo and every file in the repo."""

RUN = """## Running it

Python 3.9 or newer and nothing else builds the page from the recordings with `python3 build.py`. The tests run with `python3 tests/run.py`, and Node runs the page's click-through and the parity checks between the Python and JavaScript rules. The owner's runs that read photos and call the models are in `owner/README.md`."""

LIMITS = """## What it can't do

It reads only what the photo shows, and a plate behind a bracket or under heavy glare goes to a person. It checks the installer's design rules and nothing else, and it isn't an inspection. It isn't production software, and the page can't read a new photo."""

LICENSE = """## License

The code is under PolyForm Noncommercial 1.0.0 in `LICENSE`. The fonts carry their own licenses in `site/fonts/`."""


def pct(x):
    return "" if x is None else f"{round(x * 100)}%"


def table(data, scores):
    rows = ["| Model | Fields right on test | Wrong reads past the line | Wrong verdicts that skipped the person | "
            "Reads sent to a person | Cost per photo | Seconds per photo |", "|---|---|---|---|---|---|---|"]
    for m in data["models"]:
        t = ((scores or {}).get("models", {}).get(m["id"]) or {}).get("test")
        if not t:
            continue
        line = t["line"]["partial"]
        cost = t.get("cost_per_photo")
        rows.append(f"| {m['label']} | {pct(t['fields']['accuracy'])} | {line['past']} | {t['checks']['missed']} | "
                    f"{pct(line['share'])} | {'' if cost is None else f'${cost:.4f}'} | {t.get('seconds_per_photo')} |")
    return "\n".join(rows)


def gallery():
    """(the hero under the intro, the screens section), each empty until its shots are copied into docs/gallery/."""
    have = [(n, alt) for n, alt in SHOTS if HERE.joinpath("docs", "gallery", f"{n}.png").exists()]
    hero = "".join(f"![{alt}](docs/gallery/{n}.png)" for n, alt in have if n == SHOTS[0][0])
    rest = [f"{alt}.\n\n![{alt}](docs/gallery/{n}.png)" for n, alt in have if n != SHOTS[0][0]]
    return hero, ("## Screens\n\n" + "\n\n".join(rest) if rest else "")


def route(data, comparison):
    """Which model the page opens on and why, as the page says it."""
    c, labels = comparison or {}, {m["id"]: m["label"] for m in data["models"]}
    rid = c.get("route") or data.get("route")
    if rid not in labels or c.get("route_reason") not in REASONS:
        return ""
    return f"The page opens on {labels[rid]} because it's {REASONS[c['route_reason']]}."


def write(data, scores, comparison=None):
    if data.get("preview"):
        return None
    hero, screens = gallery()
    parts = [INTRO.format(live=LIVE), hero, MAP, RESULTS, table(data, scores), route(data, comparison), screens,
             PRIVACY, RUN, LIMITS, LICENSE]
    text = "\n\n".join(p for p in parts if p) + "\n"
    HERE.joinpath("README.md").write_text(text, encoding="utf-8")
    return text
