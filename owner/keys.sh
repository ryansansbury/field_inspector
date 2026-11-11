#!/bin/bash
# The owner's machine only. Saves the API keys in the macOS Keychain under this project's own item names,
# field-inspector-anthropic and field-inspector-openai. Keys never go in a file, and this never prints one.
#
#   bash owner/keys.sh --from PREFIX            copies the keys another project saved as PREFIX-anthropic and
#                                               PREFIX-openai
#   bash owner/keys.sh --from PREFIX anthropic  copies only that one (the Call Companion kept its Anthropic key as
#                                               policy-reconciler-anthropic)
#   bash owner/keys.sh anthropic                one key, after copying it to the clipboard
#   bash owner/keys.sh openai
#
# A typed Keychain prompt can cut a long key short, which is why a new key comes from the clipboard.
set -euo pipefail

save() {
  local vendor="$1" key="$2"
  if [ ${#key} -lt 20 ]; then
    echo "The $vendor key doesn't look like a key, so it wasn't saved."
    return 1
  fi
  security add-generic-password -U -a "$USER" -s "field-inspector-$vendor" -w "$key"
  echo "Saved the $vendor key as field-inspector-$vendor (${#key} characters)."
}

case "${1:-}" in
  --from)
    prefix="${2:-}" only="${3:-}"
    if [ -z "$prefix" ] || { [ -n "$only" ] && [ "$only" != anthropic ] && [ "$only" != openai ]; }; then
      echo "Usage: bash owner/keys.sh --from PREFIX, or bash owner/keys.sh --from PREFIX anthropic|openai"
      exit 1
    fi
    for vendor in ${only:-anthropic openai}; do
      if key="$(security find-generic-password -s "$prefix-$vendor" -w 2>/dev/null)"; then
        save "$vendor" "$key"
      else
        echo "There's no Keychain item named $prefix-$vendor, so the $vendor key was skipped."
      fi
    done
    ;;
  anthropic|openai)
    save "$1" "$(pbpaste)"
    printf '' | pbcopy
    echo "Cleared the clipboard, so the key isn't left on it."
    ;;
  *)
    echo "Usage: bash owner/keys.sh --from PREFIX, or bash owner/keys.sh anthropic|openai"
    exit 1
    ;;
esac
