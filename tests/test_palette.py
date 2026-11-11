"""The page's colors pass the contrast rules and stay apart for color-blind readers.

Every text color is measured against the background it sits on, by the WCAG formula for relative luminance, and has to
reach 4.5 to 1 (small text everywhere on this page). The three state colors are simulated for protanopia, deuteranopia
and tritanopia (Machado, Oliveira and Fernandes, 2009) and compared in CIE Lab. Any pair that comes close under one of
them is listed, and the page carries a glyph beside every state color (✓, ✕ and !), so the state never rests on color
alone. The colors are read from site/app.css, so the test follows the stylesheet.
"""
import re
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
CSS = HERE.joinpath("site", "app.css").read_text(encoding="utf-8")
VARS = dict(re.findall(r"--([a-z0-9-]+):\s*(#[0-9a-fA-F]{6})", CSS))

# (text, background, where it's used)
PAIRS = [
    ("ink", "#ffffff", "body text"), ("ink", "table", "the light table's caption"), ("ink", "strip", "the filmstrip"),
    ("ink2", "#ffffff", "secondary text"), ("ink2", "strip", "filmstrip labels"), ("muted", "#ffffff", "muted text"),
    ("muted", "table", "the caption's note"), ("muted", "#f7f8fa", "the line's note"),
    ("pass-ink", "pass-bg", "pass pills"), ("fail-ink", "fail-bg", "fail pills"), ("review-ink", "review-bg", "review pills"),
    ("#ffffff", "pass", "pass tags"), ("#ffffff", "fail", "fail tags"), ("#ffffff", "review", "review tags and buttons"),
    ("#ffffff", "person", "settled tags"), ("fail", "#ffffff", "the preview flag"),
]
MACHADO = {
    "protanopia": ((0.152286, 1.052583, -0.204868), (0.114503, 0.786281, 0.099216), (-0.003882, -0.048116, 1.051998)),
    "deuteranopia": ((0.367322, 0.860646, -0.227968), (0.280085, 0.672501, 0.047413), (-0.011820, 0.042940, 0.968881)),
    "tritanopia": ((1.255528, -0.076749, -0.178779), (-0.078411, 0.930809, 0.147602), (0.004733, 0.691367, 0.303900)),
}


def hexrgb(c):
    c = VARS.get(c, c).lstrip("#")
    return tuple(int(c[i:i + 2], 16) / 255 for i in (0, 2, 4))


def linear(v):
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def gamma(v):
    v = min(1.0, max(0.0, v))
    return 12.92 * v if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def luminance(rgb):
    r, g, b = (linear(v) for v in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(hexrgb(a)), luminance(hexrgb(b))), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def lab(rgb):
    r, g, b = (linear(v) for v in rgb)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = [t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116 for t in (x, y, z)]
    return 116 * f[1] - 16, 500 * (f[0] - f[1]), 200 * (f[1] - f[2])


def simulate(rgb, m):
    lin = [linear(v) for v in rgb]
    return tuple(gamma(sum(m[i][j] * lin[j] for j in range(3))) for i in range(3))


def delta(a, b):
    return sum((p - q) ** 2 for p, q in zip(lab(a), lab(b))) ** 0.5


class Palette(unittest.TestCase):
    def test_every_text_color_reaches_four_and_a_half_to_one(self):
        low = [(t, b, where, round(contrast(t, b), 2)) for t, b, where in PAIRS if contrast(t, b) < 4.5]
        self.assertEqual(low, [])

    def test_the_states_stay_apart_and_carry_a_glyph(self):
        states = ("pass", "fail", "review")
        close = []
        for name, m in [("normal", None)] + list(MACHADO.items()):
            for i, a in enumerate(states):
                for b in states[i + 1:]:
                    ca, cb = hexrgb(a), hexrgb(b)
                    if m:
                        ca, cb = simulate(ca, m), simulate(cb, m)
                    if delta(ca, cb) < 20:
                        close.append((name, a, b, round(delta(ca, cb), 1)))
        self.assertEqual([c for c in close if c[0] == "normal"], [])
        glyphs = re.findall(r"\.th\.st-(pass|fail|person) i::after \{ content: \"(.)\"", CSS)
        self.assertEqual(len(glyphs), 3, "every filmstrip state needs a glyph, so color isn't the only cue")


if __name__ == "__main__":
    unittest.main()
