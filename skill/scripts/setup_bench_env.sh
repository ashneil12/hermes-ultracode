#!/usr/bin/env bash
# Set up an isolated venv to run the ultracode BENCHMARK backend.
#
# Why: the core hermes-ultracode harness is stdlib-only (zero deps, runs anywhere).
# ONLY the benchmark client (bench/deepseek_client.py) needs `openai`. Install it in
# a dedicated .venv so it never collides with the system hermes-agent's pinned deps
# (pip will warn about hermes-agent version conflicts — those warnings are harmless,
# the isolated venv is what runs the bench).
#
# Usage:  bash setup_bench_env.sh
# Then:   cd ~/Projects/hermes-ultracode && .venv/bin/python bench/<name>.py
#
# Requires the DeepSeek key at ~/.ultracode-bench/deepseek.env (DEEPSEEK_API_KEY=...).
set -e
REPO="${ULTRACODE_REPO:-$HOME/Projects/hermes-ultracode}"
cd "$REPO"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q "openai>=1.0"
.venv/bin/python -c "import openai; print('openai', openai.__version__, 'ready')"

ENVF="$HOME/.ultracode-bench/deepseek.env"
if [ -f "$ENVF" ]; then
  echo "bench env present: $ENVF"
else
  echo "WARNING: $ENVF missing — set DEEPSEEK_API_KEY there before running benchmarks." >&2
fi

# macOS note: there is no `timeout` binary by default. Run long benchmarks
# backgrounded (terminal background=true) and poll the log, not with `timeout`.
echo "done. Run a bench with: cd $REPO && .venv/bin/python bench/<name>.py"
