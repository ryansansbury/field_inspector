"""The confirmation step on sketched plates: found by a label or a unit, partly found for the near misses, and never found
for a value that sits by another field's label."""
import unittest

from engine import confirm as cf
from tests.helpers import APPLIANCE, BREAKERS, HVAC, H, W, ocr, read

FIELDS = cf.load_fields()


def check(rows, field, r, **kw):
    return cf.confirm(cf.Photo(ocr(rows, **kw), FIELDS), field, r)


class Found(unittest.TestCase):
    def test_a_model_by_its_label(self):
        got = check(HVAC, "model", read("HPX-36B2", "MODEL NO."))
        self.assertEqual((got["level"], got["why"]), ("found", "label"))
        self.assertFalse(got["approx"])
        self.assertAlmostEqual(got["box"][0], 400 / W, places=3)

    def test_volts_and_phase_out_of_one_combined_word(self):
        volts, phase = check(HVAC, "volts", read("208/230")), check(HVAC, "phase", read("1"))
        self.assertEqual((volts["level"], phase["level"]), ("found", "found"))
        word = 400 / W, (400 + 12 * 12) / W
        self.assertAlmostEqual(volts["box"][0], word[0], places=3)
        self.assertAlmostEqual(volts["box"][2], word[0] + (word[1] - word[0]) * 7 / 12, places=3)
        self.assertAlmostEqual(phase["box"][0], word[0] + (word[1] - word[0]) * 8 / 12, places=3)
        self.assertLess(phase["box"][2], word[1])

    def test_the_breaker_numbers_by_their_labels(self):
        self.assertEqual(check(HVAC, "mca", read("18.6"))["level"], "found")
        self.assertEqual(check(HVAC, "max_breaker", read("25 A"))["level"], "found")
        self.assertEqual(check(HVAC, "refrigerant", read("R-454B"))["level"], "found")

    def test_a_label_in_look_alike_letters(self):
        """The recognizer sometimes returns a Latin label in look-alike letters from another alphabet."""
        got = check([(100, [(100, "\u041cC\u0410"), (400, "15.2")])], "mca", read("15.2"))
        self.assertEqual((got["level"], got["why"]), ("found", "label"))

    def test_each_row_follows_its_own_tilt(self):
        """An angled shot whose far rows slant more than its near ones. The photo's overall tilt would put the model
        number on the serial number's row, so each row follows the slant of its own lines."""
        rows = [(100, [(100, "OUTDOOR UNIT")], 1.0, -0.04),
                (160, [(100, "MODEL NO.")]),
                (220, [(100, "SERIAL NO.")]),
                (280, [(100, "MIN. CIRCUIT AMPACITY")], 1.0, -0.08),
                (520, [(100, "USE COPPER CONDUCTORS ONLY")], 1.0, -0.16),
                (580, [(100, "SUITABLE FOR OUTDOOR USE")], 1.0, -0.17),
                (640, [(100, "SEE INSTALLATION INSTRUCTIONS")], 1.0, -0.18),
                (126, [(700, "HPX-36B2")])]
        page = cf.Photo(ocr(rows), FIELDS)
        self.assertLess(page.slope, -0.15)
        got = cf.confirm(page, "model", read("HPX-36B2"))
        self.assertEqual((got["level"], got["why"]), ("found", "label"))

    def test_units_confirm_an_unlabeled_appliance_line(self):
        self.assertEqual(check(APPLIANCE, "volts", read("120V"))["why"], "unit")
        self.assertEqual(check(APPLIANCE, "amps", read("12.0 A"))["why"], "unit")
        self.assertEqual(check(APPLIANCE, "model", read("DW-24P0"))["level"], "found")


class NeverFoundByTheWrongLabel(unittest.TestCase):
    def test_a_minimum_circuit_ampacity_read_as_the_largest_breaker(self):
        got = check(HVAC, "max_breaker", read("18.6"))
        self.assertEqual((got["level"], got["why"]), ("partial", "away"))

    def test_a_breaker_size_read_as_the_units_amps(self):
        self.assertEqual(check(HVAC, "amps", read("25"))["why"], "away")
        self.assertEqual(check(HVAC, "amps", read("14.1"))["why"], "away")

    def test_the_ai_cannot_label_its_way_past(self):
        got = check(HVAC, "max_breaker", read("18.6", "MIN. CIRCUIT AMPACITY"))
        self.assertEqual(got["why"], "away")

    def test_the_ai_label_helps_when_it_belongs_to_nothing_else(self):
        rows = [(200, [(100, "FULL LOAD"), (400, "6.2")])]
        self.assertEqual(check(rows, "amps", read("6.2"))["why"], "away")
        self.assertEqual(check(rows, "amps", read("6.2", "FULL LOAD"))["why"], "label")


