#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

if [[ ! -f samples/demo_case/app_usage.db ]]; then
  .venv/bin/python scripts/seed_demo.py
fi

if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install)
fi

.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 --app-dir backend &
API_PID=$!
trap 'kill $API_PID 2>/dev/null || true' EXIT
(cd frontend && npm run dev -- --host 127.0.0.1 --port 5173)