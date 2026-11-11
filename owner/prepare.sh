#!/bin/bash
# The owner's machine only. The photos, in two parts with the verification page between them.
#
#   bash owner/prepare.sh          part one and the draft read, about two minutes: every photo upright, stripped and
#                                  sized into data/unmasked/, then the text recognition drafts each value and proposes
#                                  the masks. Next comes bash owner/verify.sh, in a block of its own.
#   bash owner/prepare.sh --mask   after the verification page, about two minutes: the masks into data/photos/, the
#                                  unmasked copies deleted, the text recognition again on what's published, the
#                                  privacy scan, and the contact sheets for review.
#
# Run from the build folder. Your raw photos stay in ~/Pictures/field_inspector_raw/ and never enter the repo.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
if [ ! -x "$PY" ]; then
  echo "Run bash owner/bootstrap.sh first."
  exit 1
fi

if [ "${1:-}" = "--mask" ]; then
  "$PY" owner/prepare.py --mask
  "$PY" owner/ocr.py
  "$PY" engine/privacy.py
  echo
  echo "Done. The masked photos are in."
else
  "$PY" owner/prepare.py "$@"
  "$PY" owner/ocr.py --draft
  echo
  echo "Next, in a block of its own: bash owner/verify.sh"
fi
