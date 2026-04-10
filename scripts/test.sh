#!/usr/bin/env bash
# Run the full MedSentinel test suite.
# Usage:
#   ./scripts/test.sh             # all tests
#   ./scripts/test.sh -k agents   # filter by keyword
#   ./scripts/test.sh --cov       # with coverage report
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_PYTHON="$ROOT/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
  echo "No virtualenv found at $ROOT/.venv"
  echo "Set it up first:"
  echo "  python3 -m venv .venv && source .venv/bin/activate"
  echo "  pip install -r backend/requirements.txt"
  exit 1
fi

cd "$ROOT"

COV_ARGS=()
PYTEST_ARGS=("$@")

# If --cov flag passed, swap it for the real pytest-cov arguments
for i in "${!PYTEST_ARGS[@]}"; do
  if [[ "${PYTEST_ARGS[$i]}" == "--cov" ]]; then
    unset 'PYTEST_ARGS[$i]'
    COV_ARGS=(--cov=backend --cov-report=term-missing)
  fi
done

MEDSENTINEL_USE_SYNTHETIC_FALLBACKS=true \
  "$VENV_PYTHON" -m pytest tests/ \
    -v \
    --tb=short \
    "${COV_ARGS[@]}" \
    "${PYTEST_ARGS[@]}"
