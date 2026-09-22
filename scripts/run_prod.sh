#!/usr/bin/env bash
# Build the UI once and serve everything (API + UI) from a single process.
# Usage: scripts/run_prod.sh [port]   (set REBUILD=1 to force a UI rebuild)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${1:-8000}"

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi
if ! .venv/bin/python -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Fuseline needs Python 3.11 or newer." >&2
  exit 1
fi
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python scripts/ensure_platform_tools.py || echo "Warning: could not install bundled platform-tools; device import may be unavailable." >&2

if [[ "${REBUILD:-0}" == "1" || ! -f frontend/dist/index.html ]]; then
  echo "Building the UI..."
  (cd frontend && npm ci && npm run build)
fi

echo "Fuseline is running at http://127.0.0.1:${PORT}  (Ctrl+C to stop)"
exec .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --app-dir backend
