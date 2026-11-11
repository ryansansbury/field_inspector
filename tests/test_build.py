"""The shell builds and reads every word from WORDS.md, the never list and the other demos' names stay out of it and out
of the cast, and no module shadows one from Python's standard library."""
import json
import pkgutil
import sys
import sysconfig
import tempfile
import unittest
from pathlib import Path

import build
from app import names, never, words

HERE = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"reference", ".venv", ".cache", "node_modules", "__pycache__", "mockups"}


def stdlib_names():
    found = set(getattr(sys, "stdlib_module_names", ()))
    if not found:
        std = Path(sysconfig.get_paths()["stdlib"])
        found = {m.name for m in pkgutil.iter_modules([str(std), str(std.joinpath("lib-dynload"))])}
    return found | set(sys.builtin_module_names)


class Build(unittest.TestCase):
    def test_the_preview_shell_builds_from_words(self):
        self.assertEqual(build.main(["--preview"]), 0)
        html = HERE.joinpath("site", "index.html").read_text(encoding="utf-8")
        w = words.load()
        self.assertIn(f"<title>{w['page.title']}</title>", html)
        self.assertIn(w["page.footer_preview"], html)
        self.assertIn(w["page.preview"], html)

    def test_the_real_build_waits_for_the_names(self):
        if names.load() is None:
            with self.assertRaises(names.Pending):
                build.main([])
        else:
            self.assertEqual(build.main([]), 0)

    def test_no_inline_style_or_script_and_nothing_loaded_from_another_site(self):
        build.main(["--preview"])
        html = HERE.joinpath("site", "index.html").read_text(encoding="utf-8")
        self.assertNotIn(" style=", html)
        self.assertNotRegex(html, r"<script[^>]*>[^<]")
        self.assertNotRegex(html, r"\ssrc=['\"](https?:)?//")
        # The canonical link loads nothing, and it names the live page.
        self.assertNotRegex(html, r"<link(?![^>]*rel=['\"]canonical['\"])[^>]+href=['\"](https?:)?//")
        self.assertIn("<link rel='canonical' href='https://www.ryansansbury.com/field-inspector/'>", html)
        self.assertRegex(html, r"<meta property='og:image' content='https://www\.ryansansbury\.com/images/share/"
                               r"field-inspector\.png\?v=\d+'>")

    def test_a_missing_word_fails_loudly(self):
        with self.assertRaises(words.MissingWord):
            words.Words({}, {})["page.title"]

    def test_the_foreign_list_catches_another_demos_name(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            f = Path(d, "x.txt")
            f.write_text("A note about Xyzzy and its plates.", encoding="utf-8")
            self.assertTrue(any("another demo" in p for p in never.scan([f], never_words=(), foreign_words=("xyzzy",))))
            self.assertEqual(never.scan([f], never_words=(), foreign_words=("plugh",)), [])

    @unittest.skipUnless(never.first_names(), "the earlier casts' first names stay in the private build folder")
    def test_a_first_name_from_an_earlier_cast_is_caught(self):
        taken = never.first_names()
        person = f"{taken[0].title()} Placeholder"
        self.assertEqual(never.shared_first_names([person, "Nobody Placeholder"]), [person])

    @unittest.skipUnless(names.load(), "config/names.json hasn't landed yet")
    def test_the_cast_is_cleared_and_stands_alone(self):
        cast = names.load()
        text = " | ".join(cast.values())
        self.assertEqual(never.hits(text, never.words()), [])
        self.assertEqual(never.hits(text, never.foreign()), [])
        people = [cast[r] for r in names.PEOPLE]
        self.assertTrue(all(len(p.split()) >= 2 for p in people), "each person needs a first name and a surname")
        self.assertEqual(never.shared_first_names(people), [])
        for part in (0, -1):
            self.assertNotEqual(people[0].split()[part], people[1].split()[part])

    def test_names_read_from_strings_or_objects(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            f = Path(d, "names.json")
            f.write_text(json.dumps({"installer": {"name": " Plugh  Works "}, "technician": "A B", "reviewer": "C D"}),
                         encoding="utf-8")
            self.assertEqual(names.load(f)["installer"], "Plugh Works")
            f.write_text(json.dumps({"installer": "X"}), encoding="utf-8")
            with self.assertRaises(ValueError):
                names.load(f)

    def test_whole_words_only(self):
        self.assertEqual(never.hits("a category of cats", ["cat"]), [])
        self.assertEqual(never.hits("the cat sat", ["cat"]), ["cat"])

    def test_no_module_shadows_the_standard_library(self):
        std = stdlib_names()
        clashes = []
        for p in HERE.rglob("*.py"):
            rel = p.relative_to(HERE)
            if SKIP_DIRS & set(rel.parts) or p.stem == "__init__":
                continue
            if p.stem in std:
                clashes.append(rel.as_posix())
        self.assertEqual(clashes, [])


if __name__ == "__main__":
    unittest.main()
