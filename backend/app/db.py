from __future__ import annotations

import sqlite3
import threading
from collections.abc import Iterator
from contextlib import closing, contextmanager, suppress
from pathlib import Path

from app.config import CASES_DIR, REGISTRY_DB, ensure_dirs
from app.security import assert_safe_case_id, assert_under
from app.timeutil import parse_utc, to_epoch_ms

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

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  case_id TEXT,
  actor TEXT NOT NULL DEFAULT '',
  action TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}',
  prev_hash TEXT NOT NULL,
  entry_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_log(case_id, id);
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
  row_count INTEGER NOT NULL DEFAULT 0,
  size_bytes INTEGER NOT NULL DEFAULT 0,
  skipped_rows INTEGER NOT NULL DEFAULT 0,
  parser TEXT NOT NULL DEFAULT '',
  notes TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS events (
  id TEXT PRIMARY KEY,
  artifact_id TEXT NOT NULL,
  ts_utc TEXT NOT NULL,
  ts_ms INTEGER NOT NULL DEFAULT 0,
  ts_original TEXT NOT NULL,
  tz_assumed TEXT NOT NULL DEFAULT 'UTC',
  ts_basis TEXT NOT NULL DEFAULT 'absolute',
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

CREATE TABLE IF NOT EXISTS sessions (
  id TEXT PRIMARY KEY,
  start_utc TEXT NOT NULL,
  end_utc TEXT NOT NULL,
  score REAL NOT NULL,
  summary TEXT NOT NULL,
  member_event_ids TEXT NOT NULL,
  sources TEXT NOT NULL,
  event_count INTEGER NOT NULL DEFAULT 0,
  centroid_lat REAL,
  centroid_lon REAL,
  radius_m REAL
);

CREATE TABLE IF NOT EXISTS validation_findings (
  id TEXT PRIMARY KEY,
  severity TEXT NOT NULL,
  code TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""

# Columns added after the first release, applied to databases created by older versions.
_ADDED_COLUMNS: dict[str, dict[str, str]] = {
    "artifacts": {
        "size_bytes": "INTEGER NOT NULL DEFAULT 0",
        "skipped_rows": "INTEGER NOT NULL DEFAULT 0",
        "parser": "TEXT NOT NULL DEFAULT ''",
        "notes": "TEXT NOT NULL DEFAULT '[]'",
    },
    "events": {
        "ts_ms": "INTEGER NOT NULL DEFAULT 0",
        "ts_basis": "TEXT NOT NULL DEFAULT 'absolute'",
    },
    "sessions": {
        "event_count": "INTEGER NOT NULL DEFAULT 0",
        "centroid_lat": "REAL",
        "centroid_lon": "REAL",
        "radius_m": "REAL",
    },
}

_CASE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_events_ts_ms ON events(ts_ms, id);
CREATE INDEX IF NOT EXISTS idx_events_source_ts ON events(source, ts_ms);
CREATE INDEX IF NOT EXISTS idx_events_artifact ON events(artifact_id);
"""

_migrated: set[str] = set()
_migrate_lock = threading.Lock()


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), check_same_thread=False, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_registry() -> None:
    ensure_dirs()
    with closing(connect(REGISTRY_DB)) as conn:
        conn.executescript(REGISTRY_SCHEMA)
        conn.commit()


def case_db_path(case_id: str) -> Path:
    safe_id = assert_safe_case_id(case_id)
    return assert_under(CASES_DIR / f"{safe_id}.sqlite", CASES_DIR)


def migrate_case(conn: sqlite3.Connection) -> None:
    """Bring a case database created by an older release up to the current schema."""
    for table, columns in _ADDED_COLUMNS.items():
        existing = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({table})")}
        for name, ddl in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
    conn.executescript(_CASE_INDEXES)
    stale = conn.execute("SELECT id, ts_utc FROM events WHERE ts_ms = 0").fetchall()
    for row in stale:
        try:
            ms = to_epoch_ms(parse_utc(row["ts_utc"]))
        except ValueError:
            continue
        conn.execute("UPDATE events SET ts_ms = ? WHERE id = ?", (ms, row["id"]))
    # Pre-existing duplicate hashes would block the unique index; ingest still dedupes in code.
    with suppress(sqlite3.DatabaseError):
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_artifacts_sha256 ON artifacts(sha256)")
    conn.commit()


def init_case_db(case_id: str) -> Path:
    path = case_db_path(case_id)
    with closing(connect(path)) as conn:
        conn.executescript(CASE_SCHEMA)
        migrate_case(conn)
    _migrated.add(str(path))
    return path


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
        key = str(path)
        if key not in _migrated:
            with _migrate_lock:
                if key not in _migrated:
                    migrate_case(conn)
                    _migrated.add(key)
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def forget_case(case_id: str) -> None:
    _migrated.discard(str(case_db_path(case_id)))


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    return dict(row)
