from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.config import CASES_DIR, REGISTRY_DB
from app.security import assert_safe_case_id, assert_under

REGISTRY_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  examiner TEXT NOT NULL DEFAULT '',
  timezone TEXT NOT NULL DEFAULT 'UTC',
  notes TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  event_count INTEGER NOT NULL DEFAULT 0,
  artifact_count INTEGER NOT NULL DEFAULT 0,
  session_count INTEGER NOT NULL DEFAULT 0
);
"""

CASE_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
  id TEXT PRIMARY KEY,
  source_type TEXT NOT NULL,
  original_name TEXT NOT NULL,
  stored_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  ingested_at TEXT NOT NULL,
  row_count INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL,
  ts_utc TEXT NOT NULL,
  ts_original TEXT NOT NULL,
  tz_assumed TEXT NOT NULL DEFAULT 'UTC',
  source TEXT NOT NULL,
  event_type TEXT NOT NULL,
  title TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  lat REAL,
  lon REAL,
  package TEXT,
  url TEXT,
  domain TEXT,
  confidence REAL NOT NULL DEFAULT 1.0,
  FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts_utc);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256);

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  start_utc TEXT NOT NULL,
  end_utc TEXT NOT NULL,
  score REAL NOT NULL,
  summary TEXT NOT NULL,
  member_event_ids TEXT NOT NULL,
  sources TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS validation_findings (
  id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_registry() -> None:
    with connect(REGISTRY_DB) as conn:
        conn.executescript(REGISTRY_SCHEMA)
        conn.commit()


def case_db_path(case_id: str) -> Path:
    safe_id = assert_safe_case_id(case_id)
    path = CASES_DIR / f"{safe_id}.sqlite"
    return assert_under(path, CASES_DIR)


def init_case_db(case_id: str) -> Path:
    path = case_db_path(case_id)
    with connect(path) as conn:
        conn.executescript(CASE_SCHEMA)
        conn.commit()
    return path


def ensure_case_indexes(conn: sqlite3.Connection) -> None:
    """Apply indexes for DBs created before schema updates."""
    try:
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256)"
        )
    except sqlite3.OperationalError:
        # Existing duplicate hashes block unique index creation; ingest still checks in code.
        pass


@contextmanager
def registry_conn() -> Iterator[sqlite3.Connection]:
    init_registry()
    conn = connect(REGISTRY_DB)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def case_conn(case_id: str) -> Iterator[sqlite3.Connection]:
    path = case_db_path(case_id)
    if not path.exists():
        raise FileNotFoundError(f"Case database not found: {case_id}")
    conn = connect(path)
    try:
        ensure_case_indexes(conn)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)