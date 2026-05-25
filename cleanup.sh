#!/usr/bin/env bash
set -euo pipefail

UV_BIN="${UV_BIN:-}"
if [[ -z "$UV_BIN" ]]; then
  UV_BIN="$(command -v uv || true)"
fi
if [[ -z "$UV_BIN" && -x "/home/v/.local/bin/uv" ]]; then
  UV_BIN="/home/v/.local/bin/uv"
fi
if [[ -z "$UV_BIN" ]]; then
  echo "uv not found on PATH and /home/v/.local/bin/uv is unavailable" >&2
  exit 127
fi

find . -type d -name __pycache__ -prune -exec rm -rf {} +
"$UV_BIN" run ruff check --fix *.py
"$UV_BIN" run ty check --error-on-warning *.py
