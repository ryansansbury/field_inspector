"""The dress rehearsal of the real build (tests/rehearse.py) passes: the real build path on rehearsal recordings, the
node click-through on the model the page opens with, the export's checks, and the planted mistakes scored the way the
method says they should be."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


class Rehearsal(unittest.TestCase):
    def test_the_real_build_path_holds_up(self):
        r = subprocess.run([sys.executable, str(HERE.joinpath("tests", "rehearse.py"))], cwd=HERE, capture_output=True,
                           text=True)
        self.assertEqual(r.returncode, 0, r.stdout[-800:] + r.stderr[-800:])
        out = json.loads(r.stdout)
        self.assertTrue(out["click_through_ok"], out["failures"])
        if HERE.joinpath("tools", "export_public.py").exists():
            self.assertIn("every check clean", out["export"])
        else:
            self.assertTrue(out["export"].startswith("skipped"), out["export"])
        planted, clean = out["test"]["claude-haiku"], out["test"]["claude-sonnet"]
        self.assertEqual(clean, {"accuracy": 1.0, "past_line": 0, "caught": 0, "missed": 0})
        self.assertEqual((planted["past_line"], planted["caught"], planted["missed"]), (1, 1, 0),
                         "the confirmed misread is past the line, the near miss is caught, and the design check still "
                         "sends the confirmed misread to a person")


if __name__ == "__main__":
    unittest.main()
