#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$ROOT/.venv/bin/python"
export GIGAAM_CACHE="${GIGAAM_CACHE:-$ROOT/.cache}"

if [[ ! -x "$VENV" ]]; then
  echo "Нет $VENV — сначала ./install.sh" >&2
  exit 1
fi

if [[ "${1:-}" == "--preload" ]]; then
  shift
  exec "$VENV" "$ROOT/preload.py" "$@"
fi

exec "$VENV" "$ROOT/transcribe_dialogue.py" "$@"
