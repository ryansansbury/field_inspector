"""Every doc follows the writing rules: the copy lint is clean (when the private tool is here), no word from the never
list or another demo's names appears, no local path or email address ships, and no phrase of five words or more turns
up twice in what a visitor reads."""
import importlib.util
import re
import unittest
from pathlib import Path

from app import never, readme, words

HERE = Path(__file__).resolve().parent.parent
TOOL = HERE.joinpath("tools", "lint_copy.py")
DOCS = sorted(HERE.joinpath("docs").glob("*.md")) + [HERE.joinpath("owner", "README.md"), HERE.joinpath("WORDS.md")] + \
    ([HERE.joinpath("README.md")] if HERE.joinpath("README.md").exists() else [])


def reading(entries, raw):
    """(place, text) for the prose a visitor reads: How it works with its map and pipeline, the tour and the footer.
    Titles, column labels, the rules list and the reasons are vocabulary that's meant to repeat."""
    def rows(key):
        return [(f"{key}.{line[2:].partition(' = ')[0]}", line[2:].partition(" = ")[2])
                for line in raw[key].splitlines() if line.startswith("- ")]
    prose = [(k, v) for k, v in entries.items()
             if k.startswith("how.") and not k.endswith(".title") and not raw[k].strip().startswith("- ")]
    return prose + rows("how.map") + rows("how.pipeline") + rows("ui.present.texts") + [("page.footer", entries["page.footer"])]


def twice(places):
    """Every run of five words that turns up in two different places, with both places named."""
    seen, out = {}, set()
    for place, text in places:
        for piece in re.split(r"\{[^}]*\}|[.,;:?!|`()]", text):
            toks = re.findall(r"[a-z0-9']+", piece.lower())
            for i in range(len(toks) - 4):
                run = " ".join(toks[i:i + 5])
                if seen.setdefault(run, place) != place:
                    out.add(f"{run} ({seen[run]} and {place})")
    return sorted(out)


def lint_tool():
    spec = importlib.util.spec_from_file_location("lint_copy_test", str(TOOL))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class Copy(unittest.TestCase):
    @unittest.skipUnless(TOOL.exists(), "the copy lint stays in the private build folder")
    def test_the_copy_lint_is_clean(self):
        mod = lint_tool()
        for path in DOCS:
            flagged = [s for line in mod.prose(path) for s in mod.sentences(line) if mod.check(s, strict=True)]
            self.assertEqual(flagged, [], path.name)

    def test_no_never_words_or_other_demos(self):
        self.assertEqual(never.scan(DOCS), [])

    def test_no_phrase_twice_in_what_a_visitor_reads(self):
        self.assertEqual(twice(reading(*words.parse(HERE.joinpath("WORDS.md").read_text(encoding="utf-8")))), [])
        sections = ("INTRO", "MAP", "RESULTS", "PRIVACY", "RUN", "LIMITS")
        self.assertEqual(twice([(name, getattr(readme, name)) for name in sections]), [])

    def test_the_readme_names_the_route_the_way_the_page_does(self):
        w, data = words.load(), {"models": [{"id": "a", "label": "Model A"}], "route": "a"}
        for why, text in w.table("how.models.reasons").items():
            self.assertEqual(readme.route(data, {"route": "a", "route_reason": why}),
                             w.fill("how.models.route", model="Model A", reason=text))
        self.assertEqual(readme.route(data, None), "")

    def test_no_local_paths_or_email(self):
        for path in DOCS:
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, "/" + "Users/[A-Za-z]|~" + "/projects", path.name)
            self.assertNotRegex(text, r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.(com|net|org|io)\b", path.name)


if __name__ == "__main__":
    unittest.main()
