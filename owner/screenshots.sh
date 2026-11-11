#!/bin/bash
# The owner's machine only. A few minutes. Builds the page, opens it in headless Chrome with a fresh profile from the
# file system and from a server on 127.0.0.1, takes every asset, control, tour step and phone screen, and checks the line
# rule, overlaps, console errors and network requests. Results land in owner/out/.
#
#   bash owner/screenshots.sh              the real page
#   bash owner/screenshots.sh --preview    the preview on the drawn plates, for an early look at the layout
#
# Run from the build folder.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
[ -x "$PY" ] || PY=python3
"$PY" build.py "$@"
"$PY" owner/browser_check.py
