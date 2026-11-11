"""The owner scripts' plain parts, which run without Vision or Pillow: Vision's box flip, the mask
proposals, the mask geometry, the masked-word list, the verification page's save check, and the key copier against a
stand-in Keychain."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from engine import confirm as cf
from owner import ocr, prepare, verify
from tests.helpers import HVAC, ocr as sketch

FIELDS = cf.load_fields()


class Flip(unittest.TestCase):
    def test_a_vision_rectangle_comes_out_from_the_top_left(self):
        self.assertEqual(ocr.flip(((0.1, 0.7), (0.2, 0.1))), [0.1, 0.2, 0.3, 0.3])

    def test_a_line_box_splits_into_word_boxes_by_characters(self):
        words = ocr.split_box([0.1, 0.2, 0.5, 0.3], "MCA 18.6")
        self.assertEqual([w["text"] for w in words], ["MCA", "18.6"])
        self.assertEqual(words[0]["box"], [0.1, 0.2, 0.25, 0.3])
        self.assertEqual(words[1]["box"], [0.3, 0.2, 0.5, 0.3])


class Proposals(unittest.TestCase):
    def proposals(self, rows, barcodes=()):
        return ocr.propose(cf.Photo(sketch(rows), FIELDS), FIELDS, barcodes)

    def test_the_serial_value_is_masked_and_the_label_is_not(self):
        got = [p for p in self.proposals(HVAC) if p["why"] == "serial"]
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0]["box"][0], 400 / 1568, places=3)

    def test_web_phone_address_and_listing_lines(self):
        rows = [(100, [(100, "WWW.PLUGH.EXAMPLE")]), (150, [(100, "CALL 555-201-4400")]),
                (200, [(100, "ANYTOWN, ZZ 99999")]), (250, [(100, "LISTED 4KA2")]), (300, [(100, "MODEL X-1")])]
        self.assertEqual([p["why"] for p in self.proposals(rows)], ["web", "phone", "address", "listing"])

    def test_tall_lettering_is_masked_unless_it_is_plain_plate_words(self):
        rows = [(100, [(100, "MODEL X-1")]), (150, [(100, "VOLTS 120")]), (200, [(100, "AMPS 12")])]
        sketch_rows = sketch(rows)
        sketch_rows["lines"].append({"text": "PLUGHCO", "conf": 1, "box": [0.1, 0.5, 0.5, 0.6],
                                     "words": [{"text": "PLUGHCO", "box": [0.1, 0.5, 0.5, 0.6]}]})
        sketch_rows["lines"].append({"text": "WATER HEATER", "conf": 1, "box": [0.1, 0.7, 0.5, 0.8],
                                     "words": [{"text": "WATER", "box": [0.1, 0.7, 0.3, 0.8]},
                                               {"text": "HEATER", "box": [0.31, 0.7, 0.5, 0.8]}]})
        got = ocr.propose(cf.Photo(sketch_rows, FIELDS), FIELDS)
        self.assertEqual([p["why"] for p in got], ["lettering"])

    def test_barcodes_are_masked(self):
        got = self.proposals(HVAC, [{"box": [0.6, 0.6, 0.8, 0.7], "payload": "x"}])
        self.assertIn({"box": [0.6, 0.6, 0.8, 0.7], "why": "barcode"}, got)


class Masks(unittest.TestCase):
    def test_the_padding_never_leaves_the_photo(self):
        outer, core = prepare.pad_box([0.0, 0.5, 0.2, 0.6], 1000, 500)
        self.assertEqual(outer[0], 0)
        self.assertEqual(core, (0, 250, 200, 300))
        self.assertLess(outer[1], 250)

    def test_masked_words_keep_names_and_serials_and_drop_plain_words(self):
        draft = {"lines": [{"words": [{"text": "PLUGHCO", "box": [0.1, 0.1, 0.2, 0.15]},
                                      {"text": "VOLTS", "box": [0.21, 0.1, 0.3, 0.15]},
                                      {"text": "X12345678", "box": [0.1, 0.2, 0.3, 0.25]},
                                      {"text": "25", "box": [0.1, 0.3, 0.12, 0.35]},
                                      {"text": "OUTSIDE", "box": [0.8, 0.8, 0.9, 0.85]}]}],
                 "barcodes": [{"payload": "ser=Q77GZ12"}]}
        masks = [[0.05, 0.05, 0.4, 0.4]]
        got = prepare.masked_words(draft, masks, {"VOLTS"})
        self.assertEqual(got, {"PLUGHCO", "X12345678", "Q77GZ12"})


class Save(unittest.TestCase):
    def body(self, **change):
        photo = {"status": "done", "plate": " Water  heater ", "kind": "water heater", "shot": "glare",
                 "fields": {"model": {"value": " EWH-50 ", "box": [0.1, 0.1, 0.2, 0.2]}, "mca": None},
                 "masks": [[0.1, 0.1, 0.5, 0.2], [0.5, 0.5, 0.4, 0.6]]}
        photo.update(change)
        return {"photos": {"p01": photo}}

    def test_a_good_save_is_cleaned(self):
        out = verify.clean_save(self.body(), {"p01"}, {"model", "mca"})["photos"]["p01"]
        self.assertEqual(out["plate"], "Water heater")
        self.assertEqual(out["fields"], {"model": {"value": "EWH-50", "box": [0.1, 0.1, 0.2, 0.2]}, "mca": None})
        self.assertEqual(out["masks"], [[0.1, 0.1, 0.5, 0.2]])

    def test_a_bad_save_is_refused(self):
        with self.assertRaises(ValueError):
            verify.clean_save(self.body(status="maybe"), {"p01"}, {"model", "mca"})
        with self.assertRaises(ValueError):
            verify.clean_save(self.body(), {"p02"}, {"model", "mca"})
        with self.assertRaises(ValueError):
            verify.clean_save(self.body(fields={"serial": None}), {"p01"}, {"model", "mca"})


class Keys(unittest.TestCase):
    """owner/keys.sh with a stand-in for the macOS security command, so no real key is read or written."""
    KEY = "sk-stand-in-0123456789abcdef"
    STAND_IN = """#!/bin/bash
