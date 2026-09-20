from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
CASES_DIR = DATA_DIR / "cases"
UPLOADS_DIR = DATA_DIR / "uploads"
SAMPLES_DIR = PROJECT_ROOT / "samples" / "demo_case"
REGISTRY_DB = DATA_DIR / "registry.sqlite"

DEFAULT_CORRELATION_WINDOW_SECONDS = 300
DEFAULT_TIMEZONE = "UTC"
MAX_UPLOAD_BYTES = 64 * 1024 * 1024

CASES_DIR.mkdir(parents=True, exist_ok=True)
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)