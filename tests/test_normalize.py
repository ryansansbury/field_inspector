"""Normalizing by kind, the edges the parity vectors carry to the page, and the rule that O and 0 never swap."""
import unittest

from engine import normalize as n

CASES = [
    ("code", "hpx-36 b2", "HPX36B2"),
    ("code", "HPX-36BO", "HPX36BO"),
    ("code", "HPX-36B0", "HPX36B0"),
    ("code", " -/ ", None),
    ("code", "МCА", "MCA"),
    ("code", "СА13-24А1", "CA1324A1"),
    ("volts", "208-230V", "208/230"),
    ("volts", "230/208", "208/230"),
    ("volts", "115V~", "115"),
    ("volts", "120/240", "120/240"),
    ("volts", "208/230-1-60", "208/230"),
    ("volts", "120 VAC 60 HZ", "120"),
    ("volts", "200A", None),
    ("volts", "60Hz", None),
    ("volts", "120.0 V", "120"),
    ("phase", "1PH", "1"),
    ("phase", "1Ø", "1"),
    ("phase", "single phase", "1"),
    ("phase", "3", "3"),
    ("phase", "THREE PHASE", "3"),
    ("phase", "208/230-1-60", "1"),
    ("phase", "1-3", None),
    ("phase", "230", None),
    ("amps", "18.60 A", "18.6"),
    ("amps", "25A", "25"),
    ("amps", "12.0", "12"),
    ("amps", ".5 A", "0.5"),
    ("amps", "14.1 / 82", None),
    ("amps", "none", None),
    ("capacity", "50 GAL.", "50 GAL"),
    ("capacity", "4500W", "4.5 KW"),
    ("capacity", "60,000 BTU/H", "60000 BTUH"),
    ("capacity", "60 MBH", "60000 BTUH"),
    ("capacity", "189 L 50 GAL", "50 GAL"),
    ("capacity", "1.5 TONS", "1.5 TON"),
    ("capacity", "1,440 WATTS", "1.44 KW"),
    ("capacity", "50", None),
    ("capacity", "7 LB", None),
    ("refrigerant", "R-454B", "R454B"),
    ("refrigerant", "r410a", "R410A"),
    ("refrigerant", "HFC-134a", "R134A"),
    ("refrigerant", "R-454B·7 LB 4 OZ", "R454B"),
    ("refrigerant", "REFRIGERANT", None),
    ("refrigerant", "R1234yf", "R1234YF"),
]


class Normalize(unittest.TestCase):
    def test_every_case(self):
        for kind, text, want in CASES:
            with self.subTest(kind=kind, text=text):
                self.assertEqual(n.canon(kind, text), want)

    def test_o_and_zero_never_swap(self):
        self.assertNotEqual(n.canon("code", "HPX-36BO"), n.canon("code", "HPX-36B0"))
        self.assertEqual(n.distance(n.canon("code", "HPX-36BO"), n.canon("code", "HPX-36B0")), 1)

    def test_numbers_and_shifts(self):
        self.assertEqual(n.number("018.60"), "18.6")
        self.assertEqual(n.number("."), None)
        self.assertEqual(n.shift("4500", -3), "4.5")
        self.assertEqual(n.shift("60", 3), "60000")
        self.assertEqual(n.shift("0.75", -3), "0.00075")
        self.assertEqual(n.drop_thousands("1,000,000 and 12,5"), "1000000 and 12,5")

    def test_pieces_pull_values_out_of_longer_words(self):
        self.assertEqual(n.pieces("volts", "208/230-1-60"), ["208/230"])
        self.assertEqual(n.pieces("phase", "208/230-1-60"), ["1"])
        self.assertEqual(n.pieces("amps", "14.1/82"), ["14.1", "82"])
        self.assertEqual(n.pieces("capacity", "50 GAL 4500 W"), ["50 GAL", "4.5 KW"])

    def test_distance(self):
        self.assertEqual(n.distance("DW24P1", "DW24P7"), 1)
        self.assertEqual(n.distance("", "AB"), 2)
        self.assertEqual(n.distance("ABC", "ABC"), 0)

    def test_label_words(self):
        self.assertEqual(n.words("MAX. FUSE OR CKT. BKR."), ["MAX", "FUSE", "OR", "CKT", "BKR"])
        self.assertEqual(n.words("V-PH-HZ"), ["V", "PH", "HZ"])
        self.assertEqual(n.words("M/N"), ["M", "N"])
        self.assertEqual(n.words("BTU/H"), ["BTU", "H"])

    def test_an_unknown_kind_fails(self):
        with self.assertRaises(ValueError):
            n.canon("serial", "X")


if __name__ == "__main__":
    unittest.main()
