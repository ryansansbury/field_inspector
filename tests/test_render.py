"""The synthetic photos' specs and the renderer's geometry: every value reads as its kind, the split follows the plan's
rules, the job carries its planted outcomes, and the perspective math lands every corner where it should."""
import json
import random
import unittest
from pathlib import Path

from engine import confirm, normalize as norm, rules
from generate import render

HERE = Path(__file__).resolve().parent.parent
SPECS = json.loads(HERE.joinpath("generate", "plates.json").read_text(encoding="utf-8"))
CFG = rules.load_config()


class Geometry(unittest.TestCase):
    def test_the_perspective_map_lands_every_corner(self):
        src = [(0, 0), (100, 0), (100, 50), (0, 50)]
        dst = [(10, 20), (130, 15), (120, 90), (5, 70)]
        h = render.homography(src, dst)
        for (x, y), (u, v) in zip(src, dst):
            got = render.apply(h, x, y)
            self.assertAlmostEqual(got[0], u, places=6)
            self.assertAlmostEqual(got[1], v, places=6)

    def test_a_box_carries_into_fractions(self):
        h = render.homography([(0, 0), (10, 0), (10, 10), (0, 10)], [(0, 0), (20, 0), (20, 20), (0, 20)])
        self.assertEqual(render.carry(h, (1, 2, 3, 4), (40, 40)), [0.05, 0.1, 0.15, 0.2])

    def test_straight_shots_stay_square_and_angled_ones_pull(self):
        for shot, lo, hi in (("straight", 0.0, 0.05), ("angled", 0.12, 0.3)):
            pts = render.quad(1000, 600, shot, random.Random(3), 0.9)
            left, right = abs(pts[3][1] - pts[0][1]), abs(pts[2][1] - pts[1][1])
            pull = abs(left - right) / max(left, right)
            self.assertTrue(lo <= pull <= hi, (shot, pull))


class Specs(unittest.TestCase):
    def test_every_value_reads_as_its_kind(self):
        for s in SPECS["subjects"]:
            for field, value in render.field_values(s).items():
                if value is not None:
                    self.assertIsNotNone(norm.canon(render.KINDS[field], value), (s["id"], field, value))
            for r in s.get("rows", []):
                for field, printed in (r.get("fields") or {}).items():
                    self.assertIn(printed, r["value"], (s["id"], field))

    def test_the_split_follows_the_plan(self):
        dev = [s for s in SPECS["subjects"] if s["split"] == "dev"]
        values = {s["id"]: render.field_values(s) for s in SPECS["subjects"]}
        self.assertTrue(any(values[s["id"]]["mca"] and values[s["id"]]["max_breaker"] for s in dev))
        self.assertTrue(any(s["kind"] == "breaker" for s in dev))
        test_plates = [s for s in SPECS["subjects"] if s["split"] == "test" and s["kind"] != "breaker"]
        self.assertGreaterEqual(len(test_plates), 8)
        job = {a["plate"] for a in SPECS["job"]["assets"]} | {a.get("breaker") for a in SPECS["job"]["assets"]} - {None}
        self.assertFalse(job & {s["id"] for s in dev}, "the job's photos come from the test plates")

    def test_every_check_is_a_rule_and_the_job_points_at_real_shots(self):
        by_id = {s["id"]: s for s in SPECS["subjects"]}
        for s in SPECS["subjects"]:
            self.assertTrue(set(s["design"]["checks"]) <= set(CFG["rules"]), s["id"])
        for a in SPECS["job"]["assets"]:
            self.assertLess(a["shot"], len(by_id[a["plate"]]["shots"]))
            if a.get("breaker"):
                self.assertEqual(by_id[a["breaker"]]["kind"], "breaker")

    def test_the_job_carries_its_planted_outcomes(self):
        by_id = {s["id"]: s for s in SPECS["subjects"]}
        job = {"assets": [], "designs": {}}
        reads = {}
        for a in SPECS["job"]["assets"]:
            pid, asset = f"{a['plate']}-photo", {"id": a["id"], "photo": f"{a['plate']}-photo"}
            reads[pid] = {f: {"status": "read", "value": v, "level": "found"}
                          for f, v in render.field_values(by_id[a["plate"]]).items() if v}
            design = dict(by_id[a["plate"]]["design"], checks=list(by_id[a["plate"]]["design"]["checks"]))
            if a.get("breaker"):
                asset["breaker_photo"] = f"{a['breaker']}-photo"
                reads[asset["breaker_photo"]] = {"breaker": {"status": "read", "value": by_id[a["breaker"]]["breaker"]["rating"],
                                                             "level": "found"}}
                design["checks"].append("panel")
            job["assets"].append(asset)
            job["designs"][a["id"]] = design
        reads["dryer-photo"]["model"]["level"] = "missing"
        out = rules.evaluate(job, reads, {}, "partial", CFG)
        states = {k: v["state"] for k, v in out["assets"].items()}
        self.assertEqual(states.pop("heat-pump"), "fail")
        self.assertEqual(states.pop("water-heater"), "fail")
        self.assertEqual(states.pop("dryer"), "person")
        self.assertEqual(states.pop("dishwasher"), "person")
        self.assertEqual(set(states.values()), {"pass"}, states)
        check = next(c for c in out["assets"]["heat-pump"]["checks"] if c["rule"] == "breaker_max")
        self.assertEqual((check["status"], check["why"]), ("fail", "over"))

    def test_the_minimum_fail_sits_in_a_test_design(self):
        s = next(s for s in SPECS["subjects"] if s["id"] == "heat-pump-water-heater")
        self.assertLess(float(s["design"]["breaker"]), float(render.field_values(s)["mca"]))
        self.assertEqual(s["split"], "test")