class PartlyAndNotFound(unittest.TestCase):
    def test_one_character_off(self):
        got = check(HVAC, "model", read("HPX-36B7"))
        self.assertEqual((got["level"], got["why"], got["seen"]), ("partial", "one_off", "HPX-36B2"))

    def test_o_against_zero_is_never_found(self):
        got = check(APPLIANCE, "model", read("DW-24PO"))
        self.assertEqual((got["level"], got["why"]), ("partial", "one_off"))

    def test_numbers_are_never_one_character_off(self):
        self.assertEqual(check(HVAC, "max_breaker", read("35"))["level"], "missing")

    def test_a_low_confidence_line(self):
        rows = [(100, [(100, "MODEL"), (300, "HPX-36B2")], 0.3)]
        self.assertEqual(check(rows, "model", read("HPX-36B2"))["why"], "low")

    def test_a_value_pieced_across_two_lines(self):
        rows = [(100, [(100, "MODEL NO."), (400, "HPX-36")]), (130, [(400, "B2")])]
        got = check(rows, "model", read("HPX-36B2"))
        self.assertEqual((got["level"], got["why"]), ("partial", "split"))

    def test_joined_words_on_one_line_are_found(self):
        rows = [(100, [(100, "MODEL NO."), (400, "HPX-36 B2")])]
        self.assertEqual(check(rows, "model", read("HPX-36B2"))["level"], "found")

    def test_unreadable_and_absent(self):
        box = [0.1, 0.1, 0.2, 0.2]
        got = check(HVAC, "model", read(None, box=box, status="unreadable"))
        self.assertEqual((got["level"], got["approx"], got["box"]), ("missing", True, box))
        self.assertIsNone(check(HVAC, "capacity", read(None, status="absent")))

    def test_not_on_the_photo_keeps_the_ai_box_as_approximate(self):
        got = check(HVAC, "capacity", read("50 GAL", box=[0.5, 0.5, 0.6, 0.55]))
        self.assertEqual((got["level"], got["approx"]), ("missing", True))


class Breakers(unittest.TestCase):
    def test_the_one_rating_inside_the_ai_box(self):
        x0 = 770 / W
        box = [x0 - 0.005, 560 / H, x0 + 0.02, 590 / H]
        self.assertEqual(check(BREAKERS, "breaker", read("30", box=box))["level"], "found")

    def test_two_of_the_same_rating_in_the_middle_is_ambiguous(self):
        rows = [(560, [(500, "20"), (770, "30"), (1000, "20")])]
        self.assertEqual(check(rows, "breaker", read("20"))["why"], "ambiguous")

    def test_a_rating_only_outside_the_box_is_away(self):
        box = [0.9, 0.9, 0.95, 0.95]
        self.assertEqual(check(BREAKERS, "breaker", read("30", box=box))["why"], "away")


class Draft(unittest.TestCase):
    def test_the_draft_reads_every_labeled_field(self):
        got = cf.draft(cf.Photo(ocr(HVAC), FIELDS))
        want = {"model": "HPX-36B2", "volts": "208/230", "phase": "1", "mca": "18.6", "max_breaker": "25",
                "refrigerant": "R454B"}
        self.assertEqual({k: v["value"] for k, v in got.items()}, want)

    def test_the_draft_reads_an_appliance_by_units(self):
        got = cf.draft(cf.Photo(ocr(APPLIANCE), FIELDS))
        self.assertEqual(got["volts"]["value"], "120")
        self.assertEqual(got["amps"]["value"], "12")
        self.assertEqual(got["model"]["value"], "DW-24P0")

    def test_the_draft_reads_the_centered_breaker(self):
        got = cf.draft(cf.Photo(ocr(BREAKERS), FIELDS))
        self.assertEqual(got["breaker"]["value"], "30")


if __name__ == "__main__":
    unittest.main()
