#!/usr/bin/env bash
# Start the Fuseline API (auto-reload, :8000) and the Vite dev UI (:5173).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Fuseline needs Python 3.11 or newer." >&2
  exit 1
fi

.venv/bin/pip install -q -r requirements-dev.txt

if [[ ! -f samples/demo_case/app_usage.db ]]; then
  .venv/bin/python scripts/seed_demo.py
fi

if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install)
fi

echo "Starting API on http://127.0.0.1:8000 and UI on http://127.0.0.1:5173 (Ctrl+C to stop)..."
.venv/bin/python -m uvicorn app.main:app --reload --reload-dir backend \
  --host 127.0.0.1 --port 8000 --app-dir backend &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173)
