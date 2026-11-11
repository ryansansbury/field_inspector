"""Every check the build relies on, in one command.

    python3 tests/run.py          everything, quietly
    python3 tests/run.py -v       with each test's name

The unit tests, then the node checks on the built page and the parity vectors. Exits 1 if anything fails.
"""
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    loader = unittest.defaultTestLoader
    suite = loader.discover(str(HERE.joinpath("tests")), top_level_dir=str(HERE))
    ok = unittest.TextTestRunner(verbosity=2 if "-v" in argv else 1).run(suite).wasSuccessful()
    for script in sorted(HERE.joinpath("tests", "js").glob("check_*.js")):
        ok &= subprocess.run(["node", str(script)], cwd=HERE).returncode == 0
    print("All checks pass." if ok else "Something failed.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
