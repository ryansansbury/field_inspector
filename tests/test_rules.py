"""The checks on the mini job: every outcome, a design edit moving a failure, the line moving work to a person, and the
person's accept, correct, approved equal and wrong unit."""
import copy
import unittest

from engine import rules
from tests.helpers import found, mini_job

CFG = rules.load_config()


def run(job=None, reads=None, person=None, line="partial"):
    j, r = mini_job()
    return rules.evaluate(job or j, reads or r, person or {}, line, CFG)


def status(out, asset, rule):
    return next(c for c in out["assets"][asset]["checks"] if c["rule"] == rule)


class States(unittest.TestCase):
    def test_a_fresh_job(self):
        out = run()
        self.assertEqual({a: v["state"] for a, v in out["assets"].items()},
                         {"heat-pump": "fail", "dishwasher": "person", "water-heater": "fail", "dryer": "pass"})
        self.assertEqual(out["counts"], {"pass": 1, "fail": 2, "person": 1, "reads": 14, "sent": 1})
        self.assertEqual(status(out, "heat-pump", "breaker_max")["why"], "over")
        self.assertEqual(status(out, "heat-pump", "panel")["status"], "pass")
        self.assertEqual(status(out, "dishwasher", "model")["status"], "review")
        self.assertEqual([q["type"] for q in out["queue"]], ["check", "read"])

    def test_the_check_names_every_value_and_where_it_came_from(self):
        c = status(run(), "heat-pump", "breaker_max")
        self.assertEqual(c["inputs"], [{"from": "design", "field": "breaker", "value": "30"},
                                       {"from": "photo", "photo": "p1", "field": "max_breaker", "value": "25",
                                        "level": "found"}])


class Edits(unittest.TestCase):
    def test_the_design_breaker_edit_moves_the_failure_to_the_panel(self):
        job, reads = mini_job()
        job["designs"]["heat-pump"]["breaker"] = "25 A"
        out = run(job, reads)
        self.assertEqual(status(out, "heat-pump", "breaker_max")["status"], "pass")
        self.assertEqual(status(out, "heat-pump", "panel")["status"], "fail")
        self.assertEqual(out["assets"]["heat-pump"]["state"], "fail")

    def test_the_capacity_edit_leaves_only_the_glare_read(self):
        job, reads = mini_job()
        job["designs"]["water-heater"]["capacity"] = "50 gallons"
        self.assertEqual(run(job, reads)["assets"]["water-heater"]["state"], "person")
        self.assertEqual(run(job, reads, line="missing")["assets"]["water-heater"]["state"], "pass")

    def test_every_read_goes_to_a_person_at_the_top_of_the_line(self):
        out = run(line="all")
        self.assertEqual(out["counts"]["sent"], out["counts"]["reads"])
        self.assertEqual(out["assets"]["heat-pump"]["state"], "person")


class Person(unittest.TestCase):
    def test_accept_and_correct(self):
        out = run(person={"reads": {"p3/model": {"action": "accept"}, "p1/max_breaker": {"action": "correct",
                                                                                          "value": "30A"}}})
        self.assertEqual(status(out, "heat-pump", "breaker_max")["status"], "pass")
        self.assertEqual(out["assets"]["heat-pump"]["state"], "pass")
        self.assertEqual(out["counts"]["sent"], 0)
        self.assertEqual(out["counts"]["reads"], 14)

    def test_approved_equal_and_wrong_unit(self):
        self.assertEqual(run(person={"checks": {"dishwasher/model": "approved"}})["assets"]["dishwasher"]["state"],
                         "pass")
        out = run(person={"checks": {"dishwasher/model": "wrong_unit"}})
        self.assertEqual((out["assets"]["dishwasher"]["state"], status(out, "dishwasher", "model")["why"]),
                         ("fail", "wrong_unit"))

    def test_an_approved_equal_in_the_design(self):
        job, reads = mini_job()
        job["designs"]["dishwasher"]["approved"] = ["DW-24P7"]
        self.assertEqual(status(run(job, reads), "dishwasher", "model")["why"], "approved")


class Edges(unittest.TestCase):
    def test_a_needed_read_marked_absent_waits_for_a_person(self):
        job, reads = mini_job()
        reads["p1"]["mca"] = {"status": "absent"}
        reads["p1"]["max_breaker"] = found("30")
        out = run(job, reads)
        self.assertEqual(status(out, "heat-pump", "breaker_min")["status"], "unknown")
        self.assertEqual(out["assets"]["heat-pump"]["state"], "person")
        confirmed = run(job, reads, person={"reads": {"p1/mca": {"action": "accept"}}})
        self.assertEqual(status(confirmed, "heat-pump", "breaker_min")["status"], "unknown")

    def test_an_unreadable_read_is_settled_only_by_a_correction(self):
        """Accepting a read the AI couldn't make out would say the plate doesn't print it and let the check pass
        unseen, so it keeps waiting until a person types the value."""
        job, reads = mini_job()
        reads["p4"]["model"] = {"status": "unreadable"}
        accepted = run(job, reads, person={"reads": {"p4/model": {"action": "accept"}}})
        self.assertEqual((status(accepted, "dryer", "model")["status"], accepted["assets"]["dryer"]["state"]),
                         ("unknown", "person"))
        fixed = run(job, reads, person={"reads": {"p4/model": {"action": "correct", "value": "DRY-27E"}}})
        self.assertEqual((status(fixed, "dryer", "model")["status"], fixed["assets"]["dryer"]["state"]), ("pass", "pass"))

    def test_a_fail_resting_on_a_waiting_read_stays_blue(self):
        job, reads = mini_job()
        reads["p1"]["max_breaker"] = found("25", "partial")
        out = run(job, reads)
        self.assertEqual(status(out, "heat-pump", "breaker_max")["waits"], ["p1/max_breaker"])
        self.assertEqual(out["assets"]["heat-pump"]["state"], "person")

    def test_breaker_limits_at_under_and_over(self):
        job, reads = mini_job()
        for breaker, want in (("25", "pass"), ("24.9", "pass"), ("25.1", "fail")):
            job["designs"]["heat-pump"]["breaker"] = breaker
            self.assertEqual(status(run(job, reads), "heat-pump", "breaker_max")["status"], want, breaker)
        for breaker, want in (("18.6", "pass"), ("18.5", "fail")):
            job["designs"]["heat-pump"]["breaker"] = breaker
            self.assertEqual(status(run(job, reads), "heat-pump", "breaker_min")["status"], want, breaker)

    def test_volts_classes_and_phase(self):
        job, reads = mini_job()
        self.assertEqual(status(run(job, reads), "dryer", "volts")["status"], "pass")
        reads["p4"]["volts"] = found("120")
        job2 = copy.deepcopy(job)
        job2["designs"]["dryer"]["volts"] = "240"
        self.assertEqual(status(run(job2, reads), "dryer", "volts")["why"], "volts")
        reads["p1"]["phase"] = found("3")
        self.assertEqual(status(run(job, reads), "heat-pump", "volts")["why"], "phase")

    def test_unreadable_photo(self):
        job, reads = mini_job()
        job["designs"]["dryer"]["checks"].append("readable")
        reads["p4"] = {"model": {"status": "unreadable"}}
        out = run(job, reads)
        self.assertEqual(status(out, "dryer", "readable")["status"], "fail")


if __name__ == "__main__":
    unittest.main()