case "$1" in
  find-generic-password) [ "$3" = old-anthropic ] && echo "{key}" && exit 0; exit 44 ;;
  add-generic-password) echo "$6" >> "{log}" ;;
esac
"""

    def keys(self, *args):
        here = Path(__file__).resolve().parent.parent
        scratch = here.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as tmp:
            fake, log = Path(tmp), Path(tmp).joinpath("saved")
            fake.joinpath("security").write_text(self.STAND_IN.format(key=self.KEY, log=log), encoding="utf-8")
            fake.joinpath("security").chmod(0o755)
            run = subprocess.run(["bash", "-c", 'PATH="$0:$PATH" bash owner/keys.sh "$@"', str(fake), *args],
                                 cwd=here, capture_output=True, text=True)
            saved = log.read_text(encoding="utf-8").split() if log.exists() else []
        self.assertNotIn(self.KEY, run.stdout + run.stderr)
        return run, saved

    def test_one_vendor_from_another_project(self):
        run, saved = self.keys("--from", "old", "anthropic")
        self.assertEqual((run.returncode, saved), (0, ["field-inspector-anthropic"]))
        self.assertIn("Saved the anthropic key", run.stdout)

    def test_both_vendors_skip_the_missing_one(self):
        run, saved = self.keys("--from", "old")
        self.assertEqual((run.returncode, saved), (0, ["field-inspector-anthropic"]))
        self.assertIn("no Keychain item named old-openai", run.stdout)

    def test_an_unknown_vendor_is_refused(self):
        run, saved = self.keys("--from", "old", "other")
        self.assertEqual((run.returncode, saved), (1, []))


if __name__ == "__main__":
    unittest.main()
