from __future__ import annotations

import sqlite3
from contextlib import closing

from app.db import case_conn, case_db_path, forget_case

# The case schema exactly as shipped in Fuseline 1.0.0 (no ts_ms / ts_basis / provenance columns).
LEGACY_SCHEMA = """
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE artifacts (
  id TEXT PRIMARY KEY, source_type TEXT NOT NULL, original_name TEXT NOT NULL, stored_path TEXT NOT NULL,
  sha256 TEXT NOT NULL, ingested_at TEXT NOT NULL, row_count INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE events (
  id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL, ts_utc TEXT NOT NULL, ts_original TEXT NOT NULL,
  tz_assumed TEXT NOT NULL DEFAULT 'UTC', source TEXT NOT NULL, event_type TEXT NOT NULL, title TEXT NOT NULL,
  detail_json TEXT NOT NULL DEFAULT '{}', lat REAL, lon REAL, package TEXT, url TEXT, domain TEXT,
  confidence REAL NOT NULL DEFAULT 1.0, FOREIGN KEY (artifact_id) REFERENCES artifacts(id)
);
CREATE INDEX idx_events_ts ON events(ts_utc);
CREATE TABLE sessions (
  id TEXT PRIMARY KEY, start_utc TEXT NOT NULL, end_utc TEXT NOT NULL, score REAL NOT NULL,
  summary TEXT NOT NULL, member_event_ids TEXT NOT NULL, sources TEXT NOT NULL
);
CREATE TABLE validation_findings (
  id TEXT PRIMARY KEY, severity TEXT NOT NULL, code TEXT NOT NULL, message TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def test_a_1_0_case_database_is_migrated_in_place(client, case_id):
    path = case_db_path(case_id)
    path.unlink()
    with closing(sqlite3.connect(path)) as legacy:
        legacy.executescript(LEGACY_SCHEMA)
        legacy.execute(
            "INSERT INTO artifacts VALUES ('a1', 'location', 'old.csv', '/x/old.csv', ?, "
            "'2024-06-15T10:00:00.000Z', 1)",
            ("0" * 64,),
        )
        legacy.execute(
            "INSERT INTO events (id, artifact_id, ts_utc, ts_original, source, event_type, title, lat, lon) "
            "VALUES ('e1', 'a1', '2024-06-15T10:00:00.000Z', 'raw', 'location', 'fix', '12.9, 77.5', 12.9, 77.5)"
        )
        legacy.execute(
            "INSERT INTO sessions VALUES ('s1', '2024-06-15T10:00:00.000Z', '2024-06-15T10:01:00.000Z', 2.0, 'x', "
            "'[\"e1\"]', '[\"location\"]')"
        )
        legacy.commit()
    forget_case(case_id)  # make the app treat the file as not yet migrated

    # The whole read API works against the upgraded database ...
    timeline = client.get(f"/api/cases/{case_id}/timeline").json()
    assert timeline["total"] == 1
    event = timeline["events"][0]
    assert event["ts_ms"] == 1718445600000  # backfilled from ts_utc
    assert event["ts_basis"] == "absolute"  # new column takes its default
    assert client.get(f"/api/cases/{case_id}/overview").json()["total"] == 1
    assert client.get(f"/api/cases/{case_id}/artifacts").json()[0]["skipped_rows"] == 0
    (session,) = client.get(f"/api/cases/{case_id}/sessions").json()
    assert session["event_count"] == 1 and session["centroid_lat"] is None

    # ... and so does writing to it: new evidence ingests alongside the legacy rows.
    upload_csv = b"package,timestamp\ncom.a,2024-06-15T10:00:30Z\n"
    r = client.post(f"/api/cases/{case_id}/acquire", files={"file": ("usage.csv", upload_csv)})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/cases/{case_id}/timeline").json()["total"] == 2


def test_migration_is_idempotent(client, case_id):
    forget_case(case_id)
    with case_conn(case_id) as conn:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
    forget_case(case_id)
    with case_conn(case_id) as conn:  # second run must not try to re-add columns
        assert {row[1] for row in conn.execute("PRAGMA table_info(events)")} == columns
