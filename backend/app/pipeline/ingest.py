from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import SAMPLES_DIR, UPLOADS_DIR
from app.db import case_conn, registry_conn
from app.parsers.registry import parse_artifact
from app.pipeline.correlate import RawEvent, correlate_events
from app.pipeline.normalize import normalize_records
from app.pipeline.validate import findings_with_ids, validate_case
from app.security import assert_safe_case_id, assert_under, sanitize_filename


def _utcnow() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _refresh_registry_counts(case_id: str) -> None:
    with case_conn(case_id) as conn:
        event_count = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        artifact_count = conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    now = _utcnow()
    with registry_conn() as reg:
        reg.execute(
            """
            UPDATE cases
            SET event_count=?, artifact_count=?, session_count=?, updated_at=?
            WHERE id=?
            """,
            (event_count, artifact_count, session_count, now, case_id),
        )


def rebuild_sessions(case_id: str, window_seconds: int = 300) -> int:
    with case_conn(case_id) as conn:
        rows = conn.execute(
            "SELECT id, ts_utc, source, title, package, domain, lat, lon FROM events"
        ).fetchall()
        events = [
            RawEvent(
                id=r["id"],
                ts_utc=r["ts_utc"],
                source=r["source"],
                title=r["title"],
                package=r["package"],
                domain=r["domain"],
                lat=r["lat"],
                lon=r["lon"],
            )
            for r in rows
        ]
        sessions = correlate_events(events, window_seconds=window_seconds)
        conn.execute("DELETE FROM sessions")
        for s in sessions:
            conn.execute(
                """
                INSERT INTO sessions (id, start_utc, end_utc, score, summary, member_event_ids, sources)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    s.id,
                    s.start_utc,
                    s.end_utc,
                    s.score,
                    s.summary,
                    json.dumps(s.member_event_ids),
                    json.dumps(s.sources),
                ),
            )
    _refresh_registry_counts(case_id)
    return len(sessions)


def run_validation(case_id: str, events_added: int | None = None) -> list[dict]:
    with case_conn(case_id) as conn:
        hashes = [r[0] for r in conn.execute("SELECT sha256 FROM artifacts").fetchall()]
        timestamps = [r[0] for r in conn.execute("SELECT ts_utc FROM events").fetchall()]
        source_rows = conn.execute(
            "SELECT source, COUNT(*) FROM events GROUP BY source"
        ).fetchall()
        source_counts = {r[0]: r[1] for r in source_rows}
        total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        findings = validate_case(
            artifact_hashes=hashes,
            event_timestamps=timestamps,
            source_counts=source_counts,
            events_added=total_events if events_added is None else events_added,
        )
        if events_added is None and total_events > 0:
            findings = validate_case(
                artifact_hashes=hashes,
                event_timestamps=timestamps,
                source_counts=source_counts,
                events_added=total_events,
            )
        created = _utcnow()
        rows = findings_with_ids(findings, created)
        conn.execute("DELETE FROM validation_findings")
        for row in rows:
            conn.execute(
                """
                INSERT INTO validation_findings (id, severity, code, message, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (row["id"], row["severity"], row["code"], row["message"], row["created_at"]),
            )
    return rows


def _artifact_payload(row) -> dict:
    return {
        "id": row["id"],
        "source_type": row["source_type"],
        "original_name": row["original_name"],
        "sha256": row["sha256"],
        "ingested_at": row["ingested_at"],
        "row_count": row["row_count"],
    }


def ingest_file(
    case_id: str,
    src_path: Path,
    original_name: str,
    preferred_source: str | None = None,
) -> dict:
    case_id = assert_safe_case_id(case_id)
    safe_name = sanitize_filename(original_name)

    case_upload = assert_under(UPLOADS_DIR / case_id, UPLOADS_DIR)
    case_upload.mkdir(parents=True, exist_ok=True)

    artifact_id = str(uuid.uuid4())
    dest = assert_under(case_upload / f"{artifact_id}_{safe_name}", case_upload)
    shutil.copy2(src_path, dest)
    digest = sha256_file(dest)

    with case_conn(case_id) as conn:
        existing = conn.execute(
            "SELECT * FROM artifacts WHERE sha256=?",
            (digest,),
        ).fetchone()
        if existing:
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            sessions_n = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            findings_rows = conn.execute(
                "SELECT * FROM validation_findings ORDER BY created_at"
            ).fetchall()
            payload = {
                "artifact": _artifact_payload(existing),
                "events_added": 0,
                "sessions_rebuilt": sessions_n,
                "findings": [dict(r) for r in findings_rows],
                "duplicate": True,
            }
            # Fall through after releasing the connection if validation is empty
            if payload["findings"]:
                return payload
            need_validation = True
            cached_payload = payload
        else:
            need_validation = False
            cached_payload = None

    if need_validation and cached_payload is not None:
        cached_payload["findings"] = run_validation(case_id)
        return cached_payload

    parser, records = parse_artifact(dest, preferred_source=preferred_source)

    with registry_conn() as reg:
        row = reg.execute("SELECT timezone FROM cases WHERE id=?", (case_id,)).fetchone()
        if row is None:
            raise FileNotFoundError(f"Case not found: {case_id}")
        tz = row["timezone"] or "UTC"

    records = normalize_records(records, case_timezone=tz)
    now = _utcnow()

    with case_conn(case_id) as conn:
        conn.execute(
            """
            INSERT INTO artifacts (id, source_type, original_name, stored_path, sha256, ingested_at, row_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                parser.source,
                safe_name,
                str(dest),
                digest,
                now,
                len(records),
            ),
        )
        for rec in records:
            conn.execute(
                """
                INSERT INTO events (
                  id, artifact_id, ts_utc, ts_original, tz_assumed, source, event_type,
                  title, detail_json, lat, lon, package, url, domain, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    artifact_id,
                    rec.ts_utc,
                    rec.ts_original,
                    rec.tz_assumed,
                    rec.source,
                    rec.event_type,
                    rec.title,
                    rec.detail_json(),
                    rec.lat,
                    rec.lon,
                    rec.package,
                    rec.url,
                    rec.domain,
                    rec.confidence,
                ),
            )

    sessions_n = rebuild_sessions(case_id)
    findings = run_validation(case_id, events_added=len(records))
    _refresh_registry_counts(case_id)

    return {
        "artifact": {
            "id": artifact_id,
            "source_type": parser.source,
            "original_name": safe_name,
            "sha256": digest,
            "ingested_at": now,
            "row_count": len(records),
        },
        "events_added": len(records),
        "sessions_rebuilt": sessions_n,
        "findings": findings,
        "duplicate": False,
    }


def load_demo_case(case_id: str) -> dict:
    case_id = assert_safe_case_id(case_id)
    if not SAMPLES_DIR.exists():
        raise FileNotFoundError(
            "Sample evidence missing. Run: python scripts/seed_demo.py"
        )

    mapping = [
        ("app_usage.db", "app_usage"),
        ("History", "browsing"),
        ("location.csv", "location"),
        ("plaso_sample.l2t.csv", "plaso"),
    ]
    artifacts = []
    total_events = 0
    findings: list[dict] = []
    sessions_n = 0

    for filename, preferred in mapping:
        path = SAMPLES_DIR / filename
        if not path.exists():
            continue
        result = ingest_file(case_id, path, filename, preferred_source=preferred)
        artifacts.append(result["artifact"])
        total_events += result["events_added"]
        findings = result["findings"]
        sessions_n = result["sessions_rebuilt"]

    if not artifacts:
        raise FileNotFoundError(
            "No sample evidence files found under samples/demo_case. Run: python scripts/seed_demo.py"
        )

    # After a full sample load (including skips), refresh validation against the whole case
    findings = run_validation(case_id)
    sessions_n = rebuild_sessions(case_id)

    return {
        "artifacts": artifacts,
        "events_added": total_events,
        "sessions_rebuilt": sessions_n,
        "findings": findings,
    }
