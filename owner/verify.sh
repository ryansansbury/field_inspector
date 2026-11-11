#!/bin/bash
# The owner's machine only. The verification page, about 25 minutes. It opens in your browser on 127.0.0.1
# at a free port and saves every change as you go. It runs until Control-C, so start it in a block of its own, and stop
# it once the page says every photo is settled.
# Run from the build folder:   bash owner/verify.sh
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/python3 ]; then
  echo "Run bash owner/bootstrap.sh first."
  exit 1
fi
.venv/bin/python3 owner/verify.py
