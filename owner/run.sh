#!/bin/bash
# The owner's machine only. The AI reads in two runs, with a review between them. Each run is safe to
# start again, since a read already recorded with today's prompt is skipped.
#
#   bash owner/run.sh 1   The tuning round, about five minutes: a dry run with the stand-in (no model, no cost),
#                         then the default model on the dev photos and their scores. Then the prompt is
#                         tuned and either frozen or sent back for run 2's dev round.
#   bash owner/run.sh 2   Once the prompt is ready, about fifteen minutes and unattended: the dev
#                         round again if the prompt changed (and the freeze if it did no worse), then every model on
#                         every photo, the real build and the screenshots.
#
# Run from the build folder. The keys come from this project's Keychain items, saved by owner/keys.sh, and are never
# printed.
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python3
if [ ! -x "$PY" ]; then
  echo "Run bash owner/bootstrap.sh first."
  exit 1
fi
say() { printf '\n== %s\n' "$*"; }
ready() {
  "$PY" -c "import sys; sys.path.insert(0, '.'); from evals import freeze; sys.exit(0 if freeze.ready('$1') else 1)"
}

one() {
  for stage in photos designs; do
    if ! ready "$stage"; then
      echo "The $stage stage isn't frozen yet, so no model runs."
      exit 1
    fi
  done
  if ! security find-generic-password -s field-inspector-anthropic >/dev/null 2>&1; then
    echo "There's no Keychain item named field-inspector-anthropic yet. Copy it, then run bash owner/keys.sh anthropic."
    exit 1
  fi
  say "A dry run with the stand-in, with no model and no cost"
  "$PY" owner/record_ai_runs.py --split dev --stand-in
  say "The tuning round: the default model on the dev photos"
  "$PY" owner/record_ai_runs.py --split dev
  "$PY" evals/score.py
  "$PY" evals/tuning.py
  echo
  echo "Run 1 is done. The tuning round is recorded."
}

two() {
  if ! ready prompts; then
    say "The dev round again, on the revised prompt"
    "$PY" owner/record_ai_runs.py --split dev
    "$PY" evals/score.py
    "$PY" evals/tuning.py --freeze
  fi
  if ! security find-generic-password -s field-inspector-openai >/dev/null 2>&1; then
    echo "There's no Keychain item named field-inspector-openai, so GPT-6 Luna sits out."
  fi
  say "Every model on every photo"
  if ! "$PY" owner/record_ai_runs.py --split all --models compare; then
    echo "Some reads stopped, as listed above. Running bash owner/run.sh 2 again picks up where they left off."
  fi
  say "Every model's scores"
  "$PY" evals/score.py
  if [ -f config/names.json ]; then
    say "The real page and its screenshots"
    bash owner/screenshots.sh
    echo
    echo "Run 2 is done. The reads and the screenshots are in."
  else
    echo
    echo "Run 2 is done. The real page waits for config/names.json from the names check, so its screenshots"
    echo "wait too. The reads are in."
  fi
}

case "${1:-}" in
  1) one ;;
  2) two ;;
  *) echo "Usage: bash owner/run.sh 1|2   (see the top of this file)"; exit 1 ;;
esac
