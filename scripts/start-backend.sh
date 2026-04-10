#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "Missing virtualenv at $ROOT_DIR/.venv" >&2
  echo "Create it and install backend dependencies first:" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  source .venv/bin/activate" >&2
  echo "  pip install -r backend/requirements.txt" >&2
  exit 1
fi

cd "$ROOT_DIR"
exec "$VENV_PYTHON" -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
