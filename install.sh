#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_SRC="$DIR/bin/pr-status"
BIN_DEST="$HOME/.local/bin/pr-status"
SKILL_SRC="$DIR/skills/pr-status"
SKILL_DEST="$HOME/.gemini/config/skills/pr-status"

echo "=== Installing pr-status ==="

# 1. Check prerequisites
if ! command -v python3 &>/dev/null; then
  echo "Error: Python 3 is required." >&2
  exit 1
fi

if ! python3 -c 'import sys; assert sys.version_info >= (3, 8)' 2>/dev/null; then
  echo "Error: Python 3.8 or higher is required." >&2
  exit 1
fi

if ! command -v gh &>/dev/null; then
  echo "Error: GitHub CLI ('gh') is required. Install from https://cli.github.com." >&2
  exit 1
fi

# 2. Install executable in ~/.local/bin
mkdir -p "$HOME/.local/bin"
if [ -e "$BIN_DEST" ] && [ ! -L "$BIN_DEST" ]; then
  echo "Backing up existing file to $BIN_DEST.bak..."
  mv "$BIN_DEST" "$BIN_DEST.bak"
fi

chmod +x "$BIN_SRC" "$DIR/skills/pr-status/scripts/audit_prs.py"
ln -sf "$BIN_SRC" "$BIN_DEST"
chmod +x "$BIN_DEST"
echo "✓ Executable 'pr-status' linked to $BIN_DEST"

# 3. Install skill in Antigravity / Gemini CLI skills directory
if [ -d "$HOME/.gemini/config/skills" ]; then
  rm -rf "$SKILL_DEST"
  ln -sf "$SKILL_SRC" "$SKILL_DEST"
  echo "✓ Skill 'pr-status' linked to $SKILL_DEST"
fi

# 4. PATH verification
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
  echo ""
  echo "Note: Make sure ~/.local/bin is in your PATH. Add it with:"
  echo '  export PATH="$HOME/.local/bin:$PATH"'
fi

echo ""
echo "Installation complete!"
echo "Run 'pr-status' to audit your pull requests:"
echo "  pr-status"
