"""The key builder's checks, the seeded split's rules, and the freeze's hashes and history."""
import json
import tempfile
import unittest
from pathlib import Path

from engine import confirm
from evals import freeze, key

HERE = Path(__file__).resolve().parent.parent
FIELDS = confirm.load_fields()


def shot(plate, kind, shot="straight", status="done", **values):
    fields = {f["id"]: None for f in FIELDS["fields"]}
    fields.update({k: {"value": v} for k, v in values.items()})
    return {"status": status, "plate": plate, "kind": kind, "shot": shot, "fields": fields, "masks": []}


def house():
    photos = {
        "p01": shot("Condenser", "condenser", mca="18.6", max_breaker="25"),
        "p02": shot("Condenser", "condenser", "glare", mca="18.6", max_breaker="25"),
        "p03": shot("Air handler", "air handler", mca="9.1", max_breaker="15"),
        "p04": shot("Furnace", "furnace", mca="12", max_breaker="20"),
        "p05": shot("Breaker 30", "breaker", breaker="30"),
        "p06": shot("Breaker 20", "breaker", breaker="20"),
        "p07": shot("Breaker 40", "breaker", breaker="40"),
    }
    for i, name in enumerate(["Washer", "Dryer", "Range", "Dishwasher", "Microwave", "Fridge", "Opener", "Charger",
                              "Heater", "Panel"]):
        photos[f"p{10 + i}"] = shot(name, "other", model=f"QX-{100 + i}")
    return {"photos": photos}


class Build(unittest.TestCase):
    def test_a_clean_house_builds(self):
        k, problems = key.build(house(), FIELDS)
        self.assertEqual(problems, [])
        self.assertEqual(k["plates"]["condenser"]["photos"], ["p01", "p02"])
        self.assertEqual(k["photos"]["p02"]["fields"]["max_breaker"]["canon"], "25")
        self.assertIsNone(k["photos"]["p02"]["fields"]["model"])

    def test_problems_are_named(self):
        d = house()
        d["photos"]["p02"]["fields"]["mca"] = {"value": "16.8"}
        d["photos"]["p03"]["fields"]["volts"] = {"value": "two hundred"}
        d["photos"]["p04"]["status"] = "open"
        d["photos"]["p10"]["plate"] = "Plughco washer"
        _, problems = key.build(d, FIELDS, private=["plughco"])
        text = " | ".join(problems)
        self.assertIn("disagree on mca", text)
        self.assertIn("doesn't read as a volts value", text)
        self.assertIn("p04 isn't confirmed", text)
        self.assertIn("p10's plate name holds a word from under the masks", text)

    def test_dropped_photos_stay_out(self):
        d = house()
        d["photos"]["p02"]["status"] = "dropped"
        k, _ = key.build(d, FIELDS)
        self.assertNotIn("p02", k["photos"])
        self.assertIn("p02", k["dropped"])


class Split(unittest.TestCase):
    def test_the_rules_hold_and_the_draw_repeats(self):
        k, _ = key.build(house(), FIELDS)
        split = key.draw_split(k)
        dev = sorted(n for n, s in split.items() if s == "dev")
        self.assertEqual(split["air-handler"], "test", "the lowest largest breaker stays for the job")
        self.assertEqual(split["breaker-40"], "test", "the highest-rated breaker stays for the job")
        self.assertEqual(sum(1 for n in dev if n in ("condenser", "furnace")), 1)
        self.assertEqual(sum(1 for n in dev if n.startswith("breaker")), 1)
        self.assertEqual(len(dev), 5)
        self.assertGreaterEqual(sum(1 for n, s in split.items() if s == "test" and not n.startswith("breaker")), 8)
        self.assertEqual(split, key.draw_split(k))


class Freeze(unittest.TestCase):
    def test_hashes_changes_and_history(self):
        scratch = HERE.joinpath(".cache", "tmp")
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=scratch) as d:
            root = Path(d)
            root.joinpath("evals").mkdir()
            root.joinpath("data").mkdir()
            root.joinpath("data", "job.json").write_text("{}", encoding="utf-8")
            self.assertIsNone(freeze.changed("designs", root))
            freeze.freeze("designs", root=root)
            self.assertTrue(freeze.ready("designs", root))
            root.joinpath("data", "job.json").write_text('{"x": 1}', encoding="utf-8")
            self.assertEqual(freeze.changed("designs", root), [("data/job.json", "changed")])
            with self.assertRaises(SystemExit):
                freeze.freeze("designs", root=root)
            freeze.freeze("designs", again=True, root=root)
            data = json.loads(root.joinpath("evals", "frozen.json").read_text(encoding="utf-8"))
            self.assertEqual(len(data["history"]), 1)
            self.assertTrue(freeze.ready("designs", root))


if __name__ == "__main__":
    unittest.main()
