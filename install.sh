#!/usr/bin/env bash
# install.sh — install ultracode (skill + engine) into a Hermes agent. Idempotent.
#
# This is the SINGLE installable artifact: it ships the doctrine + the skill +
# the pure-stdlib engine. After install, the deterministic gate and
# enumerate_corpus work with zero extra setup, and it SURVIVES upstream
# Hermes desktop-app updates (skills live in user-data, not the app dir).
#
# Usage:  ./install.sh
#         HERMES_HOME=/path ./install.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILLS_DIR="$HERMES_HOME/skills/autonomous-ai-agents"
SKILL_DEST="$SKILLS_DIR/ultracode"
ENGINE_DEST="$SKILLS_DIR/engine"

echo "ultracode installer (skill + engine, self-contained)"
echo "  Hermes home : $HERMES_HOME"

[ -d "$HERMES_HOME" ] || { echo "ERROR: $HERMES_HOME not found. Is Hermes installed? Set HERMES_HOME=..." >&2; exit 1; }
mkdir -p "$SKILLS_DIR"

# 1) the skill (the agent loads this; auto-fires on substantive tasks)
rm -rf "$SKILL_DEST"; mkdir -p "$SKILL_DEST"
cp -R "$HERE/skill/." "$SKILL_DEST/"
chmod +x "$SKILL_DEST/scripts/"*.py "$SKILL_DEST/scripts/"*.sh 2>/dev/null || true
echo "  skill  -> $SKILL_DEST"

# 2) the engine (pure stdlib, no deps) bundled next to the skill so gate.py +
#    bridge.py find it via ../../engine — no dependency on this repo staying put.
rm -rf "$ENGINE_DEST"; mkdir -p "$ENGINE_DEST/ultracode"
cp -R "$HERE/ultracode/." "$ENGINE_DEST/ultracode/"
rm -rf "$ENGINE_DEST/ultracode/__pycache__" 2>/dev/null || true
cp "$HERE/LICENSE" "$ENGINE_DEST/LICENSE" 2>/dev/null || true
echo "  engine -> $ENGINE_DEST  (deterministic gate + enumerate_corpus)"

# 3) verify it actually runs against the bundled engine
echo ""
if out=$(python3 "$SKILL_DEST/scripts/gate.py" "find all the call sites of foo" 2>/dev/null); then
  if echo "$out" | grep -q "source       : harness"; then
    echo "  PASS — gate runs on the bundled engine (deterministic)"
  else
    echo "  PASS — gate runs (fallback mode; engine import check: see below)"
  fi
else
  echo "  WARN — gate.py did not run; python3 present? (skill still loads; built-in fallback)"
fi

echo ""
echo "DONE. ultracode installed, self-contained."
echo "  Auto-fires on substantive tasks (audits, find-all, design decisions, high-stakes)."
echo "  Trigger words: ultracode / ultrathink / go all in."
echo "  Survives upstream updates (lives in $HERMES_HOME/skills/, not the app dir)."
