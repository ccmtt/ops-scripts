#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "$ROOT_DIR/backend/.venv" ]]; then
  python3 -m venv "$ROOT_DIR/backend/.venv"
fi

"$ROOT_DIR/backend/.venv/bin/pip" install -r "$ROOT_DIR/agents/capture/requirements.txt"

export PYTHONPATH="$ROOT_DIR/backend"
exec "$ROOT_DIR/backend/.venv/bin/uvicorn" agents.capture.app.main:app --host 127.0.0.1 --port 9000
