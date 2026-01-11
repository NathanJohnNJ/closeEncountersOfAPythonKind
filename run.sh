#!/usr/bin/env bash
set -euo pipefail
# Runs the app with the project virtualenv if available.
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Prefer these venv locations (project .env, .venv, venv_alien, temp venv used during testing)
if [ -x "$ROOT_DIR/.env/bin/python" ]; then
  PY="$ROOT_DIR/.env/bin/python"
elif [ -x "$ROOT_DIR/.venv/bin/python" ]; then
  PY="$ROOT_DIR/.venv/bin/python"
elif [ -x "$ROOT_DIR/venv_alien/bin/python" ]; then
  PY="$ROOT_DIR/venv_alien/bin/python"
elif [ -x "/tmp/alien_venv4/bin/python" ]; then
  PY="/tmp/alien_venv4/bin/python"
else
  echo "No virtualenv found. Create one with:"
  echo "  python3 -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -r requirements.txt"
  exit 1
fi
exec "$PY" "$ROOT_DIR/main.py" "$@"
