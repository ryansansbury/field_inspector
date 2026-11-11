#!/bin/bash
# The owner's machine only. About a minute. Reads the text on every photo in data/photos/ with the Mac's own Vision
# framework into data/ocr/, then runs the privacy scan. The photos are synthetic, drawn by generate/render.py, so this
# is the only step they need before the AI runs. (Real photos would go through owner/prepare.sh and the verification
# page first, and owner/README.md describes that path.)
# Run from the build folder:   bash owner/ocr.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python3 ]; then
  echo "Run bash owner/bootstrap.sh first."
  exit 1
fi
.venv/bin/python3 owner/ocr.py
.venv/bin/python3 engine/privacy.py
echo
echo "Done. The text is read."
