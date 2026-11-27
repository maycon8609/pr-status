#!/usr/bin/env bash
set -euo pipefail

BIN_DEST="$HOME/.local/bin/pr-status"
SKILL_DEST="$HOME/.gemini/config/skills/pr-status"

echo "=== Uninstalling pr-status ==="

if [ -L "$BIN_DEST" ]; then
  rm -f "$BIN_DEST"
  echo "✓ Removed executable link at $BIN_DEST."
  if [ -f "$BIN_DEST.bak" ]; then
    mv "$BIN_DEST.bak" "$BIN_DEST"
    echo "✓ Restored previous backup at $BIN_DEST."
  fi
fi

if [ -L "$SKILL_DEST" ]; then
  rm -f "$SKILL_DEST"
  echo "✓ Removed skill link at $SKILL_DEST."
fi

echo "Uninstallation complete."
