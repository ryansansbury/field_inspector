"""The scorer on a small key: the stand-in scores perfectly, a wrong read the photo confirmed counts as past the line, a
wrong read sent to a person is caught, and a wrong verdict that skipped the person fails the decision bar."""
import copy
import unittest

from engine import rules
from evals import score

CFG = rules.load_config()
BARS = {"accuracy": 0.9, "past_line": 0, "missed_decisions": 0}


def field(value):
    return {"value": value, "canon": value}


def make_key():
    empty = {f: None for f in CFG["kinds"]}
    photos = {
        "p1": {"plate": "condenser", "shot": "straight", "split": "test",
               "fields": dict(empty, model=field("HPX36B2"), mca=field("18.6"), max_breaker=field("25"))},
        "p2": {"plate": "condenser", "shot": "glare", "split": "test",
               "fields": dict(empty, model=field("HPX36B2"), mca=field("18.6"), max_breaker=field("25"))},
        "p9": {"plate": "breaker-30", "shot": "straight", "split": "test", "fields": dict(empty, breaker=field("30"))},
        "p5": {"plate": "dryer", "shot": "angled", "split": "dev", "fields": dict(empty, model=field("DRY27E"))},
    }
    return {"photos": photos}


DESIGNS = {"plates": {"condenser": {"model": "HPX36B2", "breaker": "25", "checks": ["model", "breaker_max",
                                                                                   "breaker_min"]},
                      "breaker-30": {"checks": []}, "dryer": {"model": "DRY27E", "checks": ["model"]}}}
JOB = {"assets": [{"id": "condenser", "photo": "p1", "breaker_photo": "p9"}],
       "designs": {"condenser": {"model": "HPX36B2", "breaker": "30",
                                 "checks": ["model", "breaker_max", "breaker_min", "panel"]}}}


def stand_in(key):
    return {p: {"reads": {f: {"status": "read", "value": v["value"], "level": "found"}
                          for f, v in ph["fields"].items() if v}, "cost_usd": 0.0, "ms": 0}
            for p, ph in key["photos"].items()}


class Score(unittest.TestCase):
    def test_the_stand_in_scores_perfectly(self):
        key = make_key()
        out = score.score(key, DESIGNS, JOB, {"stand-in": stand_in(key)}, CFG, BARS)["stand-in"]
        for split in ("dev", "test", "job"):
            self.assertEqual(out[split]["fields"]["accuracy"], 1.0, split)
            self.assertEqual(out[split]["checks"]["missed"], 0, split)
            self.assertTrue(all(out[split]["bars"].values()), split)
        self.assertEqual(out["job"]["checks"]["agree"], 4)

    def test_a_confirmed_wrong_read_is_past_the_line_and_skips_the_person(self):
        key = make_key()
        view = stand_in(key)
        view["p2"]["reads"]["max_breaker"] = {"status": "read", "value": "35", "level": "found"}
        out = score.score(key, DESIGNS, JOB, {"m": view}, CFG, BARS)["m"]["test"]
        self.assertEqual(out["fields"]["wrong"], 1)
        self.assertEqual(out["line"]["partial"]["past"], 1)
        self.assertEqual(out["line"]["all"]["past"], 0)
        self.assertEqual(out["checks"]["missed"], 0, "both verdicts pass, since 25 fits under 35 and under 25")
        self.assertFalse(out["bars"]["past_line"])

    def test_a_wrong_verdict_that_skipped_the_person(self):
        key = make_key()
        view = stand_in(key)
        view["p2"]["reads"]["max_breaker"] = {"status": "read", "value": "20", "level": "found"}
        out = score.score(key, DESIGNS, JOB, {"m": view}, CFG, BARS)["m"]["test"]
        self.assertEqual(out["checks"]["missed"], 1)
        self.assertEqual(out["checks"]["missed_list"][0]["rule"], "breaker_max")
        self.assertFalse(out["bars"]["decisions"])
        view["p2"]["reads"]["max_breaker"]["level"] = "partial"
        out = score.score(key, DESIGNS, JOB, {"m": view}, CFG, BARS)["m"]["test"]
        self.assertEqual((out["checks"]["missed"], out["checks"]["caught"]), (0, 1))
        self.assertEqual(out["line"]["partial"]["past"], 0)

    def test_misses_false_reads_and_the_shot_breakdown(self):
        key = make_key()
        view = stand_in(key)
        view["p2"]["reads"]["model"] = {"status": "unreadable"}
        view["p2"]["reads"]["amps"] = {"status": "read", "value": "12", "level": "partial"}
        out = score.score(key, DESIGNS, JOB, {"m": view}, CFG, BARS)["m"]["test"]
        self.assertEqual((out["fields"]["miss"], out["fields"]["false"]), (1, 1))
        self.assertEqual(out["by_shot"]["glare"]["accuracy"], round(2 / 3, 3))
        self.assertEqual(out["by_shot"]["straight"]["accuracy"], 1.0)

    def test_the_job_catches_the_breaker_over_the_maximum(self):
        key = make_key()
        out = score.score(key, DESIGNS, JOB, {"s": stand_in(key)}, CFG, BARS)["s"]["job"]
        self.assertEqual(out["photos"], 2)
        job2 = copy.deepcopy(JOB)
        self.assertEqual(rules.evaluate(job2, {p: v["reads"] for p, v in stand_in(key).items()}, {}, "partial", CFG)
                         ["assets"]["condenser"]["state"], "fail")


if __name__ == "__main__":
    unittest.main()