@unittest.skipUnless(HERE.joinpath("data", "key", "key.json").exists(), "the photos haven't been rendered yet")
class Rendered(unittest.TestCase):
    def test_the_key_matches_the_specs_and_every_box_is_sane(self):
        key = json.loads(HERE.joinpath("data", "key", "key.json").read_text(encoding="utf-8"))
        by_id = {s["id"]: s for s in SPECS["subjects"]}
        self.assertEqual(len(key["photos"]), sum(len(s["shots"]) for s in SPECS["subjects"]))
        for pid, p in key["photos"].items():
            want = render.field_values(by_id[p["plate"]])
            self.assertEqual({f: (v or {}).get("value") for f, v in p["fields"].items()}, want, pid)
            for f, v in p["fields"].items():
                if v:
                    self.assertIn("box", v, (pid, f))
                    b = v["box"]
                    self.assertTrue(0 <= b[0] < b[2] <= 1 and 0 <= b[1] < b[3] <= 1, (pid, f, b))

    def test_the_planted_outcomes_hold_on_the_recognized_text(self):
        """A reader that gets every value right, confirmed against the photos' real text recognition, still lands each
        asset where the plan put it. So the glare really hides the dryer's model from the recognizer, and the rest
        confirm."""
        key = json.loads(HERE.joinpath("data", "key", "key.json").read_text(encoding="utf-8"))
        job = json.loads(HERE.joinpath("data", "job.json").read_text(encoding="utf-8"))
        shas = {e["id"]: e["sha256"] for e in json.loads(HERE.joinpath("data", "photos", "manifest.json")
                                                         .read_text(encoding="utf-8"))["photos"]}
        fields, reads = confirm.load_fields(), {}
        for a in job["assets"]:
            for pid in [a["photo"]] + ([a["breaker_photo"]] if a.get("breaker_photo") else []):
                path = HERE.joinpath("data", "ocr", f"{pid}.json")
                ocr = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
                if ocr.get("sha256") != shas[pid]:
                    self.skipTest(f"the text recognition is older than {pid}, so run owner/ocr.sh")
                page, reads[pid] = confirm.Photo(ocr, fields), {}
                for f, v in key["photos"][pid]["fields"].items():
                    if v:
                        read = {"status": "read", "value": v["value"], "box": v["box"]}
                        reads[pid][f] = dict(read, level=confirm.confirm(page, f, read)["level"])
        out = rules.evaluate(job, reads, {}, "partial", CFG)
        states = {k: v["state"] for k, v in out["assets"].items()}
        want = {"heat-pump": "fail", "water-heater": "fail", "dryer": "person", "dishwasher": "person"}
        self.assertEqual(states, {k: want.get(k, "pass") for k in states})


if __name__ == "__main__":
    unittest.main()
