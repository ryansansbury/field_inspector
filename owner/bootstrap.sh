#!/bin/bash
# The owner's machine only. About three minutes the first time. It creates .venv with Homebrew's Python, installs
# Pillow, pillow-heif (iPhone photos arrive as HEIC) and the Vision bindings for the Mac's own text recognition, puts
# the fonts in place, and runs both self-tests on images they make themselves, so a problem shows up before any real
# photo is touched. The build itself needs only the standard library.
# Run from the build folder:   bash owner/bootstrap.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PY=""
for cand in /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.13 /usr/local/bin/python3.12 python3.13 python3.12; do
  if command -v "$cand" >/dev/null 2>&1; then
    PY="$(command -v "$cand")"
    break
  fi
done
if [ -z "$PY" ]; then
  echo "Installing Python 3.13 with Homebrew..."
  brew install python@3.13
  PY="$(brew --prefix)/bin/python3.13"
fi
echo "Using $PY ($("$PY" --version))"

if [ ! -x .venv/bin/python3 ]; then
  "$PY" -m venv .venv
fi
.venv/bin/python3 -m pip install --quiet --upgrade pip
.venv/bin/python3 -m pip install --quiet "pillow>=10.1" pillow-heif pyobjc-framework-Vision pyobjc-framework-Quartz

mkdir -p site/fonts
if [ -d reference/fonts ]; then
  cp reference/fonts/inter-latin.woff2 reference/fonts/jetbrains-mono-latin.woff2 site/fonts/
  cp reference/fonts/Inter-LICENSE.txt reference/fonts/JetBrainsMono-OFL.txt site/fonts/
fi

echo "Self-test: preparing a photo..."
.venv/bin/python3 owner/prepare.py --self-test
echo "Self-test: reading a plate with Vision..."
.venv/bin/python3 owner/ocr.py --self-test
echo "Ready. Next: bash owner/prepare.sh"
